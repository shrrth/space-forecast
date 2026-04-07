from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.db.models import LocalWeatherSnapshot, SpaceWeatherSnapshot, User
from app.engine.score import profile_for_user, score_breakdown, score_label


def _normalize_lang(raw: str | None) -> str:
    lang = (raw or "ko").strip().lower()
    if lang.startswith("en"):
        return "en"
    return "ko"


def build_emergency_message(snapshot: SpaceWeatherSnapshot, language_code: str | None = None) -> str:
    lang = _normalize_lang(language_code)
    observed = snapshot.observed_at.strftime("%Y-%m-%d %H:%M UTC")
    if lang == "en":
        return (
            "[Emergency Space Weather Alert]\n"
            f"- Time: {observed}\n"
            f"- Kp: {snapshot.kp_index:.1f}\n"
            f"- X-ray: {snapshot.xray_class or 'N/A'}\n"
            "Check mount alignment and power status before observation."
        )
    return (
        "[긴급 우주기상 경보]\n"
        f"- 시각: {observed}\n"
        f"- Kp: {snapshot.kp_index:.1f}\n"
        f"- X-ray: {snapshot.xray_class or 'N/A'}\n"
        "관측 전 장비 정렬과 전원 상태를 점검하세요."
    )


def build_daily_message(
    user: User,
    space_weather: SpaceWeatherSnapshot | None,
    local_weather: LocalWeatherSnapshot,
) -> str:
    lang = _normalize_lang(user.language_code)
    now_local = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(user.timezone))
    equipment_level = user.equipment_level or "basic"
    observation_purpose = user.observation_purpose or "deep_sky"
    kp = 0.0 if space_weather is None else space_weather.kp_index
    xray_class = space_weather.xray_class if space_weather else None
    profile = profile_for_user(
        equipment_level=equipment_level,
        observation_purpose=observation_purpose,
    )
    precip_prob_pct = float(local_weather.precip_prob_pct or 0.0)
    precip_mm = float(local_weather.precip_mm or 0.0)
    breakdown = score_breakdown(
        kp_index=kp,
        cloud_pct=local_weather.cloud_pct,
        humidity=local_weather.humidity,
        temperature_c=local_weather.temperature_c,
        wind_mps=local_weather.wind_mps,
        seeing_score=local_weather.seeing_score,
        xray_class=xray_class,
        precip_prob_pct=precip_prob_pct,
        precip_mm=precip_mm,
        profile=profile,
    )
    label = score_label(breakdown.score)
    if lang == "en":
        label = {"권장": "Recommended", "보통": "Fair", "주의": "Caution"}.get(label, label)
    if lang == "en":
        return (
            "[Daily Observation Report]\n"
            f"- Location: {user.location_label}\n"
            f"- Time: {now_local.strftime('%Y-%m-%d %H:%M %Z')}\n"
            f"- Profile: equipment {equipment_level}, purpose {observation_purpose}\n"
            f"- Space weather: Kp {kp:.1f}, X-ray {(xray_class or 'N/A')}\n"
            f"- Local weather: cloud {local_weather.cloud_pct:.0f}%, humidity {local_weather.humidity:.0f}%, "
            f"temp {local_weather.temperature_c:.1f}°C, wind {local_weather.wind_mps:.1f}m/s, "
            f"precip. prob {precip_prob_pct:.0f}%, precip {precip_mm:.1f}mm, "
            f"seeing {local_weather.seeing_score:.1f}/5\n"
            f"- Observation score: {breakdown.score}/100 ({label})\n"
            f"- Breakdown: cloud -{breakdown.cloud_penalty}, humidity -{breakdown.humidity_penalty}, "
            f"temp -{breakdown.temp_penalty}, wind -{breakdown.wind_penalty}, "
            f"precip_prob -{breakdown.precip_prob_penalty}, precip -{breakdown.precip_amount_penalty}, "
            f"Kp -{breakdown.kp_penalty}, X-ray -{breakdown.xray_penalty}, seeing +{breakdown.seeing_bonus}"
        )

    return (
        "[일일 관측 리포트]\n"
        f"- 위치: {user.location_label}\n"
        f"- 시각: {now_local.strftime('%Y-%m-%d %H:%M %Z')}\n"
        f"- 프로필: 장비 {equipment_level}, 목적 {observation_purpose}\n"
        f"- 우주기상: Kp {kp:.1f}, X-ray {(xray_class or 'N/A')}\n"
        f"- 지상날씨: 구름 {local_weather.cloud_pct:.0f}%, 습도 {local_weather.humidity:.0f}%, "
        f"기온 {local_weather.temperature_c:.1f}°C, 풍속 {local_weather.wind_mps:.1f}m/s, "
        f"강수확률 {precip_prob_pct:.0f}%, 강수량 {precip_mm:.1f}mm, "
        f"시상 {local_weather.seeing_score:.1f}/5\n"
        f"- 종합 관측 지수: {breakdown.score}/100 ({label})\n"
        f"- 점수 근거: 구름 -{breakdown.cloud_penalty}, 습도 -{breakdown.humidity_penalty}, "
        f"기온 -{breakdown.temp_penalty}, 풍속 -{breakdown.wind_penalty}, "
        f"강수확률 -{breakdown.precip_prob_penalty}, 강수량 -{breakdown.precip_amount_penalty}, "
        f"Kp -{breakdown.kp_penalty}, X-ray -{breakdown.xray_penalty}, 시상 +{breakdown.seeing_bonus}"
    )
