"""
Fetches current Lagos weather from Open-Meteo free API.
Uses past_hours=6 to get overnight precipitation data.
Lagos rain is convective — use `precipitation` not `rain` (rain field is often 0).
"""

import httpx
from config import OPEN_METEO_URL

WEATHER_CODE_LABELS: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


async def fetch_weather() -> dict:
    """
    Returns:
        precip_sum_mm    — total precipitation over the past 6 hours
        precip_hours     — number of hourly slots with > 0.1mm (drain saturation signal)
        weather_code     — current WMO weather code
        condition_label  — human-readable condition string
        season           — "peak" (Jul–Sep), "secondary" (Jun, Oct), "dry" (Nov–Mar)
        raw              — full Open-Meteo hourly response for debugging
    """
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(OPEN_METEO_URL)
        resp.raise_for_status()
        data = resp.json()

    hourly = data.get("hourly", {})
    precip_list: list[float] = hourly.get("precipitation", [])
    code_list: list[int]     = hourly.get("weathercode", [])

    # past_hours=6 puts the past 6 readings first in the hourly arrays
    past_precip = precip_list[:6]

    precip_sum_mm = round(sum(past_precip), 2)
    precip_hours  = sum(1 for p in past_precip if p > 0.1)

    # current weather = most recent hourly slot (index 5 of the past 6)
    current_code = code_list[5] if len(code_list) >= 6 else 0
    condition    = WEATHER_CODE_LABELS.get(current_code, f"Code {current_code}")

    # Determine season (Lagos rainfall calendar)
    from datetime import datetime
    import pytz
    now_lagos = datetime.now(pytz.timezone("Africa/Lagos"))
    month = now_lagos.month
    if month in (7, 8, 9):
        season = "peak"
    elif month in (6, 10):
        season = "secondary"
    else:
        season = "dry"

    season_labels = {"peak": "Peak flood season (Jul–Sep)", "secondary": "Secondary rainy season", "dry": "Dry season"}

    return {
        "precip_sum_mm":   precip_sum_mm,
        "precip_hours":    precip_hours,
        "weather_code":    current_code,
        "condition_label": condition,
        "season":          season,
        "season_label":    season_labels[season],
        "month":           month,
        "raw":             data,
    }
