"""
Morning Marketing Briefing — Capability 1 of OpenClaw Marketing Agent (P10).

Wraps P1's marketing intelligence pipeline to produce a structured JSON
briefing with metrics summary, anomaly detection, and AI analysis.

Usage:
    python scripts/briefing.py --output json
    python scripts/briefing.py
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Add P1's src/ to import path
P1_SRC = Path(r"C:\Users\ahmad\Downloads\Hack2Skill\marketing-intelligence-agent\src")
if str(P1_SRC) not in sys.path:
    sys.path.insert(0, str(P1_SRC))


# ---------------------------------------------------------------------------
# Sample / fallback data (used when BigQuery credentials are unavailable)
# ---------------------------------------------------------------------------

def _generate_sample_data():
    """Generate realistic sample data matching P1's fetch_aggregated_daily() output."""
    import pandas as pd
    import numpy as np

    np.random.seed(42)
    dates = pd.date_range("2021-01-01", periods=31, freq="D")

    sessions = np.random.randint(800, 1500, size=31)
    users = (sessions * np.random.uniform(0.7, 0.9, size=31)).astype(int)
    page_views = (sessions * np.random.uniform(2.5, 4.0, size=31)).astype(int)
    purchases = np.random.randint(5, 30, size=31)
    revenue = (purchases * np.random.uniform(15.0, 80.0, size=31)).round(2)

    # Inject a spike on Jan 18 to trigger an anomaly
    sessions[17] = 3200
    users[17] = 2800
    page_views[17] = 9500
    purchases[17] = 65
    revenue[17] = 4200.0

    daily = pd.DataFrame({
        "date": dates,
        "users": users,
        "sessions": sessions,
        "page_views": page_views,
        "purchases": purchases,
        "revenue": revenue,
    })
    daily["conversion_rate"] = (daily["purchases"] / daily["sessions"] * 100).round(2)
    daily["revenue_per_session"] = (daily["revenue"] / daily["sessions"]).round(2)
    return daily


def _generate_sample_channel_data():
    """Generate sample channel-level data matching P1's fetch_daily_metrics() output."""
    import pandas as pd
    import numpy as np

    np.random.seed(42)
    dates = pd.date_range("2021-01-01", periods=31, freq="D")
    channels = [
        ("google", "organic"),
        ("(direct)", "(none)"),
        ("referral", "referral"),
        ("google", "cpc"),
    ]

    rows = []
    for date in dates:
        for source, medium in channels:
            sessions = int(np.random.randint(100, 400))
            rows.append({
                "date": date,
                "source": source,
                "medium": medium,
                "users": int(sessions * np.random.uniform(0.7, 0.9)),
                "sessions": sessions,
                "page_views": int(sessions * np.random.uniform(2.5, 4.0)),
                "purchases": int(np.random.randint(1, 10)),
                "revenue": round(np.random.uniform(50, 500), 2),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Core briefing logic
# ---------------------------------------------------------------------------

def _create_metrics_summary(daily_df) -> dict:
    """Create a summary dict from the aggregated daily DataFrame (inlined from P1 ai_analyzer)."""
    return {
        "period": f"{daily_df['date'].min().strftime('%Y-%m-%d')} to {daily_df['date'].max().strftime('%Y-%m-%d')}",
        "total_days": len(daily_df),
        "total_sessions": int(daily_df["sessions"].sum()),
        "total_users": int(daily_df["users"].sum()),
        "total_page_views": int(daily_df["page_views"].sum()),
        "total_purchases": int(daily_df["purchases"].sum()),
        "total_revenue": float(daily_df["revenue"].sum()),
        "avg_daily_sessions": int(daily_df["sessions"].mean()),
        "avg_daily_revenue": round(float(daily_df["revenue"].mean()), 2),
        "avg_conversion_rate": round(float(daily_df["conversion_rate"].mean()), 2),
        "best_day_revenue": {
            "date": daily_df.loc[daily_df["revenue"].idxmax(), "date"].strftime("%Y-%m-%d"),
            "revenue": float(daily_df["revenue"].max()),
        },
        "worst_day_revenue": {
            "date": daily_df.loc[daily_df["revenue"].idxmin(), "date"].strftime("%Y-%m-%d"),
            "revenue": float(daily_df["revenue"].min()),
        },
    }


def run_briefing() -> dict:
    """
    Run the morning briefing pipeline.

    Returns a structured dict with:
      - generated_at, period
      - metrics_summary
      - anomalies (list of dicts)
      - anomaly_summary (human-readable string)
    """
    from anomaly_detector import detect_anomalies, summarize_anomalies

    # --- Fetch data (BigQuery or fallback) ---
    try:
        from data_fetcher import fetch_aggregated_daily
        daily = fetch_aggregated_daily()
        data_source = "bigquery"
    except Exception as e:
        print(f"[briefing] BigQuery unavailable ({e}), using sample data.", file=sys.stderr)
        daily = _generate_sample_data()
        data_source = "sample"

    # --- Anomaly detection ---
    anomalies_df = detect_anomalies(daily)
    anomaly_summary = summarize_anomalies(anomalies_df)

    # --- Metrics summary ---
    metrics_summary = _create_metrics_summary(daily)

    # --- Build anomaly records ---
    anomaly_records = []
    if len(anomalies_df) > 0:
        for _, row in anomalies_df.iterrows():
            anomaly_records.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "metric": row["metric"],
                "value": row["value"],
                "rolling_avg": row["rolling_avg"],
                "z_score": row["z_score"],
                "severity": row["severity"],
                "pct_change": row["pct_change"],
                "direction": row["direction"],
                "description": row["description"],
            })

    briefing = {
        "generated_at": datetime.now().isoformat(),
        "data_source": data_source,
        "period": metrics_summary.get("period", "unknown"),
        "metrics_summary": metrics_summary,
        "anomalies": anomaly_records,
        "anomaly_count": len(anomaly_records),
        "critical_count": sum(1 for a in anomaly_records if a["severity"] == "CRITICAL"),
        "warning_count": sum(1 for a in anomaly_records if a["severity"] == "WARNING"),
        "anomaly_summary": anomaly_summary,
    }

    return briefing


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Morning Marketing Briefing (P10 Capability 1)")
    parser.add_argument("--output", choices=["json", "text"], default="text",
                        help="Output format: json (structured) or text (human-readable)")
    args = parser.parse_args()

    briefing = run_briefing()

    if args.output == "json":
        print(json.dumps(briefing, indent=2, default=str))
    else:
        print("=" * 60)
        print("MORNING MARKETING BRIEFING")
        print(f"Generated: {briefing['generated_at']}")
        print(f"Data source: {briefing['data_source']}")
        print(f"Period: {briefing['period']}")
        print("=" * 60)
        print()
        print("METRICS SUMMARY")
        print("-" * 40)
        ms = briefing["metrics_summary"]
        print(f"  Sessions:        {ms['total_sessions']:,}")
        print(f"  Users:           {ms['total_users']:,}")
        print(f"  Page Views:      {ms['total_page_views']:,}")
        print(f"  Purchases:       {ms['total_purchases']:,}")
        print(f"  Revenue:         ${ms['total_revenue']:,.2f}")
        print(f"  Avg Daily Rev:   ${ms['avg_daily_revenue']:,.2f}")
        print(f"  Conversion Rate: {ms['avg_conversion_rate']:.2f}%")
        print()
        print("ANOMALY REPORT")
        print("-" * 40)
        print(briefing["anomaly_summary"])


if __name__ == "__main__":
    main()
