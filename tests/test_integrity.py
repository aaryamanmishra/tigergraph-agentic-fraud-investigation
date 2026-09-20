"""
Unit Tests for Entity ID Dataset Integrity.
"""

import unittest
from evaluation.check_integrity import DatasetEntityRegistry, check_case_integrity


class TestEntityIntegrity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create a lightweight mock registry for unit tests
        cls.registry = DatasetEntityRegistry()
        cls.registry.case_pack_ids = {"HHG-001", "HHG-002"}
        cls.registry.closed_case_ids = {"CC-1066", "CC-2964"}
        cls.registry.customer_ids = {"C12382", "C11891"}
        cls.registry.card_ids = {"C12382-K1", "C11891-K1"}
        cls.registry.txn_ids = {"3514030", "3478782"}
        cls.registry.txn_amounts = {"3514030": 77.07, "3478782": 292.36}
        cls.registry.device_profiles = {"SAMSUNG SM-G892A Build/NRD90M | Android 7.0 | samsung browser 6.2 | 2220x1080"}
        cls.registry._loaded = True

    def test_valid_ids_pass(self):
        valid_data = {
            "case_id": "HHG-001",
            "case": {
                "affected_txn_ids": [],
                "first_suspicious_txn_id": "",
                "connected_card_ids": [],
                "connected_device_profiles": [],
                "exposure_usd": 0.0,
                "similar_prior_cases": ["CC-1066"],
                "evidence": [
                    {"claim": "Evidence", "source": "graph", "ref": "query", "entity_ids": ["3514030", "C12382"]}
                ]
            },
            "sar": {"file": False}
        }
        errors = check_case_integrity(valid_data, self.registry)
        self.assertEqual(len(errors), 0, f"Expected no errors, got: {errors}")

    def test_hallucinated_case_id(self):
        data = {
            "case_id": "HHG-999",
            "case": {"affected_txn_ids": [], "exposure_usd": 0.0, "similar_prior_cases": []},
            "sar": {"file": False}
        }
        errors = check_case_integrity(data, self.registry)
        self.assertTrue(any("HHG-999" in e for e in errors))

    def test_hallucinated_transaction_id(self):
        data = {
            "case_id": "HHG-001",
            "case": {
                "affected_txn_ids": ["T9999999"],
                "first_suspicious_txn_id": "T9999999",
                "connected_card_ids": [],
                "connected_device_profiles": [],
                "exposure_usd": 100.0,
                "similar_prior_cases": []
            },
            "sar": {"file": False}
        }
        errors = check_case_integrity(data, self.registry)
        self.assertTrue(any("T9999999" in e for e in errors))

    def test_exposure_mismatch(self):
        data = {
            "case_id": "HHG-002",
            "case": {
                "affected_txn_ids": ["3478782"],
                "first_suspicious_txn_id": "3478782",
                "connected_card_ids": [],
                "connected_device_profiles": [],
                "exposure_usd": 500.00,  # Real amount is 292.36
                "similar_prior_cases": []
            },
            "sar": {"file": False}
        }
        errors = check_case_integrity(data, self.registry)
        self.assertTrue(any("does not match sum of affected transactions" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
