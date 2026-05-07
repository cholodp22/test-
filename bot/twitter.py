"""thin async wrapper around twscrape for fetching new tweets."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import AsyncIterator

from twscrape import API, Tweet
from twscrape.logger import set_log_level

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewTweet:
    id: str
    username: str
    text: str
    url: str


class TwitterClient:
    def __init__(
        self,
        accounts_db: str,
        login: str,
        password: str,
        email: str = "",
        email_password: str = "",
        cookies: str = "",
    ) -> None:
        self._accounts_db = accounts_db
        self._login = login
        self._password = password
        self._email = email
        self._email_password = email_password
        self._cookies = cookies
        self._api: API | None = None

    @property
    def api(self) -> API:
        if self._api is None:
            raise RuntimeError("twitter client not initialised — call start() first")
        return self._api

    async def start(self) -> None:
        set_log_level("WARNING")
        self._api = API(self._accounts_db)

        kwargs: dict[str, str] = {}
        if self._cookies:
            kwargs["cookies"] = self._cookies

        await self._api.pool.add_account(
            self._login,
            self._password,
            self._email or f"{self._login}@example.invalid",
            self._email_password or "unused",
            **kwargs,
        )

        if self._cookies:
            log.info("twscrape pool ready (cookie-based auth)")
            return

        try:
            await self._api.pool.login_all()
        except Exception:  # noqa: BLE001
            log.exception(
                "twscrape login failed — provide X_COOKIES or X_EMAIL/X_EMAIL_PASSWORD"
            )
            raise
        log.info("twscrape pool ready (password-based auth)")

    async def resolve_user_id(self, username: str) -> str | None:
        username = username.lstrip("@")
        try:
            user = await self.api.user_by_login(username)
        except Exception as exc:  # noqa: BLE001
            log.warning("user_by_login(%s) failed: %s", username, exc)
            return None
        if user is None:
            return None
        return str(user.id)

    async def fetch_new(
        self,
        user_id: str,
        username: str,
        last_seen_id: str | None,
        limit: int,
    ) -> AsyncIterator[NewTweet]:
        """yield tweets newer than last_seen_id, oldest-first."""
        try:
            uid_int = int(user_id)
        except ValueError:
            log.warning("invalid user_id for %s: %r", username, user_id)
            return

        cutoff = int(last_seen_id) if last_seen_id and last_seen_id.isdigit() else 0
        collected: list[Tweet] = []
        try:
            async for tweet in self.api.user_tweets(uid_int, limit=limit):
                if tweet.id <= cutoff:
                    continue
                collected.append(tweet)
        except Exception as exc:  # noqa: BLE001
            log.warning("user_tweets(%s) failed: %s", username, exc)
            return

        for tweet in sorted(collected, key=lambda t: t.id):
            yield NewTweet(
                id=str(tweet.id),
                username=username,
                text=tweet.rawContent or "",
                url=tweet.url,
            )
