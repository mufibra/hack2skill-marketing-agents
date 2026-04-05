"""Create the SQLite database and tables for marketing intelligence tracking."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "marketing_intel.db"


def create_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Original tracking tables ──────────────────────────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS workflow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'running',
            result_summary TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_run_id INTEGER,
            agent_name TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            input_params TEXT,
            output_summary TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workflow_run_id) REFERENCES workflow_runs(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            assigned_agent TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS query_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text TEXT NOT NULL,
            agent_name TEXT,
            result_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── P1: Daily marketing metrics (GA4 e-commerce) ─────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            date TEXT NOT NULL,
            source TEXT,
            medium TEXT,
            users INTEGER,
            sessions INTEGER,
            page_views INTEGER,
            purchases INTEGER,
            revenue REAL,
            PRIMARY KEY (date, source, medium)
        )
    """)

    # ── P8: Support tickets (NLP customer intelligence) ──────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id TEXT PRIMARY KEY,
            customer_id TEXT,
            customer_name TEXT,
            customer_plan TEXT,
            created_date TEXT,
            category TEXT,
            sentiment_label TEXT,
            text TEXT,
            resolution_status TEXT,
            days_to_resolve INTEGER,
            is_repeat_contact TEXT,
            priority TEXT
        )
    """)

    # ── P4: Scored leads (XGBoost + SHAP) ────────────────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS scored_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_origin TEXT,
            lead_source TEXT,
            do_not_email INTEGER,
            do_not_call INTEGER,
            total_visits REAL,
            total_time_spent REAL,
            page_views_per_visit REAL,
            last_activity TEXT,
            country TEXT,
            specialization TEXT,
            current_occupation TEXT,
            search INTEGER,
            newspaper_article INTEGER,
            x_education_forums INTEGER,
            newspaper INTEGER,
            digital_advertisement INTEGER,
            through_recommendations INTEGER,
            tags TEXT,
            lead_quality TEXT,
            lead_profile TEXT,
            city TEXT,
            free_copy_mastering_interview INTEGER,
            last_notable_activity TEXT,
            engagement_score REAL,
            is_referred INTEGER,
            is_working_professional INTEGER,
            is_high_activity INTEGER,
            website_engagement_level TEXT,
            lead_quality_numeric INTEGER,
            source_historical_conv_rate REAL,
            actual_converted INTEGER,
            predicted_proba REAL,
            predicted_converted INTEGER,
            lead_score REAL
        )
    """)

    # ── P5: Customer segments (RFM + CLV) ────────────────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS customer_segments (
            customer_id INTEGER,
            recency INTEGER,
            frequency INTEGER,
            monetary REAL,
            r_score INTEGER,
            f_score INTEGER,
            m_score INTEGER,
            rfm_score INTEGER,
            rfm_segment TEXT,
            segment TEXT,
            cluster INTEGER,
            cluster_name TEXT,
            cluster_action TEXT,
            clv REAL,
            clv_tier TEXT,
            prob_alive REAL,
            pred_purchases_90d REAL,
            pred_avg_order_value REAL,
            lt_frequency REAL,
            lt_recency REAL,
            lt_t REAL,
            lt_monetary_value REAL
        )
    """)

    # ── P6: Attribution results (7 models) ───────────────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS attribution_results (
            channel TEXT PRIMARY KEY,
            first_click REAL,
            last_click REAL,
            linear REAL,
            time_decay REAL,
            position_based REAL,
            markov REAL,
            shapley REAL
        )
    """)

    # ── P6: Journey data (user paths) ────────────────────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS journey_data (
            user_id TEXT,
            journey_medium_path TEXT,
            journey_source_path TEXT,
            has_conversion INTEGER,
            conversion_value REAL,
            journey_length INTEGER,
            first_visit_date TEXT,
            last_visit_date TEXT,
            journey_path TEXT,
            channel_list TEXT
        )
    """)

    # ── P7: CRM contacts ─────────────────────────────────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS crm_contacts (
            contact_id TEXT PRIMARY KEY,
            email TEXT,
            company TEXT,
            industry TEXT,
            lead_source TEXT,
            lifecycle_stage TEXT,
            created_date TEXT,
            last_activity_date TEXT,
            deal_value REAL,
            num_touches INTEGER,
            email_opens INTEGER,
            page_views INTEGER
        )
    """)

    # ── P7: Pipeline run history ─────────────────────────────────────

    c.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'success',
            rows_extracted INTEGER,
            rows_loaded INTEGER,
            duration_seconds REAL,
            error_message TEXT
        )
    """)

    # ── P2: Competitive intelligence (merged from competitive_intel.db) ──

    c.execute("""
        CREATE TABLE IF NOT EXISTS competitive_prompts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_text TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS competitive_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            raw_response TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prompt_id) REFERENCES competitive_prompts(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS competitive_citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            brand_mentioned TEXT NOT NULL,
            position INTEGER,
            source_url TEXT,
            sentiment TEXT DEFAULT 'neutral',
            context_snippet TEXT,
            FOREIGN KEY (response_id) REFERENCES competitive_responses(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS competitive_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            platform TEXT,
            prompts_sent INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database created at {DB_PATH}")
    print("Tables: workflow_runs, agent_actions, tasks, query_results,")
    print("        daily_metrics, support_tickets, scored_leads, customer_segments,")
    print("        attribution_results, journey_data, crm_contacts, pipeline_runs,")
    print("        competitive_prompts, competitive_responses, competitive_citations, competitive_runs")


if __name__ == "__main__":
    create_tables()
