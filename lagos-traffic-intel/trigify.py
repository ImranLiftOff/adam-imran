"""
Pulls results from two Trigify saved searches:
  - Lagos Traffic Keywords (keyword search)
  - @lagostraffic961 profile (Lagos Traffic Radio 96.1FM)
Returns list of post dicts for signals.py to process.

Endpoint and response shape verified directly against the live API on
2026-07-06 (the old /api/searches/.../results and /api/search/.../posts
guesses both 404'd, so this pipeline had never actually ingested a single
real post before this fix):

  GET https://api.trigify.io/v1/searches/{id}/results?limit=N
  Authorization: Bearer <TRIGIFY_API_KEY>
  -> {"success": true, "data": [
       {"author": {"name", "username", ...},
        "content": {"text", "url", "media": [...]},
        "engagement": {"likes", "comments", "shares"},
        "published_at", "collected_at", ...}, ...
     ]}
"""

import httpx
from config import TRIGIFY_API_KEY, TRIGIFY_SEARCH_KEYWORDS, TRIGIFY_SEARCH_LAGOSTRAFFIC

TRIGIFY_BASE = "https://api.trigify.io/v1"
MAX_POSTS = 30  # per search


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {TRIGIFY_API_KEY}",
        "Content-Type": "application/json",
    }


def _extract_posts(response_data: dict | list) -> list[dict]:
    """Normalise the real Trigify results response into a flat list of post dicts."""
    if isinstance(response_data, list):
        items = response_data
    elif isinstance(response_data, dict):
        items = response_data.get("data", [])
        if not isinstance(items, list):
            items = []
    else:
        items = []

    posts: list[dict] = []
    for item in items[:MAX_POSTS]:
        author  = item.get("author") or {}
        content = item.get("content") or {}
        posts.append({
            "text":       str(content.get("text", ""))[:600],
            "author":     author.get("username") or author.get("name") or "",
            "posted_at":  item.get("published_at", ""),
            "url":        content.get("url", ""),
            "raw":        item,
        })
    return posts


async def fetch_trigify_posts() -> list[dict]:
    """
    Fetches latest posts from both saved searches concurrently.
    Returns combined list; any individual failure returns empty list for that search.
    """
    all_posts: list[dict] = []
    search_ids = [TRIGIFY_SEARCH_KEYWORDS, TRIGIFY_SEARCH_LAGOSTRAFFIC]

    async with httpx.AsyncClient(headers=_headers(), timeout=20) as client:
        for search_id in search_ids:
            try:
                resp = await client.get(
                    f"{TRIGIFY_BASE}/searches/{search_id}/results",
                    params={"limit": MAX_POSTS},
                )
                resp.raise_for_status()
                data = resp.json()
                posts = _extract_posts(data)
                for p in posts:
                    p["_search_id"] = search_id
                all_posts.extend(posts)
            except Exception as e:
                all_posts.append({
                    "text":      f"[trigify fetch failed for {search_id}: {e}]",
                    "author":    "",
                    "posted_at": "",
                    "url":       "",
                    "_search_id": search_id,
                    "error":     True,
                })

    return all_posts
