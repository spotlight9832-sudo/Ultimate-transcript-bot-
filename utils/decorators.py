"""
utils/decorators.py
--------------------
Access control decorators for message/callback handlers.

  @owner_only     : Only the bot owner can execute this handler
  @authorized     : Only authorized (allowed) users can execute this handler
  @not_banned     : Rejects banned users before anything else

Usage in handlers:
  @app.on_message(filters.command("ban"))
  @owner_only(db)
  async def ban_cmd(client, message, db):
      ...
"""

import logging
from functools import wraps

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery

from config import Config

logger = logging.getLogger(__name__)


def owner_only(db):
    """Decorator: restrict handler to bot owner only."""
    def decorator(func):
        @wraps(func)
        async def wrapper(client: Client, update, *args, **kwargs):
            user_id = update.from_user.id if update.from_user else 0
            if user_id != Config.OWNER_ID:
                if isinstance(update, CallbackQuery):
                    await update.answer("🚫 Owner only command!", show_alert=True)
                else:
                    await update.reply("🚫 Ye command sirf owner ke liye hai.")
                return
            return await func(client, update, db, *args, **kwargs)
        return wrapper
    return decorator


def authorized_only(db):
    """
    Decorator: allow only authorized users.
    Banned users are rejected first with a permanent ban message.
    Unauthorized users are shown the access denied message.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(client: Client, update, *args, **kwargs):
            user = update.from_user
            if not user:
                return

            user_id = user.id

            # Owner always passes
            if user_id == Config.OWNER_ID:
                return await func(client, update, db, *args, **kwargs)

            # Check ban first
            if await db.is_banned(user_id):
                msg = (
                    f"🚫 **Aapko is bot se permanently ban kar diya gaya hai.**\n\n"
                    f"Owner: {Config.OWNER_USERNAME}"
                )
                if isinstance(update, CallbackQuery):
                    await update.answer("You are banned!", show_alert=True)
                else:
                    await update.reply(msg)
                return

            # Check authorization
            if not await db.is_authorized(user_id):
                msg = (
                    f"🚫 **Access Denied!**\n\n"
                    f"Aap is bot ko use karne ke liye authorized nahi hain.\n\n"
                    f"Access ke liye bot owner se sampark karein:\n"
                    f"👤 Owner: {Config.OWNER_USERNAME}"
                )
                if isinstance(update, CallbackQuery):
                    await update.answer("Access Denied!", show_alert=True)
                else:
                    await update.reply(msg)
                return

            return await func(client, update, db, *args, **kwargs)
        return wrapper
    return decorator
  
