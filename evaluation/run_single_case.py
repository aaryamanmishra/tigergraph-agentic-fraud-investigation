"""
Single Case Evaluation CLI Runner for TigerGraph Fraud Investigation Agent.
Executes an end-to-end investigation on a specific benchmark case, serializes the result,
and runs both Schema Validation (docs/answer_schema.md) and Entity Integrity checks.

Usage:
    python evaluation/run_single_case.py --case HHG-001
    python evaluation/run_single_case.py --case HHG-014 --backend in_memory --provider mock
    python evaluation/run_single_case.py --case HHG-001 --output results/HHG-001_answer.json
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
    backend: str = "in_memory",
    provider: str = "mock",
    output_path: Optional[str] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Executes an investigation case end-to-end and validates outputs.
    """
    print(f"\n========================================================")
    print(f"  INVESTIGATION RUNNER: {case_id}")
    print(f"  Backend: {backend} | LLM Provider: {provider}")
    print(f"========================================================")

    # 1. Load case metadata
    case_data = load_case_from_case_pack(case_id)
    print(f"[*] Loaded case metadata: {case_data['trigger_type']} (Card: {case_data['card_id']}, Txn: {case_data['flagged_txn_id']})")

    # 2. Initialize Adapter & Tools
    adapter = GraphAdapter(backend=backend)
    tools = InvestigationTools(adapter=adapter)

    # 3. Initialize LLM Provider
    llm = get_llm_provider(provider_type=provider)
    print(f"[*] LLM reasoner initialized: {getattr(llm, 'model_name', provider)}")

    # 4. Execute Investigation Workflow
    workflow = InvestigationWorkflow(tools=tools, llm_provider=llm)
    t0 = time.time()
    state = workflow.run(case_data)
    elapsed_s = round(time.time() - t0, 3)

    print(f"[✓] Workflow finished in {elapsed_s}s (latency recorded: {state.latency_ms}ms)")
    print(f"[*] State outcome: Verdict={state.verdict}, Pattern={state.fraud_pattern}, Probability={state.fraud_probability:.2f}")

    # 5. Serialize to benchmark answer
    answer = serialize_case_answer(state)

    # 6. Validate JSON Schema and Cross-Field Invariants
    schema_res = validate_case_answer(answer)
    if schema_res.is_valid:
        print("[✓] Schema Validation: PASSED")
    else:
        print(f"[✗] Schema Validation: FAILED ({len(schema_res.errors)} errors)")
        for err in schema_res.errors:
            print(f"    - {err}")

    # 7. Check Entity Integrity
    registry = get_entity_registry()
    integrity_errors = check_case_integrity(answer, registry=registry)
    if not integrity_errors:
        print("[✓] Entity ID Integrity: PASSED (All IDs strictly grounded in dataset)")
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

    # Summary
    is_fully_valid = schema_res.is_valid and len(integrity_errors) == 0
    print("\n--------------------------------------------------------")
    print(f"Summary for {case_id}:")
    print(f"  Status:             {answer['case']['status']}")
    print(f"  Verdict:            {answer['case']['verdict']}")
    print(f"  Fraud Probability:  {answer['case']['fraud_probability']}")
    print(f"  Pattern:            {answer['case']['pattern']}")
    print(f"  Exposure:           ${answer['case']['exposure_usd']:,.2f}")
    print(f"  SAR Filed:          {answer['sar']['file']}")
    print(f"  Final Actions:      {[a['action'] for a in answer['next_best_actions']['final']]}")
    print(f"  Stop Reason:        {answer['stop_reason']}")
    print(f"  Overall Valid:      {is_fully_valid}")
    print("--------------------------------------------------------\n")

    return is_fully_valid, answer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run single case fraud investigation")
    parser.add_argument("--case", type=str, default="HHG-001", help="Target Case ID (e.g. HHG-001, HHG-014)")
    parser.add_argument("--backend", type=str, default=os.environ.get("TG_BACKEND", "in_memory"), choices=["in_memory", "tigergraph"], help="Graph backend")
    parser.add_argument("--provider", type=str, default="mock", choices=["mock", "openai"], help="LLM provider")
    parser.add_argument("--output", type=str, default=None, help="Output path for answer JSON")
    args = parser.parse_args()

    success, _ = run_case(
        case_id=args.case,
        backend=args.backend,
        provider=args.provider,
        output_path=args.output
    )
    sys.exit(0 if success else 1)
