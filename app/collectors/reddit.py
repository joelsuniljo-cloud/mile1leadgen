import time
from datetime import datetime, timezone

import httpx

from .. import config
from .base import RawPost

_token = {"value": "", "exp": 0.0}


def _get_token() -> str:
    if _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    r = httpx.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(config.REDDIT_CLIENT_ID, config.REDDIT_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": config.REDDIT_USER_AGENT}, timeout=20,
    )
    r.raise_for_status()
    j = r.json()
    _token.update(value=j["access_token"], exp=time.time() + j.get("expires_in", 3600))
    return _token["value"]


def fetch(query: str, since: datetime, limit: int = 25) -> list[RawPost]:
    headers = {"Authorization": f"bearer {_get_token()}", "User-Agent": config.REDDIT_USER_AGENT}
    r = httpx.get("https://oauth.reddit.com/search",
                  params={"q": query, "sort": "new", "t": "month", "limit": limit, "type": "link"},
                  headers=headers, timeout=20)
    r.raise_for_status()
    out = []
    for c in r.json().get("data", {}).get("children", []):
        d = c.get("data", {})
        created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
        if created < since:
            continue
        author = d.get("author") or ""
        out.append(RawPost(
            source="reddit", external_id=d["id"],
            url="https://www.reddit.com" + d.get("permalink", ""),
            author=author,
            author_url=f"https://www.reddit.com/user/{author}" if author and author != "[deleted]" else "",
            title=f"r/{d.get('subreddit')} · {d.get('title', '')}",
            text=d.get("selftext", "") or "", posted_at=created,
        ))
    return out
