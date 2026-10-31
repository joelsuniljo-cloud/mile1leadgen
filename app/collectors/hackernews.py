from datetime import datetime, timezone

import httpx

from .base import RawPost, strip_html

API = "https://hn.algolia.com/api/v1/search_by_date"


def fetch(query: str, since: datetime, limit: int = 30) -> list[RawPost]:
    params = {
        "query": query,
        "tags": "(story,comment)",
        "numericFilters": f"created_at_i>{int(since.timestamp())}",
        "hitsPerPage": limit,
    }
    r = httpx.get(API, params=params, timeout=20)
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        oid = h.get("objectID")
        text = strip_html(h.get("comment_text") or h.get("story_text") or "")
        title = h.get("title") or h.get("story_title") or ""
        if not (text or title):
            continue
        out.append(RawPost(
            source="hackernews", external_id=str(oid),
            url=f"https://news.ycombinator.com/item?id={oid}",
            author=h.get("author") or "",
            author_url=f"https://news.ycombinator.com/user?id={h.get('author')}" if h.get("author") else "",
            title=title, text=text,
            posted_at=datetime.fromtimestamp(h["created_at_i"], tz=timezone.utc),
        ))
    return out
