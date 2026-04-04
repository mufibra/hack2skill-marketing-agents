"""
Customer Intelligence MCP Server — serves pre-computed sentiment, lead scoring, and segmentation results.

Run:  python mcp_servers/customer_server.py
"""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

mcp = FastMCP("customer_intel")


@mcp.tool()
def analyze_sentiment() -> str:
    """Analyze customer sentiment from feedback and support tickets. Returns sentiment
    distribution, spike detection, worst categories, sample negative reviews, and
    recommended actions."""
    return (DATA_DIR / "customer_sentiment.json").read_text(encoding="utf-8")


@mcp.tool()
def score_leads(hot_threshold: float = 0.7) -> str:
    """Score leads using XGBoost model and return hot/warm/cold categorization with
    SHAP-based explanations for why each lead scored high or low."""
    return (DATA_DIR / "lead_scores.json").read_text(encoding="utf-8")


@mcp.tool()
def get_customer_segments() -> str:
    """Run customer segmentation analysis. Returns segment summaries, shift detection,
    campaign triggers, and recommended actions for each segment."""
    return (DATA_DIR / "segments.json").read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run(transport="stdio")
