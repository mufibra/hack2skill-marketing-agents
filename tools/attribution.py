"""
Attribution Agent — Capability 4 of OpenClaw Marketing Agent (P10).

Wraps P6's multi-model marketing attribution pipeline (7 statistical models
+ LSTM deep learning) and P7's data pipeline to answer attribution questions.

Usage:
    python scripts/attribution.py --query "Which channel should get more budget?" --output json
    python scripts/attribution.py --query "Compare organic vs paid search" --output text
"""

import sys
import os
import json
import argparse
import random
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# P6 and P7 repo paths
P6_ROOT = Path(r"C:\Users\ahmad\Downloads\Hack2Skill\marketing-attribution-agent")
P7_ROOT = Path(r"C:\Users\ahmad\Downloads\Hack2Skill\marketing-data-pipeline")
if str(P6_ROOT) not in sys.path:
    sys.path.insert(0, str(P6_ROOT))

# Pre-computed data files from P6
P6_ATTRIBUTION_CSV = P6_ROOT / "data" / "attribution_results.csv"
P6_LSTM_CSV = P6_ROOT / "data" / "lstm_results.csv"
P6_JOURNEY_CSV = P6_ROOT / "data" / "journey_data.csv"

# History file
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "attribution_history.json"

# The 8 attribution models
MODEL_NAMES = [
    "first_click", "last_click", "linear", "time_decay",
    "position_based", "markov", "shapley", "lstm_deep_learning",
]

STATISTICAL_MODELS = MODEL_NAMES[:7]

CHANNEL_DISPLAY = {
    "organic_search": "Organic Search",
    "paid_search": "Paid Search",
    "direct": "Direct",
    "referral": "Referral",
    "social": "Social",
    "email": "Email",
    "display": "Display",
    "affiliate": "Affiliate",
    "other": "Other",
}


def load_history():
    """Load previous attribution query history."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"queries": [], "last_query": None}


def save_history(history):
    """Save attribution query history."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, default=str)


def load_attribution_data():
    """
    Load attribution results. Priority:
    1. P6's pre-computed CSV files (fastest, no dependencies)
    2. Run P6's models live (requires MAM + BigQuery)
    3. Fall back to built-in sample data
    """
    import pandas as pd

    attribution_df = None
    lstm_df = None
    journey_stats = None
    data_source = "sample"

    # Try loading P6's pre-computed results
    try:
        if P6_ATTRIBUTION_CSV.exists():
            attribution_df = pd.read_csv(P6_ATTRIBUTION_CSV)
            data_source = "p6_precomputed"

        if P6_LSTM_CSV.exists():
            lstm_df = pd.read_csv(P6_LSTM_CSV)

        if P6_JOURNEY_CSV.exists():
            jdf = pd.read_csv(P6_JOURNEY_CSV)
            journey_stats = {
                "total_journeys": len(jdf),
                "conversions": int(jdf["has_conversion"].sum()),
                "conversion_rate": round(jdf["has_conversion"].mean() * 100, 2),
                "avg_journey_length": round(jdf["journey_length"].mean(), 1),
                "total_revenue": round(jdf["conversion_value"].sum(), 2),
                "unique_channels": int(
                    jdf["journey_path"].str.split(" > ").explode().nunique()
                ),
            }
    except Exception:
        pass

    # Try running P6's models live if no pre-computed data
    if attribution_df is None:
        try:
            from src.attribution.data_prep import extract_journeys
            from src.attribution.models import run_all_models

            jdf = extract_journeys()
            results = run_all_models(jdf)
            attribution_df = results["results"]
            data_source = "p6_live"

            journey_stats = {
                "total_journeys": len(jdf),
                "conversions": int(jdf["has_conversion"].sum()),
                "conversion_rate": round(jdf["has_conversion"].mean() * 100, 2),
                "avg_journey_length": round(jdf["journey_length"].mean(), 1),
                "total_revenue": round(jdf["conversion_value"].sum(), 2),
                "unique_channels": int(
                    jdf["journey_path"].str.split(" > ").explode().nunique()
                ),
            }
        except Exception:
            pass

    # Fallback: built-in sample data
    if attribution_df is None:
        attribution_df, lstm_df, journey_stats = _generate_sample_data()
        data_source = "sample"

    return attribution_df, lstm_df, journey_stats, data_source


def _generate_sample_data():
    """Generate realistic sample attribution data when P6 is unavailable."""
    import pandas as pd

    channels = ["organic_search", "paid_search", "direct", "referral", "other"]

    # Realistic attribution weights that sum to ~1.0 per model
    sample_data = {
        "channel": channels,
        "first_click":    [0.358, 0.046, 0.228, 0.170, 0.198],
        "last_click":     [0.239, 0.009, 0.213, 0.266, 0.273],
        "linear":         [0.271, 0.024, 0.216, 0.235, 0.254],
        "time_decay":     [0.271, 0.023, 0.215, 0.236, 0.254],
        "position_based": [0.288, 0.026, 0.219, 0.224, 0.242],
        "markov":         [0.260, 0.037, 0.225, 0.234, 0.244],
        "shapley":        [0.000, 0.000, 0.000, 0.000, 0.000],
    }
    attribution_df = pd.DataFrame(sample_data)

    lstm_data = {
        "channel": channels,
        "lstm_deep_learning": [0.319, 0.035, 0.216, 0.205, 0.226],
    }
    lstm_df = pd.DataFrame(lstm_data)

    journey_stats = {
        "total_journeys": 14206,
        "conversions": 1015,
        "conversion_rate": 7.14,
        "avg_journey_length": 8.3,
        "total_revenue": 48291.50,
        "unique_channels": 5,
    }

    return attribution_df, lstm_df, journey_stats


def build_model_results(attribution_df, lstm_df):
    """Build per-model channel rankings from the attribution DataFrames."""
    import pandas as pd

    model_results = {}

    # Statistical models
    for model in STATISTICAL_MODELS:
        if model in attribution_df.columns:
            ranked = attribution_df[["channel", model]].copy()
            ranked = ranked.sort_values(model, ascending=False)
            rankings = []
            for _, row in ranked.iterrows():
                val = row[model]
                if val > 0:
                    rankings.append({
                        "channel": row["channel"],
                        "display_name": CHANNEL_DISPLAY.get(
                            row["channel"], row["channel"]
                        ),
                        "attribution_weight": round(float(val), 4),
                        "attribution_pct": round(float(val) * 100, 2),
                    })
            model_results[model] = rankings

    # LSTM model
    if lstm_df is not None and "lstm_deep_learning" in lstm_df.columns:
        ranked = lstm_df.sort_values("lstm_deep_learning", ascending=False)
        rankings = []
        for _, row in ranked.iterrows():
            val = row["lstm_deep_learning"]
            if val > 0:
                rankings.append({
                    "channel": row["channel"],
                    "display_name": CHANNEL_DISPLAY.get(
                        row["channel"], row["channel"]
                    ),
                    "attribution_weight": round(float(val), 4),
                    "attribution_pct": round(float(val) * 100, 2),
                })
        model_results["lstm_deep_learning"] = rankings

    return model_results


def compute_model_agreement(model_results):
    """
    Compute agreement score across models.
    High agreement = models rank channels similarly.
    Uses average rank correlation between all model pairs.
    """
    if len(model_results) < 2:
        return {"score": 0.0, "interpretation": "insufficient_models"}

    # Get channel rankings per model
    rankings = {}
    for model, channels in model_results.items():
        if not channels:
            continue
        rank_map = {}
        for rank, ch in enumerate(channels, 1):
            rank_map[ch["channel"]] = rank
        rankings[model] = rank_map

    if len(rankings) < 2:
        return {"score": 0.0, "interpretation": "insufficient_models"}

    # Compute pairwise Spearman rank correlation (simplified)
    models = list(rankings.keys())
    all_channels = set()
    for rank_map in rankings.values():
        all_channels.update(rank_map.keys())
    all_channels = sorted(all_channels)
    n = len(all_channels)

    if n < 2:
        return {"score": 1.0, "interpretation": "single_channel"}

    correlations = []
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            r1 = rankings[models[i]]
            r2 = rankings[models[j]]
            # Compute rank difference squared
            d_sq_sum = 0
            for ch in all_channels:
                rank_a = r1.get(ch, n + 1)
                rank_b = r2.get(ch, n + 1)
                d_sq_sum += (rank_a - rank_b) ** 2
            # Spearman: 1 - (6 * sum(d²)) / (n * (n² - 1))
            rho = 1 - (6 * d_sq_sum) / (n * (n ** 2 - 1))
            correlations.append(rho)

    avg_correlation = sum(correlations) / len(correlations)
    # Normalize to 0-100 scale
    score = round(max(0, (avg_correlation + 1) / 2 * 100), 1)

    if score >= 80:
        interp = "strong_agreement"
    elif score >= 60:
        interp = "moderate_agreement"
    elif score >= 40:
        interp = "mixed_signals"
    else:
        interp = "significant_disagreement"

    return {
        "score": score,
        "avg_rank_correlation": round(avg_correlation, 4),
        "model_pairs_compared": len(correlations),
        "interpretation": interp,
    }


def find_top_channel(model_results):
    """Determine the top channel across all models."""
    channel_votes = {}
    channel_total_weight = {}

    for model, channels in model_results.items():
        if not channels:
            continue
        # Top channel gets a vote
        top = channels[0]["channel"]
        channel_votes[top] = channel_votes.get(top, 0) + 1

        # Accumulate weights
        for ch in channels:
            name = ch["channel"]
            channel_total_weight[name] = (
                channel_total_weight.get(name, 0) + ch["attribution_weight"]
            )

    if not channel_votes:
        return {"channel": "unknown", "confidence": "low"}

    # Winner by vote count, tie-break by total weight
    winner = max(
        channel_votes.keys(),
        key=lambda c: (channel_votes[c], channel_total_weight.get(c, 0)),
    )
    total_models = len(model_results)
    votes = channel_votes[winner]
    confidence = "high" if votes / total_models >= 0.7 else (
        "medium" if votes / total_models >= 0.4 else "low"
    )

    return {
        "channel": winner,
        "display_name": CHANNEL_DISPLAY.get(winner, winner),
        "models_agreeing": votes,
        "total_models": total_models,
        "confidence": confidence,
        "avg_attribution_weight": round(
            channel_total_weight.get(winner, 0) / total_models, 4
        ),
    }


def generate_budget_recommendations(model_results, top_channel_info):
    """Generate budget allocation recommendations based on model consensus."""
    if not model_results:
        return []

    # Average attribution weight across all models per channel
    channel_avg = {}
    model_count = len(model_results)

    for model, channels in model_results.items():
        for ch in channels:
            name = ch["channel"]
            if name not in channel_avg:
                channel_avg[name] = 0.0
            channel_avg[name] += ch["attribution_weight"]

    for ch in channel_avg:
        channel_avg[ch] = round(channel_avg[ch] / model_count, 4)

    # Sort by average weight
    sorted_channels = sorted(
        channel_avg.items(), key=lambda x: x[1], reverse=True
    )

    recs = []
    for rank, (channel, avg_weight) in enumerate(sorted_channels, 1):
        pct = round(avg_weight * 100, 1)
        display = CHANNEL_DISPLAY.get(channel, channel)

        if rank == 1:
            action = "increase"
            rationale = (
                f"{display} has the highest average attribution ({pct}%) "
                f"across all models. Consider increasing budget allocation."
            )
        elif rank == 2:
            action = "maintain_or_increase"
            rationale = (
                f"{display} ranks #2 in attribution ({pct}%). "
                f"Maintain current spend or explore incremental increases."
            )
        elif avg_weight >= 0.15:
            action = "maintain"
            rationale = (
                f"{display} contributes {pct}% of conversions. "
                f"Maintain current investment level."
            )
        else:
            action = "review"
            rationale = (
                f"{display} shows low attribution ({pct}%). "
                f"Review ROI and consider reallocating budget."
            )

        recs.append({
            "rank": rank,
            "channel": channel,
            "display_name": display,
            "avg_attribution_pct": pct,
            "recommended_action": action,
            "rationale": rationale,
        })

    return recs


def analyze_model_disagreements(model_results):
    """Find channels where models disagree the most."""
    if not model_results:
        return []

    # Collect all attribution weights per channel
    channel_weights = {}
    for model, channels in model_results.items():
        for ch in channels:
            name = ch["channel"]
            if name not in channel_weights:
                channel_weights[name] = {}
            channel_weights[name][model] = ch["attribution_weight"]

    disagreements = []
    for channel, weights in channel_weights.items():
        if len(weights) < 2:
            continue
        values = list(weights.values())
        spread = max(values) - min(values)
        max_model = max(weights, key=weights.get)
        min_model = min(weights, key=weights.get)

        if spread > 0.05:  # Only report meaningful disagreements
            disagreements.append({
                "channel": channel,
                "display_name": CHANNEL_DISPLAY.get(channel, channel),
                "spread": round(spread, 4),
                "spread_pct": round(spread * 100, 1),
                "highest_model": max_model,
                "highest_value": round(weights[max_model] * 100, 1),
                "lowest_model": min_model,
                "lowest_value": round(weights[min_model] * 100, 1),
            })

    return sorted(disagreements, key=lambda x: x["spread"], reverse=True)


def classify_query(query):
    """Classify the user's question to tailor the response."""
    query_lower = query.lower()

    if any(w in query_lower for w in ["budget", "spend", "allocat", "invest"]):
        return "budget"
    if any(w in query_lower for w in ["compare", "vs", "versus", "difference"]):
        return "comparison"
    if any(w in query_lower for w in ["best", "top", "most", "highest", "winner"]):
        return "top_channel"
    if any(w in query_lower for w in ["model", "agree", "disagree", "consensus"]):
        return "model_analysis"
    if any(w in query_lower for w in ["lstm", "deep learn", "neural"]):
        return "deep_learning"
    return "general"


def main():
    parser = argparse.ArgumentParser(
        description="Attribution Agent — OpenClaw Capability 4"
    )
    parser.add_argument(
        "--query", type=str, default="Which channel drives the most conversions?",
        help="Natural language attribution question",
    )
    parser.add_argument(
        "--output", type=str, choices=["json", "text"], default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    # Load history
    history = load_history()

    # Load attribution data
    attribution_df, lstm_df, journey_stats, data_source = load_attribution_data()

    # Build per-model channel rankings
    model_results = build_model_results(attribution_df, lstm_df)

    # Compute agreement
    agreement = compute_model_agreement(model_results)

    # Find top channel
    top_channel = find_top_channel(model_results)

    # Budget recommendations
    budget_recs = generate_budget_recommendations(model_results, top_channel)

    # Model disagreements
    disagreements = analyze_model_disagreements(model_results)

    # Classify the query
    query_type = classify_query(args.query)

    # Count active models (those with actual data)
    active_models = [m for m, r in model_results.items() if r]

    # Save to history
    history_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": args.query,
        "query_type": query_type,
        "data_source": data_source,
        "top_channel": top_channel["channel"],
        "agreement_score": agreement["score"],
    }
    history["queries"].append(history_entry)
    history["last_query"] = history_entry["timestamp"]
    if len(history["queries"]) > 50:
        history["queries"] = history["queries"][-50:]
    save_history(history)

    # Build output
    output = {
        "timestamp": datetime.now().isoformat(),
        "query": args.query,
        "query_type": query_type,
        "data_source": data_source,
        "journey_stats": journey_stats,
        "models_active": active_models,
        "models_count": len(active_models),
        "model_results": model_results,
        "top_channel": top_channel,
        "model_agreement": agreement,
        "budget_recommendations": budget_recs,
        "model_disagreements": disagreements,
        "queries_in_history": len(history["queries"]),
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, default=str))
    else:
        _print_text(output)


def _print_text(output):
    """Render attribution results as formatted text."""
    agreement = output["model_agreement"]
    top = output["top_channel"]

    print("=" * 60)
    print("ATTRIBUTION ANALYSIS")
    print(f"Query: {output['query']}")
    print(f"Source: {output['data_source']} | Models: {output['models_count']}")
    print("=" * 60)

    # Journey stats
    js = output.get("journey_stats")
    if js:
        print(f"\n  Data Summary:")
        print(f"    Journeys: {js['total_journeys']:,}  |  "
              f"Conversions: {js['conversions']:,}  |  "
              f"Rate: {js['conversion_rate']}%")
        print(f"    Avg Length: {js['avg_journey_length']} touchpoints  |  "
              f"Revenue: ${js['total_revenue']:,.2f}")

    # Top channel
    conf_icon = {"high": "+++", "medium": "++", "low": "+"}.get(
        top["confidence"], "?"
    )
    print(f"\n  Top Channel: {top.get('display_name', top['channel'])} "
          f"[{conf_icon} {top['confidence']} confidence]")
    print(f"    {top['models_agreeing']}/{top['total_models']} models agree  |  "
          f"Avg weight: {top['avg_attribution_weight']:.1%}")

    # Model agreement
    interp_labels = {
        "strong_agreement": "Strong",
        "moderate_agreement": "Moderate",
        "mixed_signals": "Mixed",
        "significant_disagreement": "Low",
    }
    print(f"\n  Model Agreement: {agreement['score']:.0f}/100 "
          f"({interp_labels.get(agreement['interpretation'], agreement['interpretation'])})")

    # Budget recommendations
    print(f"\n  Budget Recommendations:")
    for rec in output["budget_recommendations"]:
        action_icons = {
            "increase": "^", "maintain_or_increase": "~^",
            "maintain": "=", "review": "v",
        }
        icon = action_icons.get(rec["recommended_action"], " ")
        print(f"    [{icon}] #{rec['rank']} {rec['display_name']:20s} "
              f"{rec['avg_attribution_pct']:5.1f}%  — {rec['recommended_action']}")

    # Model disagreements
    if output["model_disagreements"]:
        print(f"\n  Key Disagreements:")
        for d in output["model_disagreements"][:3]:
            print(f"    {d['display_name']:20s} spread: {d['spread_pct']:.1f}% "
                  f"({d['highest_model']}: {d['highest_value']:.1f}% "
                  f"vs {d['lowest_model']}: {d['lowest_value']:.1f}%)")


if __name__ == "__main__":
    main()
