"""
Reproducible Graph Data Loader.
Loads raw dataset CSVs into graph topology without modifying raw data.
"""

import csv
import os
import time
from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field


@dataclass
class CustomerVertex:
    customer_id: str


@dataclass
class CardVertex:
    card_id: str
    customer_id: str
    card1: str
    card2: str
    card3: str
    card4: str
    card5: str
    card6: str


@dataclass
class TransactionVertex:
    txn_id: str
    ts: str
    amount: float
    product_cd: str
    channel: str
    risk_score: float
    dist1: str
    dist2: str
    p_emaildomain: str
    r_emaildomain: str
    card_id: str
    customer_id: str
    addr1: str
    addr2: str


@dataclass
class DeviceProfileVertex:
    device_profile_id: str
    device_info: str
    os: str
    browser: str
    screen: str
    device_type: str
    proxy_status: str


@dataclass
class ClosedCaseVertex:
    case_id: str
    opened_at: str
    closed_at: str
    outcome: str
    pattern: str
    first_fraud_txn_id: str
    n_txns: int
    exposure_usd: float
    actions_taken: str
    report_filed: str
    analyst_notes: str
    card_id: str
    txn_ids: List[str]
    connected_card_ids: List[str]


class GraphStore:
    """In-Memory Graph Store mirroring TigerGraph schema and multi-hop edges."""

    def __init__(self):
        # Vertices
        self.customers: Dict[str, CustomerVertex] = {}
        self.cards: Dict[str, CardVertex] = {}
        self.transactions: Dict[str, TransactionVertex] = {}
        self.devices: Dict[str, DeviceProfileVertex] = {}
        self.regions: Dict[str, Dict[str, Any]] = {}
        self.domains: Set[str] = set()
        self.closed_cases: Dict[str, ClosedCaseVertex] = {}

        # Edges
        self.customer_owns_cards: Dict[str, Set[str]] = {}
        self.card_owned_by_customer: Dict[str, str] = {}
        self.card_made_txns: Dict[str, List[str]] = {}
        self.txn_made_by_card: Dict[str, str] = {}
        self.txn_from_device: Dict[str, str] = {}
        self.device_for_txns: Dict[str, Set[str]] = {}
        self.txn_billed_in: Dict[str, str] = {}
        self.region_has_txns: Dict[str, Set[str]] = {}
        self.card_had_case: Dict[str, Set[str]] = {}
        self.case_on_card: Dict[str, str] = {}
        self.case_involves_txns: Dict[str, Set[str]] = {}
        self.case_connected_cards: Dict[str, Set[str]] = {}
        self.txn_purchaser_email: Dict[str, str] = {}
        self.next_txn: Dict[str, str] = {}
        self.prev_txn: Dict[str, str] = {}

        self.loaded = False

    def load_from_csv(self, data_dir: str = ".") -> Dict[str, int]:
        """Loads and indexes all dataset files reproducibly."""
        start_time = time.time()
        print(f"Loading GraphStore from CSV files in '{data_dir}'...")

        # 1. Closed cases
        closed_path = os.path.join(data_dir, "closed_cases_history.csv")
        if os.path.exists(closed_path):
            with open(closed_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    cid = r["case_id"]
                    tids = [t.strip() for t in r.get("txn_ids", "").split("|") if t.strip()]
                    ccards = [c.strip() for c in r.get("connected_card_ids", "").split("|") if c.strip()]
                    primary_card = r.get("card_id", "")
                    
                    cc = ClosedCaseVertex(
                        case_id=cid,
                        opened_at=r.get("opened_at", ""),
                        closed_at=r.get("closed_at", ""),
                        outcome=r.get("outcome", ""),
                        pattern=r.get("pattern", ""),
                        first_fraud_txn_id=r.get("first_fraud_txn_id", ""),
                        n_txns=int(r.get("n_txns", 0) or 0),
                        exposure_usd=float(r.get("exposure_usd", 0.0) or 0.0),
                        actions_taken=r.get("actions_taken", ""),
                        report_filed=r.get("report_filed", ""),
                        analyst_notes=r.get("analyst_notes", ""),
                        card_id=primary_card,
                        txn_ids=tids,
                        connected_card_ids=ccards
                    )
                    self.closed_cases[cid] = cc

                    if primary_card:
                        self.card_had_case.setdefault(primary_card, set()).add(cid)
                        self.case_on_card[cid] = primary_card

                    for tid in tids:
                        self.case_involves_txns.setdefault(cid, set()).add(tid)

                    for ccard in ccards:
                        self.case_connected_cards.setdefault(cid, set()).add(ccard)

        # 1b. Case Pack mappings
        cust_card_map = {}
        case_pack_path = os.path.join(data_dir, "case_pack.csv")
        if os.path.exists(case_pack_path):
            with open(case_pack_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    if r.get("customer_id") and r.get("card_id"):
                        cust_card_map[r["customer_id"]] = r["card_id"]

        # 2. Identity Records
        id_path = os.path.join(data_dir, "identity.csv")
        if os.path.exists(id_path):
            with open(id_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    tid = r["TransactionID"]
                    prof = f"{r.get('DeviceInfo','')} | {r.get('id_30','')} | {r.get('id_31','')} | {r.get('id_33','')}"
                    dp = DeviceProfileVertex(
                        device_profile_id=prof,
                        device_info=r.get("DeviceInfo", ""),
                        os=r.get("id_30", ""),
                        browser=r.get("id_31", ""),
                        screen=r.get("id_33", ""),
                        device_type=r.get("DeviceType", ""),
                        proxy_status=r.get("id_23", "")
                    )
                    self.devices[prof] = dp
                    self.txn_from_device[tid] = prof
                    self.device_for_txns.setdefault(prof, set()).add(tid)

        # 3. Transactions
        txns_path = os.path.join(data_dir, "transactions.csv")
        if os.path.exists(txns_path):
            with open(txns_path, "r", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    tid = r["TransactionID"]
                    cust_id = r.get("customer_id", "")
                    card_id = cust_card_map.get(cust_id, f"{cust_id}-K1")
                    amt = float(r.get("TransactionAmt", 0.0) or 0.0)
                    risk = float(r.get("risk_score", 0.0) or 0.0)
                    addr1 = r.get("addr1", "")
                    addr2 = r.get("addr2", "")
                    p_email = r.get("P_emaildomain", "")
                    r_email = r.get("R_emaildomain", "")

                    tx = TransactionVertex(
                        txn_id=tid,
                        ts=r.get("ts", ""),
                        amount=amt,
                        product_cd=r.get("ProductCD", ""),
                        channel=r.get("channel", ""),
                        risk_score=risk,
                        dist1=r.get("dist1", ""),
                        dist2=r.get("dist2", ""),
                        p_emaildomain=p_email,
                        r_emaildomain=r_email,
                        card_id=card_id,
                        customer_id=cust_id,
                        addr1=addr1,
                        addr2=addr2
                    )
                    self.transactions[tid] = tx

                    # Customer & Card
                    if cust_id and cust_id not in self.customers:
                        self.customers[cust_id] = CustomerVertex(customer_id=cust_id)
                    if card_id and card_id not in self.cards:
                        self.cards[card_id] = CardVertex(
                            card_id=card_id,
                            customer_id=cust_id,
                            card1=r.get("card1", ""),
                            card2=r.get("card2", ""),
                            card3=r.get("card3", ""),
                            card4=r.get("card4", ""),
                            card5=r.get("card5", ""),
                            card6=r.get("card6", "")
                        )
                        self.customer_owns_cards.setdefault(cust_id, set()).add(card_id)
                        self.card_owned_by_customer[card_id] = cust_id

                    # Edges
                    self.card_made_txns.setdefault(card_id, []).append(tid)
                    self.txn_made_by_card[tid] = card_id

                    if addr1:
                        self.regions.setdefault(addr1, {"region_id": addr1, "country_code": addr2})
                        self.txn_billed_in[tid] = addr1
                        self.region_has_txns.setdefault(addr1, set()).add(tid)

                    if p_email:
                        self.domains.add(p_email)
                        self.txn_purchaser_email[tid] = p_email

        # Sort transactions per card chronologically and link NEXT edges
        for cid, tx_list in self.card_made_txns.items():
            tx_list.sort(key=lambda t: self.transactions[t].ts)
            for i in range(len(tx_list) - 1):
                cur_tid = tx_list[i]
                nxt_tid = tx_list[i + 1]
                self.next_txn[cur_tid] = nxt_tid
                self.prev_txn[nxt_tid] = cur_tid

        self.loaded = True
        duration = time.time() - start_time
        print(f"GraphStore loaded in {duration:.2f}s.")

        return self.get_summary()

    def get_vertex_counts(self) -> Dict[str, int]:
        return {
            "Customer": len(self.customers),
            "Card": len(self.cards),
            "Transaction": len(self.transactions),
            "DeviceProfile": len(self.devices),
            "BillingRegion": len(self.regions),
            "EmailDomain": len(self.domains),
            "ClosedCase": len(self.closed_cases),
        }

    def get_edge_counts(self) -> Dict[str, int]:
        # Count total directed instances for each edge type
        owns_count = sum(len(cards) for cards in self.customer_owns_cards.values())
        made_count = len(self.txn_made_by_card)
        from_device_count = len(self.txn_from_device)
        billed_in_count = len(self.txn_billed_in)
        on_card_count = len(self.case_on_card)
        involves_count = sum(len(tids) for tids in self.case_involves_txns.values())
        connected_to_count = sum(len(cards) for cards in self.case_connected_cards.values())
        purchaser_email_count = len(self.txn_purchaser_email)
        next_count = len(self.next_txn)

        return {
            "OWNS": owns_count,
            "MADE": made_count,
            "FROM_DEVICE": from_device_count,
            "BILLED_IN": billed_in_count,
            "ON_CARD": on_card_count,
            "INVOLVES": involves_count,
            "CONNECTED_TO": connected_to_count,
            "PURCHASER_EMAIL": purchaser_email_count,
            "NEXT": next_count
        }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "vertices": self.get_vertex_counts(),
            "edges": self.get_edge_counts()
        }


_GLOBAL_STORE: Optional[GraphStore] = None


def get_graph_store(data_dir: str = ".") -> GraphStore:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = GraphStore()
        _GLOBAL_STORE.load_from_csv(data_dir)
    return _GLOBAL_STORE
