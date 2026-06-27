"""
services/transcriber.py
------------------------
Whisper Large-v3 transcription engine.

Uses faster-whisper (CTranslate2 backend) for production-grade performance.
Supports:
  - Language detection
  - Transcription in original language
  - Translation to any target language (via Whisper's built-in translation)
  - SRT and VTT subtitle generation
  - Plain text output
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Segment:
    """A single transcript segment with timing information."""
    start: float       # seconds
    end: float         # seconds
    text: str          # transcript text


@dataclass
class TranscriptResult:
    """Full transcription result returned by the engine."""
    text: str                          # Full concatenated transcript
    segments: list[Segment]           # Individual timed segments
    detected_language: str            # ISO language code
    duration: float                   # Audio duration in seconds


class Transcriber:
    """
    Singleton-style Whisper transcription engine.
    Model is loaded once at startup to avoid repeated disk I/O.
    """

    _model = None

    @classmethod
    def load_model(cls):
        """Load the Whisper model into memory. Call once at startup."""
        if cls._model is not None:
            return  # Already loaded

        from faster_whisper import WhisperModel
        from config import Config

        logger.info(f"Loading Whisper model: {Config.WHISPER_MODEL} "
                    f"(device={Config.WHISPER_DEVICE}, compute_type={Config.WHISPER_COMPUTE_TYPE})")

        cls._model = WhisperModel(
            Config.WHISPER_MODEL,
            device=Config.WHISPER_DEVICE,
            compute_type=Config.WHISPER_COMPUTE_TYPE,
            num_workers=2,
        )
        logger.info("Whisper model loaded successfully.")

    @classmethod
    async def transcribe(
        cls,
        audio_path: str,
        source_language: Optional[str] = None,   # None → auto detect
        target_language: Optional[str] = None,   # None → same as source
        progress_callback=None,
    ) -> TranscriptResult:
        """
        Transcribe audio file using Whisper Large-v3.

        Args:
            audio_path      : Path to the audio file (WAV/MP3/etc.)
            source_language : ISO 639-1 code or None for auto-detect
            target_language : ISO 639-1 code or None for no translation
            progress_callback: Async callable(percent: int) for progress updates

        Returns:
            TranscriptResult with full text, segments, language, and duration
        """
        if cls._model is None:
            cls.load_model()

        import asyncio

        # Determine Whisper task
        task = "transcribe"
        translate_target = None

        if target_language and target_language != "auto":
            if source_language != target_language:
                # Whisper natively translates TO English; for other targets we
                # transcribe first then translate separately via Whisper's
                # translation pass or post-process.
                if target_language == "en":
                    task = "translate"   # Whisper built-in: any → English
                else:
                    task = "transcribe"  # We'll handle translation post-transcription
                    translate_target = target_language

        logger.debug(f"Starting transcription: {audio_path}, lang={source_language}, task={task}")

        # Run synchronous Whisper in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result_data = await loop.run_in_executor(
            None,
            lambda: cls._run_whisper(
                audio_path,
                source_language if source_language != "auto" else None,
                task,
            )
        )

        raw_segments, info = result_data

        # Build segment list
        segments = []
        full_text_parts = []
        total_duration = info.duration

        for i, seg in enumerate(raw_segments):
            segments.append(Segment(
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
            ))
            full_text_parts.append(seg.text.strip())

            # Report progress every 10 segments
            if progress_callback and i % 10 == 0:
                progress = min(int((seg.end / total_duration) * 100), 99)
                try:
                    await progress_callback(progress)
                except Exception:
                    pass

        full_text = " ".join(full_text_parts)
        detected_language = info.language

        # Post-transcription translation for non-English targets
        if translate_target and translate_target != detected_language:
            logger.debug(f"Post-translating from {detected_language} to {translate_target}")
            full_text, segments = await cls._translate_segments(
                segments, detected_language, translate_target
            )

        if progress_callback:
            try:
                await progress_callback(100)
            except Exception:
                pass

        return TranscriptResult(
            text=full_text,
            segments=segments,
            detected_language=detected_language,
            duration=total_duration,
        )

    @classmethod
    def _run_whisper(cls, audio_path: str, language: Optional[str], task: str):
        """Synchronous Whisper call (runs in thread executor)."""
        segments_generator, info = cls._model.transcribe(
            audio_path,
            language=language,
            task=task,
            beam_size=5,
            best_of=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            word_timestamps=True,
        )
        # Materialize the generator (must happen in this thread)
        segments_list = list(segments_generator)
        return segments_list, info

    @classmethod
    async def _translate_segments(
        cls,
        segments: list[Segment],
        source_lang: str,
        target_lang: str,
    ) -> tuple[str, list[Segment]]:
        """
        Translate segment texts using Argos Translate for non-English targets.
        Falls back to text-only translation if Argos unavailable.
        """
        try:
            import argostranslate.package
            import argostranslate.translate
            import asyncio

            loop = asyncio.get_event_loop()

            def translate_text(text, src, tgt):
                # Argos uses ISO 639-1 codes
                src_code = src[:2]
                tgt_code = tgt[:2]
                try:
                    translated = argostranslate.translate.translate(text, src_code, tgt_code)
                    return translated
                except Exception:
                    return text  # Return original if translation fails

            translated_segments = []
            all_texts = []
            for seg in segments:
                t_text = await loop.run_in_executor(
                    None, translate_text, seg.text, source_lang, target_lang
                )
                translated_segments.append(Segment(
                    start=seg.start,
                    end=seg.end,
                    text=t_text,
                ))
                all_texts.append(t_text)

            return " ".join(all_texts), translated_segments

        except ImportError:
            logger.warning("argostranslate not installed — returning original transcription")
            return " ".join(seg.text for seg in segments), segments

    @classmethod
    def generate_srt(cls, segments: list[Segment]) -> str:
        """Generate SRT subtitle content from segments."""
        lines = []
        for i, seg in enumerate(segments, 1):
            start = cls._format_srt_time(seg.start)
            end = cls._format_srt_time(seg.end)
            lines.append(f"{i}\n{start} --> {end}\n{seg.text}\n")
        return "\n".join(lines)

    @classmethod
    def generate_vtt(cls, segments: list[Segment]) -> str:
        """Generate WebVTT subtitle content from segments."""
        lines = ["WEBVTT\n"]
        for i, seg in enumerate(segments, 1):
            start = cls._format_vtt_time(seg.start)
            end = cls._format_vtt_time(seg.end)
            lines.append(f"{i}\n{start} --> {end}\n{seg.text}\n")
        return "\n".join(lines)

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """Convert seconds to SRT timestamp: HH:MM:SS,mmm"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _format_vtt_time(seconds: float) -> str:
        """Convert seconds to VTT timestamp: HH:MM:SS.mmm"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
          
