"""
Marketing Intelligence API Server — wraps ADK agents as a FastAPI app with custom endpoints.

Run:  python api_server.py
"""

import os
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

app = get_fast_api_app(
    agents_dir=".",
    session_service_uri="sqlite:///./db/sessions.db",
    allow_origins=["*"],
    web=True,
)


@app.get("/status")
def status():
    return {
        "status": "healthy",
        "agents": 5,
        "mcp_servers": 5,
        "tools": 11,
        "database": "sqlite",
    }


@app.get("/workflows")
def workflows():
    from db.db_utils import get_recent_workflows
    return {"workflows": get_recent_workflows(limit=20)}


@app.get("/agents")
def agents():
    return {
        "orchestrator": {
            "name": "marketing_orchestrator",
            "model": "gemini-2.5-flash",
            "tools": ["log_workflow", "log_action", "get_recent_workflows", "create_task"],
            "sub_agents": [
                {
                    "name": "marketing_intel",
                    "tools": ["get_morning_briefing", "detect_anomalies"],
                },
                {
                    "name": "competitive_intel",
                    "tools": ["scan_competitors", "get_competitive_history"],
                },
                {
                    "name": "customer_intel",
                    "tools": ["analyze_sentiment", "score_leads", "get_customer_segments"],
                },
                {
                    "name": "operations",
                    "tools": ["check_pipeline_health", "get_attribution_analysis"],
                },
            ],
        }
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
