"""background task that polls tracked x accounts and forwards new tweets."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

from .config import Config
from .db import Database
from .formatting import tweet_message
from .twitter import TwitterClient

log = logging.getLogger(__name__)


class Poller:
    def __init__(
        self,
        bot: Bot,
        db: Database,
        twitter: TwitterClient,
        config: Config,
    ) -> None:
        self._bot = bot
        self._db = db
        self._twitter = twitter
        self._config = config
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="x-poller")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None

    async def _run(self) -> None:
        log.info("poller started (interval=%ss)", self._config.poll_interval_seconds)
        while not self._stop.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("poller tick failed")
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._config.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue
        log.info("poller stopped")

    async def _tick(self) -> None:
        accounts = await self._db.list_accounts()
        if not accounts:
            return

        for account in accounts:
            user_id = account.user_id
            if user_id is None:
                resolved = await self._twitter.resolve_user_id(account.username)
                if resolved is None:
                    log.warning("could not resolve @%s — skipping", account.username)
                    continue
                await self._db.set_user_id(account.username, resolved)
                user_id = resolved

            is_first_poll = not account.last_tweet_id
            highest_seen = account.last_tweet_id
            try:
                async for tweet in self._twitter.fetch_new(
                    user_id=user_id,
                    username=account.username,
                    last_seen_id=account.last_tweet_id,
                    limit=self._config.tweets_per_poll,
                ):
                    if not is_first_poll:
                        await self._send(tweet.username, tweet.text, tweet.url)
                    if highest_seen is None or int(tweet.id) > int(highest_seen):
                        highest_seen = tweet.id
            except Exception:  # noqa: BLE001
                log.exception("fetch failed for @%s", account.username)
                continue

            if is_first_poll and highest_seen is None:
                highest_seen = "0"
            if highest_seen and highest_seen != account.last_tweet_id:
                await self._db.set_last_tweet_id(account.username, highest_seen)
            if is_first_poll:
                log.info(
                    "@%s seeded at last_tweet_id=%s (no historical posts forwarded)",
                    account.username,
                    highest_seen,
                )

    async def _send(self, username: str, text: str, url: str) -> None:
        try:
            await self._bot.send_message(
                chat_id=self._config.chat_id,
                text=tweet_message(username, text, url),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        except TelegramAPIError as exc:
            log.warning("failed to forward tweet from @%s: %s", username, exc)
