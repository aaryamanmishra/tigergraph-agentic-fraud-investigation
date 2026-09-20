"""
Policy Simulator Interface.
Allows feeding structured investigation states into the deterministic PolicyEngine.
"""

from typing import Dict, Any, Union
from src.policy.engine import PolicyEngine, InvestigationState, PolicyEvaluationResult


class PolicySimulator:
    """Convenience runner for evaluating fraud investigation states against the policy engine."""

    @staticmethod
    def simulate(state_input: Union[Dict[str, Any], InvestigationState]) -> Dict[str, Any]:
        """
        Evaluates an investigation state dictionary or InvestigationState model.
        Returns a serializable dictionary containing recommended actions, approval routes,
        triggered rules, SAR requirement, case requirement, and policy reasoning.
        """
        if isinstance(state_input, dict):
            state = InvestigationState(**state_input)
        else:
            state = state_input

        result: PolicyEvaluationResult = PolicyEngine.evaluate(state)
        return result.model_dump()


def run_simulation(state_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Helper functional wrapper for PolicySimulator.simulate."""
    return PolicySimulator.simulate(state_dict)
