"""
Canonical Action Definitions and Statutory Approval Routes.
Fraud Policy Version 1.0.
"""

from enum import Enum
from typing import NamedTuple, Optional, List


class Action(str, Enum):
    ALLOW_TRANSACTION = "ALLOW_TRANSACTION"
    DECLINE_TRANSACTION = "DECLINE_TRANSACTION"
    MONITOR_CARD = "MONITOR_CARD"
    MONITOR_CONNECTED_CARDS = "MONITOR_CONNECTED_CARDS"
    WARN_CUSTOMER = "WARN_CUSTOMER"
    VERIFY_WITH_CUSTOMER = "VERIFY_WITH_CUSTOMER"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    BLOCK_CARD = "BLOCK_CARD"
    BLOCK_ALL_CARDS = "BLOCK_ALL_CARDS"
    GENERATE_REPORT = "GENERATE_REPORT"
    CREATE_CASE = "CREATE_CASE"
    FILE_REPORT = "FILE_REPORT"
    ESCALATE_TO_ANALYST = "ESCALATE_TO_ANALYST"
    CLOSE_NO_FRAUD = "CLOSE_NO_FRAUD"


class ApprovalRoute(str, Enum):
    AUTO = "auto"
    L1 = "L1"
    L2 = "L2"


class ActionRecommendation(NamedTuple):
    action: Action
    route: ApprovalRoute
    reason: str

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "route": self.route.value,
            "reason": self.reason
        }


def get_statutory_approval_route(action: Action, exposure_usd: float = 0.0) -> ApprovalRoute:
    """
    Returns the statutory approval route for a given action under Fraud Policy Section 2.
    
    Routes:
    - auto: ALLOW_TRANSACTION, MONITOR_CARD, MONITOR_CONNECTED_CARDS, WARN_CUSTOMER,
            VERIFY_WITH_CUSTOMER, STEP_UP_AUTH, GENERATE_REPORT, CREATE_CASE,
            ESCALATE_TO_ANALYST, CLOSE_NO_FRAUD
    - L1:   DECLINE_TRANSACTION; BLOCK_CARD when exposure <= $2,500
    - L2:   BLOCK_CARD when exposure > $2,500; BLOCK_ALL_CARDS always; FILE_REPORT always
    """
    if action == Action.DECLINE_TRANSACTION:
        return ApprovalRoute.L1

    if action == Action.BLOCK_CARD:
        if exposure_usd > 2500.0:
            return ApprovalRoute.L2
        return ApprovalRoute.L1

    if action in (Action.BLOCK_ALL_CARDS, Action.FILE_REPORT):
        return ApprovalRoute.L2

    return ApprovalRoute.AUTO


def validate_action_route(action: Action, route: ApprovalRoute, exposure_usd: float = 0.0) -> bool:
    """
    Validates whether an assigned approval route matches statutory policy requirements.
    """
    expected = get_statutory_approval_route(action, exposure_usd)
    return route == expected
