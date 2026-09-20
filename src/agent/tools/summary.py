"""
Graph Evidence Summarizer and Context-Size Controller.
Transforms raw graph queries containing hundreds or thousands of transactions into compact,
information-dense analytical evidence summaries suitable for LLM consumption.
Enforces Context-Size Control (Requirement #5).
"""

import math
import statistics
import datetime
from typing import Dict, List, Any, Optional
from collections import Counter


class EvidenceSummarizer:
    """
    Computes statistical and pattern summaries from graph query payloads
    so the agent reasoning engine never receives thousands of uncompressed records.
    """

    @staticmethod
    def summarize_card_history(
        txns: List[Dict[str, Any]],
        flagged_txn_id: str = "",
        flagged_region: str = "",
        sample_limit: int = 12
    ) -> Dict[str, Any]:
        """
        Summarizes a full card transaction history into compact analytical dimensions:
        - Volume and time span
        - Amount distribution (min, max, mean, median, stdev, sum)
        - Regional breakdown and familiarity with flagged region
        - Channel mix and risk distribution
        - Temporal cadence (e.g., weekend evening clustering)
        - High-signal representative transaction slice
        """
        if not txns:
            return {
                "total_transactions": 0,
                "time_range": {},
                "amount_stats": {},
                "regional_summary": {},
                "representative_sample": [],
                "anomalies": {}
            }

        total_txns = len(txns)
        amounts = [float(t.get("amount", 0.0) or 0.0) for t in txns]
        risk_scores = [float(t.get("risk_score", 0.0) or 0.0) for t in txns if t.get("risk_score") is not None]
        regions = [str(t.get("billing_region", "")) for t in txns if t.get("billing_region")]
        channels = [str(t.get("channel", "")) for t in txns if t.get("channel")]

        # 1. Amount Statistics
        mean_amt = round(statistics.mean(amounts), 2) if amounts else 0.0
        median_amt = round(statistics.median(amounts), 2) if amounts else 0.0
        stdev_amt = round(statistics.stdev(amounts), 2) if len(amounts) > 1 else 0.0
        min_amt = round(min(amounts), 2) if amounts else 0.0
        max_amt = round(max(amounts), 2) if amounts else 0.0
        sum_amt = round(sum(amounts), 2) if amounts else 0.0

        # 2. Time Range & Cadence
        sorted_txns = sorted(txns, key=lambda x: x.get("ts", ""))
        first_ts = sorted_txns[0].get("ts", "")
        last_ts = sorted_txns[-1].get("ts", "")

        span_days = 0.0
        weekend_count = 0
        night_count = 0
        try:
            dt_first = datetime.datetime.strptime(first_ts, "%Y-%m-%d %H:%M:%S")
            dt_last = datetime.datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
            span_days = max(1.0, round((dt_last - dt_first).total_seconds() / 86400.0, 1))

            for t in sorted_txns:
                dt = datetime.datetime.strptime(t["ts"], "%Y-%m-%d %H:%M:%S")
                if dt.weekday() in (5, 6):  # Saturday, Sunday
                    weekend_count += 1
                if dt.hour >= 20 or dt.hour < 5:  # Night / evening
                    night_count += 1
        except Exception:
            pass

        # 3. Regional Breakdown
        region_counts = Counter(regions)
        top_regions = [{"region_id": r, "count": cnt, "pct": round(cnt / total_txns * 100, 1)} for r, cnt in region_counts.most_common(5)]
        flagged_reg_count = region_counts.get(str(flagged_region), 0) if flagged_region else 0
        flagged_reg_familiarity = "routine" if flagged_reg_count >= 5 else ("occasional" if flagged_reg_count >= 1 else "novel_zero_history")

        # 4. Anomalies and High-Signal Indicators
        micro_auths = [t["txn_id"] for t in txns if float(t.get("amount", 0.0) or 0.0) < 5.00 and t.get("channel") == "online"]
        large_purchases = [t["txn_id"] for t in txns if float(t.get("amount", 0.0) or 0.0) >= 1000.00]

        # 5. Representative Sample Extraction (Capped)
        # Includes: 3 earliest, 3 latest, 3 largest, flagged txn, and matching region txns
        sample_dict: Dict[str, Dict[str, Any]] = {}

        # Flagged transaction
        for t in sorted_txns:
            if flagged_txn_id and t.get("txn_id") == flagged_txn_id:
                sample_dict[t["txn_id"]] = {**t, "sample_reason": "flagged_transaction"}

        # Earliest 3
        for t in sorted_txns[:3]:
            if t["txn_id"] not in sample_dict:
                sample_dict[t["txn_id"]] = {**t, "sample_reason": "historical_baseline_earliest"}

        # Latest 3
        for t in sorted_txns[-3:]:
            if t["txn_id"] not in sample_dict:
                sample_dict[t["txn_id"]] = {**t, "sample_reason": "most_recent_activity"}

        # Top 3 largest
        largest_txns = sorted(txns, key=lambda x: float(x.get("amount", 0.0) or 0.0), reverse=True)[:3]
        for t in largest_txns:
            if t["txn_id"] not in sample_dict:
                sample_dict[t["txn_id"]] = {**t, "sample_reason": "peak_amount_transaction"}

        # Flagged region sample (up to 3)
        if flagged_region:
            reg_txns = [t for t in sorted_txns if str(t.get("billing_region", "")) == str(flagged_region)]
            for t in reg_txns[:3]:
                if t["txn_id"] not in sample_dict:
                    sample_dict[t["txn_id"]] = {**t, "sample_reason": f"region_{flagged_region}_comparison"}

        # Truncate sample to limit
        representative_sample = list(sample_dict.values())[:sample_limit]

        return {
            "total_transactions": total_txns,
            "time_range": {
                "start_time": first_ts,
                "end_time": last_ts,
                "span_days": span_days,
                "txns_per_day": round(total_txns / span_days, 2)
            },
            "amount_stats": {
                "min_usd": min_amt,
                "max_usd": max_amt,
                "mean_usd": mean_amt,
                "median_usd": median_amt,
                "stdev_usd": stdev_amt,
                "total_volume_usd": sum_amt
            },
            "cadence": {
                "weekend_txns": weekend_count,
                "weekend_pct": round(weekend_count / total_txns * 100, 1) if total_txns else 0.0,
                "night_txns": night_count,
                "night_pct": round(night_count / total_txns * 100, 1) if total_txns else 0.0
            },
            "regional_summary": {
                "unique_regions_count": len(region_counts),
                "top_regions": top_regions,
                "flagged_region": flagged_region,
                "flagged_region_txns_count": flagged_reg_count,
                "flagged_region_familiarity": flagged_reg_familiarity
            },
            "channel_mix": dict(Counter(channels)),
            "risk_score_stats": {
                "mean_risk": round(statistics.mean(risk_scores), 3) if risk_scores else 0.0,
                "max_risk": round(max(risk_scores), 3) if risk_scores else 0.0
            },
            "anomalies": {
                "micro_authorization_count": len(micro_auths),
                "large_purchase_count": len(large_purchases),
                "micro_authorization_sample": micro_auths[:5],
                "large_purchase_sample": large_purchases[:5]
            },
            "representative_sample_count": len(representative_sample),
            "representative_sample": representative_sample
        }

    @staticmethod
    def summarize_customer_portfolio(cust_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarizes multi-card ownership and cross-card spend activity."""
        cards = cust_data.get("cards", [])
        total_txns = cust_data.get("total_transactions", 0)
        return {
            "customer_id": cust_data.get("customer_id", ""),
            "total_cards_owned": len(cards),
            "cards": [c.get("card_id") for c in cards],
            "total_cross_card_transactions": total_txns,
            "has_multiple_cards": len(cards) > 1
        }

    @staticmethod
    def summarize_device_network(dev_data: Dict[str, Any]) -> Dict[str, Any]:
        """Summarizes multi-card device clusters and syndicate risk."""
        cards = dev_data.get("connected_cards", [])
        custs = dev_data.get("connected_customers", [])
        total_txns = dev_data.get("total_txns", len(cards))
        return {
            "device_profile": dev_data.get("device_profile", ""),
            "connected_card_count": len(cards),
            "connected_customer_count": len(custs),
            "total_device_transactions": total_txns,
            "is_shared_device": len(cards) > 1,
            "syndicate_risk_tier": "CRITICAL" if len(cards) >= 10 else ("ELEVATED" if len(cards) >= 3 else "LOW"),
            "sample_connected_cards": cards[:10]
        }
