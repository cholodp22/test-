"""bot entry point."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import Config, load_config
from .db import Database
from .handlers import build_dispatcher
from .poller import Poller
from .twitter import TwitterClient


async def _amain(config: Config) -> None:
    db = Database(config.db_path)
    await db.init()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    twitter: TwitterClient | None = None
    poller: Poller | None = None
    if config.has_x_credentials:
        twitter = TwitterClient(cookies=config.x_cookies)
        try:
            await twitter.start()
            poller = Poller(bot=bot, db=db, twitter=twitter, config=config)
            poller.start()
        except Exception:  # noqa: BLE001
            logging.exception("twitter init failed — continuing without poller")
            if twitter is not None:
                await twitter.stop()
            twitter = None
            poller = None
    else:
        logging.warning(
            "x credentials not configured — bot runs without forwarding"
        )

    dp = build_dispatcher(bot=bot, db=db, twitter=twitter, config=config)

    try:
        await dp.start_polling(bot, handle_signals=True)
    finally:
        if poller is not None:
            await poller.stop()
        if twitter is not None:
            await twitter.stop()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    config = load_config()
    asyncio.run(_amain(config))


if __name__ == "__main__":
    main()
