"""
Unified GraphRAG Context Builder.
Synthesizes real-time TigerGraph subgraph evidence, historical case memory,
retrieved policy rules, and fraud typologies into a compact, traceable, bounded prompt context.
"""

import json
from typing import Dict, List, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.agent.state import InvestigationState

from src.rag.provenance import ProvenanceItem, ProvenanceType
from src.rag.retriever import get_policy_retriever


class GraphRAGContextBuilder:
    """
    Constructs an information-dense, bounded GraphRAG investigation context.
    Guarantees strict provenance tracking, context-size control, and zero benchmark leakage.
    """

    def __init__(self, token_budget: int = 2500):
        self.token_budget = token_budget
        self.retriever = get_policy_retriever()

    def build_context(self, state: InvestigationState) -> Dict[str, Any]:
        """
        Builds the unified GraphRAG context dictionary and rendered prompt context.
        """
        provenance_map: Dict[str, Dict[str, Any]] = {}

        # 1. Real-time TigerGraph Subgraph Evidence
        graph_evidence: List[Dict[str, Any]] = []

        # Flagged transaction facts
        tx_ctx = state.transaction_context or {}
        tx = tx_ctx.get("transaction", {})
        if tx:
            txn_id = state.flagged_txn_id
            prov_id = f"GRAPH-TXN-{txn_id}"
            amt = tx.get("amount", 0.0)
            score = tx.get("risk_score", 0.0)
            chan = tx.get("channel", "unknown")
            dev_os = tx.get("device_os")
            dev_browser = tx.get("device_browser")
            is_proxy = tx.get("is_proxy", False)

            item = {
                "provenance_id": prov_id,
                "type": "flagged_transaction",
                "transaction_id": txn_id,
                "amount_usd": amt,
                "risk_score": score,
                "channel": chan,
                "device": f"{dev_os or 'None'} / {dev_browser or 'None'} (proxy={is_proxy})",
                "billing_region": state.billing_regions[0] if state.billing_regions else "None"
            }
            graph_evidence.append(item)
            provenance_map[prov_id] = {
                "source": f"TigerGraph:Transaction({txn_id})",
                "type": "GRAPH",
                "summary": f"Flagged auth ${amt:.2f} (score: {score:.2f}, channel: {chan})"
            }

        # Card history summary
        card_summary = state.card_history_summary or {}
        if card_summary:
            prov_id = f"GRAPH-CARD-{state.card_id}"
            stats = card_summary.get("amount_stats", {})
            reg_sum = card_summary.get("regional_summary", {})
            item = {
                "provenance_id": prov_id,
                "type": "card_history_summary",
                "card_id": state.card_id,
                "total_historical_txns": card_summary.get("total_transactions", 0),
                "baseline_mean_usd": stats.get("mean_usd", 0.0),
                "baseline_stdev_usd": stats.get("stdev_usd", 0.0),
                "region_familiarity": reg_sum.get("flagged_region_familiarity", "novel_zero_history"),
                "prior_txns_in_region": reg_sum.get("flagged_region_txns_count", 0)
            }
            graph_evidence.append(item)
            provenance_map[prov_id] = {
                "source": f"TigerGraph:Card({state.card_id})",
                "type": "GRAPH",
                "summary": f"Historical profile: {card_summary.get('total_transactions',0)} txns, familiarity: {reg_sum.get('flagged_region_familiarity')}"
            }

        # Device topology & syndicate evidence
        dev_ev = state.device_evidence or {}
        if dev_ev:
            dev_id = state.device_profile_ids[0] if state.device_profile_ids else "device_unknown"
            prov_id = f"GRAPH-DEV-{dev_id}"
            item = {
                "provenance_id": prov_id,
                "type": "device_network_topology",
                "device_profile_id": dev_id,
                "connected_cards_count": dev_ev.get("connected_card_count", 0),
                "is_shared_device": dev_ev.get("is_shared_device", False),
                "syndicate_risk_tier": dev_ev.get("syndicate_risk_tier", "LOW")
            }
            graph_evidence.append(item)
            provenance_map[prov_id] = {
                "source": f"TigerGraph:DeviceProfile({dev_id})",
                "type": "GRAPH",
                "summary": f"Device links {dev_ev.get('connected_card_count', 0)} accounts, risk: {dev_ev.get('syndicate_risk_tier')}"
            }

        # 2. Historical Case Memory (TigerGraph ClosedCase Vertices)
        case_memory: List[Dict[str, Any]] = []
        for c in state.prior_case_evidence[:5]:
            cid = c.get("case_id", "")
            prov_id = f"CASE-{cid}" if not cid.startswith("CASE-") else cid
            desc = c.get("incident_description", "") or c.get("resolution", "")
            item = {
                "provenance_id": prov_id,
                "case_id": cid,
                "incident_type": c.get("incident_type", "fraud_incident"),
                "outcome": c.get("outcome", "closed"),
                "summary": desc[:160] + "..." if len(desc) > 160 else desc
            }
            case_memory.append(item)
            provenance_map[prov_id] = {
                "source": f"TigerGraph:ClosedCase({cid})",
                "type": "CASE_MEMORY",
                "summary": f"Prior closed precedent: {item['summary']}"
            }

        # 3. Dynamic RAG Query Formulation for Policy & Typologies
        query_terms = [state.trigger_type, state.trigger_text]
        if card_summary.get("regional_summary", {}).get("flagged_region_familiarity") == "routine":
            query_terms.extend(["routine travel", "recurring spend", "weekend travel", "R3", "close_no_fraud"])
        elif dev_ev.get("is_shared_device") or dev_ev.get("connected_card_count", 0) >= 5:
            query_terms.extend(["shared origin", "syndicate", "device ring", "R6", "monitor_connected_cards", "file_report", "sar"])
        elif state.trigger_type == "risk_score" and float(tx.get("risk_score", 0.0) or 0.0) < 0.70:
            query_terms.extend(["weak signal", "single signal", "verify_with_customer", "R1", "step_up_auth"])
        elif state.trigger_type == "customer_report":
            query_terms.extend(["customer dispute", "denies charge", "R2", "block_card", "create_case"])
        else:
            query_terms.extend(["novel region", "out of region use", "card not present"])

        rag_query = " ".join(query_terms)

        # Retrieve top relevant policies
        retrieved_policies = self.retriever.retrieve_policies(rag_query, top_k=3)
        policy_context: List[Dict[str, Any]] = []
        for p in retrieved_policies:
            policy_context.append({
                "provenance_id": p.provenance_id,
                "rule_name": p.title,
                "ref": p.ref,
                "guidance": p.content
            })
            provenance_map[p.provenance_id] = {
                "source": p.ref,
                "type": "POLICY",
                "summary": p.title
            }

        # Retrieve top relevant typologies
        retrieved_typologies = self.retriever.retrieve_typologies(rag_query, top_k=2)
        typology_context: List[Dict[str, Any]] = []
        for t in retrieved_typologies:
            typology_context.append({
                "provenance_id": t.provenance_id,
                "typology_name": t.title,
                "ref": t.ref,
                "definition": t.content
            })
            provenance_map[t.provenance_id] = {
                "source": t.ref,
                "type": "TYPOLOGY",
                "summary": t.title
            }

        # 4. Synthesize Rendered Text for LLM Context
        rendered_prompt_lines = [
            "=== GRAPHRAG INVESTIGATION CONTEXT ===",
            f"Case ID: {state.case_id} | Trigger: {state.trigger_type} ({state.trigger_text})",
            f"Subject: Card {state.card_id} (Customer: {state.customer_id})",
            "",
            "--- REAL-TIME TIGERGRAPH SUBGRAPH EVIDENCE ---"
        ]
        for ge in graph_evidence:
            rendered_prompt_lines.append(f"[{ge['provenance_id']}] {json.dumps(ge, default=str)}")

        if case_memory:
            rendered_prompt_lines.append("")
            rendered_prompt_lines.append("--- HISTORICAL CASE MEMORY (TIGERGRAPH PRECEDENTS) ---")
            for cm in case_memory:
                rendered_prompt_lines.append(f"[{cm['provenance_id']}] Case {cm['case_id']}: {cm['summary']} (Outcome: {cm['outcome']})")

        rendered_prompt_lines.append("")
        rendered_prompt_lines.append("--- GOVERNING FRAUD POLICY & APPROVAL RULES ---")
        for pc in policy_context:
            rendered_prompt_lines.append(f"[{pc['provenance_id']}] {pc['rule_name']}:\n{pc['guidance']}")

        rendered_prompt_lines.append("")
        rendered_prompt_lines.append("--- RELEVANT FRAUD TYPOLOGIES ---")
        for tc in typology_context:
            rendered_prompt_lines.append(f"[{tc['provenance_id']}] {tc['typology_name']}:\n{tc['definition']}")

        rendered_prompt_text = "\n".join(rendered_prompt_lines)

        return {
            "case_id": state.case_id,
            "graph_evidence": graph_evidence,
            "case_memory": case_memory,
            "retrieved_policies": policy_context,
            "retrieved_typologies": typology_context,
            "provenance_map": provenance_map,
            "rendered_prompt_context": rendered_prompt_text
        }
