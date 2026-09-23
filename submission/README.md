# FraudNet — Submission Package
## Hacker House Goa 2026 — TigerGraph Agentic Fraud Investigation

---

## What is FraudNet?

FraudNet is an autonomous, graph-native fraud investigation platform built for the Hacker House Goa 2026 TigerGraph Agentic Fraud Investigation Challenge.

The system treats a suspicious transaction risk score as an **investigation trigger**, not a verdict. Starting from that signal, the agent gathers multi-hop graph evidence, assesses uncertainty, requests additional evidence when needed, applies a deterministic policy engine, recommends the next-best action with approval routing, and writes eligible cases back to TigerGraph as organizational memory for future investigations.

---

## Contents of This Submission

```
submission/
├── README.md             ← this file
└── answers/
    ├── HHG-001.json      ← investigation result for case HHG-001
    ├── HHG-002.json
    ├── ...
    └── HHG-020.json      ← investigation result for case HHG-020
```

The `answers/` directory contains the **20 final validated investigation answer files**, one per benchmark case.

---

## How the Answer Files Were Generated

Each answer file was produced by a fully automated end-to-end investigation run:

1. **Case trigger ingested** from `case_pack.csv` (20 cases: `HHG-001` through `HHG-020`).
2. **TigerGraph queried** via the official TigerGraph MCP interface for transaction context, card history, customer history, device relationships, and similar closed cases.
3. **GraphRAG retrieval** pulled relevant fraud policy documents, typologies, and prior closed investigations from the FraudNet graph.
4. **LLM reasoning** synthesized graph evidence into structured findings (Provider: Groq; Model: `openai/gpt-oss-20b` via OpenAI-compatible API).
5. **Uncertainty evaluated** — if unresolved, a controlled evidence-request loop ran and the case was reassessed.
6. **Deterministic PolicyEngine** applied Rules R1–R10 to assign actions, approval routes, and SAR requirements.
7. **Answer serialized** and validated against the schema (`evaluation/validate_schema.py`) and entity-integrity checker (`evaluation/check_integrity.py`).
8. **Eligible cases written back** to TigerGraph for case memory.

No answer file was hand-crafted. All investigation decisions, evidence, entity references, and metrics come directly from the live system execution.

---

## Benchmark Results (Actual)

All 20 cases passed schema validation and entity-integrity checks.

| Metric | Result |
|:---|:---|
| Cases executed | 20 / 20 |
| Schema valid | 20 / 20 |
| Entity integrity valid | 20 / 20 |
| Backend | TigerGraph Cloud / FraudNet |
| LLM provider | Groq (`openai/gpt-oss-20b`) |
| Fraud verdicts | 18 |
| Legitimate verdicts | 2 |
| SAR filed | 10 |
| Evidence-request loops triggered | 16 / 20 |
| Average latency | 30.0 s |
| Min / Max latency | 19.1 s / 95.0 s |
| Average tool calls per case | 5.6 |
| Average tokens per case | 676 |
| Total exposure detected | $3,515.23 |
| Accuracy / Precision / Recall / F1 | Not measured (ground-truth labels not published) |

---

## Answer File Schema

Each `HHG-NNN.json` file contains the following top-level fields:

| Field | Description |
|:---|:---|
| `case_id` | Case identifier (e.g. `HHG-001`) |
| `case` | Full case record: verdict, fraud_probability, pattern, affected transactions, connected cards/devices, evidence, similar prior cases, exposure, graph writeback status |
| `evidence_requests` | Evidence request(s) submitted during investigation, including type, rationale, and simulated customer response |
| `next_best_actions` | Initial (pre-evidence loop) and final recommended actions with approval routes; includes `what_changed` explanation |
| `sar` | SAR filing decision: whether filed, reason, narrative, subjects, amount, activity dates |
| `stop_reason` | Why the investigation loop terminated (`sufficient_evidence`, `customer_confirmed`, `max_loops`) |
| `tool_calls` | Number of tool calls made |
| `tokens` | Total tokens consumed by the LLM |
| `latency_s` | Total investigation wall-clock time in seconds |

---

## How to Run the Application

### Prerequisites

```bash
cd /path/to/task4

# Activate the virtual environment
source .venv/bin/activate

# Copy .env.example and fill in your credentials
cp .env.example .env
# Edit .env: TG_HOST, TG_GRAPH_NAME, TG_SECRET, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
```

### Launch the Investigation Control Room (Replay UI)

```bash
cd ui
../.venv/bin/python app.py
```

Then open: **http://127.0.0.1:5000**

- Landing page: HHG-014 (fraud hero case — coordinated device/network syndicate)
- Use the case dropdown or ← → arrow keys to navigate all 20 cases
- Visit `/benchmark` for the aggregate dashboard and 20-case matrix

### Run the Full Test Suite

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: **126 passed**

### Run a Single Investigation (requires live TigerGraph + LLM credentials)

```bash
PYTHONPATH=. .venv/bin/python -m evaluation.run_single_case \
  --case HHG-014 \
  --backend tigergraph \
  --provider openai \
  --output results/groq_tigergraph/HHG-014.json
```

> **Note:** The 20 saved benchmark result files are the canonical source of truth. Re-running investigations requires live TigerGraph Cloud credentials and will consume LLM API credits.

---

## Replay UI — What is Reconstructed/Derived

The Investigation Control Room at `http://127.0.0.1:5000` displays the saved benchmark results. The following information is **derived or reconstructed** from the stored result files and is clearly labeled as such in the UI:

| UI Component | Source | Label in UI |
|:---|:---|:---|
| Agent Activity Trace | Reconstructed from ordered evidence `ref` fields in the saved JSON | "Reconstructed Investigation Trace" |
| Uncertainty Level (LOW/MEDIUM/HIGH) | Derived from `fraud_probability` value | "Derived from saved benchmark evidence" |
| Initial → Final verdict delta | Derived from `next_best_actions.initial` vs `.final` | Shown as delta flow |
| PolicyEngine gate | Extracted from `next_best_actions` and evidence `ref` fields containing policy rule codes | "Extracted from Evidence" |
| Case Timeline | Reconstructed from evidence record ordering | "Reconstructed" |
| Evidence graph | Built from actual `entity_ids` listed in each evidence record | Real entity IDs, force-directed layout |
| GraphRAG Case Memory | Populated from `case.similar_prior_cases` in the saved JSON | Real case IDs |

### Simulated Customer Responses

When the agent triggered a customer validation request during the original investigation, the response that drove reassessment was simulated by the agent (clearly labeled `[SIMULATION]` in the UI). The investigation decision following that response is real and recorded in the saved benchmark file.

---

## What the Replay UI Does NOT Do

- It does **not** trigger new LLM investigations.
- It does **not** re-query TigerGraph.
- It does **not** display fabricated data.
- It does **not** imply the replay view is a live streaming investigation.
- Evidence, verdicts, entity IDs, exposures, and policy decisions are all read directly from the saved benchmark files.

---

## Architecture Overview

```
Case Trigger (case_pack.csv)
    │
    ▼
InvestigationWorkflow (src/agent/workflow.py)
    │
    ├──▶ TigerGraph / FraudNet (via TigerGraph MCP)
    │       transaction context · card history · customer history
    │       device relationships · similar closed cases
    │
    ├──▶ GraphRAG (src/rag/)
    │       fraud policy · typologies · case memory
    │
    ├──▶ LLM Reasoning (src/agent/llm/)
    │       evidence synthesis · uncertainty · structured findings
    │
    ├──▶ Evidence-Request Loop (when uncertainty is unresolved)
    │
    ├──▶ PolicyEngine (src/policy/engine.py) — deterministic, R1–R10
    │       actions · approval routes · SAR requirements
    │
    ├──▶ Serializer + Validator (src/agent/serializer.py + evaluation/)
    │
    └──▶ TigerGraph write-back (case memory)
```

---

## Source of Truth

The canonical investigation results are:

```
results/groq_tigergraph/HHG-001.json  through  HHG-020.json
```

The files in `submission/answers/` are identical copies of those files.
