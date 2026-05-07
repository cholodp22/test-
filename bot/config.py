"""configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

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


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"env {name!r} is required but not set")
    return value


def _admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "").strip()
    if not raw:
        return set()
    out: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.add(int(chunk))
        except ValueError as exc:
            raise ValueError(f"ADMIN_IDS must contain integers, got {chunk!r}") from exc
    return out


@dataclass(frozen=True)
class Config:
    bot_token: str
    chat_id: int
    admin_ids: set[int] = field(default_factory=set)

    x_login: str = ""
    x_password: str = ""
    x_email: str = ""
    x_email_password: str = ""

    poll_interval_seconds: int = 120
    tweets_per_poll: int = 20

    db_path: str = "bot.db"
    twscrape_db_path: str = "accounts.db"

    @property
    def has_x_credentials(self) -> bool:
        return all(
            [self.x_login, self.x_password, self.x_email, self.x_email_password]
        )


def load_config() -> Config:
    return Config(
        bot_token=_required("BOT_TOKEN"),
        chat_id=int(_required("CHAT_ID")),
        admin_ids=_admin_ids(),
        x_login=os.getenv("X_LOGIN", "").strip(),
        x_password=os.getenv("X_PASSWORD", ""),
        x_email=os.getenv("X_EMAIL", "").strip(),
        x_email_password=os.getenv("X_EMAIL_PASSWORD", ""),
        poll_interval_seconds=max(30, _int("POLL_INTERVAL_SECONDS", 120)),
        tweets_per_poll=max(1, _int("TWEETS_PER_POLL", 20)),
        db_path=os.getenv("DB_PATH", "bot.db").strip() or "bot.db",
        twscrape_db_path=os.getenv("TWSCRAPE_DB_PATH", "accounts.db").strip()
        or "accounts.db",
    )
