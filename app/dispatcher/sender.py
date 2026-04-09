from __future__ import annotations

from datetime import datetime, timedelta

from telegram.ext import Application

from app.common.config import get_settings
from app.db.models import MessageJob, SpaceWeatherSnapshot, User
from app.db.session import SessionLocal
from app.dispatcher.queue import pop_job_ids
from app.dispatcher.throttled_sender import throttled_send
from app.engine.messages import build_daily_message, build_emergency_message
from app.engine.weather import fallback_weather_snapshot, latest_local_weather, region_key_for_user
from app.observability.metrics import incr_counter, record_failure


def _latest_snapshot() -> SpaceWeatherSnapshot | None:
    db = SessionLocal()
    try:
        return (
            db.query(SpaceWeatherSnapshot)
            .order_by(SpaceWeatherSnapshot.observed_at.desc())
            .first()
        )
    finally:
        db.close()


def _get_job(job_id: int, expected_type: str) -> MessageJob | None:
    db = SessionLocal()
    try:
        job = db.get(MessageJob, job_id)
        if not job:
            return None
        if job.type != expected_type or job.status != "pending":
            return None
        return job
    finally:
        db.close()


def _get_user(user_id: int) -> User | None:
    db = SessionLocal()
    try:
        return db.get(User, user_id)
    finally:
        db.close()


def _mark_sent(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(MessageJob, job_id)
        if not job:
            return
        job.status = "sent"
        job.sent_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def _retry_backoff_sec(retry_count: int) -> int:
    settings = get_settings()
    base = max(settings.sender_retry_base_sec, 1)
    max_sec = max(settings.sender_retry_max_sec, base)
    # exponential backoff: base, 2*base, 4*base, ...
    backoff = base * (2 ** max(retry_count - 1, 0))
    return min(backoff, max_sec)


def _reschedule_or_fail(job_id: int, error: str) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        job = db.get(MessageJob, job_id)
        if not job:
            return

        next_retry_count = int(job.retry_count or 0) + 1
        if next_retry_count <= settings.sender_max_retries:
            delay_sec = _retry_backoff_sec(next_retry_count)
            job.retry_count = next_retry_count
            job.status = "pending"
            job.scheduled_at = datetime.utcnow() + timedelta(seconds=delay_sec)
            job.error = f"retry#{next_retry_count}: {error[:900]}"
            db.commit()
            incr_counter("sender:retry_scheduled")
            record_failure("sender", f"retry#{next_retry_count}:{error}")
            return

        job.retry_count = next_retry_count
        job.status = "failed"
        job.error = error[:1000]
        db.commit()
        incr_counter("sender:retry_exhausted")
        record_failure("sender", f"exhausted:{error}")
    finally:
        db.close()


def _mark_failed_permanent(job_id: int, error: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(MessageJob, job_id)
        if not job:
            return
        job.status = "failed"
        job.error = error[:1000]
        db.commit()
        incr_counter("sender:failed_permanent")
        record_failure("sender", error)
    finally:
        db.close()


async def send_pending_emergency(application: Application) -> int:
    snapshot = _latest_snapshot()
    if snapshot is None:
        return 0

    job_ids = pop_job_ids(job_type="emergency", limit=200)
    sent = 0

    for job_id in job_ids:
        job = _get_job(job_id=job_id, expected_type="emergency")
        if job is None:
            continue

        user = _get_user(job.user_id)
        if user is None:
            _mark_failed_permanent(job_id, "missing user")
            continue

        text = build_emergency_message(snapshot, language_code=user.language_code)
        try:
            await throttled_send(
                application.bot.send_message,
                chat_id=user.telegram_user_id,
                text=text,
            )
            _mark_sent(job_id)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            _reschedule_or_fail(job_id, str(exc))

    return sent


async def send_pending_daily(application: Application) -> int:
    snapshot = _latest_snapshot()
    job_ids = pop_job_ids(job_type="daily", limit=200)
    sent = 0

    for job_id in job_ids:
        job = _get_job(job_id=job_id, expected_type="daily")
        if job is None:
            continue

        user = _get_user(job.user_id)
        if user is None:
            _mark_failed_permanent(job_id, "missing user")
            continue

        region_key = region_key_for_user(user.lat, user.lon)
        local_weather = latest_local_weather(region_key) or fallback_weather_snapshot(region_key)
        text = build_daily_message(user=user, space_weather=snapshot, local_weather=local_weather)

        try:
            await throttled_send(
                application.bot.send_message,
                chat_id=user.telegram_user_id,
                text=text,
            )
            _mark_sent(job_id)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            _reschedule_or_fail(job_id, str(exc))

    return sent
