"""
Unit Tests for Fraud Policy Rules R1 through R10.
"""

import unittest
from src.policy.actions import Action, ApprovalRoute
from src.policy.engine import PolicyEngine, InvestigationState


class TestPolicyRules(unittest.TestCase):

    def test_r1_weak_signal_customer_verification(self):
        """R1: Single signal & prob < 0.70 mandates verification before blocking."""
        state = InvestigationState(
            case_id="HHG-001",
            flagged_txn_id="3514030",
            card_id="C12382-K1",
            customer_id="C12382",
            fraud_probability=0.35,
            verdict="uncertain",
            is_single_signal=True,
            stage="initial"
        )
        res = PolicyEngine.evaluate(state)
        self.assertIn("R1", res.policy_rules_triggered)
        self.assertTrue(res.requires_more_evidence)
        actions = [a["action"] for a in res.recommended_actions]
        self.assertIn(Action.VERIFY_WITH_CUSTOMER.value, actions)
        self.assertNotIn(Action.BLOCK_CARD.value, actions)
        self.assertNotIn(Action.DECLINE_TRANSACTION.value, actions)

    def test_r2_customer_denies_transaction(self):
        """R2: Customer denies transaction -> BLOCK_CARD, CREATE_CASE; FILE_REPORT if > $1000."""
        # Case A: Exposure <= 1000
        state_low = InvestigationState(
            case_id="HHG-002",
            flagged_txn_id="3478782",
            card_id="C11891-K1",
            customer_id="C11891",
            fraud_probability=0.85,
            verdict="fraud",
            exposure_usd=350.0,
            customer_reply="denied",
            stage="final"
        )
        res_low = PolicyEngine.evaluate(state_low)
        self.assertIn("R2", res_low.policy_rules_triggered)
        actions_low = [a["action"] for a in res_low.recommended_actions]
        self.assertIn(Action.BLOCK_CARD.value, actions_low)
        self.assertIn(Action.CREATE_CASE.value, actions_low)
        self.assertFalse(res_low.sar_required)

        # Case B: Exposure > 1000 -> mandates FILE_REPORT
        state_high = InvestigationState(
            case_id="HHG-010",
            flagged_txn_id="3506725",
            card_id="C10434-K1",
            customer_id="C10434",
            fraud_probability=0.90,
            verdict="fraud",
            exposure_usd=1200.0,
            customer_reply="denied",
            stage="final"
        )
        res_high = PolicyEngine.evaluate(state_high)
        self.assertIn("R2", res_high.policy_rules_triggered)
        actions_high = [a["action"] for a in res_high.recommended_actions]
        self.assertIn(Action.BLOCK_CARD.value, actions_high)
        self.assertIn(Action.CREATE_CASE.value, actions_high)
        self.assertIn(Action.FILE_REPORT.value, actions_high)
        self.assertTrue(res_high.sar_required)

    def test_r3_customer_confirms_transaction(self):
        """R3: Customer confirms transaction -> CLOSE_NO_FRAUD."""
        state = InvestigationState(
            case_id="HHG-001",
            flagged_txn_id="3514030",
            card_id="C12382-K1",
            customer_id="C12382",
            fraud_probability=0.10,
            verdict="legitimate",
            customer_reply="confirmed",
            stage="final"
        )
        res = PolicyEngine.evaluate(state)
        self.assertIn("R3", res.policy_rules_triggered)
        actions = [a["action"] for a in res.recommended_actions]
        self.assertEqual(actions, [Action.CLOSE_NO_FRAUD.value])
        self.assertFalse(res.sar_required)
        self.assertFalse(res.case_required)

    def test_r4_no_customer_reply_within_24h(self):
        """R4: No reply within 24h -> MONITOR_CARD, DECLINE_TRANSACTION; ESCALATE if > $500."""
        # Exposure <= 500
        state_under = InvestigationState(
            case_id="HHG-003",
            flagged_txn_id="3530164",
            card_id="C08623-K2",
            customer_id="C08623",
            fraud_probability=0.45,
            verdict="uncertain",
            exposure_usd=200.0,
            customer_reply="no_reply_24h",
            stage="final"
        )
        res_under = PolicyEngine.evaluate(state_under)
        self.assertIn("R4", res_under.policy_rules_triggered)
        actions_under = [a["action"] for a in res_under.recommended_actions]
        self.assertIn(Action.MONITOR_CARD.value, actions_under)
        self.assertIn(Action.DECLINE_TRANSACTION.value, actions_under)
        self.assertNotIn(Action.ESCALATE_TO_ANALYST.value, actions_under)

        # Exposure > 500
        state_over = InvestigationState(
            case_id="HHG-006",
            flagged_txn_id="3476682",
            card_id="C07297-K1",
            customer_id="C07297",
            fraud_probability=0.55,
            verdict="uncertain",
            exposure_usd=650.0,
            customer_reply="no_reply_24h",
            stage="final"
        )
        res_over = PolicyEngine.evaluate(state_over)
        self.assertIn("R4", res_over.policy_rules_triggered)
        actions_over = [a["action"] for a in res_over.recommended_actions]
        self.assertIn(Action.MONITOR_CARD.value, actions_over)
        self.assertIn(Action.DECLINE_TRANSACTION.value, actions_over)
        self.assertIn(Action.ESCALATE_TO_ANALYST.value, actions_over)

    def test_r5_card_testing_sequence(self):
        """R5: Card testing sequence -> DECLINE_TRANSACTION + STEP_UP_AUTH; BLOCK if cleared > $100."""
        # Testing without cleared > $100
        state_pending = InvestigationState(
            case_id="HHG-005",
            flagged_txn_id="3523199",
            card_id="C02923-K1",
            customer_id="C02923",
            fraud_probability=0.75,
            verdict="fraud",
            card_testing_detected=True,
            card_testing_cleared_over_100=False
        )
        res_pending = PolicyEngine.evaluate(state_pending)
        self.assertIn("R5", res_pending.policy_rules_triggered)
        actions_pending = [a["action"] for a in res_pending.recommended_actions]
        self.assertIn(Action.DECLINE_TRANSACTION.value, actions_pending)
        self.assertIn(Action.STEP_UP_AUTH.value, actions_pending)
        self.assertNotIn(Action.BLOCK_CARD.value, actions_pending)

        # Testing with cleared purchase > $100
        state_cleared = InvestigationState(
            case_id="HHG-005",
            flagged_txn_id="3523199",
            card_id="C02923-K1",
            customer_id="C02923",
            fraud_probability=0.88,
            verdict="fraud",
            exposure_usd=150.0,
            card_testing_detected=True,
            card_testing_cleared_over_100=True
        )
        res_cleared = PolicyEngine.evaluate(state_cleared)
        self.assertIn("R5", res_cleared.policy_rules_triggered)
        actions_cleared = [a["action"] for a in res_cleared.recommended_actions]
        self.assertIn(Action.DECLINE_TRANSACTION.value, actions_cleared)
        self.assertIn(Action.BLOCK_CARD.value, actions_cleared)

    def test_r6_shared_origin_coordinated_attack(self):
        """R6: Shared origin across cards -> CREATE_CASE, FILE_REPORT, MONITOR_CONNECTED_CARDS."""
        state = InvestigationState(
            case_id="HHG-014",
            flagged_txn_id="3478561",
            card_id="C13487-K1",
            customer_id="C13487",
            fraud_probability=0.85,
            verdict="fraud",
            shared_origin_detected=True,
            shared_origin_element="DeviceProfile: SM-G935F / Proxy",
            connected_card_ids=["C03528-K1", "C09998-K1"]
        )
        res = PolicyEngine.evaluate(state)
        self.assertIn("R6", res.policy_rules_triggered)
        actions = [a["action"] for a in res.recommended_actions]
        self.assertIn(Action.CREATE_CASE.value, actions)
        self.assertIn(Action.FILE_REPORT.value, actions)
        self.assertIn(Action.MONITOR_CONNECTED_CARDS.value, actions)
        self.assertTrue(res.sar_required)

    def test_r7_disputed_recurring_spend(self):
        """R7: Disputed recurring charge -> CREATE_CASE, VERIFY_WITH_CUSTOMER, WARN_CUSTOMER; no block."""
        state = InvestigationState(
            case_id="HHG-004",
            flagged_txn_id="3583227",
            card_id="C08106-K1",
            customer_id="C08106",
            fraud_probability=0.25,
            verdict="uncertain",
            customer_reply="disputed_recurring"
        )
        res = PolicyEngine.evaluate(state)
        self.assertIn("R7", res.policy_rules_triggered)
        actions = [a["action"] for a in res.recommended_actions]
        self.assertIn(Action.CREATE_CASE.value, actions)
        self.assertIn(Action.VERIFY_WITH_CUSTOMER.value, actions)
        self.assertIn(Action.WARN_CUSTOMER.value, actions)
        self.assertNotIn(Action.BLOCK_CARD.value, actions)

    def test_r8_escalate_uncertain_and_exposed(self):
        """R8: Uncertain verdict & exposure > $500 -> ESCALATE_TO_ANALYST."""
        state = InvestigationState(
            case_id="HHG-015",
            flagged_txn_id="3464869",
            card_id="C03042-K1",
            customer_id="C03042",
            fraud_probability=0.50,
            verdict="uncertain",
            exposure_usd=599.94
        )
        res = PolicyEngine.evaluate(state)
        self.assertIn("R8", res.policy_rules_triggered)
        actions = [a["action"] for a in res.recommended_actions]
        self.assertIn(Action.ESCALATE_TO_ANALYST.value, actions)

    def test_r9_undocumented_patterns(self):
        """R9: Undocumented pattern -> CREATE_CASE, FILE_REPORT, ESCALATE_TO_ANALYST."""
        state = InvestigationState(
            case_id="HHG-014",
            flagged_txn_id="3478561",
            card_id="C13487-K1",
            customer_id="C13487",
            fraud_probability=0.88,
            verdict="fraud",
            pattern="undocumented",
            is_undocumented_abuse=True
        )
        res = PolicyEngine.evaluate(state)
        self.assertIn("R9", res.policy_rules_triggered)
        actions = [a["action"] for a in res.recommended_actions]
        self.assertIn(Action.CREATE_CASE.value, actions)
        self.assertIn(Action.FILE_REPORT.value, actions)
        self.assertIn(Action.ESCALATE_TO_ANALYST.value, actions)
        self.assertTrue(res.sar_required)

    def test_r10_never_block_all_cards_unless_multi_compromise(self):
        """R10: BLOCK_ALL_CARDS requires 2+ customer cards confirmed fraud or compromised credentials."""
        # Only 1 card compromised: BLOCK_ALL_CARDS forbidden
        state_single = InvestigationState(
            case_id="HHG-002",
            flagged_txn_id="3478782",
            card_id="C11891-K1",
            customer_id="C11891",
            fraud_probability=0.92,
            verdict="fraud",
            num_compromised_cards_for_customer=1,
            credentials_compromised=False
        )
        res_single = PolicyEngine.evaluate(state_single)
        actions_single = [a["action"] for a in res_single.recommended_actions]
        self.assertNotIn(Action.BLOCK_ALL_CARDS.value, actions_single)

        # 2 cards compromised: BLOCK_ALL_CARDS permitted
        state_multi = InvestigationState(
            case_id="HHG-002",
            flagged_txn_id="3478782",
            card_id="C11891-K1",
            customer_id="C11891",
            fraud_probability=0.92,
            verdict="fraud",
            num_compromised_cards_for_customer=2,
            credentials_compromised=False
        )
        res_multi = PolicyEngine.evaluate(state_multi)
        self.assertIn("R10", res_multi.policy_rules_triggered)
        actions_multi = [a["action"] for a in res_multi.recommended_actions]
        self.assertIn(Action.BLOCK_ALL_CARDS.value, actions_multi)


if __name__ == "__main__":
    unittest.main()
