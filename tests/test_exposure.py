"""
Unit Tests for Deterministic Exposure Calculation.
Fraud Policy Section 4.
"""

import unittest
from src.policy.exposure import (
    calculate_exposure,
    calculate_transaction_exposure,
    exceeds_escalation_threshold,
    exceeds_sar_threshold,
    exceeds_manager_approval_threshold
)


class TestExposureCalculation(unittest.TestCase):

    def test_zero_exposure(self):
        """Empty lists must produce 0.0 exposure."""
        self.assertEqual(calculate_exposure([]), 0.0)
        self.assertEqual(calculate_transaction_exposure([], {}), 0.0)

    def test_single_transaction_exposure(self):
        """Single transaction exposure matches rounded amount."""
        amt_map = {"T1001": 292.36}
        self.assertEqual(calculate_exposure([292.36]), 292.36)
        self.assertEqual(calculate_transaction_exposure(["T1001"], amt_map), 292.36)

    def test_multiple_transactions_exposure(self):
        """Multiple transactions sum correctly."""
        amt_map = {
            "T1001": 1.10,
            "T1002": 2.40,
            "T1003": 0.95,
            "T1004": 259.98
        }
        txns = ["T1001", "T1002", "T1003", "T1004"]
        expected = round(1.10 + 2.40 + 0.95 + 259.98, 2)
        self.assertEqual(calculate_exposure(list(amt_map.values())), expected)
        self.assertEqual(calculate_transaction_exposure(txns, amt_map), expected)

    def test_deduplication_of_transaction_ids(self):
        """Duplicate transaction IDs in affected list must be counted only once."""
        amt_map = {"T1001": 100.00, "T1002": 50.00}
        txns_with_dups = ["T1001", "T1002", "T1001", "T1002", "T1001"]
        self.assertEqual(calculate_transaction_exposure(txns_with_dups, amt_map), 150.00)

    def test_absolute_value_handling(self):
        """Negative amounts (e.g. adjustments/credits) are summed by absolute value per Section 4."""
        self.assertEqual(calculate_exposure([-75.50, 24.50]), 100.00)

    def test_missing_transaction_id_raises_value_error(self):
        """If an affected txn ID is missing from amount map, raise ValueError."""
        amt_map = {"T1001": 100.0}
        with self.assertRaises(ValueError):
            calculate_transaction_exposure(["T1001", "T_MISSING"], amt_map)

    def test_threshold_predicates(self):
        """Test $500, $1,000, and $2,500 boundary conditions."""
        # $500 threshold
        self.assertFalse(exceeds_escalation_threshold(500.00))
        self.assertTrue(exceeds_escalation_threshold(500.01))

        # $1,000 threshold
        self.assertFalse(exceeds_sar_threshold(1000.00))
        self.assertTrue(exceeds_sar_threshold(1000.01))

        # $2,500 threshold
        self.assertFalse(exceeds_manager_approval_threshold(2500.00))
        self.assertTrue(exceeds_manager_approval_threshold(2500.01))


if __name__ == "__main__":
    unittest.main()
