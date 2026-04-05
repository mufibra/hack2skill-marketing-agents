# Marketing Intelligence Multi-Agent System

A multi-agent marketing intelligence platform built with **Google ADK v1.28.1**, powered by a **dual-model architecture** — Gemini 2.5 Pro for orchestration and Gemini 2.5 Flash for tool execution. Five coordinated AI agents analyze marketing performance, competitive landscape, customer sentiment, lead quality, and operational health through 9 specialized tools backed by a live 16-table SQLite database with 70K+ rows of real analytics data.

Built for the **Hack2Skill Gen AI Hackathon** (Google-sponsored).

## Architecture

```
                         ┌───────────────────────────┐
                         │  marketing_orchestrator    │
                         │    Gemini 2.5 Pro          │
                         │  tools: log_workflow,      │
                         │    log_action,             │
                         │    get_recent_workflows,   │
                         │    create_task             │
                         └────────┬──────────────────┘
                                  │ delegates + transfer_to_agent
            ┌─────────────┬───────┴───────┬──────────────┐
            ▼             ▼               ▼              ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │marketing_intel│ │competitive_  │ │customer_intel│ │  operations  │
    │ Gemini Flash  │ │    intel     │ │ Gemini Flash  │ │ Gemini Flash  │
    │              │ │ Gemini Flash  │ │              │ │              │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │                │                │                │
           ▼                ▼                ▼                ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │              marketing_agents/tools.py (FunctionTool)           │
    │    9 Python functions — direct in-process execution, no MCP     │
    └──────────────────────────────┬───────────────────────────────────┘
                                   │ SQL queries
                                   ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                  SQLite — marketing_intel.db (12 MB)            │
    │  16 tables │ 70K+ rows │ GA4 metrics, leads, segments,         │
    │  sentiment, attribution, competitive citations, CRM pipeline   │
    └──────────────────────────────────────────────────────────────────┘
```

## Key Engineering Features

1. **In-Process Tool Execution (FunctionTool)** — All agent tools run as direct Python functions within the main process, eliminating subprocess overhead. This achieves consistent sub-second tool response times across all 9 tools, even on containerized Cloud Run deployments.

2. **Reliable Multi-Agent Session Chaining** — Implemented a transfer-back protocol that ensures sub-agents return control to the root orchestrator after completing their analysis. This enables complex 90+ step sessions where multiple agents chain sequentially across domains — marketing analytics -> competitive intelligence -> customer sentiment -> pipeline operations — all in a single conversation.

3. **Live Database Query Engine** — Every tool call executes real SQL queries against a 16-table SQLite database with 70K+ rows of source data from 7 upstream analytics projects. No static files or cached responses — all metrics, anomalies, and scores are computed at query time.

4. **Dual-Model Architecture** — Root orchestrator runs on Gemini 2.5 Pro for superior multi-agent routing and synthesis, while 4 specialized sub-agents run on Gemini 2.5 Flash for speed-optimized tool execution. This balances intelligence with performance.

5. **Data-Aware Agent Instructions** — Each agent knows exactly what data it has access to (row counts, column names, date ranges, model accuracy scores), enabling precise tool selection and contextual responses without hallucination.

## Agents

| Agent | Model | Role | Tools |
|---|---|---|---|
| `marketing_orchestrator` | Gemini 2.5 Pro | Root orchestrator — routes requests, chains sub-agents, synthesizes multi-agent results | `log_workflow`, `log_action`, `get_recent_workflows`, `create_task` |
| `marketing_intel` | Gemini 2.5 Flash | Marketing analytics: GA4 metrics, anomaly detection, trend analysis | `get_morning_briefing`, `detect_anomalies` |
| `competitive_intel` | Gemini 2.5 Flash | Competitor monitoring: brand citations, platform coverage, market positioning | `scan_competitors`, `get_competitive_history` |
| `customer_intel` | Gemini 2.5 Flash | Customer intelligence: sentiment analysis, lead scoring, RFM segmentation | `analyze_sentiment`, `score_leads`, `get_customer_segments` |
| `operations` | Gemini 2.5 Flash | Operational health: ETL pipeline monitoring, multi-model attribution analysis | `check_pipeline_health`, `get_attribution_analysis` |

## Database Schema

The SQLite database consolidates data from 7 upstream analytics projects into 16 tables:

| Category | Tables | Source | Records |
|---|---|---|---|
| GA4 Analytics | `daily_metrics` | P1: marketing-data-pipeline | 186 rows |
| Competitive Intel | `competitive_prompts`, `competitive_responses`, `competitive_citations`, `competitive_runs` | P3: ai-competitive-intel | 512 citations |
| Lead Scoring | `scored_leads` | P4: lead-scoring-system | 1,848 leads (93.8% model accuracy) |
| Customer Segments | `customer_segments` | P5: customer-segmentation-clv | 4,338 customers with RFM + CLV |
| Attribution | `attribution_results`, `journey_data` | P6: marketing-attribution-agent | 47,364 journeys, 7 models |
| Pipeline & CRM | `crm_contacts`, `pipeline_runs` | P7: customer-support-agent | 500 contacts, $8.6M pipeline |
| Sentiment | `support_tickets` | P8: nlp-customer-intelligence | 10,000 tickets |
| Agent Tracking | `workflow_runs`, `agent_actions`, `tasks`, `query_results` | Internal | Runtime logging |

## Multi-Step Workflows

### 1. Full Marketing Status Update

Triggered by: *"Give me a full marketing status update"* or *"executive summary"*

```
User → orchestrator
  → marketing_intel (briefing + anomalies) → transfer back
  → competitive_intel (competitor scan) → transfer back
  → customer_intel (sentiment overview) → transfer back
  → orchestrator synthesizes: executive summary with top risks, opportunities, action items
```

### 2. Competitive Threat Response

Triggered by: *"A competitor launched a new product, what should we do?"*

```
User → orchestrator
  → competitive_intel (detailed scan) → transfer back
  → customer_intel (sentiment impact) → transfer back
  → operations (pipeline health) → transfer back
  → orchestrator synthesizes: threat assessment + action plan
```

### 3. Lead & Pipeline Analysis

Triggered by: *"Analyze our leads and pipeline"*

```
User → orchestrator
  → customer_intel (lead scores + segments) → transfer back
  → operations (pipeline health + attribution) → transfer back
  → orchestrator synthesizes: prioritized recommendations
```

All workflows are logged to the database with each agent action tracked.

## Tech Stack

- **Agent Framework**: Google ADK v1.28.1
- **LLM (Orchestrator)**: Gemini 2.5 Pro
- **LLM (Sub-agents)**: Gemini 2.5 Flash
- **Tool Architecture**: FunctionTool (in-process Python functions)
- **API**: FastAPI + Uvicorn (via ADK's `get_fast_api_app()`)
- **Database**: SQLite (16 tables, 70K+ rows)
- **Language**: Python 3.14

## Quick Start

```bash
# Clone
git clone https://github.com/mufibra23/hack2skill-marketing-agents.git
cd hack2skill-marketing-agents

# Setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Configure
echo GOOGLE_GENAI_API_KEY=your-key-here > .env

# Initialize database and load data
python db/setup.py
python db/load_data.py

# Run with ADK Dev UI
adk web

# Or run as API server
python api_server.py
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | ADK health check |
| `GET` | `/status` | System status: agent count, tool count, database info |
| `GET` | `/agents` | Full agent hierarchy with tool lists |
| `GET` | `/workflows` | Recent workflow runs from database |
| `POST` | `/run` | Execute agent (ADK built-in) |
| `POST` | `/run_sse` | Execute agent with streaming (ADK built-in) |

## Project Structure

```
hack2skill-marketing-agents/
├── marketing_agents/
│   ├── __init__.py
│   ├── agent.py              # Root + 4 sub-agents (LlmAgent), dual-model config
│   └── tools.py              # 9 tool functions querying SQLite directly
├── tools/                    # Reference implementations from upstream projects
│   ├── briefing.py           # GA4 metrics pipeline (from P1)
│   ├── competitive.py        # Competitive intelligence (from P3)
│   ├── sentiment.py          # NLP sentiment analysis (from P8)
│   ├── lead_scoring.py       # XGBoost lead scoring (from P4)
│   ├── segmentation.py       # RFM + K-Means + CLV (from P5)
│   ├── pipeline_health.py    # CRM pipeline monitoring (from P7)
│   └── attribution.py        # 7 attribution models (from P6)
├── db/
│   ├── setup.py              # 16-table schema creation
│   ├── load_data.py          # Data loading pipeline from source projects
│   ├── db_utils.py           # SQLite helper functions
│   └── marketing_intel.db    # SQLite database (12 MB)
├── source_data/              # Bundled CSVs from upstream projects
├── api_server.py             # FastAPI deployment server
├── requirements.txt
├── .env                      # GOOGLE_GENAI_API_KEY (gitignored)
└── README.md
```
