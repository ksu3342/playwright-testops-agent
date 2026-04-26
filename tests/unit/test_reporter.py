from pathlib import Path

from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.parser import parse_prd
from app.core.reporter import create_bug_report_from_run
from app.core.runner import run_test_script


def test_reporter_generates_markdown_for_failed_run() -> None:
    run_result = run_test_script("tests/assets/playwright_login_failure_case.py")

    report_result = create_bug_report_from_run(run_result["artifact_paths"]["run_dir"])

    assert report_result["generated"] is True
    assert report_result["status"] == "failed"

    report_path = Path(report_result["report_path"])
    assert report_path.exists()

    content = report_path.read_text(encoding="utf-8")
    assert run_result["run_id"] in content
    assert "## Execution Status" in content
    assert "tests/assets/playwright_login_failure_case.py" in content
    assert "## Evidence" in content
    assert "## Probable Cause Hypothesis" in content
    assert "Hypothesis:" in content
    assert "not a confirmed root cause" in content.lower()
    assert "root cause is confirmed" not in content.lower()
    assert "Screenshot artifact:" in content
    assert run_result["artifact_paths"]["screenshot"] in content


def test_reporter_does_not_generate_product_bug_report_for_blocked_run() -> None:
    document = parse_prd("data/inputs/sample_prd_search.md")
    test_points = extract_test_points(document)
    script_path = generate_test_script(document, test_points)
    run_result = run_test_script(str(script_path))

    report_result = create_bug_report_from_run(run_result["artifact_paths"]["run_dir"])

    assert report_result["generated"] is False
    assert report_result["status"] == "blocked"
    assert "execution was not actually ready" in report_result["reason"].lower()


def test_reporter_does_not_generate_product_bug_report_for_passed_run() -> None:
    run_result = run_test_script("tests/assets/runner_pass_case.py")

    report_result = create_bug_report_from_run(run_result["artifact_paths"]["run_dir"])

    assert report_result["generated"] is False
    assert report_result["status"] == "passed"
    assert "no bug report draft is generated" in report_result["reason"].lower()


def test_reporter_handles_environment_error_honestly() -> None:
    run_result = run_test_script("tests/assets/does_not_exist.py")

    report_result = create_bug_report_from_run(run_result["artifact_paths"]["run_dir"])

    assert report_result["generated"] is False
    assert report_result["status"] == "environment_error"
    assert "environment/setup issue" in report_result["reason"].lower()
