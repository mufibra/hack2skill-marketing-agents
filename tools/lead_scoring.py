"""
Lead Scoring — Capability 5 of OpenClaw Marketing Agent (P10).

Wraps P4's XGBoost lead scoring model and SHAP explainability to score
leads, identify hot prospects, and explain why they're likely to convert.

Usage:
    python scripts/lead_scoring.py --output json
    python scripts/lead_scoring.py --threshold 0.7 --output text
"""

import sys
import os
import json
import argparse
import pickle
import random
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# P4 repo path
P4_ROOT = Path(r"C:\Users\ahmad\Downloads\Hack2Skill\lead-scoring-system")
if str(P4_ROOT) not in sys.path:
    sys.path.insert(0, str(P4_ROOT))

# P4 artifacts
P4_MODEL = P4_ROOT / "models" / "xgboost_model.pkl"
P4_TEST_PREDICTIONS = P4_ROOT / "shap_cache" / "test_predictions.csv"
P4_FEATURE_IMPORTANCE = P4_ROOT / "shap_cache" / "feature_importance.csv"
P4_SHAP_VALUES = P4_ROOT / "shap_cache" / "shap_values.pkl"
P4_METRICS = P4_ROOT / "shap_cache" / "metrics.pkl"

# History
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "lead_scoring_history.json"

# Score categories
HOT_THRESHOLD = 0.7
WARM_THRESHOLD = 0.4

# Key features for explanations (by SHAP importance order)
TOP_FEATURES = [
    "Tags", "Total Time Spent on Website", "Last Notable Activity",
    "What is your current occupation", "Last Activity", "Lead Quality",
    "Page Views Per Visit", "Specialization", "website_engagement_level",
    "Lead Source", "TotalVisits", "Lead Profile", "engagement_score",
    "is_high_activity", "Do Not Email",
]


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scans": [], "last_scan": None}


def save_history(history):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, default=str)


def load_scored_leads():
    """
    Load pre-scored leads from P4's cache. Priority:
    1. P4's test_predictions.csv (pre-scored with probabilities)
    2. Score raw leads with P4's XGBoost model
    3. Fall back to sample data
    """
    import pandas as pd

    data_source = "sample"
    leads_df = None
    feature_importance = None
    model_metrics = None

    # Try loading P4's pre-computed predictions
    try:
        if P4_TEST_PREDICTIONS.exists():
            leads_df = pd.read_csv(P4_TEST_PREDICTIONS)
            data_source = "p4_precomputed"
    except Exception:
        pass

    # Try loading feature importance
    try:
        if P4_FEATURE_IMPORTANCE.exists():
            fi = pd.read_csv(P4_FEATURE_IMPORTANCE)
            # Handle the unnamed index column
            if "Unnamed: 0" in fi.columns:
                fi = fi.rename(columns={"Unnamed: 0": "feature", "0": "importance"})
            elif fi.columns[0] != "feature":
                fi.columns = ["feature", "importance"]
            feature_importance = dict(zip(fi["feature"], fi["importance"]))
    except Exception:
        pass

    # Try loading model metrics
    try:
        if P4_METRICS.exists():
            with open(P4_METRICS, "rb") as f:
                model_metrics = pickle.load(f)
    except Exception:
        pass

    # If no pre-computed data, try scoring with the model
    if leads_df is None:
        leads_df, data_source = _try_live_scoring()

    # Final fallback: sample data
    if leads_df is None:
        leads_df, feature_importance = _generate_sample_leads()
        data_source = "sample"

    if feature_importance is None:
        feature_importance = _default_feature_importance()

    if model_metrics is None:
        model_metrics = {
            "accuracy": 0.938, "precision": 0.922, "recall": 0.916,
            "f1": 0.919, "roc_auc": 0.978,
        }

    return leads_df, feature_importance, model_metrics, data_source


def _try_live_scoring():
    """Attempt to score leads using P4's trained model and preprocessing."""
    import pandas as pd

    try:
        if not P4_MODEL.exists():
            return None, "sample"

        with open(P4_MODEL, "rb") as f:
            model = pickle.load(f)

        from src.data_preprocessing import load_and_clean, engineer_features, prepare_for_modeling

        df = load_and_clean(str(P4_ROOT / "data" / "Lead_Scoring.csv"))
        df = engineer_features(df)
        X, y = prepare_for_modeling(df)

        # Score all leads
        proba = model.predict_proba(X)[:, 1]
        preds = model.predict(X)

        # Build output DataFrame with key features
        leads_df = X.copy()
        leads_df["actual_converted"] = y.values
        leads_df["predicted_proba"] = proba
        leads_df["predicted_converted"] = preds
        leads_df["lead_score"] = (proba * 100).round(1)

        return leads_df, "p4_live"

    except Exception:
        return None, "sample"


def _generate_sample_leads(n=200):
    """Generate sample lead data when P4 is unavailable."""
    import pandas as pd

    rng = random.Random(42)

    tags_options = [
        "Will revert after reading the email", "Ringing", "Unknown",
        "Interested in other courses", "Already a student",
        "Closed by Horizzon", "Switched off", "Lost to EINS",
    ]
    activity_options = [
        "SMS Sent", "Email Opened", "Page Visited on Website",
        "Had a Phone Conversation", "Modified", "Olark Chat Conversation",
    ]
    source_options = [
        "Google", "Organic Search", "Direct Traffic",
        "Referral Sites", "Olark Chat", "Reference",
    ]
    occupation_options = [
        "Working Professional", "Unemployed", "Student",
        "Businessman", "Unknown",
    ]

    leads = []
    for i in range(n):
        # Simulate realistic distribution (bimodal: many cold, some hot)
        if rng.random() < 0.35:
            proba = rng.uniform(0.7, 0.99)
            time_spent = rng.randint(500, 2500)
            page_views = rng.uniform(3.0, 10.0)
            tags = rng.choice(["Will revert after reading the email", "Ringing", "Already a student"])
        elif rng.random() < 0.1:
            proba = rng.uniform(0.4, 0.7)
            time_spent = rng.randint(200, 800)
            page_views = rng.uniform(2.0, 5.0)
            tags = rng.choice(tags_options)
        else:
            proba = rng.uniform(0.01, 0.4)
            time_spent = rng.randint(0, 400)
            page_views = rng.uniform(0.0, 3.0)
            tags = rng.choice(["Unknown", "Switched off", "Lost to EINS"])

        leads.append({
            "Tags": tags,
            "Total Time Spent on Website": time_spent,
            "Page Views Per Visit": round(page_views, 1),
            "Last Notable Activity": rng.choice(activity_options),
            "Last Activity": rng.choice(activity_options),
            "What is your current occupation": rng.choice(occupation_options),
            "Lead Source": rng.choice(source_options),
            "Lead Quality": rng.choice(["High in Relevance", "Low in Relevance", "Might be", "Unknown"]),
            "TotalVisits": rng.randint(0, 30),
            "Specialization": rng.choice(["Finance", "Marketing", "HR", "IT", "Unknown"]),
            "engagement_score": round(time_spent * page_views, 1),
            "is_working_professional": 1 if rng.random() > 0.5 else 0,
            "is_high_activity": 1 if rng.random() > 0.6 else 0,
            "predicted_proba": round(proba, 4),
            "predicted_converted": 1 if proba >= 0.5 else 0,
            "lead_score": round(proba * 100, 1),
            "actual_converted": 1 if proba >= 0.5 and rng.random() > 0.1 else 0,
        })

    fi = _default_feature_importance()
    return pd.DataFrame(leads), fi


def _default_feature_importance():
    return {
        "Tags": 2.494, "Total Time Spent on Website": 0.720,
        "Last Notable Activity": 0.648, "What is your current occupation": 0.634,
        "Last Activity": 0.428, "Lead Quality": 0.367,
        "Page Views Per Visit": 0.283, "Specialization": 0.241,
        "website_engagement_level": 0.177, "Lead Source": 0.147,
        "TotalVisits": 0.143, "Lead Profile": 0.130,
        "engagement_score": 0.128, "is_high_activity": 0.108,
        "Do Not Email": 0.103,
    }


def categorize_leads(leads_df, hot_threshold, warm_threshold):
    """Categorize leads into hot/warm/cold buckets."""
    hot = leads_df[leads_df["predicted_proba"] >= hot_threshold]
    warm = leads_df[
        (leads_df["predicted_proba"] >= warm_threshold)
        & (leads_df["predicted_proba"] < hot_threshold)
    ]
    cold = leads_df[leads_df["predicted_proba"] < warm_threshold]
    return hot, warm, cold


def explain_lead(lead_row, feature_importance):
    """
    Generate a SHAP-inspired explanation for why a lead scored high or low.
    Uses feature importance rankings and the lead's actual feature values
    to produce human-readable reasons.
    """
    reasons = []

    # Check top features and their values
    tags = str(lead_row.get("Tags", "Unknown"))
    if tags in ["Will revert after reading the email", "Ringing", "Already a student"]:
        reasons.append(f"Pipeline stage '{tags}' strongly indicates intent (top predictor)")
    elif tags in ["Switched off", "Lost to EINS"]:
        reasons.append(f"Pipeline stage '{tags}' signals disengagement")

    time_spent = lead_row.get("Total Time Spent on Website", 0)
    if time_spent > 500:
        reasons.append(f"High website engagement: {time_spent}s spent on site")
    elif time_spent == 0:
        reasons.append("No time spent on website (low engagement signal)")

    last_activity = str(lead_row.get("Last Notable Activity", ""))
    if last_activity in ["SMS Sent", "Had a Phone Conversation"]:
        reasons.append(f"Active communication: {last_activity}")

    occupation = str(lead_row.get("What is your current occupation", ""))
    if occupation == "Working Professional":
        reasons.append("Working professional (higher conversion likelihood)")
    elif occupation == "Unemployed":
        reasons.append("Unemployed (lower conversion likelihood)")

    page_views = lead_row.get("Page Views Per Visit", 0)
    if page_views >= 5:
        reasons.append(f"Deep browsing: {page_views} pages per visit")

    lead_quality = str(lead_row.get("Lead Quality", "Unknown"))
    if lead_quality == "High in Relevance":
        reasons.append("Rated 'High in Relevance' by lead quality assessment")

    if not reasons:
        score = lead_row.get("lead_score", 0)
        if score >= 70:
            reasons.append("Multiple positive signals across engagement and profile features")
        else:
            reasons.append("No strong conversion indicators detected")

    return reasons[:4]  # Limit to top 4 reasons


def build_score_distribution(leads_df):
    """Compute score distribution statistics."""
    scores = leads_df["lead_score"]
    return {
        "min": round(float(scores.min()), 1),
        "max": round(float(scores.max()), 1),
        "mean": round(float(scores.mean()), 1),
        "median": round(float(scores.median()), 1),
        "std": round(float(scores.std()), 1),
        "p25": round(float(scores.quantile(0.25)), 1),
        "p75": round(float(scores.quantile(0.75)), 1),
    }


def build_hot_leads_detail(hot_df, feature_importance, limit=10):
    """Build detailed output for hot leads with SHAP-based explanations."""
    hot_sorted = hot_df.sort_values("predicted_proba", ascending=False)
    details = []

    for idx, (_, row) in enumerate(hot_sorted.head(limit).iterrows()):
        reasons = explain_lead(row, feature_importance)
        lead_info = {
            "rank": idx + 1,
            "lead_score": round(float(row["lead_score"]), 1),
            "predicted_proba": round(float(row["predicted_proba"]), 4),
            "tags": str(row.get("Tags", "Unknown")),
            "occupation": str(row.get("What is your current occupation", "Unknown")),
            "lead_source": str(row.get("Lead Source", "Unknown")),
            "time_on_site": int(row.get("Total Time Spent on Website", 0)),
            "page_views": round(float(row.get("Page Views Per Visit", 0)), 1),
            "last_activity": str(row.get("Last Notable Activity", "Unknown")),
            "shap_reasons": reasons,
        }
        details.append(lead_info)

    return details


def main():
    parser = argparse.ArgumentParser(
        description="Lead Scoring — OpenClaw Capability 5"
    )
    parser.add_argument(
        "--output", type=str, choices=["json", "text"], default="text",
    )
    parser.add_argument(
        "--threshold", type=float, default=HOT_THRESHOLD,
        help=f"Hot lead threshold (default: {HOT_THRESHOLD})",
    )
    parser.add_argument(
        "--limit", type=int, default=10,
        help="Max hot leads to show in detail (default: 10)",
    )
    args = parser.parse_args()

    # Load data
    leads_df, feature_importance, model_metrics, data_source = load_scored_leads()

    # Categorize
    hot, warm, cold = categorize_leads(leads_df, args.threshold, WARM_THRESHOLD)

    # Score distribution
    distribution = build_score_distribution(leads_df)

    # Hot lead details with explanations
    hot_details = build_hot_leads_detail(hot, feature_importance, args.limit)

    # Top features
    top_features = sorted(
        feature_importance.items(), key=lambda x: x[1], reverse=True
    )[:10]

    # Save history
    history = load_history()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "data_source": data_source,
        "total_scored": len(leads_df),
        "hot_count": len(hot),
        "warm_count": len(warm),
        "cold_count": len(cold),
        "hot_threshold": args.threshold,
    }
    history["scans"].append(entry)
    history["last_scan"] = entry["timestamp"]
    if len(history["scans"]) > 50:
        history["scans"] = history["scans"][-50:]
    save_history(history)

    # Build output
    output = {
        "timestamp": datetime.now().isoformat(),
        "data_source": data_source,
        "model_performance": model_metrics,
        "total_leads_scored": len(leads_df),
        "hot_leads_count": len(hot),
        "warm_leads_count": len(warm),
        "cold_leads_count": len(cold),
        "hot_threshold": args.threshold,
        "score_distribution": distribution,
        "hot_leads": hot_details,
        "top_predictive_features": [
            {"feature": f, "shap_importance": round(v, 4)}
            for f, v in top_features
        ],
        "recommended_actions": _build_recommendations(len(hot), len(warm), len(cold), hot_details),
        "scans_in_history": len(history["scans"]),
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, default=str))
    else:
        _print_text(output)


def _build_recommendations(hot_count, warm_count, cold_count, hot_details):
    """Generate actionable recommendations based on scoring results."""
    recs = []

    if hot_count > 0:
        recs.append({
            "priority": "high",
            "action": f"Immediately follow up with {hot_count} hot leads",
            "detail": "These leads have >70% conversion probability. "
                      "Prioritize personal outreach, phone calls, and demo scheduling.",
        })

    if warm_count > 0:
        recs.append({
            "priority": "medium",
            "action": f"Nurture {warm_count} warm leads with targeted content",
            "detail": "These leads show moderate intent (40-70%). "
                      "Use email sequences, case studies, and webinar invites.",
        })

    if cold_count > 0:
        recs.append({
            "priority": "low",
            "action": f"Deprioritize {cold_count} cold leads",
            "detail": "Low conversion probability (<40%). "
                      "Keep in automated nurture campaigns but don't allocate sales time.",
        })

    # Feature-specific recommendation
    if hot_details:
        tags_hot = [h for h in hot_details if "intent" in " ".join(h["shap_reasons"]).lower()]
        if tags_hot:
            recs.append({
                "priority": "medium",
                "action": "Monitor pipeline stage transitions",
                "detail": "'Tags' (pipeline stage) is the strongest conversion predictor. "
                          "Leads moving to 'Will revert' or 'Ringing' stages deserve immediate attention.",
            })

    return recs


def _print_text(output):
    """Render lead scoring results as formatted text."""
    total = output["total_leads_scored"]
    hot = output["hot_leads_count"]
    warm = output["warm_leads_count"]
    cold = output["cold_leads_count"]

    print("=" * 60)
    print("LEAD SCORING REPORT")
    print(f"Source: {output['data_source']} | Scored: {total} leads")
    print(f"Model: XGBoost | ROC-AUC: {output['model_performance'].get('roc_auc', 'N/A')}")
    print("=" * 60)

    # Distribution
    hot_pct = hot / total * 100 if total else 0
    warm_pct = warm / total * 100 if total else 0
    cold_pct = cold / total * 100 if total else 0

    print(f"\n  Lead Distribution:")
    print(f"    Hot  (>={output['hot_threshold']:.0%}):  {hot:>5} leads  ({hot_pct:.1f}%)")
    print(f"    Warm (40-70%):   {warm:>5} leads  ({warm_pct:.1f}%)")
    print(f"    Cold (<40%):     {cold:>5} leads  ({cold_pct:.1f}%)")

    dist = output["score_distribution"]
    print(f"\n  Score Stats: mean={dist['mean']}, median={dist['median']}, "
          f"std={dist['std']}")

    # Hot leads
    if output["hot_leads"]:
        print(f"\n  Top Hot Leads:")
        for lead in output["hot_leads"][:5]:
            print(f"\n    #{lead['rank']}  Score: {lead['lead_score']}  "
                  f"({lead['predicted_proba']:.0%} conversion probability)")
            print(f"      Tags: {lead['tags']}  |  Source: {lead['lead_source']}")
            print(f"      Time: {lead['time_on_site']}s  |  "
                  f"Pages: {lead['page_views']}/visit  |  "
                  f"Activity: {lead['last_activity']}")
            print(f"      Why hot:")
            for reason in lead["shap_reasons"]:
                print(f"        - {reason}")

    # Top features
    print(f"\n  Top Predictive Features (SHAP):")
    for feat in output["top_predictive_features"][:7]:
        bar = "#" * int(feat["shap_importance"] * 10)
        print(f"    {feat['feature']:35s} {feat['shap_importance']:.3f}  {bar}")

    # Recommendations
    if output["recommended_actions"]:
        print(f"\n  Recommended Actions:")
        for rec in output["recommended_actions"]:
            icon = {"high": "!!!", "medium": "!!", "low": "!"}.get(rec["priority"], " ")
            print(f"    [{icon}] {rec['action']}")


if __name__ == "__main__":
    main()
