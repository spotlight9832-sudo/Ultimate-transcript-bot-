"""
utils/text_utils.py
--------------------
Smart text splitting for Telegram messages.

Rules (in order of priority):
  1. Never exceed max_length characters
  2. Split at paragraph boundaries first (double newline)
  3. Split at sentence boundaries (. ! ?)
  4. Split at space boundaries
  5. NEVER split in the middle of a word
"""

import re
from typing import Generator


def smart_split(text: str, max_length: int = 3000) -> list[str]:
    """
    Split text into chunks that fit Telegram's message limits.

    Priority:
      1. Paragraph boundary (\\n\\n)
      2. Sentence boundary (. ! ?)
      3. Space boundary
      Never cuts words.

    Args:
        text       : Input text to split
        max_length : Maximum characters per chunk

    Returns:
        List of text chunks, each ≤ max_length characters
    """
    if len(text) <= max_length:
        return [text.strip()] if text.strip() else []

    chunks = []
    remaining = text.strip()

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to find a split point within max_length
        window = remaining[:max_length]

        # Priority 1: Paragraph boundary
        split_pos = window.rfind("\n\n")
        if split_pos > max_length // 4:  # At least 25% into the window
            chunk = remaining[:split_pos].strip()
            remaining = remaining[split_pos:].strip()
            if chunk:
                chunks.append(chunk)
            continue

        # Priority 2: Sentence boundary (. ! ?)
        sentence_pattern = re.compile(r'(?<=[.!?])\s+')
        matches = list(sentence_pattern.finditer(window))
        if matches:
            last_match = matches[-1]
            split_pos = last_match.start()
            chunk = remaining[:split_pos].strip()
            remaining = remaining[split_pos:].strip()
            if chunk:
                chunks.append(chunk)
            continue

        # Priority 3: Single newline
        split_pos = window.rfind("\n")
        if split_pos > max_length // 4:
            chunk = remaining[:split_pos].strip()
            remaining = remaining[split_pos:].strip()
            if chunk:
                chunks.append(chunk)
            continue

        # Priority 4: Space boundary (never cut words)
        split_pos = window.rfind(" ")
        if split_pos > 0:
            chunk = remaining[:split_pos].strip()
            remaining = remaining[split_pos:].strip()
            if chunk:
                chunks.append(chunk)
            continue

        # Absolute last resort: force split at max_length
        # (only happens if a single word is > max_length, extremely rare)
        chunks.append(remaining[:max_length])
        remaining = remaining[max_length:]

    return [c for c in chunks if c]


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def truncate(text: str, max_len: int = 50) -> str:
    """Truncate text with ellipsis for display."""
    return text[:max_len] + "..." if len(text) > max_len else text
      
