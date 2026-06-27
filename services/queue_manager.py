"""
services/queue_manager.py
--------------------------
Async job queue for processing transcription requests.

Uses asyncio.Queue to ensure:
  - Jobs are processed in order (FIFO)
  - Configurable concurrent processing slots
  - Progress updates sent back to users
  - Clean error handling per job
  - No blocking of the main bot thread

Each job is a TranscriptionJob dataclass that carries all the
information needed to process a media file end-to-end.
"""

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionJob:
    """Represents a single transcription task."""
    job_id: str
    user_id: int
    chat_id: int
    message_id: int          # The "Processing..." message to edit
    file_path: str           # Path to the downloaded media file
    file_name: str           # Original file name for display
    file_type: str           # "audio" or "video"
    source_language: str     # ISO code or "auto"
    target_language: str     # ISO code or "auto"
    output_format: str       # "message", "txt", "srt", "vtt"
    created_at: float = field(default_factory=time.time)


class QueueManager:
    """
    Manages the transcription job queue.
    Spawns worker coroutines up to MAX_CONCURRENT_JOBS.
    """

    def __init__(self):
        self._queue: asyncio.Queue[TranscriptionJob] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._app = None
        self._db = None
        # Track queue position: job_id → position
        self._pending: dict[str, int] = {}

    async def start(self, app, db):
        """Start worker coroutines."""
        self._app = app
        self._db = db
        self._running = True

        for i in range(Config.MAX_CONCURRENT_JOBS):
            task = asyncio.create_task(self._worker(i), name=f"worker-{i}")
            self._workers.append(task)

        logger.info(f"Queue started with {Config.MAX_CONCURRENT_JOBS} workers.")

    async def stop(self):
        """Gracefully stop all workers."""
        self._running = False
        # Poison pill — one per worker
        for _ in self._workers:
            await self._queue.put(None)
        for task in self._workers:
            try:
                await asyncio.wait_for(task, timeout=30)
            except asyncio.TimeoutError:
                task.cancel()
        logger.info("Queue stopped.")

    async def enqueue(self, job: TranscriptionJob) -> int:
        """
        Add a job to the queue.
        Returns the estimated queue position (1 = next up).
        """
        await self._queue.put(job)
        position = self._queue.qsize()
        self._pending[job.job_id] = position
        logger.info(f"Job {job.job_id} enqueued. Position: {position}")
        return position

    def queue_size(self) -> int:
        """Current number of pending jobs."""
        return self._queue.qsize()

    async def _worker(self, worker_id: int):
        """Worker loop — processes jobs sequentially."""
        logger.info(f"Worker {worker_id} started.")

        while self._running:
            try:
                job = await self._queue.get()
            except asyncio.CancelledError:
                break

            if job is None:  # Poison pill
                self._queue.task_done()
                break

            try:
                await self._process_job(job)
            except Exception as e:
                logger.exception(f"Worker {worker_id} error processing job {job.job_id}: {e}")
                try:
                    await self._send_error(job, str(e))
                except Exception:
                    pass
            finally:
                self._queue.task_done()
                self._pending.pop(job.job_id, None)

        logger.info(f"Worker {worker_id} stopped.")

    async def _process_job(self, job: TranscriptionJob):
        """End-to-end processing of a single transcription job."""
        from services.audio_extractor import AudioExtractor
        from services.transcriber import Transcriber
        from utils.text_utils import smart_split
        from utils.cleanup import cleanup_files

        start_time = time.time()
        wav_path = None

        try:
            # ── Step 1: Extract/convert audio ──────────────────────────────
            await self._update_status(job, "🔄 **Processing...**\n\n🎵 Audio extract kar raha hoon...")

            wav_path = os.path.join(
                Config.TEMP_DIR,
                f"{job.job_id}.wav"
            )

            await AudioExtractor.extract_audio(job.file_path, wav_path)

            # Get duration
            duration = await AudioExtractor.get_duration(wav_path)

            # ── Step 2: Transcribe ──────────────────────────────────────────
            await self._update_status(job, "🔄 **Processing...**\n\n🎙 Transcription chal rahi hai...\n(yeh thoda time le sakta hai)")

            progress_sent = [0]

            async def on_progress(pct: int):
                if pct - progress_sent[0] >= 20:
                    progress_sent[0] = pct
                    bar = "▓" * (pct // 10) + "░" * (10 - pct // 10)
                    await self._update_status(
                        job,
                        f"🔄 **Processing...**\n\n🎙 Transcribing...\n[{bar}] {pct}%"
                    )

            result = await Transcriber.transcribe(
                audio_path=wav_path,
                source_language=job.source_language if job.source_language != "auto" else None,
                target_language=job.target_language if job.target_language != "auto" else None,
                progress_callback=on_progress,
            )

            elapsed = time.time() - start_time
            elapsed_str = self._format_duration(elapsed)
            duration_str = self._format_duration(duration)
            lang_name = self._get_lang_name(result.detected_language)

            # ── Step 3: Format and deliver output ──────────────────────────
            await self._update_status(job, "✅ Done! Output prepare ho raha hai...")

            if job.output_format == "message":
                chunks = smart_split(result.text, Config.MAX_MESSAGE_LENGTH)
                # Send completion header
                header = (
                    f"✅ **Transcript Ready!**\n\n"
                    f"📄 File: `{job.file_name}`\n"
                    f"🌐 Language: {lang_name}\n"
                    f"⏱ Duration: {duration_str}\n"
                    f"⏳ Processing Time: {elapsed_str}\n"
                    f"📝 Parts: {len(chunks)}\n"
                    f"{'─'*30}"
                )
                await self._app.edit_message_text(job.chat_id, job.message_id, header)
                for i, chunk in enumerate(chunks, 1):
                    part_header = f"**Part {i}/{len(chunks)}:**\n\n" if len(chunks) > 1 else ""
                    await self._app.send_message(job.chat_id, f"{part_header}{chunk}")

            elif job.output_format == "txt":
                out_path = os.path.join(Config.OUTPUTS_DIR, f"{job.job_id}.txt")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(result.text)
                caption = (
                    f"✅ **Transcript Ready!**\n\n"
                    f"📄 File: `{job.file_name}`\n"
                    f"🌐 Language: {lang_name}\n"
                    f"⏱ Duration: {duration_str}\n"
                    f"⏳ Processing Time: {elapsed_str}"
                )
                await self._app.edit_message_text(job.chat_id, job.message_id, "📤 File bhej raha hoon...")
                await self._app.send_document(
                    job.chat_id,
                    out_path,
                    caption=caption,
                    file_name=f"transcript_{Path(job.file_name).stem}.txt",
                )
                os.remove(out_path)

            elif job.output_format == "srt":
                srt_content = Transcriber.generate_srt(result.segments)
                out_path = os.path.join(Config.OUTPUTS_DIR, f"{job.job_id}.srt")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(srt_content)
                caption = (
                    f"✅ **Transcript Ready!**\n\n"
                    f"📄 File: `{job.file_name}`\n"
                    f"🌐 Language: {lang_name}\n"
                    f"⏱ Duration: {duration_str}\n"
                    f"⏳ Processing Time: {elapsed_str}"
                )
                await self._app.edit_message_text(job.chat_id, job.message_id, "📤 File bhej raha hoon...")
                await self._app.send_document(
                    job.chat_id,
                    out_path,
                    caption=caption,
                    file_name=f"transcript_{Path(job.file_name).stem}.srt",
                )
                os.remove(out_path)

            elif job.output_format == "vtt":
                vtt_content = Transcriber.generate_vtt(result.segments)
                out_path = os.path.join(Config.OUTPUTS_DIR, f"{job.job_id}.vtt")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(vtt_content)
                caption = (
                    f"✅ **Transcript Ready!**\n\n"
                    f"📄 File: `{job.file_name}`\n"
                    f"🌐 Language: {lang_name}\n"
                    f"⏱ Duration: {duration_str}\n"
                    f"⏳ Processing Time: {elapsed_str}"
                )
                await self._app.edit_message_text(job.chat_id, job.message_id, "📤 File bhej raha hoon...")
                await self._app.send_document(
                    job.chat_id,
                    out_path,
                    caption=caption,
                    file_name=f"transcript_{Path(job.file_name).stem}.vtt",
                )
                os.remove(out_path)

            # ── Step 4: Save to DB ──────────────────────────────────────────
            await self._db.add_history(job.user_id, {
                "file_name": job.file_name,
                "file_type": job.file_type,
                "source_language": result.detected_language,
                "target_language": job.target_language,
                "output_format": job.output_format,
                "duration": duration,
                "processing_time": elapsed,
                "transcript_preview": result.text[:200],
            })

            is_video = job.file_type == "video"
            await self._db.increment_stat("total_transcripts")
            await self._db.increment_stat("total_duration_secs", duration)
            if is_video:
                await self._db.increment_stat("total_videos")
            else:
                await self._db.increment_stat("total_audios")
            await self._db.record_daily_analytics(is_video, duration)

        finally:
            # ── Cleanup ─────────────────────────────────────────────────────
            files_to_clean = [f for f in [job.file_path, wav_path] if f]
            await cleanup_files(files_to_clean)

    async def _update_status(self, job: TranscriptionJob, text: str):
        """Edit the processing status message."""
        try:
            await self._app.edit_message_text(
                job.chat_id,
                job.message_id,
                text,
            )
        except Exception as e:
            logger.debug(f"Could not update status message: {e}")

    async def _send_error(self, job: TranscriptionJob, error: str):
        """Notify user of processing error."""
        try:
            await self._app.edit_message_text(
                job.chat_id,
                job.message_id,
                f"❌ **Processing Failed!**\n\n"
                f"📄 File: `{job.file_name}`\n"
                f"🔴 Error: `{error[:300]}`\n\n"
                f"Dobara try karein ya owner se contact karein: {Config.OWNER_USERNAME}",
            )
        except Exception:
            pass

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds into human-readable duration."""
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}h {m}m {s}s"
        elif m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

    @staticmethod
    def _get_lang_name(code: str) -> str:
        """Get display name for a language code."""
        lang = Config.LANGUAGES.get(code, ("", code))
        return f"{lang[0]} {lang[1]}"
          
