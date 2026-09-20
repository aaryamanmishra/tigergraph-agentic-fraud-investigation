# TigerGraph Live FraudNet Data Loading Strategy
## TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation

**Document Version**: 1.0  
**Target Graph**: `FraudNet` on TigerGraph Savanna Cloud (v4.2.5)  
**Dataset**: HHGOA_IEEE Fraud Benchmark (`transactions.csv`, `identity.csv`, `closed_cases_history.csv`)  

---

## 1. Environment Analysis & Mechanism Comparison

The target environment is a managed TigerGraph Savanna Cloud cluster accessed remotely over HTTPS (`https://tg-2d7fe474-b044-4277-b26c-8c21e6faf617.tg-2635877100.i.tgcloud.io`) from a macOS local development workspace containing the raw dataset files.

Three data loading mechanisms were evaluated:

| Dimension | Option A: GSQL File Loading Job (`RUN LOADING JOB`) | Option B: REST++ Batch Upsert API (`POST /restpp/graph/FraudNet`) | Option C: S3/Cloud Storage Connector |
|:---|:---|:---|:---|
| **File Location Requirement** | Must reside on remote TigerGraph server container disk | Resides locally on client laptop; streamed over REST | Must be hosted in an external AWS S3 or GCS bucket |
| **Prerequisites** | SSH access / local `gsql` CLI / server disk mount | Standard Python `urllib` / HTTP requests | AWS S3 credentials and TigerGraph Cloud connector config |
| **Availability in this Environment** | ❌ No local `gsql` CLI or SSH access to cloud container | ✅ Fully verified and authenticated via Bearer token | ❌ No external cloud bucket configured |
| **Idempotence & Safety** | Natively idempotent | Natively idempotent (upsert semantics) | Natively idempotent |
| **Resumability** | Job-level checkpointing | Chunk/batch state checkpointing (`.load_checkpoint.json`) | Storage-level sync |
| **Schema Compatibility** | Requires local server path mapping | Exact 1:1 mapping with `FraudNet` 7 vertices & 9 edges | Exact 1:1 mapping |

### Decision: Option B — Python-Driven REST++ Batch Upsert
The **REST++ Batch Upsert API** is the only fully supported, reproducible, and verifiable loading mechanism in this environment. It communicates directly over port 443 with bearer tokens minted via `/gsql/v1/tokens`, provides native upsert idempotency, allows fine-grained rate limiting, and supports stateful resumption.

---

## 2. Target Graph Topology & Entity Mapping

The loader ingests raw CSVs into the 7 vertices and 9 edges of `FraudNet`:

```
 [Customer] ────(OWNS)────► [Card] ────(MADE)────► [Transaction] ────(NEXT)────► [Transaction]
                               ▲                       │      │
                               │ (ON_CARD)             │      │ (BILLED_IN)
                               │                       │      ▼
                         [ClosedCase]                  │   [BillingRegion]
                               │ (INVOLVES)            │
                               ▼                       ▼ (FROM_DEVICE)
                         [Transaction]          [DeviceProfile]
                               ▲
                               │ (CONNECTED_TO)
                               │
                            [Card]
```

### Entity Transformation Rules:
1. **`Customer`**: Unique `customer_id` from `transactions.csv` (13,553 entities).
2. **`Card`**: Synthesized key `${customer_id}-K1` (13,553 entities) preserving attributes `card1`–`card6`.
3. **`Transaction`**: Raw `TransactionID` (590,742 entities) with financial, risk, and channel attributes.
4. **`DeviceProfile`**: Composite identity `${DeviceInfo} | ${id_30} | ${id_31} | ${id_33}` (9,706 entities).
5. **`BillingRegion`**: Unique `addr1` codes with `country_code` (`addr2`).
6. **`EmailDomain`**: Unique `P_emaildomain` identities (59 entities).
7. **`ClosedCase`**: Historical investigations from `closed_cases_history.csv` (5,565 entities).

### Edge Transformation Rules:
1. **`OWNS`**: `Customer` $\rightarrow$ `Card` (13,553 edges).
2. **`MADE`**: `Card` $\rightarrow$ `Transaction` (590,742 edges).
3. **`FROM_DEVICE`**: `Transaction` $\rightarrow$ `DeviceProfile` from `identity.csv` (144,432 edges).
4. **`BILLED_IN`**: `Transaction` $\rightarrow$ `BillingRegion` (525,003 edges).
5. **`PURCHASER_EMAIL`**: `Transaction` $\rightarrow$ `EmailDomain` (496,262 edges).
6. **`NEXT`**: Intra-card temporal sequence linking `Transaction[i]` $\rightarrow$ `Transaction[i+1]` with attribute `delta_seconds` (577,189 edges).
7. **`INVOLVES`**: `ClosedCase` $\rightarrow$ `Transaction` (14,955 edges).
8. **`ON_CARD`**: `ClosedCase` $\rightarrow$ `Card` (5,565 edges).
9. **`CONNECTED_TO`**: `ClosedCase` $\rightarrow$ `Card` for cross-card device compromise links (92 edges).

---

## 3. Controlled Phased Execution Strategy

To ensure zero risk to cluster stability and maintain strict verification standards:

### Phase I: Small Representative Pilot Load
- **Scope**:
  - Sample customer: `C12382` (HHG-001 reference customer, 422 transactions, region 444.0).
  - Sample closed cases: `CC-1066`, `CC-1673`, `CC-2964`, `CC-3587`.
  - Sample multi-card device cluster: `C13487-K1`, `C03528-K1`, `C09998-K1` (HHG-014 reference, 114 transactions).
  - Sample closed cases for HHG-014: `CC-2649`, `CC-2971`, `CC-2985`, `CC-3035`.
- **Validation**:
  - Verify all 7 vertex types and 9 edge types receive non-zero counts.
  - Verify HHG-001 and HHG-014 graph traversals against live TigerGraph REST++ queries.
  - Verify idempotence by executing pilot load twice and confirming vertex/edge counts remain identical.

### Phase II: Full Production Data Load
- **Order of Ingestion**:
  1. `ClosedCase`, `ON_CARD`, `INVOLVES`, `CONNECTED_TO` (5,565 cases, fast ~10s).
  2. `DeviceProfile` and `FROM_DEVICE` index (from `identity.csv`).
  3. `Customer`, `Card`, `EmailDomain`, `BillingRegion`, and `OWNS`.
  4. `Transaction`, `MADE`, `BILLED_IN`, `PURCHASER_EMAIL`, and `NEXT`.
- **Batching & Checkpointing**:
  - Batch size: 2,500 entities per HTTP POST payload.
  - Local checkpoint state: `.load_checkpoint.json` tracks processed chunk indices.
  - Exponential backoff retry on HTTP 429 / network errors.

---

## 4. Idempotence & Error Handling

- **Duplicate Prevention**: TigerGraph REST++ upsert replaces attributes or ignores identical keys; edge upsert updates or adds without duplicate creation.
- **Fail-Safe**: All operations strictly target `/restpp/graph/FraudNet`. Under no circumstances is `Transaction_Fraud` addressed.
