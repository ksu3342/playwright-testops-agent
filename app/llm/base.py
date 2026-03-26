from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot complete a request honestly."""


class BaseLLMProvider:
    """Small interface for future LLM-backed steps."""

    def generate(self, prompt: str) -> LLMResponse:
        raise NotImplementedError


# TODO: Add a real provider only when prompt-based generation becomes necessary.
