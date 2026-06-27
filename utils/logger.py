"""
utils/logger.py
---------------
Centralized logging configuration.
Sets up both console and rotating file logging.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from config import Config


def setup_logger(name: str = "transcript_bot", level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return a logger with console + file handlers.

    Args:
        name  : Logger name
        level : Logging level (default: INFO)

    Returns:
        Configured Logger instance
    """
    os.makedirs(Config.LOGS_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers on re-import
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console Handler ────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ── Rotating File Handler ──────────────────────────────────────────────
    file_handler = RotatingFileHandler(
        filename=os.path.join(Config.LOGS_DIR, "bot.log"),
        maxBytes=10 * 1024 * 1024,   # 10 MB per file
        backupCount=5,                 # Keep 5 rotated files
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Suppress overly verbose third-party loggers
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.INFO)

    return logger
  
