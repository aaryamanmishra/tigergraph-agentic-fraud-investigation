"""
InvestigationState for TigerGraph Fraud Investigation Agent.
Provides strongly-typed state management throughout the investigation lifecycle.
Enforces strict separation between FACT, DERIVED, and INFERENCE evidence categories.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional
import datetime


class EvidenceCategory(str, Enum):
    """
    Strict categorization of evidence:
    - FACT: Directly returned by dataset or TigerGraph database queries.
    - DERIVED: Deterministically calculated from graph data / statistics (e.g. cluster size, velocity, mean).
    - INFERENCE: Reasoned conclusion, hypothesis, or interpretation produced by the agent.
    """
    FACT = "FACT"
    DERIVED = "DERIVED"
    INFERENCE = "INFERENCE"


class CaseStatus(str, Enum):
    """Lifecycle statuses for an investigation case."""
    INITIALIZED = "INITIALIZED"
    OBSERVING = "OBSERVING"
    EVIDENCE_GATHERING = "EVIDENCE_GATHERING"
    ASSESSING = "ASSESSING"
    EVIDENCE_LOOP = "EVIDENCE_LOOP"
    REASSESSING = "REASSESSING"
    POLICY_EVALUATION = "POLICY_EVALUATION"
    PREPARING_CASE = "PREPARING_CASE"
    PERSISTING = "PERSISTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StopReason(str, Enum):
    """Explicit terminal stopping criteria for the investigation loop."""
    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    CUSTOMER_CONFIRMED = "customer_confirmed"
    CUSTOMER_DENIED = "customer_denied"
    NO_ADDITIONAL_EVIDENCE_AVAILABLE = "no_additional_evidence_available"
    POLICY_ACTION_SELECTED = "policy_action_selected"
    ANALYST_ESCALATION = "analyst_escalation"
    INVESTIGATION_ERROR = "investigation_error"


@dataclass
class EvidenceItem:
    """Individual item of evidence with provenance and confidence tracking."""
    category: EvidenceCategory
    source: str
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value if isinstance(self.category, EvidenceCategory) else self.category,
            "source": self.source,
            "description": self.description,
            "data": self.data,
            "confidence": self.confidence,
            "timestamp": self.timestamp
        }


@dataclass
class TimelineEvent:
    """Structured audit trail event for UI visualization and explainability."""
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    stage: str = ""
    tool_used: str = ""
    evidence_discovered: str = ""
    result: str = ""
    state_change: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "stage": self.stage,
            "tool_used": self.tool_used,
            "evidence_discovered": self.evidence_discovered,
            "result": self.result,
            "state_change": self.state_change
        }


@dataclass
class InvestigationState:
    """
    Complete, typed agent investigation state tracking all phases of a fraud investigation.
    """

    # 1. Case identity
    case_id: str = ""
    trigger_type: str = ""  # "risk_score" | "customer_report" | "analyst_request"
    trigger_text: str = ""
    flagged_txn_id: str = ""

    # 2. Core entities
    customer_id: str = ""
    card_id: str = ""
    transaction_ids: List[str] = field(default_factory=list)
    connected_card_ids: List[str] = field(default_factory=list)
    device_profile_ids: List[str] = field(default_factory=list)
    email_domains: List[str] = field(default_factory=list)
    billing_regions: List[str] = field(default_factory=list)

    # 3. Categorized evidence repository (FACT vs DERIVED vs INFERENCE)
    facts: List[EvidenceItem] = field(default_factory=list)
    derived: List[EvidenceItem] = field(default_factory=list)
    inferences: List[EvidenceItem] = field(default_factory=list)

    # 4. Investigation evidence summaries
    transaction_context: Optional[Dict[str, Any]] = None
    card_history_summary: Optional[Dict[str, Any]] = None
    customer_history_summary: Optional[Dict[str, Any]] = None
    connected_card_evidence: Optional[Dict[str, Any]] = None
    device_evidence: Optional[Dict[str, Any]] = None
    transaction_chain_evidence: Optional[Dict[str, Any]] = None
    prior_case_evidence: List[Dict[str, Any]] = field(default_factory=list)
    pattern_evidence: Dict[str, Any] = field(default_factory=dict)

    # 5. Assessment
    fraud_probability: float = 0.0  # 0.0 to 1.0
    verdict: str = "inconclusive"    # "fraud" | "benign" | "inconclusive"
    fraud_pattern: str = "none"     # "routine_travel_anomaly" | "multi_card_device_cluster" | "card_testing" | ...
    pattern_description: str = ""
    uncertainty: str = "high"       # "low" | "medium" | "high"
    missing_evidence: List[str] = field(default_factory=list)
    first_suspicious_txn_id: Optional[str] = None
    affected_txn_ids: List[str] = field(default_factory=list)
    exposure_usd: float = 0.0

    # 6. Evidence loop
    evidence_requests: List[Dict[str, Any]] = field(default_factory=list)
    evidence_responses: List[Dict[str, Any]] = field(default_factory=list)
    customer_response: Optional[str] = None
    requires_more_evidence: bool = False
    initial_assessment: Optional[Dict[str, Any]] = None
    final_assessment: Optional[Dict[str, Any]] = None

    # 7. Policy evaluation
    policy_rules_triggered: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    approval_routes: List[str] = field(default_factory=list)
    sar_required: bool = False

    # 8. Case lifecycle
    case_status: CaseStatus = CaseStatus.INITIALIZED
    stop_reason: Optional[StopReason] = None
    investigation_timeline: List[TimelineEvent] = field(default_factory=list)
    graph_case_id: Optional[str] = None
    written_to_graph: bool = False

    # 9. Observability & diagnostics
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    errors: List[str] = field(default_factory=list)

    def add_fact(self, source: str, description: str, data: Optional[Dict[str, Any]] = None) -> EvidenceItem:
        """Appends a verified database or dataset ground truth fact."""
        item = EvidenceItem(
            category=EvidenceCategory.FACT,
            source=source,
            description=description,
            data=data or {}
        )
        self.facts.append(item)
        return item

    def add_derived(self, source: str, description: str, data: Optional[Dict[str, Any]] = None, confidence: float = 1.0) -> EvidenceItem:
        """Appends a deterministic analytical computation derived from graph facts."""
        item = EvidenceItem(
            category=EvidenceCategory.DERIVED,
            source=source,
            description=description,
            data=data or {},
            confidence=confidence
        )
        self.derived.append(item)
        return item

    def add_inference(self, source: str, description: str, data: Optional[Dict[str, Any]] = None, confidence: float = 0.8) -> EvidenceItem:
        """Appends an investigative hypothesis or conclusion produced by reasoning."""
        item = EvidenceItem(
            category=EvidenceCategory.INFERENCE,
            source=source,
            description=description,
            data=data or {},
            confidence=confidence
        )
        self.inferences.append(item)
        return item

    def append_timeline_event(
        self,
        stage: str,
        tool_used: str,
        evidence_discovered: str,
        result: str,
        state_change: str = ""
    ) -> TimelineEvent:
        """Appends a structured event to the investigation audit timeline."""
        event = TimelineEvent(
            stage=stage,
            tool_used=tool_used,
            evidence_discovered=evidence_discovered,
            result=result,
            state_change=state_change
        )
        self.investigation_timeline.append(event)
        return event

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the investigation state into a structured JSON-compatible dictionary."""
        return {
            "case_identity": {
                "case_id": self.case_id,
                "trigger_type": self.trigger_type,
                "trigger_text": self.trigger_text,
                "flagged_txn_id": self.flagged_txn_id
            },
            "entities": {
                "customer_id": self.customer_id,
                "card_id": self.card_id,
                "transaction_ids": self.transaction_ids,
                "connected_card_ids": self.connected_card_ids,
                "device_profile_ids": self.device_profile_ids,
                "email_domains": self.email_domains,
                "billing_regions": self.billing_regions
            },
            "evidence": {
                "facts": [f.to_dict() for f in self.facts],
                "derived": [d.to_dict() for d in self.derived],
                "inferences": [i.to_dict() for i in self.inferences],
                "transaction_context": self.transaction_context,
                "card_history_summary": self.card_history_summary,
                "customer_history_summary": self.customer_history_summary,
                "connected_card_evidence": self.connected_card_evidence,
                "device_evidence": self.device_evidence,
                "transaction_chain_evidence": self.transaction_chain_evidence,
                "prior_case_evidence": self.prior_case_evidence,
                "pattern_evidence": self.pattern_evidence
            },
            "assessment": {
                "fraud_probability": self.fraud_probability,
                "verdict": self.verdict,
                "fraud_pattern": self.fraud_pattern,
                "pattern_description": self.pattern_description,
                "uncertainty": self.uncertainty,
                "missing_evidence": self.missing_evidence,
                "first_suspicious_txn_id": self.first_suspicious_txn_id,
                "affected_txn_ids": self.affected_txn_ids,
                "exposure_usd": self.exposure_usd
            },
            "evidence_loop": {
                "evidence_requests": self.evidence_requests,
                "evidence_responses": self.evidence_responses,
                "initial_assessment": self.initial_assessment,
                "final_assessment": self.final_assessment
            },
            "policy": {
                "policy_rules_triggered": self.policy_rules_triggered,
                "recommended_actions": self.recommended_actions,
                "approval_routes": self.approval_routes,
                "sar_required": self.sar_required
            },
            "lifecycle": {
                "case_status": self.case_status.value if isinstance(self.case_status, CaseStatus) else self.case_status,
                "stop_reason": self.stop_reason.value if isinstance(self.stop_reason, StopReason) else self.stop_reason,
                "investigation_timeline": [e.to_dict() for e in self.investigation_timeline],
                "graph_case_id": self.graph_case_id,
                "written_to_graph": self.written_to_graph
            },
            "observability": {
                "tool_calls": self.tool_calls,
                "latency_ms": self.latency_ms,
                "token_usage": self.token_usage,
                "errors": self.errors
            }
        }
