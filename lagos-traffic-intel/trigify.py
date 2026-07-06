"""
Pulls results from two Trigify saved searches:
  - Lagos Traffic Keywords (keyword search)
  - @lagostraffic961 profile (Lagos Traffic Radio 96.1FM)
Returns list of post dicts for signals.py to process.
"""

import httpx
from config import TRIGIFY_API_KEY, TRIGIFY_SEARCH_KEYWORDS, TRIGIFY_SEARCH_LAGOSTRAFFIC

TRIGIFY_BASE = "https://api.trigify.io/api"
MAX_POSTS = 25  # per search, last 24h is sufficient


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {TRIGIFY_API_KEY}",
        "Content-Type": "application/json",
    }


def _extract_posts(response_data: dict | list) -> list[dict]:
    """
    Normalise Trigify response into a flat list of post dicts.
    Trigify may return {data: [...]} or a direct list — handle both.
    """
    if isinstance(response_data, list):
        items = response_data
    elif isinstance(response_data, dict):
        items = response_data.get("data", response_data.get("results", response_data.get("posts", [])))
        if not isinstance(items, list):
            items = []
    else:
        items = []

    posts: list[dict] = []
    for item in items[:MAX_POSTS]:
        text = (
            item.get("text") or item.get("content") or
            item.get("post_text") or item.get("message") or ""
        )
        posts.append({
            "text":       str(text)[:500],
            "author":     item.get("author") or item.get("username") or item.get("handle") or "",
            "posted_at":  item.get("created_at") or item.get("posted_at") or item.get("timestamp") or "",
            "url":        item.get("url") or item.get("post_url") or item.get("link") or "",
            "search_id":  item.get("_search_id", ""),
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
                # Try the results endpoint first
                resp = await client.get(
                    f"{TRIGIFY_BASE}/searches/{search_id}/results",
                    params={"limit": MAX_POSTS},
                )
                if resp.status_code == 404:
                    # Fallback path some Trigify versions use
                    resp = await client.get(
                        f"{TRIGIFY_BASE}/search/{search_id}/posts",
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
