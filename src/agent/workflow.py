"""
Investigation Workflow State Machine for TigerGraph Fraud Investigation Agent.
Coordinates lifecycle transitions across modular investigation nodes.
"""

import time
from typing import Dict, Any, Optional

from src.agent.state import InvestigationState, CaseStatus, StopReason
from src.agent.tools.contracts import InvestigationTools
from src.agent.nodes import InvestigationNodes


class InvestigationWorkflow:
    """
    Executes the multi-stage fraud investigation lifecycle.
    Enforces observation/action separation, deterministic policy evaluation, and complete audit timeline.
    """

    def __init__(self, tools: Optional[InvestigationTools] = None):
        self.tools = tools or InvestigationTools()

    def run(self, initial_state_or_case: Any) -> InvestigationState:
        """
        Executes the full investigation workflow on a case or initialized state.
        Returns the finalized InvestigationState.
        """
        t0 = time.time()

        if isinstance(initial_state_or_case, InvestigationState):
            state = initial_state_or_case
        elif isinstance(initial_state_or_case, dict):
            state = InvestigationState(
                case_id=initial_state_or_case.get("case_id", ""),
                trigger_type=initial_state_or_case.get("trigger_type", ""),
                trigger_text=initial_state_or_case.get("trigger_text", ""),
                flagged_txn_id=str(initial_state_or_case.get("flagged_txn_id", "")),
                card_id=initial_state_or_case.get("card_id", ""),
                customer_id=initial_state_or_case.get("customer_id", "")
            )
        else:
            raise ValueError("Input must be an InvestigationState instance or dictionary.")

        # Stage 1: Load Case
        state = InvestigationNodes.load_case(state, self.tools)

        # Stage 2: Investigate Transaction
        state = InvestigationNodes.investigate_transaction(state, self.tools)

        # Stage 3: Investigate Relationships (Card history, customer, device)
        state = InvestigationNodes.investigate_relationships(state, self.tools)

        # Stage 4: Retrieve Prior Cases
        state = InvestigationNodes.retrieve_prior_cases(state, self.tools)

        # Stage 5: Assess Evidence
        state = InvestigationNodes.assess_evidence(state, self.tools)

        # Stage 6: Assess Uncertainty
        state = InvestigationNodes.assess_uncertainty(state, self.tools)

        # Stage 7 & 8: Evidence Loop (only if uncertainty warrants outreach)
        if state.case_status == CaseStatus.EVIDENCE_LOOP:
            state = InvestigationNodes.request_evidence(state, self.tools)
            state = InvestigationNodes.reassess(state, self.tools)

        # Stage 9: Apply Policy (Deterministic PolicyEngine)
        state = InvestigationNodes.apply_policy(state, self.tools)

        # Stage 10: Prepare Case
        state = InvestigationNodes.prepare_case(state, self.tools)

        # Stage 11: Write Case
        state = InvestigationNodes.write_case(state, self.tools)

        # Stage 12: Finish
        state = InvestigationNodes.finish(state, self.tools)

        state.latency_ms = round((time.time() - t0) * 1000, 2)
        return state
