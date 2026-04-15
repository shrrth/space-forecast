from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from timezonefinder import TimezoneFinder

from app.common.config import get_settings
from app.db.models import User, UserAlertState
from app.db.session import SessionLocal


@dataclass
class LocationData:
    lat: float
    lon: float
    timezone: str
    location_label: str


_tf = TimezoneFinder()


def resolve_location(lat: float, lon: float, label: Optional[str] = None) -> LocationData:
    settings = get_settings()
    tz = _tf.timezone_at(lat=lat, lng=lon) or settings.default_timezone
    return LocationData(
        lat=lat,
        lon=lon,
        timezone=tz,
        location_label=label or f"{lat:.3f},{lon:.3f}",
    )


def upsert_user(telegram_user_id: int, location: LocationData, language_code: str | None = None) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_user_id == telegram_user_id).one_or_none()
        if user is None:
            user = User(
                telegram_user_id=telegram_user_id,
                timezone=location.timezone,
                lat=location.lat,
                lon=location.lon,
                location_label=location.location_label,
                alert_enabled=True,
                language_code=(language_code or "ko"),
                equipment_level="basic",
                observation_purpose="deep_sky",
            )
            db.add(user)
            db.flush()
            db.add(UserAlertState(user_id=user.id, daily_report_hour_local=18))
        else:
            user.timezone = location.timezone
            user.lat = location.lat
            user.lon = location.lon
            user.location_label = location.location_label
            if language_code:
                user.language_code = language_code

        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def get_user(telegram_user_id: int) -> Optional[User]:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.telegram_user_id == telegram_user_id).one_or_none()
    finally:
        db.close()


def update_user_profile(
    telegram_user_id: int,
    language_code: str | None = None,
    equipment_level: str | None = None,
    observation_purpose: str | None = None,
) -> Optional[User]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_user_id == telegram_user_id).one_or_none()
        if user is None:
            return None

        if language_code is not None:
            user.language_code = language_code
        if equipment_level is not None:
            user.equipment_level = equipment_level
        if observation_purpose is not None:
            user.observation_purpose = observation_purpose

        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()
