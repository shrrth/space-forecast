from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreBreakdown:
    score: int
    cloud_penalty: int
    humidity_penalty: int
    temp_penalty: int
    wind_penalty: int
    precip_prob_penalty: int
    precip_amount_penalty: int
    kp_penalty: int
    xray_penalty: int
    seeing_bonus: int


@dataclass(frozen=True)
class ScoreProfile:
    cloud_mult: float = 1.0
    humidity_mult: float = 1.0
    temp_mult: float = 1.0
    wind_mult: float = 1.0
    precip_prob_mult: float = 1.0
    precip_amount_mult: float = 1.0
    kp_mult: float = 1.0
    xray_mult: float = 1.0
    seeing_mult: float = 1.0


def profile_for_user(equipment_level: str | None, observation_purpose: str | None) -> ScoreProfile:
    equipment = (equipment_level or "basic").strip().lower()
    purpose = (observation_purpose or "deep_sky").strip().lower()

    profile = ScoreProfile()
    if equipment == "visual":
        profile = ScoreProfile(cloud_mult=1.1, wind_mult=1.15, seeing_mult=0.7)
    elif equipment == "advanced":
        profile = ScoreProfile(cloud_mult=0.9, temp_mult=0.9, wind_mult=0.9, precip_prob_mult=0.9, seeing_mult=1.2)

    if purpose == "planetary":
        profile = ScoreProfile(
            cloud_mult=profile.cloud_mult * 0.95,
            humidity_mult=profile.humidity_mult * 1.05,
            temp_mult=profile.temp_mult,
            wind_mult=profile.wind_mult * 1.1,
            precip_prob_mult=profile.precip_prob_mult * 0.9,
            precip_amount_mult=profile.precip_amount_mult * 0.9,
            kp_mult=profile.kp_mult,
            xray_mult=profile.xray_mult,
            seeing_mult=profile.seeing_mult * 1.25,
        )
    elif purpose == "widefield":
        profile = ScoreProfile(
            cloud_mult=profile.cloud_mult * 0.85,
            humidity_mult=profile.humidity_mult,
            temp_mult=profile.temp_mult,
            wind_mult=profile.wind_mult * 0.9,
            precip_prob_mult=profile.precip_prob_mult,
            precip_amount_mult=profile.precip_amount_mult,
            kp_mult=profile.kp_mult,
            xray_mult=profile.xray_mult,
            seeing_mult=profile.seeing_mult * 0.9,
        )
    elif purpose == "deep_sky":
        profile = ScoreProfile(
            cloud_mult=profile.cloud_mult * 1.15,
            humidity_mult=profile.humidity_mult * 1.05,
            temp_mult=profile.temp_mult,
            wind_mult=profile.wind_mult,
            precip_prob_mult=profile.precip_prob_mult * 1.2,
            precip_amount_mult=profile.precip_amount_mult * 1.3,
            kp_mult=profile.kp_mult,
            xray_mult=profile.xray_mult * 0.9,
            seeing_mult=profile.seeing_mult * 1.1,
        )

    return profile


def _apply_mult(value: int, mult: float, cap: int) -> int:
    return min(max(int(round(value * mult)), 0), cap)


def _xray_penalty(xray_class: str | None) -> int:
    x = (xray_class or "").upper()
    if x.startswith("X"):
        return 20
    if x.startswith("M"):
        return 10
    if x.startswith("C"):
        return 5
    return 0


def score_breakdown(
    kp_index: float,
    cloud_pct: float,
    humidity: float,
    temperature_c: float,
    wind_mps: float,
    seeing_score: float,
    xray_class: str | None,
    precip_prob_pct: float = 0.0,
    precip_mm: float = 0.0,
    profile: ScoreProfile | None = None,
) -> ScoreBreakdown:
    # Weighted heuristic for MVP:
    # weather dominates feasibility, space weather adds risk penalty.
    active = profile or ScoreProfile()
    cloud_penalty = _apply_mult(min(int(cloud_pct * 0.45), 45), active.cloud_mult, 45)
    humidity_penalty = _apply_mult(min(max(int((humidity - 45.0) * 0.35), 0), 20), active.humidity_mult, 20)
    temp_penalty = _apply_mult(min(max(int(abs(temperature_c - 12.0) * 1.2), 0), 15), active.temp_mult, 15)
    wind_penalty = _apply_mult(min(max(int((wind_mps - 3.0) * 2.0), 0), 20), active.wind_mult, 20)
    precip_prob_penalty = _apply_mult(min(int(max(precip_prob_pct, 0.0) * 0.20), 20), active.precip_prob_mult, 20)
    precip_amount_penalty = _apply_mult(min(int(max(precip_mm, 0.0) * 3.0), 15), active.precip_amount_mult, 15)
    kp_penalty = _apply_mult(min(int(kp_index * 4.5), 30), active.kp_mult, 30)
    xray = _apply_mult(_xray_penalty(xray_class), active.xray_mult, 20)
    seeing_bonus = _apply_mult(min(max(int((seeing_score - 2.0) * 5), 0), 15), active.seeing_mult, 15)

    raw_score = (
        100
        - cloud_penalty
        - humidity_penalty
        - temp_penalty
        - wind_penalty
        - precip_prob_penalty
        - precip_amount_penalty
        - kp_penalty
        - xray
        + seeing_bonus
    )
    score = max(0, min(100, raw_score))
    return ScoreBreakdown(
        score=score,
        cloud_penalty=cloud_penalty,
        humidity_penalty=humidity_penalty,
        temp_penalty=temp_penalty,
        wind_penalty=wind_penalty,
        precip_prob_penalty=precip_prob_penalty,
        precip_amount_penalty=precip_amount_penalty,
        kp_penalty=kp_penalty,
        xray_penalty=xray,
        seeing_bonus=seeing_bonus,
    )


def observation_score(kp_index: float, cloud_pct: float) -> int:
    # Backward-compatible wrapper used in legacy tests/callers.
    # Keep the previous two-factor model for stable behavior.
    raw = 100 - int(kp_index * 5) - int(cloud_pct)
    return max(0, min(100, raw))


def score_label(score: int) -> str:
    if score >= 75:
        return "권장"
    if score >= 50:
        return "보통"
    return "주의"
