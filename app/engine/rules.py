from __future__ import annotations

from app.db.models import SpaceWeatherSnapshot


def is_emergency(snapshot: SpaceWeatherSnapshot | None) -> bool:
    if snapshot is None:
        return False
    if snapshot.kp_index >= 6.0:
        return True
    return (snapshot.xray_class or "").upper().startswith("X")
