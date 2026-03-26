from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from app.config import get_settings
from app.core.parser import parse_prd
from app.llm.base import BaseLLMProvider, LLMProviderError
from app.llm.live_provider import LiveLLMProvider
from app.llm.mock_provider import MockLLMProvider


MODULE_DIR = Path(__file__).resolve().parent
APP_DIR = MODULE_DIR.parent
REPO_ROOT = APP_DIR.parent
NORMALIZED_DIR = REPO_ROOT / "data" / "normalized"
REQUIRED_HEADINGS = [
    "# Title",
    "## Feature Name",
    "## Page URL",
    "## Preconditions",
    "## User Actions",
    "## Expected Results",
]


class NormalizationError(RuntimeError):
    """Raised when requirement normalization cannot complete honestly."""


@dataclass(frozen=True)
class NormalizationResult:
    input_path: str
    output_path: Path
    provider_name: str
    normalized_markdown: str
    parser_validation_passed: bool
    missing_sections: list[str]
    raw_text: str


def _resolve_input_path(input_path: str) -> Path:
    candidate = Path(input_path)
    if candidate.is_absolute():
        return candidate.resolve()

    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return candidate.resolve()


def _extract_markdown(response_text: str) -> str:
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _build_prompt(raw_text: str) -> str:
    return (
        "Normalize the following requirement notes into parser-compatible PRD markdown.\n"
        "Use this exact heading structure and nothing broader than the input supports:\n\n"
        "# Title\n"
        "...\n\n"
        "## Feature Name\n"
        "...\n\n"
        "## Page URL\n"
        "...\n\n"
        "## Preconditions\n"
        "- ...\n\n"
        "## User Actions\n"
        "1. ...\n\n"
        "## Expected Results\n"
        "- ...\n\n"
        "Rules:\n"
        "- Do not invent URLs, selectors, business rules, or edge cases.\n"
        "- If information is missing, leave the section empty.\n"
        "- Keep the output concise and deterministic.\n\n"
        "<<<RAW_REQUIREMENT_NOTES>>>\n"
        f"{raw_text.strip()}\n"
        "<<<END_RAW_REQUIREMENT_NOTES>>>"
    )


def _select_provider(provider_name: Optional[str], provider: Optional[BaseLLMProvider]) -> Tuple[BaseLLMProvider, str]:
    if provider is not None:
        name = provider_name or provider.__class__.__name__
        return provider, str(name)

    settings = get_settings()
    selected_name = (provider_name or settings.llm_provider or "mock").strip().lower()
    if selected_name == "mock":
        return MockLLMProvider(), "mock"
    if selected_name == "live":
        try:
            return LiveLLMProvider.from_settings(settings), "live"
        except LLMProviderError as exc:
            raise NormalizationError(str(exc)) from exc

    raise NormalizationError(f"Unsupported provider '{selected_name}'. Supported providers: mock, live.")


def normalize_requirement_file(
    input_path: str,
    provider_name: Optional[str] = None,
    provider: Optional[BaseLLMProvider] = None,
    output_dir: Optional[Path] = None,
) -> NormalizationResult:
    source_path = _resolve_input_path(input_path)
    if not source_path.exists():
        raise NormalizationError(f"Input requirement file was not found: {input_path}")

    raw_text = source_path.read_text(encoding="utf-8")
    if not raw_text.strip():
        raise NormalizationError("Input requirement file is empty.")

    llm_provider, resolved_provider_name = _select_provider(provider_name, provider)
    prompt = _build_prompt(raw_text)
    try:
        response = llm_provider.generate(prompt)
    except LLMProviderError as exc:
        raise NormalizationError(str(exc)) from exc
    normalized_markdown = _extract_markdown(response.content)

    destination_dir = (output_dir or NORMALIZED_DIR).resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    output_path = destination_dir / f"{source_path.stem}_normalized.md"
    normalized_text = normalized_markdown.rstrip() + "\n"
    output_path.write_text(normalized_text, encoding="utf-8")

    parser_validation_passed = all(heading in normalized_markdown for heading in REQUIRED_HEADINGS)
    missing_sections: list[str] = []
    if parser_validation_passed:
        document = parse_prd(str(output_path))
        missing_sections = document.missing_sections

    return NormalizationResult(
        input_path=source_path.as_posix(),
        output_path=output_path,
        provider_name=resolved_provider_name,
        normalized_markdown=normalized_text,
        parser_validation_passed=parser_validation_passed,
        missing_sections=missing_sections,
        raw_text=raw_text,
    )
