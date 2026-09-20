"""
Pydantic Schemas for LLM Structured Reasoning and Tool Decisioning.
Ensures typed outputs for intermediate reasoning steps, hypothesis generation,
evidence citations, and final fraud synthesis.
"""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field, field_validator


class ToolCallProposal(BaseModel):
    """Next tool recommended by the LLM during investigation."""
    tool_name: str = Field(
        ...,
        description="Name of the investigation tool (e.g. 'get_card_history', 'get_device_neighbors', 'get_similar_closed_cases')"
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of parameters to pass to the tool"
    )
    rationale: str = Field(
        ...,
        description="Investigation rationale explaining why this tool call will reduce uncertainty"
    )


class StructuredFinding(BaseModel):
    """Individual finding grounded in verified evidence."""
    claim: str = Field(..., description="Factual claim or derived conclusion")
    source: Literal["graph", "document", "customer", "external"] = Field(
        ...,
        description=(
            "Evidence source category: must be one of 'graph' (TigerGraph database/queries), "
            "'document' (governing policies, matrix rules, typologies, regulatory requirements), "
            "'customer' (direct verification/inquiry responses), or 'external' (third-party intelligence/benchmarks). "
            "All policy rules (e.g. POLICY-R1 to R10) and matrix documents MUST be classified as 'document'."
        )
    )
    ref: str = Field(..., description="Query name, document name, or data table reference")
    entity_ids: List[str] = Field(
        default_factory=list,
        description="Specific entity IDs supporting this finding (txns, cards, customers, cases, devices)"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, v: Any) -> Any:
        """
        Normalizes policy or rule document sources to canonical 'document' if LLM outputs
        'policy', 'policy_matrix', 'guidelines', 'rules', etc., preventing validation crashes
        or unnecessary repair roundtrips.
        """
        if isinstance(v, str):
            clean = v.strip().lower()
            if clean in ("policy", "policies", "policy_matrix", "guideline", "guidelines", "rule", "rules", "doc", "docs"):
                return "document"
            return clean
        return v


class EvidenceRequestProposal(BaseModel):
    """Proposal to initiate follow-up inquiry (e.g. with cardholder)."""
    type: Literal["customer_validation", "step_up_auth", "analyst_info"] = Field(
        ...,
        description="Standard evidence request typology"
    )
    asked_after_step: int = Field(default=1, ge=1)
    assumed_response: str = Field(..., description="Expected or simulated response text")
    query: str = Field(..., description="Specific inquiry question submitted")


class LLMReasoningStep(BaseModel):
    """
    Structured output for an intermediate step in the investigation loop.
    Encourages structured chain-of-thought, hypothesis testing, and factual grounding.
    """
    thought: str = Field(..., description="Internal investigative reasoning and synthesis")
    observations: List[str] = Field(default_factory=list, description="Key data points noted from prior tool output")
    hypotheses: List[str] = Field(default_factory=list, description="Active fraud or benign hypotheses under consideration")
    findings: List[StructuredFinding] = Field(default_factory=list, description="New findings identified in this step")
    tentative_verdict: Optional[Literal["fraud", "legitimate", "uncertain"]] = Field(
        default=None,
        description="Tentative verdict based on current evidence"
    )
    tentative_pattern: Optional[str] = Field(
        default=None,
        description="Tentative fraud pattern typology"
    )
    uncertainty: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Assessment of remaining uncertainty"
    )
    proposed_tool: Optional[ToolCallProposal] = Field(
        default=None,
        description="Tool call to execute next if more evidence is needed"
    )
    evidence_request: Optional[EvidenceRequestProposal] = Field(
        default=None,
        description="Inquiry to raise if customer or analyst verification is required"
    )


class LLMFinalSynthesis(BaseModel):
    """
    Final comprehensive synthesis produced by the reasoning model.
    Must be fully grounded in accumulated facts and verified entity IDs.
    """
    summary: str = Field(..., description="Executive narrative summary of the case investigation")
    verdict: Literal["fraud", "legitimate", "uncertain"] = Field(
        ...,
        description="Final fraud verdict"
    )
    fraud_probability: float = Field(..., ge=0.0, le=1.0, description="Calibrated posterior probability of fraud")
    pattern: str = Field(
        ...,
        description="Identified pattern: card_testing, card_not_present_fraud, card_not_present_new_device, out_of_region_use, account_takeover, undocumented, or none"
    )
    pattern_description: str = Field(
        default="",
        description="Detailed description required if pattern is 'undocumented', must be empty string otherwise"
    )
    affected_txn_ids: List[str] = Field(
        default_factory=list,
        description="List of fraudulent transaction IDs directly attributed to this case"
    )
    first_suspicious_txn_id: Optional[str] = Field(
        default=None,
        description="ID of the earliest suspicious transaction in the sequence"
    )
    connected_card_ids: List[str] = Field(
        default_factory=list,
        description="List of other card IDs compromised or connected via shared infrastructure"
    )
    connected_device_profiles: List[str] = Field(
        default_factory=list,
        description="Device profiles associated with the malicious activity"
    )
    exposure_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Total monetary exposure in USD (must be 0.0 if legitimate)"
    )
    similar_prior_cases: List[str] = Field(
        default_factory=list,
        description="Historical closed case IDs establishing pattern precedent"
    )
    evidence: List[StructuredFinding] = Field(
        default_factory=list,
        description="Grounded evidence items citing sources, refs, and verified entity IDs"
    )
    sar_narrative: Optional[str] = Field(
        default=None,
        description="Substantial 3-6 sentence SAR narrative naming devices, tactics, and victim accounts if SAR is filed"
    )
