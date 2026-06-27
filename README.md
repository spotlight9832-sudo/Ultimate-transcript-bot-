# 🎙 Telegram Transcript Bot

A production-ready Telegram bot that transcribes audio and video files using **Whisper Large-v3** — the most accurate open-source speech recognition model. Supports 19 languages, subtitle generation, and translation.

---

## ✨ Features

- 🎵 **All Audio Formats** — MP3, WAV, M4A, FLAC, OGG, OPUS, AAC, WMA, AIFF and more
- 🎬 **All Video Formats** — MP4, MKV, AVI, MOV, WEBM, FLV, MPEG, TS and more
- 🎙 **Voice Messages & Video Notes** — Native Telegram formats supported
- 🌐 **19 Languages** — Auto-detect or manually select source/target language
- 📄 **4 Output Formats** — Telegram message, TXT, SRT subtitles, VTT subtitles
- 🔐 **Private Access** — Only owner-approved users can access the bot
- 🚫 **Ban System** — Permanently ban disruptive users
- 📊 **Statistics & History** — Per-user and global analytics
- 📡 **Broadcast** — Message all users at once
- 🔄 **Async Queue** — Multiple files processed concurrently
- 🐳 **Docker Ready** — One command deployment
- 🔁 **Auto Restart** — Systemd service for VPS

---

## 📁 Project Structure

```
transcript-bot/
│
├── bot.py                    # Main entry point — starts the bot
├── config.py                 # All configuration (reads from .env)
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker image definition
├── docker-compose.yml        # Docker Compose (bot + MongoDB)
├── .env.example              # Environment variable template
├── .gitignore                # Git ignore rules
├── transcript-bot.service    # Systemd service for VPS
│
├── handlers/                 # Telegram message/callback handlers
│   ├── __init__.py           # Registers all handlers in correct order
│   ├── start.py              # /start, /help — welcome + access denied
│   ├── media.py              # Audio/video/voice file processing flow
│   ├── admin.py              # Owner commands: /allow /ban /broadcast etc.
│   └── user.py               # User commands: /history /stats /translate
│
├── keyboards/                # Inline keyboard definitions
│   ├── __init__.py
│   └── inline.py             # Language picker, format picker, approve/reject
│
├── database/                 # MongoDB interface
│   ├── __init__.py
│   └── mongo.py              # All DB operations (users, history, stats)
│
├── services/                 # Core business logic
│   ├── __init__.py
│   ├── transcriber.py        # Whisper Large-v3 transcription engine
│   ├── audio_extractor.py    # FFmpeg audio extraction and conversion
│   └── queue_manager.py      # Async job queue and worker management
│
├── utils/                    # Shared utilities
│   ├── __init__.py
│   ├── logger.py             # Logging setup (console + rotating files)
│   ├── text_utils.py         # Smart text splitting for Telegram
│   ├── cleanup.py            # File cleanup after processing
│   └── decorators.py         # @owner_only and @authorized_only decorators
│
├── downloads/                # Downloaded media files (auto-cleaned)
├── outputs/                  # Generated transcript files (auto-cleaned)
├── logs/                     # Bot logs (rotating, 10 MB per file)
└── temp/                     # Temporary WAV files during processing
```

### Why each file exists

| File | Purpose |
|------|---------|
| `bot.py` | Creates the Pyrogram client, connects DB, starts the queue, registers handlers |
| `config.py` | Single source of truth for all configuration — prevents hardcoded values |
| `handlers/start.py` | First thing a user sees — handles auth flow and owner notifications |
| `handlers/media.py` | The core user flow: receive file → ask language → ask format → download → queue |
| `handlers/admin.py` | All owner-only commands with proper auth checks |
| `handlers/user.py` | Self-service commands for authorized users |
| `keyboards/inline.py` | Centralized keyboard definitions — change UI in one place |
| `database/mongo.py` | All DB logic in one place — handlers never touch MongoDB directly |
| `services/transcriber.py` | Whisper wrapper — handles transcription, SRT/VTT generation, translation |
| `services/audio_extractor.py` | FFmpeg wrapper — converts any format to WAV for Whisper |
| `services/queue_manager.py` | Processes jobs asynchronously — users get real-time progress updates |
| `utils/decorators.py` | Reusable auth guards — `@owner_only` and `@authorized_only` |
| `utils/text_utils.py` | Smart word-boundary text splitting for long transcripts |
| `utils/cleanup.py` | Deletes temp files after processing — keeps VPS storage clean |
| `utils/logger.py` | Configured logging — console for development, files for production |

---

## 🚀 VPS Deployment Guide

### Step 1 — Ubuntu Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y git curl wget nano htop
```

### Step 2 — Install Python 3.12

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev
python3.12 --version  # Should show 3.12.x
```

### Step 3 — Install FFmpeg

```bash
sudo apt install -y ffmpeg
ffmpeg -version  # Verify installation
```

### Step 4 — Install MongoDB

```bash
# Import MongoDB GPG key
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
    sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
    https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

sudo apt update
sudo apt install -y mongodb-org

# Start and enable MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod
sudo systemctl status mongod  # Should show "active (running)"
```

### Step 5 — Clone Repository

```bash
cd ~
git clone https://github.com/yourusername/transcript-bot.git
cd transcript-bot
```

### Step 6 — Create Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
```

### Step 7 — Create .env File

```bash
cp .env.example .env
nano .env
```

Fill in all values:
```env
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
OWNER_ID=987654321
OWNER_USERNAME=@YourUsername
MONGO_URI=mongodb://localhost:27017
DB_NAME=transcript_bot
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
MAX_FILE_SIZE_MB=2048
MAX_CONCURRENT_JOBS=2
```

### Step 8 — Install Dependencies

```bash
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ **Note:** Installing `torch` and `faster-whisper` may take 5–10 minutes. The Whisper Large-v3 model (~3GB) will download automatically on first run.

### Step 9 — Test Run

```bash
source venv/bin/activate
python bot.py
```

If you see `Bot started as @YourBot`, it's working. Press `Ctrl+C` to stop.

### Step 10 — Create Systemd Service (Auto-start)

```bash
# Copy service file
sudo cp transcript-bot.service /etc/systemd/system/

# Edit paths if needed (change 'ubuntu' to your username)
sudo nano /etc/systemd/system/transcript-bot.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable transcript-bot
sudo systemctl start transcript-bot

# Check status
sudo systemctl status transcript-bot

# View logs
sudo journalctl -u transcript-bot -f
```

The bot will now **automatically restart** on crash and **start on server reboot**.

---

## 🐳 Docker Deployment

Docker is the easiest deployment method.

### Prerequisites
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo apt install -y docker-compose-plugin
```

### Deploy

```bash
# Clone repo
git clone https://github.com/yourusername/transcript-bot.git
cd transcript-bot

# Create .env
cp .env.example .env
nano .env  # Fill in your values

# Start (builds image, starts MongoDB, starts bot)
docker compose up -d

# View logs
docker compose logs -f bot

# Stop
docker compose down
```

> **Note:** First run downloads Whisper Large-v3 (~3GB). Progress is visible in logs.

---

## ⚙️ Configuration Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | ✅ | Telegram API ID from my.telegram.org |
| `API_HASH` | ✅ | Telegram API Hash from my.telegram.org |
| `BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `OWNER_ID` | ✅ | Your numeric Telegram user ID |
| `OWNER_USERNAME` | ✅ | Your @username (shown in messages) |
| `MONGO_URI` | ✅ | MongoDB connection string |
| `DB_NAME` | ❌ | Database name (default: `transcript_bot`) |
| `WHISPER_MODEL` | ❌ | Model size (default: `large-v3`) |
| `WHISPER_DEVICE` | ❌ | `cpu` or `cuda` (default: `cpu`) |
| `WHISPER_COMPUTE_TYPE` | ❌ | `int8` for CPU, `float16` for GPU |
| `MAX_FILE_SIZE_MB` | ❌ | Max upload size in MB (default: 2048) |
| `MAX_CONCURRENT_JOBS` | ❌ | Parallel transcription jobs (default: 2) |

### Getting your Telegram credentials

1. **API_ID & API_HASH** — Go to https://my.telegram.org/apps, log in, create an app
2. **BOT_TOKEN** — Message @BotFather on Telegram → `/newbot`
3. **OWNER_ID** — Message @userinfobot on Telegram, it shows your ID

---

## 📋 Commands Reference

### User Commands
| Command | Description |
|---------|-------------|
| `/start` | Start the bot / see welcome message |
| `/help` | Show help message |
| `/history` | View your transcript history (last 20) |
| `/stats` | Your personal statistics |
| `/translate` | Translate text to another language |

### Owner Commands
| Command | Description |
|---------|-------------|
| `/allow USER_ID` | Grant access to a user |
| `/deny USER_ID` | Revoke access from a user |
| `/ban USER_ID` | Permanently ban a user |
| `/unban USER_ID` | Remove ban from a user |
| `/users` | List all authorized users |
| `/banned` | List all banned users |
| `/broadcast` | Send message to all users |
| `/stats` | Full bot statistics and analytics |

---

## 🌐 Supported Languages

Auto Detect, English, Hindi, Chinese (Simplified), Chinese (Traditional), Japanese, Korean, Spanish, French, German, Russian, Arabic, Portuguese, Italian, Turkish, Indonesian, Vietnamese, Thai, Bengali

---

## 🔧 Troubleshooting

### Bot doesn't start
```bash
# Check logs
sudo journalctl -u transcript-bot -n 50

# Verify .env is correct
cat .env

# Test manually
source venv/bin/activate
python bot.py
```

### MongoDB connection failed
```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Start if stopped
sudo systemctl start mongod

# Test connection
mongosh --eval "db.adminCommand('ping')"
```

### FFmpeg not found
```bash
# Install FFmpeg
sudo apt install -y ffmpeg

# Verify
ffmpeg -version
```

### Whisper model download fails
```bash
# Manually download
source venv/bin/activate
python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3')"
```

### Out of memory (CPU)
Use a smaller model in `.env`:
```env
WHISPER_MODEL=medium
WHISPER_COMPUTE_TYPE=int8
```

### Enable GPU (NVIDIA)
```bash
# Install CUDA toolkit, then:
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
MAX_CONCURRENT_JOBS=4
```

---

## 📈 Scaling to Multiple VPS

The architecture supports horizontal scaling:

1. **Centralized MongoDB** — Point all VPS instances to MongoDB Atlas or a dedicated server
2. **Shared `.env`** — Use same `MONGO_URI` on all servers
3. **Independent workers** — Each VPS runs its own queue workers
4. **No shared state** — The queue is per-instance (for distributed queue, use Redis)

### MongoDB Atlas Setup (Cloud)
```env
MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/
```

---

## 📄 License

MIT License — Free to use and modify.

---

## 🤝 Credits

- [Pyrogram](https://pyrogram.org/) — Telegram MTProto library
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CTranslate2 Whisper backend
- [Motor](https://motor.readthedocs.io/) — Async MongoDB driver
- [FFmpeg](https://ffmpeg.org/) — Universal audio/video processing

