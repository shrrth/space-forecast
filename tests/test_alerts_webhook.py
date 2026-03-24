from app.observability.alerts import _webhook_payload


def test_webhook_payload_shape() -> None:
    payload = _webhook_payload("hello")
    assert payload == {"text": "hello"}
