"""
handlers/media.py
-----------------
Handles incoming media files (audio, video, voice, video notes, documents).

Flow:
  1. User sends a media file
  2. Bot checks file size and format
  3. Bot asks: source language?
  4. Bot asks: target language?
  5. Bot asks: output format?
  6. File is downloaded and queued for transcription

State is stored in a dict keyed by (user_id, chat_id) to manage
the multi-step conversation flow without a database.
"""

import logging
import os
import uuid
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

from config import Config
from keyboards.inline import language_keyboard, output_format_keyboard
from utils.decorators import authorized_only
from services.audio_extractor import AudioExtractor

logger = logging.getLogger(__name__)

# In-memory state store: user_id → state dict
# Keys: file_path, file_name, file_type, source_language, target_language, status_msg_id
_user_state: dict[int, dict] = {}


def register_media_handlers(app: Client, db, queue_manager):
    """Register all media-related handlers."""

    async def _handle_media(client: Client, message: Message, db):
        """Common handler for all supported media types."""
        user_id = message.from_user.id
        chat_id = message.chat.id

        # ── Identify the media ────────────────────────────────────────────
        media = None
        file_name = None
        file_size = 0
        file_type = "audio"

        if message.audio:
            media = message.audio
            file_name = media.file_name or f"audio_{media.file_id}.mp3"
            file_size = media.file_size or 0
            file_type = "audio"

        elif message.video:
            media = message.video
            file_name = media.file_name or f"video_{media.file_id}.mp4"
            file_size = media.file_size or 0
            file_type = "video"

        elif message.voice:
            media = message.voice
            file_name = f"voice_{media.file_id}.ogg"
            file_size = media.file_size or 0
            file_type = "audio"

        elif message.video_note:
            media = message.video_note
            file_name = f"videonote_{media.file_id}.mp4"
            file_size = media.file_size or 0
            file_type = "video"

        elif message.document:
            media = message.document
            file_name = media.file_name or f"file_{media.file_id}"
            file_size = media.file_size or 0
            ext = Path(file_name).suffix.lower()
            if ext in Config.VIDEO_EXTENSIONS:
                file_type = "video"
            elif ext in Config.AUDIO_EXTENSIONS:
                file_type = "audio"
            else:
                await message.reply(
                    f"❌ **Unsupported Format!**\n\n"
                    f"File: `{file_name}`\n\n"
                    f"Supported audio: mp3, wav, m4a, flac, ogg, opus, aac, wma...\n"
                    f"Supported video: mp4, mkv, avi, mov, webm, flv..."
                )
                return
        else:
            return  # Ignore non-media messages

        # ── File size check ───────────────────────────────────────────────
        max_bytes = Config.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            await message.reply(
                f"❌ **File Too Large!**\n\n"
                f"Maximum allowed: {Config.MAX_FILE_SIZE_MB} MB\n"
                f"Your file: {file_size / (1024*1024):.1f} MB"
            )
            return

        # ── Store state ───────────────────────────────────────────────────
        _user_state[user_id] = {
            "stage": "src_lang",
            "file_id": media.file_id,
            "file_name": file_name,
            "file_type": file_type,
            "file_size": file_size,
            "chat_id": chat_id,
            "source_language": None,
            "target_language": None,
            "output_format": None,
        }

        # ── Ask source language ───────────────────────────────────────────
        emoji = "🎬" if file_type == "video" else "🎵"
        await message.reply(
            f"{emoji} **File Received!**\n\n"
            f"📄 File: `{file_name}`\n"
            f"📦 Size: {file_size / (1024*1024):.1f} MB\n\n"
            f"**Audio/Video kis language mein hai?**",
            reply_markup=language_keyboard("src_lang"),
        )

    # ─── Register filters ─────────────────────────────────────────────────────

    @app.on_message(filters.private & filters.audio)
    @authorized_only(db)
    async def audio_handler(client, message, db):
        await _handle_media(client, message, db)

    @app.on_message(filters.private & filters.video)
    @authorized_only(db)
    async def video_handler(client, message, db):
        await _handle_media(client, message, db)

    @app.on_message(filters.private & filters.voice)
    @authorized_only(db)
    async def voice_handler(client, message, db):
        await _handle_media(client, message, db)

    @app.on_message(filters.private & filters.video_note)
    @authorized_only(db)
    async def video_note_handler(client, message, db):
        await _handle_media(client, message, db)

    @app.on_message(filters.private & filters.document)
    @authorized_only(db)
    async def document_handler(client, message, db):
        await _handle_media(client, message, db)

    # ─── Callback: Source Language ────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^src_lang:(.+)$"))
    @authorized_only(db)
    async def src_lang_callback(client: Client, callback: CallbackQuery, db):
        user_id = callback.from_user.id
        lang_code = callback.matches[0].group(1)

        state = _user_state.get(user_id)
        if not state or state.get("stage") != "src_lang":
            await callback.answer("Session expired. File dobara bhejein.", show_alert=True)
            return

        lang_info = Config.LANGUAGES.get(lang_code, ("", lang_code))
        lang_display = f"{lang_info[0]} {lang_info[1]}"

        state["source_language"] = lang_code
        state["stage"] = "tgt_lang"

        await callback.message.edit_text(
            f"✅ Source language: **{lang_display}**\n\n"
            f"**Transcript kis language mein chahiye?**",
            reply_markup=language_keyboard("tgt_lang"),
        )
        await callback.answer()

    # ─── Callback: Target Language ────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^tgt_lang:(.+)$"))
    @authorized_only(db)
    async def tgt_lang_callback(client: Client, callback: CallbackQuery, db):
        user_id = callback.from_user.id
        lang_code = callback.matches[0].group(1)

        state = _user_state.get(user_id)
        if not state or state.get("stage") != "tgt_lang":
            await callback.answer("Session expired. File dobara bhejein.", show_alert=True)
            return

        lang_info = Config.LANGUAGES.get(lang_code, ("", lang_code))
        lang_display = f"{lang_info[0]} {lang_info[1]}"

        state["target_language"] = lang_code
        state["stage"] = "output_fmt"

        await callback.message.edit_text(
            f"✅ Output language: **{lang_display}**\n\n"
            f"**Output format kya chahiye?**",
            reply_markup=output_format_keyboard(),
        )
        await callback.answer()

    # ─── Callback: Output Format → Queue job ─────────────────────────────────

    @app.on_callback_query(filters.regex(r"^output_fmt:(.+)$"))
    @authorized_only(db)
    async def output_fmt_callback(client: Client, callback: CallbackQuery, db):
        user_id = callback.from_user.id
        fmt = callback.matches[0].group(1)

        state = _user_state.get(user_id)
        if not state or state.get("stage") != "output_fmt":
            await callback.answer("Session expired. File dobara bhejein.", show_alert=True)
            return

        state["output_format"] = fmt
        state["stage"] = "downloading"

        fmt_label = Config.OUTPUT_FORMATS.get(fmt, fmt)
        await callback.message.edit_text(
            f"✅ Output format: **{fmt_label}**\n\n"
            f"⬇️ **Downloading...**\n`{state['file_name']}`"
        )
        await callback.answer()

        # ── Download file ─────────────────────────────────────────────────
        try:
            job_id = str(uuid.uuid4())
            download_path = os.path.join(
                Config.DOWNLOADS_DIR,
                f"{job_id}{Path(state['file_name']).suffix or '.tmp'}"
            )

            # Progress bar for download
            last_pct = [0]

            async def download_progress(current, total):
                if total:
                    pct = int((current / total) * 100)
                    if pct - last_pct[0] >= 20:
                        last_pct[0] = pct
                        bar = "▓" * (pct // 10) + "░" * (10 - pct // 10)
                        try:
                            await callback.message.edit_text(
                                f"⬇️ **Downloading...**\n"
                                f"`{state['file_name']}`\n"
                                f"[{bar}] {pct}%"
                            )
                        except Exception:
                            pass

            await client.download_media(
                state["file_id"],
                file_name=download_path,
                progress=download_progress,
            )

            if not os.path.exists(download_path):
                raise RuntimeError("Download failed — file not found after download")

            # ── Enqueue job ───────────────────────────────────────────────
            from services.queue_manager import TranscriptionJob

            job = TranscriptionJob(
                job_id=job_id,
                user_id=user_id,
                chat_id=state["chat_id"],
                message_id=callback.message.id,
                file_path=download_path,
                file_name=state["file_name"],
                file_type=state["file_type"],
                source_language=state["source_language"],
                target_language=state["target_language"],
                output_format=state["output_format"],
            )

            position = await queue_manager.enqueue(job)

            queue_msg = ""
            if position > 1:
                queue_msg = f"\n\n⏳ Queue position: **{position}**"

            await callback.message.edit_text(
                f"✅ **Queued for Processing!**\n\n"
                f"📄 File: `{state['file_name']}`\n"
                f"🌐 Source: {Config.LANGUAGES.get(state['source_language'], ('', state['source_language']))[1]}\n"
                f"🎯 Target: {Config.LANGUAGES.get(state['target_language'], ('', state['target_language']))[1]}\n"
                f"📋 Format: {Config.OUTPUT_FORMATS.get(fmt, fmt)}"
                f"{queue_msg}"
            )

        except Exception as e:
            logger.exception(f"Download/queue error for user {user_id}: {e}")
            await callback.message.edit_text(
                f"❌ **Error!**\n\n`{str(e)[:300]}`\n\nDobara try karein."
            )
        finally:
            # Clean up state
            _user_state.pop(user_id, None)

    # ─── Cancel ───────────────────────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^cancel$"))
    async def cancel_callback(client: Client, callback: CallbackQuery):
        user_id = callback.from_user.id
        _user_state.pop(user_id, None)
        await callback.message.edit_text("❌ **Cancelled.**")
        await callback.answer()
