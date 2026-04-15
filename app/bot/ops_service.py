from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy import func

from app.common.config import get_settings
from app.db.models import MessageJob
from app.db.models import LocalWeatherSnapshot
from app.db.session import SessionLocal
from app.dispatcher.queue import get_all_queue_lengths
from app.ingestor.noaa import get_latest_space_weather
from app.observability.metrics import recent_failure_count


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if token.lstrip("-").isdigit():
            ids.add(int(token))
    return ids


def is_ops_admin(user_id: int) -> bool:
    settings = get_settings()
    admins = _parse_admin_ids(settings.ops_admin_ids)
    if not admins:
        return False
    return user_id in admins


def latest_local_weather_observed_at() -> datetime | None:
    db = SessionLocal()
    try:
        stmt = select(LocalWeatherSnapshot.observed_at).order_by(LocalWeatherSnapshot.observed_at.desc()).limit(1)
        row = db.execute(stmt).first()
        return None if row is None else row[0]
    finally:
        db.close()


def _age_minutes(ts: datetime | None) -> int | None:
    if ts is None:
        return None
    delta = datetime.utcnow() - ts
    return max(0, int(delta.total_seconds() // 60))


def pending_retry_backlog() -> int:
    db = SessionLocal()
    try:
        stmt = (
            select(func.count())
            .select_from(MessageJob)
            .where(MessageJob.status == "pending")
            .where(MessageJob.retry_count > 0)
        )
        row = db.execute(stmt).first()
        return 0 if row is None else int(row[0])
    finally:
        db.close()


def build_ops_status_text() -> str:
    settings = get_settings()
    queues = get_all_queue_lengths()
    noaa = get_latest_space_weather()
    local_wx_at = latest_local_weather_observed_at()
    retry_backlog = pending_retry_backlog()

    jobs_fail_5m = recent_failure_count("jobs", minutes=5)
    api_fail_5m = recent_failure_count("api", minutes=5)
    sender_fail_5m = recent_failure_count("sender", minutes=5)

    noaa_at = noaa.observed_at.isoformat() if noaa else "N/A"
    local_at = local_wx_at.isoformat() if local_wx_at else "N/A"
    noaa_age_min = _age_minutes(noaa.observed_at) if noaa else None
    local_age_min = _age_minutes(local_wx_at)

    queue_warn = any(depth >= settings.alert_queue_threshold for depth in queues.values())
    fail_warn = (
        jobs_fail_5m >= settings.alert_failure_threshold
        or api_fail_5m >= settings.alert_failure_threshold
        or sender_fail_5m >= settings.alert_failure_threshold
    )
    # freshness guardrails for operator visibility
    ingest_warn = (
        noaa_age_min is None
        or local_age_min is None
        or noaa_age_min > 40
        or local_age_min > 80
    )
    overall = "WARN" if (queue_warn or fail_warn or ingest_warn) else "OK"

    return (
        "[Ops Status]\n"
        f"- overall: {overall}\n"
        f"- queue emergency: {queues.get('emergency', 0)}\n"
        f"- queue daily: {queues.get('daily', 0)}\n"
        f"- retry backlog(pending retry_count>0): {retry_backlog}\n"
        f"- queue threshold: {settings.alert_queue_threshold}\n"
        f"- alert channels: telegram={'ON' if bool(settings.alert_chat_id) else 'OFF'}, "
        f"webhook={'ON' if bool(settings.alert_webhook_url) else 'OFF'}\n"
        f"- failures(5m): jobs={jobs_fail_5m}, api={api_fail_5m}, sender={sender_fail_5m}\n"
        f"- failure threshold(5m): {settings.alert_failure_threshold}\n"
        f"- latest ingest: noaa={noaa_at} ({noaa_age_min if noaa_age_min is not None else 'N/A'}m ago), "
        f"local_weather={local_at} ({local_age_min if local_age_min is not None else 'N/A'}m ago)"
    )
