"""telegram command handlers."""

from __future__ import annotations

import logging
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from .config import Config
from .db import Database
from .formatting import b, shift_ended, shift_started
from .twitter import TwitterClient

log = logging.getLogger(__name__)


HELP = (
    "минималистичный бот для пересылки постов из x.\n\n"
    "команды:\n"
    "• /exeduty — заступить / окончить смену\n"
    "• /add &lt;username&gt; — добавить аккаунт x (админ)\n"
    "• /remove &lt;username&gt; — удалить аккаунт x (админ)\n"
    "• /list — список отслеживаемых (админ)\n"
)


def _display_name(message: Message) -> str:
    user = message.from_user
    if user is None:
        return "unknown"
    if user.username:
        return user.username
    return (user.full_name or "unknown").lower()


def _is_admin(message: Message, config: Config) -> bool:
    if not config.admin_ids:
        return True
    user = message.from_user
    return user is not None and user.id in config.admin_ids


def build_dispatcher(
    bot: Bot,
    db: Database,
    twitter: TwitterClient | None,
    config: Config,
) -> Dispatcher:
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        await message.answer(
            "привет.\nя пересылаю " + b("новости из x") + " в эту беседу.\n\n" + HELP,
            parse_mode=ParseMode.HTML,
        )

    @dp.message(Command("help"))
    async def on_help(message: Message) -> None:
        await message.answer(HELP, parse_mode=ParseMode.HTML)

    @dp.message(Command("exeduty"))
    async def on_exeduty(message: Message) -> None:
        user = message.from_user
        if user is None:
            return
        username = _display_name(message)
        active = await db.get_shift(user.id)
        if active is None:
            await db.start_shift(user.id, username)
            await message.answer(shift_started(username), parse_mode=ParseMode.HTML)
            return
        ended = await db.end_shift(user.id)
        elapsed = int(time.time()) - (ended.started_at if ended else active.started_at)
        await message.answer(
            shift_ended(username, elapsed),
            parse_mode=ParseMode.HTML,
        )

    @dp.message(Command("add"))
    async def on_add(message: Message) -> None:
        if not _is_admin(message, config):
            return
        text = (message.text or "").split(maxsplit=1)
        if len(text) < 2 or not text[1].strip():
            await message.answer(
                "укажи username: " + b("/add elonmusk"),
                parse_mode=ParseMode.HTML,
            )
            return
        username = text[1].strip().split()[0]
        added = await db.add_account(username)
        clean = username.lstrip("@").lower()
        if added:
            await message.answer(
                "добавлен " + b("@" + clean),
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.answer(
                b("@" + clean) + " уже отслеживается",
                parse_mode=ParseMode.HTML,
            )

    @dp.message(Command("remove"))
    async def on_remove(message: Message) -> None:
        if not _is_admin(message, config):
            return
        text = (message.text or "").split(maxsplit=1)
        if len(text) < 2 or not text[1].strip():
            await message.answer(
                "укажи username: " + b("/remove elonmusk"),
                parse_mode=ParseMode.HTML,
            )
            return
        username = text[1].strip().split()[0]
        removed = await db.remove_account(username)
        clean = username.lstrip("@").lower()
        if removed:
            await message.answer(
                "удалён " + b("@" + clean),
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.answer(
                b("@" + clean) + " не найден",
                parse_mode=ParseMode.HTML,
            )

    @dp.message(Command("list"))
    async def on_list(message: Message) -> None:
        if not _is_admin(message, config):
            return
        accounts = await db.list_accounts()
        if not accounts:
            await message.answer("список " + b("пуст"), parse_mode=ParseMode.HTML)
            return
        body = "\n".join(f"• <b>@{a.username}</b>" for a in accounts)
        await message.answer(
            "отслеживаемые аккаунты:\n" + body,
            parse_mode=ParseMode.HTML,
        )

    @dp.message(Command("chatid"))
    async def on_chatid(message: Message) -> None:
        await message.answer(
            "chat id: " + b(str(message.chat.id)),
            parse_mode=ParseMode.HTML,
        )

    @dp.message(F.chat.type == ChatType.PRIVATE)
    async def on_unknown_private(message: Message) -> None:
        if (message.text or "").startswith("/"):
            await message.answer(HELP, parse_mode=ParseMode.HTML)

    return dp
