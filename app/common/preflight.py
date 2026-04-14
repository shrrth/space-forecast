from __future__ import annotations

from app.common.config import get_settings
from app.observability.exporter import _validate_metrics_security


def validate_runtime_settings() -> None:
    settings = get_settings()
    if settings.metrics_enabled:
        _validate_metrics_security()


def main() -> None:
    validate_runtime_settings()
    print("preflight: ok")


if __name__ == "__main__":
    main()
