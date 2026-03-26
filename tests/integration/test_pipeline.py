import os
import subprocess
import sys
from pathlib import Path

from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.normalizer import normalize_requirement_file
from app.core.parser import parse_prd
from app.core.runner import run_test_script


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


def test_cli_normalize_command_generates_parser_compatible_markdown() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "normalize", "--input", "data/inputs/free_text_login_notes.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "normalized_output: data/normalized/free_text_login_notes_normalized.md" in result.stdout
    assert "provider_used: mock" in result.stdout
    assert "parser_validation_passed: yes" in result.stdout
    assert Path("data/normalized/free_text_login_notes_normalized.md").exists()


def test_cli_normalize_command_supports_positional_input() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "normalize", "data/inputs/free_text_search_notes.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "normalized_output: data/normalized/free_text_search_notes_normalized.md" in result.stdout
    assert "provider_used: mock" in result.stdout


def test_cli_normalize_command_supports_explicit_mock_provider_selection() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.main",
            "normalize",
            "--input",
            "data/inputs/free_text_login_notes.md",
            "--provider",
            "mock",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "normalized_output: data/normalized/free_text_login_notes_normalized.md" in result.stdout
    assert "provider_used: mock" in result.stdout
    assert "parser_validation_passed: yes" in result.stdout


def test_cli_normalize_command_fails_clearly_when_live_config_is_missing() -> None:
    env = dict(os.environ)
    env.pop("LLM_LIVE_BASE_URL", None)
    env.pop("LLM_LIVE_MODEL", None)
    env.pop("LLM_LIVE_API_KEY", None)
    env["LLM_PROVIDER"] = "mock"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.main",
            "normalize",
            "--input",
            "data/inputs/free_text_login_notes.md",
            "--provider",
            "live",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0
    assert "Live provider configuration is missing required environment variable(s)" in result.stderr
    assert "LLM_LIVE_BASE_URL, LLM_LIVE_MODEL, LLM_LIVE_API_KEY" in result.stderr


def test_pipeline_normalize_then_parse_flow_returns_structured_document(tmp_path: Path) -> None:
    result = normalize_requirement_file("data/inputs/free_text_search_notes.md", output_dir=tmp_path)
    assert result.parser_validation_passed is True

    document = parse_prd(str(result.output_path))
    assert document.feature_name == "Keyword Search"
    assert document.page_url == "/search"
    assert any("empty state" in item.lower() for item in document.expected_results)


def test_cli_generate_command_prints_summary_and_generated_path() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "generate", "--input", "data/inputs/sample_prd_search.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Extracted 2 test point(s):" in result.stdout
    assert "TP-001 [happy_path]" in result.stdout
    assert "TP-002 [negative_path]" in result.stdout
    assert "generated/tests/test_search_generated.py" in result.stdout


def test_cli_generate_command_supports_positional_input() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "generate", "data/inputs/sample_prd_login.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Extracted 1 test point(s):" in result.stdout
    assert "generated/tests/test_login_generated.py" in result.stdout
    assert Path("generated/tests/test_login_generated.py").exists()


def test_cli_run_command_reports_passed_status_for_local_asset() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.main", "run", "tests/assets/runner_pass_case.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Run status: passed" in result.stdout
    assert "Run directory: data/runs/" in result.stdout


def test_cli_run_command_reports_blocked_status_for_generated_scaffold() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)

    result = subprocess.run(
        [sys.executable, "-m", "app.main", "run", str(script_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Run status: blocked" in result.stdout
    assert "Reason:" in result.stdout


def test_cli_report_command_generates_report_for_failed_run() -> None:
    run_result = run_test_script("tests/assets/runner_fail_case.py")

    result = subprocess.run(
        [sys.executable, "-m", "app.main", "report", run_result["artifact_paths"]["run_dir"]],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Run status: failed" in result.stdout
    assert "Report generated: yes" in result.stdout
    assert f"generated/reports/bug_report_{run_result['run_id']}.md" in result.stdout


def test_cli_report_command_skips_blocked_run() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)
    run_result = run_test_script(str(script_path))

    result = subprocess.run(
        [sys.executable, "-m", "app.main", "report", run_result["artifact_paths"]["run_dir"]],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Run status: blocked" in result.stdout
    assert "Report generated: no" in result.stdout
    assert "execution was not actually ready" in result.stdout.lower()


def test_cli_report_command_skips_passed_run() -> None:
    run_result = run_test_script("tests/assets/runner_pass_case.py")

    result = subprocess.run(
        [sys.executable, "-m", "app.main", "report", run_result["artifact_paths"]["run_dir"]],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Run status: passed" in result.stdout
    assert "Report generated: no" in result.stdout
