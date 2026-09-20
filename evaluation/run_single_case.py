"""
Single Case Evaluation CLI Runner for TigerGraph Fraud Investigation Agent.
Executes an end-to-end investigation on a specific benchmark case, serializes the result,
and runs both Schema Validation (docs/answer_schema.md) and Entity Integrity checks.

Usage:
    python evaluation/run_single_case.py --case HHG-001 --backend tigergraph --provider gemini
    python evaluation/run_single_case.py --case HHG-014 --backend tigergraph --provider gemini
    python evaluation/run_single_case.py --case HHG-001 --backend in_memory --provider mock
"""

import os
import sys
import csv
import json
import argparse
import time
from typing import Dict, Any, Optional, Tuple

from src.config import config, _load_dotenv
_load_dotenv()

from src.graph.adapter import GraphAdapter
from src.agent.tools.contracts import InvestigationTools
from src.agent.llm.factory import get_llm_provider
from src.agent.workflow import InvestigationWorkflow
from src.agent.serializer import serialize_case_answer
from evaluation.validate_schema import validate_case_answer
from evaluation.check_integrity import check_case_integrity, get_entity_registry


def load_case_from_case_pack(case_id: str, data_dir: str = ".") -> Dict[str, Any]:
    """Loads target case attributes from case_pack.csv."""
    case_pack_path = os.path.join(data_dir, "case_pack.csv")
    if not os.path.exists(case_pack_path):
        raise FileNotFoundError(f"case_pack.csv not found at {case_pack_path}")

    with open(case_pack_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["case_id"] == case_id:
                return dict(row)

    raise ValueError(f"Case ID '{case_id}' not found in {case_pack_path}")


def run_case(
    case_id: str,
    backend: str = "tigergraph",
    provider: str = "gemini",
    output_path: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Executes an investigation case end-to-end and validates outputs.
    """
    # 1. Initialize LLM Provider
    llm = get_llm_provider(provider_type=provider)
    is_real = getattr(llm, "is_real", False)
    llm_mode = "REAL" if is_real else "MOCK"
    provider_label = getattr(llm, "provider_name", "Mock")

    # 2. Initialize Adapter & Tools
    adapter = GraphAdapter(backend=backend)
    actual_backend = getattr(adapter, "backend", backend).upper()
    actual_graph = getattr(adapter, "graph_name", "FraudNet")

    # Guard: Fail immediately if live TigerGraph requested but failed to attach to FraudNet
    if backend.lower() == "tigergraph":
        if actual_backend != "TIGERGRAPH":
            raise RuntimeError(f"Backend verification failed: requested TIGERGRAPH but got '{actual_backend}'")
        if actual_graph != "FraudNet":
            raise RuntimeError(f"Graph verification failed: expected 'FraudNet' but got '{actual_graph}'")

    print(f"\n========================================================")
    print(f"Case: {case_id}")
    print(f"LLM Provider: {provider_label}")
    print(f"LLM Mode: {llm_mode}")
    print(f"Model: {getattr(llm, 'model_name', 'default')}")
    print(f"Backend: {actual_backend}")
    print(f"Graph: {actual_graph}")
    print(f"========================================================")

    # 3. Load case metadata
    case_data = load_case_from_case_pack(case_id)
    print(f"[*] Trigger: {case_data['trigger_type']} | Flagged Txn: {case_data['flagged_txn_id']} | Card: {case_data['card_id']} | Customer: {case_data['customer_id']}")

    tools = InvestigationTools(adapter=adapter)

    # 4. Execute Investigation Workflow
    workflow = InvestigationWorkflow(tools=tools, llm_provider=llm)
    t0 = time.time()
    state = workflow.run(case_data)
    elapsed_s = round(time.time() - t0, 3)

    print(f"\n--- Investigation Execution Details ---")
    print(f"Workflow finished in: {elapsed_s}s (Engine Latency: {state.latency_ms}ms)")
    print(f"Tool Calls Executed ({len(state.tool_calls)}):")
    for tc in state.tool_calls:
        err_info = f" (error: {tc.get('error')})" if tc.get("error") else ""
        print(f"  - {tc.get('tool_name')}: success={tc.get('success')}, latency={tc.get('latency_ms')}ms{err_info}")

    if state.errors:
        print(f"\nExecution Errors / Warnings ({len(state.errors)}):")
        for err in state.errors:
            print(f"  [!] {err}")


    print(f"\nReasoning Timeline ({len(state.investigation_timeline)} steps):")
    for ev in state.investigation_timeline:
        disc = (ev.evidence_discovered[:90] + '...') if len(ev.evidence_discovered) > 90 else ev.evidence_discovered
        print(f"  [{ev.stage}] {ev.tool_used} -> {ev.result} ({disc})")

    if state.evidence_requests:
        print(f"\nEvidence Requests ({len(state.evidence_requests)}):")
        for req in state.evidence_requests:
            print(f"  - Type: {req.get('type')}, Target: {req.get('target')}, Query: {req.get('query')}")
        for resp in state.evidence_responses:
            print(f"  - Response: {resp.get('response')} ({resp.get('note')})")

    print(f"\nInitial Assessment: {state.initial_assessment}")
    print(f"Final Assessment:   {state.final_assessment}")
    print(f"Policy Rules Triggered: {state.policy_rules_triggered}")
    print(f"Statutory Actions:      {state.recommended_actions}")
    print(f"Approval Routes:        {state.approval_routes}")
    print(f"SAR Required:           {state.sar_required}")
    if state.rag_context:
        print(f"\nGraphRAG Retrieval Context:")
        print(f"  - Retrieved Policies: {state.rag_context.get('retrieved_policies', [])}")
        print(f"  - Retrieved Typologies: {state.rag_context.get('retrieved_typologies', [])}")
        print(f"  - Case Memory Precedents: {state.rag_context.get('case_memory_count', 0)}")
        print(f"  - Subgraph Evidence Items: {state.rag_context.get('graph_evidence_count', 0)}")
    print(f"Token Usage:            {state.token_usage}")

    # 5. Serialize to benchmark answer
    answer = serialize_case_answer(state)

    # 6. Validate JSON Schema and Cross-Field Invariants
    schema_res = validate_case_answer(answer)
    if schema_res.is_valid:
        print("\n[✓] Schema Validation: PASSED")
    else:
        print(f"\n[✗] Schema Validation: FAILED ({len(schema_res.errors)} errors)")
        for err in schema_res.errors:
            print(f"    - {err}")

    # 7. Check Entity Integrity
    registry = get_entity_registry()
    integrity_errors = check_case_integrity(answer, registry=registry)
    if not integrity_errors:
        print("[✓] Entity ID Integrity: PASSED (All referenced IDs strictly grounded in dataset)")
    else:
        print(f"[✗] Entity ID Integrity: FAILED ({len(integrity_errors)} errors)")
        for err in integrity_errors:
            print(f"    - {err}")

    # 8. Save output if requested
    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(answer, f, indent=2)
        print(f"[✓] Answer written to: {output_path}")

    # Final Summary
    is_fully_valid = schema_res.is_valid and len(integrity_errors) == 0
    print("\n========================================================")
    print(f"Case:               {case_id}")
    print(f"LLM Provider:       {provider_label}")
    print(f"LLM Mode:           {llm_mode}")
    print(f"Backend:            {actual_backend}")
    print(f"Graph:              {actual_graph}")
    print(f"Status:             {answer['case']['status']}")
    print(f"Verdict:            {answer['case']['verdict']}")
    print(f"Fraud Probability:  {answer['case']['fraud_probability']}")
    print(f"Pattern:            {answer['case']['pattern']}")
    print(f"Exposure:           ${answer['case']['exposure_usd']:,.2f}")
    print(f"SAR Filed:          {answer['sar']['file']}")
    print(f"Final Actions:      {[a['action'] for a in answer['next_best_actions']['final']]}")
    print(f"Stop Reason:        {answer['stop_reason']}")
    print(f"Overall Valid:      {is_fully_valid}")
    print("========================================================\n")

    return is_fully_valid, answer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run single case fraud investigation")
    parser.add_argument("--case", type=str, default="HHG-001", help="Target Case ID (e.g. HHG-001, HHG-014)")
    parser.add_argument("--backend", type=str, default=os.environ.get("TG_BACKEND", "tigergraph"), choices=["in_memory", "tigergraph"], help="Graph backend")
    parser.add_argument("--provider", type=str, default="gemini", choices=["gemini", "openai", "mistral", "mock"], help="LLM provider")
    parser.add_argument("--output", type=str, default=None, help="Output path for answer JSON")
    args = parser.parse_args()

    success, _ = run_case(
        case_id=args.case,
        backend=args.backend,
        provider=args.provider,
        output_path=args.output
    )
    sys.exit(0 if success else 1)
