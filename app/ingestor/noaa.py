from __future__ import annotations

import json
from datetime import datetime
from time import perf_counter

import httpx
from sqlalchemy import select

from app.common.config import get_settings
from app.db.models import SpaceWeatherSnapshot
from app.db.session import SessionLocal
from app.observability.metrics import record_api_call


def _extract_latest_kp(payload: list) -> float:
    # NOAA Kp endpoint returns header row + data rows.
    if len(payload) <= 1:
        return 0.0
    latest = payload[-1]
    return float(latest[1])


def _extract_latest_xray(payload: list[dict]) -> str | None:
    if not payload:
        return None
    flux = payload[-1].get("flux")
    if flux is None:
        return None
    flux = float(flux)
    if flux >= 1e-4:
        return "X"
    if flux >= 1e-5:
        return "M"
    if flux >= 1e-6:
        return "C"
    if flux >= 1e-7:
        return "B"
    return "A"


def fetch_and_store_space_weather() -> SpaceWeatherSnapshot:
    settings = get_settings()
    with httpx.Client(timeout=20) as client:
        kp_start = perf_counter()
        try:
            kp_resp = client.get(settings.noaa_kp_api)
            kp_resp.raise_for_status()
            kp_payload = kp_resp.json()
            record_api_call("noaa_kp", ok=True, duration_ms=int((perf_counter() - kp_start) * 1000))
        except Exception as exc:  # noqa: BLE001
            record_api_call(
                "noaa_kp",
                ok=False,
                duration_ms=int((perf_counter() - kp_start) * 1000),
                error=str(exc),
            )
            raise

        xray_start = perf_counter()
        try:
            xray_resp = client.get(settings.noaa_xray_api)
            xray_resp.raise_for_status()
            xray_payload = xray_resp.json()
            record_api_call("noaa_xray", ok=True, duration_ms=int((perf_counter() - xray_start) * 1000))
        except Exception as exc:  # noqa: BLE001
            record_api_call(
                "noaa_xray",
                ok=False,
                duration_ms=int((perf_counter() - xray_start) * 1000),
                error=str(exc),
            )
            raise

    snapshot = SpaceWeatherSnapshot(
        observed_at=datetime.utcnow(),
        kp_index=_extract_latest_kp(kp_payload),
        xray_class=_extract_latest_xray(xray_payload),
        raw_payload=json.dumps({"kp": kp_payload, "xray": xray_payload}),
    )

    db = SessionLocal()
    try:
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot
    finally:
        db.close()


def get_latest_space_weather() -> SpaceWeatherSnapshot | None:
    db = SessionLocal()
    try:
        stmt = select(SpaceWeatherSnapshot).order_by(SpaceWeatherSnapshot.observed_at.desc()).limit(1)
        return db.scalars(stmt).first()
    finally:
        db.close()
