"""telegram command handlers."""

from __future__ import annotations

import logging
import time

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from .config import Config
from .db import Database
from .formatting import b, shift_ended, shift_started
from .twitter import TwitterClient

log = logging.getLogger(__name__)


START_TEXT = (
    "🤡 <b>slaveEXE</b> — специально разработанный бот для оперативного ведения "
    "телеграм-каналов сетки .exe\n\n"
    "<b>команды:</b>\n"
    ". /exeduty — заступить / окончить смену [отслеживание часов]\n"
    ". /add &lt;username&gt; — добавить отслеживаемый аккаунт\n"
    ". /remove &lt;username&gt; — удалить отслеживание\n"
    ". /list — список отслеживаемых аккаунтов\n\n"
    "<b>prescription:</b>\n"
    ". добавить/удалить новый отслеживаемый аккаунт — обращайся к своему начальнику\n"
)

HELP = START_TEXT


def _display_name(message: Message) -> str:
    user = message.from_user
    if user is None:
        return "unknown"
    if user.username:
        return user.username
    return (user.full_name or "unknown").lower()


def build_dispatcher(
    bot: Bot,
    db: Database,
    twitter: TwitterClient | None,
    config: Config,
) -> Dispatcher:
    dp = Dispatcher()
    # bot reacts ONLY in the configured chat — 0 reaction anywhere else.
    dp.message.filter(F.chat.id == config.chat_id)

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        await message.answer(START_TEXT, parse_mode=ParseMode.HTML)

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
        accounts = await db.list_accounts()
        if not accounts:
            await message.answer("список " + b("пуст"), parse_mode=ParseMode.HTML)
            return
        body = "\n".join(f"• {b('@' + a.username)}" for a in accounts)
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

    return dp
