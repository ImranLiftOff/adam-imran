"""
Generates the traffic narrative via Claude API.
Claude receives the deterministic score as an input — it only writes, never decides.
Falls back to level-based templates if the API call fails.
"""

import anthropic
from config import ANTHROPIC_API_KEY, DAY_CONTEXT
from signals import signals_to_text

FALLBACK_NARRATIVES: dict[str, str] = {
    "Light":
        "Conditions are light across Lagos this morning. Most major routes are moving "
        "freely. Allow standard travel time.",
    "Moderate":
        "Moderate traffic on Lagos roads this morning. Allow extra time on Third Mainland "
        "Bridge, Lekki-Epe Expressway, and Oshodi-Apapa. Standard rush hour density.",
    "Heavy":
        "Heavy traffic across Lagos this morning. Expect significant delays on Third "
        "Mainland Bridge, Lekki-Epe Expressway, and Oshodi-Apapa Expressway. Leave "
        "earlier than usual.",
    "Severe":
        "Severe conditions across Lagos this morning. All major corridors — Third Mainland "
        "Bridge, Lekki-Epe, Ikorodu Road, Oshodi-Apapa — are heavily congested. Plan for "
        "45–90 minute delays on the Island routes.",
    "Gridlock":
        "Gridlock across Lagos this morning. Third Mainland Bridge, Lekki-Epe Expressway, "
        "Oshodi-Apapa, and Ikorodu Road are all critically affected. Delay travel until "
        "mid-morning if possible.",
}

SYSTEM_PROMPT = (
    "You are the Lagos Traffic Intel narrator. The traffic score and level have been "
    "determined by a deterministic algorithm — you do not re-analyze or second-guess them. "
    "Your only job is to write clear, direct text that tells a Lagos commuter what that "
    "score means on the ground this morning."
)


def _build_user_prompt(ctx: dict) -> str:
    flood_lines = "\n".join(
        f"  • {z['name']} ({z['confidence']} confidence)"
        for z in ctx.get("flood_zones", [])
    ) or "  None — rainfall below flood thresholds"

    return f"""=== TODAY'S TRAFFIC BRIEF ===
Date: {ctx['day_of_week'].title()}, {ctx['date_label']} — 6:00 AM WAT
Traffic Level: {ctx['level']} ({ctx['score']}/10)

Scoring inputs:
- Base score ({ctx['day_of_week']} morning rush): {ctx['base_score']}/10
  ({DAY_CONTEXT.get(ctx['day_of_week'], '')})
- Weather modifier: +{ctx['weather_modifier']} ({ctx['precip_sum_mm']}mm rainfall over {ctx['precip_hours']} hours since midnight)
- Signal modifier: +{ctx['signal_modifier']} ({ctx['signal_count']} event(s) found in news/radio)

Rainfall context: {ctx['condition_label']} — {ctx['season_label']}

Flood zones at risk:
{flood_lines}

Events from news/radio:
{ctx['signal_lines']}

=== WRITE THE ADVISORY ===

Rules you must follow:
1. Open with one sentence stating the level and its main driver.
   If score >= 7 and no events were found, describe the expected baseline heavy conditions
   for this day and time. NEVER write "no disruptions" or "roads are clear" when score >= 7.
2. Write 2–3 bullet points naming specific Lagos roads. Use real names: Third Mainland Bridge,
   Eko Bridge, Lekki-Epe Expressway, Oshodi-Apapa Expressway, Ikorodu Road, CMS, VI, etc.
3. If flood zones are listed above, add one flood warning sentence at the end.
4. 150 words maximum. Plain text only — no markdown, no asterisks, no emojis, no hashtags.
5. Second person: "Expect...", "Avoid...", "Plan for..."
6. Do not mention the score number. Do not say "based on the data" or "according to signals."
7. Begin directly — no preamble, no "Here is the advisory:" opener.
"""


async def generate_narrative(ctx: dict) -> tuple[str, bool]:
    """
    Returns (narrative_text, used_fallback).
    ctx keys: day_of_week, date_label, level, score, base_score, weather_modifier,
              signal_modifier, signal_count, precip_sum_mm, precip_hours,
              condition_label, season_label, flood_zones, signal_lines
    """
    if not ANTHROPIC_API_KEY:
        return FALLBACK_NARRATIVES.get(ctx.get("level", "Moderate"), FALLBACK_NARRATIVES["Moderate"]), True

    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(ctx)}],
        )
        text = msg.content[0].text.strip()
        return text, False
    except Exception:
        fallback = FALLBACK_NARRATIVES.get(ctx.get("level", "Moderate"), FALLBACK_NARRATIVES["Moderate"])
        return fallback, True
