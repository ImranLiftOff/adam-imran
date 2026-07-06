"""
Extracts structured traffic events from raw article/post text.
Pattern-matched, no AI call — this keeps signal detection cheap and fast.
"""

import re

# (pattern, event_type, severity, affected_route_hint)
SIGNAL_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(r"convoy|presidential convoy|vip movement|presidential motorcade", re.I),
     "convoy", "HIGH", "multiple routes"),
    (re.compile(r"third mainland bridge.{0,30}(clos|shut|block|damag|crack|repai)", re.I),
     "bridge_closure", "HIGH", "Third Mainland Bridge"),
    (re.compile(r"eko bridge.{0,30}(clos|shut|block|damag|repai)", re.I),
     "bridge_closure", "HIGH", "Eko Bridge"),
    (re.compile(r"(carter|falomo|lekki ikoyi).{0,30}(clos|shut|block)", re.I),
     "bridge_closure", "HIGH", "Lekki-Ikoyi / Carter Bridge"),
    (re.compile(r"(road|highway|expressway).{0,30}(flood|submerge|underwater|inundat)", re.I),
     "flooding_confirmed", "HIGH", "flooded road"),
    (re.compile(r"(marathon|road race|governor.{0,15}procession|independence day parade)", re.I),
     "major_event", "HIGH", "multiple routes"),
    (re.compile(r"(fatal|multiple|serious).{0,20}accident.{0,30}(expressway|bridge|highway)", re.I),
     "accident", "HIGH", "expressway/bridge"),
    (re.compile(r"accident.{0,40}(third mainland|lekki|oshodi|ikorodu|apapa|vi )", re.I),
     "accident", "MEDIUM", "major corridor"),
    (re.compile(r"(road.{0,10}(repair|maintenance|construction|work).{0,30}(divert|lane))", re.I),
     "maintenance", "MEDIUM", "diverted route"),
    (re.compile(r"(fuel|petrol).{0,20}(scarcity|shortage).{0,30}(queue|traffic|gridlock)", re.I),
     "fuel_scarcity", "MEDIUM", "filling station corridors"),
]


def extract_signals(articles: list[dict], posts: list[dict]) -> list[dict]:
    """
    Combines articles (from scraper) and posts (from Trigify) into one text corpus,
    runs pattern matching, deduplicates by event type, returns signal list.
    """
    signals: list[dict] = []
    seen_types: set[str] = set()

    all_texts: list[tuple[str, str, str]] = []
    for a in articles:
        if not a.get("error"):
            text = f"{a.get('title', '')} {a.get('snippet', '')}"
            all_texts.append((text, a.get("source", "news"), a.get("url", "")))
    for p in posts:
        text = p.get("text", "") or p.get("content", "") or str(p)
        all_texts.append((text, "trigify", p.get("url", "")))

    for text, source, url in all_texts:
        for pattern, event_type, severity, route_hint in SIGNAL_PATTERNS:
            if pattern.search(text):
                key = f"{event_type}:{route_hint}"
                if key not in seen_types:
                    seen_types.add(key)
                    signals.append({
                        "type":              event_type,
                        "severity":          severity,
                        "description":       _clean_description(text[:200]),
                        "affected_route":    route_hint,
                        "source":            source,
                        "url":               url,
                    })

    # HIGH signals first
    signals.sort(key=lambda s: (0 if s["severity"] == "HIGH" else 1))
    return signals


def _clean_description(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:200]


def signals_to_text(signals: list[dict]) -> str:
    """Formats signal list for injection into narrator prompt."""
    if not signals:
        return "No specific events found in today's news or radio monitoring."
    lines = []
    for s in signals[:5]:  # cap at 5 for prompt length
        lines.append(f"- [{s['severity']}] {s['type'].replace('_', ' ').title()}: {s['description']} (via {s['source']})")
    return "\n".join(lines)
