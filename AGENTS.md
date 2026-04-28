# Marketing Intelligence Agent — AI Coding Guide

## Project context

Multi-agent AI system for cross-domain marketing intelligence. Built for Google Cloud Gen AI Academy APAC 2026 hackathon. Currently in the **top 100 round — 2-day refinement sprint** to turn the prototype into a polished product.

Live deployment: `https://hack2skill-778200673789.asia-southeast1.run.app`

## Tech stack

- **Backend:** Python 3.14, Google ADK v1.28.1, Gemini 3.1 Pro via Vertex AI (global endpoint), FastAPI, SQLite
- **Frontend:** Single HTML file, Tailwind via CDN, vanilla JavaScript (no npm, no build step)
- **Deployment:** Google Cloud Run (asia-southeast1), GCP project `galvanic-smoke-489914-u7`

## File ownership

**Asha owns:**
- `frontend/` — HTML, CSS, JS for the user-facing UI

**Ibra owns:**
- `marketing_agents/` — agent definitions, prompts, tools
- `db/` — SQLite database setup and data
- `api_server.py` — FastAPI app and Cloud Run entry point
- `Dockerfile`, `requirements.txt` — deployment config

**Shared (touch only after agreement in WhatsApp):**
- `SPEC.md` — the API contract between frontend and backend. Locked after Day 1 morning sync.
- `README.md`
- `.env.example`

## Code style

- **Python:** type hints on all functions. Simple over clever. No unnecessary abstractions.
- **HTML/JS:** vanilla only. No React, no build step. Tailwind via CDN.
- **Comments:** only when the *why* is non-obvious. Skip docstrings for trivial functions.

## Cardinal rules

1. **One file, one owner.** Don't edit files outside your ownership column without explicit WhatsApp confirmation.
2. **Branch then merge.** No direct commits to `main`. Each feature gets a branch, push, fast review, merge.
3. **SPEC.md is the contract.** Once locked Day 1 morning, both agents must conform to it. Frontend renders what backend produces. Backend produces what SPEC.md specifies.
4. **No new dependencies without asking.** Especially no npm packages, no Python libs not already in `requirements.txt`.
5. **Test before pushing.** What you ship must run end-to-end on your machine first.

## Operating environment

- **Backend dev:** `python api_server.py` runs ADK on `localhost:8000`
- **Frontend dev:** open `frontend/index.html` directly in browser, points at deployed Cloud Run URL
- **Production deploy:** Ibra runs `gcloud run deploy` after Day 2 features merged
