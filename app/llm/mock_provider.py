from app.llm.base import BaseLLMProvider, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Deterministic placeholder used for scaffold demos and tests."""

    def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(content=f"MOCK RESPONSE:\n{prompt[:120]}")
