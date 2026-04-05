"""
Analytics MCP Server — queries daily_metrics in SQLite for live briefing and anomaly detection.

Run:  python mcp_servers/analytics_server.py
"""

import json
import math
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "marketing_intel.db"

mcp = FastMCP("analytics")


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _query_daily_totals(limit=31):
    """Get daily aggregated metrics for the most recent `limit` days."""
    conn = _conn()
    rows = conn.execute(
        """
        SELECT date,
               SUM(users)      AS users,
               SUM(sessions)   AS sessions,
               SUM(page_views) AS page_views,
               SUM(purchases)  AS purchases,
               ROUND(SUM(revenue), 2) AS revenue
        FROM daily_metrics
        GROUP BY date
        ORDER BY date DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    # Return oldest-first for rolling window computation
    return [dict(r) for r in reversed(rows)]


def _compute_anomalies(daily_rows, window=7, warn_threshold=2.0, crit_threshold=3.0):
    """Compute z-score anomalies against a rolling window mean/std."""
    metrics = ["sessions", "users", "page_views", "purchases", "revenue"]
    anomalies = []

    for i, row in enumerate(daily_rows):
        # Need at least `window` prior days to compute a baseline
        if i < window:
            continue

        window_rows = daily_rows[i - window : i]

        for metric in metrics:
            values = [r[metric] for r in window_rows if r[metric] is not None]
            if len(values) < 3:
                continue

            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = math.sqrt(variance) if variance > 0 else 0

            current = row[metric]
            if current is None or std == 0:
                continue

            z = (current - mean) / std

            if abs(z) >= warn_threshold:
                severity = "CRITICAL" if abs(z) >= crit_threshold else "WARNING"
                pct_change = round((current - mean) / mean * 100, 1) if mean != 0 else 0
                direction = "above" if z > 0 else "below"
                anomalies.append({
                    "date": row["date"],
                    "metric": metric,
                    "value": current,
                    "rolling_avg": round(mean, 2),
                    "rolling_std": round(std, 2),
                    "z_score": round(z, 2),
                    "severity": severity,
                    "percent_change": pct_change,
                    "description": f"{metric} is {abs(pct_change)}% {direction} the 7-day average ({severity})",
                })

    return anomalies


@mcp.tool()
def get_morning_briefing() -> str:
    """Run the morning marketing briefing: query daily_metrics from SQLite,
    compute summary stats (totals, averages, best/worst days), and detect
    anomalies via z-score against 7-day rolling averages. Returns structured JSON."""
    daily = _query_daily_totals(31)

    if not daily:
        return json.dumps({"error": "No data in daily_metrics table"})

    # ── Period summary ────────────────────────────────────────────────
    n = len(daily)
    metrics = ["sessions", "users", "page_views", "purchases", "revenue"]
    totals = {}
    averages = {}
    best_days = {}
    worst_days = {}

    for m in metrics:
        vals = [(r["date"], r[m]) for r in daily if r[m] is not None]
        if not vals:
            continue
        total = sum(v for _, v in vals)
        totals[m] = round(total, 2)
        averages[m] = round(total / len(vals), 2)
        best = max(vals, key=lambda x: x[1])
        worst = min(vals, key=lambda x: x[1])
        best_days[m] = {"date": best[0], "value": best[1]}
        worst_days[m] = {"date": worst[0], "value": worst[1]}

    # Derived rates
    if totals.get("sessions", 0) > 0:
        averages["conversion_rate"] = round(totals.get("purchases", 0) / totals["sessions"] * 100, 3)
        averages["revenue_per_session"] = round(totals.get("revenue", 0) / totals["sessions"], 2)

    # ── Latest day snapshot ───────────────────────────────────────────
    latest = daily[-1]

    # ── Anomaly detection ─────────────────────────────────────────────
    anomalies = _compute_anomalies(daily)

    result = {
        "report_date": latest["date"],
        "period": {"start": daily[0]["date"], "end": daily[-1]["date"], "days": n},
        "latest_day": latest,
        "period_summary": {
            "totals": totals,
            "daily_averages": averages,
            "best_days": best_days,
            "worst_days": worst_days,
        },
        "anomalies": {
            "count": len(anomalies),
            "critical": sum(1 for a in anomalies if a["severity"] == "CRITICAL"),
            "warnings": sum(1 for a in anomalies if a["severity"] == "WARNING"),
            "details": anomalies,
        },
    }

    return json.dumps(result, indent=2)


@mcp.tool()
def detect_anomalies() -> str:
    """Run z-score anomaly detection on daily_metrics from SQLite.
    Returns ONLY the anomalies found — each with date, metric, value,
    rolling average, z-score, severity, and percent change."""
    daily = _query_daily_totals(31)

    if not daily:
        return json.dumps({"error": "No data in daily_metrics table"})

    anomalies = _compute_anomalies(daily)

    result = {
        "period": {"start": daily[0]["date"], "end": daily[-1]["date"]},
        "total_anomalies": len(anomalies),
        "critical": [a for a in anomalies if a["severity"] == "CRITICAL"],
        "warnings": [a for a in anomalies if a["severity"] == "WARNING"],
    }

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
