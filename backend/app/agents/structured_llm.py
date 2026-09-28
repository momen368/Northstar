import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.app.core.config import settings


OutputModel = TypeVar("OutputModel", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class LLMConfigurationError(LLMError):
    pass


class LLMProviderError(LLMError):
    pass


class LLMTimeoutError(LLMProviderError):
    pass


class LLMInvalidResponseError(LLMError):
    pass


class StructuredLLM:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.base_url = settings.ai_base_url
        self.model = settings.ai_model
        self.api_key = settings.ai_api_key
        self.timeout = settings.ai_timeout_seconds
        self.transport = transport

    async def complete(self, system_prompt: str, user_prompt: str, output_schema: type[OutputModel]) -> OutputModel:
        if not self.base_url.strip() or not self.model.strip():
            raise LLMConfigurationError("AI provider is not configured.")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt + " Return only valid JSON matching the schema."},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(f"{self.base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("AI provider timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("AI provider request failed.") from exc
        try:
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Provider content was not text")
            return output_schema.model_validate(json.loads(content))
        except (ValueError, TypeError, KeyError, IndexError, ValidationError) as exc:
            raise LLMInvalidResponseError("AI provider returned invalid structured data.") from exc