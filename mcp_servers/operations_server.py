"""
Operations MCP Server — serves pre-computed pipeline health and attribution results.

Run:  python mcp_servers/operations_server.py
"""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

mcp = FastMCP("operations")


@mcp.tool()
def check_pipeline_health(api_url: str = "http://localhost:8000", api_key: str = "default-dev-key") -> str:
    """Check marketing data pipeline health: API status, BigQuery connectivity,
    data freshness, ETL config, and local file states. Returns errors and warnings."""
    return (DATA_DIR / "pipeline_health.json").read_text(encoding="utf-8")


@mcp.tool()
def get_attribution_analysis(query: str = "Which channel drives the most conversions?") -> str:
    """Run multi-model marketing attribution analysis (7 statistical + LSTM deep learning).
    Returns per-channel attribution, model agreement scores, budget recommendations,
    and model disagreements. Pass a natural language query to tailor the analysis."""
    return (DATA_DIR / "attribution.json").read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run(transport="stdio")
