"""
OpenAI-Compatible LLM Provider for TigerGraph Fraud Investigation Agent.
Supports OpenAI, DeepSeek, Gemini (via OpenAI compatibility), and local Ollama/vLLM endpoints.
Enforces credential scrubbing, retry resilience, token accounting, and robust JSON repair.
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Type, TypeVar
import urllib.request
import urllib.error

from pydantic import BaseModel, ValidationError

from src.agent.llm.base import BaseLLMProvider, LLMResponse, TokenUsage, redact_credentials

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI-compatible HTTP provider using standard library urllib to minimize external runtime dependencies.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: int = 45,
        provider_name: str = "openai"
    ):
        self.provider_name = provider_name
        self.provider = provider_name
        self.is_real = True
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        model = model_name or os.environ.get("OPENAI_MODEL", "gpt-4o")
        super().__init__(model_name=model)
        self.timeout_seconds = timeout_seconds

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes HTTP POST request with bearer authentication and credential scrubbing."""
        if not self.api_key:
            env_var = "OPENAI_API_KEY" if self.provider_name == "openai" else f"{self.provider_name.upper()}_API_KEY"
            raise ValueError(f"{env_var} is not configured in environment.")

        endpoint = f"{self.base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
		"User-Agent": "tigergraph-fraud-investigation-agent/1.0",
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            clean_err = redact_credentials(f"HTTP {e.code}: {e.reason} - {err_body}")
            if self.api_key and len(self.api_key) > 4:
                clean_err = clean_err.replace(self.api_key, "[REDACTED_API_KEY]")
            logger.error(f"LLM API Error: {clean_err}")
            raise RuntimeError(f"LLM API call failed: {clean_err}") from None
        except Exception as e:
            clean_err = redact_credentials(str(e))
            if self.api_key and len(self.api_key) > 4:
                clean_err = clean_err.replace(self.api_key, "[REDACTED_API_KEY]")
            logger.error(f"LLM Connection Error: {clean_err}")
            raise RuntimeError(f"LLM connection error: {clean_err}") from None

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any
    ) -> LLMResponse:
        t0 = time.time()
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        res_json = self._call_api(payload)
        lat = round((time.time() - t0) * 1000, 2)

        choices = res_json.get("choices", [])
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        usage_data = res_json.get("usage", {})

        return LLMResponse(
            content=content,
            token_usage=TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            ),
            model=self.model_name,
            raw_response=res_json,
            latency_ms=lat
        )

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any
    ) -> T:
        """
        Requests structured output matching the JSON schema of response_model.
        """
        schema_def = response_model.model_json_schema()
        system_injection = {
            "role": "system",
            "content": f"You are a fraud investigation reasoning engine. You must output STRICT VALID JSON conforming to this schema:\n{json.dumps(schema_def, indent=2)}\nDo not include any conversational preamble or markdown code fences."
        }
        augmented_messages = [system_injection] + list(messages)

        resp = self.generate(
            messages=augmented_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **kwargs
        )

        try:
            parsed_dict = self.repair_and_parse_json(resp.content)
            return response_model.model_validate(parsed_dict)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Failed to parse structured output on first attempt: {e}. Retrying with repair prompt...")
            # Retry once with explicit correction prompt
            repair_messages = list(augmented_messages) + [
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": f"The output failed validation with error: {e}. Please fix the JSON output to strictly match the schema."}
            ]
            repair_resp = self.generate(messages=repair_messages, temperature=0.0, response_format={"type": "json_object"})
            parsed_dict = self.repair_and_parse_json(repair_resp.content)
            return response_model.model_validate(parsed_dict)
