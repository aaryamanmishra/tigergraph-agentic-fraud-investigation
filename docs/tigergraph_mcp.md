# TigerGraph Model Context Protocol (MCP) Integration Guide
## TigerGraph × Hacker House Goa 2026 — Agentic Fraud Investigation

### 1. Overview & Architecture

The **TigerGraph MCP Server** connects the agentic reasoning runtime to TigerGraph using the standardized Model Context Protocol (MCP). Rather than allowing an LLM to generate unstructured graph queries, the MCP server exposes curated, parameterized GSQL investigation tools.

```
+------------------+          stdio / SSE          +-----------------------+          REST++          +-------------------+
|  Agent Workflow  | <===========================> |  TigerGraph MCP Server | <======================> | TigerGraph Engine |
|  (LangGraph/SDK) |       JSON-RPC 2.0 Tools      | (tigergraph-mcp/stdio)|        Port 14240        |   (Graph / GSQL)  |
+------------------+                               +-----------------------+                          +-------------------+
```

---

### 2. Available Investigation Tools

Only the 8 purpose-built fraud investigation tools are exposed through the MCP layer to eliminate hallucination and unnecessary context expansion.

| Tool Name | Parameters | Description |
|---|---|---|
| `get_transaction_context` | `txn_id: string` | Retrieves transaction amounts, timestamp, channel, card, customer, device profile, proxy status, and risk score. |
| `get_card_history` | `card_id: string, start_time?: string, end_time?: string` | Retrieves ordered transaction history on a card for velocity and spending baseline analysis. |
| `get_customer_history` | `customer_id: string` | Retrieves all cards owned by the customer and complete cross-card activity. |
| `get_connected_cards` | `card_id: string` | Discovers victim cards sharing devices or infrastructure with the target card. |
| `get_device_neighbors` | `device_profile: string` | Explores other cards and customers using the specified device fingerprint. |
| `get_transaction_chain` | `txn_id: string, window_hours?: int` | Retrieves transactions immediately preceding and following a flagged charge. |
| `get_similar_closed_cases`| `card_id?: string, device_profile?: string` | Retrieves historical closed cases (case memory) for similar cards or devices. |
| `detect_card_testing` | `card_id: string, window_start: string` | Deterministic query identifying 3+ small authorizations (<$5) in 1 hour followed by a larger purchase (Policy R5). |
| `write_case` | `case_data: object` | Persists a closed or progressed case vertex and edges back into TigerGraph. |

---

### 3. Server Configuration & Setup

#### 3.1 Claude Desktop / Antigravity MCP Configuration (`mcp.json`)

To connect TigerGraph MCP to your assistant or agent runner:

```json
{
  "mcpServers": {
    "tigergraph-fraud": {
      "command": "python3",
      "args": ["-m", "src.graph.mcp_server"],
      "env": {
        "TG_HOST": "https://savanna.tgcloud.io",
        "TG_REST_PORT": "14240",
        "TG_GRAPH_NAME": "FraudNet",
        "TG_USERNAME": "tigergraph",
        "TG_PASSWORD": "your-password-here",
        "TG_TOKEN": "your-bearer-token-here",
        "TG_BACKEND": "auto"
      }
    }
  }
}
```

#### 3.2 Authentication Modes

1. **TigerGraph Savanna (Cloud Token)**:
   - Provide `TG_TOKEN` obtained from the Savanna Workspace Dashboard.
   - All REST++ and GSQL queries pass `Authorization: Bearer <TG_TOKEN>`.
2. **Community Edition (Basic Auth)**:
   - Provide `TG_USERNAME` and `TG_PASSWORD`.
   - The MCP server authenticates and requests an ephemeral session token via `/gsqlserver/gsql/secure`.
3. **Automated Local Fallback**:
   - If TigerGraph is offline or credentials are unset, the server operates against `src.graph.adapter`'s in-memory graph store, identifying `"source": "in_memory"`.

---

### 4. Example MCP Tool Invocations

#### Example 1: Discovering Shared Device Infrastructure (HHG-014)

**Tool Call Request**:
```json
{
  "name": "get_device_neighbors",
  "arguments": {
    "device_profile": "SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080"
  }
}
```

**Tool Response**:
```json
{
  "query": "get_device_neighbors",
  "inputs": {
    "device_profile": "SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080"
  },
  "results": [
    {
      "device_profile": "SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080",
      "connected_cards": ["C03528-K1", "C06617-K1", "C09733-K1", "C09998-K1", "C13487-K1"],
      "total_txns": 218,
      "recent_txn_ids": ["3478561", "3478540", "3478491"]
    }
  ],
  "evidence_type": "device_neighbors",
  "source": "tigergraph"
}
```

#### Example 2: Historical Case Memory Retrieval

**Tool Call Request**:
```json
{
  "name": "get_similar_closed_cases",
  "arguments": {
    "device_profile": "SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080"
  }
}
```

**Tool Response**:
```json
{
  "query": "get_similar_closed_cases",
  "inputs": {
    "device_profile": "SM-G935F Build/NRD90M | Android 7.0 | chrome 62.0 for android | 1920x1080"
  },
  "results": [
    {
      "case_id": "CC-2649",
      "outcome": "confirmed_fraud",
      "pattern": "undocumented",
      "exposure_usd": 390.04,
      "actions_taken": "CREATE_CASE|BLOCK_CARD|FILE_REPORT",
      "report_filed": "Yes",
      "analyst_notes": "Case CC-2649: cardholder C03528 reported 3 online purchase(s) they did not make. The purchases came from a Samsung SM-G935F on Chrome for Android behind an anonymous proxy..."
    }
  ],
  "evidence_type": "similar_closed_cases",
  "source": "tigergraph"
}
```

---

### 5. Failure Handling & Resilience

1. **Connection Timeouts**: If a TigerGraph query exceeds 5.0 seconds, the adapter catches the `URLError` / `socket.timeout`, logs a warning, and returns an explicit error payload:
   ```json
   {
     "error": true,
     "message": "TigerGraph connection timed out after 5.0s",
     "source": "tigergraph"
   }
   ```
2. **Entity Not Found**: Missing transaction or card IDs return an empty `results: []` array without crashing the agent.
3. **Backend Transparency**: Every tool response carries `"source": "tigergraph"` or `"source": "in_memory"` so the agent and evaluator can verify whether live graph execution occurred.
