from pathlib import Path

import pytest

from app.core.extractor import extract_test_points
from app.core.normalizer import NormalizationError, normalize_requirement_file
from app.core.parser import parse_prd
from app.llm.base import BaseLLMProvider, LLMResponse


class StaticProvider(BaseLLMProvider):
    def __init__(self, content: str) -> None:
        self.content = content

    def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(content=self.content)


def test_normalizer_converts_login_notes_into_parser_compatible_markdown(tmp_path: Path) -> None:
    result = normalize_requirement_file("data/inputs/free_text_login_notes.md", output_dir=tmp_path)

    assert result.provider_name == "mock"
    assert result.parser_validation_passed is True
    assert result.output_path.name == "free_text_login_notes_normalized.md"
    assert "# Title" in result.normalized_markdown
    assert "## Feature Name" in result.normalized_markdown
    assert "## Page URL" in result.normalized_markdown
    assert "## Preconditions" in result.normalized_markdown
    assert "## User Actions" in result.normalized_markdown
    assert "## Expected Results" in result.normalized_markdown

    document = parse_prd(str(result.output_path))
    assert document.page_url == "/login"
    assert document.user_actions[0] == "enter a valid email address"
    assert any(
        item.lower() == "no blocking validation error is shown for valid credentials"
        for item in document.expected_results
    )


def test_normalizer_handles_missing_information_honestly(tmp_path: Path) -> None:
    notes_path = tmp_path / "free_text_missing_notes.md"
    notes_path.write_text(
        "Simple profile update note. Existing users can change profile information. Main flow: open profile settings, save changes.",
        encoding="utf-8",
    )

    result = normalize_requirement_file(str(notes_path), output_dir=tmp_path)
    document = parse_prd(str(result.output_path))

    assert document.page_url is None
    assert "Page URL" in document.missing_sections
    assert "Expected Results" in document.missing_sections


def test_normalizer_output_can_continue_into_extraction(tmp_path: Path) -> None:
    result = normalize_requirement_file("data/inputs/free_text_search_notes.md", output_dir=tmp_path)
    document = parse_prd(str(result.output_path))
    test_points = extract_test_points(document)

    assert any(point.type == "happy_path" for point in test_points)
    assert any(point.type == "negative_path" for point in test_points)


def test_normalizer_supports_explicit_mock_provider_selection(tmp_path: Path) -> None:
    result = normalize_requirement_file(
        "data/inputs/free_text_login_notes.md",
        provider_name="mock",
        output_dir=tmp_path,
    )

    assert result.provider_name == "mock"
    assert result.parser_validation_passed is True


def test_normalizer_fails_cleanly_for_missing_live_provider_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_LIVE_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_LIVE_MODEL", raising=False)
    monkeypatch.delenv("LLM_LIVE_API_KEY", raising=False)

    with pytest.raises(NormalizationError, match="LLM_LIVE_BASE_URL, LLM_LIVE_MODEL, LLM_LIVE_API_KEY"):
        normalize_requirement_file(
            "data/inputs/free_text_login_notes.md",
            provider_name="live",
            output_dir=tmp_path,
        )


def test_normalizer_reads_provider_selection_from_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "live")
    monkeypatch.delenv("LLM_LIVE_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_LIVE_MODEL", raising=False)
    monkeypatch.delenv("LLM_LIVE_API_KEY", raising=False)

    with pytest.raises(NormalizationError, match="Set them explicitly before using '--provider live'"):
        normalize_requirement_file(
            "data/inputs/free_text_login_notes.md",
            output_dir=tmp_path,
        )


def test_live_output_repair_normalizes_first_h1_and_removes_placeholder_lines(tmp_path: Path) -> None:
    live_like_output = (
        "# Login Page Flow for Existing Users\n"
        "\n"
        "## Feature Name\n"
        "Login flow for existing users\n"
        "\n"
        "## Page URL\n"
        "/login\n"
        "...\n"
        "\n"
        "## Preconditions\n"
        "- The user already has an account\n"
        "- The user can reach the /login page\n"
        "- ...\n"
        "\n"
        "## User Actions\n"
        "1. Enter a valid email address\n"
        "2. Enter the correct password\n"
        "3. Click the login button\n"
        "...\n"
        "\n"
        "## Expected Results\n"
        "- The login request is submitted successfully\n"
        "- The user is redirected to the dashboard\n"
        "- No blocking validation error is shown for valid credentials\n"
    )

    result = normalize_requirement_file(
        "data/inputs/free_text_login_notes.md",
        provider_name="live",
        provider=StaticProvider(live_like_output),
        output_dir=tmp_path,
    )

    document = parse_prd(str(result.output_path))
    assert result.provider_name == "live"
    assert result.parser_validation_passed is True
    assert document.title == "Login Page Flow for Existing Users"
    assert result.normalized_markdown.startswith("# Title\nLogin Page Flow for Existing Users\n")
    assert "...\n" not in result.normalized_markdown


def test_live_output_repair_fails_honestly_when_required_structure_is_still_missing(tmp_path: Path) -> None:
    malformed_live_output = (
        "# Login Page Flow for Existing Users\n"
        "\n"
        "## Page URL\n"
        "/login\n"
        "\n"
        "## Preconditions\n"
        "- The user already has an account\n"
    )

    with pytest.raises(NormalizationError, match="still not parser-compatible"):
        normalize_requirement_file(
            "data/inputs/free_text_login_notes.md",
            provider_name="live",
            provider=StaticProvider(malformed_live_output),
            output_dir=tmp_path,
        )


def test_live_output_repair_fails_when_title_body_is_missing_even_if_heading_exists(tmp_path: Path) -> None:
    malformed_live_output = (
        "# Title\n"
        "## Feature Name\n"
        "Login Flow\n"
        "## Page URL\n"
        "/login\n"
        "## Preconditions\n"
        "- The user already has an account.\n"
        "- The user can reach the login page.\n"
        "## User Actions\n"
        "1. Enter a valid email address.\n"
        "2. Enter the correct password.\n"
        "3. Click the login button.\n"
        "## Expected Results\n"
        "- Login request is submitted successfully.\n"
        "- The user is redirected to the dashboard.\n"
        "- No blocking validation error is shown for valid credentials.\n"
    )

    with pytest.raises(NormalizationError, match="invalid for downstream use"):
        normalize_requirement_file(
            "data/inputs/free_text_login_notes.md",
            provider_name="live",
            provider=StaticProvider(malformed_live_output),
            output_dir=tmp_path,
        )


def test_live_output_repair_fails_when_feature_name_body_is_missing(tmp_path: Path) -> None:
    malformed_live_output = (
        "# Title\n"
        "Login Flow\n"
        "## Feature Name\n"
        "## Page URL\n"
        "/login\n"
        "## Preconditions\n"
        "- The user already has an account.\n"
        "- The user can reach the login page.\n"
        "## User Actions\n"
        "1. Enter a valid email address.\n"
        "2. Enter the correct password.\n"
        "3. Click the login button.\n"
        "## Expected Results\n"
        "- Login request is submitted successfully.\n"
        "- The user is redirected to the dashboard.\n"
        "- No blocking validation error is shown for valid credentials.\n"
    )

    with pytest.raises(NormalizationError, match="invalid for downstream use"):
        normalize_requirement_file(
            "data/inputs/free_text_login_notes.md",
            provider_name="live",
            provider=StaticProvider(malformed_live_output),
            output_dir=tmp_path,
        )
