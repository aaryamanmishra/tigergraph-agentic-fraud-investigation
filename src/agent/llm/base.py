"""
Base LLM Provider Interface for TigerGraph Fraud Investigation Agent.
Provides vendor-independent abstraction with token tracking, structured output parsing,
credential redaction, and graceful fallback.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Type, TypeVar
import json
import re
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class TokenUsage:
    """Token consumption metrics for observability and cost tracking."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "TokenUsage"):
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens

    def to_dict(self) -> Dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    parsed: Optional[Any] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""
    raw_response: Optional[Any] = None
    latency_ms: float = 0.0


def redact_credentials(text: str) -> str:
    """
    Redacts API keys, bearer tokens, passwords, and sensitive credentials
    from prompt logs and error messages to prevent credential leakage.
    """
    if not isinstance(text, str):
        return text
    
    # Redact Bearer tokens
    text = re.sub(r'(Bearer\s+)[A-Za-z0-9_\-\.]{12,}', r'\1[REDACTED_SECRET]', text, flags=re.IGNORECASE)
    # Redact OpenAI / Anthropic / TigerGraph style keys
    text = re.sub(r'(sk-[A-Za-z0-9_\-]{16,})', r'[REDACTED_API_KEY]', text)
    text = re.sub(r'((?:password|secret|token|api_key)\s*[:=]\s*["\']?)[^"\'\s,;]+(["\']?)', r'\1[REDACTED_SECRET]\2', text, flags=re.IGNORECASE)
    return text


class BaseLLMProvider(ABC):
    """
    Vendor-independent abstract interface for LLM reasoning models.
    """

    def __init__(self, model_name: str = "mock-reasoner"):
        self.model_name = model_name

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Generates text completion from chat messages.
        """
        pass

    @abstractmethod
    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any
    ) -> T:
        """
        Generates structured output validated against a Pydantic model.
        """
        pass

    def repair_and_parse_json(self, content: str) -> Dict[str, Any]:
        """
        Robust JSON extractor that handles markdown code fences and common LLM syntax irregularities.
        """
        cleaned = content.strip()
        # Strip markdown ```json ... ``` code blocks
        if "```json" in cleaned:
            match = re.search(r'```json\s*(.*?)\s*```', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
        elif "```" in cleaned:
            match = re.search(r'```\s*(.*?)\s*```', cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt basic repair for trailing commas or single quotes
            repaired = re.sub(r',\s*([\]}])', r'\1', cleaned)
            return json.loads(repaired)
