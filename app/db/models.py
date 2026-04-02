from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    location_label: Mapped[str] = mapped_column(String(120), nullable=False)
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    language_code: Mapped[str] = mapped_column(String(8), default="ko")
    equipment_level: Mapped[str] = mapped_column(String(32), default="basic")
    observation_purpose: Mapped[str] = mapped_column(String(32), default="deep_sky")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserAlertState(Base):
    __tablename__ = "user_alert_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    last_emergency_alert_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    daily_report_hour_local: Mapped[int] = mapped_column(Integer, default=18)


class MessageJob(Base):
    __tablename__ = "message_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "type", "scheduled_at", name="uq_user_type_scheduled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)


class SpaceWeatherSnapshot(Base):
    __tablename__ = "space_weather_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    kp_index: Mapped[float] = mapped_column(Float)
    xray_class: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_payload: Mapped[str] = mapped_column(Text)


class LocalWeatherSnapshot(Base):
    __tablename__ = "local_weather_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_key: Mapped[str] = mapped_column(String(64), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    cloud_pct: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    temperature_c: Mapped[float] = mapped_column(Float, default=15.0)
    wind_mps: Mapped[float] = mapped_column(Float, default=2.0)
    precip_prob_pct: Mapped[float] = mapped_column(Float, default=0.0)
    precip_mm: Mapped[float] = mapped_column(Float, default=0.0)
    seeing_score: Mapped[float] = mapped_column(Float)
    raw_payload: Mapped[str] = mapped_column(Text)
