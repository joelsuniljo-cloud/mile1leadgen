# Mile 1 · Lead Radar

Type a phrase like *"looking for digital marketing agency"* and get a live feed of people asking for it, with who posted, where, when, a 0–100 buying-intent score and a suggested reply.

**How it works:** collectors (Hacker News, Reddit, Google-indexed LinkedIn/web posts) → dedupe → Claude scores each post for real buying intent (promo and noise are dropped) → dashboard. Scans run every `POLL_MINUTES` (default 15) and on demand.

## Deploy on Render
1. Push this folder to a GitHub repo.
2. Render → **New → Blueprint** → select the repo. It creates the web service and a Postgres database from `render.yaml`.
3. Set the secret env vars when prompted:
   | Var | Needed for |
   |---|---|
   | `APP_PASSWORD` | **Required.** Login password (username `mile1`). Without it the dashboard is public. |
   | `ANTHROPIC_API_KEY` | AI intent scoring, query expansion, reply drafts. Without it, a crude keyword heuristic is used. |
   | `SERPER_API_KEY` | LinkedIn + Web sources (serper.dev). |
   | `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Reddit source (reddit.com/prefs/apps, "script" app). Check Reddit's API terms for commercial use. |
4. Use the **Starter** plan (or above) for the web service: the free tier sleeps and stops polling.

Hacker News works with no keys, so you can verify the pipeline end to end first.

## Run locally
```
pip install -r requirements.txt
cp .env.example .env   # fill in keys
set -a; source .env; set +a
uvicorn app.main:app --reload
pytest
```

## Notes
- **LinkedIn is never scraped.** Posts come from what Google already shows publicly (title, snippet, URL), so no account is at risk and LinkedIn's anti-scraping terms aren't touched. Coverage is therefore partial: it finds indexed public posts, not everything.
- Sample leads are marked **SAMPLE** and can be cleared from the banner. Set `SEED_DEMO=false` in production (the Blueprint does).
- Poll runs inside the web process (APScheduler). Run a single instance; if you scale to several, move polling to a Render background worker.
- Treat scraped data as personal data (GDPR / India DPDP). Reply manually or review drafts; don't automate bulk outreach.

## Brand
Built to Mile 1 Brand Guidelines v1.0: Charcoal/White/Sand surfaces, Blue only for actions and "hot" signals, Satoshi (Fontshare), official logo SVGs in `static/img/`. "Lead Radar" is a placeholder product name.

## Layout
```
app/        FastAPI app, collectors/, ai.py (Claude), pipeline.py, db.py
static/     index.html, app.css, app.js, img/ (logos)
tests/      pytest suite
render.yaml Render Blueprint
```
