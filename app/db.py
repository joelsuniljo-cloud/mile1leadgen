from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String,
                        Text, UniqueConstraint, create_engine)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

from .config import DATABASE_URL


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Search(Base):
    __tablename__ = "searches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    query: Mapped[str] = mapped_column(String(300))
    offering: Mapped[str] = mapped_column(Text, default="")  # what the user sells
    variants: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    leads = relationship("Lead", back_populates="search", cascade="all, delete-orphan")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("search_id", "source", "external_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("searches.id"), index=True)
    source: Mapped[str] = mapped_column(String(30), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(1000))
    author: Mapped[str] = mapped_column(String(200), default="")
    author_url: Mapped[str] = mapped_column(String(1000), default="")
    title: Mapped[str] = mapped_column(String(500), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    intent: Mapped[str] = mapped_column(String(20), default="buying")
    reason: Mapped[str] = mapped_column(Text, default="")
    suggested_reply: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    search = relationship("Search", back_populates="leads")


def _iso(d: datetime | None) -> str | None:
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.isoformat()


def lead_dict(l: Lead) -> dict:
    return {
        "id": l.id, "search_id": l.search_id, "search_name": l.search.name if l.search else "",
        "source": l.source, "url": l.url, "author": l.author, "author_url": l.author_url,
        "title": l.title, "text": l.text, "posted_at": _iso(l.posted_at),
        "found_at": _iso(l.found_at), "score": l.score, "intent": l.intent,
        "reason": l.reason, "suggested_reply": l.suggested_reply, "status": l.status,
        "is_demo": l.is_demo,
    }


def search_dict(s: Search, lead_count: int = 0, new_count: int = 0) -> dict:
    return {
        "id": s.id, "name": s.name, "query": s.query, "offering": s.offering,
        "variants": s.variants or [], "sources": s.sources or [], "active": s.active,
        "is_demo": s.is_demo, "created_at": _iso(s.created_at),
        "last_run_at": _iso(s.last_run_at), "last_error": s.last_error,
        "lead_count": lead_count, "new_count": new_count,
    }


connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
