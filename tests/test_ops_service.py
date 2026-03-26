from types import SimpleNamespace

from app.bot.ops_service import _parse_admin_ids, build_ops_status_text, is_ops_admin


def test_parse_admin_ids() -> None:
    ids = _parse_admin_ids("123, 456 ,bad, , 789")
    assert ids == {123, 456, 789}


def test_is_ops_admin(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.bot.ops_service.get_settings",
        lambda: SimpleNamespace(ops_admin_ids="10,20"),
    )
    assert is_ops_admin(10) is True
    assert is_ops_admin(99) is False


def test_build_ops_status_text(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.bot.ops_service.get_settings",
        lambda: SimpleNamespace(
            alert_queue_threshold=500,
            alert_failure_threshold=20,
            alert_chat_id="123456",
            alert_webhook_url="https://example.com/webhook",
        ),
    )
    monkeypatch.setattr("app.bot.ops_service.get_all_queue_lengths", lambda: {"emergency": 3, "daily": 7})
    monkeypatch.setattr("app.bot.ops_service.recent_failure_count", lambda component, minutes=5: 1)
    monkeypatch.setattr("app.bot.ops_service.get_latest_space_weather", lambda: None)
    monkeypatch.setattr("app.bot.ops_service.latest_local_weather_observed_at", lambda: None)
    monkeypatch.setattr("app.bot.ops_service.pending_retry_backlog", lambda: 4)

    text = build_ops_status_text()

    assert "overall: WARN" in text
    assert "queue emergency: 3" in text
    assert "queue daily: 7" in text
    assert "retry backlog(pending retry_count>0): 4" in text
    assert "queue threshold: 500" in text
    assert "alert channels: telegram=ON, webhook=ON" in text
    assert "failures(5m):" in text
    assert "failure threshold(5m): 20" in text
    assert "latest ingest:" in text
