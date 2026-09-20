"""
LLM Provider Factory for TigerGraph Fraud Investigation Agent.
Safely selects and initializes the configured provider (mock vs live OpenAI-compatible).
Defaults to MockLLMProvider when credentials are unset to prevent test breakages.
"""

import os
from typing import Optional
import logging

from src.agent.llm.base import BaseLLMProvider
from src.agent.llm.mock import MockLLMProvider
from src.agent.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


def get_llm_provider(
    provider_type: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> BaseLLMProvider:
    """
    Returns an initialized BaseLLMProvider instance.
    - If provider_type == 'mock' or LLM_PROVIDER == 'mock', returns MockLLMProvider.
    - If OPENAI_API_KEY is present and provider_type != 'mock', returns OpenAIProvider.
    - Otherwise safely falls back to MockLLMProvider.
    """
    chosen_type = provider_type or os.environ.get("LLM_PROVIDER", "").lower()
    openai_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    if chosen_type == "openai" or (not chosen_type and openai_key):
        if openai_key:
            return OpenAIProvider(
                api_key=openai_key,
                base_url=base_url,
                model_name=model_name
            )
        else:
            logger.warning("OPENAI_API_KEY is not set. Falling back to MockLLMProvider.")
            return MockLLMProvider(model_name=model_name or "mock-reasoner-v1")

    # Default to Mock
    return MockLLMProvider(model_name=model_name or "mock-reasoner-v1")
