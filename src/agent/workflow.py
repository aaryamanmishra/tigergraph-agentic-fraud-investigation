"""
Investigation Workflow State Machine for TigerGraph Fraud Investigation Agent.
Coordinates lifecycle transitions across modular investigation nodes.
Equipped with step guard, LLM provider integration, and deterministic policy evaluation.
"""

import time
from typing import Dict, Any, Optional

from src.agent.state import InvestigationState, CaseStatus, StopReason
from src.agent.tools.contracts import InvestigationTools
from src.agent.nodes import InvestigationNodes
from src.agent.llm.base import BaseLLMProvider
from src.agent.llm.factory import get_llm_provider


class InvestigationWorkflow:
    """
    Executes the multi-stage fraud investigation lifecycle.
    Enforces observation/action separation, deterministic policy evaluation,
    LLM reasoning grounding, and a step guard preventing infinite cycles.
    """

    def __init__(
        self,
        tools: Optional[InvestigationTools] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        max_steps: int = 10
    ):
        self.tools = tools or InvestigationTools()
        self.llm_provider = llm_provider if llm_provider is not None else get_llm_provider()
        self.max_steps = max_steps

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

        step_count = 0

        # Stage 1: Load Case
        state = InvestigationNodes.load_case(state, self.tools)
        step_count += 1

        # Stage 2: Investigate Transaction
        state = InvestigationNodes.investigate_transaction(state, self.tools)
        step_count += 1

        # Stage 3: Investigate Relationships (Card history, customer, device)
        state = InvestigationNodes.investigate_relationships(state, self.tools)
        step_count += 1

        # Stage 4: Retrieve Prior Cases
        state = InvestigationNodes.retrieve_prior_cases(state, self.tools)
        step_count += 1

        # Stage 5: Assess Evidence (with optional LLM reasoning)
        state = InvestigationNodes.assess_evidence(state, self.tools, llm=self.llm_provider)
        step_count += 1

        # Stage 6: Assess Uncertainty
        state = InvestigationNodes.assess_uncertainty(state, self.tools)
        step_count += 1

        # Step Guard Check: If exceeded step limit, conclude observation
        if step_count >= self.max_steps:
            state.stop_reason = StopReason.SUFFICIENT_EVIDENCE
            state.append_timeline_event(
                stage="step_guard",
                tool_used="internal:step_guard",
                evidence_discovered=f"Step guard limit reached ({step_count}/{self.max_steps}). Terminating evidence loop.",
                result="MAX_STEPS_REACHED",
                state_change="stop_reason -> sufficient_evidence"
            )

        # Stage 7 & 8: Evidence Loop (only if uncertainty warrants outreach and steps remain)
        if state.case_status == CaseStatus.EVIDENCE_LOOP and step_count < self.max_steps:
            state = InvestigationNodes.request_evidence(state, self.tools, llm=self.llm_provider)
            step_count += 1
            state = InvestigationNodes.reassess(state, self.tools, llm=self.llm_provider)
            step_count += 1

        # Stage 9: Apply Policy (Deterministic PolicyEngine is strictly authoritative)
        state = InvestigationNodes.apply_policy(state, self.tools)
        step_count += 1

        # Stage 10: Prepare Case
        state = InvestigationNodes.prepare_case(state, self.tools)
        step_count += 1

        # Stage 11: Write Case
        state = InvestigationNodes.write_case(state, self.tools)

        # Stage 12: Finish
        state = InvestigationNodes.finish(state, self.tools)

        state.latency_ms = round((time.time() - t0) * 1000, 2)
        return state
