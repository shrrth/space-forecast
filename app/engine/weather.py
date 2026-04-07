from __future__ import annotations

from datetime import datetime

from app.db.models import LocalWeatherSnapshot
from app.db.session import SessionLocal


def latest_local_weather(region_key: str) -> LocalWeatherSnapshot | None:
    db = SessionLocal()
    try:
        return (
            db.query(LocalWeatherSnapshot)
            .filter(LocalWeatherSnapshot.region_key == region_key)
            .order_by(LocalWeatherSnapshot.observed_at.desc())
            .first()
        )
    finally:
        db.close()


def region_key_for_user(lat: float, lon: float) -> str:
    # MVP grouping key: approx 0.5-degree tile
    return f"{round(lat * 2) / 2:.1f}:{round(lon * 2) / 2:.1f}"


def fallback_weather_snapshot(region_key: str) -> LocalWeatherSnapshot:
    return LocalWeatherSnapshot(
        region_key=region_key,
        observed_at=datetime.utcnow(),
        cloud_pct=30.0,
        humidity=55.0,
        temperature_c=14.0,
        wind_mps=2.5,
        seeing_score=3.0,
        raw_payload="{}",
    )
