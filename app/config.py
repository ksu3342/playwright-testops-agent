from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    playwright_browser: str = os.getenv("PLAYWRIGHT_BROWSER", "chromium")
    headless: bool = os.getenv("HEADLESS", "true").lower() == "true"
    base_url: str = os.getenv("BASE_URL", "https://example.com")
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")


def get_settings() -> Settings:
    return Settings()
