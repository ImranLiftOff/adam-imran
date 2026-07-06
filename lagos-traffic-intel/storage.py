import json
import os
from datetime import datetime, timezone

from config import TODAY_JSON, HISTORY_JSON, DATA_DIR

MAX_HISTORY = 30


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def write_today(data: dict) -> None:
    """Atomic write — writes to .tmp then renames so the live file is never partial."""
    _ensure_dirs()
    tmp = TODAY_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TODAY_JSON)


def read_today() -> dict | None:
    try:
        with open(TODAY_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def append_history(data: dict) -> None:
    """Keeps last MAX_HISTORY entries. Writes daily even if today already exists."""
    _ensure_dirs()
    history: list[dict] = []
    try:
        with open(HISTORY_JSON, encoding="utf-8") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Replace today's entry if already present, else append
    today_label = data.get("date_label", "")
    history = [e for e in history if e.get("date_label") != today_label]
    history.append({
        "date_label":   data.get("date_label"),
        "generated_at": data.get("generated_at"),
        "score":        data.get("traffic", {}).get("score"),
        "level":        data.get("traffic", {}).get("level"),
        "hex_color":    data.get("traffic", {}).get("hex_color"),
        "precip_mm":    data.get("weather", {}).get("precip_sum_mm"),
    })
    history = history[-MAX_HISTORY:]

    tmp = HISTORY_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_JSON)


def read_history() -> list[dict]:
    try:
        with open(HISTORY_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def mark_stale(today_data: dict | None) -> bool:
    """True if last run was more than 26 hours ago."""
    if not today_data:
        return True
    gen = today_data.get("generated_at", "")
    try:
        ts = datetime.fromisoformat(gen)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        return age_hours > 26
    except (ValueError, TypeError):
        return True
