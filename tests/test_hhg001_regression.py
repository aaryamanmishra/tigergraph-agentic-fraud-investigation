"""
Regression Test for Reference Case HHG-001.
Validates the complete reference investigation against schema, dataset integrity, and policy engine.
"""

import unittest
import json
import os

from evaluation.validate_schema import validate_case_answer
from evaluation.check_integrity import get_entity_registry, check_case_integrity
from src.policy.engine import PolicyEngine, InvestigationState
from src.policy.actions import Action, ApprovalRoute


class TestHHG001Regression(unittest.TestCase):

    def setUp(self):
        self.case_path = os.path.join("cases", "HHG-001.json")
        self.assertTrue(os.path.exists(self.case_path), "cases/HHG-001.json must exist")
        with open(self.case_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_hhg001_schema_conformance(self):
        """HHG-001 must satisfy all schema requirements and cross-field invariants."""
        res = validate_case_answer(self.data)
        self.assertTrue(res.is_valid, f"HHG-001 schema errors: {res.errors}")
        self.assertEqual(self.data["case"]["verdict"], "legitimate")
        self.assertEqual(self.data["case"]["exposure_usd"], 0.0)
        self.assertEqual(self.data["case"]["affected_txn_ids"], [])
        self.assertFalse(self.data["sar"]["file"])

    def test_hhg001_dataset_integrity(self):
        """Every transaction, customer, card, and closed case ID in HHG-001 must exist in raw data."""
        registry = get_entity_registry(".")
        errors = check_case_integrity(self.data, registry)
        self.assertEqual(len(errors), 0, f"HHG-001 entity integrity errors: {errors}")

    def test_hhg001_policy_initial_phase(self):
        """Initial evaluation of HHG-001 must trigger Rule R1 and mandate VERIFY_WITH_CUSTOMER."""
        initial_state = InvestigationState(
            case_id="HHG-001",
            flagged_txn_id="3514030",
            card_id="C12382-K1",
            customer_id="C12382",
            fraud_probability=0.20,
            verdict="uncertain",
            is_single_signal=True,
            stage="initial"
        )
        res = PolicyEngine.evaluate(initial_state)
        self.assertIn("R1", res.policy_rules_triggered)
        self.assertTrue(res.requires_more_evidence)
        actions = [a["action"] for a in res.recommended_actions]
        self.assertIn(Action.VERIFY_WITH_CUSTOMER.value, actions)
        self.assertNotIn(Action.BLOCK_CARD.value, actions)

    def test_hhg001_policy_final_phase(self):
        """Final evaluation of HHG-001 after customer confirmation must trigger Rule R3 and CLOSE_NO_FRAUD."""
        final_state = InvestigationState(
            case_id="HHG-001",
            flagged_txn_id="3514030",
            card_id="C12382-K1",
            customer_id="C12382",
            fraud_probability=0.05,
            verdict="legitimate",
            customer_reply="confirmed",
            stage="final"
        )
        res = PolicyEngine.evaluate(final_state)
        self.assertIn("R3", res.policy_rules_triggered)
        self.assertFalse(res.requires_more_evidence)
        actions = [a["action"] for a in res.recommended_actions]
        self.assertEqual(actions, [Action.CLOSE_NO_FRAUD.value])
        self.assertFalse(res.sar_required)
        self.assertFalse(res.case_required)


if __name__ == "__main__":
    unittest.main()
