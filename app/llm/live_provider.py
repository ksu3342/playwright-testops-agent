from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.llm.base import BaseLLMProvider, LLMProviderError, LLMResponse


SYSTEM_PROMPT = (
    "You normalize free-text requirement notes into parser-compatible PRD markdown. "
    "Return only markdown that follows the requested heading structure. "
    "Do not invent missing details."
)


@dataclass(frozen=True)
class LiveLLMProvider(BaseLLMProvider):
    endpoint_url: str
    model: str
    api_key: str
    timeout_seconds: int = 30

    @classmethod
    def from_settings(cls, settings: Settings) -> "LiveLLMProvider":
        missing_vars = [
            name
            for name, value in [
                ("LLM_LIVE_BASE_URL", settings.llm_live_base_url),
                ("LLM_LIVE_MODEL", settings.llm_live_model),
                ("LLM_LIVE_API_KEY", settings.llm_live_api_key),
            ]
            if not value
        ]
        if missing_vars:
            missing = ", ".join(missing_vars)
            raise LLMProviderError(
                f"Live provider configuration is missing required environment variable(s): {missing}. "
                "Set them explicitly before using '--provider live'."
            )

        return cls(
            endpoint_url=settings.llm_live_base_url,
            model=settings.llm_live_model,
            api_key=settings.llm_live_api_key,
        )

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMProviderError("Live provider returned no choices in the response payload.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LLMProviderError("Live provider returned an unexpected choice payload.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LLMProviderError("Live provider returned no message payload.")

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text)
            if parts:
                return "\n".join(parts)

        raise LLMProviderError("Live provider returned an unsupported message content format.")

    def generate(self, prompt: str) -> LLMResponse:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        request = Request(
            self.endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            message = detail or exc.reason
            raise LLMProviderError(f"Live provider request failed with HTTP {exc.code}: {message}") from exc
        except URLError as exc:
            raise LLMProviderError(f"Live provider request failed: {exc.reason}") from exc
        except OSError as exc:
            raise LLMProviderError(f"Live provider request failed: {exc}") from exc

        try:
            payload_json = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise LLMProviderError("Live provider returned invalid JSON.") from exc

        return LLMResponse(content=self._extract_content(payload_json))
