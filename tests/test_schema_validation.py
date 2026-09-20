"""
Unit Tests for JSON Schema and Cross-Field Invariant Validation.
"""

import unittest
import copy
from evaluation.validate_schema import validate_case_answer


class TestSchemaValidation(unittest.TestCase):

    def setUp(self):
        # Canonical valid test answer dictionary
        self.valid_answer = {
            "case_id": "HHG-001",
            "case": {
                "status": "closed_legitimate",
                "verdict": "legitimate",
                "fraud_probability": 0.05,
                "pattern": "none",
                "pattern_description": "",
                "affected_txn_ids": [],
                "first_suspicious_txn_id": "",
                "connected_card_ids": [],
                "connected_device_profiles": [],
                "exposure_usd": 0.0,
                "evidence": [
                    {
                        "claim": "Routine recurring spend verified",
                        "source": "graph",
                        "ref": "query:card_history",
                        "entity_ids": ["3514030"]
                    }
                ],
                "similar_prior_cases": ["CC-1066"],
                "summary": "Investigation revealed routine legitimate spend.",
                "written_to_graph": True,
                "graph_case_id": "CASE-2016-1205-001"
            },
            "evidence_requests": [
                {
                    "type": "customer_validation",
                    "asked_after_step": 4,
                    "assumed_response": "Customer confirmed transaction."
                }
            ],
            "next_best_actions": {
                "initial": [
                    {
                        "action": "VERIFY_WITH_CUSTOMER",
                        "route": "auto",
                        "reason": "R1: Single signal with prob < 0.70"
                    }
                ],
                "final": [
                    {
                        "action": "CLOSE_NO_FRAUD",
                        "route": "auto",
                        "reason": "R3: Customer confirmed transaction"
                    }
                ],
                "what_changed": "Verification confirmed spend."
            },
            "sar": {
                "file": False,
                "reason": "No fraud identified",
                "narrative": "",
                "subjects": [],
                "total_amount_usd": 0.0,
                "activity_dates": []
            },
            "stop_reason": "Customer confirmed legitimate spend.",
            "tool_calls": 4,
            "tokens": 4500,
            "latency_s": 7.2
        }

    def test_valid_answer_passes(self):
        res = validate_case_answer(self.valid_answer)
        self.assertTrue(res.is_valid, f"Expected valid, got errors: {res.errors}")
        self.assertEqual(len(res.errors), 0)

    def test_missing_top_level_field(self):
        data = copy.deepcopy(self.valid_answer)
        del data["stop_reason"]
        res = validate_case_answer(data)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("stop_reason" in e for e in res.errors))

    def test_invalid_case_id_format(self):
        data = copy.deepcopy(self.valid_answer)
        data["case_id"] = "INVALID-123"
        res = validate_case_answer(data)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("case_id" in e for e in res.errors))

    def test_invalid_action_name(self):
        data = copy.deepcopy(self.valid_answer)
        data["next_best_actions"]["final"][0]["action"] = "FREEZE_ACCOUNT"
        res = validate_case_answer(data)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("invalid action" in e for e in res.errors))

    def test_invalid_approval_route(self):
        data = copy.deepcopy(self.valid_answer)
        data["next_best_actions"]["final"][0]["route"] = "L3"
        res = validate_case_answer(data)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("invalid route" in e for e in res.errors))

    def test_legitimate_verdict_invariant_violations(self):
        # Case A: Legitimate verdict with non-empty affected_txn_ids
        data = copy.deepcopy(self.valid_answer)
        data["case"]["affected_txn_ids"] = ["3514030"]
        res = validate_case_answer(data)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("affected_txn_ids must be empty for legitimate" in e for e in res.errors))

        # Case B: Legitimate verdict with non-zero exposure
        data = copy.deepcopy(self.valid_answer)
        data["case"]["exposure_usd"] = 77.07
        res = validate_case_answer(data)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("exposure_usd must be 0.0 for legitimate" in e for e in res.errors))

    def test_sar_cross_field_invariants(self):
        # If SAR is true, FILE_REPORT must be in final actions, narrative non-empty, dates present
        data = copy.deepcopy(self.valid_answer)
        data["case"]["verdict"] = "fraud"
        data["case"]["status"] = "closed_fraud"
        data["case"]["pattern"] = "card_not_present_fraud"
        data["case"]["affected_txn_ids"] = ["3478782"]
        data["case"]["exposure_usd"] = 1200.00
        data["sar"]["file"] = True
        data["sar"]["reason"] = "R2: Exposure > $1,000"
        data["sar"]["narrative"] = "Subject carried out unauthorized purchases. Multiple charges observed. Bank blocked card."
        data["sar"]["subjects"] = ["C11891", "C11891-K1"]
        data["sar"]["total_amount_usd"] = 1200.00
        data["sar"]["activity_dates"] = ["2016-11-22", "2016-11-22"]
        
        # Missing FILE_REPORT in final actions
        data["next_best_actions"]["final"] = [
            {"action": "BLOCK_CARD", "route": "L1", "reason": "R2"}
        ]
        res = validate_case_answer(data)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("FILE_REPORT" in e for e in res.errors))

        # Add FILE_REPORT with L2 route -> passes
        data["next_best_actions"]["final"].append(
            {"action": "FILE_REPORT", "route": "L2", "reason": "R2: Regulatory threshold exceeded"}
        )
        res_valid = validate_case_answer(data)
        self.assertTrue(res_valid.is_valid, f"Expected valid SAR, got: {res_valid.errors}")

    def test_graph_persistence_consistency(self):
        data = copy.deepcopy(self.valid_answer)
        data["case"]["written_to_graph"] = True
        data["case"]["graph_case_id"] = ""
        res = validate_case_answer(data)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("graph_case_id cannot be empty" in e for e in res.errors))


if __name__ == "__main__":
    unittest.main()
