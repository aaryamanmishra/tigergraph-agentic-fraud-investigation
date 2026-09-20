"""
LLM Provider Abstraction Package for TigerGraph Fraud Investigation Agent.
"""

from src.agent.llm.base import BaseLLMProvider, LLMResponse, TokenUsage, redact_credentials
from src.agent.llm.schemas import (
    ToolCallProposal,
    StructuredFinding,
    EvidenceRequestProposal,
    LLMReasoningStep,
    LLMFinalSynthesis
)
from src.agent.llm.mock import MockLLMProvider
from src.agent.llm.openai_provider import OpenAIProvider
from src.agent.llm.gemini_provider import GeminiProvider
from src.agent.llm.factory import get_llm_provider

__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "TokenUsage",
    "redact_credentials",
    "ToolCallProposal",
    "StructuredFinding",
    "EvidenceRequestProposal",
    "LLMReasoningStep",
    "LLMFinalSynthesis",
    "MockLLMProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "get_llm_provider",
]
