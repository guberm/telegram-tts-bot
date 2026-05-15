# Telegram TTS Bot

A small Telegram bot that converts any text message into an MP3 audio file using Microsoft Edge Text-to-Speech (`edge-tts`).

Небольшой Telegram-бот, который принимает текстовое сообщение и возвращает MP3-аудиофайл, сгенерированный через Microsoft Edge Text-to-Speech (`edge-tts`).

---

## English

### Features

- Send any text message and receive an MP3 audio reply.
- Uses free Microsoft Edge neural voices via `edge-tts`.
- Supports Russian, Ukrainian, English, and many other languages.
- Per-chat/user voice selection with `/voice <voice>`.
- Quick voice examples with `/voices`.
- Configurable text length limit via `MAX_CHARS`.
- Polling mode: no webhook, public domain, or SSL certificate required.
- Optional Docker and systemd service setup.

### Quick start

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and copy the bot token.
2. Clone and install:

```bash
git clone https://github.com/guberm/telegram-tts-bot.git
cd telegram-tts-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # paste TELEGRAM_BOT_TOKEN
python bot.py
```

3. Open your bot in Telegram, send `/start`, then send any text.

### Configuration

Create `.env` from `.env.example`:

```env
TELEGRAM_BOT_TOKEN=your_botfather_token_here
TTS_VOICE=ru-RU-DmitryNeural
TTS_RATE=+0%
TTS_VOLUME=+0%
MAX_CHARS=3500
OUTPUT_DIR=/tmp/telegram-tts-bot
LOG_LEVEL=INFO
```

Configuration values:

- `TELEGRAM_BOT_TOKEN`: required Telegram bot token from BotFather.
- `TTS_VOICE`: default Edge TTS voice.
- `TTS_RATE`: speech rate, for example `+0%`, `-10%`, `+15%`.
- `TTS_VOLUME`: speech volume, for example `+0%`, `-10%`, `+20%`.
- `MAX_CHARS`: maximum input text length.
- `OUTPUT_DIR`: temporary directory for generated MP3 files.
- `LOG_LEVEL`: Python logging level.

### Bot commands

- `/start` — start message.
- `/help` — usage help.
- `/voices` — show common voice examples.
- `/voice` — show the current voice.
- `/voice ru-RU-SvetlanaNeural` — change voice for the current user/chat.

### Common voices

- `ru-RU-DmitryNeural` — Russian male.
- `ru-RU-SvetlanaNeural` — Russian female.
- `uk-UA-OstapNeural` — Ukrainian male.
- `uk-UA-PolinaNeural` — Ukrainian female.
- `en-US-GuyNeural` — English male.
- `en-US-JennyNeural` — English female.

Full voice list:

```bash
source .venv/bin/activate
python -m edge_tts --list-voices
```

### Run as a systemd service

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

Logs:

```bash
journalctl -u telegram-tts-bot -f
```

### Docker

```bash
git clone https://github.com/guberm/telegram-tts-bot.git
cd telegram-tts-bot
cp .env.example .env
nano .env

docker build -t telegram-tts-bot .
docker run --rm --env-file .env telegram-tts-bot
```

### Security notes

- Never commit `.env` with your real bot token.
- Keep your BotFather token private.
- If the bot is personal-only, do not publish its username widely.
- For stricter personal use, add a Telegram user ID allowlist in `bot.py`.

---

## Русский

### Возможности

- Отправляешь любой текст — получаешь MP3-аудиофайл в ответ.
- Использует бесплатные Microsoft Edge neural voices через `edge-tts`.
- Поддерживает русский, украинский, английский и многие другие языки.
- Выбор голоса на пользователя/чат через `/voice <voice>`.
- Быстрые примеры голосов через `/voices`.
- Лимит длины текста настраивается через `MAX_CHARS`.
- Polling mode: не нужен webhook, публичный домен или SSL-сертификат.
- Есть запуск через Docker и systemd.

### Быстрый запуск

1. Создай Telegram-бота через [@BotFather](https://t.me/BotFather) и скопируй token.
2. Склонируй проект и установи зависимости:

```bash
git clone https://github.com/guberm/telegram-tts-bot.git
cd telegram-tts-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # вставь TELEGRAM_BOT_TOKEN
python bot.py
```

3. Открой своего бота в Telegram, отправь `/start`, потом отправь любой текст.

### Настройки

Создай `.env` из `.env.example`:

```env
TELEGRAM_BOT_TOKEN=твой_token_от_botfather
TTS_VOICE=ru-RU-DmitryNeural
TTS_RATE=+0%
TTS_VOLUME=+0%
MAX_CHARS=3500
OUTPUT_DIR=/tmp/telegram-tts-bot
LOG_LEVEL=INFO
```

Параметры:

- `TELEGRAM_BOT_TOKEN`: обязательный token Telegram-бота от BotFather.
- `TTS_VOICE`: голос Edge TTS по умолчанию.
- `TTS_RATE`: скорость речи, например `+0%`, `-10%`, `+15%`.
- `TTS_VOLUME`: громкость речи, например `+0%`, `-10%`, `+20%`.
- `MAX_CHARS`: максимальная длина входного текста.
- `OUTPUT_DIR`: временная папка для MP3-файлов.
- `LOG_LEVEL`: уровень логирования Python.

### Команды бота

- `/start` — стартовое сообщение.
- `/help` — помощь.
- `/voices` — примеры популярных голосов.
- `/voice` — показать текущий голос.
- `/voice ru-RU-SvetlanaNeural` — сменить голос для текущего пользователя/чата.

### Популярные голоса

- `ru-RU-DmitryNeural` — русский мужской.
- `ru-RU-SvetlanaNeural` — русский женский.
- `uk-UA-OstapNeural` — украинский мужской.
- `uk-UA-PolinaNeural` — украинский женский.
- `en-US-GuyNeural` — английский мужской.
- `en-US-JennyNeural` — английский женский.

Полный список голосов:

```bash
source .venv/bin/activate
python -m edge_tts --list-voices
```

### Запуск как systemd service

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

### Docker

```bash
git clone https://github.com/guberm/telegram-tts-bot.git
cd telegram-tts-bot
cp .env.example .env
nano .env

docker build -t telegram-tts-bot .
docker run --rm --env-file .env telegram-tts-bot
```

### Безопасность

- Не коммить `.env` с реальным токеном.
- Держи BotFather token приватным.
- Если бот только личный, не публикуй username широко.
- Для более строгого личного использования можно добавить allowlist по Telegram user ID в `bot.py`.
