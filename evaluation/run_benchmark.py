"""
Full 20-Case Real Benchmark Batch Runner for TigerGraph Fraud Investigation Agent.
Executes all 20 benchmark cases (HHG-001 through HHG-020) against live TigerGraph FraudNet
with real Gemini LLM reasoning and GraphRAG retrieval.
Validates each answer against official schemas, entity integrity, and policy authority.
Generates individual submission files cases/<CASE_ID>.json and docs/full_benchmark_report.md.
"""

import os
import sys
import csv
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from src.config import config, _load_dotenv
_load_dotenv()

from src.graph.adapter import GraphAdapter
from src.agent.tools.contracts import InvestigationTools
from src.agent.llm.factory import get_llm_provider
from src.agent.workflow import InvestigationWorkflow
from src.agent.serializer import serialize_case_answer
from evaluation.validate_schema import validate_case_answer
from evaluation.check_integrity import check_case_integrity, get_entity_registry


def load_all_benchmark_cases(data_dir: str = ".") -> List[Dict[str, Any]]:
    """Loads all 20 cases from case_pack.csv in sorted order."""
    case_pack_path = os.path.join(data_dir, "case_pack.csv")
    if not os.path.exists(case_pack_path):
        raise FileNotFoundError(f"case_pack.csv not found at {case_pack_path}")

    cases = []
    with open(case_pack_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(dict(row))

    # Sort numerically by case_id suffix (HHG-001 to HHG-020)
    cases.sort(key=lambda c: int(c["case_id"].split("-")[-1]) if "-" in c["case_id"] else 0)
    return cases


def run_benchmark(
    backend: str = "tigergraph",
    provider: str = "gemini",
    case_filter: Optional[List[str]] = None,
    output_dir: str = "cases",
    report_path: str = "docs/full_benchmark_report.md"
) -> Dict[str, Any]:
    """
    Executes the full benchmark evaluation across specified cases.
    Enforces strict configuration guards, live backend verification, and audit logging.
    """
    t_start = time.time()
    os.makedirs(output_dir, exist_ok=True)
    registry = get_entity_registry()

    # 1. Initialize & Verify LLM Provider
    llm = get_llm_provider(provider_type=provider)
    is_real = getattr(llm, "is_real", False)
    llm_mode = "REAL" if is_real else "MOCK"
    provider_label = getattr(llm, "provider_name", "Mock")
    model_name = getattr(llm, "model_name", "default")

    if provider.lower() == "gemini" and not is_real:
        raise RuntimeError("Strict 'gemini' provider requested but got Mock provider. Set GEMINI_API_KEY in .env.")

    # 2. Initialize & Verify Graph Adapter
    adapter = GraphAdapter(backend=backend)
    actual_backend = getattr(adapter, "backend", backend).upper()
    actual_graph = getattr(adapter, "graph_name", "FraudNet")

    if backend.lower() == "tigergraph":
        if actual_backend != "TIGERGRAPH":
            raise RuntimeError(f"Backend verification failed: requested TIGERGRAPH but got '{actual_backend}'")
        if actual_graph != "FraudNet":
            raise RuntimeError(f"Graph verification failed: expected 'FraudNet' but got '{actual_graph}'")

    print("================================================================================")
    print("           TIGERGRAPH FRAUD INVESTIGATION AGENT: 20-CASE BENCHMARK             ")
    print("================================================================================")
    print(f"Backend:            {actual_backend}")
    print(f"Graph Database:     {actual_graph}")
    print(f"LLM Provider:       {provider_label} ({llm_mode})")
    print(f"LLM Model:          {model_name}")
    print(f"GraphRAG:           ENABLED")
    print(f"Timestamp:          {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("================================================================================\n")

    # 3. Load Benchmark Cases
    all_cases = load_all_benchmark_cases()
    if case_filter:
        cases_to_run = [c for c in all_cases if c["case_id"] in case_filter]
    else:
        cases_to_run = all_cases

    tools = InvestigationTools(adapter=adapter)
    workflow = InvestigationWorkflow(tools=tools, llm_provider=llm)

    results: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    # 4. Iterate Over Cases
    for idx, case_data in enumerate(cases_to_run, start=1):
        case_id = case_data["case_id"]
        print(f"[{idx}/{len(cases_to_run)}] Executing {case_id}...")
        t_case_start = time.time()

        try:
            state = workflow.run(case_data)
            case_elapsed_s = round(time.time() - t_case_start, 3)

            # Audit LLM Proposals vs Deterministic PolicyEngine Actions
            discrepancies = []
            for act in state.llm_proposed_actions:
                if act in ("BLOCK_CARD", "BLOCK_ALL_CARDS", "DECLINE_TRANSACTION", "FILE_REPORT"):
                    if act not in state.recommended_actions:
                        discrepancies.append(
                            f"LLM proposed '{act}' but PolicyEngine overruled it (statutory: {state.recommended_actions})"
                        )

            # Special Check for HHG-014
            hhg014_check = None
            if case_id == "HHG-014":
                block_card_in_final = "BLOCK_CARD" in state.recommended_actions
                block_card_in_llm = "BLOCK_CARD" in state.llm_proposed_actions
                hhg014_check = {
                    "block_card_in_final_policy": block_card_in_final,
                    "block_card_in_llm_proposal": block_card_in_llm,
                    "status": "Verified PolicyEngine Control" if block_card_in_final else "Investigation Discrepancy"
                }

            # Serialize to official schema
            answer = serialize_case_answer(state)

            # Run Validations
            schema_res = validate_case_answer(answer)
            integrity_errs = check_case_integrity(answer, registry=registry)

            is_valid = schema_res.is_valid and len(integrity_errs) == 0

            # Write Case Answer File
            out_file = os.path.join(output_dir, f"{case_id}.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(answer, f, indent=2)

            if not is_valid:
                fail_file = os.path.join(output_dir, f"{case_id}_failed.json")
                with open(fail_file, "w", encoding="utf-8") as f:
                    json.dump(answer, f, indent=2)
                failures.append({
                    "case_id": case_id,
                    "category": "VALIDATION",
                    "schema_errors": schema_res.errors,
                    "integrity_errors": integrity_errs
                })

            case_result = {
                "case_id": case_id,
                "trigger_type": case_data.get("trigger_type", ""),
                "verdict": answer["case"]["verdict"],
                "pattern": answer["case"]["pattern"],
                "fraud_probability": answer["case"]["fraud_probability"],
                "exposure_usd": answer["case"]["exposure_usd"],
                "sar_filed": answer["sar"]["file"],
                "final_actions": [a["action"] for a in answer["next_best_actions"]["final"]],
                "initial_assessment": state.initial_assessment,
                "final_assessment": state.final_assessment,
                "evidence_requests_count": len(state.evidence_requests),
                "stop_reason": state.stop_reason.value if state.stop_reason else "unknown",
                "tool_calls_count": len(state.tool_calls),
                "graph_written": state.written_to_graph,
                "graph_case_id": state.graph_case_id,
                "token_usage": state.token_usage,
                "latency_s": case_elapsed_s,
                "schema_valid": schema_res.is_valid,
                "integrity_valid": len(integrity_errs) == 0,
                "is_valid": is_valid,
                "policy_discrepancies": discrepancies,
                "hhg014_check": hhg014_check,
                "rag_context": state.rag_context or {}
            }
            results.append(case_result)
            print(f"    -> Status: {case_result['verdict'].upper()} | Pattern: {case_result['pattern']} | Exp: ${case_result['exposure_usd']} | Valid: {is_valid} ({case_elapsed_s}s)")

        except Exception as e:
            err_msg = str(e)
            print(f"    -> [ERROR] Failed on {case_id}: {err_msg}")
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "rate limit" in err_msg.lower():
                category = "RATE_LIMIT"
            elif "500" in err_msg or "Connection" in err_msg or "restpp" in err_msg:
                category = "INFRASTRUCTURE"
            else:
                category = "EXECUTION_EXCEPTION"

            failures.append({
                "case_id": case_id,
                "category": category,
                "error": err_msg
            })
            if category in ("RATE_LIMIT", "INFRASTRUCTURE"):
                print(f"    -> {category} encountered. Halting benchmark run cleanly.")
                break

    total_elapsed_s = round(time.time() - t_start, 2)

    # 5. Generate docs/full_benchmark_report.md
    generate_markdown_report(
        results=results,
        failures=failures,
        backend=actual_backend,
        graph_name=actual_graph,
        provider=provider_label,
        model=model_name,
        total_time_s=total_elapsed_s,
        report_path=report_path
    )

    return {
        "total_cases_attempted": len(results) + len(failures),
        "total_completed": len(results),
        "validation_success_count": sum(1 for r in results if r["is_valid"]),
        "failures_count": len(failures),
        "total_time_s": total_elapsed_s,
        "results": results,
        "failures": failures
    }


def generate_markdown_report(
    results: List[Dict[str, Any]],
    failures: List[Dict[str, Any]],
    backend: str,
    graph_name: str,
    provider: str,
    model: str,
    total_time_s: float,
    report_path: str
) -> None:
    """Renders the comprehensive benchmark report in markdown format."""
    total_completed = len(results)
    valid_count = sum(1 for r in results if r["is_valid"])
    latencies = [r["latency_s"] for r in results]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    median_latency = round(sorted(latencies)[len(latencies)//2], 2) if latencies else 0.0
    min_latency = min(latencies) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0

    total_tokens = sum(r["token_usage"].get("total_tokens", 0) for r in results)
    avg_tokens = round(total_tokens / total_completed, 1) if total_completed else 0.0
    total_graph_tools = sum(r["tool_calls_count"] for r in results)

    lines = [
        "# Comprehensive 20-Case Real Benchmark Evaluation Report",
        "",
        "## 1. Executive Summary & Configuration",
        "",
        f"- **Evaluation Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"- **Graph Database**: `{backend}` (Graph: `{graph_name}`)",
        f"- **Reasoning Provider**: `{provider}` (`{model}`)",
        f"- **GraphRAG Subsystem**: `ENABLED` (Authoritative policies + Graph Case Memory)",
        f"- **Cases Completed**: **{total_completed} / 20**",
        f"- **Schema & Integrity Validation Rate**: **{valid_count} / {total_completed} (100%)**" if total_completed == valid_count else f"- **Validation Pass Rate**: **{valid_count} / {total_completed}**",
        f"- **Total Benchmark Runtime**: **{total_time_s:.2f}s** (Avg: {avg_latency}s / case)",
        "",
        "---",
        "",
        "## 2. Benchmark Case Results Table",
        "",
        "| Case | Verdict | Pattern | Fraud Probability | Exposure | SAR | Final Actions | Evidence Requested | Tool Calls | Latency | Validation |",
        "|---|---|---|---|---|---|---|---|---|---|---|"
    ]

    for r in results:
        actions_str = ", ".join(r["final_actions"][:3])
        if len(r["final_actions"]) > 3:
            actions_str += f" (+{len(r['final_actions'])-3})"
        val_icon = "PASS" if r["is_valid"] else "FAIL"
        lines.append(
            f"| `{r['case_id']}` | **{r['verdict'].upper()}** | `{r['pattern']}` | {r['fraud_probability']:.2f} | ${r['exposure_usd']:,.2f} | {r['sar_filed']} | {actions_str} | {r['evidence_requests_count']} req | {r['tool_calls_count']} | {r['latency_s']:.2f}s | {val_icon} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Aggregate Engineering Metrics",
        "",
        f"- **Total Cases Attempted**: {total_completed + len(failures)}",
        f"- **Total Successfully Processed**: {total_completed}",
        f"- **Validation Success Count**: {valid_count}",
        f"- **Failures**: {len(failures)}",
        f"- **Latency Statistics**:",
        f"  - Average Latency: `{avg_latency}s`",
        f"  - Median Latency: `{median_latency}s`",
        f"  - Min Latency: `{min_latency}s`",
        f"  - Max Latency: `{max_latency}s`",
        f"- **Token & LLM Usage**:",
        f"  - Total Tokens Tracked: `{total_tokens:,}`",
        f"  - Average Tokens / Case: `{avg_tokens:,}`",
        f"- **Graph Operations**:",
        f"  - Total Graph Tool Invocations: `{total_graph_tools}`",
        f"  - Average Graph Calls / Case: `{total_graph_tools / max(total_completed, 1):.1f}`",
        "",
        "---",
        "",
        "## 4. Policy Engine Authority & Statutory Control Audit",
        "",
        "The deterministic `PolicyEngine` enforces Rules R1 through R10 over all LLM proposals. Discrepancies and overrides are audited below:",
        ""
    ])

    discrepancy_count = 0
    for r in results:
        if r.get("policy_discrepancies"):
            discrepancy_count += 1
            lines.append(f"### Case `{r['case_id']}` Policy Enforcement")
            for disc in r["policy_discrepancies"]:
                lines.append(f"- **Policy Override**: {disc}")
            lines.append(f"- **Final Approved Statutory Actions**: `{r['final_actions']}`")
            lines.append("")

    if discrepancy_count == 0:
        lines.append("> [!NOTE]\n> All LLM reasoning proposals fully aligned with statutory policy rules or non-conforming suggestions were safely governed by PolicyEngine authority.\n")

    # HHG-014 Audit
    hhg014 = next((r for r in results if r["case_id"] == "HHG-014"), None)
    if hhg014 and hhg014.get("hhg014_check"):
        check = hhg014["hhg014_check"]
        lines.extend([
            "### HHG-014 Special Inspection (Syndicate Mobile Proxy)",
            f"- **`BLOCK_CARD` in final PolicyEngine actions**: `{check['block_card_in_final_policy']}`",
            f"- **`BLOCK_CARD` in LLM proposals**: `{check['block_card_in_llm_proposal']}`",
            f"- **Compliance Status**: **{check['status']}**",
            ""
        ])

    lines.extend([
        "---",
        "",
        "## 5. Failure Triage & Classification",
        ""
    ])

    if failures:
        lines.append("| Case | Category | Details |")
        lines.append("|---|---|---|")
        for f in failures:
            details = f.get("error") or str(f.get("schema_errors"))
            lines.append(f"| `{f['case_id']}` | **{f['category']}** | `{details[:120]}` |")
        lines.append("")
    else:
        lines.append("> [!TIP]\n> Zero failures recorded. All attempted cases completed end-to-end.\n")

    lines.extend([
        "---",
        "",
        "## 6. Case-by-Case Factual Investigation Summaries",
        ""
    ])

    for r in results:
        cid = r["case_id"]
        init_ass = r.get("initial_assessment") or {}
        fin_ass = r.get("final_assessment") or {}
        rag = r.get("rag_context") or {}
        pol_list = ", ".join(rag.get("retrieved_policies", [])) or "None"
        case_mem = rag.get("case_memory_count", 0)

        lines.extend([
            f"### `{cid}` ({r['trigger_type']})",
            f"- **Verdict**: `{r['verdict']}` | **Pattern**: `{r['pattern']}` | **Fraud Probability**: `{r['fraud_probability']:.2f}`",
            f"- **Exposure**: `${r['exposure_usd']:,.2f}` | **SAR Filed**: `{r['sar_filed']}`",
            f"- **Initial Assessment**: Verdict `{init_ass.get('verdict')}`, Pattern `{init_ass.get('fraud_pattern')}`",
            f"- **Final Assessment**: Verdict `{fin_ass.get('verdict') or r['verdict']}`, Pattern `{fin_ass.get('fraud_pattern') or r['pattern']}`",
            f"- **GraphRAG Citations**: Retrieved Policies: `[{pol_list}]`, Historical Precedents: `{case_mem}`",
            f"- **Final Actions**: `{r['final_actions']}`",
            f"- **Stop Reason**: `{r['stop_reason']}`",
            f"- **Graph Persistence**: Written=`{r['graph_written']}` (Graph Case ID: `{r['graph_case_id']}`)",
            ""
        ])

    report_content = "\n".join(lines)
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"\n[✓] Benchmark Report successfully written to: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="TigerGraph Fraud Agent: 20-Case Real Benchmark Evaluation Runner")
    parser.add_argument("--backend", default="tigergraph", choices=["tigergraph", "in_memory"], help="Graph execution backend")
    parser.add_argument("--provider", default="gemini", choices=["gemini", "mock", "openai", "mistral"], help="LLM reasoning provider")
    parser.add_argument("--cases", nargs="*", help="Optional list of specific case IDs (e.g. HHG-001 HHG-014)")
    parser.add_argument("--output-dir", default="cases", help="Directory where case answer JSONs are written")
    parser.add_argument("--report-path", default="docs/full_benchmark_report.md", help="Path for benchmark markdown report")

    args = parser.parse_args()

    run_benchmark(
        backend=args.backend,
        provider=args.provider,
        case_filter=args.cases,
        output_dir=args.output_dir,
        report_path=args.report_path
    )


if __name__ == "__main__":
    main()
