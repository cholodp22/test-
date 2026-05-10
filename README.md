# ...

минималистичный telegram-бот, который пересылает посты из x (twitter) в одну
заданную беседу и трекает смены через `/exeduty`.

## возможности

- база отслеживаемых аккаунтов x (sqlite)
- фоновый поллер новых твитов через [twscrape](https://github.com/vladkens/twscrape)
  (логин под отдельным x-аккаунтом)
- команда `/exeduty` — заступить / окончить смену с подсчётом времени
- **все сообщения** в нижнем регистре, важные части — жирным

## команды

бот реагирует **только** в одном заданном чате (`CHAT_ID`). в любом другом
чате/личке — полное молчание.

| команда | описание |
|---|---|
| `/start`, `/help` | справка |
| `/exeduty` | заступить / окончить смену |
| `/add <username>` | добавить аккаунт x |
| `/remove <username>` | удалить аккаунт x |
| `/list` | список отслеживаемых |
| `/chatid` | id текущего чата |

## установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполни .env
python -m bot
```

## переменные окружения

см. `.env.example`. обязательные:

- `BOT_TOKEN` — токен от [@botfather](https://t.me/botfather)
- `CHAT_ID` — id единственного чата, где бот реагирует и куда шлёт твиты
  (узнать: добавить бота в чат, ненадолго снять `CHAT_ID`/перевести на любой
  тестовый id, написать `/chatid` — но проще через [@userinfobot](https://t.me/userinfobot)
  или forward сообщения в [@JsonDumpBot](https://t.me/JsonDumpBot))

для пересылки твитов нужны cookies технического x-аккаунта:

- `X_COOKIES` — формат `auth_token=...; ct0=...`,
  берётся в dev tools → application → cookies → `x.com` после ручного логина

без них бот запустится, но будет работать только `/exeduty` и команды управления.

## как это работает

1. `bot/config.py` читает `.env`
2. `bot/db.py` хранит отслеживаемых и активные смены в sqlite
3. `bot/twitter.py` логинит x-аккаунт через `twscrape`
4. `bot/poller.py` каждые `POLL_INTERVAL_SECONDS` обходит аккаунты,
   достаёт новые твиты по `last_tweet_id` и шлёт в `CHAT_ID`
5. `bot/handlers.py` обрабатывает команды телеграм
