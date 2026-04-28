# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Google ADK (v1.28.1) multi-agent marketing intelligence platform. Five LlmAgents (1 root orchestrator + 4 sub-agents) query a 16-table SQLite database with 70K+ rows of marketing data. All agents run on `gemini-3.1-pro-preview` via Vertex AI. The Cloud Run service is in `asia-southeast1`, but `GOOGLE_CLOUD_LOCATION=global` because Gemini 3.x is only served from the global Vertex endpoint.

## Commands

```bash
# Setup
venv\Scripts\activate
pip install -r requirements.txt

# Initialize database (run once, or to reset)
python db/setup.py
python db/load_data.py

# Run with ADK Dev UI (primary development mode)
adk web

# Run as API server
python api_server.py          # default port 8001
```

## Architecture

### Agent Hierarchy (`marketing_agents/agent.py`)

`root_agent` (marketing_orchestrator, gemini-3.1-pro-preview) delegates to 4 sub-agents (all gemini-3.1-pro-preview):
- `marketing_intel` — GA4 analytics, anomaly detection
- `competitive_intel` — competitor share-of-voice, citations
- `customer_intel` — sentiment, lead scoring, RFM segmentation
- `operations` — pipeline health, CRM funnel, attribution (7 models)

Sub-agents MUST transfer back to `marketing_orchestrator` after completing analysis (enforced in each agent's instruction). This transfer-back protocol enables multi-step session chaining.

### Tool Architecture (`marketing_agents/tools.py`)

All 9 domain tools + 4 orchestrator tools are plain Python functions. ADK auto-wraps them as `FunctionTool` — no MCP subprocess overhead. Every tool queries SQLite directly via `_conn()` helper and returns a dict.

Orchestrator tools: `log_workflow`, `log_action`, `get_recent_workflows`, `create_task`
Domain tools: `get_morning_briefing`, `detect_anomalies`, `scan_competitors`, `get_competitive_history`, `analyze_sentiment`, `score_leads`, `get_customer_segments`, `check_pipeline_health`, `get_attribution_analysis`

### Database (`db/marketing_intel.db`)

- Schema defined in `db/setup.py` — 16 tables
- Data loaded by `db/load_data.py` from CSVs in `source_data/`
- Logging helpers in `db/db_utils.py`
- DB path resolved via `Path(__file__).resolve().parent.parent / "db" / "marketing_intel.db"` in tools.py

### API (`api_server.py`)

Wraps ADK's `get_fast_api_app()` with custom `/status`, `/workflows`, `/agents` endpoints. Sessions stored in `db/sessions.db`.

### Legacy Reference (`tools/`)

Contains upstream project implementations (briefing, competitive, sentiment, etc.) — reference only, not used by the agents.

## Environment Variables

Requires `.env` with:
- `GOOGLE_GENAI_USE_VERTEXAI=True` — route ADK Gemini calls through Vertex AI
- `GOOGLE_CLOUD_PROJECT=galvanic-smoke-489914-u7`
- `GOOGLE_CLOUD_LOCATION=global` (Gemini 3.x is only available on the global Vertex endpoint; the Cloud Run service still runs in `asia-southeast1`)

Local auth: run `gcloud auth application-default login` and `gcloud auth application-default set-quota-project galvanic-smoke-489914-u7` once. Cloud Run uses the compute service account (`778200673789-compute@developer.gserviceaccount.com`) with `roles/aiplatform.user`.

## Deployment

Cloud Run service `hack2skill` in `asia-southeast1` (project `galvanic-smoke-489914-u7`):
- Public URL: `https://hack2skill-778200673789.asia-southeast1.run.app`
- `min-instances=1` (no cold starts)
- Redeploy from source: `gcloud run deploy hack2skill --source . --region asia-southeast1`

## Key Patterns

- Agent instructions include exact data shapes (row counts, column names, model accuracy) to prevent hallucination
- `function_calling_config mode=ANY` forces sub-agents to always use tools before responding
- The `mcp_servers/` directory exists but MCP is not used — all tools are in-process FunctionTool

## Sprint Rules (Apr 29-30 — Top 100 refinement)

This 2-day sprint involves a frontend collaborator (Asha) working in `frontend/`. To avoid stomping each other's work:

- **Don't edit `frontend/`** — that's Asha's territory, owned via Cursor
- **SPEC.md is locked** after Day 1 morning sync. Don't change response schemas unilaterally
- **Every tool function must log SQL** and return `{"result": ..., "sql": "..."}` per SPEC.md (needed for the Query Viewer feature)
- **No new dependencies** without asking — sprint is feature-focused, not refactor-focused
- **No `gcloud run deploy`** until Day 2 afternoon — keep iterations local until features are stable
- **Branch then merge.** Backend work on `feature/backend-modes`, never direct to main
