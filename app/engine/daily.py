from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.models import MessageJob, User, UserAlertState
from app.db.session import SessionLocal
from app.dispatcher.queue import enqueue_job_ids


def enqueue_daily_jobs(now_utc: datetime | None = None) -> int:
    now = now_utc or datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        rows = db.execute(
            select(User, UserAlertState)
            .join(UserAlertState, UserAlertState.user_id == User.id)
            .where(User.alert_enabled.is_(True))
        ).all()

        created = 0
        job_ids: list[int] = []
        for user, state in rows:
            user_tz = ZoneInfo(user.timezone)
            local_now = now.astimezone(user_tz)
            if local_now.hour != int(state.daily_report_hour_local):
                continue

            day_start_local = datetime.combine(local_now.date(), datetime.min.time(), tzinfo=user_tz)
            day_end_local = day_start_local.replace(hour=23, minute=59, second=59)
            day_start_utc = day_start_local.astimezone(timezone.utc).replace(tzinfo=None)
            day_end_utc = day_end_local.astimezone(timezone.utc).replace(tzinfo=None)

            existing = db.execute(
                select(MessageJob)
                .where(MessageJob.user_id == user.id)
                .where(MessageJob.type == "daily")
                .where(MessageJob.status.in_(["pending", "sent"]))
                .where(MessageJob.scheduled_at >= day_start_utc)
                .where(MessageJob.scheduled_at <= day_end_utc)
            ).scalars().first()
            if existing:
                continue

            job = MessageJob(
                user_id=user.id,
                type="daily",
                status="pending",
                scheduled_at=now.replace(tzinfo=None),
            )
            db.add(job)
            db.flush()
            job_ids.append(int(job.id))
            created += 1

        db.commit()
        enqueue_job_ids(job_type="daily", job_ids=job_ids)
        return created
    finally:
        db.close()
