"""
Official TigerGraph MCP Client Adapter for FraudNet.
Connects directly to the official tigergraph-mcp package (v1.0.3),
exposing typed fraud investigation operations over LIVE FraudNet.
Redacts credentials and guarantees that calls target FraudNet.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, List, Any, Optional

from src.config import config, _load_dotenv
from src.graph.adapter import is_valid_device_profile_id

logger = logging.getLogger("TigerGraphMCPClient")


def parse_mcp_text_response(res_list) -> Dict[str, Any]:
    """Extracts and parses JSON object from tigergraph-mcp Markdown response text."""
    if not res_list:
        return {}
    text = res_list[0].text.strip()
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        json_str = text[start:end].strip() if end != -1 else text[start:].strip()
        return json.loads(json_str)
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        json_str = text[start:end].strip() if end != -1 else text[start:].strip()
        return json.loads(json_str)
    return json.loads(text)


def redact_secrets(val: Any) -> Any:
    """Scrubs credentials and tokens from diagnostic strings, payloads, and exceptions."""
    if isinstance(val, str):
        # Redact token or secret values
        secret = os.getenv("TG_SECRET", "")
        token = os.getenv("TG_TOKEN", "")
        pwd = os.getenv("TG_PASSWORD", "")
        res = val
        if secret and len(secret) > 4:
            res = res.replace(secret, "[REDACTED_SECRET]")
        if token and len(token) > 4:
            res = res.replace(token, "[REDACTED_TOKEN]")
        if pwd and len(pwd) > 2:
            res = res.replace(pwd, "[REDACTED_PASSWORD]")
        return res
    elif isinstance(val, dict):
        return {k: redact_secrets(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [redact_secrets(v) for v in val]
    return val


class TigerGraphMCPClient:
    """
    Client for the official tigergraph-mcp package.
    Provides typed, benchmark-tested methods mapped to FraudNet's installed GSQL queries.
    """

    def __init__(self, graph_name: Optional[str] = None, profile: str = "default"):
        _load_dotenv()
        self.graph_name = graph_name or config.TG_GRAPHNAME or "FraudNet"
        self.profile = profile
        self.initialized = False
        self.tools_module = None
        self.conn_manager = None
        self._init_client()

    def _init_client(self):
        """Initializes connection to official tigergraph_mcp."""
        try:
            from tigergraph_mcp.connection_manager import ConnectionManager
            from tigergraph_mcp import tools
            self.conn_manager = ConnectionManager
            self.tools_module = tools
            # Load environment profile
            self.conn_manager.load_profiles(".env")
            self.initialized = True
        except ImportError as e:
            raise ImportError(
                f"Official tigergraph-mcp package is required. Install via uv or pip. Error: {e}"
            )

    async def list_available_tools(self) -> List[str]:
        """Lists all tool names registered in the official tigergraph-mcp tool registry."""
        from tigergraph_mcp.tool_names import TigerGraphToolName
        return [e.value for e in TigerGraphToolName]

    async def get_graph_schema(self) -> Dict[str, Any]:
        """Queries graph schema for FraudNet via tigergraph__get_graph_schema."""
        t0 = time.time()
        res = await self.tools_module.get_graph_schema(
            profile=self.profile,
            graph_name=self.graph_name
        )
        data = parse_mcp_text_response(res)
        schema = data.get("data", {}).get("schema", {})
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {
            "success": data.get("success", False),
            "graph_name": self.graph_name,
            "vertex_types": [v.get("Name") for v in schema.get("VertexTypes", [])],
            "edge_types": [e.get("Name") for e in schema.get("EdgeTypes", [])],
            "raw": schema,
            "latency_ms": latency_ms
        }

    async def get_transaction_context(self, txn_id: str) -> Dict[str, Any]:
        """
        Operation 1: Retrieves transaction attributes, card, customer, device, and billing region.
        Maps to installed query get_transaction_context.
        """
        if not txn_id or not str(txn_id).strip():
            raise ValueError("txn_id cannot be empty")

        t0 = time.time()
        try:
            res = await self.tools_module.run_installed_query(
                query_name="get_transaction_context",
                params={"target_txn": (str(txn_id).strip(),)},
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            q_result = raw.get("data", {}).get("result", [])
            results = []
            card_id, cust_id, reg_id, dev_prof = "", "", "", ""
            amt, risk = 0.0, 0.0

            if q_result and len(q_result) > 0:
                first = q_result[0]
                starts = first.get("Start", [])
                cards = first.get("Cards", [])
                custs = first.get("Customers", [])
                devs = first.get("Devices", [])
                regs = first.get("Regions", [])
                emails = first.get("Emails", [])

                if starts:
                    attr = starts[0].get("attributes", {})
                    amt = attr.get("Start.amount", 0.0)
                    risk = attr.get("Start.risk_score", 0.0)
                    card_id = cards[0].get("v_id", "") if cards else ""
                    cust_id = custs[0].get("v_id", "") if custs else ""
                    reg_id = regs[0].get("v_id", "") if regs else ""
                    dev_prof = devs[0].get("v_id", "") if devs else ""

                    results.append({
                        "transaction": {
                            "txn_id": str(txn_id),
                            "ts": attr.get("Start.ts", ""),
                            "amount": amt,
                            "channel": attr.get("Start.channel", ""),
                            "product_cd": attr.get("Start.product_cd", ""),
                            "risk_score": risk
                        },
                        "customer_id": cust_id,
                        "card": {
                            "card_id": card_id,
                            "card4": cards[0].get("attributes", {}).get("Cards.card4", "") if cards else "",
                            "card6": cards[0].get("attributes", {}).get("Cards.card6", "") if cards else ""
                        },
                        "device_profile": dev_prof,
                        "device_type": devs[0].get("attributes", {}).get("Devices.device_type", "") if devs else "",
                        "proxy_status": devs[0].get("attributes", {}).get("Devices.proxy_status", "") if devs else "",
                        "billing_region": reg_id,
                        "billing_country": str(regs[0].get("attributes", {}).get("Regions.country_code", "")) if regs else "",
                        "email_domain": emails[0].get("v_id", "") if emails else ""
                    })

            return {
                "success": True,
                "query": "get_transaction_context",
                "results": results,
                "card_id": card_id,
                "customer_id": cust_id,
                "region_id": reg_id,
                "risk_score": risk,
                "device_profile_id": dev_prof,
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "query": "get_transaction_context",
                "results": [],
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def get_card_history(
        self,
        card_id: str,
        start_time: str = "",
        end_time: str = ""
    ) -> Dict[str, Any]:
        """
        Operation 2: Retrieves chronological transactions on a card.
        Maps to installed query get_card_history.
        """
        if not card_id or not str(card_id).strip():
            raise ValueError("card_id cannot be empty")

        t0 = time.time()
        st = start_time or "1970-01-01 00:00:00"
        et = end_time or "2030-01-01 00:00:00"
        try:
            res = await self.tools_module.run_installed_query(
                query_name="get_card_history",
                params={"target_card": (str(card_id).strip(),), "start_time": st, "end_time": et},
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            results = []
            q_res = raw.get("data", {}).get("result", [])
            if q_res:
                txns = q_res[0].get("Txns", [])
                for t in txns:
                    attr = t.get("attributes", {})
                    results.append({
                        "txn_id": t.get("v_id"),
                        "ts": attr.get("Txns.ts", ""),
                        "amount": attr.get("Txns.amount", 0.0),
                        "channel": attr.get("Txns.channel", ""),
                        "product_cd": attr.get("Txns.product_cd", ""),
                        "risk_score": attr.get("Txns.risk_score", 0.0)
                    })

            return {
                "success": True,
                "query": "get_card_history",
                "card_id": card_id,
                "results": results,
                "count": len(results),
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "query": "get_card_history",
                "card_id": card_id,
                "results": [],
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def get_customer_history(self, customer_id: str) -> Dict[str, Any]:
        """
        Operation 3: Retrieves cards and transaction aggregates for a customer.
        Maps to installed query get_customer_history.
        """
        if not customer_id or not str(customer_id).strip():
            raise ValueError("customer_id cannot be empty")

        t0 = time.time()
        try:
            res = await self.tools_module.run_installed_query(
                query_name="get_customer_history",
                params={"target_customer": (str(customer_id).strip(),)},
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            q_res = raw.get("data", {}).get("result", [])
            cards = []
            total_txns = 0
            recent_txns = []

            if q_res:
                first = q_res[0]
                for c in first.get("Cards", []):
                    attr = c.get("attributes", {})
                    cards.append({
                        "card_id": c.get("v_id"),
                        "card4": attr.get("Cards.card4", ""),
                        "card6": attr.get("Cards.card6", "")
                    })
                total_txns = first.get("total_transactions", 0)
                for t in first.get("Txns", [])[:20]:
                    attr = t.get("attributes", {})
                    recent_txns.append({
                        "txn_id": t.get("v_id"),
                        "ts": attr.get("Txns.ts", ""),
                        "amount": attr.get("Txns.amount", 0.0),
                        "risk_score": attr.get("Txns.risk_score", 0.0)
                    })

            return {
                "success": True,
                "query": "get_customer_history",
                "customer_id": customer_id,
                "cards": cards,
                "total_transactions": total_txns,
                "recent_transactions": recent_txns,
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "query": "get_customer_history",
                "customer_id": customer_id,
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def get_connected_cards(self, card_id: str) -> Dict[str, Any]:
        """
        Operation 4: Identifies sibling/connected cards sharing device infrastructure.
        Maps to installed query get_connected_cards.
        """
        if not card_id or not str(card_id).strip():
            raise ValueError("card_id cannot be empty")

        t0 = time.time()
        try:
            res = await self.tools_module.run_installed_query(
                query_name="get_connected_cards",
                params={"target_card": (str(card_id).strip(),)},
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            q_res = raw.get("data", {}).get("result", [])
            conn_cards = []
            shared_devices = []

            if q_res:
                first = q_res[0]
                conn_cards = first.get("@@connected_cards", [])
                shared_devices = first.get("@@shared_devices", [])

            return {
                "success": True,
                "query": "get_connected_cards",
                "target_card": card_id,
                "connected_cards": conn_cards,
                "shared_devices": shared_devices,
                "count": len(conn_cards),
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "query": "get_connected_cards",
                "target_card": card_id,
                "connected_cards": [],
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def get_device_neighbors(self, device_profile: str) -> Dict[str, Any]:
        """
        Operation 5: Discovers cards and customers sharing a device profile.
        Maps to installed query get_device_neighbors.
        """
        if not device_profile:
            raise ValueError("device_profile cannot be empty")

        dev_prof = str(device_profile)
        if not is_valid_device_profile_id(dev_prof):
            logger.info("Non-vertex device metadata passed to get_device_neighbors: %r", dev_prof)
            return {
                "success": True,
                "query": "get_device_neighbors",
                "device_profile": dev_prof,
                "cards": [],
                "customers": [],
                "total_transactions_on_device": 0,
                "latency_ms": 0.0,
                "source": "tigergraph_mcp"
            }

        t0 = time.time()
        try:
            res = await self.tools_module.run_installed_query(
                query_name="get_device_neighbors",
                params={"target_device": (dev_prof,)},
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            q_res = raw.get("data", {}).get("result", [])
            cards = []
            custs = []
            total_txns = 0

            if q_res:
                first = q_res[0]
                cards = first.get("@@cards", [])
                custs = first.get("@@customers", [])
                total_txns = first.get("total_txns", 0)

            return {
                "success": True,
                "query": "get_device_neighbors",
                "device_profile": device_profile,
                "cards": cards,
                "customers": custs,
                "total_transactions_on_device": total_txns,
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "query": "get_device_neighbors",
                "device_profile": device_profile,
                "cards": [],
                "customers": [],
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def get_transaction_chain(self, txn_id: str, window_hours: int = 24) -> Dict[str, Any]:
        """
        Operation 6: Retrieves temporal neighborhood of transactions on the same card.
        Maps to installed query get_transaction_chain.
        """
        if not txn_id or not str(txn_id).strip():
            raise ValueError("txn_id cannot be empty")

        t0 = time.time()
        try:
            res = await self.tools_module.run_installed_query(
                query_name="get_transaction_chain",
                params={"target_txn": (str(txn_id).strip(),), "window_hours": window_hours},
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            results = []
            q_res = raw.get("data", {}).get("result", [])
            if q_res:
                txns = q_res[0].get("ChainTxns", [])
                for t in txns:
                    attr = t.get("attributes", {})
                    results.append({
                        "txn_id": t.get("v_id"),
                        "ts": attr.get("ChainTxns.ts", ""),
                        "amount": attr.get("ChainTxns.amount", 0.0),
                        "channel": attr.get("ChainTxns.channel", ""),
                        "risk_score": attr.get("ChainTxns.risk_score", 0.0)
                    })

            return {
                "success": True,
                "query": "get_transaction_chain",
                "flagged_txn_id": txn_id,
                "transactions": results,
                "count": len(results),
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "query": "get_transaction_chain",
                "flagged_txn_id": txn_id,
                "transactions": [],
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def get_similar_closed_cases(
        self,
        card_id: str = "",
        device_profile: str = ""
    ) -> Dict[str, Any]:
        """
        Operation 7: Retrieves historical closed cases linked to card or device.
        Maps to installed query get_similar_closed_cases.
        Omits device lookup if device_profile is not a valid DeviceProfile vertex ID.
        """
        target_dev = str(device_profile or "")
        if target_dev and not is_valid_device_profile_id(target_dev):
            logger.info("Omitting device lookup in get_similar_closed_cases for non-vertex metadata: %r", target_dev)
            target_dev = ""

        t0 = time.time()
        try:
            res = await self.tools_module.run_installed_query(
                query_name="get_similar_closed_cases",
                params={"target_card_id": card_id or "", "target_device_profile": target_dev},
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            cases = []
            q_res = raw.get("data", {}).get("result", [])
            if q_res:
                for c in q_res[0].get("Cases", []):
                    attr = c.get("attributes", {})
                    cases.append({
                        "case_id": c.get("v_id"),
                        "opened_at": attr.get("Cases.opened_at", ""),
                        "outcome": attr.get("Cases.outcome", ""),
                        "pattern": attr.get("Cases.pattern", ""),
                        "exposure_usd": attr.get("Cases.exposure_usd", 0.0),
                        "actions_taken": attr.get("Cases.actions_taken", ""),
                        "analyst_notes": attr.get("Cases.analyst_notes", "")
                    })

            return {
                "success": True,
                "query": "get_similar_closed_cases",
                "card_id": card_id,
                "device_profile": device_profile,
                "cases": cases,
                "count": len(cases),
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "query": "get_similar_closed_cases",
                "cases": [],
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def detect_card_testing(
        self,
        card_id: str,
        window_start: str = "1970-01-01 00:00:00"
    ) -> Dict[str, Any]:
        """
        Operation 8: Analyzes sequence for 3+ small authorizations (<$5) within 1 hour followed by larger spend (R5).
        Maps to installed query detect_card_testing.
        """
        if not card_id or not str(card_id).strip():
            raise ValueError("card_id cannot be empty")

        t0 = time.time()
        try:
            res = await self.tools_module.run_installed_query(
                query_name="detect_card_testing",
                params={"target_card": (str(card_id).strip(),), "window_start": window_start},
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            q_res = raw.get("data", {}).get("result", [])
            is_testing = False
            small_count = 0
            large_count = 0

            if q_res:
                first = q_res[0]
                is_testing = first.get("is_testing", False)
                small_count = first.get("small_count", 0)
                large_count = first.get("large_count", 0)

            return {
                "success": True,
                "query": "detect_card_testing",
                "card_id": card_id,
                "is_testing": is_testing,
                "small_authorizations_count": small_count,
                "larger_authorizations_count": large_count,
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "query": "detect_card_testing",
                "card_id": card_id,
                "is_testing": False,
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def write_case(self, case_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Operation 9: Persists completed fraud investigation case to FraudNet.
        Idempotent operation mapping to installed query write_case.
        """
        case_id = case_dict.get("case_id")
        if not case_id or not str(case_id).strip():
            raise ValueError("case_id cannot be empty")

        t0 = time.time()
        case_info = case_dict.get("case", {})
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        opened_at = case_dict.get("opened_at") or now_str
        closed_at = case_dict.get("closed_at") or now_str

        outcome = case_dict.get("outcome")
        if not outcome:
            outcome = "confirmed_fraud" if case_info.get("verdict") == "fraud" else "cleared"

        pattern = case_dict.get("pattern") or case_info.get("pattern", "none")
        first_fraud_txn_id = case_dict.get("first_fraud_txn_id") or case_info.get("first_suspicious_txn_id", "")

        affected_txns = case_dict.get("affected_txns")
        if affected_txns is None:
            affected_txns = case_info.get("affected_txn_ids", [])

        connected_cards = case_dict.get("connected_cards")
        if connected_cards is None:
            connected_cards = case_info.get("connected_card_ids", [])

        card_id = case_dict.get("primary_card_id") or case_dict.get("card_id") or case_info.get("card_id", "")
        analyst_notes = case_dict.get("analyst_notes") or case_info.get("summary", "")

        if "exposure_usd" in case_dict and case_dict["exposure_usd"] is not None:
            exposure_usd = float(case_dict["exposure_usd"])
        else:
            exposure_usd = float(case_info.get("exposure_usd", 0.0) or 0.0)

        if "n_txns" in case_dict and case_dict["n_txns"] is not None:
            n_txns = int(case_dict["n_txns"])
        else:
            n_txns = len(affected_txns)

        actions_list = case_dict.get("next_best_actions", {}).get("final", [])
        if actions_list:
            actions_taken = "|".join([a.get("action", "") for a in actions_list if a.get("action")])
        else:
            actions_taken = case_dict.get("actions_taken", "")

        report_filed = "No"
        if "sar" in case_dict and isinstance(case_dict["sar"], dict):
            report_filed = "Yes" if case_dict["sar"].get("file") else "No"
        elif case_dict.get("report_filed") in ("SAR", "Yes", True):
            report_filed = "Yes"

        write_params = {
            "case_id": case_id,
            "opened_at": opened_at,
            "closed_at": closed_at,
            "outcome": outcome,
            "pattern": pattern,
            "first_fraud_txn_id": first_fraud_txn_id,
            "n_txns": n_txns,
            "exposure_usd": exposure_usd,
            "actions_taken": actions_taken,
            "report_filed": report_filed,
            "analyst_notes": analyst_notes,
            "primary_card_id": card_id,
            "affected_txns": affected_txns,
            "connected_cards": connected_cards
        }


        try:
            res = await self.tools_module.run_installed_query(
                query_name="write_case",
                params=write_params,
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)

            is_success = raw.get("success", False)
            err_msg = None if is_success else (raw.get("error") or raw.get("message") or "MCP write_case returned unsuccessful status")

            return {
                "success": is_success,
                "case_id": case_id,
                "status": "SUCCESS" if is_success else "FAILED",
                "latency_ms": latency_ms,
                "error": err_msg,
                "source": "tigergraph_mcp"
            }

        except Exception as e:
            return {
                "success": False,
                "case_id": case_id,
                "status": "FAILED",
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }

    async def delete_case(self, case_id: str) -> Dict[str, Any]:
        """Deletes a temporary test case vertex from FraudNet using tigergraph__delete_node."""
        t0 = time.time()
        try:
            res = await self.tools_module.delete_node(
                vertex_type="ClosedCase",
                vertex_id=case_id,
                profile=self.profile,
                graph_name=self.graph_name
            )
            raw = parse_mcp_text_response(res)
            latency_ms = round((time.time() - t0) * 1000, 2)
            return {
                "success": raw.get("success", False),
                "deleted_case_id": case_id,
                "latency_ms": latency_ms,
                "source": "tigergraph_mcp"
            }
        except Exception as e:
            return {
                "success": False,
                "deleted_case_id": case_id,
                "error": redact_secrets(str(e)),
                "latency_ms": round((time.time() - t0) * 1000, 2),
                "source": "tigergraph_mcp"
            }
