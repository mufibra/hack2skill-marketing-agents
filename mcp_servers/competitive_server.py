"""
Competitive Intelligence MCP Server — serves pre-computed competitor scan results.

Run:  python mcp_servers/competitive_server.py
"""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

mcp = FastMCP("competitive_intel")


@mcp.tool()
def scan_competitors(competitors: str = "shopify,woocommerce,bigcommerce") -> str:
    """Scan competitors for share of voice, sentiment, citation quality, and detect
    changes from previous scans. Pass comma-separated competitor names."""
    return (DATA_DIR / "competitive_results.json").read_text(encoding="utf-8")


@mcp.tool()
def get_competitive_history() -> str:
    """Return historical competitive scan data including past scans and trends."""
    return (DATA_DIR / "competitive_history.json").read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run(transport="stdio")
