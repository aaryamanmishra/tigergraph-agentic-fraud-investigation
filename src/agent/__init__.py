"""
Agent module for TigerGraph Fraud Investigation.
Provides strongly-typed state management, tool contracts, analytical summarization,
and modular investigation workflow nodes.
"""

from src.agent.state import (
    InvestigationState,
    EvidenceCategory,
    EvidenceItem,
    TimelineEvent,
    CaseStatus,
    StopReason
)
from src.agent.tools.contracts import (
    InvestigationTools,
    ToolExecutionResult
)
from src.agent.tools.summary import EvidenceSummarizer
from src.agent.nodes import InvestigationNodes
from src.agent.workflow import InvestigationWorkflow

__all__ = [
    "InvestigationState",
    "EvidenceCategory",
    "EvidenceItem",
    "TimelineEvent",
    "CaseStatus",
    "StopReason",
    "InvestigationTools",
    "ToolExecutionResult",
    "EvidenceSummarizer",
    "InvestigationNodes",
    "InvestigationWorkflow"
]
