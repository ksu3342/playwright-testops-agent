from pathlib import Path

import pytest

from app.core.extractor import extract_test_points
from app.core.normalizer import NormalizationError, normalize_requirement_file
from app.core.parser import parse_prd


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
