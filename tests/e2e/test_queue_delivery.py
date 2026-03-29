from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import SpaceWeatherSnapshot, User, UserAlertState
from app.dispatcher.emergency import enqueue_emergency_jobs
from app.dispatcher.sender import send_pending_daily, send_pending_emergency
from app.engine.daily import enqueue_daily_jobs


class _FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


class _FakeApp:
    def __init__(self) -> None:
        self.bot = _FakeBot()


def test_e2e_emergency_and_daily_queue_flow(test_db, in_memory_queue) -> None:
    session = test_db()
    user_id: int
    try:
        user = User(
            telegram_user_id=12345,
            timezone="UTC",
            lat=37.5,
            lon=127.0,
            location_label="Seoul",
            alert_enabled=True,
        )
        session.add(user)
        session.flush()
        user_id = int(user.id)

        session.add(UserAlertState(user_id=user_id, daily_report_hour_local=18))
        session.add(
            SpaceWeatherSnapshot(
                observed_at=datetime.utcnow(),
                kp_index=6.2,
                xray_class="M",
                raw_payload="{}",
            )
        )
        session.commit()

        snapshot = session.query(SpaceWeatherSnapshot).order_by(SpaceWeatherSnapshot.id.desc()).first()
        assert snapshot is not None
    finally:
        session.close()

    created_emergency = enqueue_emergency_jobs(snapshot)
    created_daily = enqueue_daily_jobs(now_utc=datetime(2026, 2, 20, 18, 0, 0, tzinfo=timezone.utc))

    assert created_emergency == 1
    assert created_daily == 1
    assert in_memory_queue["emergency"]
    assert in_memory_queue["daily"]

    app = _FakeApp()

    import asyncio

    emergency_sent = asyncio.run(send_pending_emergency(app))
    daily_sent = asyncio.run(send_pending_daily(app))

    assert emergency_sent == 1
    assert daily_sent == 1
    assert len(app.bot.messages) == 2
