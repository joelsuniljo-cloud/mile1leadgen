import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from . import ai, config
from .collectors import COLLECTORS
from .db import Lead, Search, SessionLocal, now

log = logging.getLogger("pipeline")
_running: set[int] = set()
_lock = threading.Lock()


def run_search(search_id: int) -> int:
    """Collect -> dedupe -> classify -> store. Returns number of new leads."""
    with _lock:
        if search_id in _running:
            return 0
        _running.add(search_id)
    try:
        return _run(search_id)
    finally:
        _running.discard(search_id)


def _run(search_id: int) -> int:
    avail = config.available_sources()
    with SessionLocal() as db:
        s = db.get(Search, search_id)
        if not s or s.is_demo:
            return 0
        since = s.last_run_at or (now() - timedelta(days=7))
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        queries = ([s.query] + [v for v in (s.variants or []) if v != s.query])[:config.MAX_VARIANTS]

        raw, errors = {}, []
        for src in s.sources or []:
            if not avail.get(src):
                errors.append(f"{src}: not configured")
                continue
            for q in queries:
                try:
                    for p in COLLECTORS[src](q, since):
                        raw[(p.source, p.external_id)] = p
                except Exception as e:  # one failing source must not stop the others
                    errors.append(f"{src}: {type(e).__name__}: {str(e)[:120]}")
                    log.warning("collector %s failed: %s", src, e)
                    break

        existing = set(db.execute(
            select(Lead.source, Lead.external_id).where(Lead.search_id == s.id)).all())
        fresh = [p for k, p in raw.items() if k not in existing]

        verdicts = ai.classify(
            [{"title": p.title, "text": p.text, "source": p.source, "author": p.author} for p in fresh],
            s.offering, s.query)

        added = 0
        for p, v in zip(fresh, verdicts):
            if v["intent"] != "buying" or v["score"] < config.MIN_SCORE:
                continue
            db.add(Lead(search_id=s.id, source=p.source, external_id=p.external_id[:200],
                        url=p.url[:1000], author=p.author[:200], author_url=p.author_url[:1000],
                        title=p.title[:500], text=p.text[:4000], posted_at=p.posted_at,
                        score=v["score"], intent=v["intent"], reason=v["reason"],
                        suggested_reply=v["reply"]))
            try:
                db.flush()
                added += 1
            except IntegrityError:
                db.rollback()
        s.last_run_at = now()
        s.last_error = "; ".join(errors)[:500] or None
        db.commit()
        return added


def run_all_active() -> None:
    with SessionLocal() as db:
        ids = [i for (i,) in db.execute(select(Search.id).where(Search.active, ~Search.is_demo)).all()]
    for i in ids:
        try:
            run_search(i)
        except Exception:
            log.exception("search %s failed", i)
