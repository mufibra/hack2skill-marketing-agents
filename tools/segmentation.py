"""
Segment-Triggered Campaigns — Capability 6 of OpenClaw Marketing Agent (P10).

Wraps P5's K-means customer segmentation and CLV prediction to detect
segment shifts, generate campaign recommendations, and identify retention risks.

Usage:
    python scripts/segmentation.py --output json
    python scripts/segmentation.py --output text
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

# P5 repo path
P5_ROOT = Path(r"C:\Users\ahmad\Downloads\Hack2Skill\customer-segmentation-clv")
if str(P5_ROOT) not in sys.path:
    sys.path.insert(0, str(P5_ROOT))

# P5 pre-computed data
P5_CLV_PREDICTIONS = P5_ROOT / "data" / "processed" / "clv_predictions.csv"
P5_RFM_CLUSTERED = P5_ROOT / "data" / "processed" / "rfm_clustered.csv"
P5_CLV_RETURNING = P5_ROOT / "data" / "processed" / "clv_returning_only.csv"

# History
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORY_FILE = DATA_DIR / "segmentation_history.json"

# Segment campaign mapping
CAMPAIGN_TEMPLATES = {
    "VIP Champions": {
        "campaign_type": "loyalty_retention",
        "campaigns": [
            "VIP exclusive early access to new products",
            "Referral reward program (give $X, get $X)",
            "Personalized thank-you with premium perks",
            "Private sale or members-only event invitation",
        ],
        "urgency": "maintain",
        "channel_mix": ["email", "sms", "direct_mail"],
    },
    "Loyal Regulars": {
        "campaign_type": "upsell_cross_sell",
        "campaigns": [
            "Cross-sell complementary product bundles",
            "Tiered loyalty program with upgrade incentives",
            "Early access to seasonal collections",
            "Personalized product recommendations email series",
        ],
        "urgency": "grow",
        "channel_mix": ["email", "retargeting", "social"],
    },
    "New Potentials": {
        "campaign_type": "onboarding_nurture",
        "campaigns": [
            "Welcome email series with brand story",
            "First repeat-purchase discount (10-15% off)",
            "Educational content about product usage",
            "Social proof campaign (reviews, testimonials)",
        ],
        "urgency": "convert",
        "channel_mix": ["email", "social", "push"],
    },
    "Lost / Dormant": {
        "campaign_type": "win_back",
        "campaigns": [
            "Win-back email: 'We miss you' with 20% off",
            "Sunset flow: last-chance offer before list removal",
            "Survey: 'What made you leave?' feedback request",
            "Re-engagement retargeting ads with new products",
        ],
        "urgency": "re_engage",
        "channel_mix": ["email", "retargeting", "sms"],
    },
    "Lost Causes": {
        "campaign_type": "win_back",
        "campaigns": [
            "Win-back email: 'We miss you' with 20% off",
            "Sunset flow: last-chance offer before list removal",
            "Survey: 'What made you leave?' feedback request",
            "Re-engagement retargeting ads with new products",
        ],
        "urgency": "re_engage",
        "channel_mix": ["email", "retargeting", "sms"],
    },
}

# Fallback for unknown segments
DEFAULT_CAMPAIGN = {
    "campaign_type": "general_nurture",
    "campaigns": [
        "General engagement email with brand updates",
        "Seasonal promotion offer",
    ],
    "urgency": "monitor",
    "channel_mix": ["email"],
}


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scans": [], "last_scan": None}


def save_history(history):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, default=str)


def load_segmentation_data():
    """
    Load segmentation data. Priority:
    1. P5's pre-computed clv_predictions.csv
    2. Run P5's pipeline live
    3. Fall back to sample data
    """
    import pandas as pd

    data_source = "sample"
    df = None

    # Try P5's pre-computed data
    try:
        if P5_CLV_PREDICTIONS.exists():
            df = pd.read_csv(P5_CLV_PREDICTIONS)
            data_source = "p5_precomputed"
    except Exception:
        pass

    # Try running P5's pipeline
    if df is None:
        try:
            from src.data_cleaning import clean_retail_data
            from src.rfm_analysis import compute_rfm, score_rfm, label_segments
            from src.clustering import prepare_features, fit_and_profile, name_clusters

            clean_df = clean_retail_data(str(P5_ROOT / "data" / "raw" / "online_retail.csv"))
            rfm = compute_rfm(clean_df)
            rfm = score_rfm(rfm)
            rfm = label_segments(rfm)
            scaled, _ = prepare_features(rfm)
            rfm, _ = fit_and_profile(rfm, scaled, n_clusters=4)
            rfm, _ = name_clusters(rfm)
            df = rfm
            data_source = "p5_live"
        except Exception:
            pass

    # Fallback: sample data
    if df is None:
        df = _generate_sample_data()
        data_source = "sample"

    return df, data_source


def _generate_sample_data():
    """Generate sample segmentation data when P5 is unavailable."""
    import pandas as pd

    rng = random.Random(42)
    segments = [
        ("VIP Champions", 716, 12, 13.7, 8074.0),
        ("Loyal Regulars", 1173, 71, 4.1, 1803.0),
        ("New Potentials", 837, 18, 2.1, 552.0),
        ("Lost / Dormant", 1612, 182, 1.3, 343.0),
    ]

    rows = []
    cid = 12347
    for seg_name, count, avg_r, avg_f, avg_m in segments:
        for _ in range(count):
            recency = max(1, int(rng.gauss(avg_r, avg_r * 0.4)))
            frequency = max(1, int(rng.gauss(avg_f, avg_f * 0.3)))
            monetary = max(10, rng.gauss(avg_m, avg_m * 0.5))

            clv = monetary * frequency * 0.3 if seg_name != "Lost / Dormant" else rng.uniform(0, 500)
            clv_tier = (
                "Platinum" if clv > 5000 else
                "High" if clv > 1500 else
                "Medium" if clv > 500 else "Low"
            )

            rows.append({
                "CustomerID": cid,
                "Recency": recency,
                "Frequency": frequency,
                "Monetary": round(monetary, 2),
                "Cluster_Name": seg_name,
                "Cluster_Action": CAMPAIGN_TEMPLATES.get(
                    seg_name, DEFAULT_CAMPAIGN
                )["campaigns"][0],
                "CLV": round(clv, 2) if seg_name != "Lost / Dormant" or clv > 100 else None,
                "CLV_Tier": clv_tier if clv > 0 else None,
                "prob_alive": round(rng.uniform(0.8, 1.0), 3) if seg_name != "Lost / Dormant" else round(rng.uniform(0.1, 0.6), 3),
                "pred_purchases_90d": round(rng.uniform(0.5, 5.0), 2) if seg_name != "Lost / Dormant" else round(rng.uniform(0.0, 0.3), 2),
            })
            cid += 1

    return pd.DataFrame(rows)


def compute_segment_summary(df):
    """Compute per-segment summary statistics."""
    import pandas as pd
    import numpy as np

    summaries = []
    total_customers = len(df)
    total_revenue = df["Monetary"].sum()

    for seg_name, group in df.groupby("Cluster_Name"):
        count = len(group)
        revenue = group["Monetary"].sum()
        avg_clv = group["CLV"].dropna().mean() if "CLV" in group.columns else 0
        avg_recency = group["Recency"].mean()
        avg_frequency = group["Frequency"].mean()
        avg_monetary = group["Monetary"].mean()

        # Prob alive stats
        avg_prob_alive = group["prob_alive"].dropna().mean() if "prob_alive" in group.columns else None

        # CLV tier distribution
        clv_tiers = {}
        if "CLV_Tier" in group.columns:
            tier_counts = group["CLV_Tier"].dropna().value_counts().to_dict()
            clv_tiers = {str(k): int(v) for k, v in tier_counts.items()}

        # Predicted purchases
        avg_pred_purchases = group["pred_purchases_90d"].dropna().mean() if "pred_purchases_90d" in group.columns else None

        summaries.append({
            "segment_name": seg_name,
            "customer_count": count,
            "customer_pct": round(count / total_customers * 100, 1),
            "total_revenue": round(float(revenue), 2),
            "revenue_pct": round(float(revenue / total_revenue * 100), 1) if total_revenue > 0 else 0,
            "avg_recency_days": round(float(avg_recency), 1),
            "avg_frequency": round(float(avg_frequency), 1),
            "avg_monetary": round(float(avg_monetary), 2),
            "avg_clv": round(float(avg_clv), 2) if not pd.isna(avg_clv) else None,
            "avg_prob_alive": round(float(avg_prob_alive), 3) if avg_prob_alive is not None and not pd.isna(avg_prob_alive) else None,
            "avg_pred_purchases_90d": round(float(avg_pred_purchases), 2) if avg_pred_purchases is not None and not pd.isna(avg_pred_purchases) else None,
            "clv_tier_distribution": clv_tiers,
        })

    return sorted(summaries, key=lambda x: x["total_revenue"], reverse=True)


def detect_segment_shifts(current_summary, history):
    """Compare current segment sizes against previous scan to detect shifts."""
    shifts = []

    if not history["scans"]:
        return shifts

    previous = {
        s["segment_name"]: s
        for s in history["scans"][-1]["segment_summary"]
    }

    for seg in current_summary:
        name = seg["segment_name"]
        prev = previous.get(name)
        if not prev:
            shifts.append({
                "segment": name,
                "shift_type": "new_segment",
                "description": f"New segment detected: {name}",
                "severity": "notable",
            })
            continue

        # Customer count change
        count_delta = seg["customer_count"] - prev["customer_count"]
        count_pct = count_delta / prev["customer_count"] * 100 if prev["customer_count"] > 0 else 0

        if abs(count_pct) >= 5:
            direction = "grew" if count_delta > 0 else "shrank"
            sev = "urgent" if abs(count_pct) >= 15 else "notable"

            # Context-sensitive severity
            if name in ("Lost / Dormant", "Lost Causes") and count_delta > 0:
                sev = "urgent"  # Growing dormant is always bad
            elif name == "VIP Champions" and count_delta < 0:
                sev = "urgent"  # Losing VIPs is always bad

            shifts.append({
                "segment": name,
                "shift_type": "size_change",
                "description": (
                    f"{name} {direction}: {prev['customer_count']} → "
                    f"{seg['customer_count']} ({count_pct:+.1f}%)"
                ),
                "severity": sev,
                "previous_count": prev["customer_count"],
                "current_count": seg["customer_count"],
                "delta": count_delta,
                "delta_pct": round(count_pct, 1),
            })

        # Revenue shift
        rev_delta = seg["total_revenue"] - prev["total_revenue"]
        rev_pct = rev_delta / prev["total_revenue"] * 100 if prev["total_revenue"] > 0 else 0

        if abs(rev_pct) >= 10:
            direction = "increased" if rev_delta > 0 else "decreased"
            shifts.append({
                "segment": name,
                "shift_type": "revenue_change",
                "description": (
                    f"{name} revenue {direction}: "
                    f"£{prev['total_revenue']:,.0f} → £{seg['total_revenue']:,.0f} "
                    f"({rev_pct:+.1f}%)"
                ),
                "severity": "notable",
                "delta_pct": round(rev_pct, 1),
            })

        # CLV shift
        if seg.get("avg_clv") and prev.get("avg_clv") and prev["avg_clv"] > 0:
            clv_delta_pct = (seg["avg_clv"] - prev["avg_clv"]) / prev["avg_clv"] * 100
            if abs(clv_delta_pct) >= 10:
                direction = "rose" if clv_delta_pct > 0 else "fell"
                shifts.append({
                    "segment": name,
                    "shift_type": "clv_change",
                    "description": (
                        f"{name} avg CLV {direction}: "
                        f"£{prev['avg_clv']:,.0f} → £{seg['avg_clv']:,.0f} "
                        f"({clv_delta_pct:+.1f}%)"
                    ),
                    "severity": "notable",
                    "delta_pct": round(clv_delta_pct, 1),
                })

    return shifts


def generate_campaign_triggers(segment_summary):
    """Generate campaign recommendations for each segment."""
    triggers = []

    for seg in segment_summary:
        name = seg["segment_name"]
        template = CAMPAIGN_TEMPLATES.get(name, DEFAULT_CAMPAIGN)

        # Pick the most relevant campaigns based on segment stats
        campaigns = list(template["campaigns"])

        # Add urgency-based prioritization
        priority = "medium"
        if name in ("Lost / Dormant", "Lost Causes") and seg["customer_count"] > 1000:
            priority = "high"
            campaigns.insert(0, f"URGENT: {seg['customer_count']} dormant customers need win-back")
        elif name == "VIP Champions":
            priority = "high"
            campaigns.insert(0, f"Protect {seg['customer_count']} VIPs — ensure satisfaction & retention")
        elif name == "New Potentials" and seg.get("avg_pred_purchases_90d", 0) and seg["avg_pred_purchases_90d"] < 1:
            priority = "high"
            campaigns.insert(0, f"Convert {seg['customer_count']} new customers before they churn")

        # Churn risk indicator
        churn_risk = "low"
        if seg.get("avg_prob_alive") is not None:
            if seg["avg_prob_alive"] < 0.5:
                churn_risk = "high"
            elif seg["avg_prob_alive"] < 0.8:
                churn_risk = "medium"

        triggers.append({
            "segment": name,
            "campaign_type": template["campaign_type"],
            "priority": priority,
            "churn_risk": churn_risk,
            "customer_count": seg["customer_count"],
            "avg_clv": seg.get("avg_clv"),
            "recommended_campaigns": campaigns[:4],
            "channel_mix": template["channel_mix"],
            "urgency": template["urgency"],
        })

    return sorted(triggers, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])


def build_recommended_actions(segment_summary, shifts, triggers):
    """Build top-level action recommendations."""
    actions = []

    # Shift-based actions
    urgent_shifts = [s for s in shifts if s["severity"] == "urgent"]
    if urgent_shifts:
        for shift in urgent_shifts:
            actions.append({
                "priority": "high",
                "action": f"Investigate: {shift['description']}",
                "detail": "This segment shift requires immediate attention.",
            })

    # Segment-based actions
    for trigger in triggers:
        if trigger["priority"] == "high":
            actions.append({
                "priority": "high",
                "action": f"Launch {trigger['campaign_type']} for {trigger['segment']}",
                "detail": (
                    f"{trigger['customer_count']} customers | "
                    f"Churn risk: {trigger['churn_risk']} | "
                    f"Channels: {', '.join(trigger['channel_mix'])}"
                ),
            })

    # Revenue concentration warning
    if segment_summary:
        top_seg = segment_summary[0]
        if top_seg["revenue_pct"] > 50:
            actions.append({
                "priority": "medium",
                "action": f"Revenue concentration: {top_seg['segment_name']} = {top_seg['revenue_pct']}% of total",
                "detail": "Diversify revenue sources. Over-reliance on one segment is risky.",
            })

    # Dormant segment size warning
    for seg in segment_summary:
        if "dormant" in seg["segment_name"].lower() or "lost" in seg["segment_name"].lower():
            if seg["customer_pct"] > 30:
                actions.append({
                    "priority": "medium",
                    "action": f"{seg['segment_name']} is {seg['customer_pct']}% of customer base",
                    "detail": "Large dormant segment. Consider aggressive win-back or list hygiene.",
                })

    if not actions:
        actions.append({
            "priority": "low",
            "action": "Segments are stable — continue current campaigns",
            "detail": "No urgent shifts detected. Monitor next scan.",
        })

    return actions


def main():
    parser = argparse.ArgumentParser(
        description="Segment-Triggered Campaigns — OpenClaw Capability 6"
    )
    parser.add_argument(
        "--output", type=str, choices=["json", "text"], default="text",
    )
    args = parser.parse_args()

    # Load data
    df, data_source = load_segmentation_data()

    # Compute segment summary
    segment_summary = compute_segment_summary(df)

    # Load history and detect shifts
    history = load_history()
    shifts = detect_segment_shifts(segment_summary, history)

    # Generate campaign triggers
    triggers = generate_campaign_triggers(segment_summary)

    # Build actions
    actions = build_recommended_actions(segment_summary, shifts, triggers)

    # Overall severity
    if any(s["severity"] == "urgent" for s in shifts):
        overall_severity = "urgent"
    elif shifts:
        overall_severity = "notable"
    else:
        overall_severity = "stable"

    # Save to history
    entry = {
        "timestamp": datetime.now().isoformat(),
        "data_source": data_source,
        "segment_summary": segment_summary,
        "shift_count": len(shifts),
        "overall_severity": overall_severity,
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
        "overall_severity": overall_severity,
        "total_customers": int(df.shape[0]),
        "total_segments": len(segment_summary),
        "segment_summary": segment_summary,
        "segment_shifts": shifts,
        "shift_count": len(shifts),
        "campaign_triggers": triggers,
        "recommended_actions": actions,
        "scans_in_history": len(history["scans"]),
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, default=str))
    else:
        _print_text(output)


def _print_text(output):
    """Render segmentation results as formatted text."""
    sev_icons = {"stable": "=", "notable": "!", "urgent": "!!!"}
    sev = output["overall_severity"]

    print("=" * 60)
    print(f"SEGMENT-TRIGGERED CAMPAIGNS  [{sev_icons.get(sev, '?')}] {sev.upper()}")
    print(f"Source: {output['data_source']} | Customers: {output['total_customers']:,}")
    print("=" * 60)

    # Segment summary
    print(f"\n  Segments ({output['total_segments']}):")
    for seg in output["segment_summary"]:
        clv_str = f"CLV: £{seg['avg_clv']:,.0f}" if seg.get("avg_clv") else "CLV: N/A"
        alive_str = f"Alive: {seg['avg_prob_alive']:.0%}" if seg.get("avg_prob_alive") else ""
        print(f"\n    {seg['segment_name']:20s}  {seg['customer_count']:>5} customers ({seg['customer_pct']}%)")
        print(f"      Revenue: £{seg['total_revenue']:>12,.0f} ({seg['revenue_pct']}%)  |  {clv_str}")
        print(f"      R={seg['avg_recency_days']:.0f}d  F={seg['avg_frequency']:.1f}  M=£{seg['avg_monetary']:,.0f}  {alive_str}")

    # Shifts
    if output["segment_shifts"]:
        print(f"\n  Segment Shifts ({output['shift_count']}):")
        for shift in output["segment_shifts"]:
            icon = "!!!" if shift["severity"] == "urgent" else "!"
            print(f"    [{icon}] {shift['description']}")

    # Campaign triggers
    print(f"\n  Campaign Recommendations:")
    for trigger in output["campaign_triggers"]:
        pri = {"high": "!!!", "medium": "!!", "low": "!"}.get(trigger["priority"], " ")
        print(f"\n    [{pri}] {trigger['segment']} — {trigger['campaign_type']}")
        print(f"      Churn risk: {trigger['churn_risk']} | Channels: {', '.join(trigger['channel_mix'])}")
        for camp in trigger["recommended_campaigns"][:2]:
            print(f"      - {camp}")

    # Actions
    if output["recommended_actions"]:
        print(f"\n  Top Actions:")
        for act in output["recommended_actions"][:5]:
            pri = {"high": "!!!", "medium": "!!", "low": "!"}.get(act["priority"], " ")
            print(f"    [{pri}] {act['action']}")


if __name__ == "__main__":
    main()
