from __future__ import annotations

import re


_SECRET_PATTERNS = [
    re.compile(r"(?i)(appid=)([^&\s]+)"),
    re.compile(r"(?i)(servicekey=)([^&\s]+)"),
    re.compile(r"(?i)(token=)([^&\s]+)"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)([^\s]+)"),
]


def sanitize_error_message(message: str, limit: int = 200) -> str:
    redacted = message
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted[:limit]
