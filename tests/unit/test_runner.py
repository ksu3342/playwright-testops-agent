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
    document = parse_prd("data/inputs/sample_prd_search.md")
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)

    result = run_test_script(str(script_path))

    assert result["status"] == "blocked"
    assert "TODO" in result["reason"]

    summary = _load_summary(result["artifact_paths"]["summary"])
    assert summary["status"] == "blocked"
    assert summary["execution_readiness"] == "blocked_by_incomplete_markers"


def test_runner_executes_generated_login_script_when_no_blockers_remain() -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)

    first_result = run_test_script(str(script_path))
    second_result = run_test_script(str(script_path))

    assert first_result["status"] == "passed"
    assert first_result["reason"] == "Execution completed successfully."
    assert second_result["status"] == "passed"
    assert second_result["reason"] == "Execution completed successfully."

    first_summary = _load_summary(first_result["artifact_paths"]["summary"])
    second_summary = _load_summary(second_result["artifact_paths"]["summary"])
    assert first_summary["status"] == "passed"
    assert first_summary["execution_readiness"] == "ready"
    assert second_summary["status"] == "passed"
    assert second_summary["execution_readiness"] == "ready"


def test_runner_prioritizes_selector_contract_missing_marker(tmp_path: Path) -> None:
    document = parse_prd("data/inputs/sample_prd_login.md")
    test_points = extract_test_points(document)
    contract_payload = json.loads(Path("data/contracts/demo_app_selectors.json").read_text(encoding="utf-8"))
    del contract_payload["selectors"]["login.email_input"]
    contract_path = tmp_path / "demo_app_selectors.json"
    contract_path.write_text(json.dumps(contract_payload, indent=2), encoding="utf-8")
    script_path = generate_test_script(document, test_points, selector_contract_path=contract_path)

    result = run_test_script(str(script_path))

    assert result["status"] == "blocked"
    assert "selector contract" in result["reason"].lower()
    assert "login.email_input" in result["reason"]

    summary = _load_summary(result["artifact_paths"]["summary"])
    assert summary["status"] == "blocked"
    assert summary["execution_readiness"] == "blocked_by_selector_contract"


def test_runner_reports_environment_error_for_missing_target_script() -> None:
    result = run_test_script("tests/assets/does_not_exist.py")

    assert result["status"] == "environment_error"
    assert result["reason"] == "Target script was not found."

    summary = _load_summary(result["artifact_paths"]["summary"])
    assert summary["status"] == "environment_error"
