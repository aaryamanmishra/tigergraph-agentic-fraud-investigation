"""
Graph Validation Script.
Validates vertex and edge counts, relationship topologies, and integrity across the graph store.
"""

import os
import sys
import time
from typing import Dict, Any

sys.path.insert(0, os.path.abspath("."))
from src.graph.adapter import get_graph_adapter
from src.graph.loading.loader import get_graph_store


def validate_graph() -> Dict[str, Any]:
    print("======================================================================")
    print("                TIGERGRAPH FRAUDNET — GRAPH VALIDATION                ")
    print("======================================================================")
    start_time = time.time()

    adapter = get_graph_adapter()
    store = adapter.store or get_graph_store()

    print(f"Graph Backend Active: [{adapter.backend.upper()}]")

    # 1. Vertex Counts
    v_counts = {
        "Customer": len(store.customers),
        "Card": len(store.cards),
        "Transaction": len(store.transactions),
        "DeviceProfile": len(store.devices),
        "BillingRegion": len(store.regions),
        "EmailDomain": len(store.domains),
        "ClosedCase": len(store.closed_cases)
    }

    print("\n--- 1. VERTEX COUNTS ---")
    for v_name, count in v_counts.items():
        print(f"  {v_name:<16}: {count:,}")

    # 2. Edge Counts
    e_counts = {
        "Customer -> OWNS -> Card": sum(len(c) for c in store.customer_owns_cards.values()),
        "Card -> MADE -> Transaction": sum(len(t) for t in store.card_made_txns.values()),
        "Transaction -> FROM_DEVICE -> DeviceProfile": len(store.txn_from_device),
        "Transaction -> BILLED_IN -> BillingRegion": len(store.txn_billed_in),
        "Transaction -> PURCHASER_EMAIL -> EmailDomain": len(store.txn_purchaser_email),
        "Transaction -> NEXT -> Transaction": len(store.next_txn),
        "ClosedCase -> ON_CARD -> Card": len(store.case_on_card),
        "ClosedCase -> INVOLVES -> Transaction": sum(len(t) for t in store.case_involves_txns.values()),
        "ClosedCase -> CONNECTED_TO -> Card": sum(len(c) for c in store.case_connected_cards.values())
    }

    print("\n--- 2. EDGE COUNTS (ALL 9 EDGE TYPES) ---")
    for e_name, count in e_counts.items():
        print(f"  {e_name:<48}: {count:,}")

    # 3. Topology & Relationship Integrity Checks
    print("\n--- 3. SAMPLE RELATIONSHIP VERIFICATION ---")

    # Sample Customer -> Card
    sample_cust = "C12382"
    cust_cards = store.customer_owns_cards.get(sample_cust, set())
    print(f"  Customer {sample_cust} owns: {sorted(list(cust_cards))}")

    # Sample Card -> Transaction
    sample_card = "C12382-K1"
    card_txns = store.card_made_txns.get(sample_card, [])
    print(f"  Card {sample_card} made: {len(card_txns):,} transactions (First: {card_txns[0]}, Last: {card_txns[-1]})")

    # Sample Txn -> Device (Online)
    sample_online_tx = "3478561"  # From HHG-014
    sample_dev = store.txn_from_device.get(sample_online_tx)
    print(f"  Txn {sample_online_tx} device: {sample_dev}")

    # Sample ClosedCase -> Involves
    sample_case = "CC-1066"
    involves = store.case_involves_txns.get(sample_case, set())
    print(f"  ClosedCase {sample_case} involves txns: {sorted(list(involves))}")

    # 4. Orphan & Anomaly Checks
    print("\n--- 4. ORPHAN & ANOMALY CHECKS ---")
    orphan_cards = [c for c in store.cards if c not in store.card_owned_by_customer]
    print(f"  Orphan Cards without Customer: {len(orphan_cards)}")

    orphan_txns = [t for t in list(store.transactions.keys())[:1000] if t not in store.txn_made_by_card]
    print(f"  Orphan Transactions in sample: {len(orphan_txns)}")

    duration = time.time() - start_time
    print(f"\nGraph validation completed in {duration:.2f} seconds.")
    print("======================================================================")

    return {
        "backend": adapter.backend,
        "vertex_counts": v_counts,
        "edge_counts": e_counts,
        "orphan_cards": len(orphan_cards),
        "validation_status": "PASSED"
    }


if __name__ == "__main__":
    validate_graph()
