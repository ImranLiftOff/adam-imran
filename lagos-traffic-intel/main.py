"""
Pipeline orchestrator. Run directly for manual/one-off execution:
  python main.py

Called by APScheduler in server.py at 5:45 AM and 4:00 PM WAT daily.
"""

import asyncio
import logging
import os
from datetime import datetime

import pytz

from config import LOG_DIR
from flood import assess_flood_zones
from narrator import generate_narrative
from scorer import full_score
from scraper import scrape_all
from signals import extract_signals, signals_to_text
from storage import append_history, write_today
from telegram import send_alert
from trigify import fetch_trigify_posts
from weather import fetch_weather

os.makedirs(LOG_DIR, exist_ok=True)

LAGOS_TZ = pytz.timezone("Africa/Lagos")


def _setup_logger() -> logging.Logger:
    now = datetime.now(LAGOS_TZ)
    log_file = os.path.join(LOG_DIR, f"pipeline_{now.strftime('%Y%m%d')}.log")
    logger = logging.getLogger("lti_pipeline")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


async def run_pipeline() -> dict | None:
    logger = _setup_logger()
    now    = datetime.now(LAGOS_TZ)
    logger.info("Pipeline starting — %s", now.isoformat())

    # ── 1. Collect all data concurrently ──────────────────────────────────────
    weather_data, articles, tg_posts = await asyncio.gather(
        _safe(fetch_weather, logger, "weather"),
        _safe(scrape_all,    logger, "scraper"),
        _safe(fetch_trigify_posts, logger, "trigify"),
    )

    weather_data = weather_data or {
        "precip_sum_mm": 0.0, "precip_hours": 0, "weather_code": 0,
        "condition_label": "Unknown", "season": "dry", "season_label": "Unknown", "month": now.month,
    }
    articles  = articles  or []
    tg_posts  = tg_posts  or []

    logger.info(
        "Collected: weather=%s, articles=%d, tg_posts=%d",
        weather_data.get("condition_label"), len(articles), len(tg_posts),
    )

    # ── 2. Extract signals ────────────────────────────────────────────────────
    signals = extract_signals(articles, tg_posts)
    logger.info("Signals found: %d", len(signals))

    # ── 3. Score ──────────────────────────────────────────────────────────────
    day_name = now.strftime("%A").lower()
    score_result = full_score(
        day          = day_name,
        hour         = now.hour,
        precip_hours = weather_data["precip_hours"],
        precip_sum_mm= weather_data["precip_sum_mm"],
        month        = weather_data["month"],
        signals      = signals,
    )
    logger.info(
        "Score: %d (%s) | base=%d weather_mod=%d signal_mod=%d",
        score_result["final_score"], score_result["level"],
        score_result["base_score"], score_result["weather_modifier"], score_result["signal_modifier"],
    )

    # ── 4. Flood zones ────────────────────────────────────────────────────────
    flood_zones = assess_flood_zones(
        precip_sum_mm = weather_data["precip_sum_mm"],
        precip_hours  = weather_data["precip_hours"],
        month         = weather_data["month"],
    )
    logger.info("Flood zones at risk: %d", len(flood_zones))

    # ── 5. Generate narrative ─────────────────────────────────────────────────
    date_label = now.strftime("%A, %B %-d")
    period     = "morning" if now.hour < 12 else "evening"
    narrator_ctx = {
        "day_of_week":      day_name,
        "date_label":       date_label,
        "period":           period,
        "run_time_label":   now.strftime("%-I:%M %p WAT"),
        "level":            score_result["level"],
        "score":            score_result["final_score"],
        "base_score":       score_result["base_score"],
        "weather_modifier": score_result["weather_modifier"],
        "signal_modifier":  score_result["signal_modifier"],
        "signal_count":     len([s for s in signals if not s.get("error")]),
        "precip_sum_mm":    weather_data["precip_sum_mm"],
        "precip_hours":     weather_data["precip_hours"],
        "condition_label":  weather_data["condition_label"],
        "season_label":     weather_data["season_label"],
        "flood_zones":      flood_zones,
        "signal_lines":     signals_to_text(signals),
    }

    narrative, used_fallback = await _safe(
        lambda: generate_narrative(narrator_ctx), logger, "narrator"
    ) or (None, True)

    if narrative is None:
        from narrator import get_fallback_narrative
        narrative    = get_fallback_narrative(score_result["level"], period)
        used_fallback = True

    logger.info("Narrative ready (fallback=%s): %.80s...", used_fallback, narrative)

    # ── 6. Build areas_to_watch ───────────────────────────────────────────────
    areas = _build_areas(score_result["level"], signals, flood_zones)

    # ── 7. Assemble today.json ────────────────────────────────────────────────
    sources_attempted = ["open_meteo", "pulse_nigeria", "vanguard", "trigify_keywords", "trigify_lagostraffic961"]
    sources_succeeded = []
    if weather_data.get("condition_label") != "Unknown":
        sources_succeeded.append("open_meteo")
    for a in articles:
        if not a.get("error") and a["source"] not in sources_succeeded:
            sources_succeeded.append(a["source"])
    for p in tg_posts:
        if not p.get("error"):
            for sid in ("trigify_keywords", "trigify_lagostraffic961"):
                if sid not in sources_succeeded:
                    sources_succeeded.append(sid)
            break

    today = {
        "schema_version": "1.0",
        "generated_at":   now.isoformat(),
        "date_label":     date_label,
        "day_of_week":    day_name,
        "traffic": {
            "score":     score_result["final_score"],
            "level":     score_result["level"],
            "hex_color": score_result["hex_color"],
            "narrative": narrative,
        },
        "scoring_breakdown": {
            "base_score":       score_result["base_score"],
            "weather_modifier": score_result["weather_modifier"],
            "signal_modifier":  score_result["signal_modifier"],
            "final_score":      score_result["final_score"],
            "capped_at_10":     score_result.get("capped_at_10", False),
        },
        "areas_to_watch": areas,
        "weather": {
            "precip_sum_mm":   weather_data["precip_sum_mm"],
            "precip_hours":    weather_data["precip_hours"],
            "weather_code":    weather_data.get("weather_code", 0),
            "condition_label": weather_data["condition_label"],
            "season":          weather_data["season"],
            "season_label":    weather_data["season_label"],
        },
        "flood_zones": flood_zones,
        "signals":     [s for s in signals if not s.get("error")][:10],
        "meta": {
            "pipeline_version":    "1.0",
            "sources_attempted":   sources_attempted,
            "sources_succeeded":   sources_succeeded,
            "narrator_used_fallback": used_fallback,
            "is_stale":            False,
            "last_successful_run": now.isoformat(),
        },
    }

    # ── 8. Persist ────────────────────────────────────────────────────────────
    write_today(today)
    append_history(today)
    logger.info("today.json written")

    # ── 9. Telegram ───────────────────────────────────────────────────────────
    tg_ok = await _safe(lambda: send_alert(today), logger, "telegram") or False
    logger.info("Telegram delivery: %s", "OK" if tg_ok else "FAILED")

    logger.info("Pipeline complete")
    return today


def _build_areas(level: str, signals: list[dict], flood_zones: list[dict]) -> list[str]:
    """
    Build areas_to_watch list. Signal-derived routes first, then flood-zone areas,
    then default high-traffic corridors for the score level.
    """
    areas: list[str] = []
    seen: set[str]   = set()

    # From confirmed signals
    for s in signals:
        if s.get("severity") == "HIGH" and s.get("affected_route") and not s.get("error"):
            route = s["affected_route"]
            if route not in seen and "multiple" not in route:
                areas.append(route)
                seen.add(route)

    # From flood zones (tier 1 first)
    for z in flood_zones:
        area = z["area"]
        if area not in seen:
            areas.append(z["name"].split("(")[0].strip())
            seen.add(area)

    # Default corridors by level
    defaults = {
        "Gridlock": ["Third Mainland Bridge", "Lekki-Epe Expressway (Sangotedo-Ajah)", "Oshodi-Apapa Expressway", "Ikorodu Road"],
        "Severe":   ["Third Mainland Bridge", "Lekki-Epe Expressway", "Oshodi-Apapa Expressway"],
        "Heavy":    ["Third Mainland Bridge", "Lekki-Epe Expressway", "Ikorodu Road"],
        "Moderate": ["Third Mainland Bridge", "Lagos Island corridors"],
        "Light":    [],
    }
    for route in defaults.get(level, []):
        if route not in seen and len(areas) < 5:
            areas.append(route)
            seen.add(route)

    return areas[:5]


async def _safe(coro_fn, logger: logging.Logger, name: str):
    try:
        result = coro_fn()
        if asyncio.iscoroutine(result):
            return await result
        return result
    except Exception as exc:
        logger.warning("%s failed: %s", name, exc)
        return None


if __name__ == "__main__":
    asyncio.run(run_pipeline())
