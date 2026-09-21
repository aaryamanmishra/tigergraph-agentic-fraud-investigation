# TigerGraph Agentic Fraud Investigation

An agentic fraud investigation system built for Hacker House Goa 2026 using TigerGraph, TigerGraph MCP, GraphRAG, and real LLM reasoning.

## Overview

This project investigates suspicious payment transactions by combining:

- TigerGraph knowledge-graph evidence
- TigerGraph MCP tools
- GraphRAG over fraud policy, typologies, and prior cases
- Real LLM reasoning
- Evidence-request loops
- Deterministic policy enforcement
- Case persistence and investigation memory
- Grounding and schema validation

The agent does not treat the transaction risk score as a fraud verdict. It gathers evidence, assesses uncertainty, requests additional evidence when necessary, applies deterministic bank policy, recommends the next best action, and writes eligible investigation cases back to the graph.

## Architecture

```text
Case Trigger
    |
    v
Investigation Agent
    |
    +--> TigerGraph / MCP
    |       |
    |       +--> Transaction context
    |       +--> Card history
    |       +--> Customer history
    |       +--> Device relationships
    |       +--> Similar closed cases
    |
    +--> GraphRAG
    |       |
    |       +--> Fraud policy
    |       +--> Fraud typologies
    |       +--> Case memory
    |
    v
LLM Evidence Reasoning
    |
    v
Uncertainty Evaluation
    |
    +--> Request additional evidence
    |        |
    |        v
    |     Customer / evidence response
    |
    v
Deterministic PolicyEngine
    |
    v
Next Best Action
    |
    +--> Allow / monitor / verify
    +--> Block / escalate
    +--> File report
    +--> Create case
    |
    v
Validation + Graph Persistence
```

## Core Components

### TigerGraph

The project uses a live TigerGraph graph named FraudNet containing the investigation entities and relationships required for the benchmark.

### TigerGraph MCP

TigerGraph MCP exposes graph operations to the agent through typed investigation tools.

### GraphRAG

GraphRAG retrieves:

- policy documents
- fraud typologies
- prior closed investigations
- relevant graph evidence

Retrieved evidence is provenance-tagged before being supplied to the reasoning layer.

### LLM Reasoning

The benchmark was executed using:

- Provider: Groq
- Model: openai/gpt-oss-20b
- Interface: OpenAI-compatible API

The LLM is used for evidence synthesis, uncertainty assessment, and investigation explanation. Policy decisions remain deterministic.

### PolicyEngine

The PolicyEngine is authoritative for:

- policy-rule evaluation
- allowed actions
- approval routes
- exposure
- SAR requirements

The LLM cannot bypass policy enforcement.

### Grounding & Validation

LLM outputs are validated through:

- Pydantic structured schemas
- evidence grounding
- entity-ID integrity checks
- output schema validation

## Investigation Flow

1. Load the investigation trigger.
2. Retrieve transaction and relationship evidence from TigerGraph.
3. Retrieve relevant prior investigations.
4. Retrieve policy and typology context with GraphRAG.
5. Ask the LLM to synthesize evidence.
6. Evaluate uncertainty.
7. Request additional evidence when necessary.
8. Reassess the case.
9. Apply deterministic policy rules.
10. Produce next-best actions.
11. Persist eligible cases to TigerGraph.
12. Validate the final answer.

## Benchmark

The final benchmark contains all 20 Hacker House Goa cases.

| Metric | Result |
| :--- | :--- |
| Cases executed | 20 / 20 |
| Backend | TigerGraph / FraudNet |
| LLM | Groq openai/gpt-oss-20b |
| Real LLM runs | 20 / 20 |
| Schema validation | 20 / 20 |
| Entity integrity | 20 / 20 |
| Overall valid | 20 / 20 |

Detailed per-case results are available in:

`results/groq_tigergraph/`

Benchmark report:

`docs/full_benchmark_report.md`

## Example Investigations

### HHG-001 — Legitimate

The agent:

- retrieved transaction, card, customer, and historical-case evidence
- identified residual uncertainty
- requested customer validation
- received confirmation that the transaction was authorized
- reassessed the case
- applied policy R3
- closed the case with CLOSE_NO_FRAUD

### HHG-014 — Fraud

The agent:

- identified a multi-card device relationship
- retrieved related prior investigations
- produced real LLM reasoning
- assessed the transaction as fraudulent
- applied policies R6 and R9
- generated CREATE_CASE, FILE_REPORT, ESCALATE_TO_ANALYST, and MONITOR_CONNECTED_CARDS
- persisted the investigation case to TigerGraph

## Project Structure

```text
.
├── src/
│   ├── agent/
│   ├── graph/
│   └── ...
├── evaluation/
├── tests/
├── cases/
├── results/
├── docs/
├── configs/
└── README.md
```

## Setup

Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

The project uses environment variables for credentials and infrastructure configuration. Do not commit .env.

## Running a Single Case

Example:

```bash
PYTHONPATH=. uv run --with tigergraph-mcp --with pytest \
  python -m evaluation.run_single_case \
  --case HHG-014 \
  --backend tigergraph \
  --provider openai \
  --output results/groq_tigergraph/HHG-014.json
```

## Running the Test Suite

```bash
PYTHONPATH=. uv run --with tigergraph-mcp --with pytest \
  python3 -m pytest tests/
```

## Benchmark Output

Each case produces a validated JSON answer containing:

- case record
- evidence requests
- next-best actions
- SAR information
- stop reason
- tool-call metadata
- token usage
- latency

## Design Principles

- Risk score is a trigger, not a verdict.
- Graph evidence remains authoritative for entity relationships.
- LLM reasoning is grounded in retrieved evidence.
- Policy enforcement is deterministic.
- Case memory is persisted in the graph.
- Invalid or ungrounded entity references are rejected.
- Dataset and annotation integrity are preserved.

## Hackathon Requirements Covered

- TigerGraph graph database
- TigerGraph MCP
- GraphRAG
- Agentic investigation workflow
- Evidence gathering
- Uncertainty / evidence requests
- Next-best action
- Policy and approval routing
- Case persistence
- SAR generation
- 20-case benchmark evaluation

## License / Attribution

Built for Hacker House Goa 2026.

Dataset attribution and original benchmark/policy material are preserved in:

`docs/hackathon_dataset_and_policy.md`
