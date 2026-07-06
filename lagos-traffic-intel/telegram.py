"""
Telegram delivery and subscriber count.
"""

import json
import os
import re
from datetime import datetime

import httpx
import pytz

from config import DATA_DIR, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
LAGOS_TZ = pytz.timezone("Africa/Lagos")
SUBSCRIBER_BASELINE_FILE = os.path.join(DATA_DIR, "subscriber_baseline.json")


def _sanitize(text: str) -> str:
    """Strip em/en dashes before anything is sent to Telegram, regardless of source."""
    text = text.replace("—", "-").replace("–", "-")
    return re.sub(r" {2,}", " ", text)


def _format_message(today: dict) -> str:
    traffic  = today.get("traffic", {})
    level    = traffic.get("level", "Unknown")
    date_lbl = today.get("date_label", "")
    narrative = traffic.get("narrative", "")
    flood_zones = today.get("flood_zones", [])

    lines = [f"Lagos Traffic Intel - {date_lbl}", "", narrative]

    if flood_zones:
        lines.append("")
        lines.append("⚠ FLOOD ADVISORY")
        for z in flood_zones[:5]:
            lines.append(f"• {z['name']} ({z['confidence']})")

    lines.append("")
    lines.append("lagostraffic.ng")  # placeholder — update when domain is live
    return "\n".join(lines)


async def send_alert(today: dict) -> bool:
    """Posts the formatted alert to the Telegram channel. Returns True on success."""
    text = _sanitize(_format_message(today))
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL, "text": text},
        )
        data = resp.json()
        return data.get("ok", False)


def _load_baseline() -> dict | None:
    try:
        with open(SUBSCRIBER_BASELINE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_baseline(date_str: str, count: int) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = SUBSCRIBER_BASELINE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"date": date_str, "count": count}, f)
    os.replace(tmp, SUBSCRIBER_BASELINE_FILE)


async def get_subscriber_count() -> dict | None:
    """
    Returns {"total": N, "new_today": M}, or None on failure.

    "new_today" is the total member count minus whatever the total was the
    first time we checked today (Lagos time) — Telegram's Bot API has no
    join-event feed, so a daily baseline snapshot is the only way to derive
    a same-day delta from getChatMemberCount alone.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{TG_API}/getChatMemberCount",
                params={"chat_id": TELEGRAM_CHANNEL},
            )
            data = resp.json()
            if not data.get("ok"):
                return None
            total = data.get("result", 0)
        except Exception:
            return None

    today_str = datetime.now(LAGOS_TZ).strftime("%Y-%m-%d")
    baseline = _load_baseline()
    if not baseline or baseline.get("date") != today_str:
        baseline = {"date": today_str, "count": total}
        _save_baseline(today_str, total)

    new_today = max(0, total - baseline["count"])
    return {"total": total, "new_today": new_today}
