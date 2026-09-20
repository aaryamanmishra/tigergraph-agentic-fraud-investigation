# System Requirements & Specification
## TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation

### 1. Executive Summary & Core Objective

The objective of this project is to build an autonomous, explainable, graph-native AI Fraud Investigation Agent powered by **TigerGraph**, **GSQL**, **TigerGraph MCP**, and **GraphRAG**. 

Unlike generic conversational chatbots, this system operates as an **institutional-grade fraud investigation workstation**. It is designed to evaluate suspicious activity triggers across credit/debit card transactions, traverse multi-hop entity relationships in TigerGraph, retrieve relevant closed-case memories, calibrate fraud probability and uncertainty, execute controlled evidence-gathering loops, apply a deterministic Fraud Policy (Rules R1–R10) with exact approval routing (`auto`, `L1`, `L2`), generate FinCEN-compliant Suspicious Activity Reports (SARs) when mandated, persist findings back to the graph for long-term organizational memory, and output benchmark-compliant case records for 20 exam cases (`case_pack.csv`).

---

### 2. Functional Requirements (FR)

#### FR-1: Trigger Ingestion & Case Initialization
- The system must ingest alerts from `case_pack.csv` across three distinct trigger types:
  1. `risk_score`: High-scoring transactions from the bank's real-time detection model (e.g. scores between 0.50 and 0.90+).
  2. `customer_report`: Inbound messages from cardholders claiming unauthorized charges or billing discrepancies.
  3. `analyst_request`: Directives from human analysts instructing the investigation of specific anomalous patterns (e.g. repeated device profiles across cards).
- The agent must extract the flagged transaction ID, customer ID, card ID, trigger timestamp, and initial risk signal without treating the trigger as a final verdict.

#### FR-2: Graph-Native Multi-Hop Investigation
- The system must query TigerGraph via GSQL and the TigerGraph MCP interface to retrieve:
  1. **Customer & Card Topology**: All cards owned by the customer (`Customer → OWNS → Card`), card network, card type, and status.
  2. **Transaction Sequence**: Full transaction history on the card ordered chronologically (`Card → MADE → Transaction`), identifying velocity, amount deviations, product codes (`ProductCD`), and `NEXT` transaction transitions.
  3. **Device & Identity Footprint**: For online transactions, retrieve device profiles (`Transaction → FROM_DEVICE → DeviceProfile`), OS, browser, screen resolution, `id_15` (device New vs. Found), `id_23` (proxy status), and match flags (`id_34`, `M1`–`M9`).
  4. **Geographic & Billing Consistency**: Card billing region (`Transaction → BILLED_IN → BillingRegion`) and country codes (`addr1`, `addr2`) compared against the customer's historical baseline.
  5. **Network / Co-occurrence Links**: Discover shared device profiles, shared recipient emails (`R_emaildomain`), or shared billing regions across distinct cards and customers to identify coordinated fraud rings or compromised infrastructure.

#### FR-3: Case Memory & GraphRAG Retrieval
- The system must leverage the 5,565 historical closed cases (`closed_cases_history.csv`) as prior organizational memory.
- Using GraphRAG (graph-linked case traversal + semantic/vector retrieval over analyst notes, typologies, and regulatory docs), the system must retrieve similar past cases based on:
  - Shared device profiles or billing regions.
  - Structural transaction sequences (e.g. rapid small authorizations).
  - Customer historical outcomes (prior cleared false alarms vs confirmed compromises).
- Identified case IDs must be recorded in `case.similar_prior_cases` (e.g. `["CC-0141", "CC-2649"]`).

#### FR-4: Pattern Recognition (Documented & Undocumented)
- The agent must evaluate the evidence against the five documented bank typologies:
  1. `card_testing`: 3+ small online authorizations (<$5) in short succession followed by a larger purchase (Policy R5).
  2. `card_not_present_fraud`: Online purchases inconsistent with history, typically in 2–4 transaction bursts within 48 hours.
  3. `card_not_present_new_device`: CNP purchases from an identity record marked `New` or behind an anonymous proxy.
  4. `out_of_region_use`: Card-present purchases in an unfamiliar billing region while domestic activity persists.
  5. `account_takeover`: Inconsistent mixed-channel activity with device/credential mismatch flags.
- **Undocumented Abuse Recognition**: If activity does not fit the 5 documented patterns but exhibits repeated or coordinated abuse (e.g. ring fraud across multiple accounts, proxy-based distributed shopping, or structuring below thresholds), the agent must classify the pattern as `undocumented`, document a concise explanation in `pattern_description`, and cite Policy R9.
- If no fraud is identified, the pattern must be designated as `none`.

#### FR-5: Calibrated Probability & Uncertainty Estimation
- The agent must estimate `fraud_probability` as a continuous score between `0.0` and `1.0`.
- The estimate must be decoupled from the raw `risk_score`:
  - Legitimate cases with high risk scores (e.g. recurring weekly spend or verified travel) must be calibrated down (e.g. $\le 0.15$).
  - Confirmed compromises with low initial risk scores must be calibrated up based on graph evidence.
- Verdict must be assigned:
  - `fraud`: High probability ($\ge 0.70$ or confirmed denial/testing sequence).
  - `legitimate`: Low probability ($\le 0.20$ or confirmed routine behavior).
  - `uncertain`: Ambiguous signals with unresolved verification or conflicting evidence.

#### FR-6: Controlled Evidence-Request Loop
- When an investigation has unresolved uncertainty (e.g. single weak signal under R1, or ambiguous online transaction), the agent must not rush to an unsupported block.
- It must generate an evidence request:
  - `customer_validation`: Inquire whether the cardholder made the transaction.
  - `step_up_auth`: Challenge the transaction with MFA/passcode.
  - `analyst_info`: Request deeper device/network review.
- The request and assumed response must be logged in `evidence_requests` with `type`, `asked_after_step`, and `assumed_response`.

#### FR-7: Dynamic Next-Best-Action Evolution
- The system must produce recommendations across two explicit stages:
  1. `initial`: Actions recommended **before** requested evidence is received.
  2. `final`: Actions recommended **after** the simulated response is processed.
- The field `what_changed` must explain the delta between initial and final recommendations.

#### FR-8: Deterministic Policy Engine & Approval Routing
- LLM reasoning proposes actions; a deterministic policy engine strictly validates and enforces rules R1 through R10.
- All actions must match the official 14 policy actions exactly.
- Each action must be assigned its statutory approval route:
  - `auto`: Executable immediately by the agent (`ALLOW_TRANSACTION`, `MONITOR_CARD`, `MONITOR_CONNECTED_CARDS`, `WARN_CUSTOMER`, `VERIFY_WITH_CUSTOMER`, `STEP_UP_AUTH`, `GENERATE_REPORT`, `CREATE_CASE`, `ESCALATE_TO_ANALYST`, `CLOSE_NO_FRAUD`).
  - `L1`: Requires Team Lead approval (`DECLINE_TRANSACTION`, `BLOCK_CARD` when exposure $\le \$2,500$).
  - `L2`: Requires Fraud Manager approval (`BLOCK_CARD` when exposure $> \$2,500$, `BLOCK_ALL_CARDS` always, `FILE_REPORT` always).

#### FR-9: Suspicious Activity Report (SAR) Generation
- Evaluated strictly against Section 3a of the Fraud Policy:
  - File SAR (`sar.file = true`) only when fraud is confirmed/strongly suspected **AND** at least one condition holds:
    a) Exposure exceeds $\$1,000$, OR
    b) Activity connects to a shared device profile, shared region cluster, or another card's fraud, OR
    c) Pattern is coordinated/undocumented (Rule R9).
- If filed, generate a complete FinCEN-standard narrative addressing **who**, **what**, **when**, **where**, **how**, and **why**, along with `subjects`, `total_amount_usd`, and `activity_dates`.
- If not filed, `sar.file = false`, `narrative = ""`, `subjects = []`, `total_amount_usd = 0`, `activity_dates = []`.

#### FR-10: Graph Persistence & Case Memory
- When a case is investigated and closed/progressed, the system must write the case node (`InvestigatedCase` / `Case`) and associated edges (`INVOLVES`, `ON_CARD`, `CONNECTED_TO`) into TigerGraph.
- The case record must reflect `written_to_graph: true` and record the generated `graph_case_id`.

#### FR-11: Standardized Answer File Generation
- For each of the 20 cases in `case_pack.csv`, output exactly one valid JSON file named `<case_id>.json` in `cases/`.
- Every file must validate against the strict JSON Schema specified in `docs/answer_schema.md`.

#### FR-12: Benchmark Evaluation Suite
- Provide an automated test and evaluation harness in `evaluation/` to validate schema conformance, entity ID presence, policy routing correctness, and before/after action evolution across all 20 cases.

---

### 3. Non-Functional Requirements (NFR)

- **Grounding & Zero Hallucination**: Every transaction ID, customer ID, card ID, and device string referenced in any field must exist in the real dataset files. Hallucinating synthetic IDs is strictly prohibited.
- **Evidence-First Explainability**: Every conclusion in `case.summary`, `case.evidence`, and `sar.narrative` must cite exact query sources, entity IDs, and policy rule references.
- **Policy Determinism**: The system must enforce mathematical boundaries on exposure ($\$500$, $\$1,000$, $\$2,500$) and card-level guardrails (Rule R10: never `BLOCK_ALL_CARDS` unless 2+ cards confirmed compromised or credentials compromised).
- **Execution Speed & Efficiency**: The investigation pipeline should execute synchronously or asynchronously with minimal latency ($\le 30$ seconds per case) and track execution metadata (`tool_calls`, `tokens`, `latency_s`).
- **Reproducibility**: Repeated execution over the same benchmark cases with deterministic seeds must yield consistent recommendations, policy decisions, and approval routes.

---

### 4. Constraints & Prohibitions

1. **No External Outcome Recovery**: Using the public Kaggle/IEEE-CIS dataset to look up disguised IDs, amounts, or labels is strictly prohibited and results in immediate disqualification.
2. **Immutable Raw Data**: Raw CSV files (`transactions.csv`, `identity.csv`, `closed_cases_history.csv`, `case_pack.csv`) must remain read-only and unmodified.
3. **No Unsanctioned Actions**: The agent must never invent custom action names or routes outside the 14 policy actions and 3 approval routes defined in the specification.
