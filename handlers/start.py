"""
handlers/start.py
-----------------
Handles /start and /help commands.
- Unauthorized users: shows access denied + notifies owner
- Authorized users: shows welcome message
- Owner: shows full owner menu
"""

import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from keyboards.inline import approve_reject_keyboard

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """
👋 **Transcript Bot mein aapka swagat hai!**

Main aapke audio/video files ko text mein convert karta hoon.

**Supported Formats:**
🎵 Audio: MP3, WAV, M4A, FLAC, OGG, OPUS, AAC, WMA aur bahut kuch
🎬 Video: MP4, MKV, AVI, MOV, WEBM, FLV aur bahut kuch
🎙 Voice Messages & Video Notes bhi!

**Kaise use karein:**
1️⃣ Koi bhi audio/video file bhejein
2️⃣ Source language select karein
3️⃣ Output language select karein
4️⃣ Output format choose karein
5️⃣ Transcript ready! ✅

**Commands:**
/history — Apni transcript history dekhein
/translate — Text translate karein
/stats — Apni statistics dekhein
/help — Yeh message phir se dekhein
"""

OWNER_EXTRA = """

**Owner Commands:**
/allow USER\\_ID — User ko allow karein
/deny USER\\_ID — User ka access hatao
/ban USER\\_ID — User ko ban karein
/unban USER\\_ID — User ko unban karein
/users — Sab users dekhein
/banned — Banned users dekhein
/broadcast — Sab users ko message bhejein
/stats — Full statistics dekhein
"""


def register_start_handlers(app: Client, db, queue_manager):
    """Register /start and /help handlers."""

    @app.on_message(filters.command(["start", "help"]) & filters.private)
    async def start_handler(client: Client, message: Message):
        user = message.from_user
        user_id = user.id
        name = user.first_name or "Unknown"
        username = f"@{user.username}" if user.username else "N/A"

        # Register user in DB
        is_new = await db.add_user(user_id, name, user.username)

        # Owner always has access
        if user_id == Config.OWNER_ID:
            full_msg = WELCOME_MESSAGE + OWNER_EXTRA
            await message.reply(full_msg.strip())
            return

        # Check ban
        if await db.is_banned(user_id):
            await message.reply(
                f"🚫 **Aapko is bot se permanently ban kar diya gaya hai.**\n\n"
                f"Owner: {Config.OWNER_USERNAME}"
            )
            return

        # Check authorization
        if await db.is_authorized(user_id):
            await message.reply(WELCOME_MESSAGE.strip())
            return

        # Unauthorized user — show denied message + notify owner
        await message.reply(
            f"🚫 **Access Denied!**\n\n"
            f"Aap is bot ko use karne ke liye authorized nahi hain.\n\n"
            f"Access ke liye bot owner se sampark karein:\n"
            f"👤 Owner: {Config.OWNER_USERNAME}"
        )

        # Notify owner only for new or fresh unauthorized users
        if is_new or message.command[0] == "start":
            try:
                await client.send_message(
                    Config.OWNER_ID,
                    f"🚨 **New Access Request**\n\n"
                    f"👤 Name: {name}\n"
                    f"🔗 Username: {username}\n"
                    f"🆔 User ID: `{user_id}`",
                    reply_markup=approve_reject_keyboard(user_id),
                )
            except Exception as e:
                logger.warning(f"Could not notify owner: {e}")
                                     
