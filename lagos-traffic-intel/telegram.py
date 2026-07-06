"""
Telegram delivery and subscriber count.
"""

import httpx
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL

TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _format_message(today: dict) -> str:
    traffic  = today.get("traffic", {})
    level    = traffic.get("level", "Unknown")
    date_lbl = today.get("date_label", "")
    narrative = traffic.get("narrative", "")
    flood_zones = today.get("flood_zones", [])

    lines = [f"Lagos Traffic Intel — {date_lbl}", "", narrative]

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
    text = _format_message(today)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL, "text": text},
        )
        data = resp.json()
        return data.get("ok", False)


async def get_subscriber_count() -> int | None:
    """Returns channel member count, or None on failure."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{TG_API}/getChatMemberCount",
                params={"chat_id": TELEGRAM_CHANNEL},
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("result", 0)
        except Exception:
            pass
    return None
