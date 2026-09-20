"""
Deterministic Exposure Calculation Engine.
Fraud Policy Section 4.
"""

from typing import Dict, List, Set, Sequence, Union


def calculate_exposure(amounts: Sequence[Union[float, int]]) -> float:
    """
    Calculates the exposure in USD as the sum of the absolute amounts of every transaction
    identified as part of the fraud episode. Rounded to 2 decimal places.
    """
    if not amounts:
        return 0.0
    total = sum(abs(float(a)) for a in amounts)
    return round(total, 2)


def calculate_transaction_exposure(
    affected_txn_ids: Sequence[str],
    txn_amount_map: Dict[str, float]
) -> float:
    """
    Calculates exposure from a list of affected transaction IDs and a mapping of ID to amount.
    Duplicate transaction IDs in affected_txn_ids are deduplicated.
    
    Raises:
        ValueError: If any affected_txn_id is not present in txn_amount_map.
    """
    if not affected_txn_ids:
        return 0.0

    seen: Set[str] = set()
    total = 0.0

    for tid in affected_txn_ids:
        if tid in seen:
            continue
        seen.add(tid)

        if tid not in txn_amount_map:
            raise ValueError(f"Transaction ID {tid} not found in transaction amount mapping.")

        amt = txn_amount_map[tid]
        total += abs(float(amt))

    return round(total, 2)


def exceeds_escalation_threshold(exposure_usd: float) -> bool:
    """Policy R4 & R8: Checks if exposure exceeds $500.00"""
    return exposure_usd > 500.00


def exceeds_sar_threshold(exposure_usd: float) -> bool:
    """Policy R2 & Section 3a: Checks if exposure exceeds $1,000.00"""
    return exposure_usd > 1000.00


def exceeds_manager_approval_threshold(exposure_usd: float) -> bool:
    """Policy Section 2: Checks if exposure exceeds $2,500.00 requiring L2 Manager approval for BLOCK_CARD"""
    return exposure_usd > 2500.00
