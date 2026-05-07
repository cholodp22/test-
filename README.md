# test-

минималистичный telegram-бот, который пересылает посты из x (twitter) в одну
заданную беседу и трекает смены через `/exeduty`.

## возможности

- база отслеживаемых аккаунтов x (sqlite)
- фоновый поллер новых твитов через [twscrape](https://github.com/vladkens/twscrape)
  (логин под отдельным x-аккаунтом)
- команда `/exeduty` — заступить / окончить смену с подсчётом времени
- **все сообщения** в нижнем регистре, важные части — жирным

## команды

| команда | описание |
|---|---|
| `/start`, `/help` | справка |
| `/exeduty` | заступить / окончить смену |
| `/add <username>` | добавить аккаунт x (админ) |
| `/remove <username>` | удалить аккаунт x (админ) |
| `/list` | список отслеживаемых (админ) |
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
- `CHAT_ID` — id беседы, куда слать твиты (можно узнать командой `/chatid`)
- `ADMIN_IDS` — список user-id через запятую, кому разрешены `/add /remove /list`
  (если не задан — доступно всем)

для пересылки твитов нужны креды x:

- `X_LOGIN`, `X_PASSWORD`, `X_EMAIL`, `X_EMAIL_PASSWORD`

без них бот запустится, но будет работать только `/exeduty` и команды управления.

## как это работает

1. `bot/config.py` читает `.env`
2. `bot/db.py` хранит отслеживаемых и активные смены в sqlite
3. `bot/twitter.py` логинит x-аккаунт через `twscrape`
4. `bot/poller.py` каждые `POLL_INTERVAL_SECONDS` обходит аккаунты,
   достаёт новые твиты по `last_tweet_id` и шлёт в `CHAT_ID`
5. `bot/handlers.py` обрабатывает команды телеграм
