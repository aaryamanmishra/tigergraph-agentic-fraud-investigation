"""
Typed Tool Contracts for TigerGraph Fraud Investigation Agent.
Provides strict, validated interfaces over graph investigation operations.
Implements Requirement #4 and #5 (Typed Tool Contracts & Context-Size Control).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import time
import logging

from src.graph.adapter import GraphAdapter, get_graph_adapter
from src.agent.tools.summary import EvidenceSummarizer

logger = logging.getLogger(__name__)



@dataclass
class ToolExecutionResult:
    """Standardized output wrapper for all tool calls."""
    success: bool
    tool_name: str
    source: str
    latency_ms: float
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "source": self.source,
            "latency_ms": self.latency_ms,
            "data": self.data,
            "error": self.error
        }


class InvestigationTools:
    """
    Typed investigation tool suite wrapping the GraphAdapter.
    Equipped with automatic analytical summarization for large query payloads.
    """

    def __init__(self, adapter: Optional[GraphAdapter] = None):
        self.adapter = adapter or get_graph_adapter()

    def get_transaction_context(self, txn_id: str) -> ToolExecutionResult:
        """
        Retrieves complete transaction context including customer, card, channel,
        device profile, proxy status, billing region, and real-time risk score.
        """
        t0 = time.time()
        try:
            if not txn_id or not str(txn_id).strip():
                raise ValueError("Transaction ID cannot be empty.")
            res = self.adapter.get_transaction_context(str(txn_id).strip())
            lat = round((time.time() - t0) * 1000, 2)
            results = res.get("results", [])
            item = results[0] if results else {}

            return ToolExecutionResult(
                success=True,
                tool_name="get_transaction_context",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data={
                    "txn_id": str(txn_id),
                    "found": len(results) > 0,
                    "transaction": item.get("transaction", {}),
                    "customer_id": item.get("customer_id", ""),
                    "card": item.get("card", {}),
                    "device_profile": item.get("device_profile", ""),
                    "device_type": item.get("device_type", ""),
                    "proxy_status": item.get("proxy_status", ""),
                    "billing_region": item.get("billing_region", ""),
                    "billing_country": item.get("billing_country", ""),
                    "email_domain": item.get("email_domain", "")
                }
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                tool_name="get_transaction_context",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=str(e)
            )

    def get_card_history(
        self,
        card_id: str,
        start_time: str = "",
        end_time: str = "",
        flagged_txn_id: str = "",
        flagged_region: str = "",
        summarize: bool = True
    ) -> ToolExecutionResult:
        """
        Retrieves transaction history for a card.
        When summarize=True (default), computes statistical dimensions and representative samples
        to prevent dumping thousands of records into prompt context.
        """
        t0 = time.time()
        try:
            if not card_id or not str(card_id).strip():
                raise ValueError("Card ID cannot be empty.")

            res = self.adapter.get_card_history(
                card_id=str(card_id).strip(),
                start_time=start_time,
                end_time=end_time
            )
            lat = round((time.time() - t0) * 1000, 2)
            raw_txns = res.get("results", [])

            if summarize:
                summary = EvidenceSummarizer.summarize_card_history(
                    txns=raw_txns,
                    flagged_txn_id=flagged_txn_id,
                    flagged_region=flagged_region
                )
                output_data = {
                    "card_id": card_id,
                    "summary_mode": True,
                    "summary": summary
                }
            else:
                output_data = {
                    "card_id": card_id,
                    "summary_mode": False,
                    "total_transactions": len(raw_txns),
                    "transactions": raw_txns
                }

            return ToolExecutionResult(
                success=True,
                tool_name="get_card_history",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data=output_data
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                tool_name="get_card_history",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=str(e)
            )

    def get_customer_history(self, customer_id: str, summarize: bool = True) -> ToolExecutionResult:
        """
        Retrieves all cards owned by the customer and multi-card activity.
        """
        t0 = time.time()
        try:
            if not customer_id or not str(customer_id).strip():
                raise ValueError("Customer ID cannot be empty.")

            res = self.adapter.get_customer_history(customer_id=str(customer_id).strip())
            lat = round((time.time() - t0) * 1000, 2)
            results = res.get("results", [])
            item = results[0] if results else {}

            if summarize:
                summary = EvidenceSummarizer.summarize_customer_portfolio(item)
                output_data = {"customer_id": customer_id, "summary": summary}
            else:
                output_data = {"customer_id": customer_id, **item}

            return ToolExecutionResult(
                success=True,
                tool_name="get_customer_history",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data=output_data
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                tool_name="get_customer_history",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=str(e)
            )

    def get_connected_cards(self, card_id: str) -> ToolExecutionResult:
        """
        Discovers sibling cards or victim cards connected via shared device footprints.
        """
        t0 = time.time()
        try:
            if not card_id:
                raise ValueError("Card ID cannot be empty.")
            res = self.adapter.get_connected_cards(card_id=str(card_id).strip())
            lat = round((time.time() - t0) * 1000, 2)
            results = res.get("results", [])
            item = results[0] if results else {}

            cards = item.get("connected_cards", [])
            devices = item.get("shared_devices", [])

            return ToolExecutionResult(
                success=True,
                tool_name="get_connected_cards",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data={
                    "card_id": card_id,
                    "connected_card_count": len(cards),
                    "connected_cards": cards,
                    "shared_device_count": len(devices),
                    "shared_devices": devices,
                    "is_multi_card_network": len(cards) > 0
                }
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                tool_name="get_connected_cards",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=str(e)
            )

    def get_device_neighbors(self, device_profile: str, summarize: bool = True) -> ToolExecutionResult:
        """
        Identifies cards and accounts that share a specific device footprint.
        """
        t0 = time.time()
        try:
            if not device_profile:
                raise ValueError("Device profile cannot be empty.")
            res = self.adapter.get_device_neighbors(device_profile=str(device_profile).strip())
            lat = round((time.time() - t0) * 1000, 2)
            results = res.get("results", [])
            item = results[0] if results else {}

            if summarize:
                summary = EvidenceSummarizer.summarize_device_network(item)
                output_data = summary
            else:
                output_data = item

            return ToolExecutionResult(
                success=True,
                tool_name="get_device_neighbors",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data=output_data
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                tool_name="get_device_neighbors",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=str(e)
            )

    def get_transaction_chain(self, txn_id: str, window_hours: int = 24) -> ToolExecutionResult:
        """
        Retrieves preceding and subsequent transactions on the same card within a temporal window.
        """
        t0 = time.time()
        try:
            if not txn_id:
                raise ValueError("Transaction ID cannot be empty.")
            res = self.adapter.get_transaction_chain(txn_id=str(txn_id).strip(), window_hours=window_hours)
            lat = round((time.time() - t0) * 1000, 2)
            txns = res.get("results", [])

            return ToolExecutionResult(
                success=True,
                tool_name="get_transaction_chain",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data={
                    "txn_id": txn_id,
                    "window_hours": window_hours,
                    "total_chain_transactions": len(txns),
                    "chain_transactions": txns
                }
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                tool_name="get_transaction_chain",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=str(e)
            )

    def get_similar_closed_cases(
        self,
        card_id: str = "",
        device_profile: str = "",
        limit: int = 10
    ) -> ToolExecutionResult:
        """
        Retrieves historical closed cases matching the card or device profile.
        """
        t0 = time.time()
        try:
            res = self.adapter.get_similar_closed_cases(
                card_id=str(card_id or "").strip(),
                device_profile=str(device_profile or "").strip()
            )
            lat = round((time.time() - t0) * 1000, 2)
            cases = res.get("results", [])

            return ToolExecutionResult(
                success=True,
                tool_name="get_similar_closed_cases",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data={
                    "card_id": card_id,
                    "device_profile": device_profile,
                    "total_similar_cases": len(cases),
                    "cases": cases[:limit]
                }
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                tool_name="get_similar_closed_cases",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=str(e)
            )

    def detect_card_testing(self, card_id: str, window_start: str) -> ToolExecutionResult:
        """
        Detects 3+ small authorizations (<$5.00) in 1 hour followed by a larger transaction.
        """
        t0 = time.time()
        try:
            if not card_id or not window_start:
                raise ValueError("Card ID and window_start are required.")
            res = self.adapter.detect_card_testing(card_id=str(card_id).strip(), window_start=window_start)
            lat = round((time.time() - t0) * 1000, 2)
            results = res.get("results", [])
            item = results[0] if results else {}

            return ToolExecutionResult(
                success=True,
                tool_name="detect_card_testing",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data={
                    "card_id": card_id,
                    "window_start": window_start,
                    "is_testing": item.get("is_testing", False),
                    "small_auth_count": item.get("small_auth_count", 0),
                    "large_auth_count": item.get("large_auth_count", 0)
                }
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            return ToolExecutionResult(
                success=False,
                tool_name="detect_card_testing",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=str(e)
            )

    def write_case(self, case_dict: Dict[str, Any]) -> ToolExecutionResult:
        """
        Writes completed investigation case back to graph.
        """
        t0 = time.time()
        try:
            if not case_dict.get("case_id"):
                raise ValueError("case_id is required to persist case.")
            res = self.adapter.write_case(case_dict)
            lat = round((time.time() - t0) * 1000, 2)
            results = res.get("results", [])
            status = results[0].get("status", "SUCCESS") if results else "SUCCESS"
            if status != "SUCCESS":
                err_msg = results[0].get("error", f"write_case returned status {status}")
                return ToolExecutionResult(
                    success=False,
                    tool_name="write_case",
                    source=res.get("source", "graph"),
                    latency_ms=lat,
                    error=err_msg
                )

            return ToolExecutionResult(
                success=True,
                tool_name="write_case",
                source=res.get("source", "graph"),
                latency_ms=lat,
                data={
                    "case_id": case_dict.get("case_id"),
                    "status": "SUCCESS",
                    "persisted": True
                }
            )
        except Exception as e:
            lat = round((time.time() - t0) * 1000, 2)
            err_str = str(e)
            logger.error(f"write_case failed: {err_str}")
            return ToolExecutionResult(
                success=False,
                tool_name="write_case",
                source=getattr(self.adapter, "backend", "unknown"),
                latency_ms=lat,
                error=err_str
            )

