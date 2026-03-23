import json
from pathlib import Path

from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.parser import parse_prd
from app.core.runner import run_test_script


def _load_summary(summary_path: str) -> dict[str, object]:
    return json.loads(Path(summary_path).read_text(encoding="utf-8"))


def test_runner_records_passed_run_artifacts() -> None:
    result = run_test_script("tests/assets/runner_pass_case.py")

    assert result["status"] == "passed"
    assert Path(result["artifact_paths"]["run_dir"]).exists()
    assert Path(result["artifact_paths"]["command"]).exists()
    assert Path(result["artifact_paths"]["stdout"]).exists()
    assert Path(result["artifact_paths"]["stderr"]).exists()
    assert Path(result["artifact_paths"]["summary"]).exists()

    summary = _load_summary(result["artifact_paths"]["summary"])
    assert summary["status"] == "passed"
    assert summary["execution_readiness"] == "ready"


def test_runner_records_failed_run_artifacts() -> None:
    result = run_test_script("tests/assets/runner_fail_case.py")

    assert result["status"] == "failed"
    assert result["return_code"] != 0

    summary = _load_summary(result["artifact_paths"]["summary"])
    assert summary["status"] == "failed"
    assert Path(result["artifact_paths"]["stdout"]).exists()
    assert Path(result["artifact_paths"]["stderr"]).exists()


def test_runner_marks_generated_scaffold_as_blocked() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)

    result = run_test_script(str(script_path))

    assert result["status"] == "blocked"
    assert "TODO" in result["reason"]

    summary = _load_summary(result["artifact_paths"]["summary"])
    assert summary["status"] == "blocked"
    assert summary["execution_readiness"] == "blocked_by_incomplete_markers"


def test_runner_reports_environment_error_for_missing_target_script() -> None:
    result = run_test_script("tests/assets/does_not_exist.py")

    assert result["status"] == "environment_error"
    assert result["reason"] == "Target script was not found."

    summary = _load_summary(result["artifact_paths"]["summary"])
    assert summary["status"] == "environment_error"
