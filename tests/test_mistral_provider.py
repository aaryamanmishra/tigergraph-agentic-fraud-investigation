"""
Unit and Integration Tests for Mistral OpenAI-Compatible LLM Provider.
Tests:
- Mistral provider initialization via factory and OpenAIProvider reuse
- MISTRAL_API_KEY missing validation error
- MISTRAL_MODEL environment variable and explicit model configuration
- Correct default and custom base URL verification
- Provider selection through factory (provider_type argument and LLM_PROVIDER env var)
- Credential scrubbing and zero leakage of MISTRAL_API_KEY
- Mocked generation and structured output parsing without live network calls
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
import urllib.error

from src.agent.llm.base import LLMResponse, TokenUsage
from src.agent.llm.openai_provider import OpenAIProvider
from src.agent.llm.factory import get_llm_provider
from src.agent.llm.schemas import LLMReasoningStep


class TestMistralProvider:
    """Unit tests for Mistral LLM integration."""

    def test_mistral_initialization_defaults(self):
        """Mistral provider must use OpenAIProvider with https://api.mistral.ai/v1 and mistral-small-latest."""
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "test-mistral-key-12345"}, clear=False):
            p = get_llm_provider(provider_type="mistral")
            assert isinstance(p, OpenAIProvider)
            assert p.provider == "mistral"
            assert p.provider_name == "mistral"
            assert p.is_real is True
            assert p.base_url == "https://api.mistral.ai/v1"
            assert p.model_name == "mistral-small-latest"
            # Ensure API key is not exposed in str representation
            assert "test-mistral-key-12345" not in str(p)

    def test_mistral_missing_api_key_raises_error(self):
        """Requesting mistral without MISTRAL_API_KEY must raise a clear ValueError."""
        env_without_mistral = {k: v for k, v in os.environ.items() if k != "MISTRAL_API_KEY"}
        with patch.dict(os.environ, env_without_mistral, clear=True):
            with pytest.raises(ValueError, match="MISTRAL_API_KEY is not configured"):
                get_llm_provider(provider_type="mistral")

    def test_mistral_model_env_configuration(self):
        """MISTRAL_MODEL env var must override the default model."""
        with patch.dict(os.environ, {
            "MISTRAL_API_KEY": "test-key-abc",
            "MISTRAL_MODEL": "mistral-large-latest"
        }, clear=False):
            p = get_llm_provider(provider_type="mistral")
            assert p.model_name == "mistral-large-latest"

    def test_mistral_explicit_model_and_base_url_override(self):
        """Explicit model_name and base_url arguments must take precedence."""
        p = get_llm_provider(
            provider_type="mistral",
            api_key="explicit-key-xyz",
            model_name="codestral-latest",
            base_url="https://custom.mistral.proxy/v1"
        )
        assert p.provider == "mistral"
        assert p.model_name == "codestral-latest"
        assert p.base_url == "https://custom.mistral.proxy/v1"

    def test_mistral_selection_via_llm_provider_env(self):
        """Setting LLM_PROVIDER=mistral in environment must automatically select Mistral."""
        with patch.dict(os.environ, {
            "LLM_PROVIDER": "mistral",
            "MISTRAL_API_KEY": "env-mistral-key"
        }, clear=False):
            p = get_llm_provider()
            assert isinstance(p, OpenAIProvider)
            assert p.provider == "mistral"
            assert p.provider_name == "mistral"

    def test_mistral_credential_scrubbing_on_api_error(self):
        """Errors and logs must never leak the MISTRAL_API_KEY."""
        p = get_llm_provider(
            provider_type="mistral",
            api_key="secret-mistral-key-99999"
        )
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"error": "Unauthorized key secret-mistral-key-99999"}'
            err = urllib.error.HTTPError(
                url="https://api.mistral.ai/v1/chat/completions",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=mock_resp
            )
            mock_urlopen.side_effect = err

            with pytest.raises(RuntimeError) as exc_info:
                p.generate([{"role": "user", "content": "Analyze case"}])

            err_str = str(exc_info.value)
            assert "secret-mistral-key-99999" not in err_str
            assert "[REDACTED" in err_str

    def test_mistral_mocked_generate_and_structured(self):
        """Mistral provider generate and generate_structured work with standard OpenAI format."""
        p = get_llm_provider(
            provider_type="mistral",
            api_key="test-key"
        )

        mock_payload = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "thought": "Observed rapid successive transactions on same device.",
                        "uncertainty": "low",
                        "tentative_verdict": "fraud",
                        "tentative_pattern": "shared_device_ring",
                        "observations": ["Observed out of region activity"]
                    })
                }
            }],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 45,
                "total_tokens": 165
            }
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            # 1. Test generate
            resp = p.generate([{"role": "user", "content": "Evaluate transaction"}])
            assert isinstance(resp, LLMResponse)
            assert "rapid successive transactions" in resp.content
            assert resp.token_usage.total_tokens == 165

            # 2. Test generate_structured
            step = p.generate_structured(
                messages=[{"role": "user", "content": "Evaluate transaction"}],
                response_model=LLMReasoningStep
            )
            assert isinstance(step, LLMReasoningStep)
            assert step.thought == "Observed rapid successive transactions on same device."
            assert step.uncertainty == "low"
            assert step.tentative_verdict == "fraud"
            assert step.tentative_pattern == "shared_device_ring"
