"""
Operations MCP Server — queries pipeline_runs, crm_contacts, attribution_results,
and journey_data in SQLite for live pipeline health and attribution analysis.

Run:  python mcp_servers/operations_server.py
"""

import json
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "marketing_intel.db"

mcp = FastMCP("operations")


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def check_pipeline_health() -> str:
    """Check marketing data pipeline health by querying pipeline_runs for ETL status
    and crm_contacts for deal pipeline metrics. Returns pipeline status
    (healthy/degraded), run history, and CRM deal funnel analysis."""
    conn = _conn()

    # ── Pipeline run stats ────────────────────────────────────────────
    total_runs = conn.execute("SELECT COUNT(*) AS n FROM pipeline_runs").fetchone()["n"]

    latest = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY run_date DESC LIMIT 1"
    ).fetchone()

    recent = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY run_date DESC LIMIT 7"
    ).fetchall()

    success_count = sum(1 for r in recent if r["status"] == "success")
    success_rate = round(success_count / len(recent) * 100, 1) if recent else 0

    avg_stats = conn.execute(
        """
        SELECT ROUND(AVG(rows_extracted), 0) AS avg_extracted,
               ROUND(AVG(rows_loaded), 0)    AS avg_loaded,
               ROUND(AVG(duration_seconds), 1) AS avg_duration,
               ROUND(MIN(rows_loaded), 0)    AS min_loaded,
               ROUND(MAX(rows_loaded), 0)    AS max_loaded
        FROM pipeline_runs
        """
    ).fetchone()

    failures = conn.execute(
        """
        SELECT run_date, status, error_message, rows_extracted, rows_loaded
        FROM pipeline_runs
        WHERE status != 'success'
        ORDER BY run_date DESC
        LIMIT 5
        """
    ).fetchall()

    # Health status
    if success_rate >= 90 and latest and latest["status"] == "success":
        health = "healthy"
    elif success_rate >= 70:
        health = "degraded"
    else:
        health = "critical"

    pipeline_status = {
        "health": health,
        "total_runs": total_runs,
        "last_run": {
            "date": latest["run_date"] if latest else None,
            "status": latest["status"] if latest else None,
            "rows_extracted": latest["rows_extracted"] if latest else None,
            "rows_loaded": latest["rows_loaded"] if latest else None,
            "duration_seconds": latest["duration_seconds"] if latest else None,
        },
        "last_7_runs": {
            "success_rate": success_rate,
            "successes": success_count,
            "failures": len(recent) - success_count,
        },
        "averages": {
            "avg_rows_extracted": avg_stats["avg_extracted"],
            "avg_rows_loaded": avg_stats["avg_loaded"],
            "avg_duration_seconds": avg_stats["avg_duration"],
            "min_rows_loaded": avg_stats["min_loaded"],
            "max_rows_loaded": avg_stats["max_loaded"],
        },
        "recent_failures": [dict(r) for r in failures],
        "recent_runs": [
            {
                "date": r["run_date"],
                "status": r["status"],
                "rows_loaded": r["rows_loaded"],
                "duration": r["duration_seconds"],
            }
            for r in recent
        ],
    }

    # ── CRM deal pipeline metrics ─────────────────────────────────────
    crm_total = conn.execute("SELECT COUNT(*) AS n FROM crm_contacts").fetchone()["n"]

    stage_dist = conn.execute(
        """
        SELECT lifecycle_stage,
               COUNT(*)              AS count,
               ROUND(SUM(deal_value), 2)  AS total_value,
               ROUND(AVG(deal_value), 2)  AS avg_value
        FROM crm_contacts
        GROUP BY lifecycle_stage
        ORDER BY count DESC
        """
    ).fetchall()

    pipeline_value = conn.execute(
        "SELECT ROUND(SUM(deal_value), 2) AS total FROM crm_contacts"
    ).fetchone()["total"]

    customers = conn.execute(
        "SELECT COUNT(*) AS n FROM crm_contacts WHERE lifecycle_stage = 'customer'"
    ).fetchone()["n"]

    avg_engagement = conn.execute(
        """
        SELECT ROUND(AVG(num_touches), 1) AS avg_touches,
               ROUND(AVG(email_opens), 1) AS avg_opens,
               ROUND(AVG(page_views), 1)  AS avg_views
        FROM crm_contacts
        """
    ).fetchone()

    industry_dist = conn.execute(
        """
        SELECT industry,
               COUNT(*) AS count,
               ROUND(SUM(deal_value), 2) AS total_value
        FROM crm_contacts
        GROUP BY industry
        ORDER BY total_value DESC
        """
    ).fetchall()

    conn.close()

    deal_pipeline = {
        "total_contacts": crm_total,
        "total_pipeline_value": pipeline_value,
        "conversion_rate": round(customers / crm_total * 100, 1) if crm_total > 0 else 0,
        "stage_distribution": [
            {
                "stage": r["lifecycle_stage"],
                "count": r["count"],
                "percent": round(r["count"] / crm_total * 100, 1),
                "total_value": r["total_value"],
                "avg_value": r["avg_value"],
            }
            for r in stage_dist
        ],
        "industry_breakdown": [
            {"industry": r["industry"], "count": r["count"], "total_value": r["total_value"]}
            for r in industry_dist
        ],
        "engagement_averages": dict(avg_engagement),
    }

    return json.dumps({"pipeline_status": pipeline_status, "deal_pipeline": deal_pipeline}, indent=2)


@mcp.tool()
def get_attribution_analysis(query: str = "Which channel drives the most conversions?") -> str:
    """Query attribution_results for per-channel weights across 7 models, and journey_data
    for conversion stats and channel frequency. Returns attribution comparison, journey
    insights, and model agreement analysis."""
    conn = _conn()

    # ── Attribution model results ─────────────────────────────────────
    models = conn.execute("SELECT * FROM attribution_results ORDER BY markov DESC").fetchall()

    model_names = ["first_click", "last_click", "linear", "time_decay", "position_based", "markov", "shapley"]

    channels = []
    for r in models:
        row = {"channel": r["channel"]}
        scores = []
        for m in model_names:
            val = round(r[m] * 100, 2)
            row[m] = val
            if val > 0:
                scores.append(val)
        row["avg_across_models"] = round(sum(scores) / len(scores), 2) if scores else 0
        channels.append(row)

    # Model agreement: std dev across models per channel (lower = more agreement)
    for ch in channels:
        vals = [ch[m] for m in model_names if ch[m] > 0]
        if len(vals) >= 2:
            mean = sum(vals) / len(vals)
            std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            ch["model_agreement"] = round(100 - std, 1)  # higher = more agreement
        else:
            ch["model_agreement"] = 100.0

    # ── Journey data insights ─────────────────────────────────────────
    journey_stats = conn.execute(
        """
        SELECT COUNT(*)              AS total_journeys,
               SUM(has_conversion)   AS conversions,
               ROUND(AVG(has_conversion) * 100, 2) AS conversion_rate,
               ROUND(AVG(journey_length), 1) AS avg_journey_length,
               MAX(journey_length)   AS max_journey_length,
               ROUND(AVG(CASE WHEN has_conversion = 1 THEN conversion_value ELSE NULL END), 2) AS avg_conversion_value
        FROM journey_data
        """
    ).fetchone()

    # Converting vs non-converting journey lengths
    conv_lengths = conn.execute(
        """
        SELECT has_conversion,
               ROUND(AVG(journey_length), 1) AS avg_length,
               COUNT(*) AS count
        FROM journey_data
        GROUP BY has_conversion
        """
    ).fetchall()

    # Channel frequency: how often each channel appears as first/last touch
    # Parse channel_list (pipe-separated)
    channel_freq = conn.execute(
        """
        SELECT channel_list FROM journey_data WHERE has_conversion = 1
        """
    ).fetchall()

    first_touch = {}
    last_touch = {}
    all_touches = {}
    for row in channel_freq:
        chs = row["channel_list"].split("|")
        if chs:
            ft = chs[0]
            lt = chs[-1]
            first_touch[ft] = first_touch.get(ft, 0) + 1
            last_touch[lt] = last_touch.get(lt, 0) + 1
            for c in chs:
                all_touches[c] = all_touches.get(c, 0) + 1

    total_conv = sum(first_touch.values()) if first_touch else 1

    # Sort by frequency
    first_touch_sorted = sorted(first_touch.items(), key=lambda x: -x[1])
    last_touch_sorted = sorted(last_touch.items(), key=lambda x: -x[1])
    all_touches_sorted = sorted(all_touches.items(), key=lambda x: -x[1])

    conn.close()

    result = {
        "query": query,
        "attribution_by_channel": channels,
        "journey_insights": {
            "total_journeys": journey_stats["total_journeys"],
            "conversions": journey_stats["conversions"],
            "conversion_rate": journey_stats["conversion_rate"],
            "avg_journey_length": journey_stats["avg_journey_length"],
            "max_journey_length": journey_stats["max_journey_length"],
            "avg_conversion_value": journey_stats["avg_conversion_value"],
            "converting_vs_non": [
                {"converted": bool(r["has_conversion"]), "avg_length": r["avg_length"], "count": r["count"]}
                for r in conv_lengths
            ],
        },
        "channel_frequency_in_conversions": {
            "first_touch": [
                {"channel": c, "count": n, "percent": round(n / total_conv * 100, 1)}
                for c, n in first_touch_sorted
            ],
            "last_touch": [
                {"channel": c, "count": n, "percent": round(n / total_conv * 100, 1)}
                for c, n in last_touch_sorted
            ],
            "all_touches": [
                {"channel": c, "total_appearances": n}
                for c, n in all_touches_sorted
            ],
        },
    }

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
