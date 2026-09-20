"""
Google Gemini LLM Provider for TigerGraph Fraud Investigation Agent.
Connects to Google's Generative Language REST API without external heavyweight dependencies.
Enforces credential scrubbing, robust JSON repair, token accounting, and strict schema validation.
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


class GeminiProvider(BaseLLMProvider):
    """
    Direct REST provider for Google Gemini models (e.g. gemini-3.6-flash, gemini-2.5-pro).
    Uses standard library urllib with zero third-party dependencies.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: int = 45
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        # Strip any prefix like "models/"
        clean_model = model.replace("models/", "")
        super().__init__(model_name=clean_model)
        self.timeout_seconds = timeout_seconds
        self.provider_name = "Gemini"
        self.is_real = True

    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes HTTP POST request against Gemini API with strict credential scrubbing."""
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured in environment.")

        data = json.dumps(payload).encode("utf-8")
        models_to_try = [self.model_name]
        if self.model_name != "gemini-flash-latest":
            models_to_try.append("gemini-flash-latest")

        last_error = None
        for attempt_model in models_to_try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{attempt_model}:generateContent?key={self.api_key}"
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                        body = resp.read().decode("utf-8")
                        return json.loads(body)
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8") if e.fp else ""
                    last_error = redact_credentials(f"Gemini HTTP {e.code}: {e.reason} - {err_body}")
                    if e.code == 503 and attempt < 2:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    break
                except Exception as e:
                    last_error = redact_credentials(str(e))
                    time.sleep(1.0)

        logger.error(f"Gemini API Error: {last_error}")
        raise RuntimeError(f"Gemini API call failed: {last_error}") from None

    def _format_messages_for_gemini(
        self,
        messages: List[Dict[str, str]]
    ) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Converts standard chat messages to Gemini's systemInstruction and contents structure."""
        system_instructions = []
        contents = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_instructions.append(content)
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        system_instruction_obj = None
        if system_instructions:
            system_instruction_obj = {
                "parts": [{"text": "\n\n".join(system_instructions)}]
            }

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Proceed with investigation."}]}]

        return system_instruction_obj, contents

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        **kwargs: Any
    ) -> LLMResponse:
        t0 = time.time()
        system_instruction, contents = self._format_messages_for_gemini(messages)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        res_json = self._call_api(payload)
        lat = round((time.time() - t0) * 1000, 2)

        candidates = res_json.get("candidates", [])
        content = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                content = parts[0].get("text", "")

        usage = res_json.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

        return LLMResponse(
            content=content,
            token_usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
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
        Generates structured output conforming to a Pydantic schema using Gemini's JSON mode.
        """
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        schema_prompt = (
            f"You are an autonomous fraud investigation reasoning engine. "
            f"You MUST output STRICT VALID JSON matching this schema:\n{schema_json}\n"
            f"Do not include any conversational preamble, markdown fences (```json), or extra text."
        )

        # Prepend schema instructions
        augmented_messages = [{"role": "system", "content": schema_prompt}] + list(messages)
        system_instruction, contents = self._format_messages_for_gemini(augmented_messages)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "response_mime_type": "application/json"
            }
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        t0 = time.time()
        res_json = self._call_api(payload)
        lat = round((time.time() - t0) * 1000, 2)

        candidates = res_json.get("candidates", [])
        raw_text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                raw_text = parts[0].get("text", "")

        # Parse & Validate
        try:
            parsed_dict = self.repair_and_parse_json(raw_text)
            return response_model.model_validate(parsed_dict)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"First-attempt JSON parse failed on Gemini output: {e}. Retrying with repair prompt...")
            # Retry with error feedback
            repair_messages = list(augmented_messages) + [
                {"role": "assistant", "content": raw_text},
                {"role": "user", "content": f"The previous JSON failed validation with error: {e}. Please return corrected strict JSON only."}
            ]
            _, repair_contents = self._format_messages_for_gemini(repair_messages)
            payload["contents"] = repair_contents
            repair_json = self._call_api(payload)
            repair_text = repair_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            parsed_dict = self.repair_and_parse_json(repair_text)
            return response_model.model_validate(parsed_dict)
