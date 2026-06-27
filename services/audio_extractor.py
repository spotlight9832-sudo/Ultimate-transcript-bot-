"""
services/audio_extractor.py
----------------------------
FFmpeg-based audio extraction service.

Responsibilities:
  - Extract audio from video files
  - Convert any audio format to WAV (required by Whisper)
  - Detect file type (audio vs video)
  - Get media file duration
  - Probe media file metadata
"""

import asyncio
import logging
import os
import json
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)


class AudioExtractor:
    """Handles all FFmpeg-based audio processing."""

    @staticmethod
    def is_video(file_path: str) -> bool:
        """Determine if a file is video based on extension."""
        ext = Path(file_path).suffix.lower()
        return ext in Config.VIDEO_EXTENSIONS

    @staticmethod
    def is_audio(file_path: str) -> bool:
        """Determine if a file is audio based on extension."""
        ext = Path(file_path).suffix.lower()
        return ext in Config.AUDIO_EXTENSIONS

    @staticmethod
    def is_supported(file_path: str) -> bool:
        """Check if the file is any supported media type."""
        ext = Path(file_path).suffix.lower()
        return ext in (Config.AUDIO_EXTENSIONS | Config.VIDEO_EXTENSIONS)

    @staticmethod
    async def get_duration(file_path: str) -> float:
        """
        Get media duration in seconds using ffprobe.
        Returns 0.0 if unable to determine.
        """
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            file_path,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                data = json.loads(stdout.decode())
                return float(data.get("format", {}).get("duration", 0.0))
        except Exception as e:
            logger.warning(f"Could not get duration for {file_path}: {e}")
        return 0.0

    @staticmethod
    async def probe(file_path: str) -> dict:
        """Run ffprobe on a file and return full metadata as dict."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return json.loads(stdout.decode())
        except Exception as e:
            logger.warning(f"ffprobe failed for {file_path}: {e}")
        return {}

    @staticmethod
    async def extract_audio(
        input_path: str,
        output_path: str,
        progress_callback=None,
    ) -> str:
        """
        Extract/convert audio to WAV format using FFmpeg.

        - For video files: extracts the audio stream
        - For audio files: converts to WAV (16kHz mono for optimal Whisper performance)

        Args:
            input_path      : Source media file
            output_path     : Destination WAV file path
            progress_callback: Optional async callable(percent: int)

        Returns:
            output_path on success

        Raises:
            RuntimeError if FFmpeg fails
        """
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-vn",               # No video
            "-acodec", "pcm_s16le",  # PCM 16-bit little-endian (WAV)
            "-ar", "16000",      # 16kHz — Whisper's native sample rate
            "-ac", "1",          # Mono
            "-y",                # Overwrite output
            output_path,
        ]

        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode(errors="replace")
            logger.error(f"FFmpeg failed:\n{error_msg}")
            raise RuntimeError(f"FFmpeg audio extraction failed: {error_msg[-500:]}")

        if not os.path.exists(output_path):
            raise RuntimeError(f"FFmpeg produced no output file at: {output_path}")

        logger.debug(f"Audio extracted to: {output_path}")
        return output_path

    @staticmethod
    async def check_ffmpeg() -> bool:
        """Verify FFmpeg is installed and accessible."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False
      
