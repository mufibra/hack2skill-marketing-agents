"""Plain Python tool functions for ADK FunctionTool.

Each function queries SQLite directly and returns a dict.
ADK auto-wraps these as FunctionTool and serializes return values to JSON.
"""

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "marketing_intel.db"


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ═══════════════════════════════════════════════════════════════════════
# ANALYTICS TOOLS (from mcp_servers/analytics_server.py)
# ═══════════════════════════════════════════════════════════════════════

def _query_daily_totals(limit=31):
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
    return [dict(r) for r in reversed(rows)]


def _compute_anomalies(daily_rows, window=7, warn_threshold=2.0, crit_threshold=3.0):
    metrics = ["sessions", "users", "page_views", "purchases", "revenue"]
    anomalies = []

    for i, row in enumerate(daily_rows):
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


def get_morning_briefing() -> dict:
    """Get the morning marketing briefing with period summary and anomaly detection.

    Returns totals, daily averages, conversion rate, revenue per session,
    best/worst days, and all anomalies detected via z-score analysis."""
    daily = _query_daily_totals(31)

    if not daily:
        return {"error": "No data in daily_metrics table"}

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

    if totals.get("sessions", 0) > 0:
        averages["conversion_rate"] = round(totals.get("purchases", 0) / totals["sessions"] * 100, 3)
        averages["revenue_per_session"] = round(totals.get("revenue", 0) / totals["sessions"], 2)

    latest = daily[-1]
    anomalies = _compute_anomalies(daily)

    return {
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


def detect_anomalies() -> dict:
    """Detect statistical anomalies in marketing metrics using z-score analysis.

    Returns only the anomalies found, each with date, metric, value,
    rolling average, z-score, severity (WARNING or CRITICAL), and percent change."""
    daily = _query_daily_totals(31)

    if not daily:
        return {"error": "No data in daily_metrics table"}

    anomalies = _compute_anomalies(daily)

    return {
        "period": {"start": daily[0]["date"], "end": daily[-1]["date"]},
        "total_anomalies": len(anomalies),
        "critical": [a for a in anomalies if a["severity"] == "CRITICAL"],
        "warnings": [a for a in anomalies if a["severity"] == "WARNING"],
    }


# ═══════════════════════════════════════════════════════════════════════
# COMPETITIVE TOOLS (from mcp_servers/competitive_server.py)
# ═══════════════════════════════════════════════════════════════════════

def _brand_metrics(conn, platform_filter=None):
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
        position_score = 1.0 / avg_pos if avg_pos > 0 else 0
        sentiment_norm = (r["avg_sentiment"] + 1) / 2
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


def scan_competitors(competitors: str = "") -> dict:
    """Scan the competitive landscape for share-of-voice, sentiment, and citation quality.

    Pass comma-separated brand names to filter (e.g. 'HubSpot,Salesforce'),
    or leave empty for all tracked brands. Returns per-brand analysis,
    platform breakdown, and cross-platform differences."""
    conn = _conn()

    all_brands = _brand_metrics(conn)

    matched = {}
    if competitors.strip():
        requested = [c.strip() for c in competitors.split(",")]
        for req in requested:
            for brand, data in all_brands.items():
                if brand.lower() == req.lower():
                    matched[brand] = data
                    break
    if not matched:
        matched = all_brands

    platforms = [r[0] for r in conn.execute(
        "SELECT DISTINCT platform FROM competitive_responses"
    ).fetchall()]

    platform_comparison = {}
    for platform in platforms:
        platform_comparison[platform] = _brand_metrics(conn, platform_filter=platform)

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

    runs = conn.execute(
        "SELECT * FROM competitive_runs ORDER BY run_date DESC LIMIT 5"
    ).fetchall()
    run_info = [dict(r) for r in runs]

    categories = conn.execute(
        "SELECT category, COUNT(*) AS cnt FROM competitive_prompts GROUP BY category ORDER BY cnt DESC"
    ).fetchall()

    conn.close()

    return {
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


def get_competitive_history() -> dict:
    """Get historical competitive scan data showing trends over time.

    Returns past scan timestamps and per-run brand metrics including
    citation counts, share-of-voice, sentiment, and position."""
    conn = _conn()

    runs = conn.execute(
        "SELECT * FROM competitive_runs ORDER BY run_date"
    ).fetchall()

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

    conn.close()

    return {
        "total_runs": len(history),
        "history": history,
    }


# ═══════════════════════════════════════════════════════════════════════
# CUSTOMER TOOLS (from mcp_servers/customer_server.py)
# ═══════════════════════════════════════════════════════════════════════

def analyze_sentiment() -> dict:
    """Analyze customer sentiment from 10,000 support tickets.

    Returns sentiment distribution, per-category breakdown with negativity
    ranking, high-priority negative tickets, resolution stats, and plan breakdown."""
    conn = _conn()

    total = conn.execute("SELECT COUNT(*) AS n FROM support_tickets").fetchone()["n"]
    if total == 0:
        conn.close()
        return {"error": "No support tickets in database"}

    dist = conn.execute(
        "SELECT sentiment_label, COUNT(*) AS count FROM support_tickets GROUP BY sentiment_label"
    ).fetchall()

    sentiment_dist = {}
    sentiment_score = 0.0
    score_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
    for r in dist:
        label = r["sentiment_label"]
        cnt = r["count"]
        sentiment_dist[label] = {"count": cnt, "percent": round(cnt / total * 100, 1)}
        sentiment_score += score_map.get(label, 0) * cnt
    sentiment_score = round(sentiment_score / total, 3)

    cats = conn.execute(
        """
        SELECT category,
               COUNT(*) AS total,
               SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative,
               SUM(CASE WHEN sentiment_label = 'neutral'  THEN 1 ELSE 0 END) AS neutral,
               SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) AS positive,
               ROUND(AVG(days_to_resolve), 1) AS avg_resolve_days
        FROM support_tickets
        GROUP BY category
        ORDER BY negative DESC
        """
    ).fetchall()

    categories = []
    for r in cats:
        cat_total = r["total"]
        categories.append({
            "category": r["category"],
            "total_tickets": cat_total,
            "negative_count": r["negative"],
            "negative_percent": round(r["negative"] / cat_total * 100, 1),
            "neutral_count": r["neutral"],
            "positive_count": r["positive"],
            "avg_resolve_days": r["avg_resolve_days"],
        })

    high_neg = conn.execute(
        """
        SELECT ticket_id, customer_id, customer_name, customer_plan,
               category, text, resolution_status, days_to_resolve
        FROM support_tickets
        WHERE sentiment_label = 'negative' AND priority = 'high'
        ORDER BY days_to_resolve DESC
        LIMIT 10
        """
    ).fetchall()

    resolution = conn.execute(
        """
        SELECT resolution_status, COUNT(*) AS count,
               ROUND(AVG(days_to_resolve), 1) AS avg_days
        FROM support_tickets GROUP BY resolution_status
        """
    ).fetchall()

    plans = conn.execute(
        """
        SELECT customer_plan, COUNT(*) AS total,
               SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative,
               ROUND(AVG(days_to_resolve), 1) AS avg_resolve_days
        FROM support_tickets GROUP BY customer_plan ORDER BY total DESC
        """
    ).fetchall()

    conn.close()

    return {
        "total_tickets": total,
        "overall_sentiment_score": sentiment_score,
        "sentiment_distribution": sentiment_dist,
        "categories_by_negativity": categories,
        "resolution_stats": [dict(r) for r in resolution],
        "plan_breakdown": [
            {
                "plan": r["customer_plan"],
                "total": r["total"],
                "negative_count": r["negative"],
                "negative_percent": round(r["negative"] / r["total"] * 100, 1),
                "avg_resolve_days": r["avg_resolve_days"],
            }
            for r in plans
        ],
        "high_priority_negatives": [dict(r) for r in high_neg],
    }


def score_leads(hot_threshold: float = 80.0, warm_threshold: float = 50.0) -> dict:
    """Score and classify leads as hot, warm, or cold based on XGBoost predictions.

    Args:
        hot_threshold: Score above this is hot (default 80).
        warm_threshold: Score above this but below hot is warm (default 50).

    Returns distribution, conversion accuracy (93.8%), feature insights,
    and top hot leads."""
    conn = _conn()

    total = conn.execute("SELECT COUNT(*) AS n FROM scored_leads").fetchone()["n"]
    if total == 0:
        conn.close()
        return {"error": "No scored leads in database"}

    buckets = conn.execute(
        """
        SELECT
            SUM(CASE WHEN lead_score >= ? THEN 1 ELSE 0 END) AS hot,
            SUM(CASE WHEN lead_score >= ? AND lead_score < ? THEN 1 ELSE 0 END) AS warm,
            SUM(CASE WHEN lead_score < ? THEN 1 ELSE 0 END) AS cold
        FROM scored_leads
        """,
        (hot_threshold, warm_threshold, hot_threshold, warm_threshold),
    ).fetchone()

    distribution = {
        "hot": {"count": buckets["hot"], "percent": round(buckets["hot"] / total * 100, 1)},
        "warm": {"count": buckets["warm"], "percent": round(buckets["warm"] / total * 100, 1)},
        "cold": {"count": buckets["cold"], "percent": round(buckets["cold"] / total * 100, 1)},
    }

    stats = conn.execute(
        """
        SELECT ROUND(MIN(lead_score), 1) AS min_score,
               ROUND(MAX(lead_score), 1) AS max_score,
               ROUND(AVG(lead_score), 1) AS avg_score
        FROM scored_leads
        """
    ).fetchone()

    accuracy = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN actual_converted = predicted_converted THEN 1 ELSE 0 END) AS correct,
            SUM(actual_converted) AS actual_conversions,
            SUM(predicted_converted) AS predicted_conversions
        FROM scored_leads
        """
    ).fetchone()

    top_leads = conn.execute(
        """
        SELECT id, lead_source, current_occupation, tags,
               website_engagement_level, lead_score, predicted_proba,
               actual_converted, total_time_spent, engagement_score
        FROM scored_leads
        WHERE lead_score >= ?
        ORDER BY lead_score DESC
        LIMIT 15
        """,
        (hot_threshold,),
    ).fetchall()

    feature_insights = {}

    sources = conn.execute(
        "SELECT lead_source, COUNT(*) AS cnt FROM scored_leads WHERE lead_score >= ? GROUP BY lead_source ORDER BY cnt DESC LIMIT 5",
        (hot_threshold,),
    ).fetchall()
    feature_insights["top_lead_sources"] = {r["lead_source"]: r["cnt"] for r in sources}

    eng = conn.execute(
        "SELECT website_engagement_level, COUNT(*) AS cnt FROM scored_leads WHERE lead_score >= ? GROUP BY website_engagement_level ORDER BY cnt DESC",
        (hot_threshold,),
    ).fetchall()
    feature_insights["engagement_levels"] = {r["website_engagement_level"]: r["cnt"] for r in eng}

    tags = conn.execute(
        "SELECT tags, COUNT(*) AS cnt FROM scored_leads WHERE lead_score >= ? GROUP BY tags ORDER BY cnt DESC LIMIT 5",
        (hot_threshold,),
    ).fetchall()
    feature_insights["top_tags"] = {r["tags"]: r["cnt"] for r in tags}

    hot_vs_cold = conn.execute(
        """
        SELECT
            CASE WHEN lead_score >= ? THEN 'hot' ELSE 'cold' END AS bucket,
            ROUND(AVG(total_time_spent), 0) AS avg_time_spent,
            ROUND(AVG(page_views_per_visit), 1) AS avg_page_views,
            ROUND(AVG(engagement_score), 0) AS avg_engagement,
            ROUND(AVG(total_visits), 1) AS avg_visits
        FROM scored_leads
        WHERE lead_score >= ? OR lead_score < ?
        GROUP BY bucket
        """,
        (hot_threshold, hot_threshold, warm_threshold),
    ).fetchall()
    feature_insights["hot_vs_cold_engagement"] = {r["bucket"]: dict(r) for r in hot_vs_cold}

    conn.close()

    return {
        "total_leads": total,
        "thresholds": {"hot": hot_threshold, "warm": warm_threshold},
        "score_stats": dict(stats),
        "distribution": distribution,
        "conversion_accuracy": {
            "total": accuracy["total"],
            "correct_predictions": accuracy["correct"],
            "accuracy_percent": round(accuracy["correct"] / accuracy["total"] * 100, 1),
            "actual_conversions": accuracy["actual_conversions"],
            "predicted_conversions": accuracy["predicted_conversions"],
        },
        "feature_insights": feature_insights,
        "top_hot_leads": [dict(r) for r in top_leads],
    }


def get_customer_segments() -> dict:
    """Get customer segmentation with RFM scores, K-Means clusters, and CLV predictions.

    Returns per-segment stats, per-cluster stats, CLV tier distribution,
    top 10 highest-value customers, and at-risk high-value customers."""
    conn = _conn()

    total = conn.execute("SELECT COUNT(*) AS n FROM customer_segments").fetchone()["n"]
    if total == 0:
        conn.close()
        return {"error": "No customer segments in database"}

    segments = conn.execute(
        """
        SELECT segment, COUNT(*) AS count,
               ROUND(AVG(recency), 0) AS avg_recency,
               ROUND(AVG(frequency), 1) AS avg_frequency,
               ROUND(AVG(monetary), 0) AS avg_monetary,
               ROUND(AVG(clv), 0) AS avg_clv,
               ROUND(AVG(prob_alive), 3) AS avg_prob_alive
        FROM customer_segments GROUP BY segment ORDER BY avg_clv DESC
        """
    ).fetchall()

    segment_list = []
    for r in segments:
        segment_list.append({
            "segment": r["segment"],
            "count": r["count"],
            "percent": round(r["count"] / total * 100, 1),
            "avg_recency_days": r["avg_recency"],
            "avg_frequency": r["avg_frequency"],
            "avg_monetary": r["avg_monetary"],
            "avg_clv": r["avg_clv"],
            "avg_prob_alive": r["avg_prob_alive"],
        })

    clusters = conn.execute(
        """
        SELECT cluster_name, cluster_action, COUNT(*) AS count,
               ROUND(AVG(recency), 0) AS avg_recency,
               ROUND(AVG(frequency), 1) AS avg_frequency,
               ROUND(AVG(monetary), 0) AS avg_monetary,
               ROUND(AVG(clv), 0) AS avg_clv
        FROM customer_segments GROUP BY cluster_name ORDER BY avg_clv DESC
        """
    ).fetchall()

    cluster_list = [
        {
            "cluster": r["cluster_name"],
            "action": r["cluster_action"],
            "count": r["count"],
            "percent": round(r["count"] / total * 100, 1),
            "avg_recency_days": r["avg_recency"],
            "avg_frequency": r["avg_frequency"],
            "avg_monetary": r["avg_monetary"],
            "avg_clv": r["avg_clv"],
        }
        for r in clusters
    ]

    tiers = conn.execute(
        """
        SELECT CASE WHEN clv_tier = '' OR clv_tier IS NULL THEN 'No CLV (one-time)'
                    ELSE clv_tier END AS tier,
               COUNT(*) AS count,
               ROUND(AVG(clv), 0) AS avg_clv,
               ROUND(SUM(clv), 0) AS total_clv
        FROM customer_segments GROUP BY tier ORDER BY avg_clv DESC
        """
    ).fetchall()

    clv_tiers = [
        {
            "tier": r["tier"],
            "count": r["count"],
            "percent": round(r["count"] / total * 100, 1),
            "avg_clv": r["avg_clv"],
            "total_clv": r["total_clv"],
        }
        for r in tiers
    ]

    top_customers = conn.execute(
        """
        SELECT customer_id, segment, cluster_name, clv, clv_tier,
               prob_alive, recency, frequency, monetary
        FROM customer_segments WHERE clv IS NOT NULL
        ORDER BY clv DESC LIMIT 10
        """
    ).fetchall()

    at_risk = conn.execute(
        """
        SELECT customer_id, segment, cluster_name, clv, clv_tier,
               prob_alive, recency, frequency, monetary
        FROM customer_segments
        WHERE clv IS NOT NULL
          AND clv_tier IN ('Platinum', 'High')
          AND (prob_alive < 0.5 OR recency > 200)
        ORDER BY clv DESC LIMIT 10
        """
    ).fetchall()

    conn.close()

    return {
        "total_customers": total,
        "rfm_segments": segment_list,
        "clusters": cluster_list,
        "clv_tiers": clv_tiers,
        "top_customers": [dict(r) for r in top_customers],
        "at_risk_high_value": [dict(r) for r in at_risk],
    }


# ═══════════════════════════════════════════════════════════════════════
# OPERATIONS TOOLS (from mcp_servers/operations_server.py)
# ═══════════════════════════════════════════════════════════════════════

def check_pipeline_health() -> dict:
    """Check sales pipeline and ETL health.

    Returns pipeline status (healthy/degraded/critical), ETL run history
    with success rates, CRM deal funnel with $8.6M pipeline across 6
    lifecycle stages, and industry breakdown."""
    conn = _conn()

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
               ROUND(AVG(rows_loaded), 0) AS avg_loaded,
               ROUND(AVG(duration_seconds), 1) AS avg_duration,
               ROUND(MIN(rows_loaded), 0) AS min_loaded,
               ROUND(MAX(rows_loaded), 0) AS max_loaded
        FROM pipeline_runs
        """
    ).fetchone()

    failures = conn.execute(
        """
        SELECT run_date, status, error_message, rows_extracted, rows_loaded
        FROM pipeline_runs WHERE status != 'success'
        ORDER BY run_date DESC LIMIT 5
        """
    ).fetchall()

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
            {"date": r["run_date"], "status": r["status"], "rows_loaded": r["rows_loaded"], "duration": r["duration_seconds"]}
            for r in recent
        ],
    }

    crm_total = conn.execute("SELECT COUNT(*) AS n FROM crm_contacts").fetchone()["n"]

    stage_dist = conn.execute(
        """
        SELECT lifecycle_stage, COUNT(*) AS count,
               ROUND(SUM(deal_value), 2) AS total_value,
               ROUND(AVG(deal_value), 2) AS avg_value
        FROM crm_contacts GROUP BY lifecycle_stage ORDER BY count DESC
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
               ROUND(AVG(page_views), 1) AS avg_views
        FROM crm_contacts
        """
    ).fetchone()

    industry_dist = conn.execute(
        """
        SELECT industry, COUNT(*) AS count,
               ROUND(SUM(deal_value), 2) AS total_value
        FROM crm_contacts GROUP BY industry ORDER BY total_value DESC
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

    return {"pipeline_status": pipeline_status, "deal_pipeline": deal_pipeline}


def get_attribution_analysis() -> dict:
    """Get marketing attribution analysis across 7 models with journey insights.

    Returns per-channel attribution weights from first-click, last-click, linear,
    time-decay, position-based, Markov, and Shapley models, plus journey stats
    and first-touch vs last-touch frequency from 47,364 user journeys."""
    conn = _conn()

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

    for ch in channels:
        vals = [ch[m] for m in model_names if ch[m] > 0]
        if len(vals) >= 2:
            mean = sum(vals) / len(vals)
            std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            ch["model_agreement"] = round(100 - std, 1)
        else:
            ch["model_agreement"] = 100.0

    journey_stats = conn.execute(
        """
        SELECT COUNT(*) AS total_journeys,
               SUM(has_conversion) AS conversions,
               ROUND(AVG(has_conversion) * 100, 2) AS conversion_rate,
               ROUND(AVG(journey_length), 1) AS avg_journey_length,
               MAX(journey_length) AS max_journey_length,
               ROUND(AVG(CASE WHEN has_conversion = 1 THEN conversion_value ELSE NULL END), 2) AS avg_conversion_value
        FROM journey_data
        """
    ).fetchone()

    conv_lengths = conn.execute(
        """
        SELECT has_conversion, ROUND(AVG(journey_length), 1) AS avg_length, COUNT(*) AS count
        FROM journey_data GROUP BY has_conversion
        """
    ).fetchall()

    channel_freq = conn.execute(
        "SELECT channel_list FROM journey_data WHERE has_conversion = 1"
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

    first_touch_sorted = sorted(first_touch.items(), key=lambda x: -x[1])
    last_touch_sorted = sorted(last_touch.items(), key=lambda x: -x[1])
    all_touches_sorted = sorted(all_touches.items(), key=lambda x: -x[1])

    conn.close()

    return {
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


# ═══════════════════════════════════════════════════════════════════════
# DATABASE / LOGGING TOOLS (from mcp_servers/database_server.py)
# ═══════════════════════════════════════════════════════════════════════

def log_workflow(workflow_name: str, status: str = "completed", result_summary: str = "") -> dict:
    """Log a workflow run to the database. Returns the workflow run ID."""
    conn = _conn()
    now = datetime.now().isoformat()
    c = conn.execute(
        "INSERT INTO workflow_runs (workflow_name, started_at, completed_at, status, result_summary) "
        "VALUES (?, ?, ?, ?, ?)",
        (workflow_name, now, now if status == "completed" else None, status, result_summary),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return {"workflow_run_id": row_id, "status": status}


def log_action(workflow_run_id: int, agent_name: str, tool_name: str, input_params: str = "", output_summary: str = "") -> dict:
    """Log an agent action within a workflow run. Returns the action ID."""
    conn = _conn()
    c = conn.execute(
        "INSERT INTO agent_actions (workflow_run_id, agent_name, tool_name, input_params, output_summary) "
        "VALUES (?, ?, ?, ?, ?)",
        (workflow_run_id, agent_name, tool_name, input_params, output_summary),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return {"action_id": row_id, "workflow_run_id": workflow_run_id}


def get_recent_workflows(limit: int = 10) -> dict:
    """Get recent workflow runs from the database."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return {"workflows": [dict(r) for r in rows]}


def create_task(title: str, description: str = "", assigned_agent: str = "", priority: str = "medium") -> dict:
    """Create a task in the database and assign it to an agent."""
    conn = _conn()
    c = conn.execute(
        "INSERT INTO tasks (title, description, assigned_agent, priority) VALUES (?, ?, ?, ?)",
        (title, description, assigned_agent, priority),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return {"task_id": row_id, "title": title, "assigned_agent": assigned_agent}
