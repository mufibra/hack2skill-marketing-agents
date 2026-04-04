"""
Sentiment Monitoring — Capability 3 of OpenClaw Marketing Agent (P10).

Wraps P8's DistilBERT sentiment classifier to monitor customer feedback,
detect negative sentiment spikes, and produce structured JSON reports.

Usage:
    python scripts/sentiment.py --output json
    python scripts/sentiment.py --source live
    python scripts/sentiment.py --source sample --output json
"""

import sys
import os
import json
import argparse
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# P8 repo path
P8_ROOT = Path(r"C:\Users\ahmad\Downloads\Hack2Skill\nlp-customer-intelligence")
if str(P8_ROOT) not in sys.path:
    sys.path.insert(0, str(P8_ROOT))

# Data directory for history
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "sentiment_history.json"
P8_TICKETS = P8_ROOT / "data" / "synthetic" / "support_tickets.csv"

# Negative spike threshold
SPIKE_THRESHOLD = 0.15  # 15% increase in negative ratio triggers alert


def load_history():
    """Load previous sentiment scan results."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scans": [], "last_scan": None, "baseline_negative_ratio": None}


def save_history(history):
    """Save sentiment scan results."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, default=str)


def load_feedback_data(sample_size=200):
    """
    Load customer feedback data. Tries P8's synthetic tickets first,
    falls back to built-in sample data.
    """
    try:
        import pandas as pd
        if P8_TICKETS.exists():
            df = pd.read_csv(P8_TICKETS)
            # Sample recent tickets (simulate a monitoring window)
            if len(df) > sample_size:
                df = df.sample(n=sample_size, random_state=int(
                    datetime.now().strftime("%Y%m%d")
                ))
            return df[["text", "sentiment_label", "category", "customer_id",
                        "created_date", "priority"]].to_dict("records"), "p8_synthetic"
    except Exception:
        pass

    return _generate_sample_feedback(sample_size), "sample"


def _generate_sample_feedback(n=200):
    """Generate sample customer feedback when P8 data is unavailable."""
    seed = int(datetime.now().strftime("%Y%m%d"))
    rng = random.Random(seed)

    categories = ["billing", "shipping", "product_defect", "cancellation",
                   "feature_request", "account_access"]

    negative_templates = [
        "I've been waiting {days} days for my order and still nothing.",
        "Your billing system charged me twice this month. Unacceptable.",
        "The product broke after {days} days of use. Very disappointed.",
        "I want to cancel my subscription immediately. Terrible experience.",
        "Cannot log into my account for the third time this week.",
        "Support took {days} days to respond. This is ridiculous.",
        "The quality has gone downhill. Not worth the price anymore.",
        "Shipping was supposed to take 3 days, it's been {days}.",
        "I'm switching to a competitor. Your service has gotten worse.",
        "Refund still not processed after {days} days. Where is my money?",
    ]

    neutral_templates = [
        "I have a question about my recent order status.",
        "Can you explain how the new pricing works?",
        "I'd like to update my shipping address please.",
        "When will the new feature be available?",
        "How do I change my subscription plan?",
        "Is there a way to export my data?",
        "I need help setting up the integration.",
        "What are the differences between plans?",
    ]

    positive_templates = [
        "Love the new update! The interface is so much cleaner.",
        "Your support team was incredibly helpful. Thank you!",
        "Best product in the category. Highly recommend to everyone.",
        "The new feature saved me hours of work this week.",
        "Shipping was super fast. Received in just {days} days!",
        "Great value for money. Impressed with the quality.",
        "Your team went above and beyond to resolve my issue.",
        "Been a customer for years and the product keeps getting better.",
    ]

    # Distribution: ~45% negative, ~30% neutral, ~25% positive
    # (slightly negative-heavy to simulate monitoring scenario)
    feedback = []
    for i in range(n):
        roll = rng.random()
        if roll < 0.45:
            sentiment = "negative"
            text = rng.choice(negative_templates).format(days=rng.randint(5, 30))
        elif roll < 0.75:
            sentiment = "neutral"
            text = rng.choice(neutral_templates)
        else:
            sentiment = "positive"
            text = rng.choice(positive_templates).format(days=rng.randint(1, 3))

        feedback.append({
            "text": text,
            "sentiment_label": sentiment,
            "category": rng.choice(categories),
            "customer_id": f"CUST-{rng.randint(1000, 9999)}",
            "created_date": (datetime.now() - timedelta(
                days=rng.randint(0, 30)
            )).strftime("%Y-%m-%d"),
            "priority": rng.choice(["low", "medium", "high"]),
        })

    return feedback


def run_model_inference(feedback_records):
    """
    Try to use P8's DistilBERT model for sentiment classification.
    Falls back to using the pre-labeled sentiment from the data.
    """
    analysis_method = "pre_labeled"
    results = []

    # Try P8's trained DistilBERT model
    try:
        from src.sentiment_model import SentimentClassifier
        model_dir = P8_ROOT / "models" / "sentiment"
        if model_dir.exists() and (model_dir / "config.json").exists():
            classifier = SentimentClassifier(str(model_dir))
            texts = [r["text"] for r in feedback_records]
            predictions = classifier.predict_batch(texts, batch_size=32)
            analysis_method = "distilbert"

            for record, pred in zip(feedback_records, predictions):
                results.append({
                    "text": record["text"],
                    "predicted_sentiment": pred["label"],
                    "confidence": pred["confidence"],
                    "category": record.get("category", "unknown"),
                    "customer_id": record.get("customer_id", "unknown"),
                    "created_date": record.get("created_date", "unknown"),
                    "priority": record.get("priority", "medium"),
                })
            return results, analysis_method
    except Exception:
        pass

    # Fallback: use pre-labeled sentiments from the data
    for record in feedback_records:
        label = record.get("sentiment_label", "neutral")
        # Simulate confidence scores
        conf_map = {"negative": 0.87, "neutral": 0.72, "positive": 0.91}
        results.append({
            "text": record["text"],
            "predicted_sentiment": label,
            "confidence": conf_map.get(label, 0.75) + random.uniform(-0.1, 0.1),
            "category": record.get("category", "unknown"),
            "customer_id": record.get("customer_id", "unknown"),
            "created_date": record.get("created_date", "unknown"),
            "priority": record.get("priority", "medium"),
        })

    return results, analysis_method


def compute_sentiment_metrics(results):
    """Compute aggregate sentiment metrics from analysis results."""
    total = len(results)
    if total == 0:
        return {}

    neg = sum(1 for r in results if r["predicted_sentiment"] == "negative")
    neu = sum(1 for r in results if r["predicted_sentiment"] == "neutral")
    pos = sum(1 for r in results if r["predicted_sentiment"] == "positive")

    neg_ratio = neg / total
    pos_ratio = pos / total
    neu_ratio = neu / total

    # Average confidence
    avg_confidence = sum(r["confidence"] for r in results) / total

    # Sentiment score: (positive - negative) / total, range -1 to +1
    sentiment_score = (pos - neg) / total

    # Category breakdown
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"negative": 0, "neutral": 0, "positive": 0, "total": 0}
        categories[cat][r["predicted_sentiment"]] += 1
        categories[cat]["total"] += 1

    # Find worst categories (highest negative ratio)
    category_neg_ratios = {}
    for cat, counts in categories.items():
        if counts["total"] > 0:
            category_neg_ratios[cat] = counts["negative"] / counts["total"]

    worst_categories = sorted(
        category_neg_ratios.items(), key=lambda x: x[1], reverse=True
    )[:3]

    # High-priority negative reviews
    high_priority_negatives = [
        r for r in results
        if r["predicted_sentiment"] == "negative" and r["priority"] == "high"
    ]

    return {
        "total_analyzed": total,
        "sentiment_distribution": {
            "negative": neg,
            "neutral": neu,
            "positive": pos,
        },
        "sentiment_ratios": {
            "negative_ratio": round(neg_ratio, 4),
            "neutral_ratio": round(neu_ratio, 4),
            "positive_ratio": round(pos_ratio, 4),
        },
        "overall_sentiment_score": round(sentiment_score, 4),
        "average_confidence": round(avg_confidence, 4),
        "category_breakdown": categories,
        "worst_categories": [
            {"category": cat, "negative_ratio": round(ratio, 4)}
            for cat, ratio in worst_categories
        ],
        "high_priority_negative_count": len(high_priority_negatives),
    }


def detect_spike(current_metrics, history):
    """
    Detect negative sentiment spikes by comparing current negative ratio
    against the baseline (rolling average of previous scans).
    """
    current_neg_ratio = current_metrics["sentiment_ratios"]["negative_ratio"]

    # Calculate baseline from history
    if history["scans"]:
        prev_ratios = [
            s["metrics"]["sentiment_ratios"]["negative_ratio"]
            for s in history["scans"][-10:]  # last 10 scans
        ]
        baseline = sum(prev_ratios) / len(prev_ratios)
    elif history.get("baseline_negative_ratio") is not None:
        baseline = history["baseline_negative_ratio"]
    else:
        # First scan — no baseline to compare against
        return {
            "spike_detected": False,
            "baseline_negative_ratio": round(current_neg_ratio, 4),
            "current_negative_ratio": round(current_neg_ratio, 4),
            "delta": 0.0,
            "message": "First scan — establishing baseline.",
        }

    delta = current_neg_ratio - baseline

    spike_detected = delta > SPIKE_THRESHOLD

    if spike_detected:
        severity = "urgent" if delta > 0.25 else "notable"
        message = (
            f"Negative sentiment spike detected: {current_neg_ratio:.1%} "
            f"(baseline: {baseline:.1%}, +{delta:.1%} increase). "
            f"Severity: {severity}."
        )
    elif delta > 0.05:
        severity = "notable"
        message = (
            f"Slight uptick in negative sentiment: {current_neg_ratio:.1%} "
            f"(baseline: {baseline:.1%}, +{delta:.1%}). Monitoring."
        )
    elif delta < -0.05:
        severity = "positive"
        message = (
            f"Positive trend: negative sentiment at {current_neg_ratio:.1%} "
            f"(baseline: {baseline:.1%}, {delta:.1%}). Improving."
        )
    else:
        severity = "stable"
        message = (
            f"Sentiment stable: {current_neg_ratio:.1%} "
            f"(baseline: {baseline:.1%})."
        )

    return {
        "spike_detected": spike_detected,
        "baseline_negative_ratio": round(baseline, 4),
        "current_negative_ratio": round(current_neg_ratio, 4),
        "delta": round(delta, 4),
        "severity": severity,
        "message": message,
    }


def generate_recommendations(metrics, spike_info):
    """Generate actionable recommendations based on sentiment analysis."""
    recs = []

    # Spike-based recommendations
    if spike_info["spike_detected"]:
        recs.append({
            "priority": "high",
            "action": "Investigate negative sentiment spike immediately",
            "detail": spike_info["message"],
        })

    # Category-based recommendations
    for wc in metrics.get("worst_categories", []):
        if wc["negative_ratio"] > 0.5:
            recs.append({
                "priority": "high",
                "action": f"Review {wc['category']} feedback — {wc['negative_ratio']:.0%} negative",
                "detail": f"The '{wc['category']}' category has a very high negative ratio. "
                          f"Consider escalating to the relevant team.",
            })

    # High-priority negative tickets
    hp_count = metrics.get("high_priority_negative_count", 0)
    if hp_count > 0:
        recs.append({
            "priority": "medium",
            "action": f"Address {hp_count} high-priority negative tickets",
            "detail": "These tickets are marked high priority with negative sentiment "
                      "and should be reviewed promptly.",
        })

    # Overall sentiment
    score = metrics.get("overall_sentiment_score", 0)
    if score < -0.2:
        recs.append({
            "priority": "medium",
            "action": "Overall sentiment is significantly negative",
            "detail": f"Sentiment score: {score:+.3f}. Consider a broader review "
                      f"of customer experience and support processes.",
        })

    if not recs:
        recs.append({
            "priority": "low",
            "action": "No immediate action required",
            "detail": "Sentiment is within normal parameters. Continue monitoring.",
        })

    return recs


def get_sample_negatives(results, limit=5):
    """Get sample negative reviews for the report."""
    negatives = [
        r for r in results if r["predicted_sentiment"] == "negative"
    ]
    # Sort by confidence (most confidently negative first)
    negatives.sort(key=lambda x: x["confidence"], reverse=True)
    return [
        {
            "text": r["text"][:200],
            "confidence": round(r["confidence"], 3),
            "category": r["category"],
            "priority": r["priority"],
            "customer_id": r["customer_id"],
        }
        for r in negatives[:limit]
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Sentiment Monitoring — OpenClaw Capability 3"
    )
    parser.add_argument(
        "--output", type=str, choices=["json", "text"], default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--source", type=str, choices=["live", "sample"], default="live",
        help="Data source: live (P8 data) or sample (built-in)",
    )
    parser.add_argument(
        "--sample-size", type=int, default=200,
        help="Number of feedback records to analyze (default: 200)",
    )
    args = parser.parse_args()

    # Load history
    history = load_history()

    # Load feedback data
    if args.source == "sample":
        feedback, data_source = _generate_sample_feedback(args.sample_size), "sample"
    else:
        feedback, data_source = load_feedback_data(args.sample_size)

    # Run sentiment analysis
    results, analysis_method = run_model_inference(feedback)

    # Compute metrics
    metrics = compute_sentiment_metrics(results)

    # Detect spikes
    spike_info = detect_spike(metrics, history)

    # Generate recommendations
    recommendations = generate_recommendations(metrics, spike_info)

    # Sample negative reviews
    sample_negatives = get_sample_negatives(results)

    # Determine overall severity
    if spike_info.get("spike_detected"):
        overall_severity = "urgent" if spike_info.get("severity") == "urgent" else "notable"
    elif spike_info.get("severity") == "notable":
        overall_severity = "notable"
    elif spike_info.get("severity") == "positive":
        overall_severity = "positive"
    else:
        overall_severity = "stable"

    # Update history
    scan_entry = {
        "timestamp": datetime.now().isoformat(),
        "data_source": data_source,
        "analysis_method": analysis_method,
        "metrics": metrics,
        "spike_info": spike_info,
        "overall_severity": overall_severity,
    }
    history["scans"].append(scan_entry)
    history["last_scan"] = scan_entry["timestamp"]
    if history["baseline_negative_ratio"] is None:
        history["baseline_negative_ratio"] = metrics["sentiment_ratios"]["negative_ratio"]
    # Keep last 50 scans
    if len(history["scans"]) > 50:
        history["scans"] = history["scans"][-50:]
    save_history(history)

    # Build output
    output = {
        "timestamp": datetime.now().isoformat(),
        "data_source": data_source,
        "analysis_method": analysis_method,
        "overall_severity": overall_severity,
        "overall_sentiment": metrics.get("overall_sentiment_score", 0),
        "sentiment_distribution": metrics.get("sentiment_distribution", {}),
        "sentiment_ratios": metrics.get("sentiment_ratios", {}),
        "negative_spike_detected": spike_info.get("spike_detected", False),
        "spike_info": spike_info,
        "worst_categories": metrics.get("worst_categories", []),
        "high_priority_negative_count": metrics.get("high_priority_negative_count", 0),
        "sample_negative_reviews": sample_negatives,
        "recommended_actions": recommendations,
        "total_analyzed": metrics.get("total_analyzed", 0),
        "average_confidence": metrics.get("average_confidence", 0),
        "scans_in_history": len(history["scans"]),
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, default=str))
    else:
        severity_icons = {
            "stable": "🟢", "positive": "🟢",
            "notable": "🟡", "urgent": "🔴",
        }
        icon = severity_icons.get(overall_severity, "⚪")

        print("=" * 60)
        print(f"SENTIMENT MONITOR  {icon} {overall_severity.upper()}")
        print(f"Source: {data_source} | Method: {analysis_method}")
        print(f"Analyzed: {metrics['total_analyzed']} feedback records")
        print("=" * 60)

        dist = metrics["sentiment_distribution"]
        ratios = metrics["sentiment_ratios"]
        print(f"\n  Sentiment Distribution:")
        print(f"    Negative: {dist['negative']:>4}  ({ratios['negative_ratio']:.1%})")
        print(f"    Neutral:  {dist['neutral']:>4}  ({ratios['neutral_ratio']:.1%})")
        print(f"    Positive: {dist['positive']:>4}  ({ratios['positive_ratio']:.1%})")
        print(f"    Score:    {metrics['overall_sentiment_score']:+.3f}")

        print(f"\n  Spike Detection:")
        print(f"    {spike_info['message']}")

        if metrics["worst_categories"]:
            print(f"\n  Worst Categories:")
            for wc in metrics["worst_categories"]:
                print(f"    {wc['category']:20s}  {wc['negative_ratio']:.0%} negative")

        if sample_negatives:
            print(f"\n  Sample Negative Reviews:")
            for sn in sample_negatives[:3]:
                print(f"    [{sn['category']}] {sn['text'][:80]}...")

        if recommendations:
            print(f"\n  Recommended Actions:")
            for rec in recommendations:
                pri = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    rec["priority"], "⚪"
                )
                print(f"    {pri} {rec['action']}")


if __name__ == "__main__":
    main()
