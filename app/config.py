import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    playwright_browser: str
    headless: bool
    base_url: str
    llm_provider: str
    llm_live_base_url: str
    llm_live_model: str
    llm_live_api_key: str


def get_settings() -> Settings:
    return Settings(
        playwright_browser=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
        headless=os.getenv("HEADLESS", "true").lower() == "true",
        base_url=os.getenv("BASE_URL", "https://example.com"),
        llm_provider=os.getenv("LLM_PROVIDER", "mock"),
        llm_live_base_url=os.getenv("LLM_LIVE_BASE_URL", "").strip(),
        llm_live_model=os.getenv("LLM_LIVE_MODEL", "").strip(),
        llm_live_api_key=os.getenv("LLM_LIVE_API_KEY", "").strip(),
    )
