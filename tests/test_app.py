import os
import tempfile
from datetime import datetime, timezone

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"
os.environ["SEED_DEMO"] = "true"
os.environ.pop("ANTHROPIC_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app import ai, pipeline  # noqa: E402
from app.collectors import serp  # noqa: E402
from app.collectors.base import RawPost, parse_relative, strip_html  # noqa: E402
from app.main import app  # noqa: E402


def test_helpers():
    assert strip_html("<p>Hi&#x27;s <b>you</b></p>") == "Hi's you"
    assert parse_relative("3 days ago") is not None
    assert parse_relative("garbage") is None


def test_linkedin_author_parse():
    name, url = serp._linkedin_author(
        "https://www.linkedin.com/posts/jane-doe-123_marketing-activity-1", "Jane Doe on LinkedIn: need agency")
    assert name == "Jane Doe" and url == "https://www.linkedin.com/in/jane-doe-123"


def test_heuristic_scoring():
    buy = ai.classify([{"title": "Looking for a marketing agency", "text": "Can anyone recommend one?",
                        "source": "reddit", "author": "x"}], "", "q")[0]
    promo = ai.classify([{"title": "Our agency", "text": "We offer SEO. Book a call, free audit",
                          "source": "web", "author": "x"}], "", "q")[0]
    assert buy["intent"] == "buying" and buy["score"] >= 70
    assert promo["intent"] == "promo"


def test_api_flow_and_pipeline(monkeypatch):
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"ok": True}
        assert len(c.get("/api/leads?min_score=0").json()) == 6  # demo seed

        fake = [RawPost("hackernews", "1", "https://news.ycombinator.com/item?id=1", "bob", "",
                        "Ask HN: need a marketing agency", "Looking for recommendations, budget 5k",
                        datetime.now(timezone.utc)),
                RawPost("hackernews", "2", "https://news.ycombinator.com/item?id=2", "eve", "",
                        "Our agency", "We offer SEO, book a call", datetime.now(timezone.utc))]
        monkeypatch.setitem(pipeline.COLLECTORS, "hackernews", lambda q, since: fake)

        r = c.post("/api/searches", json={"name": "t", "query": "looking for marketing agency",
                                          "sources": ["hackernews"]})
        assert r.status_code == 201
        sid = r.json()["id"]
        assert len(r.json()["variants"]) >= 3
        import time; time.sleep(1.5)  # background scan thread
        pipeline.run_search(sid)  # idempotent: duplicates must not be re-added
        leads = c.get(f"/api/leads?search_id={sid}&min_score=0").json()
        assert [l["author"] for l in leads] == ["bob"]  # promo post filtered out

        lid = leads[0]["id"]
        assert c.patch(f"/api/leads/{lid}", json={"status": "saved"}).json()["status"] == "saved"
        assert c.patch(f"/api/leads/{lid}", json={"status": "bogus"}).status_code == 400
        assert "bob" in c.get("/api/leads.csv").text
        assert c.post("/api/searches", json={"name": "x", "query": "abcd", "sources": ["reddit"]}).status_code == 400
        assert c.delete("/api/demo").status_code == 204


def test_auth(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "APP_PASSWORD", "pw")
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/leads").status_code == 401
        assert c.get("/api/leads", auth=("mile1", "pw")).status_code == 200
        assert c.get("/api/leads", auth=("mile1", "bad")).status_code == 401
