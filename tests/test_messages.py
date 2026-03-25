from datetime import datetime

from app.db.models import LocalWeatherSnapshot, SpaceWeatherSnapshot, User
from app.engine.messages import build_daily_message, build_emergency_message


def test_daily_message_contains_key_fields() -> None:
    user = User(
        telegram_user_id=1,
        timezone="Asia/Seoul",
        lat=37.5,
        lon=127.0,
        location_label="Seoul",
        alert_enabled=True,
        language_code="ko",
    )
    sw = SpaceWeatherSnapshot(
        observed_at=datetime.utcnow(),
        kp_index=4.5,
        xray_class="M",
        raw_payload="{}",
    )
    lw = LocalWeatherSnapshot(
        region_key="37.5:127.0",
        observed_at=datetime.utcnow(),
        cloud_pct=20.0,
        humidity=50.0,
        temperature_c=10.0,
        wind_mps=3.2,
        seeing_score=4.0,
        raw_payload="{}",
    )

    msg = build_daily_message(user, sw, lw)

    assert "일일 관측 리포트" in msg
    assert "Seoul" in msg
    assert "Kp 4.5" in msg
    assert "프로필: 장비 basic, 목적 deep_sky" in msg
    assert "기온" in msg
    assert "풍속" in msg
    assert "강수확률" in msg
    assert "강수량" in msg
    assert "종합 관측 지수" in msg
    assert "점수 근거" in msg


def test_daily_message_english_template() -> None:
    user = User(
        telegram_user_id=2,
        timezone="UTC",
        lat=51.5,
        lon=-0.1,
        location_label="London",
        alert_enabled=True,
        language_code="en",
    )
    sw = SpaceWeatherSnapshot(
        observed_at=datetime.utcnow(),
        kp_index=3.0,
        xray_class="C",
        raw_payload="{}",
    )
    lw = LocalWeatherSnapshot(
        region_key="51.5:-0.1",
        observed_at=datetime.utcnow(),
        cloud_pct=35.0,
        humidity=70.0,
        temperature_c=8.0,
        wind_mps=4.0,
        precip_prob_pct=60.0,
        precip_mm=1.2,
        seeing_score=3.5,
        raw_payload="{}",
    )

    msg = build_daily_message(user, sw, lw)
    assert "Daily Observation Report" in msg
    assert "Profile: equipment" in msg
    assert "precip. prob" in msg
    assert "Observation score" in msg


def test_emergency_message_english_template() -> None:
    sw = SpaceWeatherSnapshot(
        observed_at=datetime.utcnow(),
        kp_index=7.0,
        xray_class="X",
        raw_payload="{}",
    )
    msg = build_emergency_message(sw, language_code="en")
    assert "Emergency Space Weather Alert" in msg
    assert "Time:" in msg
