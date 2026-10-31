import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class RawPost:
    source: str
    external_id: str
    url: str
    author: str = ""
    author_url: str = ""
    title: str = ""
    text: str = ""
    posted_at: datetime | None = None


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = (s.replace("&#x27;", "'").replace("&quot;", '"').replace("&amp;", "&")
          .replace("&gt;", ">").replace("&lt;", "<").replace("&#x2F;", "/"))
    return re.sub(r"\s+", " ", s).strip()


def parse_relative(s: str | None) -> datetime | None:
    """'3 days ago', '5 hours ago' -> datetime. Returns None if unparseable."""
    if not s:
        return None
    m = re.match(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", s.strip().lower())
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    delta = {"minute": timedelta(minutes=n), "hour": timedelta(hours=n), "day": timedelta(days=n),
             "week": timedelta(weeks=n), "month": timedelta(days=30 * n)}[unit]
    return datetime.now(timezone.utc) - delta
