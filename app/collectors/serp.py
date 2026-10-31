"""Public posts discovered through Google's index (via Serper.dev).

LinkedIn is deliberately NOT scraped. We only read what a search engine already
shows publicly: title, snippet, URL. That keeps us clear of LinkedIn's anti-scraping
terms and means no LinkedIn account can be banned.
"""
import re
from datetime import datetime, timezone

import httpx

from .. import config
from .base import RawPost, parse_relative

ENDPOINT = "https://google.serper.dev/search"


def _search(q: str, num: int = 20) -> list[dict]:
    r = httpx.post(ENDPOINT, json={"q": q, "num": num, "tbs": "qdr:w"},  # past week
                   headers={"X-API-KEY": config.SERPER_API_KEY}, timeout=25)
    r.raise_for_status()
    return r.json().get("organic", [])


def _linkedin_author(link: str, title: str) -> tuple[str, str]:
    # Titles look like: "Jane Doe on LinkedIn: Looking for a marketing agency..."
    m = re.match(r"(.+?) on LinkedIn", title or "")
    name = m.group(1).strip() if m else ""
    m2 = re.search(r"linkedin\.com/posts/([^_/?]+)", link)
    handle = m2.group(1) if m2 else ""
    profile = f"https://www.linkedin.com/in/{handle}" if handle else ""
    return name or handle, profile


def fetch_linkedin(query: str, since: datetime, limit: int = 20) -> list[RawPost]:
    q = f'(site:linkedin.com/posts OR site:linkedin.com/feed/update) {query}'
    out = []
    for o in _search(q, limit):
        link = o.get("link", "")
        if "linkedin.com" not in link:
            continue
        author, author_url = _linkedin_author(link, o.get("title", ""))
        title = re.sub(r"^.+? on LinkedIn:\s*", "", o.get("title", ""))
        out.append(RawPost(
            source="linkedin", external_id=link, url=link, author=author, author_url=author_url,
            title=title, text=o.get("snippet", ""),
            posted_at=parse_relative(o.get("date")) or datetime.now(timezone.utc),
        ))
    return out


EXCLUDE = "-site:linkedin.com -site:reddit.com -site:news.ycombinator.com"


def fetch_web(query: str, since: datetime, limit: int = 20) -> list[RawPost]:
    """Forums, Quora, X/Twitter, Facebook-indexed pages, tender boards, etc."""
    out = []
    for o in _search(f"{query} {EXCLUDE}", limit):
        link = o.get("link", "")
        host = re.sub(r"^https?://(www\.)?", "", link).split("/")[0]
        out.append(RawPost(
            source="web", external_id=link, url=link, author=host, author_url="",
            title=o.get("title", ""), text=o.get("snippet", ""),
            posted_at=parse_relative(o.get("date")) or datetime.now(timezone.utc),
        ))
    return out
