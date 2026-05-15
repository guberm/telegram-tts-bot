# Telegram TTS Bot

Бот принимает текст в Telegram и возвращает MP3-аудиофайл, сгенерированный через `edge-tts`.

## Возможности

- Любой текст → MP3 audio reply
- Русские/украинские/английские Edge Neural voices
- `/voice <voice>` — голос на пользователя/чат
- `/voices` — быстрые примеры голосов
- Лимит длины текста через `MAX_CHARS`
- Polling mode: не нужен webhook/домен/SSL

## Быстрый запуск

1. Создай бота в Telegram через `@BotFather` и получи token.
2. Подготовь проект:

```bash
cd ~/telegram-tts-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # вставь TELEGRAM_BOT_TOKEN
python bot.py
```

3. Напиши боту `/start`, потом отправь любой текст.

## Настройки `.env`

```env
TELEGRAM_BOT_TOKEN=...
TTS_VOICE=ru-RU-DmitryNeural
TTS_RATE=+0%
TTS_VOLUME=+0%
MAX_CHARS=3500
OUTPUT_DIR=/tmp/telegram-tts-bot
LOG_LEVEL=INFO
```

## Голоса

Популярные:

- `ru-RU-DmitryNeural` — русский мужской
- `ru-RU-SvetlanaNeural` — русский женский
- `uk-UA-OstapNeural` — украинский мужской
- `uk-UA-PolinaNeural` — украинский женский
- `en-US-GuyNeural` — английский мужской
- `en-US-JennyNeural` — английский женский

Полный список:

```bash
source ~/telegram-tts-bot/.venv/bin/activate
python -m edge_tts --list-voices
```

## Systemd service

```bash
cd ~/telegram-tts-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env

sudo cp telegram-tts-bot.service /etc/systemd/system/telegram-tts-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-tts-bot
sudo systemctl status telegram-tts-bot
```

Логи:

```bash
journalctl -u telegram-tts-bot -f
```

## Docker

```bash
cd ~/telegram-tts-bot
docker build -t telegram-tts-bot .
docker run --rm --env-file .env telegram-tts-bot
```

## Security

- Не коммить `.env` с токеном.
- Если бот только личный, не публикуй username широко.
- При желании можно добавить allowlist по Telegram user ID.
