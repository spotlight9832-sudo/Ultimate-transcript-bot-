# ─────────────────────────────────────────────────────────────────────────────
# Transcript Bot — Dockerfile
# Multi-stage build for smaller production image
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# ── System Dependencies ────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working Directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python Dependencies ───────────────────────────────────────────────────────
# Copy requirements first (Docker layer caching — deps only rebuild when changed)
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application Code ──────────────────────────────────────────────────────────
COPY . .

# ── Create Required Directories ───────────────────────────────────────────────
RUN mkdir -p downloads outputs logs temp

# ── Non-Root User (Security) ─────────────────────────────────────────────────
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

# ── Whisper Model Cache ───────────────────────────────────────────────────────
# The Whisper model will be downloaded on first run and cached here
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/transformers

# ── Entry Point ───────────────────────────────────────────────────────────────
CMD ["python", "bot.py"]
