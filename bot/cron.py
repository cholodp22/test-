"""one-shot batch entry point for github actions cron mode.

unlike `python -m bot` (always-on aiogram poller), this module runs a
single polling cycle and exits — designed to be invoked from a github
actions schedule. state lives in `state/*.json` and is committed back
to the repo by the workflow when it changes.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

from .config import Config, load_config
from .formatting import tweet_message
from .state import JsonState, TrackedAccount, normalize_username
from .twitter import TwitterClient

log = logging.getLogger(__name__)


async def _send(bot: Bot, chat_id: int, username: str, text: str, url: str) -> None:
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=tweet_message(username, text, url),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
    except TelegramAPIError as exc:
        log.warning("failed to forward tweet from @%s: %s", username, exc)


async def _ensure_user_id(
    state: JsonState, twitter: TwitterClient, account: TrackedAccount
) -> str | None:
    if account.user_id:
        return account.user_id
    resolved = await twitter.resolve_user_id(account.username)
    if resolved is None:
        log.warning("could not resolve @%s — will retry next run", account.username)
        return None
    state.set_user_id(account.username, resolved)
    return resolved


async def _poll_account(
    state: JsonState,
    twitter: TwitterClient,
    bot: Bot,
    config: Config,
    account: TrackedAccount,
) -> None:
    user_id = await _ensure_user_id(state, twitter, account)
    if user_id is None:
        return

    last_seen = state.load_last_seen().get(account.username)
    is_first_poll = not last_seen
    highest_seen = last_seen
    try:
        async for tweet in twitter.fetch_new(
            user_id=user_id,
            username=account.username,
            last_seen_id=last_seen,
            limit=config.tweets_per_poll,
        ):
            if not is_first_poll:
                await _send(
                    bot, config.chat_id, tweet.username, tweet.text, tweet.url
                )
            if highest_seen is None or int(tweet.id) > int(highest_seen):
                highest_seen = tweet.id
    except Exception:  # noqa: BLE001
        log.exception("fetch failed for @%s", account.username)
        return

    if is_first_poll and highest_seen is None:
        highest_seen = "0"
    if highest_seen and highest_seen != last_seen:
        state.set_last_seen(account.username, highest_seen)
    if is_first_poll:
        log.info(
            "@%s seeded at %s (no historical posts forwarded)",
            account.username,
            highest_seen,
        )


async def cmd_poll(state: JsonState, twitter: TwitterClient, bot: Bot, config: Config) -> int:
    accounts = state.list_accounts()
    if not accounts:
        log.info("no tracked accounts — nothing to poll")
        return 0
    delay = config.request_delay_seconds
    log.info("polling %d accounts (stagger=%.1fs)", len(accounts), delay)
    for index, account in enumerate(accounts):
        if index > 0 and delay > 0:
            await asyncio.sleep(delay)
        await _poll_account(state, twitter, bot, config, account)
    log.info("poll cycle complete")
    return 0


async def cmd_add(state: JsonState, twitter: TwitterClient, username: str) -> int:
    norm = normalize_username(username)
    if not norm:
        log.error("username is empty")
        return 2
    added = state.add_account(norm)
    if not added:
        log.info("@%s already tracked", norm)
        return 0
    user_id = await twitter.resolve_user_id(norm)
    if user_id is None:
        log.warning("@%s added — could not resolve x user_id, will retry next poll", norm)
    else:
        state.set_user_id(norm, user_id)
        log.info("@%s added (user_id=%s)", norm, user_id)
    return 0


def cmd_remove(state: JsonState, username: str) -> int:
    norm = normalize_username(username)
    if not norm:
        log.error("username is empty")
        return 2
    if state.remove_account(norm):
        log.info("@%s removed", norm)
        return 0
    log.warning("@%s was not tracked", norm)
    return 0


def cmd_list(state: JsonState) -> int:
    accounts = state.list_accounts()
    if not accounts:
        log.info("(no tracked accounts)")
        return 0
    log.info("tracked accounts (%d):", len(accounts))
    for a in accounts:
        log.info("  • @%s (user_id=%s)", a.username, a.user_id or "?")
    return 0


async def amain(action: str, username: str | None) -> int:
    config = load_config()
    state = JsonState()

    if action == "list":
        return cmd_list(state)

    if action == "remove":
        if not username:
            log.error("--username is required for remove")
            return 2
        return cmd_remove(state, username)

    if not config.has_x_credentials:
        log.error("X_COOKIES is required for poll/add")
        return 2

    twitter = TwitterClient(cookies=config.x_cookies)
    await twitter.start()
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        if action == "poll":
            return await cmd_poll(state, twitter, bot, config)
        if action == "add":
            if not username:
                log.error("--username is required for add")
                return 2
            return await cmd_add(state, twitter, username)
        log.error("unknown action: %s", action)
        return 2
    finally:
        await twitter.stop()
        await bot.session.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    parser = argparse.ArgumentParser(description="cron-mode bot (one-shot)")
    parser.add_argument(
        "--action",
        choices=("poll", "add", "remove", "list"),
        default="poll",
        help="what to do (default: poll)",
    )
    parser.add_argument(
        "--username",
        default=None,
        help="username for add/remove (with or without @)",
    )
    args = parser.parse_args()
    return asyncio.run(amain(args.action, args.username))


if __name__ == "__main__":
    sys.exit(main())
