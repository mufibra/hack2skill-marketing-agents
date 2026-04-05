"""
Competitive Intelligence MCP Server — queries competitive_* tables in SQLite for live
share-of-voice, sentiment, citation quality, and historical trend analysis.

Run:  python mcp_servers/competitive_server.py
"""

import json
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "marketing_intel.db"

mcp = FastMCP("competitive_intel")

SENTIMENT_SCORE = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _brand_metrics(conn, platform_filter=None):
    """Compute per-brand metrics from competitive_citations.

    Returns dict keyed by brand with citation_count, share_of_voice,
    avg_sentiment, avg_position, quality_score, and sentiment breakdown.
    """
    where = ""
    params = ()
    if platform_filter:
        where = "WHERE resp.platform = ?"
        params = (platform_filter,)

    rows = conn.execute(
        f"""
        SELECT c.brand_mentioned,
               COUNT(*)                          AS citation_count,
               AVG(CASE WHEN c.sentiment = 'positive' THEN 1.0
                        WHEN c.sentiment = 'negative' THEN -1.0
                        ELSE 0.0 END)            AS avg_sentiment,
               AVG(c.position)                   AS avg_position,
               SUM(CASE WHEN c.sentiment = 'positive' THEN 1 ELSE 0 END) AS positive,
               SUM(CASE WHEN c.sentiment = 'neutral'  THEN 1 ELSE 0 END) AS neutral,
               SUM(CASE WHEN c.sentiment = 'negative' THEN 1 ELSE 0 END) AS negative
        FROM competitive_citations c
        JOIN competitive_responses resp ON resp.id = c.response_id
        {where}
        GROUP BY c.brand_mentioned
        ORDER BY citation_count DESC
        """,
        params,
    ).fetchall()

    total_citations = sum(r["citation_count"] for r in rows) if rows else 1

    brands = {}
    for r in rows:
        count = r["citation_count"]
        avg_pos = r["avg_position"] or 3.0
        # Quality score: higher citations + lower position + positive sentiment = better
        # Normalize position: 1 is best (score 1.0), 6 is worst (score ~0.17)
        position_score = 1.0 / avg_pos if avg_pos > 0 else 0
        sentiment_norm = (r["avg_sentiment"] + 1) / 2  # map [-1,1] to [0,1]
        sov = count / total_citations
        quality_score = round((sov * 0.4 + position_score * 0.3 + sentiment_norm * 0.3) * 100, 1)

        brands[r["brand_mentioned"]] = {
            "citation_count": count,
            "share_of_voice": round(sov * 100, 2),
            "avg_sentiment": round(r["avg_sentiment"], 3),
            "avg_position": round(avg_pos, 2),
            "quality_score": quality_score,
            "sentiment_breakdown": {
                "positive": r["positive"],
                "neutral": r["neutral"],
                "negative": r["negative"],
            },
        }

    return brands


@mcp.tool()
def scan_competitors(competitors: str = "HubSpot,Salesforce,Zoho CRM,Pipedrive,Attio,Close,Freshsales") -> str:
    """Scan competitors for share of voice, sentiment, citation quality, and detect
    changes across platforms. Pass comma-separated competitor/brand names to filter,
    or omit for all tracked brands."""
    conn = _conn()

    # Get overall brand metrics
    all_brands = _brand_metrics(conn)

    # Filter to requested competitors (case-insensitive match)
    requested = [c.strip() for c in competitors.split(",")]
    matched = {}
    for req in requested:
        for brand, data in all_brands.items():
            if brand.lower() == req.lower():
                matched[brand] = data
                break

    # If no matches, return all brands
    if not matched:
        matched = all_brands

    # Per-platform breakdown for change detection
    platforms = [r[0] for r in conn.execute(
        "SELECT DISTINCT platform FROM competitive_responses"
    ).fetchall()]

    platform_comparison = {}
    for platform in platforms:
        platform_comparison[platform] = _brand_metrics(conn, platform_filter=platform)

    # Detect cross-platform differences (compare platforms against each other)
    changes = []
    if len(platforms) >= 2:
        p1, p2 = platforms[0], platforms[1]
        m1 = platform_comparison.get(p1, {})
        m2 = platform_comparison.get(p2, {})
        all_brand_names = set(list(m1.keys()) + list(m2.keys()))
        for brand in all_brand_names:
            b1 = m1.get(brand, {})
            b2 = m2.get(brand, {})
            sov1 = b1.get("share_of_voice", 0)
            sov2 = b2.get("share_of_voice", 0)
            diff = round(sov2 - sov1, 2)
            if abs(diff) > 2.0:
                changes.append({
                    "brand": brand,
                    "metric": "share_of_voice",
                    "platform_a": p1,
                    "platform_b": p2,
                    "value_a": sov1,
                    "value_b": sov2,
                    "difference": diff,
                    "note": f"{brand} SoV differs by {abs(diff)}pp between {p1} and {p2}",
                })

    # Run metadata
    runs = conn.execute(
        "SELECT * FROM competitive_runs ORDER BY run_date DESC LIMIT 5"
    ).fetchall()
    run_info = [dict(r) for r in runs]

    # Prompt category coverage
    categories = conn.execute(
        "SELECT category, COUNT(*) AS cnt FROM competitive_prompts GROUP BY category ORDER BY cnt DESC"
    ).fetchall()

    conn.close()

    result = {
        "scan_summary": {
            "total_citations": sum(b["citation_count"] for b in matched.values()),
            "brands_tracked": len(matched),
            "platforms": platforms,
            "prompt_categories": {r["category"]: r["cnt"] for r in categories},
        },
        "brand_analysis": matched,
        "platform_breakdown": platform_comparison,
        "cross_platform_changes": changes,
        "recent_runs": run_info,
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def get_competitive_history() -> str:
    """Return historical competitive scan data: past run timestamps,
    per-run citation counts by brand, and trend data across scans."""
    conn = _conn()

    # All runs
    runs = conn.execute(
        "SELECT * FROM competitive_runs ORDER BY run_date"
    ).fetchall()

    # Per-platform brand trends (since runs map to platforms)
    history = []
    for run in runs:
        platform = run["platform"]
        brand_data = conn.execute(
            """
            SELECT c.brand_mentioned,
                   COUNT(*)  AS citations,
                   AVG(CASE WHEN c.sentiment = 'positive' THEN 1.0
                            WHEN c.sentiment = 'negative' THEN -1.0
                            ELSE 0.0 END) AS avg_sentiment,
                   AVG(c.position) AS avg_position
            FROM competitive_citations c
            JOIN competitive_responses resp ON resp.id = c.response_id
            WHERE resp.platform = ?
            GROUP BY c.brand_mentioned
            ORDER BY citations DESC
            """,
            (platform,),
        ).fetchall()

        total = sum(r["citations"] for r in brand_data) if brand_data else 1

        history.append({
            "run_id": run["id"],
            "run_date": run["run_date"],
            "platform": platform,
            "prompts_sent": run["prompts_sent"],
            "success_count": run["success_count"],
            "error_count": run["error_count"],
            "brands": {
                r["brand_mentioned"]: {
                    "citations": r["citations"],
                    "share_of_voice": round(r["citations"] / total * 100, 2),
                    "avg_sentiment": round(r["avg_sentiment"], 3),
                    "avg_position": round(r["avg_position"], 2),
                }
                for r in brand_data
            },
        })

    # Overall trend summary: which brands are gaining/losing across runs
    conn.close()

    result = {
        "total_runs": len(history),
        "history": history,
    }

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
