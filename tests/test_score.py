from app.engine.score import observation_score, profile_for_user, score_breakdown, score_label


def test_observation_score_bounds() -> None:
    assert observation_score(0.0, 0.0) == 100
    assert observation_score(20.0, 100.0) == 0


def test_score_label() -> None:
    assert score_label(80) == "권장"
    assert score_label(60) == "보통"
    assert score_label(30) == "주의"


def test_score_breakdown_reflects_xray_and_seeing() -> None:
    calm = score_breakdown(
        kp_index=2.0,
        cloud_pct=20.0,
        humidity=50.0,
        temperature_c=12.0,
        wind_mps=2.0,
        seeing_score=4.5,
        xray_class="B",
    )
    storm = score_breakdown(
        kp_index=2.0,
        cloud_pct=20.0,
        humidity=50.0,
        temperature_c=12.0,
        wind_mps=2.0,
        seeing_score=4.5,
        xray_class="X",
    )
    assert storm.score < calm.score
    assert calm.seeing_bonus > 0


def test_score_breakdown_reflects_wind_and_temp() -> None:
    stable = score_breakdown(
        kp_index=2.0,
        cloud_pct=20.0,
        humidity=45.0,
        temperature_c=12.0,
        wind_mps=2.0,
        seeing_score=4.0,
        xray_class="B",
    )
    harsh = score_breakdown(
        kp_index=2.0,
        cloud_pct=20.0,
        humidity=45.0,
        temperature_c=-8.0,
        wind_mps=12.0,
        seeing_score=4.0,
        xray_class="B",
    )
    assert harsh.score < stable.score
    assert harsh.wind_penalty > 0
    assert harsh.temp_penalty > 0


def test_score_breakdown_profile_changes_result() -> None:
    basic = score_breakdown(
        kp_index=3.0,
        cloud_pct=40.0,
        humidity=65.0,
        temperature_c=4.0,
        wind_mps=6.0,
        seeing_score=3.5,
        xray_class="M",
        profile=profile_for_user("basic", "deep_sky"),
    )
    advanced = score_breakdown(
        kp_index=3.0,
        cloud_pct=40.0,
        humidity=65.0,
        temperature_c=4.0,
        wind_mps=6.0,
        seeing_score=3.5,
        xray_class="M",
        profile=profile_for_user("advanced", "deep_sky"),
    )
    assert advanced.score > basic.score


def test_score_breakdown_reflects_precipitation() -> None:
    dry = score_breakdown(
        kp_index=2.0,
        cloud_pct=15.0,
        humidity=40.0,
        temperature_c=12.0,
        wind_mps=2.0,
        seeing_score=4.0,
        xray_class="B",
        precip_prob_pct=0.0,
        precip_mm=0.0,
    )
    rainy = score_breakdown(
        kp_index=2.0,
        cloud_pct=15.0,
        humidity=40.0,
        temperature_c=12.0,
        wind_mps=2.0,
        seeing_score=4.0,
        xray_class="B",
        precip_prob_pct=80.0,
        precip_mm=3.0,
    )
    assert rainy.score < dry.score
    assert rainy.precip_prob_penalty > 0
    assert rainy.precip_amount_penalty > 0
