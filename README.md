# Marketing Intelligence Multi-Agent System

A multi-agent marketing intelligence platform built with **Google ADK v1.28.1** and **Gemini 2.5 Flash**. Five coordinated AI agents analyze marketing performance, competitive landscape, customer sentiment, lead quality, and operational health through 11 specialized tools served via MCP (Model Context Protocol) servers.

Built for the **Hack2Skill Gen AI Hackathon** (Google-sponsored).

## Architecture

```
                         ┌─────────────────────────┐
                         │  marketing_orchestrator  │
                         │      (root agent)        │
                         │   tools: database_server  │
                         └────────┬────────────────┘
                                  │
            ┌─────────────┬───────┴───────┬──────────────┐
            ▼             ▼               ▼              ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │marketing_intel│ │competitive_  │ │customer_intel│ │  operations  │
    │              │ │    intel     │ │              │ │              │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │                │                │                │
           ▼                ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  analytics   │ │ competitive  │ │   customer   │ │  operations  │
    │  MCP server  │ │  MCP server  │ │  MCP server  │ │  MCP server  │
    │  (2 tools)   │ │  (2 tools)   │ │  (3 tools)   │ │  (2 tools)   │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │                │                │                │
           ▼                ▼                ▼                ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                     data/ (pre-computed JSON)                    │
    │      briefing ∙ anomalies ∙ competitive ∙ sentiment ∙ leads     │
    │              segments ∙ pipeline ∙ attribution                   │
    └──────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │   SQLite DB  │
    │ workflow_runs │
    │ agent_actions │
    │    tasks     │
    │ query_results│
    └──────────────┘
```

## Core Requirements Met

| Requirement | Implementation |
|---|---|
| Multi-agent system with Google ADK | 5 LlmAgents (1 orchestrator + 4 specialized) using ADK's agent hierarchy |
| MCP servers with tool use | 5 MCP servers exposing 11 tools via FastMCP + stdio transport |
| Multi-step workflows | Root agent chains sub-agents for complex queries with synthesis |
| Database storage | SQLite with 4 tables: workflow_runs, agent_actions, tasks, query_results |
| API deployment | FastAPI server via ADK's get_fast_api_app() + custom endpoints |

## Agents

| Agent | Role | MCP Server | Tools |
|---|---|---|---|
| `marketing_orchestrator` | Root orchestrator, routes requests, chains workflows, logs to DB | database_server | `log_workflow`, `log_action`, `get_recent_workflows`, `create_task` |
| `marketing_intel` | Marketing analytics and anomaly detection | analytics_server | `get_morning_briefing`, `detect_anomalies` |
| `competitive_intel` | Competitor monitoring and market scanning | competitive_server | `scan_competitors`, `get_competitive_history` |
| `customer_intel` | Sentiment analysis, lead scoring, segmentation | customer_server | `analyze_sentiment`, `score_leads`, `get_customer_segments` |
| `operations` | Pipeline health and attribution analysis | operations_server | `check_pipeline_health`, `get_attribution_analysis` |

## Multi-Step Workflows

### 1. Full Marketing Status Update

Triggered by: *"Give me a full marketing status update"* or *"executive summary"*

```
marketing_intel (briefing + anomalies)
    → competitive_intel (competitor scan)
        → customer_intel (sentiment overview)
            → Synthesize: executive summary with top 3 risks, top 3 opportunities, action items
```

### 2. Competitive Threat Response

Triggered by: *"A competitor launched a new product, what should we do?"*

```
competitive_intel (detailed scan)
    → customer_intel (sentiment impact)
        → operations (pipeline health)
            → Synthesize: threat assessment + action plan
```

### 3. Lead & Pipeline Analysis

Triggered by: *"Analyze our leads and pipeline"*

```
customer_intel (lead scores + segments)
    → operations (pipeline health + attribution)
        → Synthesize: prioritized recommendations
```

All workflows are logged to the database with each agent action tracked.

## Tech Stack

- **Agent Framework**: Google ADK v1.28.1
- **LLM**: Gemini 2.5 Flash
- **MCP**: FastMCP (stdio transport)
- **API**: FastAPI + Uvicorn
- **Database**: SQLite
- **Language**: Python 3.14

## Quick Start

```bash
# Clone
git clone https://github.com/mufibra23/hack2skill-marketing-agents.git
cd hack2skill-marketing-agents

# Setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install google-adk==1.28.1

# Configure
echo GOOGLE_GENAI_API_KEY=your-key-here > .env

# Initialize database
python db/setup.py

# Pre-compute data (generates data/*.json from tools/)
# See tools/ for the underlying analytics scripts

# Run with ADK Dev UI
adk web

# Or run as API server
python api_server.py
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | ADK health check |
| `GET` | `/status` | System status: agent count, MCP servers, tools |
| `GET` | `/agents` | Full agent hierarchy with tool lists |
| `GET` | `/workflows` | Recent workflow runs from database |
| `POST` | `/run` | Execute agent (ADK built-in) |
| `POST` | `/run_sse` | Execute agent with streaming (ADK built-in) |

## Project Structure

```
hack2skill-marketing-agents/
├── marketing_agents/
│   ├── __init__.py
│   └── agent.py              # Agent hierarchy: root + 4 sub-agents with MCP toolsets
├── mcp_servers/
│   ├── analytics_server.py    # Morning briefing, anomaly detection
│   ├── competitive_server.py  # Competitor scanning, history
│   ├── customer_server.py     # Sentiment, lead scoring, segmentation
│   ├── operations_server.py   # Pipeline health, attribution
│   └── database_server.py     # Workflow logging, task management
├── tools/
│   ├── briefing.py            # Marketing briefing pipeline (from P1)
│   ├── competitive.py         # Competitive intelligence (from P2)
│   ├── sentiment.py           # Sentiment analysis (from P8)
│   ├── lead_scoring.py        # XGBoost lead scoring (from P4)
│   ├── segmentation.py        # Customer segmentation (from P5)
│   ├── pipeline_health.py     # Pipeline monitoring (from P7)
│   └── attribution.py         # Multi-model attribution (from P6)
├── db/
│   ├── __init__.py
│   ├── setup.py               # Database schema creation
│   └── db_utils.py            # Database helper functions
├── data/                      # Pre-computed JSON results (gitignored)
├── api_server.py              # FastAPI deployment server
├── .env                       # API keys (gitignored)
└── README.md
```
