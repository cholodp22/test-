# ...

минималистичный telegram-бот, который пересылает посты из x (twitter) в одну
заданную беседу и трекает смены через `/exeduty`.

## возможности

- база отслеживаемых аккаунтов x
- пересылка новых твитов в `CHAT_ID` (прямые graphql-запросы к x по cookies
  технического аккаунта)
- команда `/exeduty` — заступить / окончить смену с подсчётом времени
- **все сообщения** в нижнем регистре, важные части — жирным

## два режима запуска

| режим | где живёт | как работает | команды |
|---|---|---|---|
| **always-on** (`python -m bot`) | свой vps / контейнер | держит aiogram polling, фоновый поллер тикает каждые `POLL_INTERVAL_SECONDS` | работают все команды (`/add`, `/remove`, `/list`, `/exeduty`, ...) |
| **cron** (`python -m bot.cron`) | github actions cron | один тик за запуск, выходит; стейт в `state/*.json` | `/exeduty` недоступен; `/add` / `/remove` — через `workflow_dispatch` |

## команды (always-on)

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

## переменные окружения

см. `.env.example`. обязательные:

- `BOT_TOKEN` — токен от [@botfather](https://t.me/botfather)
- `CHAT_ID` — id единственного чата, где бот реагирует и куда шлёт твиты
  (узнать: добавить бота в чат → `/chatid` или [@userinfobot](https://t.me/userinfobot))
- `X_COOKIES` — `auth_token=...; ct0=...` (dev tools → application → cookies → `x.com`)

## режим 1: always-on (свой vps)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# заполни .env
python -m bot
```

## режим 2: github actions cron (бесплатно, без карты)

cron-режим запускает один тик каждые 5 минут на ранерах github actions —
платить не нужно (для public-репо лимиты ~неограниченные, для private ~2000
минут/мес → потребуется поднять интервал до `*/30 * * * *`).

стейт хранится в репо в `state/*.json` — workflow коммитит обновлённый
`last_seen.json` обратно после каждого тика.

### настройка

1. **secrets:** `Settings → Secrets and variables → Actions → New repository secret`
   - `BOT_TOKEN`
   - `CHAT_ID`
   - `X_COOKIES`
2. **разрешить workflow коммитить:** `Settings → Actions → General → Workflow permissions → Read and write permissions`
3. **проверить cron** в `.github/workflows/bot.yml` (по дефолту `*/5 * * * *`)
4. готово — workflow `bot` будет тикать сам каждые 5 минут.

### управление списком из github actions

`Actions → bot → Run workflow`:

- **action=poll** — внеплановый тик
- **action=list** — вывести список в логах
- **action=add**, username=`elonmusk` — добавить
- **action=remove**, username=`elonmusk` — удалить

### локальная отладка cron-режима

```bash
python -m bot.cron --action list
python -m bot.cron --action add --username elonmusk
python -m bot.cron --action poll
```

## как это работает

1. `bot/config.py` — читает `.env` / `os.environ`
2. `bot/twitter.py` — graphql-клиент x по cookies
3. `bot/formatting.py` — рендер сообщения для tg
4. `bot/db.py` + `bot/poller.py` + `bot/handlers.py` + `bot/__main__.py` — always-on
5. `bot/state.py` + `bot/cron.py` + `.github/workflows/bot.yml` — cron-режим
