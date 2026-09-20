"""
Unit Tests for Statutory Approval Routing & Threshold Boundaries.
Fraud Policy Section 2.
"""

import unittest
from src.policy.actions import (
    Action,
    ApprovalRoute,
    get_statutory_approval_route,
    validate_action_route
)


class TestApprovalRouting(unittest.TestCase):

    def test_auto_actions(self):
        """Verify all 10 actions designated as auto."""
        auto_actions = [
            Action.ALLOW_TRANSACTION,
            Action.MONITOR_CARD,
            Action.MONITOR_CONNECTED_CARDS,
            Action.WARN_CUSTOMER,
            Action.VERIFY_WITH_CUSTOMER,
            Action.STEP_UP_AUTH,
            Action.GENERATE_REPORT,
            Action.CREATE_CASE,
            Action.ESCALATE_TO_ANALYST,
            Action.CLOSE_NO_FRAUD
        ]
        for act in auto_actions:
            route = get_statutory_approval_route(act, exposure_usd=5000.0)
            self.assertEqual(route, ApprovalRoute.AUTO, f"{act} should have route auto")
            self.assertTrue(validate_action_route(act, ApprovalRoute.AUTO, exposure_usd=5000.0))
            self.assertFalse(validate_action_route(act, ApprovalRoute.L1, exposure_usd=5000.0))
            self.assertFalse(validate_action_route(act, ApprovalRoute.L2, exposure_usd=5000.0))

    def test_decline_transaction_route(self):
        """DECLINE_TRANSACTION must always require L1 approval."""
        route = get_statutory_approval_route(Action.DECLINE_TRANSACTION, exposure_usd=100.0)
        self.assertEqual(route, ApprovalRoute.L1)
        self.assertTrue(validate_action_route(Action.DECLINE_TRANSACTION, ApprovalRoute.L1))
        self.assertFalse(validate_action_route(Action.DECLINE_TRANSACTION, ApprovalRoute.AUTO))
        self.assertFalse(validate_action_route(Action.DECLINE_TRANSACTION, ApprovalRoute.L2))

    def test_block_all_cards_route(self):
        """BLOCK_ALL_CARDS must always require L2 approval."""
        route = get_statutory_approval_route(Action.BLOCK_ALL_CARDS, exposure_usd=10.0)
        self.assertEqual(route, ApprovalRoute.L2)
        self.assertTrue(validate_action_route(Action.BLOCK_ALL_CARDS, ApprovalRoute.L2))
        self.assertFalse(validate_action_route(Action.BLOCK_ALL_CARDS, ApprovalRoute.AUTO))
        self.assertFalse(validate_action_route(Action.BLOCK_ALL_CARDS, ApprovalRoute.L1))

    def test_file_report_route(self):
        """FILE_REPORT must always require L2 approval."""
        route = get_statutory_approval_route(Action.FILE_REPORT, exposure_usd=500.0)
        self.assertEqual(route, ApprovalRoute.L2)
        self.assertTrue(validate_action_route(Action.FILE_REPORT, ApprovalRoute.L2))
        self.assertFalse(validate_action_route(Action.FILE_REPORT, ApprovalRoute.AUTO))
        self.assertFalse(validate_action_route(Action.FILE_REPORT, ApprovalRoute.L1))

    def test_block_card_threshold_boundary(self):
        """BLOCK_CARD requires L1 when exposure <= $2,500; L2 when exposure > $2,500."""
        # Exposure = $0.00 -> L1
        self.assertEqual(get_statutory_approval_route(Action.BLOCK_CARD, 0.0), ApprovalRoute.L1)
        # Exposure = $2,500.00 (Exact boundary) -> L1
        self.assertEqual(get_statutory_approval_route(Action.BLOCK_CARD, 2500.00), ApprovalRoute.L1)
        # Exposure = $2,500.01 (Just over boundary) -> L2
        self.assertEqual(get_statutory_approval_route(Action.BLOCK_CARD, 2500.01), ApprovalRoute.L2)
        # Exposure = $10,000.00 -> L2
        self.assertEqual(get_statutory_approval_route(Action.BLOCK_CARD, 10000.00), ApprovalRoute.L2)


if __name__ == "__main__":
    unittest.main()
