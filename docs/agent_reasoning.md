# Agent Reasoning, LLM Abstraction, and Decision Boundary Architecture
## Phase 3C Technical Reference

---

### 1. Architectural Overview

Phase 3C establishes a grounded, provider-independent LLM investigation agent for the TigerGraph × Hacker House Goa 2026 fraud detection platform.

The agent pairs **LLM inductive reasoning** (forming hypotheses, identifying multi-card topologies, recognizing behavioral routines, and generating customer-facing inquiries) with **strict deterministic guardrails** (dataset entity integrity checks, context-size control, and the authoritative Phase 1 Policy Engine).

```
                     ┌────────────────────────────────────────────────────────┐
                     │              Agent Investigation Workflow              │
                     └──────────────────────────┬─────────────────────────────┘
                                                │
       ┌────────────────────────────────────────┼────────────────────────────────────────┐
       ▼                                        ▼                                        ▼
┌──────────────┐                       ┌──────────────────┐                     ┌─────────────────┐
│ Graph Data   │                       │   LLM Reasoner   │                     │  Deterministic  │
│ & MCP Tools  │                       │  (Provider Ind.) │                     │  Policy Engine  │
└──────┬───────┘                       └────────┬─────────┘                     └────────┬────────┘
       │                                        │                                        │
  Graph Facts &                            Hypotheses,                             Strict Rules,
 Analytical Summaries                   Grounded Inferences,                     Statutory Routes,
  (Capped Tokens)                         Evidence Requests                     Actions & SAR Filing
       │                                        │                                        │
       └───────────────────┬────────────────────┴────────────────────────────────────────┘
                           ▼
              ┌────────────────────────┐
              │ GroundingValidator &   │ ◄── Rejects hallucinated IDs & verifies exposure
              │   Answer Serializer    │
              └────────────┬───────────┘
                           ▼
              ┌────────────────────────┐
              │ Benchmark Output JSON  │ ◄── Validated by evaluation/validate_schema.py
              └────────────────────────┘
```

---

### 2. LLM Provider Abstraction (`src/agent/llm/`)

The LLM abstraction ensures zero vendor lock-in and allows the test suite and evaluation runner to execute without external network calls or API keys.

#### 2.1 Core Contracts (`src/agent/llm/base.py`)
- **`BaseLLMProvider`**: Abstract interface defining `generate()` and `generate_structured()`.
- **`TokenUsage`**: Tracks `prompt_tokens`, `completion_tokens`, and `total_tokens` accumulated throughout the case lifecycle.
- **`LLMResponse`**: Encapsulates model output, parsed structured schemas, tool calls, latency, and token consumption.
- **`redact_credentials()`**: Regex scrubber that redacts API keys (`sk-...`), bearer tokens, and passwords from logs and prompts.

#### 2.2 Provider Implementations
- **`MockLLMProvider` (`src/agent/llm/mock.py`)**:
  - Deterministic reasoner designed for offline development and CI/CD.
  - Implements realistic chain-of-thought traces for `HHG-001` (routine weekend spending cadence) and `HHG-014` (anonymous proxy mobile device syndicate).
  - Includes robust heuristic fallback for arbitrary benchmark cases.
- **`OpenAIProvider` (`src/agent/llm/openai_provider.py`)**:
  - OpenAI-compatible REST client built on Python standard library `urllib` (no heavy third-party dependencies).
  - Supports OpenAI, DeepSeek, local Ollama, or Gemini/Anthropic reverse proxies.
  - Incorporates automatic JSON extraction, syntax repair, and correction retry loops.
- **`get_llm_provider()` (`src/agent/llm/factory.py`)**:
  - Factory inspecting `LLM_PROVIDER` and `OPENAI_API_KEY`.
  - Automatically defaults to `MockLLMProvider` if credentials are not configured.

---

### 3. Structured Reasoning Schemas (`src/agent/llm/schemas.py`)

Rather than unconstrained free text, the LLM produces typed Pydantic structures at each reasoning step:

#### 3.1 `LLMReasoningStep`
- `thought`: Detailed investigative synthesis and deduction.
- `observations`: Key facts extracted from database query results.
- `hypotheses`: Active fraud vs. benign explanations being tested.
- `findings`: Array of `StructuredFinding` items citing `claim`, `source` (`graph`, `document`, `customer`, `external`), `ref`, and `entity_ids`.
- `tentative_verdict`: `fraud`, `legitimate`, or `uncertain`.
- `uncertainty`: `low`, `medium`, or `high`.
- `proposed_tool`: Optional next tool call to execute.
- `evidence_request`: Optional inquiry to raise if customer validation is needed.

#### 3.2 `LLMFinalSynthesis`
- Comprehensive case summary, final verdict, calibrated fraud probability, pattern typology, exposure calculation, connected card list, prior case precedents, and FinCEN-compliant SAR narrative.

---

### 4. Strict Evidence Grounding (`src/agent/grounding.py`)

A primary vulnerability in LLM fraud investigations is hallucinating entity IDs or exaggerating exposure amounts.

The `GroundingValidator` guarantees that:
1. **Transaction IDs**: Must exist in `transactions.csv` or `case_pack.csv`. Any candidate transaction not present is rejected.
2. **Card IDs & Customer IDs**: Verified against raw dataset registries.
3. **Historical Case IDs**: Must match known closed cases in `closed_cases_history.csv`.
4. **Device Profiles**: Must match device fingerprints in `identity.csv`.
5. **Exposure Calculation**: Computed strictly as $\sum |TransactionAmt|$ of verified affected transactions. Models cannot invent or round exposure figures arbitrarily.
6. **Evidence Sanitization**: Automatically scrubs fabricated entity IDs from evidence objects before serialization.

---

### 5. Deterministic Policy Boundary & Override Auditing

The system enforces a strict boundary between LLM inference and statutory policy enforcement:

| Domain | Entity Responsible | Authority |
|---|---|---|
| **Hypothesis Generation** | LLM Reasoner | Informational |
| **Graph Pattern Recognition** | LLM + GSQL Algorithms | Informational / Investigative |
| **Uncertainty Calibration** | LLM Reasoner | Informational |
| **Policy Rules Triggered** | `PolicyEngine` (Deterministic) | **Authoritative** |
| **Recommended Actions** | `PolicyEngine` (Deterministic) | **Authoritative** |
| **Approval Routing (Auto / L1 / L2)** | `PolicyEngine` (Deterministic) | **Authoritative** |
| **Mandatory SAR Filing** | `PolicyEngine` (Deterministic) | **Authoritative** |

#### Policy Override Auditing
If an LLM recommends an unapproved action (e.g. suggesting an immediate punitive `BLOCK_CARD` on a legitimate customer under Rule R1, or failing to request `FILE_REPORT` on a shared infrastructure syndicate under Rule R6), the `PolicyEngine` overrules the proposal.

The workflow detects this discrepancy and records a `policy_override` event into the immutable audit timeline:
```json
{
  "stage": "policy_override",
  "tool_used": "policy:PolicyEngine.evaluate",
  "evidence_discovered": "Deterministic PolicyEngine overrode LLM suggestions: LLM proposed ['BLOCK_CARD']; Policy engine enforced ['CLOSE_NO_FRAUD']",
  "result": "POLICY_OVERRODE_LLM",
  "state_change": "actions enforced -> ['CLOSE_NO_FRAUD']"
}
```

---

### 6. Evidence Request Loop and Reassessment

When an investigation encounters medium or high uncertainty, the workflow triggers the **Evidence Loop** (`CaseStatus.EVIDENCE_LOOP`):
1. **Initial Assessment**: Preserved in `state.initial_assessment`.
2. **Evidence Request**: Formulates a structured inquiry (`type = "customer_validation"`).
3. **Simulated Response**: Simulates customer confirmation or denial.
4. **Reassessment**: LLM reassesses the case in light of the cardholder's response, transitioning the status to `CaseStatus.REASSESSING`.
5. **Final Assessment**: Preserved in `state.final_assessment`.
6. **Audit Diff**: In `next_best_actions.what_changed`, the serializer documents how the customer's response modified the action set from initial to final.

---

### 7. Step Guard & Terminal Stop Conditions

To protect against infinite reasoning cycles and excessive token consumption:
- **Maximum Step Guard**: `max_steps` (default 10) sets an upper bound on workflow transitions. If exceeded, the agent halts further tool execution, logs `MAX_STEPS_REACHED`, and routes immediately to policy evaluation.
- **Terminal Criteria**: Every case must terminate with an explicit `StopReason`:
  - `sufficient_evidence`
  - `customer_confirmed`
  - `customer_denied`
  - `no_additional_evidence_available`
  - `policy_action_selected`
  - `analyst_escalation`

---

### 8. Benchmark Evaluation & Verification

#### CLI Execution Hook
```bash
# Run HHG-001 (Routine Travel Spend)
python evaluation/run_single_case.py --case HHG-001 --backend in_memory

# Run HHG-014 (Coordinated Mobile Device Proxy Syndicate)
python evaluation/run_single_case.py --case HHG-014 --backend in_memory
```

#### Results
- **HHG-001**:
  - Verdict: `legitimate` | Pattern: `none` | Exposure: `$0.00`
  - Customer Verification: Confirmed routine weekend spend.
  - Final Action: `CLOSE_NO_FRAUD` (route: `auto`).
  - Schema Validation: **PASSED** | Entity Integrity: **PASSED**.
- **HHG-014**:
  - Verdict: `fraud` | Pattern: `undocumented` | Exposure: `$74.96`
  - Graph Discovery: Device `SM-G935F` behind anonymous proxy linked across 34 cards.
  - SAR Filing: `sar.file = true` with comprehensive FinCEN narrative.
  - Final Actions: `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`, `MONITOR_CONNECTED_CARDS`.
  - Schema Validation: **PASSED** | Entity Integrity: **PASSED**.

#### Test Suite Status
All **89/89 tests** pass:
- `tests/test_agent_reasoning.py`: 14 passed
- `tests/test_agent_foundation.py`: 18 passed
- `tests/test_mcp_integration.py`: 8 passed
- `tests/test_graph_adapter.py`: 11 passed
- `tests/test_policy_rules.py`: 10 passed
- `tests/test_schema_validation.py`: 8 passed
- `tests/test_exposure.py`: 7 passed
- `tests/test_approvals.py`: 5 passed
- `tests/test_hhg001_regression.py`: 4 passed
- `tests/test_integrity.py`: 4 passed
