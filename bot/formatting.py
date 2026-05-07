"""text formatting helpers (lowercase, html bold for emphasis)."""

from __future__ import annotations

from html import escape


def b(text: str) -> str:
    """wrap in <b> for telegram html parse mode."""
    return f"<b>{escape(str(text))}</b>"


def fmt_duration(total_seconds: int) -> str:
    """format duration as hh:mm:ss (hours unbounded)."""
    if total_seconds < 0:
        total_seconds = 0
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def shift_started(username: str) -> str:
    return f"{b('@' + username)} заступил на смену ✅"


def shift_ended(username: str, total_seconds: int) -> str:
    duration = fmt_duration(total_seconds)
    return (
        f"{b('@' + username)} окончил смену\n"
        f"[количество часов на смене: {b(duration)}] 😵\u200d💫"
    )


def tweet_message(username: str, text: str, url: str) -> str:
    body = escape(text or "").strip()
    parts = [f"{b('@' + username)} в x:"]
    if body:
        parts.append(body)
    parts.append(escape(url))
    return "\n\n".join(parts)
