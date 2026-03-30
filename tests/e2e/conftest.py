from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.session as db_session
from app.db.base import Base
import app.db.models  # noqa: F401
import app.dispatcher.emergency as emergency_module
import app.dispatcher.refill as refill_module
import app.dispatcher.sender as sender_module
import app.engine.daily as daily_module
import app.engine.weather as weather_module


@pytest.fixture()
def test_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "SessionLocal", Session)
    monkeypatch.setattr(emergency_module, "SessionLocal", Session)
    monkeypatch.setattr(refill_module, "SessionLocal", Session)
    monkeypatch.setattr(sender_module, "SessionLocal", Session)
    monkeypatch.setattr(daily_module, "SessionLocal", Session)
    monkeypatch.setattr(weather_module, "SessionLocal", Session)
    monkeypatch.setattr(sender_module, "incr_counter", lambda *args, **kwargs: None)
    monkeypatch.setattr(sender_module, "record_failure", lambda *args, **kwargs: None)

    yield Session

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def in_memory_queue(monkeypatch: pytest.MonkeyPatch):
    queues: dict[str, list[int]] = {"emergency": [], "daily": []}

    def fake_enqueue_job_ids(job_type: str, job_ids: list[int]) -> None:
        queues[job_type].extend(job_ids)

    def fake_pop_job_ids(job_type: str, limit: int = 200) -> list[int]:
        vals = queues[job_type][:limit]
        queues[job_type] = queues[job_type][limit:]
        return vals

    monkeypatch.setattr(emergency_module, "enqueue_job_ids", fake_enqueue_job_ids)
    monkeypatch.setattr(daily_module, "enqueue_job_ids", fake_enqueue_job_ids)
    monkeypatch.setattr(sender_module, "pop_job_ids", fake_pop_job_ids)
    return queues
