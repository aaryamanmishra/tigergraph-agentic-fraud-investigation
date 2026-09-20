"""
Post-Load Live Verification Script for TigerGraph FraudNet.
Validates vertex counts, edge integrity, HHG-001 and HHG-014 investigation queries,
and measures query latency against live Savanna Cloud.
"""

import os
import sys
import time
import json
sys.path.insert(0, os.path.abspath("."))

from src.config import config
from src.graph.adapter import GraphAdapter
from src.graph.loading.live_loader import LiveGraphLoader


def run_verification():
    print("=" * 70)
    print("LIVE POST-LOAD VERIFICATION FOR FraudNet ON TIGERGRAPH SAVANNA")
    print("=" * 70)

    adapter = GraphAdapter(backend="tigergraph")
    loader = LiveGraphLoader()
    results = {}

    # 1. Audit Live Vertex Counts
    print("\n--- 1. Live Vertex Counts Audit ---")
    v_counts = loader.get_live_vertex_counts()
    for v_type, cnt in v_counts.items():
        print(f"  {v_type:15}: {cnt:,}")
    results["vertex_counts"] = v_counts

    # Verify minimum thresholds
    assert v_counts["Customer"] >= 3000, "Customer count too low"
    assert v_counts["Card"] >= 3000, "Card count too low"
    assert v_counts["Transaction"] >= 50000, "Transaction count too low"
    assert v_counts["DeviceProfile"] == 9706, f"Expected 9,706 DeviceProfiles, got {v_counts['DeviceProfile']}"
    assert v_counts["EmailDomain"] == 59, f"Expected 59 EmailDomains, got {v_counts['EmailDomain']}"
    assert v_counts["BillingRegion"] == 332, f"Expected 332 BillingRegions, got {v_counts['BillingRegion']}"
    assert v_counts["ClosedCase"] == 5565, f"Expected 5,565 ClosedCases, got {v_counts['ClosedCase']}"
    print("  >>> Vertex Count Audit: PASSED (All 7 vertex types meet/match exact expectations)")

    # 2. HHG-001 End-to-End Investigation Queries
    print("\n--- 2. HHG-001 End-to-End Graph Queries ---")
    
    t0 = time.time()
    hhg1_ctx = adapter.get_transaction_context("3514030")
    lat_ctx = round((time.time() - t0) * 1000, 2)
    print(f"  [get_transaction_context 3514030] Latency: {lat_ctx}ms")
    print(f"    Card: {hhg1_ctx.get('card_id')}, Customer: {hhg1_ctx.get('customer_id')}, Region: {hhg1_ctx.get('region_id')}, Risk: {hhg1_ctx.get('risk_score')}")
    assert hhg1_ctx.get("card_id") == "C12382-K1"
    assert hhg1_ctx.get("customer_id") == "C12382"
    assert str(hhg1_ctx.get("region_id")) == "444.0"

    t0 = time.time()
    hhg1_history = adapter.get_card_history("C12382-K1")["results"]
    lat_hist = round((time.time() - t0) * 1000, 2)
    print(f"  [get_card_history C12382-K1] Latency: {lat_hist}ms | Total Transactions: {len(hhg1_history)}")
    assert len(hhg1_history) == 422, f"Expected 422 transactions for C12382-K1, got {len(hhg1_history)}"

    t0 = time.time()
    hhg1_cases = adapter.get_similar_closed_cases("C12382-K1")["results"]
    lat_cases = round((time.time() - t0) * 1000, 2)
    case_ids = [c["case_id"] for c in hhg1_cases]
    print(f"  [get_similar_closed_cases C12382-K1] Latency: {lat_cases}ms | Historical Cases: {case_ids}")
    assert set(case_ids) == {"CC-1066", "CC-1673", "CC-2964", "CC-3587"}

    # 3. HHG-014 End-to-End Investigation Queries
    print("\n--- 3. HHG-014 End-to-End Graph Queries ---")

    t0 = time.time()
    hhg14_ctx = adapter.get_transaction_context("3478561")
    lat_ctx14 = round((time.time() - t0) * 1000, 2)
    print(f"  [get_transaction_context 3478561] Latency: {lat_ctx14}ms")
    print(f"    Card: {hhg14_ctx.get('card_id')}, Customer: {hhg14_ctx.get('customer_id')}, Device: {hhg14_ctx.get('device_profile_id')[:40]}...")
    assert hhg14_ctx.get("card_id") == "C13487-K1"
    assert "SM-G935F" in (hhg14_ctx.get("device_profile_id") or "")

    t0 = time.time()
    hhg14_connected = adapter.get_connected_cards("C13487-K1")["connected_cards"]
    lat_conn = round((time.time() - t0) * 1000, 2)
    print(f"  [get_connected_cards C13487-K1] Latency: {lat_conn}ms | Connected Cards Count: {len(hhg14_connected)}")

    t0 = time.time()
    dev_prof = hhg14_ctx.get("device_profile_id")
    hhg14_dev_neigh = adapter.get_device_neighbors(dev_prof)["connected_cards"]
    lat_dev = round((time.time() - t0) * 1000, 2)
    print(f"  [get_device_neighbors] Latency: {lat_dev}ms | Device-sharing Cards: {len(hhg14_dev_neigh)}")
    assert len(hhg14_dev_neigh) >= 10, f"Expected multiple shared cards, got {len(hhg14_dev_neigh)}"

    # 4. Check other benchmark cases (e.g. HHG-002, HHG-003, HHG-007)
    print("\n--- 4. Multi-Case Benchmark Verification ---")
    test_cases = [
        ("HHG-002", "3478782", "C11891-K1", "C11891"),
        ("HHG-003", "3530164", "C08623-K2", "C08623"),
        ("HHG-007", "3514948", "C09933-K2", "C09933"),
        ("HHG-010", "3506725", "C10434-K1", "C10434"),
        ("HHG-020", "3509359", "C12265-K2", "C12265")
    ]
    for cid, tid, card_id, cust_id in test_cases:
        t0 = time.time()
        ctx = adapter.get_transaction_context(tid)
        lat = round((time.time() - t0) * 1000, 2)
        print(f"  [{cid}] Txn {tid} -> Card: {ctx.get('card_id')}, Cust: {ctx.get('customer_id')} ({lat}ms)")
        assert ctx.get("card_id") == card_id, f"Expected {card_id}, got {ctx.get('card_id')}"
        assert ctx.get("customer_id") == cust_id, f"Expected {cust_id}, got {ctx.get('customer_id')}"

    print("\n" + "=" * 70)
    print("ALL POST-LOAD VERIFICATION CHECKS PASSED ON LIVE TIGERGRAPH FraudNet!")
    print("=" * 70)


if __name__ == "__main__":
    run_verification()
