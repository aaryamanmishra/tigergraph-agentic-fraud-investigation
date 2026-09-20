"""
Integration and Regression Tests for Official TigerGraph MCP on Live FraudNet.
Tests MCP initialization, tool discovery, live graph connection,
HHG-001 & HHG-014 investigation queries, controlled writeback, idempotence,
cleanup, error handling, and credential redaction.
Zero dependency on external async test plugins (uses standard asyncio.run).
"""

import os
import time
import pytest
import asyncio
from typing import Dict, Any

from src.config import config, _load_dotenv
_load_dotenv()

from src.graph.mcp_client import TigerGraphMCPClient, redact_secrets
import urllib.request


def _is_live_cluster_online() -> bool:
    """Checks if the remote TigerGraph Cloud instance is actively running and responsive."""
    base = config.get_rest_base_url()
    for endpoint in [f"{base}/restpp/echo", f"{base}/echo"]:
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "TestChecker/1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            continue
    return False


@pytest.fixture
def mcp_client():
    """Provides initialized TigerGraphMCPClient targeting FraudNet for each test."""
    from tigergraph_mcp.connection_manager import ConnectionManager
    ConnectionManager._connection_pool.clear()
    return TigerGraphMCPClient(graph_name="FraudNet")


class TestTigerGraphMCPIntegration:
    """Test suite for Phase 3B official tigergraph-mcp integration."""

    def test_mcp_initialization(self, mcp_client):
        """MCP client must initialize successfully with .env profiles."""
        assert mcp_client.initialized is True
        assert mcp_client.graph_name == "FraudNet"
        assert mcp_client.conn_manager is not None
        assert mcp_client.tools_module is not None

    def test_mcp_tool_discovery(self, mcp_client):
        """Official tigergraph-mcp must expose standard tools."""
        async def _run():
            tools = await mcp_client.list_available_tools()
            assert len(tools) >= 50
            assert "tigergraph__run_installed_query" in tools
            assert "tigergraph__get_graph_schema" in tools
            assert "tigergraph__get_node" in tools
            assert "tigergraph__delete_node" in tools
            assert "tigergraph__get_vertex_count" in tools
        asyncio.run(_run())

    def test_live_fraudnet_schema_and_connection(self, mcp_client):
        """MCP schema query must verify all 7 vertex types and 9 edge types on FraudNet."""
        if not _is_live_cluster_online():
            pytest.skip("TigerGraph Cloud instance is stopped/unreachable (resume workspace on tgcloud.io to run live).")

        async def _run():
            schema = await mcp_client.get_graph_schema()
            assert schema["success"] is True
            assert schema["graph_name"] == "FraudNet"

            expected_vertices = {
                "Customer", "Card", "Transaction", "DeviceProfile",
                "EmailDomain", "BillingRegion", "ClosedCase"
            }
            expected_edges = {
                "OWNS", "MADE", "FROM_DEVICE", "PURCHASER_EMAIL",
                "BILLED_IN", "NEXT", "INVOLVES", "ON_CARD", "CONNECTED_TO"
            }
            assert expected_vertices.issubset(set(schema["vertex_types"]))
            assert expected_edges.issubset(set(schema["edge_types"]))
        asyncio.run(_run())

    def test_hhg001_mcp_regression(self, mcp_client):
        """
        HHG-001 Investigation via MCP:
        - Flagged transaction 3514030 ($77.07, region 444.0)
        - Card C12382-K1, Customer C12382
        - Complete card history (422 transactions)
        - Prior closed cases CC-1066, CC-1673, CC-2964, CC-3587
        """
        if not _is_live_cluster_online():
            pytest.skip("TigerGraph Cloud instance is stopped/unreachable (resume workspace on tgcloud.io to run live).")

        async def _run():
            # 1. Transaction context
            ctx = await mcp_client.get_transaction_context("3514030")
            assert ctx["success"] is True
            assert len(ctx["results"]) == 1
            txn_data = ctx["results"][0]
            assert txn_data["transaction"]["txn_id"] == "3514030"
            assert txn_data["transaction"]["amount"] == 77.07
            assert txn_data["card"]["card_id"] == "C12382-K1"
            assert txn_data["customer_id"] == "C12382"
            assert txn_data["billing_region"] == "444.0"

            # 2. Card history
            hist = await mcp_client.get_card_history("C12382-K1")
            assert hist["success"] is True
            assert hist["count"] > 400
            assert any(t["txn_id"] == "3514030" for t in hist["results"])

            # 3. Customer history
            cust_hist = await mcp_client.get_customer_history("C12382")
            assert cust_hist["success"] is True
            assert any(c["card_id"] == "C12382-K1" for c in cust_hist["cards"])

            # 4. Prior closed cases (CC-1066, CC-1673, CC-2964, CC-3587)
            cases_res = await mcp_client.get_similar_closed_cases(card_id="C12382-K1")
            assert cases_res["success"] is True
            retrieved_cases = [c["case_id"] for c in cases_res["cases"]]
            for required_case in ["CC-1066", "CC-1673", "CC-2964", "CC-3587"]:
                assert required_case in retrieved_cases, f"Case {required_case} missing from MCP retrieval"
        asyncio.run(_run())

    def test_hhg014_mcp_regression(self, mcp_client):
        """
        HHG-014 Investigation via MCP:
        - Flagged transaction 3478561 on C13487-K1
        - Samsung SM-G935F device profile
        - Device neighborhood with shared cards and customers
        - Connected cards (including C03528-K1)
        - Historical case CC-3035
        """
        if not _is_live_cluster_online():
            pytest.skip("TigerGraph Cloud instance is stopped/unreachable (resume workspace on tgcloud.io to run live).")

        async def _run():
            # 1. Transaction context
            ctx = await mcp_client.get_transaction_context("3478561")
            assert ctx["success"] is True
            assert len(ctx["results"]) == 1
            txn_data = ctx["results"][0]
            assert txn_data["card"]["card_id"] == "C13487-K1"
            assert txn_data["customer_id"] == "C13487"
            dev_prof = txn_data["device_profile"]
            assert dev_prof == "SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080"

            # 2. Device neighbors
            dev_neighbors = await mcp_client.get_device_neighbors(dev_prof)
            assert dev_neighbors["success"] is True
            assert "C13487-K1" in dev_neighbors["cards"]
            assert len(dev_neighbors["cards"]) > 1

            # 3. Connected cards
            conn_cards_res = await mcp_client.get_connected_cards("C13487-K1")
            assert conn_cards_res["success"] is True
            assert "C03528-K1" in conn_cards_res["connected_cards"]

            # 4. Device historical cases
            dev_cases = await mcp_client.get_similar_closed_cases(device_profile=dev_prof)
            assert dev_cases["success"] is True
            case_ids = [c["case_id"] for c in dev_cases["cases"]]
            assert "CC-3035" in case_ids
        asyncio.run(_run())

    def test_mcp_controlled_write_readback_idempotence_and_cleanup(self, mcp_client):
        """
        Controlled Writeback via MCP:
        - Write temporary test case to FraudNet
        - Read back via get_similar_closed_cases
        - Verify write idempotence
        - Clean up temporary test case
        """
        if not _is_live_cluster_online():
            pytest.skip("TigerGraph Cloud instance is stopped/unreachable (resume workspace on tgcloud.io to run live).")

        async def _run():
            test_case_id = f"TEST-MCP-{int(time.time())}"
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")

            test_payload = {
                "case_id": test_case_id,
                "opened_at": now_str,
                "closed_at": now_str,
                "case": {
                    "verdict": "fraud",
                    "pattern": "test_mcp_writeback",
                    "first_suspicious_txn_id": "3514030",
                    "affected_txn_ids": ["3514030"],
                    "exposure_usd": 77.07,
                    "summary": "Controlled MCP writeback test.",
                    "card_id": "C12382-K1",
                    "connected_card_ids": ["C12382-K1"]
                },
                "next_best_actions": {
                    "final": [{"action": "BLOCK_CARD"}, {"action": "CREATE_CASE"}]
                },
                "sar": {"file": False}
            }

            # 1. Write case
            write_res = await mcp_client.write_case(test_payload)
            assert write_res["success"] is True
            assert write_res["case_id"] == test_case_id

            # 2. Read back
            rb_res = await mcp_client.get_similar_closed_cases(card_id="C12382-K1")
            assert rb_res["success"] is True
            found_ids = [c["case_id"] for c in rb_res["cases"]]
            assert test_case_id in found_ids

            # 3. Verify idempotence
            write_res2 = await mcp_client.write_case(test_payload)
            assert write_res2["success"] is True

            # 4. Clean up
            del_res = await mcp_client.delete_case(test_case_id)
            assert del_res["success"] is True

            # 5. Verify cleanup
            rb_post_del = await mcp_client.get_similar_closed_cases(card_id="C12382-K1")
            post_del_ids = [c["case_id"] for c in rb_post_del["cases"]]
            assert test_case_id not in post_del_ids
        asyncio.run(_run())

    def test_mcp_malformed_requests(self, mcp_client):
        """MCP operations must reject empty or malformed inputs with clean exceptions."""
        async def _run():
            with pytest.raises(ValueError):
                await mcp_client.get_transaction_context("")

            with pytest.raises(ValueError):
                await mcp_client.get_card_history("")

            with pytest.raises(ValueError):
                await mcp_client.get_customer_history("")

            with pytest.raises(ValueError):
                await mcp_client.write_case({"case_id": ""})

            # Nonexistent transaction must return empty results without unhandled failure
            res = await mcp_client.get_transaction_context("NONEXISTENT_TXN_99999999")
            assert res["results"] == []
        asyncio.run(_run())

    def test_mcp_no_credential_leakage(self, mcp_client):
        """MCP client and error messages must strictly redact passwords, tokens, and secrets."""
        secret = os.getenv("TG_SECRET", "")
        pwd = os.getenv("TG_PASSWORD", "")
        token = os.getenv("TG_TOKEN", "")

        test_str = f"Error communicating with secret={secret} pwd={pwd} token={token}"
        redacted = redact_secrets(test_str)

        if secret:
            assert secret not in redacted
            assert "[REDACTED_SECRET]" in redacted
        if pwd:
            assert pwd not in redacted
            assert "[REDACTED_PASSWORD]" in redacted
        if token:
            assert token not in redacted
            assert "[REDACTED_TOKEN]" in redacted
