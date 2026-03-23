import subprocess
import sys

from app.core.extractor import extract_test_points
from app.core.parser import parse_prd


def test_pipeline_parse_flow_returns_structured_document() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    assert document.title == "Login Page PRD"
    assert document.feature_name == "User Login"
    assert len(document.user_actions) == 3


def test_pipeline_extract_flow_returns_expected_search_test_points() -> None:
    document = parse_prd("data/inputs/sample_prd_search.md")
    test_points = extract_test_points(document)
    assert any(point.type == "happy_path" for point in test_points)
    assert any(point.type == "negative_path" and "empty state" in point.expected_result.lower() for point in test_points)


def test_pipeline_extract_flow_does_not_force_unsupported_login_negative_path() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    assert any(point.type == "happy_path" for point in test_points)
    assert not any(point.type == "negative_path" for point in test_points)


def test_cli_parse_command_prints_structured_output() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "parse", "--input", "data/inputs/sample_prd_search.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"title": "Search Page PRD"' in result.stdout
    assert '"feature_name": "Keyword Search"' in result.stdout


def test_cli_parse_command_supports_positional_input() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "parse", "data/inputs/sample_prd_login.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"title": "Login Page PRD"' in result.stdout
    assert '"feature_name": "User Login"' in result.stdout


def test_cli_generate_command_prints_extracted_test_points() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "generate", "--input", "data/inputs/sample_prd_search.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"type": "happy_path"' in result.stdout
    assert '"type": "negative_path"' in result.stdout
