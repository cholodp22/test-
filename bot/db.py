"""sqlite database layer for tracked accounts and shifts."""

from __future__ import annotations

import time
from dataclasses import dataclass

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked_accounts (
    username      TEXT PRIMARY KEY,
    user_id       TEXT,
    last_tweet_id TEXT,
    added_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS shifts (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT NOT NULL,
    started_at INTEGER NOT NULL
);
"""


@dataclass(frozen=True)
class TrackedAccount:
    username: str
    user_id: str | None
    last_tweet_id: str | None
    added_at: int


@dataclass(frozen=True)
class Shift:
    user_id: int
    username: str
    started_at: int


class Database:
    def __init__(self, path: str) -> None:
        self._path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self._path) as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()

    @staticmethod
    def _norm(username: str) -> str:
        return username.strip().lstrip("@").lower()

    async def add_account(self, username: str) -> bool:
        username = self._norm(username)
        if not username:
            return False
        async with aiosqlite.connect(self._path) as conn:
            cur = await conn.execute(
                "INSERT OR IGNORE INTO tracked_accounts(username, added_at) "
                "VALUES (?, ?)",
                (username, int(time.time())),
            )
            await conn.commit()
            return cur.rowcount > 0

    async def remove_account(self, username: str) -> bool:
        username = self._norm(username)
        async with aiosqlite.connect(self._path) as conn:
            cur = await conn.execute(
                "DELETE FROM tracked_accounts WHERE username = ?", (username,)
            )
            await conn.commit()
            return cur.rowcount > 0

    async def list_accounts(self) -> list[TrackedAccount]:
        async with aiosqlite.connect(self._path) as conn:
            cur = await conn.execute(
                "SELECT username, user_id, last_tweet_id, added_at "
                "FROM tracked_accounts ORDER BY username ASC"
            )
            rows = await cur.fetchall()
        return [
            TrackedAccount(
                username=row[0],
                user_id=row[1],
                last_tweet_id=row[2],
                added_at=row[3],
            )
            for row in rows
        ]

    async def set_user_id(self, username: str, user_id: str) -> None:
        username = self._norm(username)
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "UPDATE tracked_accounts SET user_id = ? WHERE username = ?",
                (user_id, username),
            )
            await conn.commit()

    async def set_last_tweet_id(self, username: str, tweet_id: str) -> None:
        username = self._norm(username)
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "UPDATE tracked_accounts SET last_tweet_id = ? WHERE username = ?",
                (tweet_id, username),
            )
            await conn.commit()

    async def get_shift(self, user_id: int) -> Shift | None:
        async with aiosqlite.connect(self._path) as conn:
            cur = await conn.execute(
                "SELECT user_id, username, started_at FROM shifts WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        return Shift(user_id=row[0], username=row[1], started_at=row[2])

    async def start_shift(self, user_id: int, username: str) -> Shift:
        started_at = int(time.time())
        async with aiosqlite.connect(self._path) as conn:
            await conn.execute(
                "INSERT INTO shifts(user_id, username, started_at) VALUES (?, ?, ?)",
                (user_id, username, started_at),
            )
            await conn.commit()
        return Shift(user_id=user_id, username=username, started_at=started_at)

    async def end_shift(self, user_id: int) -> Shift | None:
        async with aiosqlite.connect(self._path) as conn:
            cur = await conn.execute(
                "SELECT user_id, username, started_at FROM shifts WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            await conn.execute("DELETE FROM shifts WHERE user_id = ?", (user_id,))
            await conn.commit()
        return Shift(user_id=row[0], username=row[1], started_at=row[2])
