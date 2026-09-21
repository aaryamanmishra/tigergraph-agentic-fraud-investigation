# Comprehensive 20-Case Real Benchmark Evaluation Report

## 1. Executive Summary & Configuration

- **Evaluation Date**: 2026-09-20 19:11:40 UTC
- **Graph Database**: `TIGERGRAPH` (Graph: `FraudNet`)
- **Reasoning Provider**: `openai` (`openai/gpt-oss-20b`)
- **GraphRAG Subsystem**: `ENABLED` (Authoritative policies + Graph Case Memory)
- **Cases Completed**: **3 / 20**
- **Schema & Integrity Validation Rate**: **3 / 3 (100%)**
- **Total Benchmark Runtime**: **32.20s** (Avg: 6.39s / case)

---

## 2. Benchmark Case Results Table

| Case | Verdict | Pattern | Fraud Probability | Exposure | SAR | Final Actions | Evidence Requested | Tool Calls | Latency | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| `HHG-002` | **FRAUD** | `out_of_region_use` | 0.99 | $292.36 | False | BLOCK_CARD, CREATE_CASE | 1 req | 5 | 8.64s | PASS |
| `HHG-003` | **FRAUD** | `undocumented` | 0.90 | $49.00 | False | CREATE_CASE | 0 req | 5 | 5.49s | PASS |
| `HHG-004` | **FRAUD** | `undocumented` | 0.90 | $128.33 | False | CREATE_CASE | 0 req | 6 | 5.03s | PASS |

---

## 3. Aggregate Engineering Metrics

- **Total Cases Attempted**: 3
- **Total Successfully Processed**: 3
- **Validation Success Count**: 3
- **Failures**: 0
- **Latency Statistics**:
  - Average Latency: `6.39s`
  - Median Latency: `5.49s`
  - Min Latency: `5.033s`
  - Max Latency: `8.636s`
- **Token & LLM Usage**:
  - Total Tokens Tracked: `800`
  - Average Tokens / Case: `266.7`
- **Graph Operations**:
  - Total Graph Tool Invocations: `16`
  - Average Graph Calls / Case: `5.3`

---

## 4. Policy Engine Authority & Statutory Control Audit

The deterministic `PolicyEngine` enforces Rules R1 through R10 over all LLM proposals. Discrepancies and overrides are audited below:

> [!NOTE]
> All LLM reasoning proposals fully aligned with statutory policy rules or non-conforming suggestions were safely governed by PolicyEngine authority.

---

## 5. Failure Triage & Classification

> [!TIP]
> Zero failures recorded. All attempted cases completed end-to-end.

---

## 6. Case-by-Case Factual Investigation Summaries

### `HHG-002` (risk_score)
- **Verdict**: `fraud` | **Pattern**: `out_of_region_use` | **Fraud Probability**: `0.99`
- **Exposure**: `$292.36` | **SAR Filed**: `False`
- **Initial Assessment**: Verdict `fraud`, Pattern `out_of_region_use`
- **Final Assessment**: Verdict `fraud`, Pattern `out_of_region_use`
- **GraphRAG Citations**: Retrieved Policies: `[POLICY-NEXT-BEST-ACTION, POLICY-ACTIONS, POLICY-R6]`, Historical Precedents: `1`
- **Final Actions**: `['BLOCK_CARD', 'CREATE_CASE']`
- **Stop Reason**: `customer_denied`
- **Graph Persistence**: Written=`True` (Graph Case ID: `HHG-002`)

### `HHG-003` (customer_report)
- **Verdict**: `fraud` | **Pattern**: `undocumented` | **Fraud Probability**: `0.90`
- **Exposure**: `$49.00` | **SAR Filed**: `False`
- **Initial Assessment**: Verdict `fraud`, Pattern `unauthorized_transaction`
- **Final Assessment**: Verdict `fraud`, Pattern `undocumented`
- **GraphRAG Citations**: Retrieved Policies: `[POLICY-R2, POLICY-ACTIONS, POLICY-R5]`, Historical Precedents: `5`
- **Final Actions**: `['CREATE_CASE']`
- **Stop Reason**: `sufficient_evidence`
- **Graph Persistence**: Written=`True` (Graph Case ID: `HHG-003`)

### `HHG-004` (customer_report)
- **Verdict**: `fraud` | **Pattern**: `undocumented` | **Fraud Probability**: `0.90`
- **Exposure**: `$128.33` | **SAR Filed**: `False`
- **Initial Assessment**: Verdict `fraud`, Pattern `unauthorized_transaction`
- **Final Assessment**: Verdict `fraud`, Pattern `undocumented`
- **GraphRAG Citations**: Retrieved Policies: `[POLICY-R2, POLICY-ACTIONS, POLICY-R5]`, Historical Precedents: `0`
- **Final Actions**: `['CREATE_CASE']`
- **Stop Reason**: `sufficient_evidence`
- **Graph Persistence**: Written=`True` (Graph Case ID: `HHG-004`)
