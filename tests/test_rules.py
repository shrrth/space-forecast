from datetime import datetime

from app.db.models import SpaceWeatherSnapshot
from app.engine.rules import is_emergency


def make_snapshot(kp: float, xray: str | None) -> SpaceWeatherSnapshot:
    return SpaceWeatherSnapshot(
        observed_at=datetime.utcnow(),
        kp_index=kp,
        xray_class=xray,
        raw_payload="{}",
    )


def test_emergency_by_kp() -> None:
    assert is_emergency(make_snapshot(6.0, None)) is True


def test_emergency_by_xray() -> None:
    assert is_emergency(make_snapshot(3.0, "X")) is True


def test_non_emergency() -> None:
    assert is_emergency(make_snapshot(4.0, "M")) is False
