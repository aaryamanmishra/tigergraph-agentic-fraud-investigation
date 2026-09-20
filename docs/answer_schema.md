# Official Case Answer Schema Specification
## TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation

### 1. JSON Schema Definition

Every benchmark case must produce an answer file in `cases/<case_id>.json` conforming strictly to the following schema.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "FraudInvestigationCaseAnswer",
  "type": "object",
  "required": [
    "case_id",
    "case",
    "evidence_requests",
    "next_best_actions",
    "sar",
    "stop_reason",
    "tool_calls",
    "tokens",
    "latency_s"
  ],
  "properties": {
    "case_id": {
      "type": "string",
      "pattern": "^HHG-[0-9]{3}$",
      "description": "Identifier from case_pack.csv (e.g. HHG-001)"
    },
    "case": {
      "type": "object",
      "required": [
        "status",
        "verdict",
        "fraud_probability",
        "pattern",
        "pattern_description",
        "affected_txn_ids",
        "first_suspicious_txn_id",
        "connected_card_ids",
        "connected_device_profiles",
        "exposure_usd",
        "evidence",
        "similar_prior_cases",
        "summary",
        "written_to_graph",
        "graph_case_id"
      ],
      "properties": {
        "status": {
          "type": "string",
          "enum": ["open", "closed_fraud", "closed_legitimate", "escalated"]
        },
        "verdict": {
          "type": "string",
          "enum": ["fraud", "legitimate", "uncertain"]
        },
        "fraud_probability": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0
        },
        "pattern": {
          "type": "string",
          "enum": [
            "card_testing",
            "card_not_present_fraud",
            "card_not_present_new_device",
            "out_of_region_use",
            "account_takeover",
            "undocumented",
            "none"
          ]
        },
        "pattern_description": {
          "type": "string",
          "description": "Required when pattern is 'undocumented'; empty string otherwise"
        },
        "affected_txn_ids": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Every transaction identified as part of the fraud episode. Empty if legitimate"
        },
        "first_suspicious_txn_id": {
          "type": "string",
          "description": "Transaction ID where fraud initiated; empty string if legitimate"
        },
        "connected_card_ids": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Sibling cards or other cards linked to the same compromise or device"
        },
        "connected_device_profiles": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Device profiles linking this case to other transactions or cards"
        },
        "exposure_usd": {
          "type": "number",
          "minimum": 0.0,
          "description": "Sum of absolute transaction amounts in affected_txn_ids. 0 if legitimate"
        },
        "evidence": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["claim", "source", "ref", "entity_ids"],
            "properties": {
              "claim": { "type": "string" },
              "source": {
                "type": "string",
                "enum": ["graph", "document", "customer", "external"]
              },
              "ref": { "type": "string" },
              "entity_ids": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }
        },
        "similar_prior_cases": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Closed case IDs from closed_cases_history.csv retrieved as memory"
        },
        "summary": {
          "type": "string",
          "description": "Analyst summary (two to six sentences)"
        },
        "written_to_graph": {
          "type": "boolean"
        },
        "graph_case_id": {
          "type": "string",
          "description": "Vertex ID created in TigerGraph; empty string if not written"
        }
      }
    },
    "evidence_requests": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "asked_after_step", "assumed_response"],
        "properties": {
          "type": {
            "type": "string",
            "enum": ["customer_validation", "step_up_auth", "analyst_info"]
          },
          "asked_after_step": { "type": "integer", "minimum": 1 },
          "assumed_response": { "type": "string" }
        }
      }
    },
    "next_best_actions": {
      "type": "object",
      "required": ["initial", "final", "what_changed"],
      "properties": {
        "initial": {
          "type": "array",
          "items": { "$ref": "#/$defs/actionItem" }
        },
        "final": {
          "type": "array",
          "items": { "$ref": "#/$defs/actionItem" }
        },
        "what_changed": {
          "type": "string",
          "description": "Explanation of change between initial and final actions, or 'nothing'"
        }
      }
    },
    "sar": {
      "type": "object",
      "required": [
        "file",
        "reason",
        "narrative",
        "subjects",
        "total_amount_usd",
        "activity_dates"
      ],
      "properties": {
        "file": { "type": "boolean" },
        "reason": { "type": "string" },
        "narrative": {
          "type": "string",
          "description": "FinCEN-compliant narrative (6-12 sentences) when file is true; empty string if file is false"
        },
        "subjects": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Customer, card, and device IDs named in narrative. Empty if file is false"
        },
        "total_amount_usd": {
          "type": "number",
          "minimum": 0.0,
          "description": "Total suspicious amount. 0 if file is false"
        },
        "activity_dates": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
          },
          "maxItems": 2,
          "description": "Array of [start_date, end_date]. Empty array if file is false"
        }
      }
    },
    "stop_reason": {
      "type": "string",
      "description": "Why investigation concluded"
    },
    "tool_calls": {
      "type": "integer",
      "minimum": 0
    },
    "tokens": {
      "type": "integer",
      "minimum": 0
    },
    "latency_s": {
      "type": "number",
      "minimum": 0.0
    }
  },
  "$defs": {
    "actionItem": {
      "type": "object",
      "required": ["action", "route", "reason"],
      "properties": {
        "action": {
          "type": "string",
          "enum": [
            "ALLOW_TRANSACTION",
            "DECLINE_TRANSACTION",
            "MONITOR_CARD",
            "MONITOR_CONNECTED_CARDS",
            "WARN_CUSTOMER",
            "VERIFY_WITH_CUSTOMER",
            "STEP_UP_AUTH",
            "BLOCK_CARD",
            "BLOCK_ALL_CARDS",
            "GENERATE_REPORT",
            "CREATE_CASE",
            "FILE_REPORT",
            "ESCALATE_TO_ANALYST",
            "CLOSE_NO_FRAUD"
          ]
        },
        "route": {
          "type": "string",
          "enum": ["auto", "L1", "L2"]
        },
        "reason": {
          "type": "string"
        }
      }
    }
  }
}
```

---

### 2. Strict Cross-Field Validation Rules

1. **SAR Invariance**:
   - When `sar.file == true`:
     - `sar.narrative` must not be empty (6–12 sentences addressing Who, What, When, Where, How, Why).
     - `sar.subjects` must not be empty.
     - `sar.total_amount_usd` must equal `case.exposure_usd`.
     - `sar.activity_dates` must contain exactly two dates `["YYYY-MM-DD", "YYYY-MM-DD"]`.
     - `next_best_actions.final` must contain an entry with `"action": "FILE_REPORT"`.
   - When `sar.file == false`:
     - `sar.narrative` must be `""`.
     - `sar.subjects` must be `[]`.
     - `sar.total_amount_usd` must be `0.0`.
     - `sar.activity_dates` must be `[]`.
     - `next_best_actions.final` must NOT contain `"FILE_REPORT"`.

2. **Legitimate Case Invariance**:
   - When `case.verdict == "legitimate"`:
     - `case.affected_txn_ids` must be `[]`.
     - `case.exposure_usd` must be `0.0`.
     - `sar.file` must be `false`.
     - `case.pattern` must be `"none"`.

3. **Approval Route Strictness**:
   - Any `DECLINE_TRANSACTION` action must have `"route": "L1"`.
   - Any `BLOCK_CARD` action with exposure $\le \$2,500$ must have `"route": "L1"`.
   - Any `BLOCK_CARD` action with exposure $> \$2,500$ must have `"route": "L2"`.
   - Any `BLOCK_ALL_CARDS` action must have `"route": "L2"`.
   - Any `FILE_REPORT` action must have `"route": "L2"`.
   - All other 9 actions must have `"route": "auto"`.
