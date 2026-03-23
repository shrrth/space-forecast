from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from time import perf_counter

import httpx
from sqlalchemy import select

from app.common.config import get_settings
from app.db.models import LocalWeatherSnapshot, User
from app.db.session import SessionLocal
from app.engine.weather import region_key_for_user
from app.observability.metrics import record_api_call


def _region_center_from_key(region_key: str) -> tuple[float, float]:
    lat_s, lon_s = region_key.split(":", maxsplit=1)
    return float(lat_s), float(lon_s)


def _seeing_score_from_weather(cloud_pct: float, humidity: float) -> float:
    # Simple proxy model for MVP: lower cloud/humidity -> better seeing.
    cloud_penalty = min(cloud_pct / 25.0, 3.0)
    humidity_penalty = min(max(humidity - 40.0, 0.0) / 30.0, 2.0)
    score = 5.0 - cloud_penalty - humidity_penalty
    return max(1.0, min(5.0, round(score, 1)))


def _active_region_keys() -> list[str]:
    db = SessionLocal()
    try:
        rows = db.execute(select(User.lat, User.lon)).all()
        keys = {region_key_for_user(float(lat), float(lon)) for lat, lon in rows}
        return sorted(keys)
    finally:
        db.close()


def _is_korea(lat: float, lon: float) -> bool:
    return 33.0 <= lat <= 39.5 and 124.0 <= lon <= 132.0


def _fetch_weather_openweather(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    lat: float,
    lon: float,
) -> dict:
    resp = client.get(
        base_url,
        params={
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
        },
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_weather_openmeteo(client: httpx.Client, base_url: str, lat: float, lon: float) -> dict:
    resp = client.get(
        base_url,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "cloud_cover,relative_humidity_2m,temperature_2m,wind_speed_10m,precipitation",
        },
    )
    resp.raise_for_status()
    return resp.json()


def _dfs_xy(lat: float, lon: float) -> tuple[int, int]:
    # Korea Meteorological Administration DFS grid conversion.
    re = 6371.00877
    grid = 5.0
    slat1 = 30.0
    slat2 = 60.0
    olon = 126.0
    olat = 38.0
    xo = 43
    yo = 136

    degrad = math.pi / 180.0
    re_n = re / grid
    slat1_r = slat1 * degrad
    slat2_r = slat2 * degrad
    olon_r = olon * degrad
    olat_r = olat * degrad

    sn = math.tan(math.pi * 0.25 + slat2_r * 0.5) / math.tan(math.pi * 0.25 + slat1_r * 0.5)
    sn = math.log(math.cos(slat1_r) / math.cos(slat2_r)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1_r * 0.5)
    sf = pow(sf, sn) * math.cos(slat1_r) / sn
    ro = math.tan(math.pi * 0.25 + olat_r * 0.5)
    ro = re_n * sf / pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + (lat) * degrad * 0.5)
    ra = re_n * sf / pow(ra, sn)
    theta = lon * degrad - olon_r
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = int(ra * math.sin(theta) + xo + 0.5)
    y = int(ro - ra * math.cos(theta) + yo + 0.5)
    return x, y


def _kma_base_dt(now: datetime | None = None) -> tuple[str, str]:
    t = (now or datetime.utcnow()) + timedelta(hours=9)
    # Village forecast published every hour around hh:40, use previous hour for safety.
    if t.minute < 45:
        t = t - timedelta(hours=1)
    return t.strftime("%Y%m%d"), t.strftime("%H00")


def _fetch_weather_kma(
    client: httpx.Client,
    base_url: str,
    service_key: str,
    lat: float,
    lon: float,
) -> dict:
    nx, ny = _dfs_xy(lat, lon)
    base_date, base_time = _kma_base_dt()
    resp = client.get(
        base_url,
        params={
            "serviceKey": service_key,
            "pageNo": 1,
            "numOfRows": 100,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        },
    )
    resp.raise_for_status()
    return resp.json()


def _extract_openweather(payload: dict) -> tuple[float, float, float, float, float, float]:
    cloud_pct = float(payload.get("clouds", {}).get("all", 0.0))
    humidity = float(payload.get("main", {}).get("humidity", 0.0))
    temp_c = float(payload.get("main", {}).get("temp", 15.0))
    wind_mps = float(payload.get("wind", {}).get("speed", 2.0))
    precip_prob_pct = 0.0
    precip_mm = float(payload.get("rain", {}).get("1h", 0.0)) + float(payload.get("snow", {}).get("1h", 0.0))
    return cloud_pct, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm


def _extract_openmeteo(payload: dict) -> tuple[float, float, float, float, float, float]:
    current = payload.get("current", {})
    cloud_pct = float(current.get("cloud_cover", 0.0))
    humidity = float(current.get("relative_humidity_2m", 0.0))
    temp_c = float(current.get("temperature_2m", 15.0))
    wind_mps = float(current.get("wind_speed_10m", 2.0))
    precip_prob_pct = 0.0
    precip_mm = float(current.get("precipitation", 0.0))
    return cloud_pct, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm


def _parse_kma_pcp(value: str) -> float:
    raw = (value or "").strip().replace(" ", "")
    if not raw or "강수없음" in raw or "없음" in raw:
        return 0.0
    if "미만" in raw:
        num = raw.replace("mm미만", "").replace("mm", "")
        try:
            return max(float(num) * 0.5, 0.0)
        except ValueError:
            return 0.1
    if "~" in raw and "mm" in raw:
        left, right = raw.replace("mm", "").split("~", maxsplit=1)
        try:
            return (float(left) + float(right)) / 2.0
        except ValueError:
            return 0.0
    try:
        return float(raw.replace("mm", ""))
    except ValueError:
        return 0.0


def _extract_kma(payload: dict) -> tuple[float, float, float, float, float, float]:
    items = (
        payload.get("response", {})
        .get("body", {})
        .get("items", {})
        .get("item", [])
    )
    cloud_pct = 0.0
    humidity = 0.0
    temp_c = 15.0
    wind_mps = 2.0
    precip_prob_pct = 0.0
    precip_mm = 0.0
    for item in items:
        category = item.get("category")
        val = item.get("fcstValue")
        if val is None:
            continue
        if category == "REH":
            humidity = float(val)
        elif category == "TMP":
            temp_c = float(val)
        elif category == "WSD":
            wind_mps = float(val)
        elif category == "POP":
            precip_prob_pct = float(val)
        elif category == "PCP":
            precip_mm = _parse_kma_pcp(str(val))
        elif category == "SKY":
            # KMA SKY: 1(clear),3(many clouds),4(overcast)
            sky = int(float(val))
            cloud_pct = {1: 10.0, 3: 60.0, 4: 90.0}.get(sky, 50.0)
    return cloud_pct, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm


def fetch_and_store_local_weather() -> int:
    settings = get_settings()

    region_keys = _active_region_keys()
    if not region_keys:
        return 0

    snapshots: list[LocalWeatherSnapshot] = []
    with httpx.Client(timeout=20) as client:
        for region_key in region_keys:
            lat, lon = _region_center_from_key(region_key)
            provider = "openmeteo"
            payload: dict

            if settings.openweather_api_key:
                start = perf_counter()
                try:
                    payload = _fetch_weather_openweather(
                        client,
                        base_url=settings.openweather_api_url,
                        api_key=settings.openweather_api_key,
                        lat=lat,
                        lon=lon,
                    )
                    cloud_pct, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm = _extract_openweather(payload)
                    provider = "openweather"
                    record_api_call("openweather", ok=True, duration_ms=int((perf_counter() - start) * 1000))
                except httpx.HTTPError:
                    record_api_call(
                        "openweather",
                        ok=False,
                        duration_ms=int((perf_counter() - start) * 1000),
                        error="http_error",
                    )
                    payload = {}
            else:
                payload = {}

            if provider != "openweather" and settings.kma_service_key and _is_korea(lat, lon):
                start = perf_counter()
                try:
                    payload = _fetch_weather_kma(
                        client,
                        base_url=settings.kma_api_url,
                        service_key=settings.kma_service_key,
                        lat=lat,
                        lon=lon,
                    )
                    cloud_pct, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm = _extract_kma(payload)
                    provider = "kma"
                    record_api_call("kma", ok=True, duration_ms=int((perf_counter() - start) * 1000))
                except httpx.HTTPError:
                    record_api_call(
                        "kma",
                        ok=False,
                        duration_ms=int((perf_counter() - start) * 1000),
                        error="http_error",
                    )
                    payload = {}

            if provider not in {"openweather", "kma"}:
                start = perf_counter()
                try:
                    payload = _fetch_weather_openmeteo(
                        client,
                        base_url=settings.openmeteo_api_url,
                        lat=lat,
                        lon=lon,
                    )
                    cloud_pct, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm = _extract_openmeteo(payload)
                    provider = "openmeteo"
                    record_api_call("openmeteo", ok=True, duration_ms=int((perf_counter() - start) * 1000))
                except httpx.HTTPError as exc:
                    record_api_call(
                        "openmeteo",
                        ok=False,
                        duration_ms=int((perf_counter() - start) * 1000),
                        error=str(exc),
                    )
                    raise

            seeing_score = _seeing_score_from_weather(cloud_pct=cloud_pct, humidity=humidity)

            snapshots.append(
                LocalWeatherSnapshot(
                    region_key=region_key,
                    observed_at=datetime.utcnow(),
                    cloud_pct=cloud_pct,
                    humidity=humidity,
                    temperature_c=temp_c,
                    wind_mps=wind_mps,
                    precip_prob_pct=precip_prob_pct,
                    precip_mm=precip_mm,
                    seeing_score=seeing_score,
                    raw_payload=json.dumps({"provider": provider, "payload": payload}),
                )
            )

    db = SessionLocal()
    try:
        db.add_all(snapshots)
        db.commit()
        return len(snapshots)
    finally:
        db.close()
