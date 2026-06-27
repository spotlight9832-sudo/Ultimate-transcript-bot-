"""
handlers/user.py
----------------
User-facing commands:
  /history   — View personal transcript history
  /stats     — View personal statistics
  /translate — Translate text to another language
"""

import logging

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

from config import Config
from keyboards.inline import translate_language_keyboard
from utils.decorators import authorized_only
from utils.text_utils import format_duration, smart_split

logger = logging.getLogger(__name__)

# State store for /translate flow: user_id → text to translate
_translate_state: dict[int, str] = {}


def register_user_handlers(app: Client, db, queue_manager):
    """Register user command handlers."""

    # ─── /history ────────────────────────────────────────────────────────────

    @app.on_message(filters.command("history") & filters.private)
    @authorized_only(db)
    async def history_cmd(client: Client, message: Message, db):
        user_id = message.from_user.id
        history = await db.get_user_history(user_id, limit=20)

        if not history:
            await message.reply("📋 Aapki abhi tak koi transcript history nahi hai.")
            return

        lines = ["📋 **Aapki Transcript History:**\n"]
        for i, entry in enumerate(history, 1):
            fname = entry.get("file_name", "Unknown")
            ftype = entry.get("file_type", "?")
            created = entry.get("created_at")
            date_str = created.strftime("%d %b %Y") if created else "Unknown"
            duration = entry.get("duration", 0)
            emoji = "🎬" if ftype == "video" else "🎵"
            lines.append(f"{i}. {emoji} `{fname}` — {date_str} ({format_duration(duration)})")

        await message.reply("\n".join(lines))

    # ─── /stats (User) ────────────────────────────────────────────────────────

    @app.on_message(filters.command("stats") & filters.private)
    @authorized_only(db)
    async def user_stats_cmd(client: Client, message: Message, db):
        user_id = message.from_user.id

        # If owner, redirect to admin stats
        if user_id == Config.OWNER_ID:
            # Handled by admin handler which also matches /stats
            return

        user_doc = await db.get_user(user_id)
        history = await db.get_user_history(user_id, limit=1000)

        total = len(history)
        videos = sum(1 for h in history if h.get("file_type") == "video")
        audios = sum(1 for h in history if h.get("file_type") == "audio")
        total_duration = sum(h.get("duration", 0) for h in history)

        name = user_doc.get("name", "User") if user_doc else "User"

        await message.reply(
            f"📊 **Aapki Statistics**\n\n"
            f"👤 Name: {name}\n\n"
            f"🎙 Total Transcripts: {total}\n"
            f"🎥 Videos Processed: {videos}\n"
            f"🎵 Audios Processed: {audios}\n"
            f"⏳ Total Processed Duration: {format_duration(total_duration)}"
        )

    # ─── /translate ───────────────────────────────────────────────────────────

    @app.on_message(filters.command("translate") & filters.private)
    @authorized_only(db)
    async def translate_cmd(client: Client, message: Message, db):
        user_id = message.from_user.id

        # Check if text was provided inline: /translate Hello World
        if len(message.command) > 1:
            text = message.text.split(None, 1)[1].strip()
        elif message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text
        else:
            await message.reply(
                "📝 **Translation**\n\n"
                "Usage:\n"
                "1. `/translate Text yahan likhein`\n"
                "2. Kisi message ko reply karke `/translate` karein\n"
                "3. Ya bas `/translate` karein aur next message mein text bhejein"
            )
            _translate_state[user_id] = "__waiting__"
            return

        _translate_state[user_id] = text
        await message.reply(
            f"📝 **Text to Translate:**\n`{text[:200]}{'...' if len(text) > 200 else ''}`\n\n"
            f"**Target language select karein:**",
            reply_markup=translate_language_keyboard(),
        )

    @app.on_message(filters.private & ~filters.command([]))
    @authorized_only(db)
    async def translate_text_input(client: Client, message: Message, db):
        """Capture text when user sends message after bare /translate."""
        user_id = message.from_user.id
        if _translate_state.get(user_id) != "__waiting__":
            return  # Not waiting for translate input

        text = message.text
        if not text:
            await message.reply("❌ Sirf text messages translate ho sakte hain.")
            _translate_state.pop(user_id, None)
            return

        _translate_state[user_id] = text
        await message.reply(
            f"📝 **Text to Translate:**\n`{text[:200]}{'...' if len(text) > 200 else ''}`\n\n"
            f"**Target language select karein:**",
            reply_markup=translate_language_keyboard(),
        )

    @app.on_callback_query(filters.regex(r"^translate_lang:(.+)$"))
    @authorized_only(db)
    async def translate_lang_callback(client: Client, callback: CallbackQuery, db):
        user_id = callback.from_user.id
        target_lang = callback.matches[0].group(1)

        text = _translate_state.get(user_id)
        if not text or text == "__waiting__":
            await callback.answer("Session expired. /translate dobara use karein.", show_alert=True)
            return

        _translate_state.pop(user_id, None)

        lang_info = Config.LANGUAGES.get(target_lang, ("", target_lang))
        lang_display = f"{lang_info[0]} {lang_info[1]}"

        await callback.message.edit_text(
            f"🔄 **Translating to {lang_display}...**"
        )
        await callback.answer()

        # Perform translation
        try:
            from services.transcriber import Transcriber
            import asyncio

            loop = asyncio.get_event_loop()

            try:
                import argostranslate.translate
                target_code = target_lang[:2]

                def do_translate():
                    try:
                        return argostranslate.translate.translate(text, "auto", target_code)
                    except Exception:
                        return None

                translated = await loop.run_in_executor(None, do_translate)
            except ImportError:
                translated = None

            if translated:
                chunks = smart_split(translated, Config.MAX_MESSAGE_LENGTH)
                await callback.message.edit_text(
                    f"✅ **Translated to {lang_display}:**\n\n{chunks[0]}"
                )
                for chunk in chunks[1:]:
                    await callback.message.reply(chunk)
            else:
                await callback.message.edit_text(
                    f"❌ Translation unavailable.\n\n"
                    f"argostranslate install nahi hai ya language pair supported nahi.\n\n"
                    f"Install: `pip install argostranslate`"
                )

        except Exception as e:
            logger.exception(f"Translation error: {e}")
            await callback.message.edit_text(f"❌ Translation failed: `{str(e)[:200]}`")
      
