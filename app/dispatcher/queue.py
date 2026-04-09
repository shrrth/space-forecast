from __future__ import annotations

from typing import Literal

import redis

from app.common.config import get_settings

JobType = Literal["emergency", "daily"]

_QUEUE_KEYS: dict[JobType, str] = {
    "emergency": "queue:message_jobs:emergency",
    "daily": "queue:message_jobs:daily",
}
_QUEUE_SET_KEYS: dict[JobType, str] = {
    "emergency": "queue:message_jobs:emergency:set",
    "daily": "queue:message_jobs:daily:set",
}

_client: redis.Redis | None = None

# Atomically enqueue only IDs that are new in the dedupe set.
_ENQUEUE_LUA = """
local list_key = KEYS[1]
local set_key = KEYS[2]
local pushed = 0
for i=1,#ARGV do
  local id = ARGV[i]
  if redis.call('SADD', set_key, id) == 1 then
    redis.call('RPUSH', list_key, id)
    pushed = pushed + 1
  end
end
return pushed
"""

# Atomically pop one ID from list and remove it from dedupe set.
_POP_LUA = """
local list_key = KEYS[1]
local set_key = KEYS[2]
local val = redis.call('LPOP', list_key)
if not val then
  return nil
end
redis.call('SREM', set_key, val)
return val
"""


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def enqueue_job_ids(job_type: JobType, job_ids: list[int]) -> None:
    if not job_ids:
        return
    list_key = _QUEUE_KEYS[job_type]
    set_key = _QUEUE_SET_KEYS[job_type]
    client = _redis()
    payload = [str(job_id) for job_id in job_ids]
    client.eval(_ENQUEUE_LUA, 2, list_key, set_key, *payload)


def pop_job_ids(job_type: JobType, limit: int = 200) -> list[int]:
    list_key = _QUEUE_KEYS[job_type]
    set_key = _QUEUE_SET_KEYS[job_type]
    client = _redis()
    result: list[int] = []
    for _ in range(limit):
        val = client.eval(_POP_LUA, 2, list_key, set_key)
        if val is None:
            break
        result.append(int(val))
    return result


def get_queue_length(job_type: JobType) -> int:
    key = _QUEUE_KEYS[job_type]
    return int(_redis().llen(key))


def get_all_queue_lengths() -> dict[JobType, int]:
    return {
        "emergency": get_queue_length("emergency"),
        "daily": get_queue_length("daily"),
    }
