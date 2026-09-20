"""
Unit and Integration Tests for Graph Adapter and GSQL Operations.
"""

import unittest
from src.graph.adapter import get_graph_adapter


class TestGraphAdapter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.adapter = get_graph_adapter(backend="in_memory")

    def test_backend_identification(self):
        """Adapter must explicitly identify backend as 'tigergraph' or 'in_memory'."""
        self.assertIn(self.adapter.backend, ["tigergraph", "in_memory"])

    def test_valid_transaction_lookup(self):
        """Lookup of transaction 3514030 (HHG-001) must return complete context."""
        res = self.adapter.get_transaction_context("3514030")
        self.assertEqual(res["query"], "get_transaction_context")
        self.assertEqual(len(res["results"]), 1)
        data = res["results"][0]
        self.assertEqual(data["customer_id"], "C12382")
        self.assertEqual(data["card"]["card_id"], "C12382-K1")
        self.assertEqual(data["transaction"]["amount"], 77.07)
        self.assertEqual(data["transaction"]["channel"], "in_person")
        self.assertEqual(data["billing_region"], "444.0")

    def test_invalid_transaction_lookup(self):
        """Lookup of nonexistent transaction must return empty results without error."""
        res = self.adapter.get_transaction_context("T_NONEXISTENT_999999")
        self.assertEqual(res["results"], [])

    def test_valid_card_history(self):
        """Card C12382-K1 must return chronological transactions."""
        res = self.adapter.get_card_history("C12382-K1")
        self.assertEqual(res["query"], "get_card_history")
        txns = res["results"]
        self.assertEqual(len(txns), 422)
        # Verify chronological ordering
        for i in range(len(txns) - 1):
            self.assertLessEqual(txns[i]["ts"], txns[i + 1]["ts"])

    def test_customer_history(self):
        """Customer C12382 must return card portfolio and activity."""
        res = self.adapter.get_customer_history("C12382")
        self.assertEqual(res["query"], "get_customer_history")
        self.assertEqual(len(res["results"]), 1)
        cust_data = res["results"][0]
        self.assertEqual(cust_data["customer_id"], "C12382")
        self.assertEqual(cust_data["total_transactions"], 422)

    def test_device_neighbors_and_connected_cards_hhg014(self):
        """Device lookup for HHG-014 must discover shared device and connected cards."""
        dev_prof = "SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080"
        dev_res = self.adapter.get_device_neighbors(dev_prof)
        self.assertEqual(dev_res["query"], "get_device_neighbors")
        self.assertGreater(len(dev_res["results"]), 0)
        conn_cards = dev_res["results"][0]["connected_cards"]
        self.assertIn("C13487-K1", conn_cards)
        self.assertIn("C03528-K1", conn_cards)
        self.assertIn("C09998-K1", conn_cards)

    def test_connected_cards_query(self):
        """Connected cards lookup for C13487-K1 must find cards sharing the Samsung device."""
        res = self.adapter.get_connected_cards("C13487-K1")
        self.assertEqual(res["query"], "get_connected_cards")
        self.assertEqual(len(res["results"]), 1)
        conn = res["results"][0]["connected_cards"]
        self.assertIn("C03528-K1", conn)
        self.assertIn("C09998-K1", conn)

    def test_similar_closed_cases_retrieval(self):
        """Closed cases query on card C12382-K1 must retrieve historical cases CC-1066, etc."""
        res = self.adapter.get_similar_closed_cases(card_id="C12382-K1")
        self.assertEqual(res["query"], "get_similar_closed_cases")
        cases = res["results"]
        case_ids = [c["case_id"] for c in cases]
        self.assertIn("CC-1066", case_ids)
        self.assertIn("CC-2964", case_ids)
        self.assertIn("CC-3587", case_ids)

    def test_transaction_chain_window(self):
        """Transaction chain around 3514030 within 24 hours must return adjacent transactions."""
        res = self.adapter.get_transaction_chain("3514030", window_hours=24)
        self.assertEqual(res["query"], "get_transaction_chain")
        self.assertGreaterEqual(len(res["results"]), 1)
        tids = [t["txn_id"] for t in res["results"]]
        self.assertIn("3514030", tids)

    def test_detect_card_testing_query(self):
        """Card testing query must return structured detection results."""
        res = self.adapter.detect_card_testing("C12382-K1", "2016-12-04 19:00:00")
        self.assertEqual(res["query"], "detect_card_testing")
        self.assertEqual(len(res["results"]), 1)
        # C12382 is normal spend, not testing
        self.assertFalse(res["results"][0]["is_testing"])

    def test_write_case_idempotence(self):
        """Writing an investigated case must persist it to graph and allow subsequent retrieval."""
        test_case = {
            "case_id": "TEST-HHG-999",
            "opened_at": "2016-12-05 00:00:00",
            "case": {
                "verdict": "fraud",
                "pattern": "card_not_present_fraud",
                "first_suspicious_txn_id": "3514030",
                "affected_txn_ids": ["3514030"],
                "exposure_usd": 77.07,
                "summary": "Automated integration test case writeback.",
                "card_id": "C12382-K1",
                "connected_card_ids": []
            },
            "next_best_actions": {
                "final": [{"action": "BLOCK_CARD"}]
            },
            "sar": {"file": False}
        }
        write_res = self.adapter.write_case(test_case)
        self.assertEqual(write_res["results"][0]["status"], "SUCCESS")

        # Now verify that it is discoverable via similar_closed_cases
        find_res = self.adapter.get_similar_closed_cases(card_id="C12382-K1")
        case_ids = [c["case_id"] for c in find_res["results"]]
        self.assertIn("TEST-HHG-999", case_ids)


if __name__ == "__main__":
    unittest.main()
