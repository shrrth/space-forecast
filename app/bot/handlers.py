from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from app.common.config import get_settings
from app.bot.ops_service import build_ops_status_text, is_ops_admin
from app.bot.user_service import get_user, resolve_location, update_user_profile, upsert_user


_EQUIPMENT_LEVELS = {"visual", "basic", "advanced"}
_PURPOSES = {"deep_sky", "planetary", "widefield"}
_LANG_CODES = {"ko", "en"}


def _normalize_equipment(raw: str | None) -> str | None:
    if not raw:
        return None
    v = raw.strip().lower().replace("-", "_")
    if v in _EQUIPMENT_LEVELS:
        return v
    return None


def _normalize_purpose(raw: str | None) -> str | None:
    if not raw:
        return None
    v = raw.strip().lower().replace("-", "_")
    if v in _PURPOSES:
        return v
    return None


def _normalize_lang(raw: str | None) -> str | None:
    if not raw:
        return None
    v = raw.strip().lower().replace("-", "_")
    if len(v) > 2:
        v = v[:2]
    if v in _LANG_CODES:
        return v
    return None


def _location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Send Location", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return

    settings = get_settings()
    user = get_user(update.effective_user.id)
    if user is None:
        lang = _normalize_lang(update.effective_user.language_code) or "ko"
        default_location = resolve_location(
            settings.default_lat,
            settings.default_lon,
            settings.default_location_label,
        )
        upsert_user(update.effective_user.id, default_location, language_code=lang)

    await update.message.reply_text(
        "SpaceForecast에 오신 것을 환영합니다.\n"
        "정확한 개인화 리포트를 위해 위치를 공유해 주세요.\n"
        "명령어: /setlocation /setequipment /setpurpose /setlang /status /help",
        reply_markup=_location_keyboard(),
    )


async def set_location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "아래 버튼으로 위치를 보내주세요.",
        reply_markup=_location_keyboard(),
    )


async def location_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message or not update.message.location:
        return

    lat = update.message.location.latitude
    lon = update.message.location.longitude
    location = resolve_location(lat, lon)
    user = upsert_user(update.effective_user.id, location)

    await update.message.reply_text(
        f"위치가 저장되었습니다.\\n위치: {user.location_label}\\n타임존: {user.timezone}",
        reply_markup=ReplyKeyboardRemove(),
    )


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return

    user = get_user(update.effective_user.id)
    if user is None:
        await update.message.reply_text("저장된 설정이 없습니다. /start를 먼저 실행해 주세요.")
        return

    await update.message.reply_text(
        "현재 설정\\n"
        f"- 위치: {user.location_label} ({user.lat:.3f}, {user.lon:.3f})\\n"
        f"- 타임존: {user.timezone}\\n"
        f"- 알림: {'ON' if user.alert_enabled else 'OFF'}\\n"
        f"- 언어: {user.language_code}\\n"
        f"- 장비: {user.equipment_level}\\n"
        f"- 관측 목적: {user.observation_purpose}"
    )


async def set_lang_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    value = _normalize_lang(" ".join(context.args)) if context.args else None
    if value is None:
        await update.message.reply_text(
            "사용법: /setlang <ko|en>"
        )
        return

    user = update_user_profile(update.effective_user.id, language_code=value)
    if user is None:
        await update.message.reply_text("저장된 설정이 없습니다. /start를 먼저 실행해 주세요.")
        return
    await update.message.reply_text(f"언어가 '{user.language_code}'로 저장되었습니다.")


async def set_equipment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    value = _normalize_equipment(" ".join(context.args)) if context.args else None
    if value is None:
        await update.message.reply_text(
            "사용법: /setequipment <visual|basic|advanced>"
        )
        return

    user = update_user_profile(update.effective_user.id, equipment_level=value)
    if user is None:
        await update.message.reply_text("저장된 설정이 없습니다. /start를 먼저 실행해 주세요.")
        return
    await update.message.reply_text(f"장비 프로필이 '{user.equipment_level}'로 저장되었습니다.")


async def set_purpose_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    value = _normalize_purpose(" ".join(context.args)) if context.args else None
    if value is None:
        await update.message.reply_text(
            "사용법: /setpurpose <deep_sky|planetary|widefield>"
        )
        return

    user = update_user_profile(update.effective_user.id, observation_purpose=value)
    if user is None:
        await update.message.reply_text("저장된 설정이 없습니다. /start를 먼저 실행해 주세요.")
        return
    await update.message.reply_text(f"관측 목적이 '{user.observation_purpose}'로 저장되었습니다.")


async def opsstatus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return

    if not is_ops_admin(update.effective_user.id):
        await update.message.reply_text("권한이 없습니다.")
        return

    await update.message.reply_text(build_ops_status_text())


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "/start - 초기화\\n"
        "/setlocation - 위치 재설정\\n"
        "/setequipment - 장비 설정(visual/basic/advanced)\\n"
        "/setpurpose - 관측 목적 설정(deep_sky/planetary/widefield)\\n"
        "/setlang - 언어 설정(ko/en)\\n"
        "/status - 현재 설정 확인\\n"
        "/opsstatus - 운영 상태 확인(관리자)\\n"
        "/help - 도움말"
    )


def get_handlers() -> list:
    return [
        CommandHandler("start", start_handler),
        CommandHandler("setlocation", set_location_handler),
        CommandHandler("setequipment", set_equipment_handler),
        CommandHandler("setpurpose", set_purpose_handler),
        CommandHandler("setlang", set_lang_handler),
        CommandHandler("status", status_handler),
        CommandHandler("opsstatus", opsstatus_handler),
        CommandHandler("help", help_handler),
        MessageHandler(filters.LOCATION, location_message_handler),
    ]
