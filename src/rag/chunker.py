"""
Heading-Aware Document and Policy Chunker for GraphRAG.
Deconstructs authoritative policies and specifications into semantically coherent,
identifiable chunks with standardized provenance IDs.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.rag.sources import validate_path_allowed
from src.rag.provenance import ProvenanceItem, ProvenanceType


class DocumentChunk:
    """Represents a coherent section of a policy or specification document."""
    def __init__(
        self,
        chunk_id: str,
        source_type: ProvenanceType,
        title: str,
        ref: str,
        content: str,
        keywords: Optional[List[str]] = None
    ):
        self.chunk_id = chunk_id
        self.source_type = source_type
        self.title = title
        self.ref = ref
        self.content = content.strip()
        self.keywords = keywords or []

    def to_provenance_item(self, score: float = 1.0) -> ProvenanceItem:
        return ProvenanceItem(
            provenance_id=self.chunk_id,
            source_type=self.source_type,
            title=self.title,
            ref=self.ref,
            content=self.content,
            score=score,
            metadata={"keywords": self.keywords}
        )


class PolicyChunker:
    """Specialized chunker for docs/policy_matrix.md and hackathon specifications."""

    @staticmethod
    def chunk_policy_matrix(file_path: Path) -> List[DocumentChunk]:
        """Parses docs/policy_matrix.md into specific rule and policy chunks."""
        validate_path_allowed(str(file_path))
        if not file_path.exists():
            return []

        text = file_path.read_text(encoding="utf-8")
        chunks: List[DocumentChunk] = []

        # 1. Canonical Action Definitions Chunk
        action_match = re.search(r"### 1\. Canonical Action Definitions.*?(?=### 2\.|$)", text, re.DOTALL)
        if action_match:
            chunks.append(DocumentChunk(
                chunk_id="POLICY-ACTIONS",
                source_type=ProvenanceType.POLICY,
                title="Canonical Action Definitions",
                ref=f"{file_path.name}#actions",
                content=action_match.group(0),
                keywords=["actions", "canonical", "allow_transaction", "block_card", "verify_with_customer", "decline_transaction"]
            ))

        # 2. Approval Routing Chunk
        approval_match = re.search(r"### 2\. Approval Routing Hierarchy.*?(?=### 3\.|$)", text, re.DOTALL)
        if approval_match:
            chunks.append(DocumentChunk(
                chunk_id="POLICY-APPROVALS",
                source_type=ProvenanceType.POLICY,
                title="Approval Routing Hierarchy (auto, L1, L2)",
                ref=f"{file_path.name}#approvals",
                content=approval_match.group(0),
                keywords=["approvals", "l1", "l2", "auto", "statutory", "route", "team lead", "fraud manager"]
            ))

        # 3. Individual Rules R1 through R10
        rules_pattern = re.compile(
            r"- \*\*Rule (R\d+): ([^\*]+)\*\*(.*?)(?=- \*\*Rule R|\n---\n|### 4\.|$)",
            re.DOTALL
        )
        for match in rules_pattern.finditer(text):
            rule_id = match.group(1).upper()
            rule_name = match.group(2).strip()
            rule_body = match.group(3).strip()
            full_content = f"Rule {rule_id}: {rule_name}\n{rule_body}"

            keywords = [rule_id.lower(), rule_name.lower()]
            if rule_id == "R1":
                keywords.extend(["weak signal", "single signal", "verify_with_customer", "step_up_auth", "low probability", "risk score"])
            elif rule_id == "R2":
                keywords.extend(["denies", "denied", "customer denied", "block_card", "create_case", "unauthorized"])
            elif rule_id == "R3":
                keywords.extend(["confirms", "confirmed", "legitimate", "close_no_fraud", "travel", "routine spend"])
            elif rule_id == "R4":
                keywords.extend(["no reply", "timeout", "24 hours", "monitor_card", "decline_transaction"])
            elif rule_id == "R5":
                keywords.extend(["card testing", "small authorizations", "velocity", "step_up_auth", "rapid"])
            elif rule_id == "R6":
                keywords.extend(["shared origin", "syndicate", "shared device", "device profile", "monitor_connected_cards", "file_report", "sar"])
            elif rule_id == "R7":
                keywords.extend(["recurring spend", "subscription", "warn_customer", "disputed recurring", "do not block"])
            elif rule_id == "R8":
                keywords.extend(["escalate", "uncertain", "escalate_to_analyst", "exposure > 500", "conflicting evidence"])
            elif rule_id == "R9":
                keywords.extend(["undocumented", "coordinated abuse", "distributed", "pattern", "escalate_to_analyst", "file_report"])
            elif rule_id == "R10":
                keywords.extend(["block_all_cards", "two cards", "digital banking", "compromised credentials", "restriction"])

            chunks.append(DocumentChunk(
                chunk_id=f"POLICY-{rule_id}",
                source_type=ProvenanceType.POLICY,
                title=f"Policy Rule {rule_id}: {rule_name}",
                ref=f"{file_path.name}#{rule_id}",
                content=full_content,
                keywords=keywords
            ))

        # 4. SAR Filing Conditions Chunk
        sar_match = re.search(r"### 4\. Case vs\. Suspicious Activity Report.*?(?=### 5\.|$)", text, re.DOTALL)
        if sar_match:
            chunks.append(DocumentChunk(
                chunk_id="POLICY-SAR",
                source_type=ProvenanceType.POLICY,
                title="Suspicious Activity Report (SAR) Criteria & Thresholds",
                ref=f"{file_path.name}#sar",
                content=sar_match.group(0),
                keywords=["sar", "fincen", "file_report", "1000", "exposure", "regulatory", "mandatory"]
            ))

        # 5. Next-Best-Action Evolution Chunk
        nba_match = re.search(r"### 5\. Next-Best-Action Evolution Model.*?(?=### 6\.|$)", text, re.DOTALL)
        if nba_match:
            chunks.append(DocumentChunk(
                chunk_id="POLICY-NEXT-BEST-ACTION",
                source_type=ProvenanceType.POLICY,
                title="Next-Best-Action Evolution Model (initial vs final)",
                ref=f"{file_path.name}#next-best-action",
                content=nba_match.group(0),
                keywords=["next-best-action", "initial", "final", "evolution", "what_changed", "evidence loop"]
            ))

        # 6. Exposure Calculation
        exp_match = re.search(r"### 6\. Exposure Calculation.*?(?=### 7\.|$)", text, re.DOTALL)
        if exp_match:
            chunks.append(DocumentChunk(
                chunk_id="POLICY-EXPOSURE",
                source_type=ProvenanceType.POLICY,
                title="Exposure Calculation Formula",
                ref=f"{file_path.name}#exposure",
                content=exp_match.group(0),
                keywords=["exposure", "usd", "affected_txn_ids", "calculation"]
            ))

        # 7. Stopping Criteria
        stop_match = re.search(r"### 7\. Investigation Stopping Criteria.*", text, re.DOTALL)
        if stop_match:
            chunks.append(DocumentChunk(
                chunk_id="POLICY-STOPPING-CRITERIA",
                source_type=ProvenanceType.POLICY,
                title="Investigation Stopping Criteria",
                ref=f"{file_path.name}#stopping-criteria",
                content=stop_match.group(0),
                keywords=["stopping criteria", "stop reason", "sufficient evidence", "settled"]
            ))

        return chunks

    @staticmethod
    def chunk_spec_and_typologies(file_path: Path) -> List[DocumentChunk]:
        """Extracts documented fraud typologies and system guidelines from hackathon_spec or requirements.md."""
        validate_path_allowed(str(file_path))
        if not file_path.exists():
            return []

        text = file_path.read_text(encoding="utf-8")
        chunks: List[DocumentChunk] = []

        # Standard Typologies
        typologies = [
            (
                "TYPOLOGY-CARD-TESTING",
                "Card Testing Typology",
                "card_testing",
                "Multiple rapid low-value online authorizations ($< 5.00) testing account validity followed by high-value checkout. Associated with automated script attacks.",
                ["card testing", "small authorizations", "velocity", "automated", "bot", "script"]
            ),
            (
                "TYPOLOGY-CNP-FRAUD",
                "Card-Not-Present (CNP) Fraud Typology",
                "card_not_present_fraud",
                "Online or e-commerce purchases inconsistent with historical cadence or product categories, typically occurring in 2-4 transaction bursts over 48 hours.",
                ["cnp", "card not present", "ecommerce", "online purchase", "burst"]
            ),
            (
                "TYPOLOGY-CNP-NEW-DEVICE",
                "CNP Fraud with New / Compromised Device Typology",
                "card_not_present_new_device",
                "High-risk online authorizations originating from an unrecognized device profile (id_15: New) or anonymous proxy (id_23: IP_PROXY) with identity discrepancies.",
                ["new device", "proxy", "anonymous proxy", "id_15", "id_23", "device mismatch"]
            ),
            (
                "TYPOLOGY-OUT-OF-REGION",
                "Out-of-Region / Geo-Velocity Typology",
                "out_of_region_use",
                "Physical card-present authorizations in novel billing regions without preceding travel patterns or impossible transit speed between successive transactions.",
                ["out of region", "travel", "novel region", "geo velocity", "billing region", "foreign"]
            ),
            (
                "TYPOLOGY-ACCOUNT-TAKEOVER",
                "Account Takeover (ATO) Typology",
                "account_takeover",
                "Rapid change in digital identity parameters (email domain, phone, device) followed by immediate card usage or limit testing across multiple merchant channels.",
                ["account takeover", "ato", "credential compromise", "email domain change"]
            ),
            (
                "TYPOLOGY-SHARED-DEVICE-RING",
                "Coordinated Multi-Card Device Ring Typology",
                "multi_card_device_cluster",
                "A single device profile or IP footprint linked across 5 or more distinct payment cards or customer accounts, indicating syndicate infrastructure abuse.",
                ["syndicate", "shared device", "device ring", "cluster", "multi card", "compromise ring"]
            ),
            (
                "TYPOLOGY-UNDOCUMENTED",
                "Undocumented Coordinated Abuse Typology",
                "undocumented",
                "Novel fraudulent behavior or abuse schemes not conforming to the 5 standard typologies, but showing structural repetition or coordinated multi-account anomalies (cites Rule R9).",
                ["undocumented", "novel fraud", "coordinated abuse", "anomaly", "r9"]
            ),
            (
                "TYPOLOGY-ROUTINE-TRAVEL",
                "Routine Travel & Weekend Spending (False Alarm)",
                "routine_travel_anomaly",
                "Elevated machine-learning risk score triggered by recurring weekend travel, vacation spending, or familiar merchant patterns that match historical customer baselines.",
                ["routine travel", "benign", "false alarm", "recurring spend", "weekend"]
            )
        ]

        for cid, title, code, desc, keywords in typologies:
            chunks.append(DocumentChunk(
                chunk_id=cid,
                source_type=ProvenanceType.TYPOLOGY,
                title=title,
                ref=f"typology_spec#{code}",
                content=f"Typology Code: {code}\nName: {title}\nDescription: {desc}",
                keywords=keywords
            ))

        return chunks
