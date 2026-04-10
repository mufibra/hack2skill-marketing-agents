# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Google ADK (v1.28.1) multi-agent marketing intelligence platform. Five LlmAgents (1 root orchestrator + 4 sub-agents) query a 16-table SQLite database with 70K+ rows of marketing data. Dual-model architecture: Gemini 2.5 Pro for the root orchestrator, Gemini 2.5 Flash for sub-agents.

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
- `GOOGLE_GENAI_API_KEY` — Gemini API key (used by ADK)

## Key Patterns

- Agent instructions include exact data shapes (row counts, column names, model accuracy) to prevent hallucination
- `function_calling_config mode=ANY` forces sub-agents to always use tools before responding
- The `mcp_servers/` directory exists but MCP is not used — all tools are in-process FunctionTool
