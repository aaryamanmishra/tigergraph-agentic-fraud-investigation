"""
Benchmark Coverage Audit Script for Live TigerGraph FraudNet.
Examines evidence coverage across all 20 benchmark cases in case_pack.csv.
Compares raw dataset ground truth with live graph queries.
"""

import os
import sys
import csv
import time
import json
from collections import defaultdict
from typing import Dict, List, Set, Any

sys.path.insert(0, os.path.abspath("."))
from src.config import config
from src.graph.adapter import GraphAdapter
from src.graph.loading.live_loader import LiveGraphLoader


def audit_coverage():
    print("=" * 80)
    print("STARTING BENCHMARK COVERAGE AUDIT ACROSS ALL 20 CASES ON LIVE FraudNet")
    print("=" * 80)

    adapter = GraphAdapter(backend="tigergraph")
    loader = LiveGraphLoader()

    # 1. Load ground truth from raw files
    with open("case_pack.csv", "r", encoding="utf-8") as f:
        cases = list(csv.DictReader(f))

    # Read raw transactions for benchmark customers/cards
    bench_custs = {c["customer_id"] for c in cases}
    bench_cards = {c["card_id"] for c in cases}
    bench_flagged = {c["flagged_txn_id"] for c in cases}

    print("Indexing raw transactions.csv...")
    raw_card_txns = defaultdict(list)
    raw_txn_map = {}
    with open("transactions.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tid = r["TransactionID"]
            cid = r["customer_id"]
            if cid in bench_custs or tid in bench_flagged:
                raw_txn_map[tid] = r
                # Associate with matching card in case pack if exists
                for c in cases:
                    if c["customer_id"] == cid:
                        raw_card_txns[c["card_id"]].append(r)
                        break

    # Read raw identity
    print("Indexing raw identity.csv...")
    raw_identity_map = {}
    with open("identity.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            raw_identity_map[r["TransactionID"]] = r

    # Read raw closed cases
    print("Indexing raw closed_cases_history.csv...")
    raw_closed_cases = defaultdict(list)
    raw_closed_all = {}
    with open("closed_cases_history.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            raw_closed_all[r["case_id"]] = r
            if r.get("card_id") in bench_cards or r.get("customer_id") in bench_custs:
                raw_closed_cases[r["card_id"]].append(r)

    print("\nStarting per-case live graph audit...")
    audit_results = []
    latencies = []

    for idx, c in enumerate(cases, 1):
        case_id = c["case_id"]
        flagged_txn = c["flagged_txn_id"]
        card_id = c["card_id"]
        cust_id = c["customer_id"]
        trigger_type = c["trigger_type"]
        trigger_text = c["trigger_text"]

        t_start = time.time()

        # A. Query transaction context
        t0 = time.time()
        ctx = adapter.get_transaction_context(flagged_txn)
        lat_ctx = round((time.time() - t0) * 1000, 1)

        flagged_found = len(ctx.get("results", [])) > 0
        returned_card = ctx.get("card_id", "")
        returned_cust = ctx.get("customer_id", "")
        returned_dev = ctx.get("device_profile_id", "")
        returned_reg = ctx.get("region_id", "")

        # B. Query card history
        t0 = time.time()
        hist = adapter.get_card_history(card_id)
        lat_hist = round((time.time() - t0) * 1000, 1)
        graph_txns = hist.get("results", [])
        graph_txn_count = len(graph_txns)
        raw_txn_count = len(raw_card_txns.get(card_id, []))

        # Check card history completeness
        card_history_complete = "PASS" if (graph_txn_count >= raw_txn_count and raw_txn_count > 0) else "FAIL"

        # C. Query closed cases
        t0 = time.time()
        cases_res = adapter.get_similar_closed_cases(card_id=card_id)
        lat_cases = round((time.time() - t0) * 1000, 1)
        graph_case_ids = {cs["case_id"] for cs in cases_res.get("results", [])}
        expected_case_ids = {cs["case_id"] for cs in raw_closed_cases.get(card_id, [])}
        closed_cases_complete = "PASS" if expected_case_ids.issubset(graph_case_ids) else "FAIL"

        # Check if historical transactions from closed cases exist in FraudNet
        missing_case_txns = []
        for cs_id in expected_case_ids:
            cs_row = raw_closed_all.get(cs_id, {})
            t_ids = [t.strip() for t in cs_row.get("txn_ids", "").split("|") if t.strip()]
            for t_ref in t_ids:
                # Test if transaction exists in graph by checking if context returns it
                c_test = adapter.get_transaction_context(t_ref)
                if not c_test.get("results"):
                    missing_case_txns.append(t_ref)

        # D. Query device network
        raw_id_row = raw_identity_map.get(flagged_txn)
        raw_dev_prof = ""
        if raw_id_row:
            raw_dev_prof = f"{raw_id_row.get('DeviceInfo','')} | {raw_id_row.get('id_30','')} | {raw_id_row.get('id_31','')} | {raw_id_row.get('id_33','')}"

        t0 = time.time()
        if raw_dev_prof:
            dev_res = adapter.get_device_neighbors(raw_dev_prof)
            conn_res = adapter.get_connected_cards(card_id)
            lat_dev = round((time.time() - t0) * 1000, 1)
            connected_cards_count = len(dev_res.get("connected_cards", []))
            device_complete = "PASS" if (returned_dev == raw_dev_prof and connected_cards_count > 0) else "PARTIAL"
        else:
            # In-person transaction
            lat_dev = 0.0
            device_complete = "PASS" if not returned_dev else "FAIL"
            connected_cards_count = 0

        # E. Query temporal chain
        t0 = time.time()
        chain_res = adapter.get_transaction_chain(flagged_txn, window_hours=48)
        lat_chain = round((time.time() - t0) * 1000, 1)
        chain_txns = chain_res.get("results", [])
        temporal_complete = "PASS" if len(chain_txns) > 0 or graph_txn_count <= 1 else "FAIL"

        total_case_lat = round((time.time() - t_start) * 1000, 1)
        latencies.append(total_case_lat)

        # Overall coverage
        checks = [flagged_found, card_history_complete == "PASS", closed_cases_complete == "PASS", device_complete == "PASS", temporal_complete == "PASS"]
        if all(checks):
            overall = "PASS"
        elif any(c == "FAIL" for c in [card_history_complete, closed_cases_complete]):
            overall = "FAIL"
        else:
            overall = "PARTIAL"

        audit_results.append({
            "case_id": case_id,
            "flagged_txn": flagged_txn,
            "card_id": card_id,
            "customer_id": cust_id,
            "raw_txns": raw_txn_count,
            "graph_txns": graph_txn_count,
            "card_history": card_history_complete,
            "device_network": device_complete,
            "raw_closed_cases": len(expected_case_ids),
            "graph_closed_cases": len(graph_case_ids),
            "closed_cases": closed_cases_complete,
            "missing_case_txns": len(missing_case_txns),
            "temporal_chain": temporal_complete,
            "overall": overall,
            "latency_ms": total_case_lat
        })

        print(f"[{case_id:7}] Txn={flagged_txn} | Card={card_id} | RawTxns={raw_txn_count} GraphTxns={graph_txn_count} ({card_history_complete}) | Dev={device_complete} | Closed={closed_cases_complete} | Temp={temporal_complete} | Overall={overall} ({total_case_lat}ms)")

    # Print Summary Table
    print("\n" + "=" * 100)
    print(f"{'Case':<9} | {'Flagged Txn':<12} | {'Card History':<14} | {'Device Net':<11} | {'Closed Cases':<13} | {'Temporal':<10} | {'Overall':<9} | {'Latency'}")
    print("-" * 100)
    for r in audit_results:
        print(f"{r['case_id']:<9} | {r['flagged_txn']:<12} | {r['card_history']:<14} | {r['device_network']:<11} | {r['closed_cases']:<13} | {r['temporal_chain']:<10} | {r['overall']:<9} | {r['latency_ms']}ms")
    print("=" * 100)

    avg_lat = round(sum(latencies) / len(latencies), 1)
    print(f"Average Total Investigation Query Latency per Case: {avg_lat}ms")

    with open("docs/audit_results_cache.json", "w") as f:
        json.dump({"cases": audit_results, "avg_latency": avg_lat}, f, indent=2)


if __name__ == "__main__":
    audit_coverage()
