from __future__ import annotations

from datetime import datetime

from app.db.models import MessageJob, User
from app.dispatcher.refill import refill_pending_jobs_to_redis


def test_refill_moves_pending_ids_to_queue(test_db, monkeypatch) -> None:
    collected: list[int] = []

    def fake_enqueue_job_ids(job_type: str, job_ids: list[int]) -> None:
        assert job_type == "emergency"
        collected.extend(job_ids)

    monkeypatch.setattr("app.dispatcher.refill.enqueue_job_ids", fake_enqueue_job_ids)

    session = test_db()
    try:
        user = User(
            telegram_user_id=999,
            timezone="UTC",
            lat=0.0,
            lon=0.0,
            location_label="Nowhere",
            alert_enabled=True,
        )
        session.add(user)
        session.flush()

        session.add(
            MessageJob(
                user_id=user.id,
                type="emergency",
                status="pending",
                scheduled_at=datetime.utcnow(),
            )
        )
        session.commit()
    finally:
        session.close()

    moved = refill_pending_jobs_to_redis(job_type="emergency", limit=100)

    assert moved == 1
    assert len(collected) == 1
