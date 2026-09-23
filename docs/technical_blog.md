# FraudNet: Building an Autonomous, Graph-Native Fraud Investigation Agent with TigerGraph, MCP, and GraphRAG

*Hacker House Goa 2026 — TigerGraph Agentic Fraud Investigation Challenge*

---

## 1. The Problem: Why Risk Scores Are Not Fraud Verdicts

Traditional fraud management pipelines in modern financial institutions typically end at a score:

> *"Transaction 3514030 has a risk score of 0.61."*

When an automated model flags a high score, what happens next? In most organizations, the alert is dumped into a triage queue where human analysts spend 20 to 45 minutes manually pivoting across disparate systems:
- Querying card management databases to inspect recent authorizations, velocity, and decline counts.
- Checking transaction devices, IP addresses, proxy headers, and user-agent strings.
- Searching case management software for past fraud reports or customer travel notices.
- Weighing institutional policy: Does this meet statutory thresholds for Suspicious Activity Report (SAR) filing? Does the customer agreement require customer step-up verification before blocking cards? What level of executive approval is needed?

This manual triage workflow creates a massive operational bottleneck. Worse, naive attempts to automate this with generic Large Language Model (LLM) agents fail because:
1. **Relational blindness:** Relational databases struggle with multi-hop traversals (e.g., discovering that 34 separate cards share a single device fingerprint).
2. **Hallucination & lack of grounding:** Unconstrained LLMs invent card numbers, hallucinate transaction timestamps, or misunderstand strict regulatory rules.
3. **Black-box decisions:** Compliance teams cannot audit "vibes-based" LLM assessments; they require deterministic, policy-governed audit trails.

**FraudNet** was designed to solve this. Instead of treating a risk score as a final judgment, FraudNet treats it as an **investigation trigger**. From that single signal, the agent gathers multi-hop graph evidence, assesses residual uncertainty, runs controlled evidence loops, enforces deterministic bank policies, and writes closed cases back into the graph as organizational memory.

---

## 2. What We Built: The FraudNet Architecture

FraudNet is an institutional-grade fraud investigation workstation built around **TigerGraph**, **TigerGraph MCP**, **GraphRAG**, and **Deterministic Policy Engines**.

```text
Case Trigger (case_pack.csv: risk_score / analyst_request / customer_report)
    │
    ▼
Investigation Workflow (src/agent/workflow.py — 12-Stage State Machine)
    │
    ├──▶ TigerGraph / FraudNet Graph (via official tigergraph-mcp v1.0.3)
    │       ├── get_transaction_context
    │       ├── get_card_history
    │       ├── get_customer_history
    │       ├── get_connected_cards
    │       ├── get_device_neighbors
    │       ├── get_transaction_chain
    │       ├── get_similar_closed_cases
    │       ├── detect_card_testing
    │       └── write_case
    │
    ├──▶ GraphRAG Engine (src/rag/)
    │       ├── Policy Documents (Rules R1–R10, statutory SAR triggers)
    │       ├── Fraud Typology Library (5 documented typologies + undocumented abuse)
    │       └── Case Memory Index (5,565 historical closed cases)
    │
    ├──▶ LLM Reasoning Layer (Groq `openai/gpt-oss-20b`)
    │       ├── Structured Evidence Synthesis (Pydantic Schemas)
    │       ├── Continuous Fraud Probability Calibration [0.0 – 1.0]
    │       └── Uncertainty Evaluation
    │
    ├──▶ Controlled Evidence-Request Loop (when uncertainty is unresolved)
    │       └── Simulated Customer Inquiries / Additional Graph Searches
    │
    ├──▶ Deterministic PolicyEngine (src/policy/engine.py)
    │       ├── Statutory Rule Enforcement (R1–R10)
    │       ├── Enforced Approval Routing (AUTO / L1 / L2)
    │       ├── Exposure Calculation
    │       └── Mandatory FinCEN SAR Filing
    │
    ├──▶ Grounding & Schema Validation
    │       ├── 631,219-Entity Registry Cross-Validation
    │       └── Strict Output Schema & Invariant Enforcement
    │
    └──▶ TigerGraph Writeback (Case Memory for Future Investigations)
```

---

## 3. Deep Dive into Core Technologies

### 3.1 TigerGraph & GSQL Graph Analytics
The foundation of FraudNet is a live TigerGraph Cloud instance running the `FraudNet` graph schema. In financial fraud, relationships are the primary signal. Relational SQL queries requiring 4-way or 5-way joins across millions of transactions either time out or place crippling loads on transactional databases.

TigerGraph handles complex topological queries in milliseconds:
- **Card Topology:** Traversing `Customer → OWNS → Card → MADE → Transaction`.
- **Infrastructure Clustering:** Traversing `Transaction → FROM_DEVICE → DeviceProfile ← FROM_DEVICE ← Transaction ← MADE ← Card`.
- **Card Testing Sequences:** Evaluating rapid sub-$5 micro-authorizations across tight temporal windows using native GSQL accumulator semantics (`detect_card_testing`).

### 3.2 TigerGraph MCP (Model Context Protocol)
Rather than allowing an LLM to generate arbitrary, error-prone GSQL queries, FraudNet connects to the official `tigergraph-mcp` package (v1.0.3). 

The MCP interface exposes 9 typed, parameterized investigation tools. This guarantees:
1. **Safety:** LLMs cannot execute arbitrary mutations or drop graph schemas.
2. **Context Window Efficiency:** Raw graph vertices are summarized into concise, structured responses, preventing context bloat.
3. **Security:** Connection credentials and bearer tokens are isolated inside the MCP adapter layer and redacted from execution logs.

### 3.3 GraphRAG: Policy, Typology, and Case Memory Retrieval
Context retrieval in FraudNet is graph-aware. The GraphRAG module (`src/rag/`) bridges unstructured knowledge with structured graph memory across three distinct collections:
1. **Fraud Policies:** Bank operating policies covering Rules R1 through R10, approval thresholds ($1,000 / $5,000 limits), and regulatory escalation triggers.
2. **Typologies:** Institutional playbooks for documented patterns (`card_testing`, `card_not_present_fraud`, `card_not_present_new_device`, `out_of_region_use`, `account_takeover`) and guidance for undocumented abuse.
3. **Prior Case Memory:** 5,565 historical closed investigations (`closed_cases_history.csv`).

Every retrieved chunk is tagged with its provenance (`policy`, `typology`, or `case_memory`) before being passed to the reasoning layer.

### 3.4 The 12-Stage Agentic Workflow
The investigation agent is implemented as a deterministic state machine (`src/agent/workflow.py` and `src/agent/nodes.py`) consisting of 12 discrete stages:
1. `load_case`: Ingests trigger payload from `case_pack.csv`.
2. `investigate_transaction`: Retrieves full transaction context and risk scores.
3. `investigate_relationships`: Pulls customer history, card history, and device neighbors.
4. `retrieve_prior_cases`: Traverses historical closed cases with shared attributes.
5. `assess_evidence`: Prompts the LLM to synthesize evidence into structured findings.
6. `assess_uncertainty`: Measures residual ambiguity and determines if verification is required.
7. `request_evidence`: Generates an evidence request if uncertainty is high.
8. `reassess_case`: Re-evaluates case posture with new evidence.
9. `apply_policy`: Evaluates the deterministic PolicyEngine against evidence and LLM findings.
10. `prepare_case`: Assembles SAR filings and approval routes.
11. `write_case`: Persists fraud vertices back to TigerGraph.
12. `finish`: Serializes benchmark-compliant JSON outputs.

### 3.5 Calibrated Uncertainty & Evidence-Request Loops
A critical differentiator in FraudNet is its refusal to make premature decisions on weak signals.
- In **Case HHG-001**, the transaction scored 0.61 (moderately high risk) for an in-person charge of $77.07 in an unusual billing region. The agent recognized that while the location was anomalous, the cardholder frequently traveled. Rather than immediately blocking the card, the agent generated an evidence request (`customer_validation`), received confirmation that the cardholder made the charge, and safely closed the alert without customer disruption.
- In **Case HHG-014**, a flagged transaction of $74.96 was initially reviewed with customer verification in mind. However, the graph revealed a shared device profile linked to 34 distinct payment cards, proving a coordinated syndicate attack. The agent immediately updated its fraud probability to 0.95 and triggered emergency card monitoring.

### 3.6 Deterministic PolicyEngine: Sole Authority for Actions
LLMs are probabilistic; bank policy is legal and deterministic. In FraudNet, the LLM produces a recommendation, but the **PolicyEngine** (`src/policy/engine.py`) has final authority over:
- Permitted actions: `BLOCK_CARD`, `BLOCK_ALL_CARDS`, `MONITOR_CONNECTED_CARDS`, `CREATE_CASE`, `FILE_REPORT`, `CLOSE_NO_FRAUD`.
- Approval routes: `AUTO` (standard actions), `L1` (actions requiring senior analyst sign-off), and `L2` (high-exposure actions exceeding statutory limits).
- Rule enforcement: Rules R1 through R10 (e.g., Rule R10 strictly forbids blocking all cards unless a multi-card breach is proven).

The UI and answer files explicitly record both the initial recommendation and the final enforced policy decision, ensuring full regulatory defensibility.

### 3.7 SAR (Suspicious Activity Report) Generation
Under FinCEN regulations, filing a SAR is mandatory when fraud involves coordinated rings, device syndicates, or exceeds institutional thresholds. FraudNet generates structured SAR filings complete with:
- Filing justification cited against bank policy.
- Detailed narrative explaining the transaction sequence and graph topology.
- Subject identification (card IDs, customer IDs, device fingerprints).
- Aggregate exposure calculations.

### 3.8 Strict Grounding & Entity Integrity
To prevent LLM hallucination, every output is validated through two layers:
1. **Schema Validation (`evaluation/validate_schema.py`):** Enforces cross-field invariants using Pydantic (e.g., a legitimate verdict cannot have an active SAR filing; blocked cards must have valid approval routes).
2. **Entity Integrity (`evaluation/check_integrity.py`):** Validates every transaction ID, card ID, customer ID, and device profile against an in-memory registry of 631,219 ground-truth entities loaded from raw dataset files.

---

## 4. Replay UI & Investigation Control Room

The project includes a lightweight, real-time Flask Investigation Control Room (`ui/`):
- **Interactive Evidence Graph:** Rendered with D3.js force-directed physics. Visualizes transactions, cards, customers, devices, and closed cases. Clicking any entity highlights its supporting evidence cards.
- **Reconstructed Investigation Trace:** Reconstructs the 12-stage investigation timeline directly from stored evidence references.
- **PolicyEngine Gate View:** Shows the 3-step transition from LLM recommendation → PolicyEngine rule evaluation → final enforced action.
- **Uncertainty & Decision Confidence:** Displays calibrated fraud probability bars, uncertainty ratings, and initial-to-final verdict shifts.
- **Case Memory Precedent Grid:** Displays relevant past closed cases retrieved by GraphRAG.
- **Benchmark Dashboard (`/benchmark`):** Provides a 20-case matrix and aggregate operational statistics across all benchmark runs.

*Transparency note:* The UI operates in **Replay Mode** over canonical benchmark JSON outputs. Derived fields (such as trace ordering and uncertainty bands) and simulated customer responses are explicitly labeled as such in the interface.

---

## 5. 20-Case Benchmark Results

The system was benchmarked across all 20 exam cases in `case_pack.csv` against live TigerGraph Cloud and Groq's `openai/gpt-oss-20b` endpoint:

| Benchmark Metric | Observed Value |
|:---|:---|
| **Total Cases Executed** | 20 / 20 (100%) |
| **Output Schema Validation** | 20 / 20 Passed (100%) |
| **Entity Integrity Validation** | 20 / 20 Passed (631k entities verified) |
| **Verdict Breakdown** | 18 Fraud, 2 Legitimate |
| **Mandatory SARs Filed** | 10 Cases |
| **Evidence-Request Loops** | 16 Cases |
| **Average Wall-Clock Latency** | 30.0 seconds (Min: 19.1s, Max: 95.0s) |
| **Average Tool Calls per Case** | 5.6 |
| **Average Token Usage per Case** | 676 tokens |
| **Total Fraud Exposure Detected** | $3,515.23 |
| **Classification Accuracy / F1** | *Not measured* (Official ground truth not published) |

All 20 canonical result files are stored in `results/groq_tigergraph/` and duplicated in `submission/answers/`.

---

## 6. Real-World Case Studies

### Hero Case 1: HHG-014 — Coordinated Device Syndicate Fraud
- **Trigger:** Analyst alert regarding suspicious device reuse on card `C13487-K1` (transaction `3478561`).
- **Graph Traversal:** MCP tool `get_device_neighbors` revealed that device `SM-G935F Build/NRD90M | Android 7.0` was shared across **34 distinct payment cards**.
- **GraphRAG Precedents:** Retrieved historical syndicate cases `CC-2985`, `CC-3035`, `CC-2649`, and `CC-2971`.
- **Policy Enforcement:** Rules R6 (shared device attack) and R9 (undocumented coordinated ring) triggered.
- **Enforced Actions:** `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`, `MONITOR_CONNECTED_CARDS`.
- **SAR Filing:** Mandated SAR filed covering $74.96 immediate exposure and connected syndicate entities.
- **Case Memory:** Vertex persisted to TigerGraph with status `confirmed_fraud`.

### Hero Case 2: HHG-001 — Legitimate Travel Anomaly Resolved
- **Trigger:** High automated risk score (0.61) on transaction `3514030` ($77.07, billing region 444.0) on card `C12382-K1`.
- **Graph Traversal:** Transaction was an in-person physical terminal purchase. History showed customer `C12382` travels periodically.
- **Uncertainty & Evidence Loop:** Ambiguous signal triggered an evidence request (`customer_validation`).
- **Resolution:** Cardholder confirmed transaction authorization.
- **Policy Enforcement:** Rule R3 (customer confirmed transaction) evaluated.
- **Final Action:** `CLOSE_NO_FRAUD`. Exposure set to $0.00. SAR rejected. Alert cleared without unnecessary card blockage.

---

## 7. Reliability, Resilience, and Failure Modes

Building an autonomous agent for production financial systems requires rigorous fault tolerance:
1. **Fallback Graph Store:** If TigerGraph Cloud experiences transient network dropouts, `GraphAdapter` automatically falls back to an in-memory graph mirror loaded from raw CSVs (`TG_BACKEND=auto`), ensuring zero pipeline interruptions.
2. **Resilient JSON Recovery:** When LLM providers return truncated or markdown-wrapped JSON, custom repair heuristics strip fences, repair unclosed brackets, and recover structured schemas.
3. **Strict Credential Scrubbing:** All API keys, database secrets, and tokens are scrubbed via regex filter before logging or persisting timeline states.
4. **Idempotent Graph Writes:** Case persistence checks existing vertex IDs before writing to avoid duplicate node corruption in TigerGraph.

---

## 8. Lessons Learned, Limitations, and Future Roadmap

### What We Learned
- **Graphs turn impossible LLM tasks into trivial lookups.** Prompting an LLM to identify fraud rings from raw JSON arrays consumes thousands of tokens and frequently hallucinates. Having TigerGraph identify 34 connected cards via graph traversal allows the LLM to focus purely on high-level reasoning and synthesis.
- **Policy engines must be deterministic.** Financial compliance cannot tolerate non-deterministic hallucination in legal actions and SAR filings. Separating LLM recommendation from PolicyEngine enforcement is the only viable production pattern.

### Current Limitations
- **Customer Simulation:** In the offline benchmark, customer verification responses are simulated based on underlying case context. A production deployment would integrate real-time SMS/push webhook listeners.
- **Batch Replay vs. Streaming:** The current Control Room displays completed investigations. Real-time streaming over Server-Sent Events (SSE) would enhance live analyst observation during multi-minute investigations.

### Future Improvements
1. **Multi-Hop Subgraph Visualization:** Embedding live interactive graph expansions directly into the web UI during live runs.
2. **Autonomous Policy Learning:** Analyzing clusters of analyst overrides to propose refined policy rules back to compliance teams.
3. **Distributed Graph Analytics:** Implementing GSQL PageRank and Louvain community detection algorithms to proactively flag emerging device clusters before transactions occur.

---

## 9. Conclusion

FraudNet proves that graph technology and agentic AI are natural partners. TigerGraph provides the ground-truth relationship structure that prevents hallucination, while agentic LLMs provide the adaptive synthesis and human-readable auditability that modern fraud teams desperately need.

- **GitHub Repository:** [tigergraph-agentic-fraud-investigation](https://github.com/aaryamanmishra/tigergraph-agentic-fraud-investigation)
- **Built for:** Hacker House Goa 2026 — TigerGraph Agentic Fraud Investigation Challenge
