"""
LLM Provider Factory for TigerGraph Fraud Investigation Agent.
Safely selects and initializes the configured provider (gemini vs openai vs mock).
Defaults to MockLLMProvider when credentials are unset to prevent test breakages.
"""

import os
from typing import Optional
import logging

from src.agent.llm.base import BaseLLMProvider
from src.agent.llm.mock import MockLLMProvider
from src.agent.llm.openai_provider import OpenAIProvider
from src.agent.llm.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


def get_llm_provider(
    provider_type: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> BaseLLMProvider:
    """
    Returns an initialized BaseLLMProvider instance.
    - If provider_type == 'gemini' or LLM_PROVIDER == 'gemini': returns GeminiProvider.
    - If provider_type == 'openai' or LLM_PROVIDER == 'openai': returns OpenAIProvider.
    - If provider_type == 'mock' or LLM_PROVIDER == 'mock': returns MockLLMProvider.
    - If GEMINI_API_KEY is present and provider_type not specified: returns GeminiProvider.
    - Otherwise safely falls back to MockLLMProvider.
    """
    chosen_type = (provider_type or os.environ.get("LLM_PROVIDER", "")).lower().strip()
    gemini_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    openai_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    if chosen_type == "gemini":
        if gemini_key:
            return GeminiProvider(
                api_key=gemini_key,
                model_name=model_name
            )
        else:
            raise ValueError("GEMINI_API_KEY is not configured in environment but provider 'gemini' was requested.")

    if chosen_type == "openai":
        if openai_key:
            return OpenAIProvider(
                api_key=openai_key,
                base_url=base_url,
                model_name=model_name
            )
        else:
            raise ValueError("OPENAI_API_KEY is not configured in environment but provider 'openai' was requested.")

    if chosen_type == "mock":
        return MockLLMProvider(model_name=model_name or "mock-reasoner-v1")

    # If no provider explicitly chosen, check available keys
    if gemini_key:
        return GeminiProvider(
            api_key=gemini_key,
            model_name=model_name
        )
    elif openai_key:
        return OpenAIProvider(
            api_key=openai_key,
            base_url=base_url,
            model_name=model_name
        )

    # Default to Mock
    return MockLLMProvider(model_name=model_name or "mock-reasoner-v1")
