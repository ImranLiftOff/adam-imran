# Lagos Traffic Intel

Live Lagos traffic intelligence, three times daily (6:30 AM, 4:00 PM, 8:00 PM WAT), on a public website and a Telegram channel.

- **Site:** https://lagos-traffic-intel-production.up.railway.app
- **Telegram:** channel ID `-1004333163645` ("friends subscribe here")
- **Repo:** `adamimranza-spec/adam-imran` on GitHub, this project lives in the `lagos-traffic-intel/` subdirectory of that personal monorepo

This file describes the system as it actually runs today. `spec.md` (the original Clay/WhatsApp concept doc from before anything was built) has been removed — everything in it was superseded.

---

## What It Does

Scores Lagos traffic 1–10 for right now, using a deterministic model (day of week, hour, rainfall, real incident reports), then has Claude write a short, grounded, honest advisory around that score — never inventing a specific road claim that isn't backed by real data. Narrows in on named corridors (Third Mainland Bridge, Lekki-Epe, Oshodi-Apapa, etc.) rather than claiming the whole city is affected when it isn't.

Also carries a flood-risk model from rainfall data, and shows subscriber counts / a "share to Telegram" flow on the site.

---

## Architecture

Python, FastAPI, deployed on Railway. No Clay involved in the live system (Clay was the original prototype approach in `project.md`'s first version; abandoned).

| File | Role |
|---|---|
| `server.py` | FastAPI app, entry point. APScheduler runs the pipeline at 6:30/16:00/20:00 WAT. Routes: `/health`, `/run`, `/webhook/trigify-post`, `/api/today`, `/api/history`, `/api/subscribers`, `/api/embed`, `/` (serves the frontend). |
| `main.py` | Pipeline orchestrator: fetch → dedupe → score → generate narrative → persist → send to Telegram. Runnable standalone (`python main.py [--dry-run]`). |
| `config.py` | All API keys, the day/hour → base-score matrix, flood zone definitions, file paths (volume-aware), tunable constants. |
| `trigify.py` | Polls the two saved Trigify searches (`GET /searches/{id}/results`). This poll is capped at Trigify's own **daily** re-crawl frequency — see "Trigify Setup" below for why the real-time webhook exists alongside it. |
| `signals.py` | Turns raw posts into structured signals (regex pattern match) and corridor reports (parses `@lagostraffic961`'s structured "TRAFFIC UPDATE FROM X" format). Filters: drops replies (`@user...`, usually reactive/sarcastic, not reports), drops anything older than `MAX_POST_AGE_HOURS` (20h), decodes HTML entities. |
| `scorer.py` | Pure deterministic scoring: base (day+hour) + weather modifier + signal modifier + corridor modifier (can push the score down as well as up when real reports are mostly clear), capped 1–10, mapped to a level/color. |
| `weather.py` | Open-Meteo fetch (no key needed), past 6h rainfall. |
| `flood.py` | Flood zone risk assessment from the rainfall data, tiered by historical flood-prone area. |
| `narrator.py` | Calls Claude (`claude-sonnet-4-6`) to write the advisory from the score + real corridor reports/signals. Deterministic, grounded fallback template if the API call fails. |
| `storage.py` | Reads/writes `today.json`, `history.json`, `seen_posts.json` (dedup registry), `live_posts.json` (real-time feed). All under `DATA_DIR`, which lives on the persistent volume in production. |
| `telegram.py` | Formats and sends the Telegram message, tracks subscriber count. |
| `static/index.html` | Frontend. Polls `/api/today` every 5 minutes. Has an honest fallback state (not fabricated-looking) for when the API can't be reached. |

---

## Trigify Setup

Two saved searches:

```
Lagos Traffic Keywords:   d1da38c4-36ab-4448-94a8-c694245893de   (OR-only: "Third Mainland Bridge", "Eko Bridge closed", "Lagos marathon", "Lagos traffic alert" — no AND/NOT filtering)
@lagostraffic961 profile: e07ed569-1bed-4174-9864-8c4dc51043e1   (Lagos Traffic Radio 96.1FM — the actual ground-truth source)
```

**Known issue, not yet fixed:** the Keywords search has zero AND/NOT filtering, so it's mostly noise (jokes, unrelated chatter mentioning "Third Mainland Bridge") rather than real reports — confirmed live 2026-07-09: 30 posts fetched, 0 became corridor reports, its one "signal" was a sarcastic reply that got pattern-matched as a real accident before the reply-filter was added. Needs proper boolean retuning (per the trigify skill's own guidance, this needs the user's input on acceptable tradeoffs, not a guess).

**Both searches are capped at `frequency: DAILY`** — confirmed via `trigify search get`, this is the most frequent re-crawl tier the platform offers for a saved search. Since the pipeline runs 3x/day, polling alone would mean stale data for most runs.

**Fix: real-time workflows.** Two published Trigify workflows (one per search, `New Post` trigger) forward every new matching post the moment Trigify detects it:

1. A `generic_agent` step (model `openai/gpt-5-mini`) reproduces the post text verbatim but replaces every newline with the literal marker `~n~`.
   - *Why:* Trigify's `http_request` action fails (opaque, undebuggable platform error) the instant the resolved body/headers/queryParams string contains ANY raw control character — not just invalid JSON. Confirmed via isolated testing: static body with no templating worked; the same shape with a real (newline-containing) tweet failed; a hand-built `\x01` delimiter with no newlines at all also failed. No template filter exists to pre-escape a referenced field, and no deterministic transform action exists in Trigify's action set — the AI step is the only available workaround. Costs ~$0.003–0.005/post.
2. An `http_request` step POSTs to `/webhook/trigify-post` with body `postUrl|authorUrl|datePosted|source|<flattened text>` (pipe-delimited, text last so its content can't break the split), header `X-Webhook-Secret` matching `TRIGIFY_WEBHOOK_SECRET`.

The endpoint verifies the secret, splits on `|` (maxsplit 4), restores real newlines from the `~n~` marker, and appends to `live_posts.json`. `main.py` merges this real-time feed with the daily poll every run; `filter_new_posts` (dedup by URL) means a post arriving via both paths only counts once.

**Workflow IDs:** `@lagostraffic961` → `YeEvtn5kfyJO7zel6rNRi`, Keywords → `eXN1QiO4r3QG-iOGc7cIq`. Both `PUBLISHED`, `enabled: true`.

**CLI gotcha:** `trigify workflow update` / `workflow draft upsert` + `publish` silently clears the workflow's search attachment (`social_saved_search_id` → null) — no CLI flag exists to set it outside of `create`. If a workflow ever needs its body/prompt changed again, `delete` + `create` fresh (with `--search-id` and `--status PUBLISHED --enabled true` in the same call) rather than `update`, and verify `social_saved_search_id` with a fresh `workflow get` afterward.

---

## Schedule

Runs at **6:30 AM, 4:00 PM, and 8:00 PM WAT** (APScheduler in `server.py`, `lifespan`). Longest gap between runs is ~10h30m (20:00 → 6:30), which is what `STALE_THRESHOLD_HOURS` (12h) and `SEEN_POSTS_RETENTION_HOURS` (30h) are calibrated against.

The scoring matrix (`config.py` `BASE_SCORE_MATRIX`) already covers all 24 hours for every day — adding the third run required no scoring changes, just the new `add_job` call plus recalibrating the stale threshold.

---

## Infrastructure

- **Railway project:** `harmonious-kindness` (workspace `adamimranza-spec`), service `lagos-traffic-intel`
- **GitHub connection:** `adamimranza-spec/adam-imran`, Root Directory `lagos-traffic-intel`, branch `main` — auto-deploys on push. (This was broken for most of 2026-07-09: the service had no GitHub source connected at all, running a stale manual deploy; reconnecting required transferring the repo from a different GitHub account since Railway's session was authenticated as `adamimranza-spec`.)
- **Persistent volume:** `lagos-traffic-intel-volume`, 500MB, mounted at `/data`. Added 2026-07-09 — before this, Railway's container filesystem was wiped on every deploy/restart, resetting `today.json`/`seen_posts.json`/`live_posts.json` to empty each time. `config.py`'s `DATA_DIR` uses `RAILWAY_VOLUME_MOUNT_PATH` when present, falls back to a local relative path otherwise.
- **`/health`** returns a `version` field (short commit SHA, via `RAILWAY_GIT_COMMIT_SHA` or local `git rev-parse`) specifically so a deploy can be confirmed read-only, without ever needing to hit `/run`.
- **Env vars required** (Railway dashboard + local `.env`, never committed): `ANTHROPIC_API_KEY`, `TRIGIFY_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL`, `TRIGIFY_WEBHOOK_SECRET` (must match the value baked into both published Trigify workflows' `http_request` headers).

---

## Testing

`python main.py --dry-run` (local) or `POST /run?dry_run=true` (deployed) runs the full pipeline and writes `today.json` as normal, but skips the Telegram send. Always use this for testing against the live server — a 2026-07-08 incident sent ~17 real messages to real subscribers when a polling loop hit `/run` repeatedly on code that predated `dry_run` support.

Trigify workflow changes must be tested with a **real** post pulled from the search's actual results (`trigify search results --id ...`), never fabricated text — per the trigify skill's own rule, and because a fabricated post can't reveal real platform quirks (like the control-character bug above).

---

## Positioning

Kept from the original spec, still true regardless of implementation: the hook when talking about this project is not "I built a traffic app" — it's "Google Maps tells you about traffic. It does not tell you the president is coming to Lagos tomorrow, or that today's corridor reports say a specific bridge is confirmed clear when the model alone would've scored it Gridlock." The differentiator is grounded, honest reporting, not another live-traffic layer.
