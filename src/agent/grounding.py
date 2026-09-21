"""
Evidence Grounding and Entity Integrity Filter.
Prevents LLM hallucinations from contaminating case findings, affected transaction lists,
exposure calculations, or regulatory filing reports.
"""

from typing import List, Dict, Set, Any, Tuple, Optional
import logging

from evaluation.check_integrity import get_entity_registry, DatasetEntityRegistry

logger = logging.getLogger(__name__)


class GroundingValidator:
    """
    Validates that entities cited in reasoning and final answers strictly exist in the dataset
    and have been observed during the investigation.
    """

    def __init__(self, data_dir: str = "."):
        self.registry: DatasetEntityRegistry = get_entity_registry(data_dir)

    def filter_valid_txn_ids(self, candidate_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Splits transaction IDs into valid (exist in dataset) and rejected (hallucinated)."""
        valid = []
        rejected = []
        for tid in candidate_ids:
            clean = str(tid).strip()
            if self.registry.is_valid_txn_id(clean):
                valid.append(clean)
            else:
                rejected.append(clean)
        return valid, rejected

    def filter_valid_card_ids(self, candidate_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Splits card IDs into valid and rejected."""
        valid = []
        rejected = []
        for cid in candidate_ids:
            clean = str(cid).strip()
            if self.registry.is_valid_card_id(clean):
                valid.append(clean)
            else:
                rejected.append(clean)
        return valid, rejected

    def filter_valid_closed_case_ids(self, candidate_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Splits case IDs into valid historical closed cases and rejected."""
        valid = []
        rejected = []
        for sc in candidate_ids:
            clean = str(sc).strip()
            if clean in self.registry.closed_case_ids:
                valid.append(clean)
            else:
                rejected.append(clean)
        return valid, rejected

    def filter_valid_device_profiles(self, candidate_profiles: List[str]) -> Tuple[List[str], List[str]]:
        """Splits device profiles into valid and rejected."""
        valid = []
        rejected = []
        for dp in candidate_profiles:
            raw = str(dp)
            if self.registry.is_valid_device_profile(raw):
                valid.append(raw)
            elif self.registry.is_valid_device_profile(raw.strip()):
                valid.append(raw.strip())
            else:
                rejected.append(raw)
        return valid, rejected

    def compute_grounded_exposure(self, valid_txn_ids: List[str]) -> float:
        """
        Calculates exposure strictly from transaction amounts recorded in dataset.
        Zero if no affected transactions.
        """
        total = 0.0
        for tid in valid_txn_ids:
            amt = self.registry.get_txn_amount(tid)
            if amt is not None:
                total += abs(amt)
        return round(total, 2)

    def sanitize_evidence_items(self, evidence_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ensures all entity IDs in evidence items exist in the dataset.
        Removes hallucinated IDs.
        """
        sanitized = []
        for ev in evidence_list:
            raw_ids = ev.get("entity_ids", [])
            valid_ids = []
            for eid in raw_ids:
                s_eid = str(eid).strip()
                if (
                    self.registry.is_valid_txn_id(s_eid)
                    or self.registry.is_valid_customer_id(s_eid)
                    or self.registry.is_valid_card_id(s_eid)
                    or self.registry.is_valid_case_id(s_eid)
                    or self.registry.is_valid_device_profile(s_eid)
                ):
                    valid_ids.append(s_eid)
                else:
                    logger.warning(f"Rejecting hallucinated entity ID '{s_eid}' from evidence item.")
            
            clean_item = dict(ev)
            clean_item["entity_ids"] = valid_ids
            sanitized.append(clean_item)
        return sanitized


_GLOBAL_VALIDATOR: Optional[GroundingValidator] = None


def get_grounding_validator(data_dir: str = ".") -> GroundingValidator:
    global _GLOBAL_VALIDATOR
    if _GLOBAL_VALIDATOR is None:
        _GLOBAL_VALIDATOR = GroundingValidator(data_dir)
    return _GLOBAL_VALIDATOR
