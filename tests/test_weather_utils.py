from app.engine.weather import region_key_for_user
from app.ingestor.local_weather import _seeing_score_from_weather


def test_region_key_rounding() -> None:
    assert region_key_for_user(37.56, 126.97) == "37.5:127.0"


def test_seeing_score_bounds() -> None:
    assert _seeing_score_from_weather(cloud_pct=0.0, humidity=30.0) == 5.0
    assert _seeing_score_from_weather(cloud_pct=100.0, humidity=90.0) >= 1.0
