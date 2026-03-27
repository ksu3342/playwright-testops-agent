from __future__ import annotations

import re
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
REQUIRED_HEADING_PATTERNS = [re.compile(rf"^{re.escape(heading)}\s*$", re.MULTILINE) for heading in REQUIRED_HEADINGS]
PLACEHOLDER_LINE_PATTERN = re.compile(r"^(?:[-*]|\d+[.)])?\s*\.\.\.\s*$")
REQUIRED_SCALAR_SECTIONS = {"Title", "Feature Name"}


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


def _is_placeholder_line(line: str) -> bool:
    return bool(PLACEHOLDER_LINE_PATTERN.match(line.strip()))


def _repair_live_markdown_structure(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    first_nonempty_index = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first_nonempty_index is not None:
        first_line = lines[first_nonempty_index].strip()
        if first_line.startswith("#") and not first_line.startswith("##"):
            heading_text = re.sub(r"^#+\s*", "", first_line).strip()
            if heading_text and heading_text != "Title":
                lines[first_nonempty_index] = "# Title"
                next_nonempty = next(
                    (line.strip() for line in lines[first_nonempty_index + 1 :] if line.strip()),
                    "",
                )
                if next_nonempty != heading_text:
                    lines.insert(first_nonempty_index + 1, heading_text)

    repaired_lines = [line.rstrip() for line in lines if not _is_placeholder_line(line)]
    repaired_text = "\n".join(repaired_lines).strip()
    return repaired_text + "\n" if repaired_text else ""


def _first_nonempty_line(text: str) -> Optional[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _has_exact_required_headings(text: str) -> bool:
    return all(pattern.search(text) for pattern in REQUIRED_HEADING_PATTERNS)


def _build_prompt(raw_text: str) -> str:
    return (
        "Normalize the following requirement notes into parser-compatible PRD markdown.\n"
        "Output only markdown and keep the downstream contract exact.\n\n"
        "Required exact headings, in this exact order:\n"
        "# Title\n"
        "## Feature Name\n"
        "## Page URL\n"
        "## Preconditions\n"
        "## User Actions\n"
        "## Expected Results\n\n"
        "Formatting rules:\n"
        "- The first non-empty line must be exactly '# Title'.\n"
        "- Do not rename any heading.\n"
        "- Put scalar values on the line after the heading.\n"
        "- '# Title' must have a non-empty body line directly under it.\n"
        "- '## Feature Name' must have a non-empty body line directly under it.\n"
        "- Use '-' list items for Preconditions and Expected Results.\n"
        "- Use numbered list items for User Actions.\n"
        "- If information is missing, leave that section body blank.\n"
        "- Do not output code fences, commentary, placeholder filler, or '...'.\n"
        "- Do not invent URLs, selectors, business rules, or edge cases.\n"
        "- Do not add any headings beyond the six required headings.\n\n"
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
    repaired_markdown = _repair_live_markdown_structure(normalized_markdown) if resolved_provider_name == "live" else normalized_markdown

    destination_dir = (output_dir or NORMALIZED_DIR).resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    output_path = destination_dir / f"{source_path.stem}_normalized.md"
    normalized_text = repaired_markdown.rstrip() + "\n"
    output_path.write_text(normalized_text, encoding="utf-8")

    document = parse_prd(str(output_path))
    required_scalar_sections_present = not any(section in document.missing_sections for section in REQUIRED_SCALAR_SECTIONS)
    parser_validation_passed = (
        _first_nonempty_line(normalized_text) == "# Title"
        and _has_exact_required_headings(normalized_text)
        and not any(_is_placeholder_line(line) for line in normalized_text.splitlines())
        and document.title is not None
        and document.feature_name is not None
        and required_scalar_sections_present
    )
    missing_sections = document.missing_sections

    if resolved_provider_name == "live" and not parser_validation_passed:
        raise NormalizationError(
            f"Live provider output is still not parser-compatible after thin repair and is invalid for downstream use. "
            f"Saved output to: {output_path.as_posix()}"
        )

    return NormalizationResult(
        input_path=source_path.as_posix(),
        output_path=output_path,
        provider_name=resolved_provider_name,
        normalized_markdown=normalized_text,
        parser_validation_passed=parser_validation_passed,
        missing_sections=missing_sections,
        raw_text=raw_text,
    )
