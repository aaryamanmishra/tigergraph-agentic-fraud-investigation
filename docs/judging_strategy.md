# Hackathon Judging Strategy & Scoring Playbook
## TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation

### 1. Scoring Matrix Breakdown

| Criteria | Weight | What Judges Look For | Our Architectural & Implementation Strategy |
|---|---|---|---|
| **Investigation Accuracy** | **25%** | Correct pattern identification (including undocumented abuse); precise scoping of affected transactions; accurate exposure calculation; discovering connected cards and shared infrastructure. | • Deterministic multi-hop GSQL queries for device, region, and email entity resolution.<br>• Sequence analyzers for card testing and velocity spikes.<br>• Calibration that prevents false-positive over-flagging on legitimate accounts.<br>• Exact transaction ID mapping and exposure summation. |
| **Next Best Action** | **25%** | Handling ambiguous/weak signals; disciplined application of R1–R10; evidence-request triggering; before vs. after action evolution; exact approval routing (`auto`, `L1`, `L2`). | • Decoupling LLM action suggestion from deterministic policy enforcement.<br>• Formal state-machine managing initial vs. final recommendations.<br>• Strict routing based on exposure thresholds ($\$500$, $\$1,000$, $\$2,500$) and customer reply status.<br>• Full compliance with R10 guardrails (preventing unwarranted `BLOCK_ALL_CARDS`). |
| **Case Summary & Explainability** | **10%** | Concise, professional analyst summary; structured evidence claims citing query refs and entity IDs; FinCEN-compliant SAR narrative. | • Every claim in `case.evidence` cites query names, entity IDs, and sources (`graph`, `document`, `customer`, `external`).<br>• Standalone SAR narratives satisfying the 6 core FinCEN questions (Who, What, When, Where, How, Why).<br>• Clear explanation of `stop_reason` and remaining uncertainty. |
| **Agentic Design & Engineering** | **15%** | Clean tool design (TigerGraph MCP); robust orchestration; separation of concerns; graph persistence as case memory; error handling and token efficiency. | • Modern agent orchestration (e.g. LangGraph / stateful graph workflow).<br>• Standardized MCP interface exposing GSQL graph queries as native tools.<br>• Case memory loop: reading 5,565 closed cases and writing newly investigated cases into TigerGraph.<br>• Structured validation of JSON answers via JSON Schema. |
| **Innovation** | **15%** | Originality of graph usage; GraphRAG implementation; recognizing undocumented coordinated abuse; optional live monitoring pipeline. | • GraphRAG combining graph topology with vector search over regulatory guides and closed cases.<br>• Coordinated ring fraud detection algorithms traversing shared device profiles and anonymous proxies.<br>• Standalone stream monitor for exam period alerts without contaminating benchmark cases. |
| **Demo Quality & Completeness** | **10%** | Clear, compelling 3–5 minute video demonstration; intuitive analyst workbench UI; clear end-to-end execution of all 20 benchmark cases. | • Full analyst dashboard showing real-time graph visualization, case progression, policy evaluation, and SAR preview.<br>• Clear visual demonstration of the evidence-request loop changing actions in real time.<br>• Reproducible one-click evaluation script for all 20 benchmark cases. |

---

### 2. Deep Dive: Winning Tactics by Category

#### 2.1 Investigation Accuracy (25%)
- **Avoid the "Block Everything" Trap**: The README highlights: *"Half the cases are legitimate. An agent that blocks everything scores badly."* Our agent explicitly evaluates baseline customer history. If a customer frequently transacts in region 444.0 on weekends (as seen in HHG-001), the agent identifies it as legitimate routine spend, keeping `fraud_probability` low ($\le 0.15$), `affected_txn_ids` empty, and `exposure_usd` at 0.
- **Uncompromised Entity Scoping**: For true fraud episodes, the agent traverses the `NEXT` transaction sequence and flags all transactions belonging to the compromise window, calculating `exposure_usd` exactly from dataset values.
- **Undocumented Abuse Recognition (Rule R9)**: When an attack pattern involves repeated abuse across multiple cards from an identical device profile (e.g. Samsung SM-G935F behind an anonymous proxy, as seen in HHG-014 and historical case CC-2649), the agent detects that it does not fit standard single-card CNP or ATO typologies. It designates the pattern as `undocumented`, writes a descriptive narrative in `pattern_description`, and triggers R9 policy actions (`CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`).

#### 2.2 Next Best Action (25%)
- **Strict Separation of LLM & Policy**:
  ```
  [Agent Thought & Proposal] ──► [Deterministic Policy Engine] ──► [Validated Actions & Approval Routes]
  ```
  The LLM generates reasoning and suggests candidates; the deterministic rule engine verifies conditions (e.g., probability threshold, single signal constraint, exposure limits) and outputs the statutory action list and approval route.
- **Clear Evidence Evolution**:
  - `initial`: Highlights cautious, proportional actions (e.g. `VERIFY_WITH_CUSTOMER` under R1).
  - `final`: Updates decisively based on the simulated response (e.g. upon customer denial, transitions to `BLOCK_CARD` and `CREATE_CASE` under R2).
  - `what_changed`: Articulates precisely how the assumed response shifted the risk assessment and policy obligations.

#### 2.3 Case Summary & Explainability (10%)
- **Institutional Quality**: Summaries are written in crisp financial crime compliance terminology.
- **Traceable Evidence Links**: Every item in `case.evidence` provides a concrete `ref` such as `query:card_history(card_id=C12382-K1)`, `query:device_neighbors(device_profile=...)`, or `evidence_request:1`, accompanied by relevant `entity_ids`.
- **FinCEN SAR Narrative Standard**: When a SAR is required, the narrative fulfills the six regulatory requirements:
  - **Who**: Full customer, card, and device identifiers.
  - **What**: Financial amounts, transaction counts, and authorization types.
  - **When**: Activity start and end dates.
  - **Where**: Physical billing regions, online channel, and IP proxy flags.
  - **How**: TTPs (tools, techniques, and procedures) such as credential stuffing or proxy evasion.
  - **Why**: Justification of why the conduct is suspicious and warrants filing under US Treasury / FinCEN guidelines.

#### 2.4 Agentic Design & Engineering (15%)
- **Deterministic Guardrails**: Zero hallucination through pydantic/JSON schema validation.
- **Graph Native Execution**: Tools are not generic SQL queries; they execute GSQL graph traversals utilizing TigerGraph's core strengths (sub-second multi-hop graph neighborhood expansion).
- **Dual Memory Architecture**:
  - *Short-Term Working Memory*: Current case evidence, requested items, and progressive hypotheses.
  - *Long-Term Case Memory*: Graph of 5,565 closed historical cases + real-time writeback of new cases.

#### 2.5 Innovation (15%)
- **GraphRAG Grounding**: Fusing graph topology (neighborhood subgraphs) with vector embeddings of FinCEN guidance, FATF typologies, and closed case analyst notes to ground LLM reasoning.
- **Autonomous Stream Monitor (Exam Period)**: An optional background daemon simulating real-time stream ingestion during November–December 2016 to detect coordinated fraud bursts, kept strictly isolated from the 20 benchmark answer files.

#### 2.6 Demo Quality & Completeness (10%)
- **3–5 Minute Focused Video**:
  - 0:00–0:45: Problem statement, TigerGraph architecture, and GraphRAG setup.
  - 0:45–2:15: Deep dive into 2 contrasting benchmark cases:
    1. A complex multi-card coordinated attack (HHG-014) requiring graph traversal, R9 undocumented classification, SAR filing, and L2 approval.
    2. A subtle false alarm (HHG-001) where customer routine spend avoids an erroneous block (R1/R3).
  - 2:15–3:15: Before vs. After evidence-request loop demonstration and graph persistence.
  - 3:15–4:00: Benchmark batch runner validating all 20 cases in seconds.

---

### 3. Submission Checklist

- [ ] All 20 answer JSON files in `cases/<case_id>.json` validating against JSON Schema.
- [ ] Every entity ID verified to exist in the real dataset files.
- [ ] Verified graph persistence for closed cases (`written_to_graph: true` with valid `graph_case_id`).
- [ ] SAR narratives populated if and only if `sar.file = true` and `FILE_REPORT` is present in final actions.
- [ ] Clean GitHub repository with documentation, setup instructions, and reproducible scripts.
- [ ] 3–5 minute video demo recording.
- [ ] Technical blog post detailing architecture, TigerGraph usage, agentic workflows, and learnings.
- [ ] Social media post on X/LinkedIn tagging `@TigerGraphDB`.
