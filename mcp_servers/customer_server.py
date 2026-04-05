"""
Customer Intelligence MCP Server — queries support_tickets, scored_leads, and
customer_segments in SQLite for live sentiment analysis, lead scoring, and segmentation.

Run:  python mcp_servers/customer_server.py
"""

import json
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "marketing_intel.db"

mcp = FastMCP("customer_intel")


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@mcp.tool()
def analyze_sentiment() -> str:
    """Analyze customer sentiment from support tickets. Returns total counts,
    sentiment distribution (positive/negative/neutral with percentages),
    per-category breakdown, high-priority negatives, and resolution stats."""
    conn = _conn()

    total = conn.execute("SELECT COUNT(*) AS n FROM support_tickets").fetchone()["n"]
    if total == 0:
        conn.close()
        return json.dumps({"error": "No support tickets in database"})

    # ── Overall sentiment distribution ────────────────────────────────
    dist = conn.execute(
        """
        SELECT sentiment_label,
               COUNT(*) AS count
        FROM support_tickets
        GROUP BY sentiment_label
        """
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

    # ── Per-category breakdown ────────────────────────────────────────
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

    # ── High-priority negative tickets (sample) ──────────────────────
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

    # ── Resolution stats ──────────────────────────────────────────────
    resolution = conn.execute(
        """
        SELECT resolution_status,
               COUNT(*) AS count,
               ROUND(AVG(days_to_resolve), 1) AS avg_days
        FROM support_tickets
        GROUP BY resolution_status
        """
    ).fetchall()

    # ── Plan breakdown ────────────────────────────────────────────────
    plans = conn.execute(
        """
        SELECT customer_plan,
               COUNT(*) AS total,
               SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) AS negative,
               ROUND(AVG(days_to_resolve), 1) AS avg_resolve_days
        FROM support_tickets
        GROUP BY customer_plan
        ORDER BY total DESC
        """
    ).fetchall()

    conn.close()

    result = {
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

    return json.dumps(result, indent=2)


@mcp.tool()
def score_leads(hot_threshold: float = 80.0, warm_threshold: float = 50.0) -> str:
    """Score leads from the scored_leads table. Classifies as hot (>80), warm (50-80),
    cold (<50) by lead_score. Returns distribution, top hot leads, conversion stats,
    and feature insights."""
    conn = _conn()

    total = conn.execute("SELECT COUNT(*) AS n FROM scored_leads").fetchone()["n"]
    if total == 0:
        conn.close()
        return json.dumps({"error": "No scored leads in database"})

    # ── Hot / Warm / Cold distribution ────────────────────────────────
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

    # ── Score stats ───────────────────────────────────────────────────
    stats = conn.execute(
        """
        SELECT ROUND(MIN(lead_score), 1) AS min_score,
               ROUND(MAX(lead_score), 1) AS max_score,
               ROUND(AVG(lead_score), 1) AS avg_score
        FROM scored_leads
        """
    ).fetchone()

    # ── Conversion accuracy ───────────────────────────────────────────
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

    # ── Top hot leads ─────────────────────────────────────────────────
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

    # ── Feature insights: what hot leads have in common ───────────────
    feature_insights = {}

    # Top lead sources for hot leads
    sources = conn.execute(
        """
        SELECT lead_source, COUNT(*) AS cnt
        FROM scored_leads WHERE lead_score >= ?
        GROUP BY lead_source ORDER BY cnt DESC LIMIT 5
        """,
        (hot_threshold,),
    ).fetchall()
    feature_insights["top_lead_sources"] = {r["lead_source"]: r["cnt"] for r in sources}

    # Engagement level distribution for hot leads
    eng = conn.execute(
        """
        SELECT website_engagement_level, COUNT(*) AS cnt
        FROM scored_leads WHERE lead_score >= ?
        GROUP BY website_engagement_level ORDER BY cnt DESC
        """,
        (hot_threshold,),
    ).fetchall()
    feature_insights["engagement_levels"] = {r["website_engagement_level"]: r["cnt"] for r in eng}

    # Top tags for hot leads
    tags = conn.execute(
        """
        SELECT tags, COUNT(*) AS cnt
        FROM scored_leads WHERE lead_score >= ?
        GROUP BY tags ORDER BY cnt DESC LIMIT 5
        """,
        (hot_threshold,),
    ).fetchall()
    feature_insights["top_tags"] = {r["tags"]: r["cnt"] for r in tags}

    # Avg engagement metrics: hot vs cold
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

    result = {
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

    return json.dumps(result, indent=2)


@mcp.tool()
def get_customer_segments() -> str:
    """Query customer_segments table for RFM segmentation and CLV analysis.
    Returns per-segment and per-cluster stats, CLV tier distribution,
    highest-value customers, and at-risk segment identification."""
    conn = _conn()

    total = conn.execute("SELECT COUNT(*) AS n FROM customer_segments").fetchone()["n"]
    if total == 0:
        conn.close()
        return json.dumps({"error": "No customer segments in database"})

    # ── Per RFM segment ───────────────────────────────────────────────
    segments = conn.execute(
        """
        SELECT segment,
               COUNT(*)              AS count,
               ROUND(AVG(recency), 0)   AS avg_recency,
               ROUND(AVG(frequency), 1) AS avg_frequency,
               ROUND(AVG(monetary), 0)  AS avg_monetary,
               ROUND(AVG(clv), 0)       AS avg_clv,
               ROUND(AVG(prob_alive), 3) AS avg_prob_alive
        FROM customer_segments
        GROUP BY segment
        ORDER BY avg_clv DESC
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

    # ── Per K-Means cluster ───────────────────────────────────────────
    clusters = conn.execute(
        """
        SELECT cluster_name, cluster_action,
               COUNT(*)                  AS count,
               ROUND(AVG(recency), 0)    AS avg_recency,
               ROUND(AVG(frequency), 1)  AS avg_frequency,
               ROUND(AVG(monetary), 0)   AS avg_monetary,
               ROUND(AVG(clv), 0)        AS avg_clv
        FROM customer_segments
        GROUP BY cluster_name
        ORDER BY avg_clv DESC
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

    # ── CLV tier distribution ─────────────────────────────────────────
    tiers = conn.execute(
        """
        SELECT CASE WHEN clv_tier = '' OR clv_tier IS NULL THEN 'No CLV (one-time)'
                    ELSE clv_tier END AS tier,
               COUNT(*) AS count,
               ROUND(AVG(clv), 0) AS avg_clv,
               ROUND(SUM(clv), 0) AS total_clv
        FROM customer_segments
        GROUP BY tier
        ORDER BY avg_clv DESC
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

    # ── Top 10 highest-value customers ────────────────────────────────
    top_customers = conn.execute(
        """
        SELECT customer_id, segment, cluster_name, clv, clv_tier,
               prob_alive, recency, frequency, monetary
        FROM customer_segments
        WHERE clv IS NOT NULL
        ORDER BY clv DESC
        LIMIT 10
        """
    ).fetchall()

    # ── At-risk high-value customers (high CLV but low prob_alive or high recency) ──
    at_risk = conn.execute(
        """
        SELECT customer_id, segment, cluster_name, clv, clv_tier,
               prob_alive, recency, frequency, monetary
        FROM customer_segments
        WHERE clv IS NOT NULL
          AND clv_tier IN ('Platinum', 'High')
          AND (prob_alive < 0.5 OR recency > 200)
        ORDER BY clv DESC
        LIMIT 10
        """
    ).fetchall()

    conn.close()

    result = {
        "total_customers": total,
        "rfm_segments": segment_list,
        "clusters": cluster_list,
        "clv_tiers": clv_tiers,
        "top_customers": [dict(r) for r in top_customers],
        "at_risk_high_value": [dict(r) for r in at_risk],
    }

    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
