#!/usr/bin/env python3
"""Telegram text-to-speech bot.

Send the bot any text and it returns an MP3 generated with Microsoft Edge TTS.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path

import edge_tts
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_VOICE = os.getenv("TTS_VOICE", "ru-RU-DmitryNeural").strip()
DEFAULT_RATE = os.getenv("TTS_RATE", "+0%").strip()
DEFAULT_VOLUME = os.getenv("TTS_VOLUME", "+0%").strip()
MAX_CHARS = int(os.getenv("MAX_CHARS", "3500"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", tempfile.gettempdir())).expanduser()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("telegram-tts-bot")


def clean_text(text: str) -> str:
    text = text.strip()
    # Telegram often sends URLs/markdown fine, but normalize excessive whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text


async def synthesize_mp3(text: str, voice: str = DEFAULT_VOICE) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"tts_{uuid.uuid4().hex}.mp3"
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=DEFAULT_RATE,
        volume=DEFAULT_VOLUME,
    )
    await communicate.save(str(out))
    return out


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Пришли мне текст — я верну MP3-аудиофайл.\n\n"
        "Команды:\n"
        "/voice <voice> — сменить голос для этого чата\n"
        "/voices — подсказка по голосам\n"
        "/help — помощь"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Просто отправь текст до {MAX_CHARS} символов.\n"
        "По умолчанию голос: " + DEFAULT_VOICE + "\n\n"
        "Примеры голосов:\n"
        "ru-RU-DmitryNeural — русский мужской\n"
        "ru-RU-SvetlanaNeural — русский женский\n"
        "en-US-GuyNeural — английский мужской\n"
        "en-US-JennyNeural — английский женский\n\n"
        "Сменить голос: /voice ru-RU-SvetlanaNeural"
    )


async def voices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Популярные голоса:\n"
        "• ru-RU-DmitryNeural\n"
        "• ru-RU-SvetlanaNeural\n"
        "• uk-UA-OstapNeural\n"
        "• uk-UA-PolinaNeural\n"
        "• en-US-GuyNeural\n"
        "• en-US-JennyNeural\n\n"
        "Полный список можно получить командой:\n"
        "python -m edge_tts --list-voices"
    )


async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        current = context.user_data.get("voice", DEFAULT_VOICE)
        await update.message.reply_text(f"Текущий голос: {current}\nСменить: /voice ru-RU-SvetlanaNeural")
        return
    voice = context.args[0].strip()
    if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural", voice):
        await update.message.reply_text("Похоже на неверное имя голоса. Пример: /voice ru-RU-SvetlanaNeural")
        return
    context.user_data["voice"] = voice
    await update.message.reply_text(f"Ок, голос для этого чата: {voice}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text:
        return

    text = clean_text(msg.text)
    if not text:
        await msg.reply_text("Пришли непустой текст.")
        return
    if len(text) > MAX_CHARS:
        await msg.reply_text(f"Текст слишком длинный: {len(text)} символов. Лимит: {MAX_CHARS}.")
        return

    voice = context.user_data.get("voice", DEFAULT_VOICE)
    out: Path | None = None
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.UPLOAD_VOICE)
        out = await synthesize_mp3(text, voice=voice)
        title = text[:45].replace("\n", " ")
        if len(text) > 45:
            title += "…"
        await msg.reply_audio(
            audio=out.open("rb"),
            title=title,
            performer="TTS Bot",
            caption=f"Голос: {voice}",
        )
    except Exception as exc:  # noqa: BLE001 - user-facing bot should not crash on one bad request
        log.exception("TTS failed")
        await msg.reply_text(f"Не смог сгенерировать аудио: {exc}")
    finally:
        if out:
            try:
                out.unlink(missing_ok=True)
            except Exception:
                log.warning("Could not remove temp file %s", out)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN. Put it in .env or environment.")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("voices", voices))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Starting Telegram TTS bot with default voice %s", DEFAULT_VOICE)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
