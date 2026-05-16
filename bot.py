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
import asyncio
import contextlib
from datetime import UTC, datetime
from pathlib import Path

import edge_tts
from dotenv import load_dotenv
from telegram import (
    BotCommand,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
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
TTS_TIMEOUT_SECONDS = int(os.getenv("TTS_TIMEOUT_SECONDS", "120"))
SEND_TIMEOUT_SECONDS = int(os.getenv("SEND_TIMEOUT_SECONDS", "120"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", tempfile.gettempdir())).expanduser()
PERSISTENCE_FILE = Path(os.getenv("PERSISTENCE_FILE", "data/bot-state.pickle")).expanduser()
ADMIN_IDS = {int(part) for part in re.split(r"[,\s]+", os.getenv("ADMIN_IDS", "").strip()) if part.isdigit()}
DEFAULT_LANG = "en"
SUPPORTED_LANGS = {"en", "ru"}
LANG_BUTTON_TEXTS = {"🌐 Language", "🌐 Язык", "Language", "Язык"}
ADMIN_BUTTON_TEXTS = {"👑 Admin", "👑 Админ", "Admin", "Админ"}

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
        "processing": "⏳ Generating audio… This can take a bit for long text.",
        "sending_audio": "📤 Audio is ready, uploading…",
        "tts_failed": "Could not generate audio: {error}",
        "main_menu_button": "🌐 Language",
        "admin_menu_button": "👑 Admin",
        "admin_only": "Admin-only command.",
        "admin_menu": (
            "👑 Admin menu\n\n"
            "/stats — bot statistics\n"
            "/users — recent users\n"
            "/admin — this menu"
        ),
        "stats": (
            "📊 Bot statistics\n"
            "Users: {users}\n"
            "Requests: {requests}\n"
            "Successful TTS: {tts_success}\n"
            "Failed TTS: {tts_failed}\n"
            "Admin IDs: {admin_ids}"
        ),
        "users_empty": "No users recorded yet.",
        "users_header": "👥 Users ({count} total, showing {shown}):\n",
        "new_user_notice": (
            "🆕 New TTS bot user\n"
            "ID: {id}\n"
            "Name: {name}\n"
            "Username: {username}\n"
            "Language: {language_code}\n"
            "Source: {source}"
        ),
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
        "processing": "⏳ Генерирую аудио… Для длинного текста это может занять немного времени.",
        "sending_audio": "📤 Аудио готово, загружаю…",
        "tts_failed": "Не смог сгенерировать аудио: {error}",
        "main_menu_button": "🌐 Язык",
        "admin_menu_button": "👑 Админ",
        "admin_only": "Команда только для админа.",
        "admin_menu": (
            "👑 Админ-меню\n\n"
            "/stats — статистика бота\n"
            "/users — последние пользователи\n"
            "/admin — это меню"
        ),
        "stats": (
            "📊 Статистика бота\n"
            "Пользователей: {users}\n"
            "Запросов: {requests}\n"
            "Успешных TTS: {tts_success}\n"
            "Ошибок TTS: {tts_failed}\n"
            "Admin IDs: {admin_ids}"
        ),
        "users_empty": "Пользователей пока нет.",
        "users_header": "👥 Пользователи ({count} всего, показано {shown}):\n",
        "new_user_notice": (
            "🆕 Новый пользователь TTS bot\n"
            "ID: {id}\n"
            "Имя: {name}\n"
            "Username: {username}\n"
            "Язык: {language_code}\n"
            "Источник: {source}"
        ),
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


def is_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id in ADMIN_IDS)


def main_menu(context: ContextTypes.DEFAULT_TYPE, user_id: int | None = None) -> ReplyKeyboardMarkup:
    rows = [[TEXTS[get_lang(context)]["main_menu_button"]]]
    if is_admin(user_id):
        rows.append([TEXTS[get_lang(context)]["admin_menu_button"]])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Type text for TTS",
    )


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("English", callback_data="lang:en"), InlineKeyboardButton("Русский", callback_data="lang:ru")]]
    )


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def display_user(user: object) -> str:
    if not user:
        return "unknown"
    name_parts = [getattr(user, "first_name", None), getattr(user, "last_name", None)]
    name = " ".join(part for part in name_parts if part).strip()
    return name or getattr(user, "username", None) or str(getattr(user, "id", "unknown"))


def get_stats(context: ContextTypes.DEFAULT_TYPE) -> dict[str, int]:
    stats = context.bot_data.setdefault("stats", {})
    for key in ("requests", "tts_success", "tts_failed"):
        stats.setdefault(key, 0)
    return stats


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, skip_user_id: int | None = None) -> None:
    for admin_id in ADMIN_IDS:
        if admin_id == skip_user_id:
            continue
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            log.exception("Could not notify admin_id=%s", admin_id)


async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE, source: str) -> None:
    user = update.effective_user
    if not user or user.is_bot:
        return

    users = context.bot_data.setdefault("users", {})
    user_id = str(user.id)
    now = utc_now()
    is_new = user_id not in users
    record = users.setdefault(user_id, {"id": user.id, "first_seen": now})
    record.update(
        {
            "id": user.id,
            "username": user.username or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "language_code": user.language_code or "",
            "is_admin": is_admin(user.id),
            "last_seen": now,
            "last_source": source,
        }
    )
    if update.effective_chat:
        chats = set(record.get("chat_ids", []))
        chats.add(update.effective_chat.id)
        record["chat_ids"] = sorted(chats)

    if is_new:
        notice = TEXTS["ru"]["new_user_notice"].format(
            id=user.id,
            name=display_user(user),
            username=f"@{user.username}" if user.username else "—",
            language_code=user.language_code or "—",
            source=source,
        )
        await notify_admins(context, notice, skip_user_id=user.id if is_admin(user.id) else None)


def require_admin(update: Update) -> bool:
    return is_admin(update.effective_user.id if update.effective_user else None)


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


async def keep_upload_action(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Keep Telegram's progress indicator alive during slow TTS generation/upload."""
    while True:
        with contextlib.suppress(Exception):
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VOICE)
        await asyncio.sleep(4)


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
    await register_user(update, context, "start")
    user_id = update.effective_user.id if update.effective_user else None
    await update.message.reply_text(t(context, "start"), reply_markup=main_menu(context, user_id))
    await update.message.reply_text(t(context, "language_prompt"), reply_markup=language_keyboard())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await register_user(update, context, "help")
    user_id = update.effective_user.id if update.effective_user else None
    await update.message.reply_text(
        t(context, "help", max_chars=MAX_CHARS, default_voice=DEFAULT_VOICE),
        reply_markup=main_menu(context, user_id),
    )


async def voices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await register_user(update, context, "voices")
    user_id = update.effective_user.id if update.effective_user else None
    await update.message.reply_text(t(context, "voices"), reply_markup=main_menu(context, user_id))


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_update(update, "language")
    await register_user(update, context, "language")
    await update.message.reply_text(t(context, "language_prompt"), reply_markup=language_keyboard())


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_update(update, "language_callback")
    await register_user(update, context, "language_callback")
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":", 1)[1]
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    context.user_data["lang"] = lang
    user_id = update.effective_user.id if update.effective_user else None
    await query.edit_message_text(TEXTS[lang]["language_set"])
    await query.message.reply_text(TEXTS[lang]["start"], reply_markup=main_menu(context, user_id))


async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await register_user(update, context, "voice")
    user_id = update.effective_user.id if update.effective_user else None
    if not context.args:
        current = context.user_data.get("voice", DEFAULT_VOICE)
        await update.message.reply_text(t(context, "current_voice", voice=current), reply_markup=main_menu(context, user_id))
        return
    voice = context.args[0].strip()
    if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural", voice):
        await update.message.reply_text(t(context, "invalid_voice"), reply_markup=main_menu(context, user_id))
        return
    context.user_data["voice"] = voice
    await update.message.reply_text(t(context, "voice_set", voice=voice), reply_markup=main_menu(context, user_id))


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await register_user(update, context, "admin")
    if not require_admin(update):
        await update.message.reply_text(t(context, "admin_only"))
        return
    await update.message.reply_text(t(context, "admin_menu"), reply_markup=main_menu(context, update.effective_user.id))


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await register_user(update, context, "stats")
    if not require_admin(update):
        await update.message.reply_text(t(context, "admin_only"))
        return
    stats = get_stats(context)
    users = context.bot_data.setdefault("users", {})
    await update.message.reply_text(
        t(
            context,
            "stats",
            users=len(users),
            requests=stats["requests"],
            tts_success=stats["tts_success"],
            tts_failed=stats["tts_failed"],
            admin_ids=", ".join(str(admin_id) for admin_id in sorted(ADMIN_IDS)) or "—",
        ),
        reply_markup=main_menu(context, update.effective_user.id),
    )


async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await register_user(update, context, "users")
    if not require_admin(update):
        await update.message.reply_text(t(context, "admin_only"))
        return
    users = list(context.bot_data.setdefault("users", {}).values())
    if not users:
        await update.message.reply_text(t(context, "users_empty"), reply_markup=main_menu(context, update.effective_user.id))
        return
    users.sort(key=lambda item: item.get("last_seen", ""), reverse=True)
    shown = users[:20]
    lines = [t(context, "users_header", count=len(users), shown=len(shown))]
    for record in shown:
        username = f"@{record['username']}" if record.get("username") else "—"
        full_name = " ".join(part for part in [record.get("first_name"), record.get("last_name")] if part).strip() or "—"
        marker = " 👑" if record.get("is_admin") else ""
        lines.append(
            f"• {full_name}{marker}\n"
            f"  ID: {record.get('id')} | {username}\n"
            f"  Lang: {record.get('language_code') or '—'} | Last: {record.get('last_seen') or '—'}\n"
            f"  Source: {record.get('last_source') or '—'}"
        )
    await update.message.reply_text("\n".join(lines), reply_markup=main_menu(context, update.effective_user.id))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    log_update(update, "text")
    await register_user(update, context, "text")
    msg = update.message
    if not msg or not msg.text:
        return

    user_id = update.effective_user.id if update.effective_user else None
    text = clean_text(msg.text)
    if text in LANG_BUTTON_TEXTS:
        await language_cmd(update, context)
        return
    if text in ADMIN_BUTTON_TEXTS:
        await admin_cmd(update, context)
        return
    if not text:
        await msg.reply_text(t(context, "empty_text"), reply_markup=main_menu(context, user_id))
        return
    if len(text) > MAX_CHARS:
        await msg.reply_text(
            t(context, "too_long", length=len(text), max_chars=MAX_CHARS),
            reply_markup=main_menu(context, user_id),
        )
        return

    stats = get_stats(context)
    stats["requests"] += 1
    voice = context.user_data.get("voice", DEFAULT_VOICE)
    out: Path | None = None
    status_message = None
    action_task = None
    try:
        status_message = await msg.reply_text(t(context, "processing"), reply_markup=main_menu(context, user_id))
        action_task = asyncio.create_task(keep_upload_action(context, msg.chat_id))
        log.info("Generating TTS: chat_id=%s user_id=%s chars=%s voice=%s", msg.chat_id, user_id, len(text), voice)
        out = await asyncio.wait_for(
            synthesize_mp3(text, voice=voice),
            timeout=TTS_TIMEOUT_SECONDS,
        )
        log.info("TTS generated: chat_id=%s user_id=%s bytes=%s", msg.chat_id, user_id, out.stat().st_size)
        stats["tts_success"] += 1
        with contextlib.suppress(Exception):
            await status_message.edit_text(t(context, "sending_audio"))
        title = text[:45].replace("\n", " ")
        if len(text) > 45:
            title += "…"
        with out.open("rb") as audio_file:
            await asyncio.wait_for(
                msg.reply_audio(
                    audio=audio_file,
                    title=title,
                    performer="TTS Bot",
                    caption=t(context, "caption_voice", voice=voice),
                    reply_markup=main_menu(context, user_id),
                ),
                timeout=SEND_TIMEOUT_SECONDS,
            )
        if status_message:
            with contextlib.suppress(Exception):
                await status_message.delete()
        log.info("TTS audio sent: chat_id=%s user_id=%s", msg.chat_id, user_id)
    except Exception as exc:  # noqa: BLE001 - user-facing bot should not crash on one bad request
        stats["tts_failed"] += 1
        log.exception("TTS failed")
        error_text = t(context, "tts_failed", error=exc)
        if status_message:
            with contextlib.suppress(Exception):
                await status_message.edit_text(error_text)
        else:
            await msg.reply_text(error_text, reply_markup=main_menu(context, user_id))
    finally:
        if action_task:
            action_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await action_task
        if out:
            try:
                out.unlink(missing_ok=True)
            except Exception:
                log.warning("Could not remove temp file %s", out)


async def setup_bot_commands(app: Application) -> None:
    default_commands = [
        BotCommand("start", "Start / language"),
        BotCommand("help", "Help"),
        BotCommand("voices", "Voice examples"),
        BotCommand("voice", "Show or set voice"),
        BotCommand("language", "Choose language"),
    ]
    admin_commands = [
        *default_commands,
        BotCommand("admin", "Admin menu"),
        BotCommand("stats", "Bot statistics"),
        BotCommand("users", "Recent users"),
    ]
    await app.bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            log.exception("Could not set admin commands for admin_id=%s", admin_id)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN. Put it in .env or environment.")

    PERSISTENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    persistence = PicklePersistence(filepath=PERSISTENCE_FILE)
    app = Application.builder().token(TOKEN).persistence(persistence).post_init(setup_bot_commands).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("voices", voices))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("lang", language_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:(en|ru)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Starting Telegram TTS bot with default voice %s and default language %s", DEFAULT_VOICE, DEFAULT_LANG)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
