"""configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"env {name!r} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"env {name!r} must be a number, got {raw!r}") from exc


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"env {name!r} is required but not set")
    return value


@dataclass(frozen=True)
class Config:
    bot_token: str
    chat_id: int

    x_login: str = ""
    x_password: str = ""
    x_email: str = ""
    x_email_password: str = ""
    x_cookies: str = ""

    poll_interval_seconds: int = 180
    tweets_per_poll: int = 20
    request_delay_seconds: float = 2.5

    db_path: str = "bot.db"
    twscrape_db_path: str = "accounts.db"

    @property
    def has_x_credentials(self) -> bool:
        return bool(self.x_cookies)


def load_config() -> Config:
    return Config(
        bot_token=_required("BOT_TOKEN"),
        chat_id=int(_required("CHAT_ID")),
        x_login=os.getenv("X_LOGIN", "").strip(),
        x_password=os.getenv("X_PASSWORD", ""),
        x_email=os.getenv("X_EMAIL", "").strip(),
        x_email_password=os.getenv("X_EMAIL_PASSWORD", ""),
        x_cookies=os.getenv("X_COOKIES", "").strip(),
        poll_interval_seconds=max(30, _int("POLL_INTERVAL_SECONDS", 180)),
        tweets_per_poll=max(1, _int("TWEETS_PER_POLL", 20)),
        request_delay_seconds=max(0.0, _float("REQUEST_DELAY_SECONDS", 2.5)),
        db_path=os.getenv("DB_PATH", "bot.db").strip() or "bot.db",
        twscrape_db_path=os.getenv("TWSCRAPE_DB_PATH", "accounts.db").strip()
        or "accounts.db",
    )
