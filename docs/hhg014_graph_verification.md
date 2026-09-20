# Graph Verification Report: Case HHG-014
## Multi-Card Coordinated Device Network Investigation

### 1. Benchmark Case Metadata & Trigger Context

| Field | Dataset Value |
|---|---|
| **Case ID** | `HHG-014` |
| **Opened Timestamp** | `2016-11-22 20:11:00` |
| **Trigger Type** | `analyst_request` |
| **Trigger Text** | `Analyst request: several cards this month show purchases from the same unusual device profile. Review transaction 3478561 on card C13487-K1 and look for related activity.` |
| **Flagged Transaction ID** | `3478561` |
| **Card ID** | `C13487-K1` |
| **Customer ID** | `C13487` |
| **Transaction Amount** | `$74.96` |
| **Channel / ProductCD** | `online` / `ProductCD = 'C'` |
| **Model Risk Score** | `0.05` (Demonstrating why risk score is not ground truth) |

---

### 2. Multi-Hop Graph Discovery & Evidence Path

```
 [Transaction 3478561]
         │
         │ (FROM_DEVICE)
         ▼
 [DeviceProfile: SM-G935F / Android 7.0 / Chrome / 1920x1080 / IP_PROXY:ANONYMOUS]
         │
         ├───────────────────────────────────────────────────────┐
         │ (DEVICE_FOR_TXN)                                      │ (DEVICE_FOR_TXN)
         ▼                                                       ▼
 [Historical Closed Cases]                                [Connected Victim Cards]
  - CC-2649 (C03528, $390.04, undocumented)                - C03528-K1, C09998-K1
  - CC-2971 (C09998, $108.36, undocumented)                - C06617-K1, C09733-K1
  - CC-2985 (C06617, $381.40, undocumented)                - Over 150+ cards sharing device
  - CC-3035 (C09733, $140.95, undocumented)
```

#### 2.1 Transaction Context
- **Query**: `adapter.get_transaction_context("3478561")`
- **Result**:
  - Timestamp: `2016-11-22 16:11:00`
  - Billing Region: `191.0` (Country code: 87.0)
  - Purchaser Email: `yahoo.com` / Recipient: `gmail.com`
  - Device Profile: `SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080`
  - Device Type: `mobile`
  - Proxy Status: `IP_PROXY:ANONYMOUS`
  - Risk Score: `0.05`

#### 2.2 Device Neighbors & Connected Cards
- **Query**: `adapter.get_device_neighbors("SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080")`
- **Result**:
  - The device profile is shared across multiple customer accounts and distinct cards (`C03528-K1`, `C09998-K1`, `C06617-K1`, `C09733-K1`, etc.).
  - Total transactions on this device profile across the graph: over 200 online transactions.

#### 2.3 Historical Closed Cases Memory
- **Query**: `adapter.get_similar_closed_cases(device_profile="SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080")`
- **Result**:
  Identified 4 historical closed cases from August–September 2016 explicitly confirming fraudulent abuse from this exact device and proxy configuration:
  1. **`CC-2649`** (August 27, 2016):
     - Cardholder: `C03528` | Exposure: `$390.04`
     - Pattern: `undocumented` | Outcome: `confirmed_fraud` | Report Filed: `Yes`
     - Actions: `CREATE_CASE|BLOCK_CARD|FILE_REPORT`
     - Analyst Notes: *"Cardholder C03528 reported 3 online purchase(s) they did not make. The purchases came from a Samsung SM-G935F on Chrome for Android behind an anonymous proxy, a device never seen on this account. Two other cardholders reported the same device profile this month. Pattern not matched to a documented typology. Card blocked and reissued."*
  2. **`CC-2971`** (September 3, 2016):
     - Cardholder: `C09998` | Exposure: `$108.36`
     - Pattern: `undocumented` | Outcome: `confirmed_fraud` | Report Filed: `Yes`
  3. **`CC-2985`** (September 3, 2016):
     - Cardholder: `C06617` | Exposure: `$381.40`
     - Pattern: `undocumented` | Outcome: `confirmed_fraud` | Report Filed: `Yes`
  4. **`CC-3035`** (September 4, 2016):
     - Cardholder: `C09733` | Exposure: `$140.95`
     - Pattern: `undocumented` | Outcome: `confirmed_fraud` | Report Filed: `Yes`

---

### 3. Policy Rule Application & SAR Requirements

1. **Undocumented Pattern (Rule R9)**:
   - The attack involves repeated multi-card compromises from a device behind an anonymous proxy, not fitting standard single-card CNP or ATO typologies.
   - Rule R9 strictly governs: *"When activity fits none of the known patterns but the evidence shows coordinated or repeated abuse across customers, recommend CREATE_CASE, FILE_REPORT, and ESCALATE_TO_ANALYST, and describe the pattern in your own words. Do not force it into a known category."*
2. **Shared Origin Infrastructure (Rule R6)**:
   - Multiple cards share an identical device profile (`SM-G935F`) and anonymous proxy.
   - Mandated Actions: `CREATE_CASE` (route: `auto`), `FILE_REPORT` (route: `L2`), and `MONITOR_CONNECTED_CARDS` (route: `auto`).
3. **Card Authorization & Blocking (Rule R2)**:
   - If customer denies transaction: `BLOCK_CARD` (`L1` as exposure $\le \$2,500$).
4. **SAR Filing Mandate**:
   - `sar.file = true` (Mandated by both R6 shared infrastructure, R9 undocumented abuse, and historical precedent where 100% of undocumented cases filed SARs).
   - FinCEN Narrative: Must name the Samsung SM-G935F device, anonymous proxy evasion technique, victim cards `C13487-K1`, `C03528-K1`, and cite prior cases `CC-2649` through `CC-3035`.

---

### 4. Query Latency & Performance

| Operation | Query Name | Latency (ms) | Graph Traversal Scope |
|---|---|---|---|
| **Transaction Context** | `get_transaction_context` | 1.48 ms | 1-hop expansion to Card, Customer, Device, Region, Email |
| **Device Neighbors** | `get_device_neighbors` | 1.22 ms | Multi-hop expansion: Device $\to$ Txns $\to$ Cards $\to$ Customers |
| **Connected Cards** | `get_connected_cards` | 1.84 ms | 2-hop traversal: Card $\to$ Device $\to$ Other Cards |
| **Historical Cases** | `get_similar_closed_cases` | 1.09 ms | Reverse-index lookup: Device $\to$ Txns $\to$ ClosedCase |
| **Transaction Chain** | `get_transaction_chain` | 2.66 ms | Chronological slice: Card $\to$ Transactions $\pm 48\text{h}$ |
