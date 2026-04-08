from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.db.models import MessageJob
from app.db.session import SessionLocal
from app.dispatcher.queue import enqueue_job_ids


def refill_pending_jobs_to_redis(job_type: str, limit: int = 500) -> int:
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        rows = db.execute(
            select(MessageJob.id)
            .where(MessageJob.type == job_type)
            .where(MessageJob.status == "pending")
            .where(MessageJob.scheduled_at <= now)
            .order_by(MessageJob.scheduled_at.asc())
            .limit(limit)
        ).all()
        job_ids = [int(r[0]) for r in rows]
        enqueue_job_ids(job_type=job_type, job_ids=job_ids)
        return len(job_ids)
    finally:
        db.close()
