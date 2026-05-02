from pathlib import Path

from app.agent.tools import (
    TOOL_REGISTRY,
    create_report,
    generate_test,
    get_artifacts,
    get_run_summary,
    parse_requirement,
    retrieve_testing_context,
    run_test,
)


def test_agent_tool_registry_exposes_expected_tools() -> None:
    assert {
        "normalize_requirement",
        "parse_requirement",
        "retrieve_testing_context",
        "generate_test",
        "run_test",
        "create_report",
        "get_run_summary",
        "get_artifacts",
    }.issubset(TOOL_REGISTRY)


def test_parse_and_generate_tools_return_serializable_payloads() -> None:
    parse_result = parse_requirement("data/inputs/sample_prd_login.md")

    assert parse_result["document"]["feature_name"] == "User Login"
    assert parse_result["document"]["missing_sections"] == []

    generate_result = generate_test("data/inputs/sample_prd_login.md")

    assert generate_result["test_point_count"] == 1
    assert generate_result["test_points"][0]["id"] == "TP-001"
    assert generate_result["script_path"] == "generated/tests/test_login_generated.py"
    assert Path(generate_result["script_path"]).exists()


def test_retrieval_tool_returns_context_for_generation() -> None:
    retrieval_result = retrieve_testing_context("data/inputs/sample_prd_login.md", max_results=5)

    assert retrieval_result["result_count"] >= 3
    assert "data/contracts/demo_app_selectors.json" in [
        item["source_path"] for item in retrieval_result["results"]
    ]

    generate_result = generate_test(
        "data/inputs/sample_prd_login.md",
        testing_context=retrieval_result,
    )

    assert "data/contracts/demo_app_selectors.json" in generate_result["context_source_paths"]
    assert generate_result["script_path"] == "generated/tests/test_login_generated.py"


def test_run_summary_and_artifact_tools_read_saved_run_outputs() -> None:
    run_result = run_test("tests/assets/runner_pass_case.py")

    assert run_result["status"] == "passed"

    summary_result = get_run_summary(run_result["run_id"])
    artifacts_result = get_artifacts(run_result["run_dir"])

    assert summary_result["summary"]["status"] == "passed"
    assert summary_result["summary"]["run_id"] == run_result["run_id"]
    assert artifacts_result["artifact_paths"]["summary"].endswith("summary.json")
    assert artifacts_result["run_id"] == run_result["run_id"]


def test_report_tool_generates_report_for_failed_run() -> None:
    run_result = run_test("tests/assets/runner_fail_case.py")

    assert run_result["status"] == "failed"

    report_result = create_report(run_result["run_dir"])

    assert report_result["generated"] is True
    assert report_result["status"] == "failed"
    assert report_result["report_path"].startswith("generated/reports/")
    assert Path(report_result["report_path"]).exists()
