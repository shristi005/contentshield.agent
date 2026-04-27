# ContentShield

Autonomous digital asset protection web app. A Flask server scans the web for potentially infringing copies of a user's content, classifies them, and generates DMCA takedown drafts.

## Tech Stack

- **Language:** Python 3.12
- **Framework:** Flask (with Flask-CORS), server-sent events for live scan logs
- **Frontend:** Single Jinja2 template (`templates/app.html`) with vanilla HTML/CSS/JS
- **Production server:** Gunicorn

## Project Layout

- `server.py` — Flask app, routes (`/`, `/scan`, `/send-report`)
- `main.py` — CLI demo entry point (not used by the web app)
- `hunter.py` — Searches the web for candidate URLs
- `judge.py` — Risk scoring and AI-assisted verdicts
- `reporter.py` — Email body / DMCA notice generation, SMTP send
- `fingerprint.py` — Image/video fingerprint helpers (used by CLI)
- `templates/app.html` — Web UI
- `demo_dataset.json` — Cached dataset used as fallback

## Optional Environment Variables

These are only needed for full functionality; the app falls back gracefully without them:

- `GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_ENGINE_ID` — live web search via Google Custom Search
- `GROQ_API_KEY` — AI verdict and DMCA generation
- SMTP credentials (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, etc.) — email delivery

## Replit Setup

- Workflow `Start application` runs `python server.py` on port 5000 (webview).
- Deployment is configured as `autoscale` running `gunicorn server:app` on port 5000.
