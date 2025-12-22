"""Telegram utils."""

import re


def _escape_md(text: str) -> str:
    """Escape Markdown characters in a string."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", text)
