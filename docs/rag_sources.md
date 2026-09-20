# RAG Source Inventory, Trust Tiers, and Anti-Leakage Governance

This document establishes the official source inventory, trust hierarchy, indexing permissions, and anti-leakage quarantine boundaries for the GraphRAG (Graph-Augmented Retrieval) subsystem of the TigerGraph Fraud Investigation Agent.

---

## 1. Governance Objectives & Integrity Principles

1. **Deterministic Authority**: The deterministic `PolicyEngine` remains strictly authoritative. RAG retrieves policy rules and typologies to ground LLM reasoning and explainability; it cannot override statutory policy code.
2. **Strict Anti-Leakage Boundary**: The agent must never possess prior knowledge of benchmark ground-truth answers or manual case evaluations. Indexing benchmark case solutions is strictly forbidden.
3. **Reproducible In-Memory Retrieval**: No heavy external vector database or closed third-party embedding service is required. Retrieval uses heading-aware chunking and deterministic keyword/BM25 scoring.
4. **End-to-End Provenance**: Every retrieved piece of evidence injected into the context window carries a traceable identifier (`GRAPH-xx`, `CASE-xx`, `POLICY-xx`, `TYPOLOGY-xx`).

---

## 2. Document Inventory and Trust Tiers

| Source File / Resource | Trust Tier | Index Status | Content Description & Rationale |
|---|---|---|---|
| `docs/policy_matrix.md` | **Tier 1 (Authoritative Policy)** | **INDEXED** | Canonical 14 actions, Approval Hierarchy (`auto`, `L1`, `L2`), Rules R1–R10, SAR Section 3a criteria, Next-Best-Action evolution. |
| `hackathon_spec.txt` | **Tier 1 (Authoritative Spec)** | **INDEXED** | Official competition problem statement, 5 core typologies + undocumented abuse, investigation lifecycle, evidence loop expectations. |
| `docs/requirements.md` | **Tier 1 (Authoritative Requirements)** | **INDEXED** | Functional requirements FR-1 through FR-9, system thresholds, calibrated probability guidelines. |
| TigerGraph `ClosedCase` vertices | **Tier 1 (Historical Case Memory)** | **GRAPH RETRIEVAL** | 5,565 historical closed cases in `FraudNet` graph (`closed_cases_history.csv`) accessed via `get_similar_closed_cases`. |
| `README.md` | Tier 2 (System Overview) | Excluded | High-level repository orientation; not case-investigation context. |
| `docs/dataset_analysis.md` | Tier 2 (Technical Reference) | Excluded | Data modeling notes and column distributions; engineering context. |
| `docs/graph_design.md` | Tier 2 (Technical Reference) | Excluded | GSQL schema and query definitions; engineering context. |
| `docs/agent_tool_architecture.md` | Tier 2 (Technical Reference) | Excluded | Internal tool and MCP call contracts. |
| `docs/mcp_integration.md` | Tier 2 (Technical Reference) | Excluded | Architecture of official `tigergraph-mcp` vs custom server. |
| `docs/manual_case_investigation.md` | **Tier 3 (Quarantine / Blacklist)** | **STRICTLY EXCLUDED** | Contains human ground-truth investigations of benchmark cases. **LEAKAGE HAZARD**. |
| `docs/hhg001_verification.md` | **Tier 3 (Quarantine / Blacklist)** | **STRICTLY EXCLUDED** | Ground-truth analysis of benchmark case HHG-001. **LEAKAGE HAZARD**. |
| `docs/hhg014_graph_verification.md` | **Tier 3 (Quarantine / Blacklist)** | **STRICTLY EXCLUDED** | Ground-truth analysis of benchmark case HHG-014. **LEAKAGE HAZARD**. |
| `docs/benchmark_coverage_audit.md` | **Tier 3 (Quarantine / Blacklist)** | **STRICTLY EXCLUDED** | Audit of all 20 benchmark cases and outcomes. **LEAKAGE HAZARD**. |
| `docs/real_llm_smoketest.md` | **Tier 3 (Quarantine / Blacklist)** | **STRICTLY EXCLUDED** | Historical execution outputs of benchmark cases. **LEAKAGE HAZARD**. |
| `cases/*` | **Tier 3 (Quarantine / Blacklist)** | **STRICTLY EXCLUDED** | Benchmark case manifests and metadata. |
| `results/*` | **Tier 3 (Quarantine / Blacklist)** | **STRICTLY EXCLUDED** | Serialized evaluation answers and benchmark scores. |

---

## 3. Provenance Identifier Scheme

All evidence chunks retrieved or generated are prefixed with standardized provenance keys:

- `POLICY-R<1-10>`: Specific policy rules from `docs/policy_matrix.md` (e.g. `POLICY-R1`, `POLICY-R6`).
- `POLICY-ACTION`: Canonical action definitions and approval tier constraints.
- `POLICY-SAR`: FinCEN Section 3a filing conditions and exposure thresholds.
- `TYPOLOGY-<NAME>`: Documented fraud typologies (e.g. `TYPOLOGY-CARD-TESTING`, `TYPOLOGY-SHARED-DEVICE`, `TYPOLOGY-UNDOCUMENTED`).
- `CASE-<ID>`: Historical closed cases retrieved directly from TigerGraph (e.g. `CASE-CC-0141`).
- `GRAPH-TXN-<ID>`: Real-time transaction facts and velocity from TigerGraph.
- `GRAPH-DEV-<ID>`: Real-time device compromise facts from TigerGraph.
- `GRAPH-CARD-<ID>`: Real-time multi-card topology facts from TigerGraph.

---

## 4. Enforcement in Code

The exclusion list is hardcoded in `src/rag/sources.py` as `EXCLUDED_PATTERNS`. Any attempt to load, index, or chunk files matching these patterns will raise an immediate validation exception during test and runtime execution.
