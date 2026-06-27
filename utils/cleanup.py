"""
utils/cleanup.py
----------------
Async file cleanup utilities.
Ensures downloaded, extracted, and temp files are deleted after processing
to keep VPS storage clean.
"""

import asyncio
import glob
import logging
import os
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)


async def cleanup_files(paths: list[str | None]):
    """
    Delete a list of files asynchronously.
    Silently ignores files that don't exist.
    """
    loop = asyncio.get_event_loop()
    for path in paths:
        if not path:
            continue
        try:
            await loop.run_in_executor(None, _delete_file, path)
        except Exception as e:
            logger.warning(f"Failed to delete {path}: {e}")


def _delete_file(path: str):
    """Synchronous file deletion."""
    if os.path.isfile(path):
        os.remove(path)
        logger.debug(f"Deleted: {path}")
    elif os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
        logger.debug(f"Deleted directory: {path}")


async def cleanup_old_files(directory: str, max_age_hours: int = 24):
    """
    Delete files older than max_age_hours from a directory.
    Called periodically to handle orphaned temp files (e.g., from crashes).
    """
    now = time.time()
    max_age_secs = max_age_hours * 3600

    loop = asyncio.get_event_loop()

    def _cleanup():
        deleted = 0
        for file_path in glob.glob(os.path.join(directory, "*")):
            try:
                if os.path.isfile(file_path):
                    age = now - os.path.getmtime(file_path)
                    if age > max_age_secs:
                        os.remove(file_path)
                        deleted += 1
            except Exception as e:
                logger.warning(f"Cleanup error for {file_path}: {e}")
        return deleted

    deleted = await loop.run_in_executor(None, _cleanup)
    if deleted:
        logger.info(f"Cleaned up {deleted} old files from {directory}")


async def periodic_cleanup(interval_hours: int = 6):
    """
    Background task to periodically clean temp/download directories.
    Run as an asyncio task.
    """
    from config import Config
    while True:
        await asyncio.sleep(interval_hours * 3600)
        for directory in [Config.DOWNLOADS_DIR, Config.TEMP_DIR, Config.OUTPUTS_DIR]:
            await cleanup_old_files(directory, max_age_hours=24)
          
