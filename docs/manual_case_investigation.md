# Manual Fraud Case Investigation Reference Workflow
## Case Study: HHG-001 (Customer C12382 / Card C12382-K1)

### 1. Investigation Overview & Benchmark Metadata

This manual investigation serves as the canonical reference design for the agentic investigation pipeline, demonstrating how raw signals, graph traversals, policy constraints, evidence loops, and case memory interact.

| Attribute | Benchmark Specification Value |
|---|---|
| **Case ID** | `HHG-001` |
| **Case Opened** | `2016-12-05 01:55:28` |
| **Trigger Type** | `risk_score` |
| **Trigger Text** | `Real-time model scored transaction 3514030 ($77.07, in billing region 444.0) at 0.61. Review and decide.` |
| **Flagged Transaction ID** | `3514030` |
| **Customer ID** | `C12382` |
| **Card ID** | `C12382-K1` |
| **Transaction Timestamp** | `2016-12-04 19:55:28` |
| **Transaction Amount** | `$77.07` |
| **Channel / Product Code** | `in_person` / `ProductCD = 'W'` |
| **Billing Region / Country** | `addr1 = 444.0` / `addr2 = 87.0` (Domestic) |
| **Card Features** | Visa Debit (`card1 = 21139`, `card4 = visa`, `card6 = debit`) |

---

### 2. Multi-Hop Graph Traversal Steps

#### Step 1: Customer & Card Topology (`Customer → OWNS → Card`)
- **Query**: `query:customer_cards(customer_id="C12382")`
- **Result**: Customer `C12382` owns exactly one active card: `C12382-K1`.
- **Finding**: No sibling cards exist. Compromise cannot spread across customer card portfolio.

#### Step 2: Temporal Transaction Sequence (`Card → MADE → Transaction`)
- **Query**: `query:card_history(card_id="C12382-K1", start_time="2016-07-02", end_time="2016-12-31")`
- **Result**: 422 total transactions across the 6-month period.
  - Primary billing region: `addr1 = 204.0` (over 300 transactions).
  - Channel: Exclusively `in_person` (`ProductCD = 'W'`). No online identity records exist.
- **Micro-Analysis of Billing Region `444.0`**:
  Filtering the card history for transactions in Region `444.0`:
  1. `3471020` — `2016-11-19 18:39:50` — `$76.94` (Saturday evening)
  2. `3490282` — `2016-11-26 22:54:37` — `$77.08` (Saturday night)
  3. `3514030` — `2016-12-04 19:55:28` — `$77.07` (**Flagged Transaction**, Sunday evening)
  4. `3534489` — `2016-12-11 20:53:48` — `$77.05` (Sunday evening)
  5. `3552665` — `2016-12-17 23:24:28` — `$76.96` (Saturday night)
  6. `3572011` — `2016-12-24 19:45:30` — `$77.01` (Saturday evening)
  7. `3589921` — `2016-12-31 19:14:37` — `$76.97` (Saturday evening)
- **Finding**: Transaction `3514030` is not an isolated out-of-region anomaly. It forms part of an established, weekly recurring routine spend ($76.94 to $77.08 every weekend evening).

#### Step 3: Device & Network Neighbors (`Transaction → FROM_DEVICE → DeviceProfile`)
- **Query**: `query:transaction_device(txn_id="3514030")`
- **Result**: Null. The transaction was conducted in person (`ProductCD = 'W'`). No device profile, proxy, or digital identity footprint exists.

#### Step 4: Historical Case Memory Retrieval (`ClosedCase → ON_CARD → Card`)
- **Query**: `query:similar_closed_cases(card_id="C12382-K1")`
- **Result**: 4 historical closed cases retrieved for `C12382-K1`:
  - `CC-1066` (July 2016): Confirmed fraud (`out_of_region_use`, $170.98).
  - `CC-1673` (August 2016): Confirmed fraud (`card_not_present_new_device`, $199.98).
  - `CC-2964` (September 2016): Confirmed fraud (`out_of_region_use`, $171.08).
  - `CC-3587` (September 2016): Confirmed fraud (`out_of_region_use`, $49.09).
- **Finding**: Customer `C12382` suffered historical card-present out-of-region compromises earlier in the year. Consequently, the bank's real-time risk model assigned an elevated risk score (0.61) when region `444.0` appeared. However, the subsequent weekly pattern proves that region `444.0` is now a regular personal transit/weekend location for the cardholder.

---

### 3. Policy & Uncertainty Assessment

1. **Initial Risk & Uncertainty Evaluation**:
   - Model trigger score: `0.61` (moderate risk).
   - Graph evidence: Recurring spend pattern contradicts fraud hypothesis.
   - Fraud probability assessed at `0.22` (weak suspicion, predominantly explained by legitimate recurring behavior).
2. **Application of Policy Rule R1 (Verify Before You Block on a Weak Signal)**:
   - *Condition*: Assessed fraud probability is below 0.70 and rests on a single signal (the 0.61 model score).
   - *Constraint*: Blocking the card or declining the transaction immediately would constitute a policy violation.
   - *Initial Action*: Recommends `VERIFY_WITH_CUSTOMER` (route: `auto`).
3. **Evidence Request Loop**:
   - The agent issues a simulated verification inquiry to customer `C12382`.
   - *Request*: `customer_validation` at step 4.
   - *Assumed Response*: *"Customer confirms they authorized the $77.07 purchase in region 444.0 as their regular weekend recurring expense."*
4. **Application of Policy Rule R3 (Customer Confirms the Transaction)**:
   - *Condition*: Customer affirmatively validates the transaction.
   - *Mandated Action*: `CLOSE_NO_FRAUD` (route: `auto`). Note confirmation in case record.
5. **SAR Determination (Section 3a)**:
   - No fraud occurred. Exposure is $0.00.
   - `sar.file` is `false`.

---

### 4. Ground-Truth Answer JSON for Case HHG-001

```json
{
  "case_id": "HHG-001",
  "case": {
    "status": "closed_legitimate",
    "verdict": "legitimate",
    "fraud_probability": 0.05,
    "pattern": "none",
    "pattern_description": "",
    "affected_txn_ids": [],
    "first_suspicious_txn_id": "",
    "connected_card_ids": [],
    "connected_device_profiles": [],
    "exposure_usd": 0.0,
    "evidence": [
      {
        "claim": "Transaction 3514030 ($77.07) in billing region 444.0 matches a regular weekly recurring weekend expenditure (spanning Nov 19 to Dec 31, between $76.94 and $77.08)",
        "source": "graph",
        "ref": "query:card_history(card_id=C12382-K1)",
        "entity_ids": ["3471020", "3490282", "3514030", "3534489", "3552665", "3572011", "3589921"]
      },
      {
        "claim": "Historical closed cases CC-1066, CC-2964, and CC-3587 recorded out-of-region compromises in different regions, explaining model sensitivity",
        "source": "graph",
        "ref": "query:similar_closed_cases(card_id=C12382-K1)",
        "entity_ids": ["CC-1066", "CC-2964", "CC-3587"]
      },
      {
        "claim": "Customer confirmed authorization of transaction 3514030 as routine weekend spend",
        "source": "customer",
        "ref": "evidence_request:1",
        "entity_ids": ["C12382", "3514030"]
      }
    ],
    "similar_prior_cases": ["CC-1066", "CC-2964", "CC-3587"],
    "summary": "Flagged transaction 3514030 ($77.07) in billing region 444.0 was flagged by the real-time model at 0.61 due to historical out-of-region cases on this card. Graph transaction history revealed an identical recurring weekend spending pattern across seven consecutive weeks ($76.94 to $77.08). The customer confirmed the authorization upon verification. Investigation concluded as a false alarm.",
    "written_to_graph": true,
    "graph_case_id": "CASE-2016-1205-001"
  },
  "evidence_requests": [
    {
      "type": "customer_validation",
      "asked_after_step": 4,
      "assumed_response": "Customer confirms authorization of transaction 3514030 in billing region 444.0 as regular weekend recurring spend"
    }
  ],
  "next_best_actions": {
    "initial": [
      {
        "action": "VERIFY_WITH_CUSTOMER",
        "route": "auto",
        "reason": "R1: Model score 0.61 is a single signal with fraud probability < 0.70; confirm with cardholder before taking blocking action"
      }
    ],
    "final": [
      {
        "action": "CLOSE_NO_FRAUD",
        "route": "auto",
        "reason": "R3: Customer confirmed transaction 3514030 as legitimate routine spend"
      }
    ],
    "what_changed": "Customer verification confirmed the recurring weekend expenditure, resolving uncertainty and transitioning recommendation from initial verification to closing the case as legitimate under R3."
  },
  "sar": {
    "file": false,
    "reason": "Policy Section 3a: No fraud identified; transaction validated by cardholder",
    "narrative": "",
    "subjects": [],
    "total_amount_usd": 0.0,
    "activity_dates": []
  },
  "stop_reason": "Customer confirmation settled the verdict conclusively; spending history validates recurring legitimate behavior. Further investigation is unwarranted.",
  "tool_calls": 4,
  "tokens": 4820,
  "latency_s": 8.4
}
```

---

### 5. Architectural Takeaways for Agent Implementation

1. **Deterministic Baseline Profiling**: The agent must execute a time-series clustering query on `addr1` and amounts to detect recurring cadences before evaluating out-of-region fraud.
2. **Restraint Over Reaction**: Flagging legitimate spend damages customer trust and scores poorly under hackathon criteria. The agent must strictly respect R1.
3. **Structured Traceability**: Every entity ID (transactions `3471020`, `3514030`, closed cases `CC-1066`, `CC-2964`) links directly to grounded dataset rows.
