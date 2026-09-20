"""
Unified Graph Adapter Interface.
Provides structured graph queries over TigerGraph or the in-memory graph store.
Identifies execution backend explicitly as 'tigergraph' or 'in_memory'.
"""

import datetime
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, List, Any, Optional

from src.config import config
from src.graph.loading.loader import get_graph_store, GraphStore, ClosedCaseVertex

logger = logging.getLogger(__name__)


class GraphAdapter:
    """
    Unified Graph Adapter providing multi-hop graph investigation operations.
    Returns standardized, structured payloads suitable for agentic consumption.
    """

    def __init__(self, backend: Optional[str] = None):
        self.backend = backend or config.TG_BACKEND
        self.graph_name = config.TG_GRAPH_NAME
        self.store: Optional[GraphStore] = None
        self._init_backend()

    def _init_backend(self):
        if self.backend == "auto":
            # Attempt to reach TigerGraph REST++ endpoint
            if self._check_tigergraph_connection():
                self.backend = "tigergraph"
                logger.info("GraphAdapter connected to TigerGraph backend.")
            else:
                self.backend = "in_memory"
                logger.info("TigerGraph offline or unconfigured; falling back to in_memory graph store.")
                self.store = get_graph_store(config.DATA_DIR)
        elif self.backend == "tigergraph":
            if not self._check_tigergraph_connection():
                raise ConnectionError(
                    f"Strict 'tigergraph' backend requested but could not connect to {config.get_rest_base_url()}"
                )
        elif self.backend == "in_memory":
            self.store = get_graph_store(config.DATA_DIR)
        else:
            raise ValueError(f"Unknown graph backend: '{self.backend}'")

    def _check_tigergraph_connection(self) -> bool:
        """Pings the TigerGraph REST++ echo endpoint."""
        base = config.get_rest_base_url()
        endpoints = [f"{base}/restpp/echo", f"{base}/echo"]
        for url in endpoints:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TigerGraphAdapter/1.0"})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                continue
        return False

    def _tg_rest_query(self, query_name: str, params: Dict[str, Any], use_post: bool = False) -> Any:
        """Executes a parameterized query against TigerGraph REST++ endpoint."""
        url = f"{config.get_rest_base_url()}/restpp/query/{config.TG_GRAPH_NAME}/{query_name}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "TigerGraphAdapter/1.0"
        }
        token = config.get_auth_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        if use_post:
            data = json.dumps(params).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        else:
            clean_params = {}
            for k, v in params.items():
                if v is None:
                    continue
                if isinstance(v, (list, tuple, set)):
                    clean_list = [str(item) for item in v if item]
                    if clean_list:
                        clean_params[k] = clean_list
                else:
                    clean_params[k] = str(v)

            encoded_params = urllib.parse.urlencode(
                clean_params,
                doseq=True,
                quote_via=urllib.parse.quote
            )
            if encoded_params:
                url = f"{url}?{encoded_params}"

            req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("error"):
                    msg = data.get("message", "")
                    if "Failed to convert user vertex id" in msg and not use_post:
                        return []
                    raise RuntimeError(f"TigerGraph query error: {msg}")
                return data.get("results", [])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("message") or err_body
            except Exception:
                msg = err_body
            if "Failed to convert user vertex id" in msg and not use_post:
                return []
            raise RuntimeError(f"TigerGraph REST++ HTTP {e.code}: {msg}")


    # =========================================================================
    # CORE INVESTIGATION QUERY INTERFACES
    # =========================================================================

    def get_transaction_context(self, txn_id: str) -> Dict[str, Any]:
        """
        Retrieves complete transaction context including customer, card, channel,
        device profile, proxy status, billing region, and risk score.
        """
        inputs = {"txn_id": str(txn_id)}
        card_id = ""
        cust_id = ""
        reg_id = ""
        risk_score = 0.0
        dev_prof = ""

        if self.backend == "tigergraph":
            raw_res = self._tg_rest_query("get_transaction_context", {"target_txn": txn_id})
            results = []
            if raw_res and len(raw_res) > 0:
                row = raw_res[0]
                start_list = row.get("Start", [])
                if start_list:
                    st = start_list[0]
                    st_attr = st.get("attributes", {})
                    card_list = row.get("Cards", [])
                    card_id = card_list[0].get("v_id", "") if card_list else ""
                    card_attr = card_list[0].get("attributes", {}) if card_list else {}
                    cust_list = row.get("Customers", [])
                    cust_id = cust_list[0].get("v_id", "") if cust_list else ""
                    dev_list = row.get("Devices", [])
                    dev_prof = dev_list[0].get("v_id", "") if dev_list else ""
                    dev_attr = dev_list[0].get("attributes", {}) if dev_list else {}
                    reg_list = row.get("Regions", [])
                    reg_id = reg_list[0].get("v_id", "") if reg_list else ""
                    reg_attr = reg_list[0].get("attributes", {}) if reg_list else {}
                    email_list = row.get("Emails", [])
                    email_id = email_list[0].get("v_id", "") if email_list else ""
                    risk_score = float(st_attr.get("Start.risk_score") or 0.0)

                    results = [{
                        "transaction": {
                            "txn_id": st.get("v_id"),
                            "ts": st_attr.get("Start.ts"),
                            "amount": st_attr.get("Start.amount"),
                            "channel": st_attr.get("Start.channel"),
                            "product_cd": st_attr.get("Start.product_cd"),
                            "risk_score": risk_score
                        },
                        "customer_id": cust_id,
                        "card": {
                            "card_id": card_id,
                            "card4": card_attr.get("Cards.card4", ""),
                            "card6": card_attr.get("Cards.card6", "")
                        },
                        "device_profile": dev_prof,
                        "device_type": dev_attr.get("Devices.device_type", ""),
                        "proxy_status": dev_attr.get("Devices.proxy_status", ""),
                        "billing_region": reg_id,
                        "billing_country": reg_attr.get("Regions.country_code", ""),
                        "email_domain": email_id
                    }]
        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            tx = store.transactions.get(txn_id)
            if not tx:
                results = []
            else:
                card = store.cards.get(tx.card_id)
                dev = store.devices.get(store.txn_from_device.get(txn_id, ""))
                card_id = tx.card_id
                cust_id = tx.customer_id
                reg_id = tx.addr1
                risk_score = tx.risk_score
                dev_prof = dev.device_profile_id if dev else ""
                results = [{
                    "transaction": {
                        "txn_id": tx.txn_id,
                        "ts": tx.ts,
                        "amount": tx.amount,
                        "channel": tx.channel,
                        "product_cd": tx.product_cd,
                        "risk_score": tx.risk_score
                    },
                    "customer_id": tx.customer_id,
                    "card": {
                        "card_id": tx.card_id,
                        "card4": card.card4 if card else "",
                        "card6": card.card6 if card else ""
                    },
                    "device_profile": dev_prof,
                    "device_type": dev.device_type if dev else "",
                    "proxy_status": dev.proxy_status if dev else "",
                    "billing_region": tx.addr1,
                    "billing_country": tx.addr2,
                    "email_domain": tx.p_emaildomain
                }]

        return {
            "query": "get_transaction_context",
            "inputs": inputs,
            "results": results,
            "evidence_type": "transaction_context",
            "source": self.backend,
            "card_id": card_id,
            "customer_id": cust_id,
            "region_id": reg_id,
            "risk_score": risk_score,
            "device_profile_id": dev_prof
        }

    def get_card_history(
        self,
        card_id: str,
        start_time: str = "",
        end_time: str = ""
    ) -> Dict[str, Any]:
        """
        Retrieves chronological transaction history for a card, enabling velocity,
        amount range, and geographic cadence analysis.
        """
        inputs = {"card_id": card_id, "start_time": start_time, "end_time": end_time}
        if self.backend == "tigergraph":
            st = start_time or "1970-01-01 00:00:00"
            et = end_time or "2030-01-01 00:00:00"
            raw_res = self._tg_rest_query(
                "get_card_history",
                {"target_card": card_id, "start_time": st, "end_time": et}
            )
            results = []
            if raw_res and len(raw_res) > 0:
                for t in raw_res[0].get("Txns", []):
                    attr = t.get("attributes", {})
                    results.append({
                        "txn_id": t.get("v_id"),
                        "ts": attr.get("Txns.ts"),
                        "amount": attr.get("Txns.amount"),
                        "channel": attr.get("Txns.channel"),
                        "product_cd": attr.get("Txns.product_cd"),
                        "billing_region": attr.get("Txns.billing_region", ""),
                        "risk_score": attr.get("Txns.risk_score")
                    })
        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            tids = store.card_made_txns.get(card_id, [])
            txns = [store.transactions[t] for t in tids]
            if start_time:
                txns = [t for t in txns if t.ts >= start_time]
            if end_time:
                txns = [t for t in txns if t.ts <= end_time]

            results = [{
                "txn_id": t.txn_id,
                "ts": t.ts,
                "amount": t.amount,
                "channel": t.channel,
                "product_cd": t.product_cd,
                "billing_region": t.addr1,
                "risk_score": t.risk_score
            } for t in txns]

        return {
            "query": "get_card_history",
            "inputs": inputs,
            "results": results,
            "evidence_type": "card_history",
            "source": self.backend,
            "total_transactions": len(results)
        }

    def get_customer_history(self, customer_id: str) -> Dict[str, Any]:
        """
        Retrieves customer card portfolio and aggregated transaction activity.
        """
        inputs = {"customer_id": customer_id}
        if self.backend == "tigergraph":
            raw_res = self._tg_rest_query("get_customer_history", {"target_customer": customer_id})
            results = []
            if raw_res and len(raw_res) > 0:
                row = raw_res[0]
                cards = [{
                    "card_id": c.get("v_id"),
                    "card4": c.get("attributes", {}).get("Cards.card4", ""),
                    "card6": c.get("attributes", {}).get("Cards.card6", "")
                } for c in row.get("Cards", [])]
                txns = [{
                    "txn_id": t.get("v_id"),
                    "ts": t.get("attributes", {}).get("Txns.ts"),
                    "amount": t.get("attributes", {}).get("Txns.amount"),
                    "channel": t.get("attributes", {}).get("Txns.channel"),
                    "risk_score": t.get("attributes", {}).get("Txns.risk_score")
                } for t in row.get("Txns", [])]
                results = [{
                    "customer_id": customer_id,
                    "cards": cards,
                    "total_transactions": row.get("total_transactions", len(txns)),
                    "transactions": txns
                }]
        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            cards = store.customer_owns_cards.get(customer_id, set())
            card_objs = [store.cards[c] for c in cards if c in store.cards]

            all_txns = []
            for c in cards:
                for tid in store.card_made_txns.get(c, []):
                    all_txns.append(store.transactions[tid])
            all_txns.sort(key=lambda x: x.ts)

            results = [{
                "customer_id": customer_id,
                "cards": [{
                    "card_id": c.card_id,
                    "card4": c.card4,
                    "card6": c.card6
                } for c in card_objs],
                "total_transactions": len(all_txns),
                "transactions": [{
                    "txn_id": t.txn_id,
                    "ts": t.ts,
                    "amount": t.amount,
                    "risk_score": t.risk_score,
                    "channel": t.channel
                } for t in all_txns]
            }]

        return {
            "query": "get_customer_history",
            "inputs": inputs,
            "results": results,
            "evidence_type": "customer_history",
            "source": self.backend
        }

    def get_device_neighbors(self, device_profile: str) -> Dict[str, Any]:
        """
        Identifies cards and customers that share a specific device profile.
        Crucial for detecting multi-account attacks and botnet fraud (Rules R6 & R9).
        """
        inputs = {"device_profile": device_profile}
        if self.backend == "tigergraph":
            raw_res = self._tg_rest_query("get_device_neighbors", {"target_device": device_profile})
            results = []
            if raw_res and len(raw_res) > 0:
                row = raw_res[0]
                cards = row.get("@@cards", [])
                custs = row.get("@@customers", [])
                results = [{
                    "device_profile": device_profile,
                    "connected_cards": sorted(cards),
                    "connected_customers": sorted(custs),
                    "total_txns": row.get("total_txns", len(cards)),
                    "recent_txn_ids": []
                }]
        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            tids = store.device_for_txns.get(device_profile, set())
            cards: Set[str] = set()
            customers: Set[str] = set()
            for tid in tids:
                if tid in store.transactions:
                    tx = store.transactions[tid]
                    cards.add(tx.card_id)
                    customers.add(tx.customer_id)

            sorted_txns = sorted([store.transactions[t] for t in tids if t in store.transactions], key=lambda x: x.ts, reverse=True)
            results = [{
                "device_profile": device_profile,
                "connected_cards": sorted(list(cards)),
                "connected_customers": sorted(list(customers)),
                "total_txns": len(tids),
                "recent_txn_ids": [t.txn_id for t in sorted_txns[:20]]
            }]

        return {
            "query": "get_device_neighbors",
            "inputs": inputs,
            "results": results,
            "evidence_type": "device_neighbors",
            "source": self.backend,
            "connected_cards": results[0]["connected_cards"] if results else [],
            "total_cards": len(results[0]["connected_cards"]) if results else 0
        }

    def get_connected_cards(self, card_id: str) -> Dict[str, Any]:
        """
        Discovers sibling cards or other victim cards connected through shared devices.
        """
        inputs = {"card_id": card_id}
        if self.backend == "tigergraph":
            raw_res = self._tg_rest_query("get_connected_cards", {"target_card": card_id})
            results = []
            if raw_res and len(raw_res) > 0:
                row = raw_res[0]
                results = [{
                    "card_id": card_id,
                    "connected_cards": sorted(row.get("@@connected_cards", [])),
                    "shared_devices": sorted(row.get("@@shared_devices", []))
                }]
        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            txns = store.card_made_txns.get(card_id, [])
            devices: Set[str] = set()
            for tid in txns:
                dev = store.txn_from_device.get(tid)
                if dev:
                    devices.add(dev)

            connected_cards: Set[str] = set()
            for dev in devices:
                for other_tid in store.device_for_txns.get(dev, set()):
                    if other_tid in store.transactions:
                        other_card = store.transactions[other_tid].card_id
                        if other_card != card_id:
                            connected_cards.add(other_card)

            results = [{
                "card_id": card_id,
                "connected_cards": sorted(list(connected_cards)),
                "shared_devices": sorted(list(devices))
            }]

        return {
            "query": "get_connected_cards",
            "inputs": inputs,
            "results": results,
            "evidence_type": "connected_cards",
            "source": self.backend,
            "connected_cards": results[0]["connected_cards"] if results else [],
            "total_connected": len(results[0]["connected_cards"]) if results else 0
        }

    def get_transaction_chain(self, txn_id: str, window_hours: int = 24) -> Dict[str, Any]:
        """
        Retrieves preceding and subsequent transactions on the same card within a temporal window.
        """
        inputs = {"txn_id": txn_id, "window_hours": window_hours}
        if self.backend == "tigergraph":
            raw_res = self._tg_rest_query("get_transaction_chain", {"target_txn": txn_id, "window_hours": window_hours})
            results = []
            if raw_res and len(raw_res) > 0:
                for t in raw_res[0].get("ChainTxns", []):
                    attr = t.get("attributes", {})
                    results.append({
                        "txn_id": t.get("v_id"),
                        "ts": attr.get("ChainTxns.ts"),
                        "amount": attr.get("ChainTxns.amount"),
                        "channel": attr.get("ChainTxns.channel"),
                        "risk_score": attr.get("ChainTxns.risk_score")
                    })
        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            tx = store.transactions.get(txn_id)
            if not tx:
                results = []
            else:
                card_txns = [store.transactions[t] for t in store.card_made_txns.get(tx.card_id, [])]
                try:
                    center_dt = datetime.datetime.strptime(tx.ts, "%Y-%m-%d %H:%M:%S")
                    start_dt = center_dt - datetime.timedelta(hours=window_hours)
                    end_dt = center_dt + datetime.timedelta(hours=window_hours)

                    chain = [
                        t for t in card_txns
                        if start_dt <= datetime.datetime.strptime(t.ts, "%Y-%m-%d %H:%M:%S") <= end_dt
                    ]
                except Exception:
                    chain = card_txns

                results = [{
                    "txn_id": t.txn_id,
                    "ts": t.ts,
                    "amount": t.amount,
                    "channel": t.channel,
                    "risk_score": t.risk_score,
                    "billing_region": t.addr1
                } for t in chain]

        return {
            "query": "get_transaction_chain",
            "inputs": inputs,
            "results": results,
            "evidence_type": "transaction_chain",
            "source": self.backend
        }

    def get_similar_closed_cases(
        self,
        card_id: str = "",
        device_profile: str = ""
    ) -> Dict[str, Any]:
        """
        Retrieves historical closed cases matching the card or device profile.
        Provides grounding case memory for the agent.
        """
        inputs = {"card_id": card_id, "device_profile": device_profile}
        if self.backend == "tigergraph":
            raw_res = self._tg_rest_query(
                "get_similar_closed_cases",
                {"target_card_id": card_id, "target_device_profile": device_profile}
            )
            results = []
            if raw_res and len(raw_res) > 0:
                for c in raw_res[0].get("Cases", []):
                    attr = c.get("attributes", {})
                    results.append({
                        "case_id": c.get("v_id"),
                        "opened_at": attr.get("Cases.opened_at"),
                        "outcome": attr.get("Cases.outcome"),
                        "pattern": attr.get("Cases.pattern"),
                        "exposure_usd": attr.get("Cases.exposure_usd"),
                        "actions_taken": attr.get("Cases.actions_taken"),
                        "analyst_notes": attr.get("Cases.analyst_notes")
                    })
        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            matched_cases: Set[str] = set()

            if card_id:
                for cid in store.card_had_case.get(card_id, set()):
                    matched_cases.add(cid)

            if device_profile:
                dev_txns = store.device_for_txns.get(device_profile, set())
                for cid, cc in store.closed_cases.items():
                    if any(t in dev_txns for t in cc.txn_ids):
                        matched_cases.add(cid)

            results = [{
                "case_id": store.closed_cases[cid].case_id,
                "opened_at": store.closed_cases[cid].opened_at,
                "outcome": store.closed_cases[cid].outcome,
                "pattern": store.closed_cases[cid].pattern,
                "exposure_usd": store.closed_cases[cid].exposure_usd,
                "actions_taken": store.closed_cases[cid].actions_taken,
                "report_filed": store.closed_cases[cid].report_filed,
                "analyst_notes": store.closed_cases[cid].analyst_notes
            } for cid in sorted(list(matched_cases)) if cid in store.closed_cases]

        return {
            "query": "get_similar_closed_cases",
            "inputs": inputs,
            "results": results,
            "evidence_type": "similar_closed_cases",
            "source": self.backend,
            "cases": results,
            "total_cases": len(results)
        }

    def detect_card_testing(self, card_id: str, window_start: str) -> Dict[str, Any]:
        """
        Detects 3+ small authorizations (<$5.00) in 1 hour followed by a larger transaction (Policy R5).
        """
        inputs = {"card_id": card_id, "window_start": window_start}
        if self.backend == "tigergraph":
            raw_res = self._tg_rest_query(
                "detect_card_testing",
                {"target_card": card_id, "window_start": window_start}
            )
            results = []
            if raw_res and len(raw_res) > 0:
                row = raw_res[0]
                results = [{
                    "card_id": card_id,
                    "is_testing": row.get("is_testing", False),
                    "small_auth_count": row.get("small_count", 0),
                    "large_auth_count": row.get("large_count", 0),
                    "small_txn_ids": [],
                    "large_txn_ids": []
                }]
        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            txns = [store.transactions[t] for t in store.card_made_txns.get(card_id, [])]
            try:
                start_dt = datetime.datetime.strptime(window_start, "%Y-%m-%d %H:%M:%S")
                end_dt = start_dt + datetime.timedelta(hours=1)
                window_txns = [
                    t for t in txns
                    if start_dt <= datetime.datetime.strptime(t.ts, "%Y-%m-%d %H:%M:%S") <= end_dt
                ]
            except Exception:
                window_txns = txns

            small_txns = [t.txn_id for t in window_txns if t.channel == "online" and t.amount < 5.00]
            large_txns = [t.txn_id for t in window_txns if t.amount >= 50.00]

            is_testing = len(small_txns) >= 3 and len(large_txns) >= 1
            results = [{
                "card_id": card_id,
                "is_testing": is_testing,
                "small_auth_count": len(small_txns),
                "large_auth_count": len(large_txns),
                "small_txn_ids": small_txns,
                "large_txn_ids": large_txns
            }]

        return {
            "query": "detect_card_testing",
            "inputs": inputs,
            "results": results,
            "evidence_type": "card_testing",
            "source": self.backend
        }

    def write_case(self, case_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Writes completed investigation case back to graph (Section 3a persistence & memory).
        Supports both flat case records and nested schema dictionaries.
        Idempotent operation.
        """
        case_id = case_dict.get("case_id")
        inputs = {"case_id": case_id}

        case_info = case_dict.get("case", {})
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        opened_at = case_dict.get("opened_at") or now_iso
        closed_at = case_dict.get("closed_at") or now_iso

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

        if self.backend == "tigergraph":
            tg_params = {
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
            res = self._tg_rest_query("write_case", tg_params, use_post=True)
            status = "SUCCESS"
            if res and isinstance(res, list) and isinstance(res[0], dict):
                status = res[0].get("status", "SUCCESS")

        else:
            store = self.store or get_graph_store(config.DATA_DIR)
            cc = ClosedCaseVertex(
                case_id=case_id,
                opened_at=opened_at,
                closed_at=closed_at,
                outcome=outcome,
                pattern=pattern,
                first_fraud_txn_id=first_fraud_txn_id,
                n_txns=n_txns,
                exposure_usd=exposure_usd,
                actions_taken=actions_taken,
                report_filed=report_filed,
                analyst_notes=analyst_notes,
                card_id=card_id,
                txn_ids=affected_txns,
                connected_card_ids=connected_cards
            )
            store.closed_cases[case_id] = cc
            if cc.card_id:
                store.card_had_case.setdefault(cc.card_id, set()).add(case_id)
                store.case_on_card[case_id] = cc.card_id

            for tid in cc.txn_ids:
                store.case_involves_txns.setdefault(case_id, set()).add(tid)

            for cc_card in cc.connected_card_ids:
                store.case_connected_cards.setdefault(case_id, set()).add(cc_card)

            status = "SUCCESS"

        return {
            "query": "write_case",
            "inputs": inputs,
            "results": [{"status": status, "persisted_case_id": case_id}],
            "evidence_type": "case_writeback",
            "source": self.backend
        }



_GLOBAL_ADAPTER: Optional[GraphAdapter] = None


def get_graph_adapter(backend: Optional[str] = None) -> GraphAdapter:
    global _GLOBAL_ADAPTER
    if backend is not None:
        return GraphAdapter(backend=backend)
    if _GLOBAL_ADAPTER is None:
        _GLOBAL_ADAPTER = GraphAdapter()
    return _GLOBAL_ADAPTER
