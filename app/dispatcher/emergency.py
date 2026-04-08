from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import MessageJob, SpaceWeatherSnapshot, User, UserAlertState
from app.db.session import SessionLocal
from app.dispatcher.queue import enqueue_job_ids

COOLDOWN_HOURS = 3


def enqueue_emergency_jobs(snapshot: SpaceWeatherSnapshot) -> int:
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=COOLDOWN_HOURS)

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
            if state.last_emergency_alert_at and state.last_emergency_alert_at > cutoff:
                continue

            existing = db.execute(
                select(MessageJob)
                .where(MessageJob.user_id == user.id)
                .where(MessageJob.type == "emergency")
                .where(MessageJob.status == "pending")
            ).scalars().first()
            if existing:
                continue

            job = MessageJob(
                user_id=user.id,
                type="emergency",
                status="pending",
                scheduled_at=now,
            )
            db.add(job)
            db.flush()
            job_ids.append(int(job.id))
            state.last_emergency_alert_at = now
            created += 1

        db.commit()
        enqueue_job_ids(job_type="emergency", job_ids=job_ids)
        return created
    finally:
        db.close()
