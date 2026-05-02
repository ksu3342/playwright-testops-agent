import json
from pathlib import Path

from app.agent import graph
from app.agent.orchestrator import continue_agent_run, run_agent_task


def _load_trace(trace_path: str) -> dict[str, object]:
    return json.loads(Path(trace_path).read_text(encoding="utf-8"))


def test_agent_orchestrator_records_blocked_search_trace() -> None:
    result = run_agent_task("data/inputs/sample_prd_search.md")

    assert result["final_status"] == "blocked"
    assert result["script_path"] == "generated/tests/test_search_generated.py"
    assert result["run_id"]
    assert Path(result["trace_path"]).exists()

    trace = _load_trace(result["trace_path"])
    tool_names = [call["tool_name"] for call in trace["tool_calls"]]

    assert trace["status"] == "completed"
    assert trace["final_status"] == "blocked"
    assert tool_names == [
        "parse_requirement",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
        "generate_test",
        "run_test",
    ]
    assert trace["final_output"]["run_id"] == result["run_id"]
    assert trace["final_output"]["artifact_paths"]["summary"].endswith("summary.json")
    assert "data/contracts/demo_app_selectors.json" in trace["final_output"]["retrieved_context"]["source_paths"]
    assert trace["final_output"]["plan_validation"]["status"] == "passed"


def test_agent_orchestrator_records_passed_login_trace() -> None:
    result = run_agent_task("data/inputs/sample_prd_login.md")

    assert result["final_status"] == "passed"
    assert result["script_path"] == "generated/tests/test_login_generated.py"
    assert result["artifact_paths"]["summary"].endswith("summary.json")

    trace = _load_trace(result["trace_path"])
    tool_names = [call["tool_name"] for call in trace["tool_calls"]]

    assert trace["status"] == "completed"
    assert trace["final_status"] == "passed"
    assert tool_names == [
        "parse_requirement",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
        "generate_test",
        "run_test",
    ]
    assert all(call["status"] == "succeeded" for call in trace["tool_calls"])


def test_agent_orchestrator_invokes_report_tool_for_failed_run(monkeypatch) -> None:
    def fake_parse_requirement(input_path: str) -> dict[str, object]:
        return {"resolved_input_path": input_path, "document": {"feature_name": "Fake"}}

    def fake_retrieve_testing_context(input_path: str, max_results: int = 5) -> dict[str, object]:
        return {
            "result_count": 1,
            "results": [{"source_type": "selector_contract", "source_path": "data/contracts/demo_app_selectors.json"}],
        }

    def fake_draft_test_plan(input_path: str, testing_context=None) -> dict[str, object]:
        return {
            "feature_name": "Fake",
            "page_url": "/fake",
            "retrieved_source_paths": ["data/contracts/demo_app_selectors.json"],
            "retrieved_sources": [{"source_type": "selector_contract", "source_path": "data/contracts/demo_app_selectors.json"}],
            "test_cases": [{"id": "TP-001", "title": "Fake case"}],
            "risks": [],
            "missing_inputs": [],
        }

    def fake_validate_test_plan(test_plan: dict[str, object]) -> dict[str, object]:
        return {"status": "passed", "missing_inputs": [], "can_generate": True, "reason": "test_plan_ready"}

    def fake_generate_test(input_path: str, testing_context=None) -> dict[str, object]:
        assert testing_context["result_count"] == 1
        return {
            "script_path": "generated/tests/fake_failed_test.py",
            "test_point_count": 1,
            "context_source_paths": ["data/contracts/demo_app_selectors.json"],
        }

    def fake_run_test(input_path: str) -> dict[str, object]:
        return {
            "run_id": "fake_failed_run",
            "run_dir": "data/runs/fake_failed_run",
            "status": "failed",
            "artifact_paths": {"summary": "data/runs/fake_failed_run/summary.json"},
        }

    def fake_create_report(input_path: str) -> dict[str, object]:
        return {
            "generated": True,
            "run_id": "fake_failed_run",
            "run_dir": input_path,
            "status": "failed",
            "report_path": "generated/reports/bug_report_fake_failed_run.md",
        }

    monkeypatch.setattr(graph.tools, "parse_requirement", fake_parse_requirement)
    monkeypatch.setattr(graph.tools, "retrieve_testing_context", fake_retrieve_testing_context)
    monkeypatch.setattr(graph.tools, "draft_test_plan", fake_draft_test_plan)
    monkeypatch.setattr(graph.tools, "validate_test_plan", fake_validate_test_plan)
    monkeypatch.setattr(graph.tools, "generate_test", fake_generate_test)
    monkeypatch.setattr(graph.tools, "run_test", fake_run_test)
    monkeypatch.setattr(graph.tools, "create_report", fake_create_report)

    result = run_agent_task("data/inputs/fake_failed_prd.md")

    assert result["final_status"] == "failed"
    assert result["report_path"] == "generated/reports/bug_report_fake_failed_run.md"

    trace = _load_trace(result["trace_path"])
    tool_names = [call["tool_name"] for call in trace["tool_calls"]]

    assert tool_names == [
        "parse_requirement",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
        "generate_test",
        "run_test",
        "create_report",
    ]
    assert trace["final_output"]["report_path"] == "generated/reports/bug_report_fake_failed_run.md"


def test_agent_orchestrator_manual_mode_pauses_and_resumes_login_flow() -> None:
    created = run_agent_task(
        "data/inputs/sample_prd_login.md",
        agent_run_id="manual_orchestrator_login_flow",
        approval_mode="manual",
    )

    assert created["final_status"] == "waiting_for_test_plan_approval"
    assert created["pending_approval"]["gate"] == "test_plan"
    assert created["test_plan"]["feature_name"] == "User Login"

    after_plan = continue_agent_run(
        created["agent_run_id"],
        gate="test_plan",
        decision="approved",
        reviewer="pytest",
        comment="plan ok",
    )

    assert after_plan["final_status"] == "waiting_for_execution_approval"
    assert after_plan["pending_approval"]["gate"] == "execution"
    assert after_plan["script_path"] == "generated/tests/test_login_generated.py"

    after_execution = continue_agent_run(
        created["agent_run_id"],
        gate="execution",
        decision="approved",
        reviewer="pytest",
        comment="execute",
    )

    assert after_execution["final_status"] == "passed"
    assert after_execution["run_id"]

    trace = _load_trace(after_execution["trace_path"])
    assert trace["status"] == "completed"
    assert trace["human_approvals"]["test_plan"]["decision"] == "approved"
    assert trace["human_approvals"]["execution"]["decision"] == "approved"
    assert [call["tool_name"] for call in trace["tool_calls"]] == [
        "parse_requirement",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
        "generate_test",
        "run_test",
    ]
