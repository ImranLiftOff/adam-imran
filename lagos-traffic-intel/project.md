# Lagos Traffic Intel

Daily 6am WAT traffic intelligence alert for Lagos. Scrapes Pulse Nigeria, Vanguard, and Twitter/X via Trigify, analyzes with Claude, and sends a formatted message to a Telegram channel.

---

## What It Does

Monitors for disruptions that navigation apps don't know about:
- Presidential / VIP convoys
- Road and bridge closures (Third Mainland, Eko, Carter, Falomo)
- Major events blocking routes (marathons, state functions)
- Flooding and accident-related closures

Also checks the last 6 hours of rainfall and appends a flood zone warning if rain has been ongoing for 2+ hours.

---

## Clay Table

**Table:** Lagos Traffic Intel — Sources & Alert
**Workspace:** 394038 (adam@patrickburns.co)

```
TABLE_ID = 't_0thfur0SssNPNNA6TXW'
VIEW_ID  = 'gv_0thfur1gr2jr6oquQsS'
RECORD   = 'r_0thfur14Mnp2CW2Tu4k'   # single persistent row, re-enriched daily
```

### Column Map

| Name | ID | Type | Notes |
|---|---|---|---|
| Pulse Nigeria Raw | `f_0thfutao7WwpxyxzjnM` | action | scrape-website → pulse.ng/news/local |
| Vanguard Raw | `f_0thfutbovKrA5wzA97Y` | action | scrape-website → vanguardngr.com/category/metro-news |
| Twitter — Lagos Traffic | `f_0thfuyd73VdM6BN9f5p` | action | Trigify keyword search |
| Twitter — @lagostraffic961 | `f_0thfuyeFebvbzj9Kbre` | action | Trigify profile monitoring (@lagostraffic961 = Lagos Traffic Radio 96.1FM) |
| Combined Raw Content | `f_0thfuyfBthTWhMqY7zm` | formula | concatenates all 4 sources with section headers |
| AI Analysis | `f_0thhlt6CxszYU8NPij6` | action | use-ai (Claude Sonnet 4.6) — returns plain text (STATUS/REASON/AREAS TO WATCH) |
| Formatted Message | `f_0thfuyjHVADVZ7V3f3q` | formula | builds final Telegram message from AI JSON + weather |
| Telegram Send | `f_0thfuykKodWBmDfoJgb` | action | POST to Telegram bot API |
| Send Status | `f_0thfuymJcvz76HA7h2e` | formula | extracts ok/description from Telegram response |
| Weather — Lagos | `f_0thfyio73SrTsYffAHJ` | action | Open-Meteo free API, no key needed |

---

## Trigify Searches

```
Lagos Traffic Keywords:  d1da38c4-36ab-4448-94a8-c694245893de
@lagostraffic961 profile: e07ed569-1bed-4174-9864-8c4dc51043e1
```

---

## Telegram

```
Bot token: 8782744685:AAF5Rw4KeggrZCWsTRYJjDLdsHzooDpQ1ZU
Channel ID: -1004333163645  (Lagos Traffic Intel channel — friends subscribe here)
```

Bot is admin of the channel with Post Messages permission. New subscribers join the channel; the bot posts at 6am WAT daily.

---

## Schedule

Runs daily at **6:00 AM WAT (Africa/Lagos)**, starting 2026-07-01.

Run order:
1. Weather — Lagos
2. Pulse Nigeria Raw
3. Vanguard Raw
4. Twitter — Lagos Traffic
5. Twitter — @lagostraffic961
6. AI Analysis
7. Telegram Send

Formula columns (Combined Raw Content, Formatted Message, Send Status) are computed automatically and not in the schedule.

---

## AI Analysis Output Format

The AI Analysis column returns structured JSON (Clay detected the schema from the prompt):

```json
{
  "disruptions": [
    {
      "typeOfDisruption": "Flooding",
      "affectedRouteOrArea": "Lagos Island, Third Mainland approach...",
      "expectedTimeOrDate": "Today, 30th June 2026 — ongoing",
      "severity": "HIGH"
    }
  ],
  "noMajorDisruptionsDetected": false,
  "totalCreditsCharged": 1
}
```

The Formatted Message formula extracts fields via `?.disruptions[0]?.severity` etc. Supports up to 4 disruptions (indices 0–3).

---

## Weather API

```
https://api.open-meteo.com/v1/forecast?latitude=6.5244&longitude=3.3792
  &current=precipitation,weather_code
  &hourly=precipitation
  &daily=precipitation_sum,precipitation_probability_max
  &timezone=Africa%2FLagos
  &forecast_days=1
  &past_hours=6
```

**Two-tier flood trigger** (sum of past 6 hours of precipitation):
- `< 0.5mm` → no warning
- `0.5–3.5mm` → Tier 2 only (4 main flood corridors)
- `≥ 3.5mm` → Tier 2 + Tier 1 (all 13 flood-prone areas)

Lagos rain is convective — use `precipitation` field, not `rain` (rain is always ~0 here).

---

## Flood Zones

Appended to the message when rain has been ongoing 2+ of the past 6 hours:

**Island & Bridges:** Eko Bridge inward CMS / Apongbon / Inner Marina · Ozumba Mbadiwe inward Bonny Camp · Law School to Kilimanjaro / Bonny Camp · Ikoyi–Obalende (Simpson Bridge to Dolphin / Osborne)

**Mainland:** Masha/Aguda–Doyin–Census–Adelabu corridor · Yaba – WAEC to St. Agnes · Ijaye Rd – Mobil Filling Station (Odo Eran / Oba Ogunji) · Jibowu–Yaba–Alagomeji–Adekunle–Oyingbo belt

**Outskirts:** Sangotedo – Alesh inward Ajah Under Bridge · Ketu – Iyana School inward Ile Ile / Ikosi Junction · Ojo – Franklass to Iyana Iba Flyover · Dopemu – Kwara/Jimoh Bus Stop · Alimosho – Jimoh Bus Stop inward Egbeda

---

## Sample Output

```
Lagos Traffic Intel — Tuesday, June 30

HIGH: Flooding
Lagos-wide — low-lying and flood-prone routes including Third Mainland Bridge
approach roads, Lagos Island, Lekki-Epe Expressway, Oshodi-Apapa Expressway
When: Today, 30th June 2026 — ongoing and throughout the day

⚠️ FLOOD RISK — Rain ongoing 2+ hrs

ISLAND & BRIDGES
• Eko Bridge inward CMS / Apongbon / Inner Marina
• Ozumba Mbadiwe inward Bonny Camp
• Law School to Kilimanjaro / Bonny Camp
• Ikoyi–Obalende (Simpson Bridge to Dolphin / Osborne)

MAINLAND
• Masha/Aguda–Doyin–Census–Adelabu corridor
• Yaba – WAEC to St. Agnes
• Ijaye Rd – Mobil Filling Station (Odo Eran / Oba Ogunji)
• Jibowu–Yaba–Alagomeji–Adekunle–Oyingbo belt

OUTSKIRTS
• Sangotedo – Alesh inward Ajah Under Bridge
• Ketu – Iyana School inward Ile Ile / Ikosi Junction
• Ojo – Franklass to Iyana Iba Flyover
• Dopemu – Kwara/Jimoh Bus Stop
• Alimosho – Jimoh Bus Stop inward Egbeda

Stay safe out there.
```

---

## Clay Formula Notes

- Date: `moment()?.format("dddd, MMMM D")` — Clay uses moment.js, not Excel-style `Text(Today(), ...)`
- Null check arrays: `If({{AI_COL}}?.disruptions[0], ..., "")` — `IsEmpty()` and `Length()` are invalid in Clay
- Unicode in formulas: use literal characters (—, •, ⚠️) directly, not `—` escape sequences
- String coercion: `String(val || "fallback")` for nullable fields

---

## Packages Used

```
SCRAPE_PKG  = '4299091f-3cd3-4d68-b198-0143575f471d'   # scrape-website, http-api-v2
AI_PKG      = '67ba01e9-1898-4e7d-afe7-7ebe24819a57'   # use-ai
ANTHROPIC_AUTH = 'aa_D5TnW9yPFfQx'                     # Clay-connected Anthropic account
```

Do NOT use `aa_0t9heaufWM4Ay3wd6rr` (Clay-managed Trigify) — billed per call. Trigify runs on its own platform using the API key in `.env`.
