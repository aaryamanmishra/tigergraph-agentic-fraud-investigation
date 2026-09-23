# 🕵️ FraudNet — Agentic Fraud Investigation

> **From suspicious signal → graph evidence → uncertainty → investigation → defensible action → case memory**

FraudNet is an autonomous, graph-native fraud investigation platform built for **Hacker House Goa 2026 — TigerGraph Agentic Fraud Investigation Challenge**.

The system does not treat a transaction risk score as a verdict. It treats the risk score as an **investigation trigger** and gathers evidence, assesses uncertainty, requests additional evidence when needed, applies a deterministic policy engine, recommends next-best actions with approval routing, and persists investigation cases back to TigerGraph as organizational memory.

---

## Architecture

```text
Case Trigger (case_pack.csv — 20 HHG cases)
    │
    ▼
InvestigationWorkflow (src/agent/workflow.py)
    │
    ├──▶ TigerGraph / FraudNet  (via TigerGraph MCP)
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
    ├──▶ GraphRAG  (src/rag/)
    │       ├── fraud policy documents
    │       ├── fraud typology library
    │       └── prior closed case memory (5,565 cases)
    │
    ├──▶ LLM Reasoning  (src/agent/llm/)
    │       ├── evidence synthesis
    │       ├── uncertainty assessment
    │       └── structured findings (Pydantic-validated schemas)
    │
    ├──▶ Evidence-Request Loop (when uncertainty is unresolved)
    │       └── customer_validation / additional_evidence
    │
    ├──▶ PolicyEngine  (src/policy/engine.py) — deterministic
    │       ├── Rules R1–R10
    │       ├── action assignment
    │       ├── approval routing (AUTO / L1 / L2)
    │       ├── exposure calculation
    │       └── SAR filing requirement
    │
    ├──▶ Serializer + Schema Validator
    │       └── evaluation/validate_schema.py + check_integrity.py
    │
    └──▶ TigerGraph write-back  (case memory for future investigations)
```

---

## Core Components

### TigerGraph

The project uses a live TigerGraph Cloud instance (graph: `FraudNet`) as the authoritative relationship and evidence store. Entity relationships — cards, customers, transactions, device profiles, billing regions, and closed cases — are queried via GSQL.

### TigerGraph MCP

The official `tigergraph-mcp` package exposes 9 purpose-built GSQL fraud investigation tools to the agent via the Model Context Protocol. This prevents the LLM from issuing unstructured queries and eliminates hallucinated graph operations.

### GraphRAG

GraphRAG retrieves provenance-tagged context from three sources before LLM reasoning begins:

- **Fraud policy** (Rules R1–R10, approval routes, SAR thresholds)
- **Fraud typology library** (card testing, account takeover, CNP fraud, out-of-region use, undocumented abuse)
- **Prior closed case memory** (5,565 historical investigations retrieved by card / device / region similarity)

Each retrieved chunk carries a `ProvenanceItem` tag (`policy`, `typology`, or `case_memory`) shown in the UI.

### LLM Reasoning

Benchmark executed with:

| Setting | Value |
|:---|:---|
| Provider | Groq |
| Model | `openai/gpt-oss-20b` |
| Interface | OpenAI-compatible REST API |
| Output format | Structured Pydantic schemas (`LLMReasoningStep`, `LLMFinalSynthesis`) |

LLM outputs are schema-validated. Invalid or ungrounded entity references are rejected before policy evaluation.

### PolicyEngine

The PolicyEngine (`src/policy/engine.py`) is the sole authority for all policy-sensitive decisions. The LLM produces a recommendation; the PolicyEngine evaluates it deterministically against Rules R1–R10 and enforces the final action set. The LLM recommendation and the enforced outcome are both recorded and shown separately in the UI.

### Evidence-Request Loop

When uncertainty is unresolved after initial evidence gathering, the agent generates a structured evidence request (`customer_validation` or `additional_evidence`) and reassesses the case after a response is received. Simulated customer responses are clearly labeled `[SIMULATION]` in the UI.

### Grounding & Validation

- All entity IDs (transaction, card, customer, device) are cross-checked against the live dataset (`evaluation/check_integrity.py`).
- LLM structured outputs are validated with Pydantic.
- Final answer files are validated with a full schema and cross-field invariant checker (`evaluation/validate_schema.py`).

---

## Benchmark Results

All 20 benchmark cases were executed against the live TigerGraph FraudNet graph.

| Metric | Result |
|:---|:---|
| Cases executed | 20 / 20 |
| Schema valid | 20 / 20 |
| Entity integrity valid | 20 / 20 |
| Fraud verdicts | 18 |
| Legitimate verdicts | 2 |
| SAR filed | 10 |
| Evidence-request loops triggered | 16 / 20 |
| Average latency | 30.0 s |
| Min / Max latency | 19.1 s / 95.0 s |
| Average tool calls per case | 5.6 |
| Average tokens per case | 676 |
| Total exposure detected | $3,515.23 |
| Accuracy / Precision / Recall / F1 | Not measured — ground-truth labels not published |

Detailed per-case results: `results/groq_tigergraph/`
Benchmark report: `docs/full_benchmark_report.md`

---

## Investigation Control Room (UI)

The Flask-based Investigation Control Room (`ui/`) provides a replay interface over all 20 saved benchmark investigations.

```bash
cd ui
../.venv/bin/python app.py
# Open: http://127.0.0.1:5000
```

### Key pages

| URL | Description |
|:---|:---|
| `/` | Redirects to hero case HHG-014 |
| `/case/HHG-014` | Fraud hero — coordinated device/network syndicate (34 connected cards) |
| `/case/HHG-001` | Legitimate hero — customer confirmed routine transaction |
| `/case/HHG-NNN` | Any of the 20 benchmark cases |
| `/benchmark` | Aggregate dashboard + 20-case investigation matrix |
| `/api/graph/HHG-NNN` | D3-ready node/edge JSON built from evidence entity IDs |
| `/api/case/HHG-NNN` | Raw case JSON |

### UI panels (all grounded in saved benchmark files)

- **Interactive Evidence Graph** — D3 v7 force-directed graph of entities extracted from evidence `entity_ids`. Click a node to highlight its linked evidence cards.
- **Reconstructed Agent Activity Trace** — Sequence of investigation steps reconstructed from ordered evidence records. Labeled as reconstruction in the UI.
- **Uncertainty & Confidence** — Derived uncertainty level (LOW / MEDIUM / HIGH) and probability bar from `fraud_probability`. Initial → final verdict delta.
- **Evidence Request → Response → Reassessment** — When triggered, shows the request type and rationale, the simulated customer response (labeled `[SIMULATION]`), and the reassessment outcome.
- **PolicyEngine Gate** — LLM recommendation vs. deterministic PolicyEngine output vs. final enforced actions. Shown as separate steps.
- **Case Timeline** — Vertical timeline of evidence-gathering stages with category icons.
- **GraphRAG Case Memory** — Retrieved similar closed cases from `case.similar_prior_cases`.
- **Benchmark Dashboard** — Aggregate metrics, verdict distribution, and a 20-case comparison matrix.

> The replay UI does **not** trigger new LLM investigations, re-query TigerGraph, or display fabricated data. Everything displayed is read directly from the saved benchmark files.

---

## Hero Cases

### HHG-001 — Legitimate transaction

The agent retrieved transaction, card, customer, and historical-case evidence, identified residual uncertainty, requested customer validation, received confirmation the transaction was authorized, reassessed the case, applied Policy R3, and closed with `CLOSE_NO_FRAUD`.

### HHG-014 — Coordinated device/network syndicate

The agent identified a device profile shared by 34 connected cards, retrieved related prior investigations, applied Policies R6 and R9, and generated `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`, and `MONITOR_CONNECTED_CARDS` with statutory SAR filing.

---

## Quick Start

### Requirements

- Python 3.10+
- TigerGraph Cloud credentials (for live investigations)
- Groq or other OpenAI-compatible API key (for live investigations)
- The saved benchmark results in `results/groq_tigergraph/` are sufficient to run the UI without any credentials.

### Setup

```bash
# Clone and enter the repo
git clone https://github.com/aaryamanmishra/tigergraph-agentic-fraud-investigation.git
cd tigergraph-agentic-fraud-investigation

# Create the virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install flask pydantic tigergraph-mcp requests

# Configure credentials
cp .env.example .env
# Edit .env with your TigerGraph and LLM credentials
```

### Run the Investigation Control Room (no credentials required)

```bash
cd ui
../.venv/bin/python app.py
# Open: http://127.0.0.1:5000
```

### Run the test suite

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q
# Expected: 126 passed
```

### Run a single investigation (requires live credentials)

```bash
PYTHONPATH=. .venv/bin/python -m evaluation.run_single_case \
  --case HHG-014 \
  --backend tigergraph \
  --provider openai \
  --output results/groq_tigergraph/HHG-014.json
```

---

## Project Structure

```text
.
├── src/
│   ├── agent/          ← InvestigationWorkflow, nodes, state, LLM providers, tools
│   ├── graph/          ← GraphAdapter (TigerGraph + in-memory), MCP client/server
│   ├── policy/         ← PolicyEngine (Rules R1–R10), actions, exposure, approval
│   └── rag/            ← GraphRAG retriever, chunker, context builder, provenance
├── ui/
│   ├── app.py          ← Flask Investigation Control Room
│   ├── templates/      ← index.html (case view), benchmark.html (dashboard)
│   └── static/         ← app.js (D3 graph renderer), style.css
├── evaluation/
│   ├── validate_schema.py   ← Full answer-file schema + cross-field validation
│   ├── check_integrity.py   ← Entity-ID integrity checker
│   ├── run_benchmark.py     ← 20-case batch runner
│   └── run_single_case.py   ← Single case runner
├── tests/              ← 13 test modules, 126 tests
├── results/
│   └── groq_tigergraph/     ← 20 validated benchmark answer files (source of truth)
├── submission/
│   ├── README.md            ← Submission package documentation
│   └── answers/             ← Identical copies of the 20 canonical answer files
├── docs/               ← Architecture docs, policy matrix, schema spec, RAG guide
├── case_pack.csv        ← 20 benchmark case triggers
├── .env.example         ← Environment variable template
└── README.md            ← This file
```

---

## Design Principles

- Risk score is a **trigger**, not a verdict.
- Graph evidence is **authoritative** for entity relationships.
- LLM reasoning is **grounded** in retrieved evidence.
- Policy enforcement is **deterministic** — the LLM cannot override the PolicyEngine.
- Case memory is **persisted** in TigerGraph for future investigations.
- Invalid or ungrounded entity references are **rejected** before any decision is made.
- Simulated customer responses are **explicitly labeled** as simulation.
- Accuracy, precision, recall, and F1 are **not reported** — ground-truth labels for the benchmark cases are not published.

---

## Hackathon Requirements Covered

- ✅ TigerGraph as the authoritative graph database
- ✅ TigerGraph MCP for typed agent-accessible graph tools
- ✅ GraphRAG over fraud policy, typologies, and case memory
- ✅ Real LLM reasoning with structured output validation
- ✅ Evidence-gathering investigation workflow
- ✅ Calibrated uncertainty assessment
- ✅ Controlled evidence-request loops
- ✅ Deterministic policy enforcement (R1–R10)
- ✅ Next-best action with approval routing (AUTO / L1 / L2)
- ✅ SAR generation when statutorily required
- ✅ Case persistence to TigerGraph
- ✅ 20-case benchmark evaluation
- ✅ Interactive investigation UI (Flask + D3)
- ✅ 126 automated tests

---

## License / Attribution

Built for Hacker House Goa 2026.
Dataset attribution and original benchmark/policy material: `docs/hackathon_dataset_and_policy.md`
