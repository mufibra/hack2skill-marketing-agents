"""Load all source project data into marketing_intel.db for live querying."""

import csv
import math
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "marketing_intel.db"
PROJECT_ROOT = Path(__file__).resolve().parent.parent          # hack2skill-marketing-agents/
SOURCE_DATA = PROJECT_ROOT / "source_data"                     # bundled CSVs
SIBLING_ROOT = PROJECT_ROOT.parent                             # Hack2Skill/ (dev only)


def _source(bundled_name, sibling_path):
    """Resolve source file: prefer bundled source_data/, fall back to sibling project."""
    bundled = SOURCE_DATA / bundled_name
    if bundled.exists():
        return bundled
    fallback = SIBLING_ROOT / sibling_path
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Source data not found: tried {bundled} and {fallback}")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def load_p1_daily_metrics():
    """Generate realistic GA4 e-commerce data for Jan 1-31, 2021."""
    print("Loading P1 daily_metrics (synthetic GA4)...")
    random.seed(42)
    conn = _conn()
    conn.execute("DELETE FROM daily_metrics")

    sources = [
        ("google", "organic", 0.40),
        ("(direct)", "(none)", 0.25),
        ("google", "cpc", 0.12),
        ("referral", "referral", 0.10),
        ("facebook", "social", 0.08),
        ("newsletter", "email", 0.05),
    ]

    rows = []
    for day in range(1, 32):
        date_str = f"2021-01-{day:02d}"
        dow = datetime(2021, 1, day).weekday()

        # Base daily totals with weekend dip
        weekend_mult = 0.75 if dow >= 5 else 1.0
        # Spike on Jan 18
        spike_mult = 1.6 if day == 18 else 1.0
        # Slight upward trend
        trend_mult = 1.0 + (day - 1) * 0.003

        base_sessions = int(1250 * weekend_mult * spike_mult * trend_mult * random.uniform(0.90, 1.10))
        base_users = int(base_sessions * random.uniform(0.75, 0.85))
        base_pageviews = int(base_sessions * random.uniform(2.8, 3.8))
        base_purchases = int(base_sessions * random.uniform(0.010, 0.016) * spike_mult)
        base_purchases = max(base_purchases, 8)
        base_revenue = base_purchases * random.uniform(35, 55)

        for source, medium, share in sources:
            s = max(1, int(base_sessions * share * random.uniform(0.85, 1.15)))
            u = max(1, int(base_users * share * random.uniform(0.85, 1.15)))
            pv = max(1, int(base_pageviews * share * random.uniform(0.85, 1.15)))
            p = max(0, int(base_purchases * share * random.uniform(0.7, 1.3)))
            r = round(base_revenue * share * random.uniform(0.7, 1.3), 2)
            rows.append((date_str, source, medium, u, s, pv, p, r))

    conn.executemany(
        "INSERT INTO daily_metrics (date, source, medium, users, sessions, page_views, purchases, revenue) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
    conn.close()
    print(f"  daily_metrics: {count} rows loaded")


def load_p8_support_tickets():
    """Load support tickets from P8 CSV."""
    print("Loading P8 support_tickets...")
    csv_path = _source("support_tickets.csv", "nlp-customer-intelligence/data/synthetic/support_tickets.csv")
    conn = _conn()
    conn.execute("DELETE FROM support_tickets")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                row["ticket_id"],
                row["customer_id"],
                row["customer_name"],
                row["customer_plan"],
                row["created_date"],
                row["category"],
                row["sentiment_label"],
                row["text"],
                row["resolution_status"],
                int(row["days_to_resolve"]) if row["days_to_resolve"] else None,
                row["is_repeat_contact"],
                row["priority"],
            ))

    conn.executemany(
        "INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0]
    conn.close()
    print(f"  support_tickets: {count} rows loaded")


def load_p4_scored_leads():
    """Load scored leads from P4 CSV."""
    print("Loading P4 scored_leads...")
    csv_path = _source("test_predictions.csv", "lead-scoring-system/shap_cache/test_predictions.csv")
    conn = _conn()
    conn.execute("DELETE FROM scored_leads")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            def flt(v):
                try:
                    return float(v) if v and v != "" else None
                except ValueError:
                    return None

            def itg(v):
                try:
                    return int(float(v)) if v and v != "" else None
                except ValueError:
                    return None

            rows.append((
                row.get("Lead Origin"),
                row.get("Lead Source"),
                itg(row.get("Do Not Email")),
                itg(row.get("Do Not Call")),
                flt(row.get("TotalVisits")),
                flt(row.get("Total Time Spent on Website")),
                flt(row.get("Page Views Per Visit")),
                row.get("Last Activity"),
                row.get("Country"),
                row.get("Specialization"),
                row.get("What is your current occupation"),
                itg(row.get("Search")),
                itg(row.get("Newspaper Article")),
                itg(row.get("X Education Forums")),
                itg(row.get("Newspaper")),
                itg(row.get("Digital Advertisement")),
                itg(row.get("Through Recommendations")),
                row.get("Tags"),
                row.get("Lead Quality"),
                row.get("Lead Profile"),
                row.get("City"),
                itg(row.get("A free copy of Mastering The Interview")),
                row.get("Last Notable Activity"),
                flt(row.get("engagement_score")),
                itg(row.get("is_referred")),
                itg(row.get("is_working_professional")),
                itg(row.get("is_high_activity")),
                row.get("website_engagement_level"),
                itg(row.get("lead_quality_numeric")),
                flt(row.get("source_historical_conv_rate")),
                itg(row.get("actual_converted")),
                flt(row.get("predicted_proba")),
                itg(row.get("predicted_converted")),
                flt(row.get("lead_score")),
            ))

    conn.executemany(
        "INSERT INTO scored_leads (lead_origin, lead_source, do_not_email, do_not_call, "
        "total_visits, total_time_spent, page_views_per_visit, last_activity, country, "
        "specialization, current_occupation, search, newspaper_article, x_education_forums, "
        "newspaper, digital_advertisement, through_recommendations, tags, lead_quality, "
        "lead_profile, city, free_copy_mastering_interview, last_notable_activity, "
        "engagement_score, is_referred, is_working_professional, is_high_activity, "
        "website_engagement_level, lead_quality_numeric, source_historical_conv_rate, "
        "actual_converted, predicted_proba, predicted_converted, lead_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM scored_leads").fetchone()[0]
    conn.close()
    print(f"  scored_leads: {count} rows loaded")


def load_p5_customer_segments():
    """Load customer segments from P5 CSV."""
    print("Loading P5 customer_segments...")
    csv_path = _source("clv_predictions.csv", "customer-segmentation-clv/data/processed/clv_predictions.csv")
    conn = _conn()
    conn.execute("DELETE FROM customer_segments")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            def flt(v):
                try:
                    return float(v) if v and v != "" else None
                except ValueError:
                    return None

            def itg(v):
                try:
                    return int(float(v)) if v and v != "" else None
                except ValueError:
                    return None

            rows.append((
                itg(row.get("CustomerID")),
                itg(row.get("Recency")),
                itg(row.get("Frequency")),
                flt(row.get("Monetary")),
                itg(row.get("R_Score")),
                itg(row.get("F_Score")),
                itg(row.get("M_Score")),
                itg(row.get("RFM_Score")),
                row.get("RFM_Segment"),
                row.get("Segment"),
                itg(row.get("Cluster")),
                row.get("Cluster_Name"),
                row.get("Cluster_Action"),
                flt(row.get("CLV")),
                row.get("CLV_Tier"),
                flt(row.get("prob_alive")),
                flt(row.get("pred_purchases_90d")),
                flt(row.get("pred_avg_order_value")),
                # lifetimes columns have duplicate names in CSV; they appear after CLV cols
                flt(row.get("frequency")),
                flt(row.get("recency")),
                flt(row.get("T")),
                flt(row.get("monetary_value")),
            ))

    conn.executemany(
        "INSERT INTO customer_segments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM customer_segments").fetchone()[0]
    conn.close()
    print(f"  customer_segments: {count} rows loaded")


def load_p6_attribution():
    """Load attribution results from P6 CSV."""
    print("Loading P6 attribution_results...")
    csv_path = _source("attribution_results.csv", "marketing-attribution-agent/data/attribution_results.csv")
    conn = _conn()
    conn.execute("DELETE FROM attribution_results")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                row["channel"],
                float(row["first_click"]),
                float(row["last_click"]),
                float(row["linear"]),
                float(row["time_decay"]),
                float(row["position_based"]),
                float(row["markov"]),
                float(row["shapley"]),
            ))

    conn.executemany(
        "INSERT INTO attribution_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM attribution_results").fetchone()[0]
    conn.close()
    print(f"  attribution_results: {count} rows loaded")


def load_p6_journey_data():
    """Load journey data from P6 CSV."""
    print("Loading P6 journey_data...")
    csv_path = _source("journey_data.csv", "marketing-attribution-agent/data/journey_data.csv")
    conn = _conn()
    conn.execute("DELETE FROM journey_data")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch = []
        total = 0
        for row in reader:
            batch.append((
                row["user_id"],
                row["journey_medium_path"],
                row["journey_source_path"],
                int(row["has_conversion"]),
                float(row["conversion_value"]) if row["conversion_value"] else 0.0,
                int(row["journey_length"]),
                row["first_visit_date"],
                row["last_visit_date"],
                row["journey_path"],
                row["channel_list"],
            ))
            if len(batch) >= 5000:
                conn.executemany(
                    "INSERT INTO journey_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    batch,
                )
                conn.commit()
                total += len(batch)
                batch = []

        if batch:
            conn.executemany(
                "INSERT INTO journey_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()
            total += len(batch)

    count = conn.execute("SELECT COUNT(*) FROM journey_data").fetchone()[0]
    conn.close()
    print(f"  journey_data: {count} rows loaded")


def load_p7_crm_contacts():
    """Load CRM contacts from P7 CSV."""
    print("Loading P7 crm_contacts...")
    csv_path = _source("crm_export.csv", "marketing-data-pipeline/data/raw/crm_export.csv")
    conn = _conn()
    conn.execute("DELETE FROM crm_contacts")

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                row["contact_id"],
                row["email"],
                row["company"],
                row["industry"],
                row["lead_source"],
                row["lifecycle_stage"],
                row["created_date"],
                row["last_activity_date"],
                float(row["deal_value"]),
                int(row["num_touches"]),
                int(row["email_opens"]),
                int(row["page_views"]),
            ))

    conn.executemany(
        "INSERT INTO crm_contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM crm_contacts").fetchone()[0]
    conn.close()
    print(f"  crm_contacts: {count} rows loaded")


def load_p7_pipeline_runs():
    """Generate 30 days of realistic ETL pipeline run history."""
    print("Loading P7 pipeline_runs (synthetic)...")
    random.seed(42)
    conn = _conn()
    conn.execute("DELETE FROM pipeline_runs")

    today = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    rows = []
    for i in range(29, -1, -1):
        run_date = (today - timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
        extracted = random.randint(800, 1500)
        loaded = extracted - random.randint(0, 20)  # small data quality drops
        duration = round(random.uniform(45, 180), 1)
        rows.append((run_date, "success", extracted, loaded, duration, None))

    conn.executemany(
        "INSERT INTO pipeline_runs (run_date, status, rows_extracted, rows_loaded, duration_seconds, error_message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
    conn.close()
    print(f"  pipeline_runs: {count} rows loaded")


def load_p2_competitive():
    """Merge P2 competitive_intel.db tables into marketing_intel.db."""
    print("Loading P2 competitive data...")
    src_db = _source("competitive_intel.db", "ai-competitive-intel/data/competitive_intel.db")
    conn = _conn()

    # Clear existing competitive tables
    conn.execute("DELETE FROM competitive_prompts")
    conn.execute("DELETE FROM competitive_responses")
    conn.execute("DELETE FROM competitive_citations")
    conn.execute("DELETE FROM competitive_runs")

    # Attach source DB and copy data
    conn.execute(f"ATTACH DATABASE ? AS src", (str(src_db),))

    conn.execute("INSERT INTO competitive_prompts (id, prompt_text, category, created_at) "
                 "SELECT id, prompt_text, category, created_at FROM src.prompts")
    conn.execute("INSERT INTO competitive_responses (id, prompt_id, platform, raw_response, collected_at) "
                 "SELECT id, prompt_id, platform, raw_response, collected_at FROM src.responses")
    conn.execute("INSERT INTO competitive_citations (id, response_id, brand_mentioned, position, source_url, sentiment, context_snippet) "
                 "SELECT id, response_id, brand_mentioned, position, source_url, sentiment, context_snippet FROM src.citations")
    conn.execute("INSERT INTO competitive_runs (id, run_date, platform, prompts_sent, success_count, error_count) "
                 "SELECT id, run_date, platform, prompts_sent, success_count, error_count FROM src.runs")

    conn.commit()
    conn.execute("DETACH DATABASE src")

    counts = {}
    for table in ["competitive_prompts", "competitive_responses", "competitive_citations", "competitive_runs"]:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()

    for t, c in counts.items():
        print(f"  {t}: {c} rows loaded")


def main():
    # Ensure all tables exist
    from setup import create_tables
    create_tables()

    print("\n" + "=" * 60)
    print("Loading source data into marketing_intel.db")
    print("=" * 60 + "\n")

    load_p1_daily_metrics()
    load_p8_support_tickets()
    load_p4_scored_leads()
    load_p5_customer_segments()
    load_p6_attribution()
    load_p6_journey_data()
    load_p7_crm_contacts()
    load_p7_pipeline_runs()
    load_p2_competitive()

    # Final verification
    print("\n" + "=" * 60)
    print("VERIFICATION — Row counts")
    print("=" * 60)
    conn = _conn()
    tables = [
        "daily_metrics", "support_tickets", "scored_leads", "customer_segments",
        "attribution_results", "journey_data", "crm_contacts", "pipeline_runs",
        "competitive_prompts", "competitive_responses", "competitive_citations", "competitive_runs",
    ]
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
