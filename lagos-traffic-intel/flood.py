"""
Flood zone assessment. Input: weather data. Output: list of at-risk zone dicts.
Thresholds calibrated from Lagos flood event news archives 2019–2026.
"""

from config import FLOOD_ZONES

EXTREME_MM    = 25.0  # above this → everything tier 1+ is HIGH confidence
EXTREME_HOURS = 6     # above this → everything at risk is HIGH confidence
PEAK_SEASON_FACTOR = 0.85  # reduce thresholds Jul–Sep (drain infra already saturated)


def assess_flood_zones(precip_sum_mm: float, precip_hours: int, month: int) -> list[dict]:
    """
    Returns list of at-risk zones ordered by tier then confidence.
    Confidence:
      HIGH   — both thresholds met, or extreme rain event
      MEDIUM — exactly one threshold met
    """
    season_factor = PEAK_SEASON_FACTOR if month in (7, 8, 9) else 1.0
    is_extreme    = precip_sum_mm >= EXTREME_MM or precip_hours >= EXTREME_HOURS

    at_risk: list[dict] = []
    for zone in FLOOD_ZONES:
        effective_mm  = zone["mm_threshold"]  * season_factor
        effective_hrs = zone["hours_threshold"]

        meets_mm  = precip_sum_mm >= effective_mm
        meets_hrs = precip_hours  >= effective_hrs

        if meets_mm or meets_hrs:
            confidence = "HIGH" if (is_extreme or (meets_mm and meets_hrs)) else "MEDIUM"
            at_risk.append({
                "id":         zone["id"],
                "name":       zone["name"],
                "area":       zone["area"],
                "tier":       zone["tier"],
                "confidence": confidence,
            })

    # Sort: tier 1 first, then HIGH before MEDIUM
    at_risk.sort(key=lambda z: (z["tier"], 0 if z["confidence"] == "HIGH" else 1))
    return at_risk
