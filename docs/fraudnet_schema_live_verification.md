# Live TigerGraph Schema Verification Report: `FraudNet`

**TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation**  
**Verification Timestamp**: `2026-09-20 18:56:30 UTC`  
**Target Cluster**: `https://tg-2d7fe474-b044-4277-b26c-8c21e6faf617.tg-2635877100.i.tgcloud.io`  
**TigerGraph Version**: `TigerGraph version: 4.2.5` (Enterprise Edition)  

---

## 1. Executive Summary

Phase 2A objective has been successfully achieved:
1. The hackathon graph **`FraudNet`** was created and deployed to the live TigerGraph Savanna cluster via a dedicated `SCHEMA_CHANGE JOB`.
2. The deployed topology strictly contains **7 vertex types** and **9 edge types** matching [`src/graph/schema.gsql`](file:///Users/aaryamanmishra/Documents/task4/src/graph/schema.gsql) with 100% attribute and primary key fidelity.
3. The pre-existing demo graph **`Transaction_Fraud`** remains completely untouched and intact with its 18 vertex types, 22 edge types, and 860,141 transactions.
4. No benchmark dataset transactions or CSV records have been loaded into `FraudNet` (all 7 vertex counts verified at exactly 0).

---

## 2. Remote Graph Catalog Verification

Querying `/gsql/v1/schema` and `ls` on the live TigerGraph Savanna instance confirms two isolated graphs:

| Graph Name | Scope | Vertex Types | Edge Types | Data Load Status | Notes |
|:---|:---|:---:|:---:|:---:|:---|
| **`Transaction_Fraud`** | Starter Kit | 18 | 22 | 860,141 transactions | **UNTOUCHED & PRESERVED** |
| **`FraudNet`** | Hackathon | 7 | 9 | 0 records | **DEPLOYED & VERIFIED** |

---

## 3. `FraudNet` Vertex Types Verification (7 Types)

All 7 vertex types were verified against the live TigerGraph metadata endpoint:

| Vertex Type | Primary Key | Data Type | Attributes | Verification Status |
|:---|:---|:---:|:---|:---:|
| **`Customer`** | `customer_id` | `STRING` | *(None)* | **CONFIRMED** |
| **`Card`** | `card_id` | `STRING` | `customer_id` (`STRING`), `card1` (`INT`), `card2` (`FLOAT`), `card3` (`FLOAT`), `card4` (`STRING`), `card5` (`FLOAT`), `card6` (`STRING`) | **CONFIRMED** |
| **`Transaction`** | `txn_id` | `STRING` | `ts` (`DATETIME`), `amount` (`DOUBLE`), `product_cd` (`STRING`), `channel` (`STRING`), `risk_score` (`FLOAT`), `dist1` (`FLOAT`), `dist2` (`FLOAT`), `p_emaildomain` (`STRING`), `r_emaildomain` (`STRING`) | **CONFIRMED** |
| **`DeviceProfile`** | `device_profile_id` | `STRING` | `device_info` (`STRING`), `os` (`STRING`), `browser` (`STRING`), `screen` (`STRING`), `device_type` (`STRING`), `proxy_status` (`STRING`) | **CONFIRMED** |
| **`EmailDomain`** | `domain_id` | `STRING` | *(None)* | **CONFIRMED** |
| **`BillingRegion`** | `region_id` | `STRING` | `country_code` (`FLOAT`) | **CONFIRMED** |
| **`ClosedCase`** | `case_id` | `STRING` | `opened_at` (`DATETIME`), `closed_at` (`DATETIME`), `outcome` (`STRING`), `pattern` (`STRING`), `first_fraud_txn_id` (`STRING`), `n_txns` (`INT`), `exposure_usd` (`DOUBLE`), `actions_taken` (`STRING`), `report_filed` (`STRING`), `analyst_notes` (`STRING`) | **CONFIRMED** |

---

## 4. `FraudNet` Edge Types Verification (9 Types)

All 9 directed multi-hop edge relationships and their reverse edges are active:

| Edge Type | Source Vertex | Target Vertex | Direction | Reverse Edge | Edge Attributes | Status |
|:---|:---|:---|:---:|:---|:---:|:---:|
| **`OWNS`** | `Customer` | `Card` | Directed | `OWNED_BY` | *(None)* | **CONFIRMED** |
| **`MADE`** | `Card` | `Transaction` | Directed | `MADE_BY` | *(None)* | **CONFIRMED** |
| **`FROM_DEVICE`** | `Transaction` | `DeviceProfile` | Directed | `DEVICE_FOR_TXN` | *(None)* | **CONFIRMED** |
| **`PURCHASER_EMAIL`** | `Transaction` | `EmailDomain` | Directed | `EMAIL_FOR_PURCHASER` | *(None)* | **CONFIRMED** |
| **`BILLED_IN`** | `Transaction` | `BillingRegion` | Directed | `REGION_HAS_TXN` | *(None)* | **CONFIRMED** |
| **`NEXT`** | `Transaction` | `Transaction` | Directed | None (Temporal Sequence) | `delta_seconds` (`INT`) | **CONFIRMED** |
| **`INVOLVES`** | `ClosedCase` | `Transaction` | Directed | `INVOLVED_IN_CASE` | *(None)* | **CONFIRMED** |
| **`ON_CARD`** | `ClosedCase` | `Card` | Directed | `CARD_HAD_CASE` | *(None)* | **CONFIRMED** |
| **`CONNECTED_TO`** | `ClosedCase` | `Card` | Directed | `CONNECTED_CASE_CARD` | *(None)* | **CONFIRMED** |

---

## 5. Live Population Audit (Pre-Loading State)

Verified via live REST++ endpoint `GET /restpp/graph/FraudNet/vertices/{vertex_type}?count_only=true`:

| Vertex Type | Current Live Count | Ingestion Expected (Phase 2B) |
|:---|---:|---:|
| `Customer` | **0** | 13,553 |
| `Card` | **0** | 13,553 |
| `Transaction` | **0** | 590,742 |
| `DeviceProfile` | **0** | 9,706 |
| `EmailDomain` | **0** | 59 |
| `BillingRegion` | **0** | 332 |
| `ClosedCase` | **0** | 5,565 |

All vertex counts are currently 0. No raw dataset files have been modified.

---

## 6. Confirmation of Isolation from `Transaction_Fraud`

The starter-kit graph was queried before and after deployment:
- `Transaction_Fraud` vertex types: 18 (unchanged)
- `Transaction_Fraud` edge types: 22 (unchanged)
- `Transaction_Fraud` vertex counts: `Payment_Transaction` = 860,141, `Card` = 999, `Party` = 1,692 (unchanged)
- Local vertex types for `FraudNet` were scoped inside `deploy_fraudnet_schema` ensuring complete name isolation (e.g. `FraudNet.Card` with string primary key `card_id` operates independently from `Transaction_Fraud.Card` with integer primary key `card_number`).

---

## 7. Local vs. Remote Parity Summary

| Dimension | Local Schema (`src/graph/schema.gsql`) | Remote Schema (`FraudNet` in Savanna) | Match |
|:---|:---:|:---:|:---:|
| **Graph Name** | `FraudNet` | `FraudNet` | **EXACT** |
| **Vertex Count** | 7 | 7 | **EXACT** |
| **Edge Count** | 9 | 9 | **EXACT** |
| **Reverse Edges** | 8 reverse edge types | 8 reverse edge types | **EXACT** |
| **Next Edge Attr** | `delta_seconds` (INT) | `delta_seconds` (INT) | **EXACT** |
| **Stats Property** | `OUTDEGREE_BY_EDGETYPE` | `OUTDEGREE_BY_EDGETYPE` | **EXACT** |
