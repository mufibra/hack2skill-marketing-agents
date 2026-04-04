"""
Analytics MCP Server — serves pre-computed morning briefing and anomaly detection results.

Run:  python mcp_servers/analytics_server.py
"""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

mcp = FastMCP("analytics")


@mcp.tool()
def get_morning_briefing() -> str:
    """Run the morning marketing briefing pipeline and return a structured JSON report
    with metrics summary, anomaly detection results, and period analysis."""
    return (DATA_DIR / "briefing_results.json").read_text(encoding="utf-8")


@mcp.tool()
def detect_anomalies() -> str:
    """Run anomaly detection on marketing metrics and return only the anomalies found,
    including severity, z-scores, and descriptions."""
    return (DATA_DIR / "anomalies_results.json").read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run(transport="stdio")
