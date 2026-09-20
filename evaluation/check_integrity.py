"""
Dataset Entity ID Integrity Validator.
Verifies that every referenced ID in an answer file exists in the real dataset files.
"""

import csv
import json
import os
from typing import Dict, List, Set, Any, Optional


class DatasetEntityRegistry:
    """In-memory cache of valid entity IDs loaded from raw dataset files."""

    def __init__(self, data_dir: str = "."):
        self.data_dir = data_dir
        self.case_pack_ids: Set[str] = set()
        self.closed_case_ids: Set[str] = set()
        self.customer_ids: Set[str] = set()
        self.card_ids: Set[str] = set()
        self.txn_ids: Set[str] = set()
        self.txn_amounts: Dict[str, float] = {}
        self.device_profiles: Set[str] = set()
        self._loaded = False

    def load(self):
        if self._loaded:
            return

        # 1. case_pack.csv
        case_pack_path = os.path.join(self.data_dir, "case_pack.csv")
        if os.path.exists(case_pack_path):
            with open(case_pack_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    self.case_pack_ids.add(r["case_id"])
                    self.customer_ids.add(r["customer_id"])
                    self.card_ids.add(r["card_id"])
                    self.txn_ids.add(r["flagged_txn_id"])

        # 2. closed_cases_history.csv
        closed_path = os.path.join(self.data_dir, "closed_cases_history.csv")
        if os.path.exists(closed_path):
            with open(closed_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    self.closed_case_ids.add(r["case_id"])
                    self.customer_ids.add(r["customer_id"])
                    self.card_ids.add(r["card_id"])
                    if r.get("connected_card_ids"):
                        for cc in r["connected_card_ids"].split("|"):
                            if cc.strip():
                                self.card_ids.add(cc.strip())
                    if r.get("first_fraud_txn_id"):
                        self.txn_ids.add(r["first_fraud_txn_id"])
                    if r.get("txn_ids"):
                        for tid in r["txn_ids"].split("|"):
                            if tid.strip():
                                self.txn_ids.add(tid.strip())

        # 3. identity.csv
        identity_path = os.path.join(self.data_dir, "identity.csv")
        if os.path.exists(identity_path):
            with open(identity_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    self.txn_ids.add(r["TransactionID"])
                    prof = f"{r['DeviceInfo']} | {r['id_30']} | {r['id_31']} | {r['id_33']}"
                    self.device_profiles.add(prof)

        # 4. transactions.csv
        txns_path = os.path.join(self.data_dir, "transactions.csv")
        if os.path.exists(txns_path):
            with open(txns_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    tid = r["TransactionID"]
                    self.txn_ids.add(tid)
                    self.customer_ids.add(r["customer_id"])
                    amt = float(r["TransactionAmt"]) if r.get("TransactionAmt") else 0.0
                    self.txn_amounts[tid] = amt

        self._loaded = True

    def is_valid_txn_id(self, txn_id: str) -> bool:
        return txn_id in self.txn_ids

    def is_valid_customer_id(self, customer_id: str) -> bool:
        return customer_id in self.customer_ids

    def is_valid_card_id(self, card_id: str) -> bool:
        return card_id in self.card_ids

    def is_valid_case_id(self, case_id: str) -> bool:
        return case_id in self.case_pack_ids or case_id in self.closed_case_ids

    def is_valid_device_profile(self, profile: str) -> bool:
        return profile in self.device_profiles

    def get_txn_amount(self, txn_id: str) -> Optional[float]:
        return self.txn_amounts.get(txn_id)


_GLOBAL_REGISTRY: Optional[DatasetEntityRegistry] = None


def get_entity_registry(data_dir: str = ".") -> DatasetEntityRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = DatasetEntityRegistry(data_dir)
        _GLOBAL_REGISTRY.load()
    return _GLOBAL_REGISTRY


def check_case_integrity(data: Dict[str, Any], registry: Optional[DatasetEntityRegistry] = None) -> List[str]:
    """
    Checks that every entity ID cited in data exists in the dataset.
    Returns list of error messages (empty if completely valid).
    """
    if registry is None:
        registry = get_entity_registry()

    errors: List[str] = []

    # 1. Check case_id
    case_id = data.get("case_id", "")
    if not registry.is_valid_case_id(case_id):
        errors.append(f"case_id '{case_id}' does not exist in case_pack.csv")

    case_obj = data.get("case", {})

    # 2. Check affected transactions
    affected_txns = case_obj.get("affected_txn_ids", [])
    calc_exposure = 0.0
    for tid in affected_txns:
        if not registry.is_valid_txn_id(tid):
            errors.append(f"affected_txn_id '{tid}' does not exist in transactions.csv")
        else:
            amt = registry.get_txn_amount(tid)
            if amt is not None:
                calc_exposure += abs(amt)

    # Exposure check
    reported_exp = case_obj.get("exposure_usd", 0.0)
    if affected_txns and abs(reported_exp - round(calc_exposure, 2)) > 0.05:
        errors.append(
            f"Reported exposure ${reported_exp:,.2f} does not match sum of affected transactions (${calc_exposure:,.2f})"
        )

    # 3. Check first_suspicious_txn_id
    first_tx = case_obj.get("first_suspicious_txn_id", "")
    if first_tx and not registry.is_valid_txn_id(first_tx):
        errors.append(f"first_suspicious_txn_id '{first_tx}' does not exist in transactions.csv")

    # 4. Check connected cards
    for cid in case_obj.get("connected_card_ids", []):
        if not registry.is_valid_card_id(cid):
            errors.append(f"connected_card_id '{cid}' not recognized in dataset")

    # 5. Check connected device profiles
    for dp in case_obj.get("connected_device_profiles", []):
        if not registry.is_valid_device_profile(dp):
            errors.append(f"connected_device_profile '{dp}' not found in identity.csv")

    # 6. Check similar prior cases
    for sc in case_obj.get("similar_prior_cases", []):
        if sc not in registry.closed_case_ids:
            errors.append(f"similar_prior_case '{sc}' does not exist in closed_cases_history.csv")

    # 7. Check evidence entity IDs
    for ev in case_obj.get("evidence", []):
        for eid in ev.get("entity_ids", []):
            is_valid = (
                registry.is_valid_txn_id(eid)
                or registry.is_valid_customer_id(eid)
                or registry.is_valid_card_id(eid)
                or registry.is_valid_case_id(eid)
            )
            if not is_valid:
                errors.append(f"evidence entity_id '{eid}' does not exist in dataset")

    # 8. Check SAR subjects
    sar_obj = data.get("sar", {})
    if sar_obj.get("file") is True:
        for subj in sar_obj.get("subjects", []):
            is_valid = (
                registry.is_valid_txn_id(subj)
                or registry.is_valid_customer_id(subj)
                or registry.is_valid_card_id(subj)
                or registry.is_valid_device_profile(subj)
            )
            if not is_valid:
                errors.append(f"sar subject '{subj}' does not exist in dataset")

    return errors
