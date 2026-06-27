"""
handlers/admin.py
-----------------
Owner-only administrative commands:
  /allow USER_ID    — Grant access to a user
  /deny USER_ID     — Revoke access from a user
  /ban USER_ID      — Permanently ban a user
  /unban USER_ID    — Remove ban from a user
  /users            — List all authorized users
  /banned           — List all banned users
  /broadcast        — Send message to all authorized users
  /stats            — Full owner statistics

Also handles the approve/reject callback buttons on access request notifications.
"""

import logging

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery

from config import Config
from utils.decorators import owner_only
from utils.text_utils import format_duration

logger = logging.getLogger(__name__)


def register_admin_handlers(app: Client, db, queue_manager):
    """Register all admin/owner command handlers."""

    # ─── /allow ──────────────────────────────────────────────────────────────

    @app.on_message(filters.command("allow") & filters.private)
    @owner_only(db)
    async def allow_cmd(client: Client, message: Message, db):
        args = message.command[1:]
        if not args or not args[0].isdigit():
            await message.reply("Usage: `/allow USER_ID`")
            return

        user_id = int(args[0])
        success = await db.authorize_user(user_id)

        if success:
            await message.reply(f"✅ User `{user_id}` ko access de diya gaya.")
            try:
                await client.send_message(
                    user_id,
                    f"✅ **Access Granted!**\n\n"
                    f"Aapko is bot ko use karne ki permission mil gayi hai.\n"
                    f"Shuru karne ke liye /start karein."
                )
            except Exception:
                pass
        else:
            # User not in DB — insert and authorize
            await db._db.users.update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "authorized": True, "name": "Unknown", "username": None}},
                upsert=True,
            )
            await message.reply(f"✅ User `{user_id}` ko allow kar diya gaya.")

    # ─── /deny ───────────────────────────────────────────────────────────────

    @app.on_message(filters.command("deny") & filters.private)
    @owner_only(db)
    async def deny_cmd(client: Client, message: Message, db):
        args = message.command[1:]
        if not args or not args[0].isdigit():
            await message.reply("Usage: `/deny USER_ID`")
            return

        user_id = int(args[0])
        success = await db.deny_user(user_id)
        if success:
            await message.reply(f"✅ User `{user_id}` ka access revoke kar diya gaya.")
        else:
            await message.reply(f"❌ User `{user_id}` nahi mila.")

    # ─── /ban ────────────────────────────────────────────────────────────────

    @app.on_message(filters.command("ban") & filters.private)
    @owner_only(db)
    async def ban_cmd(client: Client, message: Message, db):
        args = message.command[1:]
        if not args or not args[0].isdigit():
            await message.reply("Usage: `/ban USER_ID`")
            return

        user_id = int(args[0])
        if user_id == Config.OWNER_ID:
            await message.reply("❌ Aap apne aap ko ban nahi kar sakte!")
            return

        user_doc = await db.get_user(user_id)
        name = user_doc.get("name", "Unknown") if user_doc else "Unknown"

        success = await db.ban_user(user_id, name)
        if success:
            await message.reply(f"🚫 User `{user_id}` ({name}) ko ban kar diya gaya.")
            try:
                await client.send_message(
                    user_id,
                    f"🚫 **Aapko is bot se permanently ban kar diya gaya hai.**\n\n"
                    f"Owner: {Config.OWNER_USERNAME}"
                )
            except Exception:
                pass
        else:
            await message.reply(f"❌ User `{user_id}` pehle se ban hai ya nahi mila.")

    # ─── /unban ──────────────────────────────────────────────────────────────

    @app.on_message(filters.command("unban") & filters.private)
    @owner_only(db)
    async def unban_cmd(client: Client, message: Message, db):
        args = message.command[1:]
        if not args or not args[0].isdigit():
            await message.reply("Usage: `/unban USER_ID`")
            return

        user_id = int(args[0])
        success = await db.unban_user(user_id)
        if success:
            await message.reply(f"✅ User `{user_id}` ka ban hata diya gaya.")
        else:
            await message.reply(f"❌ User `{user_id}` banned list mein nahi hai.")

    # ─── /users ──────────────────────────────────────────────────────────────

    @app.on_message(filters.command("users") & filters.private)
    @owner_only(db)
    async def users_cmd(client: Client, message: Message, db):
        users = await db.get_authorized_users()
        if not users:
            await message.reply("👥 Koi authorized user nahi hai.")
            return

        lines = [f"👥 **Authorized Users ({len(users)}):**\n"]
        for u in users:
            name = u.get("name", "Unknown")
            uid = u.get("user_id", "?")
            uname = f"@{u['username']}" if u.get("username") else "N/A"
            count = u.get("transcripts_count", 0)
            lines.append(f"• {name} | `{uid}` | {uname} | {count} transcripts")

        text = "\n".join(lines)
        # Split if too long
        if len(text) > 4000:
            text = text[:4000] + "\n... (list truncated)"
        await message.reply(text)

    # ─── /banned ─────────────────────────────────────────────────────────────

    @app.on_message(filters.command("banned") & filters.private)
    @owner_only(db)
    async def banned_cmd(client: Client, message: Message, db):
        banned = await db.get_banned_users()
        if not banned:
            await message.reply("🚫 Koi banned user nahi hai.")
            return

        lines = [f"🚫 **Banned Users ({len(banned)}):**\n"]
        for u in banned:
            uid = u.get("user_id", "?")
            name = u.get("name", "Unknown")
            lines.append(f"• `{uid}` — {name}")

        await message.reply("\n".join(lines))

    # ─── /broadcast ──────────────────────────────────────────────────────────

    @app.on_message(filters.command("broadcast") & filters.private)
    @owner_only(db)
    async def broadcast_cmd(client: Client, message: Message, db):
        # Broadcast message is the text after /broadcast, or a reply
        if message.reply_to_message:
            bc_msg = message.reply_to_message
            use_forward = True
        elif len(message.command) > 1:
            bc_text = message.text.split(None, 1)[1]
            use_forward = False
        else:
            await message.reply(
                "Usage:\n"
                "1. `/broadcast Your message here`\n"
                "2. Reply to a message with `/broadcast`"
            )
            return

        users = await db.get_authorized_users()
        status_msg = await message.reply(f"📡 Broadcasting to {len(users)} users...")

        sent = 0
        failed = 0
        for user in users:
            uid = user.get("user_id")
            if not uid:
                continue
            try:
                if use_forward:
                    await bc_msg.forward(uid)
                else:
                    await client.send_message(uid, bc_text)
                sent += 1
            except Exception as e:
                logger.debug(f"Broadcast failed for {uid}: {e}")
                failed += 1

        await status_msg.edit_text(
            f"📡 **Broadcast Complete!**\n\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}"
        )

    # ─── /stats (Owner) ───────────────────────────────────────────────────────

    @app.on_message(filters.command("stats") & filters.private)
    @owner_only(db)
    async def owner_stats_cmd(client: Client, message: Message, db):
        gs = await db.get_global_stats()
        today = await db.get_today_analytics()
        all_users = await db.get_all_users()
        banned = await db.get_banned_users()
        users_today = await db.count_users_today()

        total_users = len(all_users)
        authorized = sum(1 for u in all_users if u.get("authorized"))
        total_banned = len(banned)

        total_transcripts = gs.get("total_transcripts", 0)
        total_videos = gs.get("total_videos", 0)
        total_audios = gs.get("total_audios", 0)
        total_duration = gs.get("total_duration_secs", 0)

        today_transcripts = today.get("transcripts", 0)
        today_duration = today.get("duration_secs", 0)

        text = (
            f"📊 **Bot Statistics**\n\n"
            f"**👥 Users:**\n"
            f"  Total: {total_users}\n"
            f"  Authorized: {authorized}\n"
            f"  🚫 Banned: {total_banned}\n"
            f"  Active Today: {users_today}\n\n"
            f"**🎙 All-Time:**\n"
            f"  Total Transcripts: {int(total_transcripts)}\n"
            f"  🎥 Videos: {int(total_videos)}\n"
            f"  🎵 Audios: {int(total_audios)}\n"
            f"  ⏳ Total Duration: {format_duration(total_duration)}\n\n"
            f"**📅 Today:**\n"
            f"  Transcripts: {int(today_transcripts)}\n"
            f"  Duration: {format_duration(today_duration)}\n"
            f"  Active Users: {users_today}\n\n"
            f"**⚙️ System:**\n"
            f"  Queue Size: {queue_manager.queue_size()}\n"
            f"  Whisper Model: {Config.WHISPER_MODEL}\n"
        )
        await message.reply(text)

    # ─── Access Approve/Reject Callbacks ─────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^access_approve:(\d+)$"))
    async def approve_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != Config.OWNER_ID:
            await callback.answer("Only owner can approve!", show_alert=True)
            return

        user_id = int(callback.matches[0].group(1))
        await db.authorize_user(user_id)

        await callback.message.edit_text(
            callback.message.text + "\n\n✅ **Approved!**"
        )
        await callback.answer("✅ User approved!")

        try:
            await client.send_message(
                user_id,
                f"✅ **Access Granted!**\n\n"
                f"Aapko is bot ko use karne ki permission mil gayi hai!\n"
                f"Shuru karne ke liye /start karein."
            )
        except Exception:
            pass

    @app.on_callback_query(filters.regex(r"^access_reject:(\d+)$"))
    async def reject_callback(client: Client, callback: CallbackQuery):
        if callback.from_user.id != Config.OWNER_ID:
            await callback.answer("Only owner can reject!", show_alert=True)
            return

        user_id = int(callback.matches[0].group(1))

        await callback.message.edit_text(
            callback.message.text + "\n\n❌ **Rejected!**"
        )
        await callback.answer("❌ User rejected!")

        try:
            await client.send_message(
                user_id,
                f"❌ **Access Request Rejected.**\n\n"
                f"Aapka access request reject kar diya gaya.\n"
                f"More info ke liye: {Config.OWNER_USERNAME}"
            )
        except Exception:
            pass
          
