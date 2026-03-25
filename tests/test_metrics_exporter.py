from types import SimpleNamespace

import pytest

from app.observability.exporter import _is_authorized, _render_prometheus, _validate_metrics_security


def test_render_prometheus_smoke(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.observability.exporter.read_counters",
        lambda: {"job_noaa_ingest_success": 3},
    )
    monkeypatch.setattr(
        "app.observability.exporter.read_durations",
        lambda: {"job_noaa_ingest": (3, 1200)},
    )
    monkeypatch.setattr(
        "app.observability.exporter.get_all_queue_lengths",
        lambda: {"daily": 2, "emergency": 1},
    )
    monkeypatch.setattr(
        "app.observability.exporter.recent_failure_count",
        lambda component, minutes=5: 0,
    )

    txt = _render_prometheus()

    assert "spaceforecast_counter" in txt
    assert "spaceforecast_duration_count" in txt
    assert "spaceforecast_queue_depth" in txt
    assert "spaceforecast_recent_failures_5m" in txt


def test_metrics_auth_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.observability.exporter.get_settings",
        lambda: SimpleNamespace(metrics_token=""),
    )
    req = SimpleNamespace(headers={})
    assert _is_authorized(req) is True


def test_metrics_auth_bearer(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.observability.exporter.get_settings",
        lambda: SimpleNamespace(metrics_token="secret"),
    )
    req = SimpleNamespace(headers={"Authorization": "Bearer secret"})
    assert _is_authorized(req) is True


def test_metrics_auth_custom_header(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.observability.exporter.get_settings",
        lambda: SimpleNamespace(metrics_token="secret"),
    )
    req = SimpleNamespace(headers={"X-Metrics-Token": "secret"})
    assert _is_authorized(req) is True


def test_metrics_auth_reject(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.observability.exporter.get_settings",
        lambda: SimpleNamespace(metrics_token="secret"),
    )
    req = SimpleNamespace(headers={"Authorization": "Bearer wrong"})
    assert _is_authorized(req) is False


def test_metrics_security_allows_local_without_token(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.observability.exporter.get_settings",
        lambda: SimpleNamespace(metrics_enabled=True, metrics_host="127.0.0.1", metrics_token="", app_env="dev"),
    )
    _validate_metrics_security()


def test_metrics_security_requires_token_on_nonlocal(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.observability.exporter.get_settings",
        lambda: SimpleNamespace(metrics_enabled=True, metrics_host="0.0.0.0", metrics_token="", app_env="dev"),
    )
    with pytest.raises(RuntimeError):
        _validate_metrics_security()


def test_metrics_security_requires_token_in_production(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.observability.exporter.get_settings",
        lambda: SimpleNamespace(metrics_enabled=True, metrics_host="127.0.0.1", metrics_token="", app_env="production"),
    )
    with pytest.raises(RuntimeError):
        _validate_metrics_security()
