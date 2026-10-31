"""Sample data so the dashboard is usable before any API keys are added.
Every record is flagged is_demo and labelled SAMPLE in the UI. All names are fictional."""
from datetime import timedelta

from sqlalchemy import select

from .db import Lead, Search, SessionLocal, now

SAMPLES = [
    ("linkedin", "Aarav Menon", "Looking for a digital marketing agency in Bangalore",
     "We're a 40-person D2C skincare brand and our in-house team can't keep up. Looking for a digital marketing agency that can run performance + content. Budget flexible, want to start next month. Recommendations welcome.",
     94, "Explicit need, named budget flexibility and start date.", 35,
     "Happy to share how we've approached D2C performance + content for brands at your stage. If useful, I can send over two relevant case studies. No pitch deck."),
    ("reddit", "u/fictional_founder", "r/startups · Need an SEO partner for B2B SaaS, any suggestions?",
     "Series A, ~$15k/mo budget. Our organic traffic has plateaued and we want someone who understands technical SEO and content for developer audiences.",
     91, "Specific budget, clear scope, actively asking for suggestions.", 120, ""),
    ("hackernews", "demo_user_hn", "Ask HN: How do you pick a marketing agency?",
     "Our agency contract ends in December and we're evaluating alternatives. What did you look for? Any you'd recommend for early-stage hardware?",
     78, "Evaluating replacements with a deadline.", 300, ""),
    ("linkedin", "Priya Nair", "Hiring a growth marketing partner for our fintech launch",
     "We are launching in Q1 and need an external growth partner for paid, lifecycle and brand. DM if you have fintech experience.",
     86, "Launch timeline plus direct invitation to fintech-experienced partners.", 480, ""),
    ("web", "fictionalforum.example", "Anyone used a PPC agency for ecommerce? Thinking of switching",
     "Spending 4L/month on Meta and Google, ROAS is flat. Considering a new agency. What questions should I ask before signing?",
     72, "Actively considering switching; asks for guidance.", 700, ""),
    ("reddit", "u/demo_clinic_owner", "r/smallbusiness · Marketing help for a dental clinic?",
     "Opening a second clinic. We've never done digital marketing properly. Who would you trust for local SEO and Google Ads?",
     83, "New location, no existing agency, asks for trusted names.", 900, ""),
]


def seed() -> None:
    with SessionLocal() as db:
        if db.execute(select(Search.id).limit(1)).first():
            return
        s = Search(name="Digital marketing agencies", query="looking for digital marketing agency",
                   offering="Digital marketing agency (SEO, paid media, content)",
                   variants=["need an SEO partner", "recommend a marketing agency", "hiring growth marketing partner"],
                   sources=["hackernews", "reddit", "linkedin", "web"], is_demo=True,
                   last_run_at=now())
        db.add(s)
        db.flush()
        for i, (src, author, title, text, score, reason, mins, reply) in enumerate(SAMPLES):
            db.add(Lead(search_id=s.id, source=src, external_id=f"demo-{i}", url="https://example.com/sample",
                        author=author, title=title, text=text, posted_at=now() - timedelta(minutes=mins),
                        found_at=now() - timedelta(minutes=max(1, mins - 4)), score=score, intent="buying",
                        reason=reason, suggested_reply=reply, is_demo=True))
        db.commit()


def clear() -> None:
    with SessionLocal() as db:
        for s in db.execute(select(Search).where(Search.is_demo)).scalars():
            db.delete(s)
        db.commit()
