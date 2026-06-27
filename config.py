"""
config.py
---------
Central configuration hub for the Transcript Bot.
All settings are loaded from environment variables (.env file).
Never hardcode secrets — everything lives in .env.
"""

import os
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()


class Config:
    # ─── Telegram API Credentials ────────────────────────────────────────────
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # ─── Owner Configuration ─────────────────────────────────────────────────
    OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
    OWNER_USERNAME: str = os.getenv("OWNER_USERNAME", "@Eren_Yeager_76")

    # ─── MongoDB ──────────────────────────────────────────────────────────────
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "transcript_bot")

    # ─── Whisper Model ────────────────────────────────────────────────────────
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "large-v3")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")   # "cuda" for GPU
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    # ─── File Size Limits ────────────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "2048"))  # 2 GB

    # ─── Paths ────────────────────────────────────────────────────────────────
    DOWNLOADS_DIR: str = "downloads"
    OUTPUTS_DIR: str = "outputs"
    TEMP_DIR: str = "temp"
    LOGS_DIR: str = "logs"

    # ─── Queue ────────────────────────────────────────────────────────────────
    MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))

    # ─── Transcript Splitting ─────────────────────────────────────────────────
    MAX_MESSAGE_LENGTH: int = 3000

    # ─── Supported Languages (code → display) ────────────────────────────────
    LANGUAGES = {
        "auto":    ("🌐", "Auto Detect"),
        "en":      ("🇬🇧", "English"),
        "hi":      ("🇮🇳", "Hindi"),
        "zh":      ("🇨🇳", "Chinese (Simplified)"),
        "zh-TW":   ("🇹🇼", "Chinese (Traditional)"),
        "ja":      ("🇯🇵", "Japanese"),
        "ko":      ("🇰🇷", "Korean"),
        "es":      ("🇪🇸", "Spanish"),
        "fr":      ("🇫🇷", "French"),
        "de":      ("🇩🇪", "German"),
        "ru":      ("🇷🇺", "Russian"),
        "ar":      ("🇸🇦", "Arabic"),
        "pt":      ("🇵🇹", "Portuguese"),
        "it":      ("🇮🇹", "Italian"),
        "tr":      ("🇹🇷", "Turkish"),
        "id":      ("🇮🇩", "Indonesian"),
        "vi":      ("🇻🇳", "Vietnamese"),
        "th":      ("🇹🇭", "Thai"),
        "bn":      ("🇮🇳", "Bengali"),
    }

    # ─── Supported Audio Extensions ──────────────────────────────────────────
    AUDIO_EXTENSIONS = {
        ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus",
        ".aac", ".wma", ".aiff", ".aif", ".alac", ".ape",
        ".mka", ".wv", ".tta", ".dsf", ".dff", ".amr",
        ".mp2", ".ac3", ".dts", ".caf", ".ra", ".rm",
    }

    # ─── Supported Video Extensions ──────────────────────────────────────────
    VIDEO_EXTENSIONS = {
        ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
        ".mpeg", ".mpg", ".ts", ".m2ts", ".mts", ".wmv",
        ".3gp", ".3g2", ".f4v", ".vob", ".divx", ".xvid",
        ".m4v", ".rmvb", ".asf", ".ogv", ".mxf",
    }

    # ─── Output Format Options ────────────────────────────────────────────────
    OUTPUT_FORMATS = {
        "message": "💬 Telegram Message",
        "txt":     "📄 TXT File",
        "srt":     "🎬 SRT Subtitle",
        "vtt":     "🌐 VTT Subtitle",
    }

    @classmethod
    def validate(cls):
        """Validate that required config values are set."""
        errors = []
        if not cls.API_ID:
            errors.append("API_ID is not set")
        if not cls.API_HASH:
            errors.append("API_HASH is not set")
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is not set")
        if not cls.OWNER_ID:
            errors.append("OWNER_ID is not set")
        if not cls.MONGO_URI:
            errors.append("MONGO_URI is not set")
        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
  
