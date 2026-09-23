# 🕵️ FraudNet

## Agentic Fraud Investigation & Next-Best-Action Platform

> **From suspicious signal → evidence → uncertainty → investigation → defensible action → case memory**

FraudNet is an agentic fraud investigation platform built for **Hacker House Goa 2026 — TigerGraph Agentic Fraud Investigation Challenge**.

The system investigates suspicious payment activity using:

* **TigerGraph** as the authoritative relationship/evidence graph
* **TigerGraph MCP** for agent-accessible graph tools
* **GSQL and graph analytics** for relationship analysis and fraud-pattern detection
* **GraphRAG** for fraud policies, typologies, regulatory context, and prior case memory
* **Real LLM reasoning** for evidence synthesis, uncertainty assessment, tool selection, and explanations
* **Deterministic PolicyEngine** for policy enforcement, permissions, approvals, exposure, and SAR requirements
* **Evidence-request loops** for resolving uncertainty
* **Case memory** for learning from previous investigations
* **Structured schemas and grounding validation** for reliable outputs
* **Interactive investigation UI** for analysts
* **Benchmarking and replay** to demonstrate system behavior and reliability

The core system already implements the fundamental investigation workflow. This project specification defines the next layer: turning the existing engine into a polished, auditable, measurable, and judge-friendly investigation product without breaking the existing functionality.

---

# 1. Project Objective

Fraud detection should not end with:

> "This transaction has a high risk score."

FraudNet treats a risk score as an **investigation trigger**, not a fraud verdict.

The system must answer:

1. What happened?
2. What entities are connected?
3. What evidence supports or contradicts fraud?
4. What fraud pattern may be involved?
5. What information is still unknown?
6. Is the evidence sufficient to act?
7. If not, what evidence should be requested?
8. What does the bank's policy allow?
9. What action should happen next?
10. What approval is required?
11. What should be written to the investigation case?
12. Can this investigation become useful memory for future cases?

The official challenge requires the agent to investigate triggered cases, gather evidence, assess uncertainty, request additional evidence when necessary, recommend actions, operate within policy, explain its decisions, and update case memory. This specification preserves that workflow and makes each stage visible and demonstrable.

---

# 2. Critical Development Rule

## ⚠️ DO NOT REWRITE THE EXISTING CORE ENGINE

The current implementation already satisfies important hackathon requirements.

The new work must be implemented as **extensions around the existing investigation engine**.

### Existing functionality that MUST remain intact

The following are considered protected core functionality:

* TigerGraph integration
* FraudNet graph
* TigerGraph MCP
* transaction retrieval
* card history retrieval
* customer history retrieval
* device relationships
* prior investigation retrieval
* GraphRAG
* policy retrieval
* fraud typology retrieval
* case memory
* real LLM reasoning
* uncertainty evaluation
* evidence-request loop
* reassessment after new evidence
* deterministic PolicyEngine
* policy-rule evaluation
* action authorization
* approval routing
* SAR determination/generation
* case creation
* case persistence
* Pydantic schemas
* evidence grounding
* entity-ID validation
* final output validation
* 20-case benchmark execution
* existing case JSON outputs
* existing test suite

The current system already reports:

```text
20 / 20 cases executed
20 / 20 real LLM runs
20 / 20 schema validation
20 / 20 entity integrity
20 / 20 overall valid
```

These capabilities must continue to work after all UI and architectural improvements.

---

# 3. Non-Negotiable Architecture Principle

The project must maintain this separation:

```text
                 ┌───────────────────────┐
                 │     CASE TRIGGER      │
                 │ Risk / Report /       │
                 │ Analyst Request       │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │  INVESTIGATION AGENT  │
                 └───────────┬───────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ↓                  ↓                  ↓
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ TigerGraph  │    │  GraphRAG   │    │ Case Memory │
   │ + GSQL      │    │             │    │             │
   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ↓
                 ┌───────────────────────┐
                 │ Evidence Synthesis    │
                 │ + LLM Reasoning       │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ Uncertainty Evaluation│
                 └───────────┬───────────┘
                             │
                    ┌────────┴────────┐
                    ↓                 ↓
              SUFFICIENT          INSUFFICIENT
                    │                 │
                    │                 ↓
                    │          Evidence Request
                    │                 │
                    │                 ↓
                    │          New Evidence
                    │                 │
                    │                 ↓
                    │           Reassessment
                    │                 │
                    └────────┬────────┘
                             ↓
                 ┌───────────────────────┐
                 │    PolicyEngine       │
                 │ Deterministic Policy  │
                 │ + Permissions         │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ Approval / Action Gate│
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ Next Best Action      │
                 └───────────┬───────────┘
                             ↓
                 ┌───────────────────────┐
                 │ Case + Evidence +     │
                 │ Outcome Persistence   │
                 └───────────┬───────────┘
                             ↓
                        TigerGraph
```

The UI must **consume this architecture**, not replace it.

---

# 4. Existing Core Investigation Flow

The existing investigation flow must remain the source of truth.

## Step 1 — Trigger

An investigation begins from:

* fraud/risk signal
* customer report
* analyst request
* another supported event

The official challenge explicitly defines these trigger types.

---

## Step 2 — Retrieve graph evidence

Retrieve relevant:

* transaction information
* card history
* customer history
* device relationships
* identity relationships
* account behavior
* connected transactions
* previous investigations

TigerGraph remains authoritative for entity relationships.

---

## Step 3 — Retrieve GraphRAG context

Retrieve:

* fraud policies
* fraud typologies
* regulatory context
* relevant prior cases
* connected graph evidence

GraphRAG must pass **relevant contextual evidence** to the LLM rather than blindly passing raw data.

This matches the challenge's requirement that GraphRAG ground the agent with relevant evidence and context.

---

## Step 4 — LLM evidence synthesis

The LLM is responsible for:

* evidence synthesis
* identifying patterns
* assessing uncertainty
* reasoning over retrieved evidence
* deciding which investigation tools/evidence may be useful
* explaining findings

The LLM must NOT become the authoritative source of:

* entity relationships
* policy authorization
* permissions
* SAR requirements
* final execution authority

---

# 5. Risk Score Is a Trigger, NOT a Verdict

This must remain one of the project's central principles.

```text
Risk Score
    ↓
Investigation Trigger
    ↓
Evidence Gathering
    ↓
Reasoning
    ↓
Uncertainty
    ↓
Policy
    ↓
Decision
```

Never:

```text
Risk Score
    ↓
Fraud = True
```

The dataset explicitly states that transactions contain a fraud-model risk score but do not contain an `Is Fraud` flag.

---

# 6. New Product Layer — Fraud Investigation Control Room

The primary new feature is a professional analyst-facing UI.

It must feel like an actual fraud operations workstation rather than a generic AI chatbot.

## Main layout

```text
┌───────────────────────────────────────────────────────────────┐
│ FRAUDNET INVESTIGATION CONTROL ROOM                           │
│ Case HHG-014          INVESTIGATING          RISK: HIGH       │
├────────────────┬────────────────────────┬─────────────────────┤
│ CASE            │ INVESTIGATION GRAPH    │ DECISION            │
│                │                        │                     │
│ Transaction    │ Customer               │ FRAUD               │
│ $1,284.32      │    │                   │ Confidence: 94%     │
│                │   Card                 │                     │
│ Card           │    │                   │ Pattern             │
│ ****4821       │ Transaction             │ Multi-card          │
│                │    │                   │ device abuse        │
│ Customer       │  Device                 │                     │
│ C-1092         │   / \                   │ ACTIONS             │
│                │ Card Card               │ CREATE_CASE         │
│ Trigger        │                        │ FILE_REPORT         │
│ Risk 0.94      │ Prior Cases             │ ESCALATE            │
├────────────────┴────────────────────────┴─────────────────────┤
│ INVESTIGATION TIMELINE                                       │
│ ✓ Transaction evidence                                      │
│ ✓ Device relationship                                       │
│ ✓ Prior investigations                                      │
│ ⚠ Customer validation requested                             │
│ ✓ Policy R6                                                 │
└───────────────────────────────────────────────────────────────┘
```

---

# 7. UI Design Principles

The UI must make these things immediately visible:

### Case

* case ID
* transaction ID
* customer
* card
* amount
* timestamp
* trigger
* current status

### Investigation

* current stage
* evidence gathered
* evidence missing
* confidence
* uncertainty
* identified fraud pattern

### Graph

* relevant entities
* relationships
* connected entities
* previous cases
* graph-derived signals

### Decision

* current assessment
* confidence
* next-best action
* approval route
* policy basis

### Agent

* tool calls
* investigation steps
* evidence retrieval
* reasoning milestones
* evidence requests
* reassessment

---

# 8. Evidence Graph — Hero Feature

The TigerGraph graph should be visualized directly in the investigation UI.

Example:

```text
                         ┌─────────────┐
                         │  CUSTOMER   │
                         │   C-1092    │
                         └──────┬──────┘
                                │
                              owns
                                │
                         ┌──────▼──────┐
                         │    CARD     │
                         │  ****4821   │
                         └──────┬──────┘
                                │
                              used in
                                │
                         ┌──────▼──────┐
                         │ TRANSACTION │
                         │   HHG-014   │
                         │   $1284.32  │
                         └──────┬──────┘
                                │
                            originated
                                │
                         ┌──────▼──────┐
                         │   DEVICE    │
                         │    D-44     │
                         └───┬────┬────┘
                             │    │
                          uses   uses
                             │    │
                          CARD-A CARD-B
                             │    │
                             └─┬──┘
                               │
                         ┌─────▼──────┐
                         │ PRIOR CASES│
                         │ HHG-003    │
                         │ HHG-009    │
                         └────────────┘
```

## Requirements

The graph visualization must:

* show only relevant subgraphs by default
* support node selection
* support edge inspection
* highlight suspicious relationships
* highlight evidence used by the reasoning engine
* allow navigation from entity → related evidence
* show previous investigation relationships
* distinguish current case entities from historical entities

---

# 9. Graph Analytics Layer

Do not make TigerGraph merely a data store.

Use GSQL/graph analytics for actual investigation signals.

The official challenge specifically requires GSQL and graph algorithms for traversal, pattern detection and relationship analysis.

## Required/desired graph-derived signals

### 9.1 Device concentration

Calculate:

```text
device
→ connected cards
→ connected customers
→ suspicious transactions
→ previous fraud cases
```

Example output:

```json
{
  "device_id": "D-44",
  "connected_cards": 7,
  "connected_customers": 5,
  "prior_fraud_cases": 3,
  "device_risk_signal": "HIGH"
}
```

---

### 9.2 Transaction velocity

Analyze transaction activity over:

* 5 minutes
* 30 minutes
* 24 hours

Example:

```text
17 transactions
within 8 minutes
```

This becomes an evidence signal, not an automatic fraud verdict.

---

### 9.3 Shared entity analysis

Trace:

```text
Customer
 ↓
Cards
 ↓
Devices
 ↓
Customers
 ↓
Transactions
 ↓
Cases
```

Expose connected exposure.

---

### 9.4 Fraud-ring / connected-component analysis

Identify suspicious connected clusters.

Example:

```text
       Customer A
        /       \
    Device 1   Device 2
      /  \        \
 Customer B     Customer C
      |            |
   Txn 12       Txn 19
```

Output:

```text
Connected investigation cluster

Customers: 3
Devices: 2
Transactions: 14
Prior confirmed cases: 2
```

Again, this is a graph-derived signal and must be presented with provenance.

---

# 10. Agent Activity Trace

Add a live investigation trace.

Example:

```text
AGENT ACTIVITY

✓ 20:43:01  Investigation triggered
✓ 20:43:02  Retrieved transaction context
✓ 20:43:02  Traversed device relationships
✓ 20:43:03  Found related cards
✓ 20:43:03  Retrieved prior investigations
✓ 20:43:04  Retrieved fraud policy
⚠ 20:43:04  Evidence confidence: 71%
→ 20:43:04  Requesting customer validation
✓ 20:43:09  Customer evidence received
✓ 20:43:09  Reassessing case
✓ 20:43:10  PolicyEngine evaluated
✓ 20:43:10  Case persisted
```

This must represent actual system events.

Do NOT fabricate agent activity purely for presentation.

---

# 11. Investigation State Machine

Represent the agent using explicit investigation states.

Suggested states:

```text
TRIGGERED
    ↓
COLLECTING_EVIDENCE
    ↓
ASSESSING
    ↓
EVIDENCE_INSUFFICIENT
    ↓
AWAITING_EVIDENCE
    ↓
REASSESSING
    ↓
POLICY_EVALUATION
    ↓
AWAITING_APPROVAL
    ↓
ACTION_READY
    ↓
CASE_PERSISTED
    ↓
CLOSED
```

Not every investigation must pass through every state.

The state machine should reflect the actual backend state.

---

# 12. Uncertainty Engine

The uncertainty stage is central to the product.

Display:

```text
INVESTIGATION STATE

Fraud confidence:       68%
Evidence sufficiency:   INSUFFICIENT

Known:
✓ Suspicious transaction
✓ New device
✓ Geographic anomaly

Unknown:
? Customer authorized transaction
? Device ownership confirmed

NEXT BEST ACTION

REQUEST_CUSTOMER_VALIDATION
```

The agent must explicitly distinguish:

* known evidence
* inferred findings
* missing evidence
* contradictory evidence
* unresolved uncertainty

---

# 13. Evidence Request Loop

This is one of the most important demo capabilities.

The flow must be:

```text
Initial evidence
      ↓
Uncertainty detected
      ↓
Evidence request
      ↓
Evidence response
      ↓
Reassessment
      ↓
Updated confidence
      ↓
Updated action
```

Example:

### Before evidence

```text
Confidence: 68%

Unknown:
Customer authorization

Action:
REQUEST_CUSTOMER_VALIDATION
```

### Customer response

```text
"I made this transaction."
```

### After evidence

```text
Confidence: 12%

Action:
CLOSE_NO_FRAUD
```

Alternative:

```text
"I did not make this transaction."
```

Results in:

```text
Confidence: 96%

Actions:
CREATE_CASE
BLOCK_CARD
FILE_REPORT
ESCALATE
```

The actual decision must come from the existing investigation/policy pipeline, not from hardcoded UI behavior.

---

# 14. "What Changed My Mind?"

Add a dedicated explainability panel.

Example:

```text
WHAT CHANGED THE ASSESSMENT?

Initial assessment:
SUSPICIOUS — 64%

Evidence requested:
Customer validation

New evidence:
Customer denied authorization

Updated assessment:
FRAUD — 96%

Decision changed:
MONITOR → BLOCK + ESCALATE

Primary evidence responsible:
Customer denial
```

This feature must be generated from actual investigation state transitions.

---

# 15. Evidence Provenance

Every important evidence item should expose its source.

Example:

```text
Evidence
────────────────────────────

Device D-44 connected to Card C-991

Source:
TigerGraph

Tool:
get_device_connections

Retrieved:
20:43:03

Authority:
Graph evidence

Used by:
Fraud assessment
```

GraphRAG example:

```text
Evidence
────────────────────────────

Policy R6

Source:
Fraud Policy

Retriever:
GraphRAG

Used for:
Card-blocking decision
```

Possible source types:

```text
TigerGraph
TigerGraph MCP
GraphRAG
Prior Case
Policy
Customer Response
Analyst Input
External Source
```

---

# 16. Explainability — "Why?"

Every major decision should have a `Why?` action.

## Fraud assessment

```text
FRAUD
Confidence: 94%

[ WHY? ]
```

Clicking it should show:

```text
WHY THIS ASSESSMENT?

+ Multi-card device relationship
+ 3 related suspicious transactions
+ 2 previous confirmed fraud cases
+ Transaction velocity anomaly
+ Device connected to unrelated customers

Evidence:
TG-Transaction-01
TG-Device-07
CASE-003
CASE-009
POLICY-R6
```

---

# 17. Deterministic PolicyEngine Must Remain Authoritative

The LLM must never directly execute policy-sensitive actions.

Architecture:

```text
                 LLM
                  ↓
           Investigation
             reasoning
                  ↓
          Proposed actions
                  ↓
          ┌───────────────┐
          │ PolicyEngine  │
          │ AUTHORITATIVE │
          └───────┬───────┘
                  ↓
        Allowed / denied actions
                  ↓
            Approval Gate
                  ↓
              Execution
```

The official challenge requires the agent to operate within predefined policies and permissions and recognizes actions requiring human approval.

---

# 18. Policy Gate Demonstration

Create a demonstrable case where the LLM proposes an action that policy rejects.

Example:

```text
LLM PROPOSAL

FREEZE_ACCOUNT
```

PolicyEngine:

```text
✗ DENIED

Reason:
Agent lacks authorization for account freeze.

Required approval:
Senior Fraud Analyst
```

Allowed actions:

```text
CREATE_CASE
FILE_REPORT
ESCALATE_TO_ANALYST
MONITOR_CONNECTED_CARDS
```

This should be a real PolicyEngine result.

Do not fake the rejection purely for the demo.

---

# 19. Approval Routing

Every action should have:

```text
action
approval_required
approval_role
authorization_status
policy_basis
```

Example:

```json
{
  "action": "BLOCK_CARD",
  "authorization_status": "REQUIRES_APPROVAL",
  "approval_role": "FRAUD_ANALYST",
  "policy_basis": ["R6"]
}
```

The UI should clearly show:

```text
ACTION
BLOCK CARD

STATUS
Awaiting Fraud Analyst Approval

POLICY
R6

Reason
Confirmed fraud + policy threshold satisfied
```

---

# 20. Case Timeline

Every investigation should expose a chronological audit trail.

Example:

```text
HHG-014

10:32:01  Trigger received
          Risk score: 0.94

10:32:02  Case opened

10:32:03  Transaction evidence retrieved

10:32:04  Device relationship discovered

10:32:05  2 prior fraud cases found

10:32:06  Fraud pattern identified
          MULTI-CARD DEVICE ABUSE

10:32:07  Policy R6/R9 retrieved

10:32:08  Actions proposed

10:32:09  Policy evaluated

10:32:10  Case persisted
```

The timeline must use actual timestamps/events wherever possible.

---

# 21. Case Memory

Case memory is already part of the core architecture and must remain intact.

The challenge explicitly asks the agent to store findings, retrieve similar previous cases, use previous outcomes, identify recurring patterns, and update memory when cases resolve.

Add a visible case-memory section:

```text
CASE MEMORY

Current Case:
HHG-014

Similar investigations:

HHG-003
Similarity: 0.89
Outcome: Confirmed Fraud

HHG-009
Similarity: 0.83
Outcome: Confirmed Fraud

Common pattern:
Multi-card device abuse
```

Then explain:

```text
MEMORY INFLUENCE

Previous confirmed investigations share:
- device topology
- transaction behavior
- card relationships

These cases were used as supporting context.
```

Do not imply that similarity alone proves fraud.

---

# 22. Investigation Replay

Add:

```text
[ REPLAY INVESTIGATION ]
```

Replay the actual investigation sequence:

```text
TRIGGER
 ↓
GRAPH RETRIEVAL
 ↓
EVIDENCE
 ↓
GRAPH ANALYSIS
 ↓
GRAPHRAG
 ↓
LLM ASSESSMENT
 ↓
UNCERTAINTY
 ↓
EVIDENCE REQUEST
 ↓
NEW EVIDENCE
 ↓
REASSESSMENT
 ↓
POLICY
 ↓
ACTION
 ↓
CASE PERSISTENCE
```

The replay must be generated from recorded investigation events.

It should not invent actions that did not occur.

---

# 23. Failure Mode / Reliability Lab

Create a developer/demo mode to demonstrate resilience.

Suggested controls:

```text
[ Simulate LLM Failure ]
[ Simulate Graph Failure ]
[ Invalid Entity ]
[ Missing Evidence ]
[ Conflicting Evidence ]
[ Policy Rejection ]
```

## LLM failure

Expected behavior:

```text
LLM unavailable

✓ No unauthorized action executed
✓ Case state preserved
✓ Evidence preserved
✓ Investigation marked incomplete
✓ Analyst escalation available
```

## Invalid entity

Example:

```text
LLM requests:

customer_id = C-999999

Entity validation:
✗ ENTITY DOES NOT EXIST

Result:
Request rejected
No invalid graph mutation
```

## Graph failure

Expected:

```text
TigerGraph unavailable

Investigation:
PAUSED

No final action executed without sufficient evidence.
```

The exact fallback must respect existing implementation constraints.

---

# 24. Grounding and Entity Validation

The existing validation system is protected.

Every LLM-generated entity reference must be validated.

Required checks:

* entity exists
* entity type matches
* relationship is valid
* case ID exists where required
* transaction ID exists
* no hallucinated graph IDs
* schema is valid
* evidence references are valid

Invalid outputs must not silently enter the graph.

---

# 25. Structured Output

Maintain Pydantic validation.

Suggested high-level output structure:

```json
{
  "case": {},
  "investigation": {},
  "evidence": [],
  "findings": [],
  "uncertainty": {},
  "evidence_requests": [],
  "assessment": {},
  "policy": {},
  "actions": [],
  "approvals": [],
  "sar": {},
  "timeline": [],
  "memory": {},
  "metadata": {}
}
```

Do not change existing schemas unless necessary.

If schemas must be extended, make additions backward compatible.

---

# 26. Next Best Action

The system must distinguish between:

### Investigation recommendation

```text
REQUEST_CUSTOMER_VALIDATION
```

### Operational action

```text
BLOCK_CARD
```

### Case action

```text
CREATE_CASE
```

### Reporting action

```text
FILE_REPORT
```

### Escalation

```text
ESCALATE_TO_ANALYST
```

### Monitoring

```text
MONITOR_CONNECTED_CARDS
```

The challenge explicitly lists these types of next actions.

---

# 27. Before / After Next Best Action

The UI must preserve both states.

Example:

```text
BEFORE ADDITIONAL EVIDENCE

Assessment:
Suspicious

Confidence:
71%

NBA:
REQUEST_CUSTOMER_VALIDATION
```

After response:

```text
AFTER ADDITIONAL EVIDENCE

Assessment:
Fraud

Confidence:
96%

NBA:
CREATE_CASE
BLOCK_CARD
FILE_REPORT
ESCALATE_TO_ANALYST
```

This is particularly important because the submission requires the next-best action and approval route to be recorded **before additional evidence is requested and after additional evidence is received.**

---

# 28. SAR Support

Existing SAR functionality must remain intact.

For applicable cases, display:

```text
SUSPICIOUS ACTIVITY REPORT

Status:
REQUIRED

Basis:
Policy R9

Evidence:
...

Investigation:
...

Recommended filing:
...
```

For cases where SAR is not required:

```text
SAR
NOT REQUIRED

Policy basis:
...
```

Never let the UI invent SAR requirements.

---

# 29. Benchmark System

The 20 Hacker House Goa benchmark cases remain the primary evaluation set.

The official dataset uses twenty cases from the final two months as the benchmark and all teams are evaluated on the same cases.

Run:

```text
HHG-001
HHG-002
...
HHG-020
```

---

# 30. Benchmark Dashboard

Create a benchmark overview:

```text
HHGOA BENCHMARK

Cases executed              20 / 20

Schema validity             20 / 20
Entity integrity            20 / 20
Real LLM runs               20 / 20

Investigation outcome       XX / 20
Next-best action            XX / 20
Evidence request            XX / 20
Policy compliance           XX / 20

Median latency              X.XX s
Average latency             X.XX s
```

## Important

Only display metrics that are actually calculated.

Do NOT invent accuracy numbers.

If a metric cannot be reliably derived from the provided annotations, label it:

```text
NOT YET MEASURED
```

rather than fabricating a score.

---

# 31. 20-Case Investigation Matrix

Generate a table:

```text
| Case | Expected | Agent | Confidence | Evidence Request | NBA | Policy | Valid |
|------|----------|-------|------------|------------------|-----|--------|-------|
| 001  | Legit    | ...   | ...        | ...              | ... | ...    | ✓ |
| 002  | Fraud    | ...   | ...        | ...              | ... | ...    | ✓ |
| ...  | ...      | ...   | ...        | ...              | ... | ...    | ... |
| 020  | ...      | ...   | ...        | ...              | ... | ...    | ✓ |
```

This should be generated automatically from benchmark results.

---

# 32. Benchmark Regression Protection

Every new feature must be tested against the original benchmark.

Before modifications:

```text
pytest tests/
```

After modifications:

```text
pytest tests/
```

Then:

```text
Run all 20 benchmark cases.
```

The project must not be considered complete if UI improvements cause benchmark regressions.

---

# 33. Regression Test Categories

Add tests for:

## Core functionality

* transaction retrieval
* graph traversal
* MCP calls
* GraphRAG
* policy retrieval
* LLM reasoning
* evidence requests
* reassessment
* persistence

## Validation

* schema validation
* entity validation
* grounding
* invalid IDs
* malformed LLM output

## Policy

* allowed action
* denied action
* approval-required action
* SAR requirement

## Memory

* prior case retrieval
* similar case retrieval
* case persistence
* historical outcome retrieval

## UI/API

* case loading
* evidence loading
* graph rendering data
* timeline
* action state
* replay

---

# 34. Security / Safety Rules

Never:

* expose secrets in UI
* expose API keys
* execute arbitrary LLM-generated commands
* allow LLM to bypass PolicyEngine
* write hallucinated entities to TigerGraph
* mark fraud solely from LLM confidence
* execute unauthorized actions
* fabricate evidence
* fabricate benchmark metrics

Environment variables remain the correct mechanism for credentials.

Never commit `.env`.

---

# 35. Data Integrity

The original benchmark dataset must remain unchanged.

Do not modify:

* original transaction records
* benchmark case definitions
* original annotations
* original policy documents
* original expected outputs

Derived data may be created separately.

Recommended:

```text
data/
  raw/
  processed/
  derived/
```

---

# 36. Recommended Project Structure

Extend the existing structure rather than replacing it.

```text
.
├── src/
│   ├── agent/
│   │   ├── ...
│   │   ├── investigation/
│   │   ├── uncertainty/
│   │   └── replay/
│   │
│   ├── graph/
│   │   ├── ...
│   │   ├── analytics/
│   │   └── queries/
│   │
│   ├── policy/
│   │   └── ...
│   │
│   ├── rag/
│   │   └── ...
│   │
│   ├── validation/
│   │   └── ...
│   │
│   ├── api/
│   │   └── ...
│   │
│   └── models/
│       └── ...
│
├── frontend/
│   ├── components/
│   ├── pages/
│   ├── investigation/
│   ├── graph/
│   ├── timeline/
│   ├── benchmark/
│   └── replay/
│
├── evaluation/
│   ├── run_single_case.py
│   ├── run_benchmark.py
│   ├── metrics.py
│   └── ...
│
├── cases/
├── results/
│   └── groq_tigergraph/
│
├── tests/
│   ├── agent/
│   ├── graph/
│   ├── policy/
│   ├── validation/
│   ├── benchmark/
│   └── integration/
│
├── docs/
│   ├── architecture.md
│   ├── investigation-flow.md
│   ├── benchmark.md
│   ├── failure-modes.md
│   └── hackathon_dataset_and_policy.md
│
├── configs/
├── README.md
└── .env.example
```

Do not force this exact structure if the existing project architecture differs. Preserve working modules wherever practical.

---

# 37. API Layer

The frontend should communicate with the backend through a stable API.

Suggested endpoints:

```text
GET  /cases
GET  /cases/{case_id}
POST /cases/{case_id}/investigate

GET  /cases/{case_id}/timeline
GET  /cases/{case_id}/evidence
GET  /cases/{case_id}/graph
GET  /cases/{case_id}/reasoning

POST /cases/{case_id}/evidence-request
POST /cases/{case_id}/evidence-response

GET  /cases/{case_id}/actions
GET  /cases/{case_id}/policy

POST /cases/{case_id}/replay

GET  /benchmark
GET  /benchmark/cases
```

These are suggested interfaces only.

Reuse existing APIs when they already provide the required functionality.

---

# 38. UI Screens

The application should contain the following major views.

## 38.1 Investigation Dashboard

Overview of active cases.

```text
ACTIVE CASES

HHG-014   HIGH       INVESTIGATING
HHG-008   MEDIUM     AWAITING EVIDENCE
HHG-019   HIGH       AWAITING APPROVAL
```

---

## 38.2 Case Investigation

Main hero screen.

Sections:

```text
Case Header
↓
Assessment
↓
Graph
↓
Evidence
↓
Agent Trace
↓
Uncertainty
↓
Actions
↓
Timeline
```

---

## 38.3 Graph Explorer

Interactive graph.

---

## 38.4 Evidence Explorer

All evidence with provenance.

---

## 38.5 Policy / Approval Panel

Show:

* proposed action
* policy
* authorization
* approval requirement
* final decision

---

## 38.6 Benchmark Dashboard

Show the 20-case evaluation.

---

## 38.7 Investigation Replay

Replay completed cases.

---

## 38.8 Reliability Lab

Developer/demo mode for failure scenarios.

---

# 39. Hero Cases

Use at least two contrasting cases in the demo.

## HHG-014 — Fraud

Current implementation already demonstrates:

* multi-card device relationship
* related prior investigations
* real LLM reasoning
* fraud assessment
* policies R6 and R9
* CREATE_CASE
* FILE_REPORT
* ESCALATE_TO_ANALYST
* MONITOR_CONNECTED_CARDS
* graph persistence

Do not break this flow.

---

## HHG-001 — Legitimate

Current implementation already demonstrates:

* transaction/card/customer/historical evidence
* residual uncertainty
* customer validation request
* customer confirmation
* reassessment
* policy R3
* CLOSE_NO_FRAUD

Do not break this flow.

These two cases provide the ideal contrast:

```text
Suspicious signal
      ↓
Need more evidence
      ↓
Authorized customer
      ↓
Close

vs.

Suspicious signal
      ↓
Graph evidence
      ↓
Prior fraud memory
      ↓
Customer denies
      ↓
Fraud
      ↓
Escalate / report / create case
```

---

# 40. Demo Mode

Create a clean demo mode that hides unnecessary developer details while retaining the real system behavior.

The demo should support:

```text
Select Case
    ↓
Start Investigation
    ↓
Watch Agent
    ↓
Inspect Graph
    ↓
Inspect Evidence
    ↓
See Uncertainty
    ↓
Provide Evidence
    ↓
See Reassessment
    ↓
See Policy Gate
    ↓
See NBA
    ↓
See Case Persistence
```

---

# 41. Demo Script

Target duration:

**3–5 minutes**

The official submission requires a 3–5 minute end-to-end demonstration.

## 0:00–0:15 — Hook

> "A bank doesn't need another fraud classifier. It needs an investigator."

Then:

> "FraudNet starts with an uncertain fraud signal, gathers graph evidence, identifies what it doesn't know, requests additional evidence, applies bank policy, and produces a defensible next-best action."

---

## 0:15–0:45 — Trigger

Open HHG-014.

Show:

```text
Transaction: $1,284
Risk score: 0.94
Status: INVESTIGATING
```

Say:

> "The risk score is only a trigger. We don't treat it as a fraud verdict."

---

## 0:45–1:20 — TigerGraph

Show graph.

Highlight:

```text
Customer
 ↓
Card
 ↓
Transaction
 ↓
Device
 ↓
Other Cards
 ↓
Prior Cases
```

Say:

> "The agent uses TigerGraph as the source of truth for entity relationships."

---

## 1:20–1:50 — GraphRAG + Memory

Show prior cases and policy.

```text
HHG-003
HHG-009

Pattern:
Multi-card device abuse

Policy:
R6
R9
```

---

## 1:50–2:20 — Uncertainty

Show:

```text
Confidence: 71%

Unknown:
Customer authorization

NEXT BEST ACTION:
REQUEST_CUSTOMER_VALIDATION
```

Say:

> "The important part is that the agent knows what it doesn't know."

---

## 2:20–2:50 — Evidence Loop

Provide:

```text
"I did not authorize this transaction."
```

Show:

```text
Confidence:
71% → 96%

Decision:
FRAUD

Actions:
CREATE_CASE
BLOCK_CARD
FILE_REPORT
ESCALATE
```

Say:

> "The new evidence changes the investigation, so the recommendation changes."

---

## 2:50–3:15 — Policy

Show:

```text
LLM:
FREEZE_ACCOUNT

PolicyEngine:
DENIED

Reason:
Human approval required
```

Then show permitted actions.

Say:

> "The LLM reasons about the case, but it cannot bypass policy."

---

## 3:15–3:40 — Persistence

Show case written to graph.

```text
CASE CREATED

Evidence
Reasoning
Actions
Approval
Timeline
Outcome
```

---

## 3:40–4:00 — Benchmark

Show actual benchmark metrics.

End with:

> "We didn't build a fraud classifier. We built an investigator."

---

# 42. Innovation Feature

The main innovation should not be "we added another AI model."

The innovation should be:

## Investigation Replay + What Changed My Mind

Together they demonstrate that the agent's decision is a process rather than a black-box answer.

The judge can inspect:

```text
What did the agent know?
What did it not know?
What did it request?
What changed?
Why did the action change?
What policy authorized it?
```

---

# 43. Technical Blog Structure

The technical blog should contain:

```text
1. Problem
2. Why fraud investigation is difficult
3. Architecture
4. TigerGraph design
5. Graph analytics
6. TigerGraph MCP
7. GraphRAG
8. Agent workflow
9. Evidence-request loop
10. PolicyEngine
11. Case memory
12. Grounding and validation
13. UI
14. Benchmark
15. Failure modes
16. What we learned
17. Limitations
18. Future improvements
```

The official submission requires the technical blog to cover what was built, architecture, TigerGraph usage, agentic capabilities, lessons learned, and improvements.

---

# 44. README Landing Page

The GitHub README should start with:

```text
# 🕵️ FraudNet

## An Agentic Fraud Investigation & Next-Best-Action Platform

From:

Suspicious Signal
        ↓
Evidence
        ↓
Uncertainty
        ↓
Investigation
        ↓
Policy
        ↓
Action
        ↓
Case Memory
```

Then immediately show:

* demo GIF/video
* architecture
* benchmark
* key capabilities
* quick start

Avoid opening the README with a long list of dependencies.

---

# 45. Core Feature Matrix

Maintain a requirements matrix.

| Requirement          |     Existing |                        Extension |
| -------------------- | -----------: | -------------------------------: |
| TigerGraph           |            ✅ |            Improve visualization |
| GSQL                 | ✅ / preserve | Add graph analytics where useful |
| TigerGraph MCP       |            ✅ |                 Show agent trace |
| GraphRAG             |            ✅ |                Add provenance UI |
| Agentic workflow     |            ✅ |            Make workflow visible |
| Evidence gathering   |            ✅ |                Evidence explorer |
| Uncertainty          |            ✅ |         Visual uncertainty panel |
| Evidence requests    |            ✅ |        Interactive evidence loop |
| Reassessment         |            ✅ |                Show before/after |
| Next-best action     |            ✅ |            Action/approval panel |
| Policy enforcement   |            ✅ |              Visible policy gate |
| Case persistence     |            ✅ |    Timeline + graph confirmation |
| SAR                  |            ✅ |                  UI presentation |
| Case memory          |            ✅ |                  Memory explorer |
| Grounding            |            ✅ |              Evidence provenance |
| Schema validation    |            ✅ |                Benchmark display |
| Entity validation    |            ✅ |                     Failure demo |
| 20-case benchmark    |            ✅ |              Benchmark dashboard |
| Analyst UI           |          New |                     Control Room |
| Graph Explorer       |   New/extend |                     Hero feature |
| Agent Trace          |          New |            Visible orchestration |
| Investigation Replay |          New |               Innovation feature |
| Failure Lab          |          New |        Reliability demonstration |

---

# 46. Definition of Done

The project is complete only when:

## Core

* [ ] Existing tests pass
* [ ] Existing benchmark still runs
* [ ] All 20 cases execute
* [ ] TigerGraph works
* [ ] MCP works
* [ ] GraphRAG works
* [ ] LLM reasoning works
* [ ] PolicyEngine remains deterministic
* [ ] Case persistence works
* [ ] Validation works

## Investigation UI

* [ ] Dashboard
* [ ] Case view
* [ ] Graph view
* [ ] Evidence view
* [ ] Agent trace
* [ ] Uncertainty view
* [ ] Action view
* [ ] Policy view
* [ ] Timeline
* [ ] Case memory

## Evidence loop

* [ ] Evidence request visible
* [ ] Response can be simulated/provided
* [ ] Reassessment occurs
* [ ] Confidence updates
* [ ] NBA updates
* [ ] Before/after states retained

## Explainability

* [ ] Why fraud?
* [ ] Why this evidence?
* [ ] Why request evidence?
* [ ] Why this action?
* [ ] Which policy?
* [ ] Which approval?

## Graph

* [ ] Relevant graph visible
* [ ] Relationships inspectable
* [ ] Graph-derived signals visible
* [ ] Prior cases connected
* [ ] No hallucinated entities

## Reliability

* [ ] LLM failure handled
* [ ] Graph failure handled
* [ ] Invalid entity rejected
* [ ] Policy rejection demonstrated
* [ ] Invalid output rejected

## Benchmark

* [ ] 20 cases
* [ ] Actual metrics
* [ ] Per-case matrix
* [ ] Regression testing
* [ ] Latency captured if available

## Demo

* [ ] 3–5 minutes
* [ ] HHG-014
* [ ] HHG-001
* [ ] Evidence loop
* [ ] Graph
* [ ] Policy gate
* [ ] Persistence
* [ ] Benchmark

---

# 47. Development Priority

Because the deadline is close, implement in this order.

## P0 — Must Have

1. Investigation Control Room
2. Interactive Evidence Graph
3. Agent Activity Trace
4. Uncertainty panel
5. Evidence request → response → reassessment
6. Policy gate visualization
7. Case timeline

## P1 — High Value

8. Evidence provenance
9. Case memory visualization
10. Benchmark dashboard
11. 20-case investigation matrix
12. Failure-mode demonstrations

## P2 — Innovation

13. Investigation Replay
14. "What Changed My Mind?"
15. Graph fraud-cluster visualization
16. Additional UI polish

Do not sacrifice P0 functionality to implement P2 features.

---

# 48. Coding Agent Instructions

When implementing this specification:

### Rule 1 — Inspect before modifying

Understand the existing repository architecture first.

Do not replace existing modules without necessity.

### Rule 2 — Preserve existing interfaces

If existing APIs/classes/functions are already working, extend them rather than breaking their contracts.

### Rule 3 — Reuse existing investigation engine

The UI should call the existing investigation pipeline.

Do not implement a second parallel fraud engine inside the frontend.

### Rule 4 — No fake data in the real pipeline

Demo-only simulated customer responses are acceptable when explicitly marked as simulation.

Never fabricate:

* graph relationships
* evidence
* benchmark metrics
* policy decisions
* investigation outcomes

### Rule 5 — Preserve determinism where required

The PolicyEngine remains authoritative.

### Rule 6 — Keep LLM grounded

LLM output must continue to use validated evidence.

### Rule 7 — Preserve graph integrity

Never write invalid entity IDs.

### Rule 8 — Test after each major change

Run:

```bash
pytest tests/
```

Then run representative cases:

```bash
PYTHONPATH=. uv run --with tigergraph-mcp --with pytest \
python -m evaluation.run_single_case \
--case HHG-001 \
--backend tigergraph
```

and:

```bash
PYTHONPATH=. uv run --with tigergraph-mcp --with pytest \
python -m evaluation.run_single_case \
--case HHG-014 \
--backend tigergraph
```

Then run the full benchmark.

### Rule 9 — Don't optimize only for screenshots

Every visible feature should reflect real backend state wherever possible.

### Rule 10 — Do not overengineer

The goal is a robust, demonstrable system, not an enormous framework.

---

# 49. Final Product Vision

FraudNet should ultimately feel like this:

```text
┌─────────────────────────────────────────────────────────────┐
│                     FRAUDNET                                │
│          AGENTIC FRAUD INVESTIGATION                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SIGNAL                                                     │
│    ↓                                                        │
│  INVESTIGATE                                                │
│    ↓                                                        │
│  GRAPH EVIDENCE                                             │
│    ↓                                                        │
│  GRAPHRAG + CASE MEMORY                                     │
│    ↓                                                        │
│  REASON                                                     │
│    ↓                                                        │
│  ┌───────────────────────────────┐                          │
│  │ "I don't know if customer     │                          │
│  │  authorized this transaction."│                          │
│  └───────────────┬───────────────┘                          │
│                  ↓                                          │
│            REQUEST EVIDENCE                                 │
│                  ↓                                          │
│            NEW INFORMATION                                  │
│                  ↓                                          │
│              REASSESS                                       │
│                  ↓                                          │
│             POLICY ENGINE                                   │
│                  ↓                                          │
│            APPROVAL GATE                                    │
│                  ↓                                          │
│            NEXT BEST ACTION                                 │
│                  ↓                                          │
│          CASE + MEMORY                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The product should communicate one central idea:

> **FraudNet doesn't just detect suspicious transactions. It investigates them.**

The agent should demonstrate:

```text
"I found something suspicious."

        ↓

"Here is the evidence."

        ↓

"Here is what I know."

        ↓

"Here is what I don't know."

        ↓

"Here is the evidence I need."

        ↓

"Here is how the new evidence changed my assessment."

        ↓

"Here is what policy permits."

        ↓

"Here is the next best action."

        ↓

"Here is the complete case record."

        ↓

"Here is what future investigations can learn from this."
```

That is the intended final form of the project.

---

# 50. Final Engineering Principle

**Do not build a bigger fraud classifier.**

Build a better **investigator**.

The difference is:

```text
Traditional:

Risk Score
    ↓
Fraud / Not Fraud


FraudNet:

Risk Signal
    ↓
Investigate
    ↓
Graph
    ↓
Evidence
    ↓
Memory
    ↓
Uncertainty
    ↓
Request Evidence
    ↓
Reassess
    ↓
Policy
    ↓
Approval
    ↓
Next Best Action
    ↓
Case
    ↓
Memory
```

The official challenge's stated goal is for the agent to move from uncertain fraud signals to a clear, defensible course of action while maintaining a complete case record and using past investigations to inform future investigations.

**Everything added to this project should strengthen that story.**
