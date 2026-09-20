# TigerGraph Schema Design & GSQL Specification
## TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation

### 1. Minimal Graph Schema Architecture

The graph model maps the financial topology, identity infrastructure, and historical investigation memory into TigerGraph. It enables sub-second multi-hop graph traversals for customer profiling, transaction sequencing, device fingerprint clustering, and case retrieval.

```
 [Customer] ────(OWNS)────► [Card] ────(MADE)────► [Transaction] ────(NEXT)────► [Transaction]
                              ▲                       │      │
                              │ (ON_CARD)             │      │ (BILLED_IN)
                              │                       │      ▼
                        [ClosedCase]                  │   [BillingRegion]
                        [InvestigatedCase]            │
                              │ (INVOLVES)            │ (FROM_DEVICE)
                              ▼                       ▼
                        [Transaction]          [DeviceProfile]
                              ▲
                              │ (CONNECTED_TO)
                              │
                           [Card]
```

---

### 2. Vertex & Edge Schema Definitions

#### 2.1 Vertex Types

```gsql
CREATE VERTEX Customer (
    PRIMARY_ID customer_id STRING,
    created_at DATETIME
) WITH STATS="OUTDEGREE";

CREATE VERTEX Card (
    PRIMARY_ID card_id STRING,
    customer_id STRING,
    card1 INT,
    card2 FLOAT,
    card3 FLOAT,
    card4 STRING,    // Network: visa, mastercard, discover, amex
    card5 FLOAT,
    card6 STRING,    // Type: credit, debit
    is_blocked BOOL DEFAULT false,
    is_monitored BOOL DEFAULT false
) WITH STATS="OUTDEGREE";

CREATE VERTEX Transaction (
    PRIMARY_ID txn_id STRING,
    ts DATETIME,
    amount DOUBLE,
    product_cd STRING,   // W (in-person), C, H, R, S (online)
    channel STRING,      // in_person, online
    risk_score FLOAT,
    dist1 FLOAT,
    dist2 FLOAT,
    p_emaildomain STRING,
    r_emaildomain STRING
) WITH STATS="OUTDEGREE";

CREATE VERTEX DeviceProfile (
    PRIMARY_ID device_profile_id STRING, // Composite: DeviceInfo|OS|Browser|Screen
    device_info STRING,
    os STRING,
    browser STRING,
    screen STRING,
    device_type STRING,                  // mobile, desktop
    proxy_status STRING                  // IP_PROXY:ANONYMOUS, IP_PROXY:HIDDEN, etc.
) WITH STATS="OUTDEGREE";

CREATE VERTEX BillingRegion (
    PRIMARY_ID region_id STRING,         // addr1 code
    country_code FLOAT                   // addr2 code (87 = domestic)
) WITH STATS="OUTDEGREE";

CREATE VERTEX EmailDomain (
    PRIMARY_ID domain_id STRING
) WITH STATS="OUTDEGREE";

CREATE VERTEX ClosedCase (
    PRIMARY_ID case_id STRING,           // e.g. CC-0141 or HHG-014 (investigated)
    opened_at DATETIME,
    closed_at DATETIME,
    outcome STRING,                      // confirmed_fraud, cleared
    pattern STRING,                      // card_testing, card_not_present_fraud, etc.
    first_fraud_txn_id STRING,
    n_txns INT,
    exposure_usd DOUBLE,
    actions_taken STRING,
    report_filed STRING,                 // Yes, No
    analyst_notes STRING
) WITH STATS="OUTDEGREE";
```

#### 2.2 Edge Types

```gsql
CREATE DIRECTED EDGE OWNS (FROM Customer, TO Card) WITH REVERSE_EDGE="OWNED_BY";
CREATE DIRECTED EDGE MADE (FROM Card, TO Transaction) WITH REVERSE_EDGE="MADE_BY";
CREATE DIRECTED EDGE FROM_DEVICE (FROM Transaction, TO DeviceProfile) WITH REVERSE_EDGE="DEVICE_FOR_TXN";
CREATE DIRECTED EDGE BILLED_IN (FROM Transaction, TO BillingRegion) WITH REVERSE_EDGE="REGION_HAS_TXN";
CREATE DIRECTED EDGE PURCHASER_EMAIL (FROM Transaction, TO EmailDomain) WITH REVERSE_EDGE="EMAIL_FOR_PURCHASER";
CREATE DIRECTED EDGE RECIPIENT_EMAIL (FROM Transaction, TO EmailDomain) WITH REVERSE_EDGE="EMAIL_FOR_RECIPIENT";
CREATE DIRECTED EDGE NEXT (FROM Transaction, TO Transaction, delta_seconds INT);
CREATE DIRECTED EDGE INVOLVES (FROM ClosedCase, TO Transaction) WITH REVERSE_EDGE="INVOLVED_IN_CASE";
CREATE DIRECTED EDGE ON_CARD (FROM ClosedCase, TO Card) WITH REVERSE_EDGE="CARD_HAD_CASE";
CREATE DIRECTED EDGE CONNECTED_TO (FROM ClosedCase, TO Card) WITH REVERSE_EDGE="CONNECTED_CASE_CARD";
```

---

### 3. Core Parameterized GSQL Queries

#### 3.1 `card_history`: Chronological Sequence & Baseline
Retrieves the complete transaction sequence for a card within an optional time window, establishing spending velocity, product categories, and baseline billing regions.

```gsql
CREATE QUERY card_history(VERTEX<Card> target_card, DATETIME start_time, DATETIME end_time) FOR GRAPH FraudNet {
    ListAccum<EDGE> @@txn_edges;
    
    Start = {target_card};
    Txns = SELECT t FROM Start:s -(MADE:e)- Transaction:t
           WHERE t.ts >= start_time AND t.ts <= end_time
           ACCUM @@txn_edges += e
           ORDER BY t.ts ASC;
           
    PRINT Txns[Txns.txn_id, Txns.ts, Txns.amount, Txns.channel, Txns.product_cd, Txns.risk_score];
}
```

#### 3.2 `device_neighbors`: Shared Infrastructure & Multi-Card Compromise
Finds all other cards, customers, and transactions linked to a given device profile. Essential for detecting shared-origin attacks (Policy R6) and undocumented botnet/proxy fraud (Policy R9).

```gsql
CREATE QUERY device_neighbors(VERTEX<DeviceProfile> target_device) FOR GRAPH FraudNet {
    SumAccum<INT> @shared_txns;
    SetAccum<STRING> @@connected_cards;
    SetAccum<STRING> @@connected_customers;
    
    Start = {target_device};
    Txns = SELECT t FROM Start -(DEVICE_FOR_TXN)- Transaction:t;
    Cards = SELECT c FROM Txns -(MADE_BY)- Card:c
            ACCUM @@connected_cards += c.card_id;
    Customers = SELECT cust FROM Cards -(OWNED_BY)- Customer:cust
                ACCUM @@connected_customers += cust.customer_id;
                
    PRINT @@connected_cards, @@connected_customers, Txns.size() AS total_txns_on_device;
}
```

#### 3.3 `card_testing_detector`: Rapid Sub-$5 Authorization Scanner
Detects sequences of 3 or more small authorizations ($< \$5.00$) within an hour followed by a larger transaction, satisfying Policy R5.

```gsql
CREATE QUERY card_testing_detector(VERTEX<Card> target_card, DATETIME window_start) FOR GRAPH FraudNet {
    OrAccum @is_testing;
    ListAccum<VERTEX<Transaction>> @@small_txns;
    ListAccum<VERTEX<Transaction>> @@large_txns;
    
    Start = {target_card};
    Txns = SELECT t FROM Start -(MADE)- Transaction:t
           WHERE t.ts >= window_start AND t.ts <= datetime_add(window_start, INTERVAL 1 HOUR)
           ORDER BY t.ts ASC;
           
    FOREACH tx IN Txns DO
        IF tx.amount < 5.00 AND tx.channel == "online" THEN
            @@small_txns += tx;
        ELSE IF tx.amount > 50.00 THEN
            @@large_txns += tx;
        END IF;
    END;
    
    PRINT @@small_txns.size() AS small_count, @@large_txns.size() AS large_count,
          (@@small_txns.size() >= 3 AND @@large_txns.size() >= 1) AS pattern_matched;
}
```

#### 3.4 `similar_closed_cases`: Case Memory Retrieval
Identifies prior closed cases that share cards, devices, or similar fraud patterns, grounding the agent in historical bank precedent.

```gsql
CREATE QUERY similar_closed_cases(VERTEX<Card> target_card, STRING target_device_id) FOR GRAPH FraudNet {
    SetAccum<STRING> @@matched_case_ids;
    
    StartCard = {target_card};
    CasesOnCard = SELECT c FROM StartCard -(CARD_HAD_CASE)- ClosedCase:c
                  ACCUM @@matched_case_ids += c.case_id;
                  
    IF target_device_id != "" THEN
        StartDev = {DeviceProfile: target_device_id};
        DevTxns = SELECT t FROM StartDev -(DEVICE_FOR_TXN)- Transaction:t;
        DevCases = SELECT c FROM DevTxns -(INVOLVED_IN_CASE)- ClosedCase:c
                   ACCUM @@matched_case_ids += c.case_id;
    END IF;
    
    Cases = {ClosedCase: @@matched_case_ids};
    PRINT Cases[Cases.case_id, Cases.outcome, Cases.pattern, Cases.exposure_usd, Cases.actions_taken, Cases.analyst_notes];
}
```

#### 3.5 `write_case`: Graph Persistence of Investigated Case
Inserts newly resolved benchmark cases into TigerGraph, linking the case to affected transactions, the primary card, and connected sibling cards.

```gsql
CREATE QUERY write_case(
    STRING case_id,
    DATETIME opened_at,
    DATETIME closed_at,
    STRING outcome,
    STRING pattern,
    STRING first_fraud_txn_id,
    INT n_txns,
    DOUBLE exposure_usd,
    STRING actions_taken,
    STRING report_filed,
    STRING analyst_notes,
    STRING primary_card_id,
    LIST<STRING> affected_txns,
    LIST<STRING> connected_cards
) FOR GRAPH FraudNet {
    INSERT INTO ClosedCase (
        PRIMARY_ID, opened_at, closed_at, outcome, pattern,
        first_fraud_txn_id, n_txns, exposure_usd, actions_taken,
        report_filed, analyst_notes
    ) VALUES (
        case_id, opened_at, closed_at, outcome, pattern,
        first_fraud_txn_id, n_txns, exposure_usd, actions_taken,
        report_filed, analyst_notes
    );
    
    INSERT INTO ON_CARD (FROM, TO) VALUES (case_id, primary_card_id);
    
    FOREACH tx IN affected_txns DO
        INSERT INTO INVOLVES (FROM, TO) VALUES (case_id, tx);
    END;
    
    FOREACH cc IN connected_cards DO
        INSERT INTO CONNECTED_TO (FROM, TO) VALUES (case_id, cc);
    END;
    
    PRINT "Case successfully persisted to graph" AS result;
}
```

---

### 4. Integration with TigerGraph MCP

The queries above are exposed to the agentic workflow as MCP tools using the standard TigerGraph MCP Server:
- `query_card_history`
- `query_device_neighbors`
- `query_card_testing_detector`
- `query_similar_closed_cases`
- `execute_write_case`

When TigerGraph Savanna or Community Edition is active, the agent queries the graph directly over MCP. In standalone or offline testing modes, an in-memory graph adapter with an identical interface provides full reproducibility without external dependencies.
