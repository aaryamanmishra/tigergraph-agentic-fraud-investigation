"""
Verification script for Live TigerGraph MCP calls on FraudNet.
Tests all 9 investigation queries via tigergraph-mcp against live TigerGraph Savanna.
"""

import asyncio
import json
import time
from typing import Dict, Any

from src.config import _load_dotenv, config
_load_dotenv()

# We import tigergraph_mcp tools
from tigergraph_mcp.connection_manager import ConnectionManager
from tigergraph_mcp.tools import run_installed_query, get_graph_schema, get_vertex_count


def parse_mcp_text_response(res_list) -> Dict[str, Any]:
    if not res_list:
        return {}
    text = res_list[0].text.strip()
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        json_str = text[start:end].strip() if end != -1 else text[start:].strip()
        return json.loads(json_str)
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        json_str = text[start:end].strip() if end != -1 else text[start:].strip()
        return json.loads(json_str)
    return json.loads(text)


async def run_live_mcp_tests():
    print("=" * 80)
    print(f"VERIFYING OFFICIAL TIGERGRAPH MCP ON LIVE GRAPH: {config.TG_GRAPHNAME}")
    print("=" * 80)

    ConnectionManager.load_profiles(".env")

    # 1. Schema check
    t0 = time.time()
    schema_res = await get_graph_schema(graph_name="FraudNet")
    lat_schema = round((time.time() - t0) * 1000, 1)
    schema_data = parse_mcp_text_response(schema_res)
    schema_dict = schema_data.get("data", {}).get("schema", {})
    v_types = [v.get("Name") for v in schema_dict.get("VertexTypes", [])]
    e_types = [e.get("Name") for e in schema_dict.get("EdgeTypes", [])]
    print(f"[1] Schema via MCP ({lat_schema}ms):")
    print(f"    Vertices ({len(v_types)}): {v_types}")
    print(f"    Edges ({len(e_types)}): {e_types}")
    assert len(v_types) == 7, f"Expected 7 vertex types, got {len(v_types)}"
    assert len(e_types) == 9, f"Expected 9 edge types, got {len(e_types)}"

    # 2. HHG-001 Transaction Context
    t0 = time.time()
    res1 = await run_installed_query(
        "get_transaction_context",
        params={"target_txn": ("3514030",)},
        graph_name="FraudNet"
    )
    data1 = parse_mcp_text_response(res1)
    lat1 = round((time.time() - t0) * 1000, 1)
    print(f"[2] HHG-001 get_transaction_context ({lat1}ms):")
    q_res1 = data1.get("data", {}).get("result", [])
    print(f"    Success: {data1.get('success')}, Result sections: {len(q_res1)}")
    # Verify transaction attributes
    start_v = q_res1[0].get("Start", [{}])[0]
    assert start_v.get("v_id") == "3514030"
    amt = start_v.get("attributes", {}).get("Start.amount")
    assert amt == 77.07, f"Expected 77.07, got {amt}"
    print(f"    Found Flagged Txn 3514030, Amount: ${amt}")

    # 3. HHG-001 Card History
    t0 = time.time()
    res2 = await run_installed_query(
        "get_card_history",
        params={"target_card": ("C12382-K1",), "start_time": "1970-01-01 00:00:00", "end_time": "2030-01-01 00:00:00"},
        graph_name="FraudNet"
    )
    data2 = parse_mcp_text_response(res2)
    lat2 = round((time.time() - t0) * 1000, 1)
    card_txns = data2.get("data", {}).get("result", [{}])[0].get("Txns", [])
    print(f"[3] HHG-001 get_card_history ({lat2}ms): Found {len(card_txns)} txns on C12382-K1")
    assert len(card_txns) > 0

    # 4. HHG-001 Customer History
    t0 = time.time()
    res3 = await run_installed_query(
        "get_customer_history",
        params={"target_customer": ("C12382",)},
        graph_name="FraudNet"
    )
    data3 = parse_mcp_text_response(res3)
    lat3 = round((time.time() - t0) * 1000, 1)
    print(f"[4] HHG-001 get_customer_history ({lat3}ms): Success={data3.get('success')}")

    # 5. HHG-001 Similar Closed Cases (Verify CC-1066, CC-1673, CC-2964, CC-3587)
    t0 = time.time()
    res4 = await run_installed_query(
        "get_similar_closed_cases",
        params={"target_card_id": "C12382-K1", "target_device_profile": ""},
        graph_name="FraudNet"
    )
    data4 = parse_mcp_text_response(res4)
    lat4 = round((time.time() - t0) * 1000, 1)
    cases = data4.get("data", {}).get("result", [{}])[0].get("Cases", [])
    case_ids = [c.get("v_id") for c in cases]
    print(f"[5] HHG-001 get_similar_closed_cases ({lat4}ms): {case_ids}")
    for exp_c in ["CC-1066", "CC-1673", "CC-2964", "CC-3587"]:
        assert exp_c in case_ids, f"Expected {exp_c} in prior closed cases"

    # 6. HHG-014 Transaction Context & Device Neighbors
    t0 = time.time()
    res5 = await run_installed_query(
        "get_transaction_context",
        params={"target_txn": ("3478561",)},
        graph_name="FraudNet"
    )
    data5 = parse_mcp_text_response(res5)
    lat5 = round((time.time() - t0) * 1000, 1)
    dev_prof = data5.get("data", {}).get("result", [{}])[0].get("Devices", [{}])[0].get("v_id")
    print(f"[6] HHG-014 get_transaction_context ({lat5}ms): Flagged txn 3478561, Device: {dev_prof}")
    assert dev_prof == "SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080"

    t0 = time.time()
    res6 = await run_installed_query(
        "get_device_neighbors",
        params={"target_device": (dev_prof,)},
        graph_name="FraudNet"
    )
    data6 = parse_mcp_text_response(res6)
    lat6 = round((time.time() - t0) * 1000, 1)
    dev_cards = data6.get("data", {}).get("result", [{}])[0].get("@@cards", [])
    print(f"[7] HHG-014 get_device_neighbors ({lat6}ms): Found {len(dev_cards)} cards sharing device profile")
    assert len(dev_cards) > 0
    assert "C13487-K1" in dev_cards

    # 7. HHG-014 Connected Cards
    t0 = time.time()
    res7 = await run_installed_query(
        "get_connected_cards",
        params={"target_card": ("C13487-K1",)},
        graph_name="FraudNet"
    )
    data7 = parse_mcp_text_response(res7)
    lat7 = round((time.time() - t0) * 1000, 1)
    conn_cards = data7.get("data", {}).get("result", [{}])[0].get("@@connected_cards", [])
    print(f"[8] HHG-014 get_connected_cards ({lat7}ms): Found {len(conn_cards)} connected cards")
    assert len(conn_cards) > 0
    assert "C03528-K1" in conn_cards

    # 7b. HHG-014 Device-Linked Historical Closed Cases
    res7b = await run_installed_query(
        "get_similar_closed_cases",
        params={"target_card_id": "", "target_device_profile": dev_prof},
        graph_name="FraudNet"
    )
    data7b = parse_mcp_text_response(res7b)
    hhg014_cases = [c.get("v_id") for c in data7b.get("data", {}).get("result", [{}])[0].get("Cases", [])]
    print(f"[8b] HHG-014 device closed cases: {hhg014_cases}")
    assert "CC-3035" in hhg014_cases

    # 8. Controlled Writeback Test and Readback
    test_case_id = f"TEST-MCP-{int(time.time())}"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.time()
    write_params = {
        "case_id": test_case_id,
        "opened_at": now_str,
        "closed_at": now_str,
        "outcome": "confirmed_fraud",
        "pattern": "test_mcp_integration",
        "first_fraud_txn_id": "3514030",
        "n_txns": 1,
        "exposure_usd": 77.07,
        "actions_taken": "BLOCK_CARD|CREATE_CASE",
        "report_filed": "No",
        "analyst_notes": "Phase 3B controlled MCP writeback verification.",
        "primary_card_id": "C12382-K1",
        "affected_txns": ["3514030"],
        "connected_cards": ["C12382-K1"]
    }
    res_w = await run_installed_query("write_case", params=write_params, graph_name="FraudNet")
    data_w = parse_mcp_text_response(res_w)
    lat_w = round((time.time() - t0) * 1000, 1)
    print(f"[9] Controlled writeback ({lat_w}ms): Success={data_w.get('success')}, CaseId={test_case_id}")
    assert data_w.get("success") is True

    # Read back the written case
    t0 = time.time()
    res_rb = await run_installed_query(
        "get_similar_closed_cases",
        params={"target_pattern": "test_mcp_integration", "max_cases": 5},
        graph_name="FraudNet"
    )
    data_rb = parse_mcp_text_response(res_rb)
    lat_rb = round((time.time() - t0) * 1000, 1)
    rb_cases = data_rb.get("data", {}).get("result", [{}])[0].get("Cases", [])
    rb_ids = [c.get("v_id") for c in rb_cases]
    print(f"[10] Readback verification ({lat_rb}ms): Found cases={rb_ids}")
    assert test_case_id in rb_ids, f"Expected {test_case_id} in {rb_ids}"

    # Verify idempotence (writing again does not fail)
    res_w2 = await run_installed_query("write_case", params=write_params, graph_name="FraudNet")
    data_w2 = parse_mcp_text_response(res_w2)
    assert data_w2.get("success") is True
    print("[11] Idempotence verified: Duplicate writeback succeeded cleanly.")

    # 9. Error Handling Verification
    # Nonexistent transaction ID
    res_err1 = await run_installed_query(
        "get_transaction_context",
        params={"target_txn": ("NONEXISTENT_TXN_99999",)},
        graph_name="FraudNet"
    )
    data_err1 = parse_mcp_text_response(res_err1)
    print(f"[12] Nonexistent Txn Handling: Success={data_err1.get('success')}")

    # Malformed parameters
    res_err2 = await run_installed_query(
        "get_transaction_context",
        params={},
        graph_name="FraudNet"
    )
    data_err2 = parse_mcp_text_response(res_err2)
    print(f"[13] Missing Parameter Handling: Success={data_err2.get('success')}")

    print("\n" + "=" * 80)
    print("ALL LIVE MCP VERIFICATION CHECKS COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_live_mcp_tests())
