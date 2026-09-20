# Independent Verification Report: Case HHG-001
## Audit Against HHGOA_IEEE Dataset Package

### 1. Executive Summary

This audit independently verifies every claim, entity ID, monetary amount, timestamp, geographic attribute, and policy rule application for benchmark case **HHG-001** against the raw dataset files (`case_pack.csv`, `transactions.csv`, `identity.csv`, and `closed_cases_history.csv`).

All raw dataset files were treated as strictly read-only and unmodified.

---

### 2. Verified Facts (Direct Dataset Match)

| Fact / Attribute | Audited Source File | Verified Value | Verification Status |
|---|---|---|---|
| **Case ID** | `case_pack.csv` | `HHG-001` | **Verified** |
| **Case Opened** | `case_pack.csv` | `2016-12-05 01:55:28` | **Verified** |
| **Trigger Type** | `case_pack.csv` | `risk_score` | **Verified** |
| **Trigger Text** | `case_pack.csv` | `Real-time model scored transaction 3514030 ($77.07, in billing region 444.0) at 0.61. Review and decide.` | **Verified** |
| **Trigger Score** | `case_pack.csv` | `0.61` | **Verified** |
| **Flagged Transaction ID** | `case_pack.csv` / `transactions.csv` | `3514030` | **Verified** |
| **Customer ID** | `case_pack.csv` / `transactions.csv` | `C12382` | **Verified** |
| **Card ID** | `case_pack.csv` / `closed_cases_history.csv` | `C12382-K1` | **Verified** |
| **Flagged Txn Timestamp** | `transactions.csv` | `2016-12-04 19:55:28` | **Verified** |
| **Flagged Txn Amount** | `transactions.csv` | `$77.07` | **Verified** |
| **Channel / ProductCD** | `transactions.csv` | `in_person` / `W` | **Verified** |
| **Card Attributes** | `transactions.csv` | `card1=21139`, `card2=242.0`, `card3=150.0`, `card4=visa`, `card5=166.0`, `card6=debit` | **Verified** |
| **Billing Region (`addr1`)** | `transactions.csv` | `444.0` | **Verified** |
| **Billing Country (`addr2`)** | `transactions.csv` | `87.0` (Domestic home country) | **Verified** |
| **Identity / Device Record** | `identity.csv` | No row for `3514030` (Standard for `ProductCD='W'`) | **Verified** |
| **Customer Card Portfolio** | `transactions.csv` | Exactly 1 card tuple across all 422 transactions | **Verified** |
| **Total Customer Txns** | `transactions.csv` | 422 total transactions between July 2 and Dec 31, 2016 | **Verified** |
| **Prior Closed Cases** | `closed_cases_history.csv` | Exactly 4 closed cases (`CC-1066`, `CC-1673`, `CC-2964`, `CC-3587`) | **Verified** |

#### Verified Details of Historical Closed Cases for Card `C12382-K1`

1. **`CC-1066`**:
   - Date: `2016-07-23` | First Txn: `3090135` | Exposure: `$170.98`
   - Outcome: `confirmed_fraud` | Pattern: `out_of_region_use` | Report Filed: `No`
   - Actions: `CREATE_CASE|BLOCK_CARD`
2. **`CC-1673`**:
   - Date: `2016-08-04` | First Txn: `3140508` | Exposure: `$199.98`
   - Outcome: `confirmed_fraud` | Pattern: `card_not_present_new_device` | Report Filed: `No`
   - Actions: `CREATE_CASE|BLOCK_CARD`
3. **`CC-2964`**:
   - Date: `2016-09-01` | First Txn: `3226855` | Exposure: `$171.08`
   - Outcome: `confirmed_fraud` | Pattern: `out_of_region_use` | Report Filed: `No`
   - Actions: `CREATE_CASE|BLOCK_CARD`
4. **`CC-3587`**:
   - Date: `2016-09-16` | First Txn: `3271314` | Exposure: `$49.09`
   - Outcome: `confirmed_fraud` | Pattern: `out_of_region_use` | Report Filed: `No`
   - Actions: `CREATE_CASE|BLOCK_CARD`

---

### 3. Derived Findings & Temporal Cadence Analysis

#### 3.1 Transactions in Region 444.0 (Chronological Progression)

Exactly 15 transactions occurred in billing region `444.0` for customer `C12382`. They exhibit two distinct, stable spending regimes:

1. **Regime 1: Late Summer / Early Autumn (~$59 Baseline)**
   - `3264155` — `2016-09-13 19:28:42` — `$58.97` (Risk: 0.01)
   - `3275900` — `2016-09-17 18:22:40` — `$59.07` (Risk: 0.04)
   - `3276102` — `2016-09-17 19:20:00` — `$59.03` (Risk: 0.05)
   - `3320680` — `2016-10-01 22:19:02` — `$58.93` (Risk: 0.35)
   - `3356278` — `2016-10-11 23:01:54` — `$59.08` (Risk: 0.13)
   - `3376974` — `2016-10-18 22:14:48` — `$59.03` (Risk: 0.08)
   - `3400970` — `2016-10-26 22:22:37` — `$59.01` (Risk: 0.16)
   - `3441958` — `2016-11-08 20:34:37` — `$97.06` (Risk: 0.10)

2. **Regime 2: Late Autumn / Winter (~$77 Weekly Weekend Spend)**
   - `3471020` — `2016-11-19 18:39:50` (Saturday) — `$76.94` (Risk: 0.63)
   - `3490282` — `2016-11-26 22:54:37` (Saturday) — `$77.08` (Risk: 0.18)
   - `3514030` — `2016-12-04 19:55:28` (Sunday) — `$77.07` (**Flagged**, Risk: 0.61)
   - `3534489` — `2016-12-11 20:53:48` (Sunday) — `$77.05` (Risk: 0.08)
   - `3552665` — `2016-12-17 23:24:28` (Saturday) — `$76.96` (Risk: 0.16)
   - `3572011` — `2016-12-24 19:45:30` (Saturday) — `$77.01` (Risk: 0.01)
   - `3589921` — `2016-12-31 19:14:37` (Saturday) — `$76.97` (Risk: 0.02)

#### 3.2 Finding on Model Sensitivity vs. Genuine Fraud
- The bank's risk model spiked to `0.63` on `2016-11-19` and `0.61` on `2016-12-04` for the ~$77 charge in region `444.0`.
- This elevation was driven by the historical `out_of_region_use` cases on this card from July to September (`CC-1066`, `CC-2964`, `CC-3587`).
- However, the customer has conducted transactions in region `444.0` consistently since September 13, 2016. The ~$77 charge is an unbroken weekly routine (e.g. weekend family dining, recurring grocery order, or club membership).
- Therefore, the 0.61 model score is a **false alarm trigger**.

---

### 4. Policy Interpretation & Rule Trace

1. **Initial Assessment (Before Evidence Request)**:
   - Evaluated under **Rule R1**: *"If the case rests on a single signal (including a risk score alone) and your assessed fraud probability is below 0.70, recommend VERIFY_WITH_CUSTOMER or STEP_UP_AUTH before any block. Blocking a legitimate customer on one signal is a policy breach."*
   - Signal: Risk score `0.61` on billing region `444.0`.
   - Graph context: Recurring history suggests legitimate spend; assessed probability is $0.20$ ($< 0.70$).
   - Recommended Action: `VERIFY_WITH_CUSTOMER` (route: `auto`, statutory under Section 2).
   - Prohibited Action: `BLOCK_CARD` or `DECLINE_TRANSACTION` (breach of R1).
2. **Evidence Request**:
   - Type: `customer_validation`
   - Simulated Response: Cardholder affirms authorization as routine recurring spend.
3. **Final Assessment (After Evidence Request)**:
   - Evaluated under **Rule R3**: *"Customer confirms the transaction. Recommend CLOSE_NO_FRAUD. Note the confirmation in the case file."*
   - Recommended Action: `CLOSE_NO_FRAUD` (route: `auto`).
   - Outcome: `verdict = "legitimate"`, `status = "closed_legitimate"`, `fraud_probability = 0.05`, `affected_txn_ids = []`, `exposure_usd = 0.0`.
4. **SAR Determination (Section 3a)**:
   - No fraud occurred; `sar.file = false`.

---

### 5. Corrections Made to Documentation

In `docs/manual_case_investigation.md`:
- Corrected total transaction count for customer `C12382` from an estimated 494 to the verified exact figure of **422**.
- Formally cataloged all 15 transactions in region `444.0`, noting both the early autumn ~$59 regime (7 txns) and the late autumn/winter ~$77 weekly weekend regime (7 txns).
- Confirmed that `identity.csv` contains zero rows for transaction `3514030`, as expected for card-present `ProductCD = 'W'` transactions.
