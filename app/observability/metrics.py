from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import time

import redis

from app.common.config import get_settings

_client: redis.Redis | None = None
_COUNTER_PREFIX = "metric:counter:"
_DURATION_PREFIX = "metric:duration:"
_FAILURE_PREFIX = "metric:failure:"


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def _bucket_minute(ts: datetime | None = None) -> str:
    now = ts or datetime.now(timezone.utc)
    return now.strftime("%Y%m%d%H%M")


def incr_counter(name: str, value: int = 1, ttl_sec: int = 86400) -> None:
    key = f"{_COUNTER_PREFIX}{name}"
    client = _redis()
    client.incrby(key, value)
    client.expire(key, ttl_sec)


def observe_duration(name: str, duration_ms: int, ttl_sec: int = 86400) -> None:
    client = _redis()
    count_key = f"{_DURATION_PREFIX}{name}:count"
    sum_key = f"{_DURATION_PREFIX}{name}:sum_ms"
    client.incr(count_key)
    client.incrby(sum_key, max(duration_ms, 0))
    client.expire(count_key, ttl_sec)
    client.expire(sum_key, ttl_sec)


def record_failure(component: str, reason: str) -> None:
    client = _redis()
    bucket = _bucket_minute()
    key = f"{_FAILURE_PREFIX}{component}:{bucket}"
    client.incr(key)
    client.expire(key, 7200)
    client.lpush(f"{_FAILURE_PREFIX}{component}:recent", f"{int(time.time())}:{reason[:240]}")
    client.ltrim(f"{_FAILURE_PREFIX}{component}:recent", 0, 99)
    client.expire(f"{_FAILURE_PREFIX}{component}:recent", 86400)


def recent_failure_count(component: str, minutes: int = 5) -> int:
    client = _redis()
    total = 0
    now = datetime.now(timezone.utc)
    for offset in range(minutes):
        bucket = _bucket_minute(now - timedelta(minutes=offset))
        val = client.get(f"{_FAILURE_PREFIX}{component}:{bucket}")
        if val:
            total += int(val)
    return total


def record_job_success(job_name: str, duration_ms: int, processed: int | None = None) -> None:
    incr_counter(f"job:{job_name}:success")
    observe_duration(f"job:{job_name}", duration_ms)
    if processed is not None:
        incr_counter(f"job:{job_name}:processed", processed)


def record_job_failure(job_name: str, error: str) -> None:
    incr_counter(f"job:{job_name}:failure")
    record_failure("jobs", f"{job_name}:{error}")


def record_api_call(provider: str, ok: bool, duration_ms: int, error: str | None = None) -> None:
    status = "success" if ok else "failure"
    incr_counter(f"api:{provider}:{status}")
    observe_duration(f"api:{provider}", duration_ms)
    if not ok and error:
        record_failure("api", f"{provider}:{error}")


def _safe_metric_name(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", raw)


def read_counters() -> dict[str, int]:
    client = _redis()
    out: dict[str, int] = {}
    cursor = 0
    while True:
        cursor, keys = client.scan(cursor=cursor, match=f"{_COUNTER_PREFIX}*", count=200)
        for key in keys:
            name = key.removeprefix(_COUNTER_PREFIX)
            val = client.get(key)
            if val is None:
                continue
            out[_safe_metric_name(name)] = int(val)
        if cursor == 0:
            break
    return out


def read_durations() -> dict[str, tuple[int, int]]:
    client = _redis()
    out: dict[str, tuple[int, int]] = {}
    cursor = 0
    while True:
        cursor, count_keys = client.scan(cursor=cursor, match=f"{_DURATION_PREFIX}*:count", count=200)
        for count_key in count_keys:
            base = count_key.removeprefix(_DURATION_PREFIX).removesuffix(":count")
            sum_key = f"{_DURATION_PREFIX}{base}:sum_ms"
            count_val = client.get(count_key)
            sum_val = client.get(sum_key)
            if count_val is None or sum_val is None:
                continue
            out[_safe_metric_name(base)] = (int(count_val), int(sum_val))
        if cursor == 0:
            break
    return out
