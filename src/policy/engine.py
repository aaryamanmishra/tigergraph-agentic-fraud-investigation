"""
Deterministic Fraud Policy Engine.
Enforces Fraud Policy v1.0 (Rules R1 to R10, Section 2, and Section 3a).
Completely independent of LLM reasoning.
"""

from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field

from src.policy.actions import Action, ApprovalRoute, ActionRecommendation, get_statutory_approval_route
from src.policy.exposure import (
    exceeds_escalation_threshold,
    exceeds_sar_threshold,
    exceeds_manager_approval_threshold
)


class InvestigationState(BaseModel):
    """Structured input state representing all evidence gathered during investigation."""
    case_id: str
    flagged_txn_id: str
    card_id: str
    customer_id: str
    fraud_probability: float = Field(..., ge=0.0, le=1.0)
    verdict: str = Field(..., pattern="^(fraud|legitimate|uncertain)$")
    pattern: str = Field(default="none")
    exposure_usd: float = Field(default=0.0, ge=0.0)
    affected_txn_ids: List[str] = Field(default_factory=list)
    
    # Signal and investigation conditions
    is_single_signal: bool = False
    customer_reply: Optional[str] = Field(
        default=None,
        description="One of: 'confirmed', 'denied', 'no_reply_24h', 'disputed_recurring', None"
    )
    card_testing_detected: bool = False
    card_testing_cleared_over_100: bool = False
    
    # Infrastructure & Network conditions
    shared_origin_detected: bool = False
    shared_origin_element: Optional[str] = None
    connected_card_ids: List[str] = Field(default_factory=list)
    
    # Abuse & Conflict conditions
    is_undocumented_abuse: bool = False
    conflicting_evidence: bool = False
    
    # Portfolio conditions for R10
    num_compromised_cards_for_customer: int = 1
    credentials_compromised: bool = False
    
    # Stage of evaluation
    stage: str = Field(default="initial", pattern="^(initial|final)$")


class PolicyEvaluationResult(BaseModel):
    """Deterministic output produced by the Policy Engine."""
    recommended_actions: List[Dict[str, str]]
    approval_routes: List[str]
    policy_rules_triggered: List[str]
    requires_more_evidence: bool
    sar_required: bool
    case_required: bool
    reason: str


class PolicyEngine:
    """
    Deterministic rule engine enforcing Rules R1–R10.
    Order of recommended actions reflects chronological execution order.
    """

    @classmethod
    def evaluate(cls, state: InvestigationState) -> PolicyEvaluationResult:
        recommendations: List[ActionRecommendation] = []
        rules_triggered: Set[str] = set()
        requires_more_evidence = False
        reasons: List[str] = []

        # =========================================================================
        # RULE R3: Customer confirms transaction (Immediate Legitimacy)
        # =========================================================================
        if state.customer_reply == "confirmed":
            rules_triggered.add("R3")
            recommendations.append(
                ActionRecommendation(
                    action=Action.CLOSE_NO_FRAUD,
                    route=ApprovalRoute.AUTO,
                    reason="R3: Customer confirmed the transaction as legitimate"
                )
            )
            reasons.append("Customer confirmed transaction authorization under Rule R3.")
            return PolicyEvaluationResult(
                recommended_actions=[r.to_dict() for r in recommendations],
                approval_routes=[r.route.value for r in recommendations],
                policy_rules_triggered=sorted(list(rules_triggered)),
                requires_more_evidence=False,
                sar_required=False,
                case_required=False,
                reason="; ".join(reasons)
            )

        # =========================================================================
        # RULE R7: Disputed but legitimate recurring spend
        # =========================================================================
        if state.customer_reply == "disputed_recurring":
            rules_triggered.add("R7")
            recommendations.append(
                ActionRecommendation(
                    action=Action.CREATE_CASE,
                    route=ApprovalRoute.AUTO,
                    reason="R7: Disputed recurring charge requires formal investigation record"
                )
            )
            recommendations.append(
                ActionRecommendation(
                    action=Action.VERIFY_WITH_CUSTOMER,
                    route=ApprovalRoute.AUTO,
                    reason="R7: Re-verify recurring subscription context with cardholder"
                )
            )
            recommendations.append(
                ActionRecommendation(
                    action=Action.WARN_CUSTOMER,
                    route=ApprovalRoute.AUTO,
                    reason="R7: Send recurring charge notice / reminder to customer"
                )
            )
            reasons.append("Charge matches established recurring pattern; card not blocked under Rule R7.")
            return PolicyEvaluationResult(
                recommended_actions=[r.to_dict() for r in recommendations],
                approval_routes=[r.route.value for r in recommendations],
                policy_rules_triggered=sorted(list(rules_triggered)),
                requires_more_evidence=False,
                sar_required=False,
                case_required=True,
                reason="; ".join(reasons)
            )

        # =========================================================================
        # RULE R1: Verify before you block on a weak signal
        # =========================================================================
        # If case rests on single signal & fraud_probability < 0.70 at initial stage
        if state.stage == "initial" and state.is_single_signal and state.fraud_probability < 0.70:
            rules_triggered.add("R1")
            requires_more_evidence = True
            recommendations.append(
                ActionRecommendation(
                    action=Action.VERIFY_WITH_CUSTOMER,
                    route=ApprovalRoute.AUTO,
                    reason=f"R1: Single signal with fraud probability {state.fraud_probability:.2f} < 0.70; verify before blocking"
                )
            )
            reasons.append(f"Single weak signal (prob {state.fraud_probability:.2f} < 0.70) mandates customer verification under Rule R1.")

        # =========================================================================
        # RULE R5: Card Testing Sequence
        # =========================================================================
        elif state.card_testing_detected:
            rules_triggered.add("R5")
            recommendations.append(
                ActionRecommendation(
                    action=Action.DECLINE_TRANSACTION,
                    route=ApprovalRoute.L1,
                    reason="R5: Rapid small authorization sequence detected"
                )
            )
            if state.card_testing_cleared_over_100:
                block_route = ApprovalRoute.L2 if exceeds_manager_approval_threshold(state.exposure_usd) else ApprovalRoute.L1
                recommendations.append(
                    ActionRecommendation(
                        action=Action.BLOCK_CARD,
                        route=block_route,
                        reason="R5: Card testing confirmed and purchase over $100 has already cleared"
                    )
                )
            else:
                recommendations.append(
                    ActionRecommendation(
                        action=Action.STEP_UP_AUTH,
                        route=ApprovalRoute.AUTO,
                        reason="R5: Challenge subsequent activity with step-up authentication"
                    )
                )
            reasons.append("Card testing authorization sequence detected under Rule R5.")

        # =========================================================================
        # RULE R2: Customer denies transaction
        # =========================================================================
        elif state.customer_reply == "denied":
            rules_triggered.add("R2")
            block_route = ApprovalRoute.L2 if exceeds_manager_approval_threshold(state.exposure_usd) else ApprovalRoute.L1
            recommendations.append(
                ActionRecommendation(
                    action=Action.BLOCK_CARD,
                    route=block_route,
                    reason=f"R2: Customer denied transaction; exposure ${state.exposure_usd:,.2f}"
                )
            )
            recommendations.append(
                ActionRecommendation(
                    action=Action.CREATE_CASE,
                    route=ApprovalRoute.AUTO,
                    reason="R2: Internal fraud case opened following customer denial"
                )
            )
            reasons.append("Customer denied authorization under Rule R2.")

        # =========================================================================
        # RULE R4: No customer reply within 24 hours
        # =========================================================================
        elif state.customer_reply == "no_reply_24h":
            rules_triggered.add("R4")
            recommendations.append(
                ActionRecommendation(
                    action=Action.MONITOR_CARD,
                    route=ApprovalRoute.AUTO,
                    reason="R4: Verification timed out after 24h; heighten monitoring sensitivity"
                )
            )
            recommendations.append(
                ActionRecommendation(
                    action=Action.DECLINE_TRANSACTION,
                    route=ApprovalRoute.L1,
                    reason="R4: Decline pending authorizations pending customer contact"
                )
            )
            if exceeds_escalation_threshold(state.exposure_usd):
                recommendations.append(
                    ActionRecommendation(
                        action=Action.ESCALATE_TO_ANALYST,
                        route=ApprovalRoute.AUTO,
                        reason=f"R4: Exposure ${state.exposure_usd:,.2f} exceeds $500 threshold with no customer reply"
                    )
                )
            reasons.append("No reply from customer within 24 hours under Rule R4.")

        # =========================================================================
        # RULE R9: Undocumented Patterns with Coordinated Abuse
        # =========================================================================
        if state.pattern == "undocumented" or state.is_undocumented_abuse:
            rules_triggered.add("R9")
            if not any(r.action == Action.CREATE_CASE for r in recommendations):
                recommendations.append(
                    ActionRecommendation(
                        action=Action.CREATE_CASE,
                        route=ApprovalRoute.AUTO,
                        reason="R9: Documented coordinated/repeated abuse requiring formal case"
                    )
                )
            if not any(r.action == Action.FILE_REPORT for r in recommendations):
                recommendations.append(
                    ActionRecommendation(
                        action=Action.FILE_REPORT,
                        route=ApprovalRoute.L2,
                        reason="R9: Coordinated undocumented abuse requires regulatory filing"
                    )
                )
            if not any(r.action == Action.ESCALATE_TO_ANALYST for r in recommendations):
                recommendations.append(
                    ActionRecommendation(
                        action=Action.ESCALATE_TO_ANALYST,
                        route=ApprovalRoute.AUTO,
                        reason="R9: Undocumented typology escalated to human Tier-2 analyst"
                    )
                )
            reasons.append("Undocumented coordinated abuse identified under Rule R9.")

        # =========================================================================
        # RULE R6: Shared Origin (Shared Device / Region / Recipient Email)
        # =========================================================================
        if state.shared_origin_detected:
            rules_triggered.add("R6")
            if not any(r.action == Action.CREATE_CASE for r in recommendations):
                recommendations.append(
                    ActionRecommendation(
                        action=Action.CREATE_CASE,
                        route=ApprovalRoute.AUTO,
                        reason="R6: Multi-card compromise sharing infrastructure requires formal case"
                    )
                )
            if not any(r.action == Action.FILE_REPORT for r in recommendations):
                recommendations.append(
                    ActionRecommendation(
                        action=Action.FILE_REPORT,
                        route=ApprovalRoute.L2,
                        reason=f"R6: Shared origin across multiple cards ({state.shared_origin_element or 'device/region/email'})"
                    )
                )
            if not any(r.action == Action.MONITOR_CONNECTED_CARDS for r in recommendations):
                recommendations.append(
                    ActionRecommendation(
                        action=Action.MONITOR_CONNECTED_CARDS,
                        route=ApprovalRoute.AUTO,
                        reason=f"R6: Place {len(state.connected_card_ids)} connected cards sharing origin under monitoring"
                    )
                )
            reasons.append("Shared origin infrastructure detected across multiple cards under Rule R6.")

        # =========================================================================
        # RULE R8: Escalate when uncertain and exposed (> $500 or conflicting)
        # =========================================================================
        if state.verdict == "uncertain" and (exceeds_escalation_threshold(state.exposure_usd) or state.conflicting_evidence):
            rules_triggered.add("R8")
            if not any(r.action == Action.ESCALATE_TO_ANALYST for r in recommendations):
                recommendations.append(
                    ActionRecommendation(
                        action=Action.ESCALATE_TO_ANALYST,
                        route=ApprovalRoute.AUTO,
                        reason=f"R8: Uncertain verdict with exposure ${state.exposure_usd:,.2f} > $500 or conflicting evidence"
                    )
                )
            reasons.append("Uncertain verdict with high exposure escalated under Rule R8.")

        # =========================================================================
        # RULE R10: Restriction on BLOCK_ALL_CARDS
        # =========================================================================
        # BLOCK_ALL_CARDS is only allowed if 2+ customer cards confirmed fraud OR credentials compromised
        if state.num_compromised_cards_for_customer >= 2 or state.credentials_compromised:
            rules_triggered.add("R10")
            # Can recommend BLOCK_ALL_CARDS if high fraud probability
            if state.fraud_probability >= 0.85:
                recommendations.append(
                    ActionRecommendation(
                        action=Action.BLOCK_ALL_CARDS,
                        route=ApprovalRoute.L2,
                        reason="R10: Customer portfolio compromise confirmed across multiple cards or credentials"
                    )
                )
                reasons.append("Portfolio-level compromise satisfies Rule R10 conditions.")

        # =========================================================================
        # SECTION 3a: Formal Case vs. SAR Filing Requirements
        # =========================================================================
        # A case must be opened whenever fraud probability >= 0.30, evidence is requested, or customer disputes
        case_mandated = (
            state.fraud_probability >= 0.30
            or requires_more_evidence
            or state.customer_reply in ("denied", "disputed_recurring")
            or "CREATE_CASE" in [r.action.value for r in recommendations]
        )
        if case_mandated and not any(r.action == Action.CREATE_CASE for r in recommendations):
            recommendations.append(
                ActionRecommendation(
                    action=Action.CREATE_CASE,
                    route=ApprovalRoute.AUTO,
                    reason="Section 3a: Investigation warrants formal case record (fraud prob >= 0.30 or evidence requested)"
                )
            )

        # A SAR must be filed when fraud is confirmed/strongly suspected AND:
        # exposure > $1,000 OR shared device/region/card OR undocumented R9
        sar_mandated = False
        is_fraud_confirmed = state.verdict == "fraud" or state.fraud_probability >= 0.70 or state.customer_reply == "denied"
        if is_fraud_confirmed:
            if exceeds_sar_threshold(state.exposure_usd):
                sar_mandated = True
            elif state.shared_origin_detected or len(state.connected_card_ids) > 0:
                sar_mandated = True
            elif state.pattern == "undocumented" or state.is_undocumented_abuse:
                sar_mandated = True

        if sar_mandated and not any(r.action == Action.FILE_REPORT for r in recommendations):
            recommendations.append(
                ActionRecommendation(
                    action=Action.FILE_REPORT,
                    route=ApprovalRoute.L2,
                    reason="Section 3a: Confirmed/suspected fraud meeting regulatory exposure or shared infrastructure threshold"
                )
            )

        # Fallback for low-risk unflagged cases
        if not recommendations:
            if state.fraud_probability <= 0.15:
                recommendations.append(
                    ActionRecommendation(
                        action=Action.CLOSE_NO_FRAUD,
                        route=ApprovalRoute.AUTO,
                        reason="Assessed fraud probability <= 0.15; no suspicious pattern detected"
                    )
                )
            else:
                recommendations.append(
                    ActionRecommendation(
                        action=Action.MONITOR_CARD,
                        route=ApprovalRoute.AUTO,
                        reason="Card remains active; heighten monitoring sensitivity"
                    )
                )

        # Deduplicate recommendations preserving order
        unique_recs: List[ActionRecommendation] = []
        seen_actions: Set[Action] = set()
        for rec in recommendations:
            if rec.action not in seen_actions:
                seen_actions.add(rec.action)
                unique_recs.append(rec)

        # Verify whether SAR or Case is required in final unique recommendations
        has_sar = any(r.action == Action.FILE_REPORT for r in unique_recs)
        has_case = any(r.action == Action.CREATE_CASE for r in unique_recs)

        return PolicyEvaluationResult(
            recommended_actions=[r.to_dict() for r in unique_recs],
            approval_routes=[r.route.value for r in unique_recs],
            policy_rules_triggered=sorted(list(rules_triggered)),
            requires_more_evidence=requires_more_evidence,
            sar_required=has_sar,
            case_required=has_case,
            reason="; ".join(reasons) if reasons else "Policy evaluation completed."
        )
