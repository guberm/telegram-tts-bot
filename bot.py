#!/usr/bin/env python3
"""Telegram text-to-speech bot.

Send the bot any text and it returns an MP3 generated with Microsoft Edge TTS.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from pathlib import Path

import edge_tts
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_VOICE = os.getenv("TTS_VOICE", "ru-RU-DmitryNeural").strip()
DEFAULT_RATE = os.getenv("TTS_RATE", "+0%").strip()
DEFAULT_VOLUME = os.getenv("TTS_VOLUME", "+0%").strip()
MAX_CHARS = int(os.getenv("MAX_CHARS", "3500"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", tempfile.gettempdir())).expanduser()
PERSISTENCE_FILE = Path(os.getenv("PERSISTENCE_FILE", "data/bot-state.pickle")).expanduser()
DEFAULT_LANG = "en"
SUPPORTED_LANGS = {"en", "ru"}
LANG_BUTTON_TEXTS = {"🌐 Language", "🌐 Язык", "Language", "Язык"}

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.request").setLevel(logging.WARNING)
log = logging.getLogger("telegram-tts-bot")

TEXTS = {
    "en": {
        "start": (
            "Send me text and I will return an MP3 audio file.\n\n"
            "Commands:\n"
            "/voice <voice> — change the TTS voice for this chat\n"
            "/voices — voice examples\n"
            "/language — choose interface language\n"
            "/help — help"
        ),
        "help": (
            "Just send text up to {max_chars} characters.\n"
            "Default voice: {default_voice}\n\n"
            "Voice examples:\n"
            "ru-RU-DmitryNeural — Russian male\n"
            "ru-RU-SvetlanaNeural — Russian female\n"
            "en-US-GuyNeural — English male\n"
            "en-US-JennyNeural — English female\n\n"
            "Change voice: /voice ru-RU-SvetlanaNeural\n"
            "Change interface language: /language"
        ),
        "voices": (
            "Popular voices:\n"
            "• ru-RU-DmitryNeural\n"
            "• ru-RU-SvetlanaNeural\n"
            "• uk-UA-OstapNeural\n"
            "• uk-UA-PolinaNeural\n"
            "• en-US-GuyNeural\n"
            "• en-US-JennyNeural\n\n"
            "Full list on the server:\n"
            "python -m edge_tts --list-voices"
        ),
        "language_prompt": "Choose interface language:",
        "language_set": "Interface language set to English.",
        "current_voice": "Current voice: {voice}\nChange it: /voice ru-RU-SvetlanaNeural",
        "invalid_voice": "This does not look like a valid voice name. Example: /voice ru-RU-SvetlanaNeural",
        "voice_set": "OK, voice for this chat: {voice}",
        "empty_text": "Send non-empty text.",
        "too_long": "Text is too long: {length} characters. Limit: {max_chars}.",
        "caption_voice": "Voice: {voice}",
        "tts_failed": "Could not generate audio: {error}",
        "main_menu_button": "🌐 Language",
    },
    "ru": {
        "start": (
            "Пришли мне текст — я верну MP3-аудиофайл.\n\n"
            "Команды:\n"
            "/voice <voice> — сменить голос для этого чата\n"
            "/voices — подсказка по голосам\n"
            "/language — выбрать язык интерфейса\n"
            "/help — помощь"
        ),
        "help": (
            "Просто отправь текст до {max_chars} символов.\n"
            "Голос по умолчанию: {default_voice}\n\n"
            "Примеры голосов:\n"
            "ru-RU-DmitryNeural — русский мужской\n"
            "ru-RU-SvetlanaNeural — русский женский\n"
            "en-US-GuyNeural — английский мужской\n"
            "en-US-JennyNeural — английский женский\n\n"
            "Сменить голос: /voice ru-RU-SvetlanaNeural\n"
            "Сменить язык интерфейса: /language"
        ),
        "voices": (
            "Популярные голоса:\n"
            "• ru-RU-DmitryNeural\n"
            "• ru-RU-SvetlanaNeural\n"
            "• uk-UA-OstapNeural\n"
            "• uk-UA-PolinaNeural\n"
            "• en-US-GuyNeural\n"
            "• en-US-JennyNeural\n\n"
            "Полный список на сервере:\n"
            "python -m edge_tts --list-voices"
        ),
        "language_prompt": "Выбери язык интерфейса:",
        "language_set": "Язык интерфейса: русский.",
        "current_voice": "Текущий голос: {voice}\nСменить: /voice ru-RU-SvetlanaNeural",
        "invalid_voice": "Похоже на неверное имя голоса. Пример: /voice ru-RU-SvetlanaNeural",
        "voice_set": "Ок, голос для этого чата: {voice}",
        "empty_text": "Пришли непустой текст.",
        "too_long": "Текст слишком длинный: {length} символов. Лимит: {max_chars}.",
        "caption_voice": "Голос: {voice}",
        "tts_failed": "Не смог сгенерировать аудио: {error}",
        "main_menu_button": "🌐 Язык",
    },
}


def clean_text(text: str) -> str:
    text = text.strip()
    # Telegram often sends URLs/markdown fine, but normalize excessive whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text


def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    lang = context.user_data.get("lang", DEFAULT_LANG)
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def t(context: ContextTypes.DEFAULT_TYPE, key: str, **kwargs: object) -> str:
    template = TEXTS[get_lang(context)][key]
    return template.format(**kwargs)


def main_menu(context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[TEXTS[get_lang(context)]["main_menu_button"]]],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Type text for TTS",
    )


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("English", callback_data="lang:en"), InlineKeyboardButton("Русский", callback_data="lang:ru")]]
    )


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


def log_update(update: Update, event: str) -> None:
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if not msg:
        log.info("%s: non-message update_id=%s", event, update.update_id)
        return
    user = update.effective_user
    log.info(
        "%s: chat_id=%s chat_type=%s user_id=%s username=%s first_name=%s",
        event,
        msg.chat_id,
        msg.chat.type if msg.chat else None,
        user.id if user else None,
        user.username if user else None,
        user.first_name if user else None,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_update(update, "start")
    await update.message.reply_text(t(context, "start"), reply_markup=main_menu(context))
    await update.message.reply_text(t(context, "language_prompt"), reply_markup=language_keyboard())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        t(context, "help", max_chars=MAX_CHARS, default_voice=DEFAULT_VOICE),
        reply_markup=main_menu(context),
    )


async def voices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(t(context, "voices"), reply_markup=main_menu(context))


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_update(update, "language")
    await update.message.reply_text(t(context, "language_prompt"), reply_markup=language_keyboard())


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_update(update, "language_callback")
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":", 1)[1]
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    context.user_data["lang"] = lang
    await query.edit_message_text(TEXTS[lang]["language_set"])
    await query.message.reply_text(TEXTS[lang]["start"], reply_markup=main_menu(context))


async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        current = context.user_data.get("voice", DEFAULT_VOICE)
        await update.message.reply_text(t(context, "current_voice", voice=current), reply_markup=main_menu(context))
        return
    voice = context.args[0].strip()
    if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural", voice):
        await update.message.reply_text(t(context, "invalid_voice"), reply_markup=main_menu(context))
        return
    context.user_data["voice"] = voice
    await update.message.reply_text(t(context, "voice_set", voice=voice), reply_markup=main_menu(context))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_update(update, "text")
    msg = update.message
    if not msg or not msg.text:
        return

    text = clean_text(msg.text)
    if text in LANG_BUTTON_TEXTS:
        await language_cmd(update, context)
        return
    if not text:
        await msg.reply_text(t(context, "empty_text"), reply_markup=main_menu(context))
        return
    if len(text) > MAX_CHARS:
        await msg.reply_text(
            t(context, "too_long", length=len(text), max_chars=MAX_CHARS),
            reply_markup=main_menu(context),
        )
        return

    voice = context.user_data.get("voice", DEFAULT_VOICE)
    out: Path | None = None
    try:
        await context.bot.send_chat_action(chat_id=msg.chat_id, action=ChatAction.UPLOAD_VOICE)
        out = await synthesize_mp3(text, voice=voice)
        title = text[:45].replace("\n", " ")
        if len(text) > 45:
            title += "…"
        with out.open("rb") as audio_file:
            await msg.reply_audio(
                audio=audio_file,
                title=title,
                performer="TTS Bot",
                caption=t(context, "caption_voice", voice=voice),
                reply_markup=main_menu(context),
            )
    except Exception as exc:  # noqa: BLE001 - user-facing bot should not crash on one bad request
        log.exception("TTS failed")
        await msg.reply_text(t(context, "tts_failed", error=exc), reply_markup=main_menu(context))
    finally:
        if out:
            try:
                out.unlink(missing_ok=True)
            except Exception:
                log.warning("Could not remove temp file %s", out)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN. Put it in .env or environment.")

    PERSISTENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    persistence = PicklePersistence(filepath=PERSISTENCE_FILE)
    app = Application.builder().token(TOKEN).persistence(persistence).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("voices", voices))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("lang", language_cmd))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:(en|ru)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Starting Telegram TTS bot with default voice %s and default language %s", DEFAULT_VOICE, DEFAULT_LANG)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
