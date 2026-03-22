import subprocess
import sys

from app.core.parser import parse_prd


def test_pipeline_parse_flow_returns_structured_document() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    assert document.title == "Login Page PRD"
    assert document.feature_name == "User Login"
    assert len(document.user_actions) == 3


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
