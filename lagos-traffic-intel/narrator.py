"""
Generates the traffic narrative via Claude API.
Claude receives the deterministic score as an input — it only writes, never decides.
Falls back to level-based templates if the API call fails.
"""

import re

import anthropic
from config import ANTHROPIC_API_KEY, DAY_CONTEXT
from signals import signals_to_text

# {period} is filled in with "morning" or "evening" at render time, so the
# same templates work for both daily runs.
FALLBACK_NARRATIVES: dict[str, str] = {
    "Light":
        "Conditions are light across Lagos this {period}. Most major routes are moving "
        "freely. Allow standard travel time.",
    "Moderate":
        "Moderate traffic on Lagos roads this {period}. Allow extra time on Third Mainland "
        "Bridge, Lekki-Epe Expressway, and Oshodi-Apapa. Standard rush hour density.",
    "Heavy":
        "Heavy traffic across Lagos this {period}. Expect significant delays on Third "
        "Mainland Bridge, Lekki-Epe Expressway, and Oshodi-Apapa Expressway. Leave "
        "earlier than usual.",
    "Severe":
        "Severe conditions across Lagos this {period}. All major corridors (Third Mainland "
        "Bridge, Lekki-Epe, Ikorodu Road, Oshodi-Apapa) are heavily congested. Plan for "
        "45-90 minute delays on the Island routes.",
    "Gridlock":
        "Gridlock across Lagos this {period}. Third Mainland Bridge, Lekki-Epe Expressway, "
        "Oshodi-Apapa, and Ikorodu Road are all critically affected. Delay travel until "
        "conditions ease if possible.",
}

SYSTEM_PROMPT = (
    "You are the Lagos Traffic Intel narrator. The traffic score and level have been "
    "determined by a deterministic algorithm; you do not re-analyze or second-guess them. "
    "Your only job is to write clear, direct text that tells a Lagos commuter what that "
    "score means on the ground right now. Never use em dashes or en dashes anywhere in "
    "your writing, as a separator or otherwise; use commas, periods, or plain hyphens instead."
)


def _sanitize(text: str) -> str:
    """Strip em/en dashes regardless of what the model or a template produced."""
    text = text.replace("—", "-").replace("–", "-")
    return re.sub(r" {2,}", " ", text)


def get_fallback_narrative(level: str, period: str = "morning") -> str:
    template = FALLBACK_NARRATIVES.get(level, FALLBACK_NARRATIVES["Moderate"])
    return _sanitize(template.format(period=period))


def _build_user_prompt(ctx: dict) -> str:
    period = ctx.get("period", "morning")
    flood_lines = "\n".join(
        f"  - {z['name']} ({z['confidence']} confidence)"
        for z in ctx.get("flood_zones", [])
    ) or "  None - rainfall below flood thresholds"

    return f"""=== TODAY'S TRAFFIC BRIEF ===
Date: {ctx['day_of_week'].title()}, {ctx['date_label']} - {ctx.get('run_time_label', '')} ({period} update)
Traffic Level: {ctx['level']} ({ctx['score']}/10)

Scoring inputs:
- Base score ({ctx['day_of_week']} {period} rush): {ctx['base_score']}/10
  ({DAY_CONTEXT.get(ctx['day_of_week'], '')})
- Weather modifier: +{ctx['weather_modifier']} ({ctx['precip_sum_mm']}mm rainfall over {ctx['precip_hours']} hours since midnight)
- Signal modifier: +{ctx['signal_modifier']} ({ctx['signal_count']} event(s) found in news/radio)

Rainfall context: {ctx['condition_label']}, {ctx['season_label']}

Flood zones at risk:
{flood_lines}

Events from news/radio:
{ctx['signal_lines']}

=== WRITE THE ADVISORY ===

Rules you must follow:
1. Open with one sentence stating the level and its main driver.
   If score >= 7 and no events were found, describe the expected baseline heavy conditions
   for this day and time. NEVER write "no disruptions" or "roads are clear" when score >= 7.
2. Write 2-3 bullet points naming specific Lagos roads. Use real names: Third Mainland Bridge,
   Eko Bridge, Lekki-Epe Expressway, Oshodi-Apapa Expressway, Ikorodu Road, CMS, VI, etc.
3. If flood zones are listed above, add one flood warning sentence at the end.
4. 150 words maximum. Plain text only - no markdown, no asterisks, no emojis, no hashtags.
5. Second person: "Expect...", "Avoid...", "Plan for..."
6. This is the {period} update - write for a commuter checking this in the {period}, not always "this morning".
7. Do not mention the score number. Do not say "based on the data" or "according to signals."
8. Do not use em dashes (—) or en dashes (–) anywhere, including as a separator. Use commas,
   periods, or plain hyphens (-) only.
9. Begin directly - no preamble, no "Here is the advisory:" opener.
"""


async def generate_narrative(ctx: dict) -> tuple[str, bool]:
    """
    Returns (narrative_text, used_fallback).
    ctx keys: day_of_week, date_label, level, score, base_score, weather_modifier,
              signal_modifier, signal_count, precip_sum_mm, precip_hours,
              condition_label, season_label, flood_zones, signal_lines, period,
              run_time_label
    """
    level  = ctx.get("level", "Moderate")
    period = ctx.get("period", "morning")

    if not ANTHROPIC_API_KEY:
        return get_fallback_narrative(level, period), True

    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(ctx)}],
        )
        text = _sanitize(msg.content[0].text.strip())
        return text, False
    except Exception:
        return get_fallback_narrative(level, period), True
