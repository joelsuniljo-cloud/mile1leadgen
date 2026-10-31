import csv
import io
import logging
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ai, config, demo, pipeline
from .db import Lead, Search, SessionLocal, init_db, lead_dict, search_dict

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).resolve().parent.parent / "static"
scheduler = BackgroundScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if config.SEED_DEMO:
        demo.seed()
    scheduler.add_job(pipeline.run_all_active, "interval", minutes=config.POLL_MINUTES,
                      id="poll", max_instances=1, coalesce=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Mile 1 Lead Radar", lifespan=lifespan)


# ------------------------------------------------------------------ auth
@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if not config.APP_PASSWORD or request.url.path == "/api/health":
        return await call_next(request)
    import base64
    ok = False
    h = request.headers.get("authorization", "")
    if h.lower().startswith("basic "):
        try:
            user, _, pw = base64.b64decode(h[6:]).decode().partition(":")
            ok = (secrets.compare_digest(user, config.APP_USER)
                  and secrets.compare_digest(pw, config.APP_PASSWORD))
        except Exception:
            ok = False
    if not ok:
        return Response("Authentication required", 401,
                        headers={"WWW-Authenticate": 'Basic realm="Mile 1 Lead Radar"'})
    return await call_next(request)


def get_db():
    with SessionLocal() as db:
        yield db


# ------------------------------------------------------------------ schemas
class SearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=3, max_length=300)
    offering: str = Field(default="", max_length=1500)
    sources: list[str] = Field(default_factory=lambda: ["hackernews"])


class LeadPatch(BaseModel):
    status: str


# ------------------------------------------------------------------ routes
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def get_config():
    return {"sources": config.available_sources(), "ai": bool(config.ANTHROPIC_API_KEY),
            "poll_minutes": config.POLL_MINUTES, "min_score": config.MIN_SCORE}


@app.get("/api/searches")
def list_searches(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Lead.search_id, func.count()).group_by(Lead.search_id)).all())
    new = dict(db.execute(select(Lead.search_id, func.count()).where(Lead.status == "new")
                          .group_by(Lead.search_id)).all())
    rows = db.execute(select(Search).order_by(Search.created_at.desc())).scalars().all()
    return [search_dict(s, counts.get(s.id, 0), new.get(s.id, 0)) for s in rows]


@app.post("/api/searches", status_code=201)
def create_search(body: SearchIn, db: Session = Depends(get_db)):
    avail = config.available_sources()
    sources = [s for s in body.sources if avail.get(s)]
    if not sources:
        raise HTTPException(400, "Pick at least one source that is configured.")
    s = Search(name=body.name.strip(), query=body.query.strip(), offering=body.offering.strip(),
               sources=sources, variants=ai.expand_query(body.query, body.offering))
    db.add(s)
    db.commit()
    threading.Thread(target=pipeline.run_search, args=(s.id,), daemon=True).start()
    return search_dict(s)


@app.post("/api/searches/{sid}/run", status_code=202)
def run_now(sid: int, db: Session = Depends(get_db)):
    s = db.get(Search, sid)
    if not s:
        raise HTTPException(404)
    if s.is_demo:
        raise HTTPException(400, "Sample searches don't scan. Create your own.")
    threading.Thread(target=pipeline.run_search, args=(sid,), daemon=True).start()
    return {"started": True}


@app.patch("/api/searches/{sid}")
def toggle_search(sid: int, active: bool, db: Session = Depends(get_db)):
    s = db.get(Search, sid)
    if not s:
        raise HTTPException(404)
    s.active = active
    db.commit()
    return search_dict(s)


@app.delete("/api/searches/{sid}", status_code=204)
def delete_search(sid: int, db: Session = Depends(get_db)):
    s = db.get(Search, sid)
    if not s:
        raise HTTPException(404)
    db.delete(s)
    db.commit()


def _lead_query(search_id, source, min_score, status, since_id, q):
    stmt = select(Lead).join(Search)
    if search_id:
        stmt = stmt.where(Lead.search_id == search_id)
    if source:
        stmt = stmt.where(Lead.source == source)
    if min_score:
        stmt = stmt.where(Lead.score >= min_score)
    if status:
        stmt = stmt.where(Lead.status == status)
    else:
        stmt = stmt.where(Lead.status != "dismissed")
    if since_id:
        stmt = stmt.where(Lead.id > since_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Lead.text.ilike(like)) | (Lead.title.ilike(like)) | (Lead.author.ilike(like)))
    return stmt


@app.get("/api/leads")
def list_leads(search_id: int | None = None, source: str | None = None, min_score: int = 0,
               status: str | None = None, since_id: int = 0, q: str | None = None,
               limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    stmt = _lead_query(search_id, source, min_score, status, since_id, q)
    # newest posts first (by when they were posted, fall back to when we found them)
    stmt = stmt.order_by(func.coalesce(Lead.posted_at, Lead.found_at).desc()).limit(limit)
    return [lead_dict(l) for l in db.execute(stmt).scalars().all()]


@app.patch("/api/leads/{lid}")
def update_lead(lid: int, body: LeadPatch, db: Session = Depends(get_db)):
    if body.status not in ("new", "saved", "contacted", "dismissed"):
        raise HTTPException(400, "Invalid status")
    l = db.get(Lead, lid)
    if not l:
        raise HTTPException(404)
    l.status = body.status
    db.commit()
    return lead_dict(l)


@app.get("/api/leads.csv")
def export_csv(search_id: int | None = None, db: Session = Depends(get_db)):
    stmt = _lead_query(search_id, None, 0, None, 0, None).order_by(Lead.found_at.desc())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["found_at", "posted_at", "source", "score", "author", "author_url", "title",
                "text", "url", "status", "reason", "suggested_reply"])
    for l in db.execute(stmt).scalars():
        w.writerow([l.found_at, l.posted_at, l.source, l.score, l.author, l.author_url, l.title,
                    l.text, l.url, l.status, l.reason, l.suggested_reply])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="mile1-leads.csv"'})


@app.delete("/api/demo", status_code=204)
def clear_demo():
    demo.clear()


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
