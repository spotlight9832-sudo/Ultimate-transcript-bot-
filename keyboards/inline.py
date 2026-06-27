"""
keyboards/inline.py
-------------------
All InlineKeyboardMarkup definitions used by the bot.
Centralizing keyboards here keeps handlers clean and makes UI changes easy.
"""

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config


def language_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    """
    Build the language selection inline keyboard.
    callback_prefix: e.g. "src_lang" or "tgt_lang" — prepended to the language code.
    """
    buttons = []
    row = []
    for code, (flag, name) in Config.LANGUAGES.items():
        label = f"{flag} {name}"
        btn = InlineKeyboardButton(label, callback_data=f"{callback_prefix}:{code}")
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def output_format_keyboard() -> InlineKeyboardMarkup:
    """Output format selection keyboard."""
    buttons = []
    for fmt_key, fmt_label in Config.OUTPUT_FORMATS.items():
        buttons.append([
            InlineKeyboardButton(fmt_label, callback_data=f"output_fmt:{fmt_key}")
        ])
    return InlineKeyboardMarkup(buttons)


def approve_reject_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Owner notification keyboard to approve/reject access requests."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"access_approve:{user_id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"access_reject:{user_id}"),
        ]
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Generic cancel button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ])


def translate_language_keyboard() -> InlineKeyboardMarkup:
    """Language selection for /translate command (excludes Auto Detect)."""
    buttons = []
    row = []
    for code, (flag, name) in Config.LANGUAGES.items():
        if code == "auto":
            continue  # Translation requires an explicit target language
        label = f"{flag} {name}"
        btn = InlineKeyboardButton(label, callback_data=f"translate_lang:{code}")
        row.append(btn)
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)
