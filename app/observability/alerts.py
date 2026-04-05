from __future__ import annotations

import logging
import time
from typing import Iterable

import httpx
import redis
from telegram.ext import Application

from app.common.config import get_settings
from app.dispatcher.queue import get_all_queue_lengths
from app.observability.metrics import recent_failure_count
from app.observability.sanitize import sanitize_error_message

logger = logging.getLogger(__name__)
_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def _webhook_payload(message: str) -> dict[str, str]:
    # Slack incoming webhook and generic webhook endpoint both accept a text field.
    return {"text": message}


async def _send_telegram_alert(application: Application, message: str) -> None:
    settings = get_settings()
    if not settings.alert_chat_id:
        return
    await application.bot.send_message(chat_id=settings.alert_chat_id, text=message)


async def _send_webhook_alert(message: str) -> None:
    settings = get_settings()
    if not settings.alert_webhook_url:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(settings.alert_webhook_url, json=_webhook_payload(message))
        resp.raise_for_status()


async def _send_alert(application: Application, message: str) -> None:
    errors: list[str] = []

    try:
        await _send_telegram_alert(application, message)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"telegram:{sanitize_error_message(str(exc), limit=300)}")

    try:
        await _send_webhook_alert(message)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"webhook:{sanitize_error_message(str(exc), limit=300)}")

    if errors:
        logger.warning("alert dispatch partially failed: %s", " | ".join(errors))


def _cooldown_key(alert_key: str) -> str:
    return f"alert:cooldown:{alert_key}"


def _should_alert(alert_key: str, cooldown_sec: int) -> bool:
    client = _redis()
    key = _cooldown_key(alert_key)
    last = client.get(key)
    now = int(time.time())
    if last and now - int(last) < cooldown_sec:
        return False
    client.setex(key, cooldown_sec, str(now))
    return True


async def maybe_alert(application: Application, alert_key: str, message: str) -> None:
    settings = get_settings()
    if _should_alert(alert_key, cooldown_sec=settings.alert_cooldown_sec):
        await _send_alert(application, message)


async def check_health_and_alert(application: Application) -> None:
    settings = get_settings()

    queue_lengths = get_all_queue_lengths()
    overloaded = [
        f"{name}={depth}"
        for name, depth in queue_lengths.items()
        if depth >= settings.alert_queue_threshold
    ]
    if overloaded:
        await maybe_alert(
            application,
            alert_key="queue_overload",
            message=(
                "[운영 경보] 큐 적체 임계치 초과\n"
                f"- 기준: {settings.alert_queue_threshold}\n"
                f"- 현재: {', '.join(overloaded)}"
            ),
        )

    job_failures = recent_failure_count("jobs", minutes=5)
    api_failures = recent_failure_count("api", minutes=5)
    sender_failures = recent_failure_count("sender", minutes=5)

    failures: Iterable[tuple[str, int]] = (
        ("jobs", job_failures),
        ("api", api_failures),
        ("sender", sender_failures),
    )
    for name, count in failures:
        if count >= settings.alert_failure_threshold:
            await maybe_alert(
                application,
                alert_key=f"failure_spike:{name}",
                message=(
                    "[운영 경보] 최근 5분 실패 급증\n"
                    f"- 대상: {name}\n"
                    f"- 실패 수: {count}\n"
                    f"- 임계치: {settings.alert_failure_threshold}"
                ),
            )
