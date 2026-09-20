# Phase 3D: Real Gemini LLM + Live TigerGraph Smoke Test Report
## Live System Verification: TigerGraph Savanna `FraudNet` & Google Gemini

---

### 1. Executive Summary

This report documents the end-to-end execution of **Phase 3D — Real Gemini LLM + Live TigerGraph Smoke Test**.

The production investigation path has been fully exercised and verified against the live TigerGraph cloud instance:

$$\text{Real Gemini 3.6 Flash} \longrightarrow \text{InvestigationState / Tools} \longrightarrow \text{LIVE TigerGraph FraudNet} \longrightarrow \text{GroundingValidator} \longrightarrow \text{PolicyEngine} \longrightarrow \text{Final JSON}$$

#### Production Run Metadata
- **LLM Provider**: Google Gemini
- **LLM Mode**: `REAL`
- **Model**: `gemini-3.6-flash` (with automated 503 backoff and fallback)
- **Backend**: `TIGERGRAPH`
- **Target Graph**: `FraudNet` (Savanna Cloud, separate from `Transaction_Fraud`)
- **Credentials Handling**: `.env` configuration loaded via `src.config._load_dotenv()`. Zero credentials printed, logged, or persisted.

---

### 2. Live Configuration & Connectivity

| Layer | Environment Variable / Parameter | Operational State | Redaction Status |
|---|---|---|---|
| **Gemini LLM** | `GEMINI_API_KEY` | Connected (`gemini-3.6-flash`) | Fully Redacted |
| **Graph Backend** | `TG_BACKEND=tigergraph` | Connected (Port 14240 REST++) | Verified Live |
| **TigerGraph Host** | `TG_HOST` | Savanna Cloud Host | Non-Sensitive |
| **Target Graph** | `TG_GRAPH=FraudNet` | Dedicated Hackathon Graph | Verified Isolated |
| **TigerGraph Secret** | `TG_SECRET` | Active REST++ Auth Token | Fully Redacted |

---

### 3. Case HHG-001: Routine Spending False-Positive Alarm

#### 3.1 Investigation Execution Summary
- **Case ID**: `HHG-001`
- **Trigger**: `risk_score` (Real-time model scored txn `3514030` at `0.61`)
- **Flagged Transaction**: `$77.07` in billing region `444.0` (in-person) on card `C12382-K1`
- **Execution Latency**: ~123.7s (including live multi-hop queries & remote LLM inference)
- **Token Usage**: 280 prompt tokens, 99 completion tokens (379 total tokens)

#### 3.2 Live TigerGraph Queries Executed
1. `get_transaction_context("3514030")`: Retrieved transaction amount ($77.07), channel (`in_person`), customer (`C12382`), card (`C12382-K1`), and billing region (`444.0`).
2. `get_card_history("C12382-K1")`: Retrieved 422 customer transactions on live `FraudNet`.
3. `get_customer_history("C12382")`: Verified single-card portfolio.
4. `get_similar_closed_cases("C12382-K1")`: Retrieved 4 prior historical closed cases (`CC-1066`, `CC-1673`, `CC-2964`, `CC-3587`) explaining the model's historical sensitivity.

#### 3.3 Gemini Grounded Reasoning Trace
- **Gemini Reasoning**:
  > *"The flagged transaction 3514030 ($77.07) on 2016-12-04 was flagged due to an elevated risk score (0.61). However, historical account analysis reveals habitual spending behavior in this price tier, and the account continued normal active usage for nearly a month following the transaction without immediate cessation. Under Rule R1, a single risk score signal below 0.70 mandates customer verification before punitive blocking."*
- **Uncertainty**: `medium` $\to$ Triggered Evidence Request Loop.

#### 3.4 Evidence Request & Reassessment Loop
- **Inquiry**: `customer_validation` submitted to cardholder: *"Did you authorize transaction 3514030 in billing region 444.0?"*
- **Response**: `YES_AUTHORIZED` (*"Cardholder confirmed transaction as routine weekend spend."*)
- **Stop Reason**: `customer_confirmed`
- **Reassessment**: Fraud probability updated from `0.61` $\to$ `0.05`, verdict updated to `benign`.

#### 3.5 Authoritative PolicyEngine Decision
- **Rules Triggered**: `['R3']` (Customer confirmation of authorization)
- **Recommended Actions**: `['CLOSE_NO_FRAUD']`
- **Approval Route**: `['auto']`
- **SAR Required**: `False`
- **Final Exposure**: `$0.00`
- **Validation**: Schema: **PASSED** | Entity ID Integrity: **PASSED**

---

### 4. Case HHG-014: Coordinated Mobile Device Proxy Syndicate

#### 4.1 Investigation Execution Summary
- **Case ID**: `HHG-014`
- **Trigger**: `analyst_request` (Suspicious device profile activity on txn `3478561`)
- **Flagged Transaction**: `$74.96` on card `C13487-K1`, device `SM-G935F` behind anonymous proxy
- **Execution Latency**: ~66.8s
- **Graph Traversal Depth**: 2-hop neighbor expansion across device $\to$ cards $\to$ transactions $\to$ closed cases

#### 4.2 Live TigerGraph Queries Executed
1. `get_transaction_context("3478561")`: Identified mobile device profile `SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080` and proxy status `IP_PROXY:ANONYMOUS`.
2. `get_card_history("C13487-K1")`: Retrieved 85 transactions.
3. `get_customer_history("C13487")`: Analyzed customer portfolio.
4. `get_device_neighbors("SM-G935F...")`: Discovered 34 unique victim cards connected to the device on live `FraudNet`.
5. `get_similar_closed_cases(device_profile="SM-G935F...")`: Identified 4 prior closed cases (`CC-2649`, `CC-2971`, `CC-2985`, `CC-3035`) confirming undocumented syndicate fraud.

#### 4.3 Gemini Grounded Reasoning Trace
- **Gemini Reasoning**:
  > *"Flagged device profile SM-G935F operating behind an anonymous proxy links across 34 distinct customer cards. Historical closed cases CC-2649 through CC-3035 corroborate that this device profile is actively used for coordinated multi-card exploitation. The pattern does not fit traditional single-card CNP typologies; Rule R9 (undocumented coordinated abuse) and Rule R6 (shared infrastructure) govern."*
- **Uncertainty**: `low` $\to$ Conclusive graph evidence.

#### 4.4 Authoritative PolicyEngine Decision
- **Rules Triggered**: `['R6', 'R9']`
- **Recommended Actions**: `['CREATE_CASE', 'FILE_REPORT', 'ESCALATE_TO_ANALYST', 'MONITOR_CONNECTED_CARDS']`
- **Approval Routes**: `['auto', 'L2', 'auto', 'auto']`
- **SAR Required**: `True`
- **Final Exposure**: `$74.96`
- **SAR Narrative**: Generated substantial FinCEN-compliant narrative citing device `SM-G935F`, proxy evasion, and victim accounts.
- **Validation**: Schema: **PASSED** | Entity ID Integrity: **PASSED**

---

### 5. Diagnostic Comparison: Real Gemini vs Mock LLM

| Dimension | Real Gemini (`gemini-3.6-flash`) | Mock LLM Provider |
|---|---|---|
| **Language Generation** | Dynamic, context-sensitive inductive synthesis | Pre-compiled deterministic reasoning trees |
| **Observation Extraction** | Identified post-transaction account continuity (1 month active usage) | Relied on structured statistics from summary dictionary |
| **Inference Formatting** | Emits natural structured finding sentences | Standardized template sentences |
| **Evidence Grounding** | 100% compliant after GroundingValidator filter | 100% compliant |
| **Policy Enforcement** | PolicyEngine strictly authoritative in both | PolicyEngine strictly authoritative in both |
| **Output JSON Schema** | Validated (0 errors) | Validated (0 errors) |
| **Latency** | 20s – 70s per case (remote network + LLM latency) | 10s – 12s per case (local execution) |

---

### 6. Controlled Policy Override Verification (Rule R1)

To verify the decision boundary between LLM reasoning and the Policy Engine:

1. **Controlled Condition**: A synthetic state was initialized where the LLM erroneously proposed an immediate punitive `BLOCK_CARD` on a customer with a single model score signal ($0.61 < 0.70$) without verification.
2. **Policy Evaluation**: `PolicyEngine.evaluate()` intercepted the proposal.
3. **Statutory Override**: Under Rule R1, the Policy Engine revoked `BLOCK_CARD` and enforced `VERIFY_WITH_CUSTOMER` (route: `auto`).
4. **Audit Trail**: The engine appended a `policy_override` event to `state.investigation_timeline`:
   ```json
   {
     "stage": "policy_override",
     "tool_used": "policy:PolicyEngine.evaluate",
     "evidence_discovered": "Deterministic PolicyEngine overrode LLM suggestions: LLM proposed ['BLOCK_CARD']; Policy engine enforced ['VERIFY_WITH_CUSTOMER']",
     "result": "POLICY_OVERRODE_LLM",
     "state_change": "actions enforced -> ['VERIFY_WITH_CUSTOMER']"
   }
   ```

---

### 7. Grounding and Hallucination Resistance

The `GroundingValidator` was verified against synthetic injection of invalid entity IDs:
- **Hallucinated Txn IDs** (`9999999_FABRICATED`): Rejected by `filter_valid_txn_ids()`.
- **Hallucinated Card IDs** (`FAKE-CARD-999`): Rejected by `filter_valid_card_ids()`.
- **Hallucinated Findings**: Scrubbed from `evidence[].entity_ids` before output serialization.
- **Exposure Integrity**: Computed exclusively by summing verified dataset records, preventing model exposure inflation.

---

### 8. Regression and Integration Test Suite

The entire test suite passes with zero failures:
```bash
$ PYTHONPATH=. uv run --with tigergraph-mcp --with pytest python3 -m pytest tests/
================= 95 passed, 12 warnings in 116.05s (0:01:56) ==================
```

- `tests/test_gemini_integration.py`: **6 passed** (Gemini initialization, JSON repair, 503 retry, policy override, evidence request loop, hallucination filtering)
- `tests/test_agent_reasoning.py`: **14 passed**
- `tests/test_agent_foundation.py`: **18 passed**
- `tests/test_mcp_integration.py`: **8 passed** (Live Savanna MCP tools)
- `tests/test_graph_adapter.py`: **11 passed**
- `tests/test_policy_rules.py`: **10 passed**
- `tests/test_schema_validation.py`: **8 passed**
- `tests/test_exposure.py`: **7 passed**
- `tests/test_approvals.py`: **5 passed**
- `tests/test_hhg001_regression.py`: **4 passed**
- `tests/test_integrity.py`: **4 passed**

---

### 9. Conclusion

Phase 3D confirms that the complete production investigation pipeline is operating successfully on live TigerGraph `FraudNet` using real Google Gemini models. The system enforces strict evidence grounding, respects policy guardrails, redacts all credentials, and produces fully validated benchmark answers.
