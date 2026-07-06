"""
Scrapes headlines and snippets from Pulse Nigeria and Vanguard.
Returns article dicts for signals.py to process.
"""

import httpx
from bs4 import BeautifulSoup

SOURCES = [
    {
        "id":     "pulse_nigeria",
        "name":   "Pulse Nigeria",
        "url":    "https://www.pulse.ng/news/local",
        "item_selectors":    ["article", "div.item__wrap", "div.article-item"],
        "title_selectors":   ["h2", "h3", "h4"],
        "snippet_selectors": ["p", "div.item__excerpt"],
    },
    {
        "id":     "vanguard",
        "name":   "Vanguard",
        "url":    "https://www.vanguardngr.com/category/metro-news/",
        "item_selectors":    ["article", "div.jeg_post", "h2.jeg_post_title"],
        "title_selectors":   ["h2", "h3"],
        "snippet_selectors": ["p", "div.jeg_post_excerpt p"],
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

MAX_ARTICLES = 15


def _extract_articles(html: str, source: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles: list[dict] = []

    # Try each item selector until we get results
    items = []
    for sel in source["item_selectors"]:
        items = soup.select(sel)
        if items:
            break

    if not items:
        # Fallback: grab all h2/h3 tags as minimal signal
        items = soup.find_all(["h2", "h3"])

    for item in items[:MAX_ARTICLES]:
        title = ""
        for tsel in source["title_selectors"]:
            tag = item.select_one(tsel) if hasattr(item, "select_one") else None
            if not tag and item.name in ("h2", "h3", "h4"):
                tag = item
            if tag:
                title = tag.get_text(strip=True)
                break

        if not title:
            title = item.get_text(separator=" ", strip=True)[:120]

        snippet = ""
        for ssel in source["snippet_selectors"]:
            stag = item.select_one(ssel) if hasattr(item, "select_one") else None
            if stag:
                snippet = stag.get_text(strip=True)[:300]
                break

        # Skip nav/boilerplate items
        if len(title) < 10 or title.lower() in ("home", "news", "metro", "local"):
            continue

        # Link
        link_tag = item.find("a") if hasattr(item, "find") else None
        url = link_tag["href"] if link_tag and link_tag.get("href") else ""
        if url and not url.startswith("http"):
            base = source["url"].split("/", 3)[:3]
            url  = "/".join(base) + url

        articles.append({
            "source":  source["id"],
            "title":   title,
            "snippet": snippet,
            "url":     url,
        })

    return articles


async def scrape_all() -> list[dict]:
    """Returns combined list of articles from all sources."""
    all_articles: list[dict] = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        for source in SOURCES:
            try:
                resp = await client.get(source["url"])
                resp.raise_for_status()
                articles = _extract_articles(resp.text, source)
                all_articles.extend(articles)
            except Exception as e:
                all_articles.append({
                    "source":  source["id"],
                    "title":   f"[scrape failed: {e}]",
                    "snippet": "",
                    "url":     source["url"],
                    "error":   True,
                })
    return all_articles
