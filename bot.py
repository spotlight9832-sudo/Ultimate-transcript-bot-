"""
bot.py
------
Main entry point for the Transcript Bot.
Creates the Pyrogram client, registers all handlers, and starts the bot.
"""

import asyncio
import logging
import os
import sys

from pyrogram import Client, idle
from config import Config
from database.mongo import Database
from services.queue_manager import QueueManager
from utils.logger import setup_logger

# ─── Setup Logging ────────────────────────────────────────────────────────────
logger = setup_logger(__name__)


async def main():
    """Initialize and run the bot."""

    # Validate configuration before starting
    try:
        Config.validate()
    except ValueError as e:
        logger.critical(f"Configuration validation failed:\n{e}")
        sys.exit(1)

    # Create required directories
    for directory in [Config.DOWNLOADS_DIR, Config.OUTPUTS_DIR, Config.TEMP_DIR, Config.LOGS_DIR]:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Directory ensured: {directory}")

    # Connect to MongoDB
    db = Database()
    await db.connect()
    logger.info("MongoDB connected successfully")

    # Initialize the processing queue
    queue_manager = QueueManager()

    # Create the Pyrogram client
    app = Client(
        name="transcript_bot",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        workers=8,
    )

    # Register all handlers (import here to avoid circular imports)
    from handlers import register_handlers
    register_handlers(app, db, queue_manager)

    logger.info("Starting Transcript Bot...")

    async with app:
        bot_info = await app.get_me()
        logger.info(f"Bot started as @{bot_info.username} (ID: {bot_info.id})")
        print(f"\n{'='*50}")
        print(f"  🤖 Transcript Bot Started!")
        print(f"  Username : @{bot_info.username}")
        print(f"  Owner ID : {Config.OWNER_ID}")
        print(f"  Whisper  : {Config.WHISPER_MODEL}")
        print(f"{'='*50}\n")

        # Start queue workers
        await queue_manager.start(app, db)

        await idle()

        # Graceful shutdown
        await queue_manager.stop()
        await db.close()
        logger.info("Bot stopped gracefully.")


if __name__ == "__main__":
    asyncio.run(main())
  
