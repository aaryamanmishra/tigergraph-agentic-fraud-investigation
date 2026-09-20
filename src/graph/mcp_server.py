"""
TigerGraph Model Context Protocol (MCP) Server.
Implements standard JSON-RPC 2.0 over stdio for graph investigation tools.
"""

import sys
import json
import logging
from typing import Dict, Any

from src.graph.adapter import get_graph_adapter

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("TigerGraphMCP")


TOOLS = [
    {
        "name": "get_transaction_context",
        "description": "Retrieves transaction attributes, customer, card, channel, device profile, proxy status, and risk score.",
        "inputSchema": {
            "type": "object",
            "required": ["txn_id"],
            "properties": {
                "txn_id": {"type": "string", "description": "Transaction ID"}
            }
        }
    },
    {
        "name": "get_card_history",
        "description": "Retrieves chronological transactions on a card for velocity, amount, and region analysis.",
        "inputSchema": {
            "type": "object",
            "required": ["card_id"],
            "properties": {
                "card_id": {"type": "string", "description": "Card identifier"},
                "start_time": {"type": "string", "description": "Optional start datetime YYYY-MM-DD HH:MM:SS"},
                "end_time": {"type": "string", "description": "Optional end datetime YYYY-MM-DD HH:MM:SS"}
            }
        }
    },
    {
        "name": "get_customer_history",
        "description": "Retrieves all cards owned by the customer and aggregated transaction activity.",
        "inputSchema": {
            "type": "object",
            "required": ["customer_id"],
            "properties": {
                "customer_id": {"type": "string", "description": "Customer ID"}
            }
        }
    },
    {
        "name": "get_device_neighbors",
        "description": "Discovers other cards and customers sharing a specific device profile.",
        "inputSchema": {
            "type": "object",
            "required": ["device_profile"],
            "properties": {
                "device_profile": {"type": "string", "description": "Canonical device profile string"}
            }
        }
    },
    {
        "name": "get_connected_cards",
        "description": "Finds sibling or other victim cards connected through shared devices or infrastructure.",
        "inputSchema": {
            "type": "object",
            "required": ["card_id"],
            "properties": {
                "card_id": {"type": "string", "description": "Target card ID"}
            }
        }
    },
    {
        "name": "get_transaction_chain",
        "description": "Retrieves transactions immediately preceding and following a flagged charge on the same card.",
        "inputSchema": {
            "type": "object",
            "required": ["txn_id"],
            "properties": {
                "txn_id": {"type": "string", "description": "Transaction ID"},
                "window_hours": {"type": "integer", "default": 24}
            }
        }
    },
    {
        "name": "get_similar_closed_cases",
        "description": "Retrieves historical closed cases matching a card or device profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "card_id": {"type": "string", "description": "Card ID"},
                "device_profile": {"type": "string", "description": "Device profile string"}
            }
        }
    },
    {
        "name": "detect_card_testing",
        "description": "Analyzes sequence for 3+ small authorizations (<$5) within 1 hour followed by larger spend (R5).",
        "inputSchema": {
            "type": "object",
            "required": ["card_id", "window_start"],
            "properties": {
                "card_id": {"type": "string", "description": "Card ID"},
                "window_start": {"type": "string", "description": "Window start datetime"}
            }
        }
    },
    {
        "name": "write_case",
        "description": "Persists an investigated fraud case vertex and edges back into TigerGraph.",
        "inputSchema": {
            "type": "object",
            "required": ["case_data"],
            "properties": {
                "case_data": {"type": "object", "description": "Complete case dictionary conforming to answer schema"}
            }
        }
    }
]


def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    adapter = get_graph_adapter()
    if name == "get_transaction_context":
        return adapter.get_transaction_context(arguments.get("txn_id", ""))
    elif name == "get_card_history":
        return adapter.get_card_history(
            arguments.get("card_id", ""),
            arguments.get("start_time", ""),
            arguments.get("end_time", "")
        )
    elif name == "get_customer_history":
        return adapter.get_customer_history(arguments.get("customer_id", ""))
    elif name == "get_device_neighbors":
        return adapter.get_device_neighbors(arguments.get("device_profile", ""))
    elif name == "get_connected_cards":
        return adapter.get_connected_cards(arguments.get("card_id", ""))
    elif name == "get_transaction_chain":
        return adapter.get_transaction_chain(
            arguments.get("txn_id", ""),
            arguments.get("window_hours", 24)
        )
    elif name == "get_similar_closed_cases":
        return adapter.get_similar_closed_cases(
            arguments.get("card_id", ""),
            arguments.get("device_profile", "")
        )
    elif name == "detect_card_testing":
        return adapter.detect_card_testing(
            arguments.get("card_id", ""),
            arguments.get("window_start", "")
        )
    elif name == "write_case":
        return adapter.write_case(arguments.get("case_data", {}))
    else:
        raise ValueError(f"Unknown tool: '{name}'")


def run_stdio_server():
    logger.info("TigerGraph MCP Stdio Server started.")
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            msg_id = req.get("id")

            if method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                params = req.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = handle_tool_call(tool_name, arguments)
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                    }
                }
            elif method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "tigergraph-fraud-mcp", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                }
            else:
                resp = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
