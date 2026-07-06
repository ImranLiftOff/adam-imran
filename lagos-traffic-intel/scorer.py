"""
Deterministic scoring engine. No I/O — pure functions only.
The score is computed before any AI call so Claude never decides traffic severity.
"""

from config import BASE_SCORE_MATRIX, DEFAULT_BASE_SCORE, SCORE_LEVELS


def get_base_score(day: str, hour: int = 7) -> int:
    key_day = day.lower()
    for (d, h0, h1), score in BASE_SCORE_MATRIX.items():
        if d == key_day and h0 <= hour < h1:
            return score
    return DEFAULT_BASE_SCORE


def weather_modifier(precip_hours: int, precip_sum_mm: float, month: int) -> int:
    """
    Primary signal: precip_hours (drain saturation).
    Secondary: precip_sum_mm (raw intensity).
    Peak season (Jul–Sep): infrastructure already stressed, lower effective threshold.
    """
    mod = 0
    if precip_hours >= 6:
        mod += 3
    elif precip_hours >= 4:
        mod += 2
    elif precip_hours >= 2:
        mod += 1

    if precip_sum_mm >= 25:
        mod += 2
    elif precip_sum_mm >= 10:
        mod += 1

    # Peak flood season bonus — drainage already compromised from accumulated rain
    if month in (7, 8, 9) and mod > 0:
        mod += 1

    return min(mod, 4)


def signal_modifier(signals: list[dict]) -> int:
    """
    +2 for any HIGH-severity event (convoy, bridge closure, confirmed flooding).
    +1 for any MEDIUM-severity event (accident, maintenance).
    Capped at 2.
    """
    mod = 0
    for sig in signals:
        sev = sig.get("severity", "LOW")
        if sev == "HIGH":
            mod = max(mod, 2)
        elif sev == "MEDIUM":
            mod = max(mod, 1)
    return mod


def compute_score(base: int, w_mod: int, s_mod: int) -> int:
    return min(base + w_mod + s_mod, 10)


def score_to_level(score: int) -> tuple[str, str]:
    """Returns (level_name, hex_color)."""
    for lo, hi, name, color in SCORE_LEVELS:
        if lo <= score <= hi:
            return name, color
    return "Light", "#16A34A"


def full_score(day: str, hour: int, precip_hours: int, precip_sum_mm: float,
               month: int, signals: list[dict]) -> dict:
    base   = get_base_score(day, hour)
    w_mod  = weather_modifier(precip_hours, precip_sum_mm, month)
    s_mod  = signal_modifier(signals)
    score  = compute_score(base, w_mod, s_mod)
    level, color = score_to_level(score)
    return {
        "base_score":       base,
        "weather_modifier": w_mod,
        "signal_modifier":  s_mod,
        "final_score":      score,
        "level":            level,
        "hex_color":        color,
        "capped_at_10":     (base + w_mod + s_mod) > 10,
    }
