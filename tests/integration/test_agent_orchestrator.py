import json
from pathlib import Path

from app.agent import graph
from app.agent.orchestrator import continue_agent_run, run_agent_task


SUCCESS_TOOL_SEQUENCE = [
    "parse_requirement",
    "analyze_information_needs",
    "retrieve_testing_context",
    "draft_test_plan",
    "validate_test_plan",
    "generate_test_from_plan",
    "run_test",
    "collect_run_evidence",
]

EXISTING_SCRIPT_FAILED_TOOL_SEQUENCE = [
    "prepare_existing_script_execution",
    "run_test",
    "collect_run_evidence",
    "create_report",
]


def _load_trace(trace_path: str) -> dict[str, object]:
    return json.loads(Path(trace_path).read_text(encoding="utf-8"))


def test_agent_orchestrator_records_blocked_search_trace() -> None:
    result = run_agent_task("data/inputs/sample_prd_search.md")

    assert result["final_status"] == "blocked_missing_context"
    assert result["script_path"] == "generated/tests/test_search_generated.py"
    assert result["run_id"]
    assert Path(result["trace_path"]).exists()

    trace = _load_trace(result["trace_path"])
    tool_names = [call["tool_name"] for call in trace["tool_calls"]]

    assert trace["status"] == "completed"
    assert trace["final_status"] == "blocked_missing_context"
    assert tool_names == SUCCESS_TOOL_SEQUENCE
    assert trace["final_output"]["run_id"] == result["run_id"]
    assert trace["final_output"]["artifact_paths"]["summary"].endswith("summary.json")
    assert trace["final_output"]["test_plan_path"] == result["test_plan_path"]
    assert Path(result["test_plan_path"]).exists()
    assert "data/contracts/demo_app_selectors.json" in trace["final_output"]["retrieved_context"]["source_paths"]
    assert trace["final_output"]["plan_validation"]["status"] == "passed"
    assert trace["final_output"]["run_summary"]["run_id"] == result["run_id"]
    assert trace["final_output"]["checkpoint_mode"] == "trace_resume_state"
    assert trace["final_output"]["retrieval_backend"] == "file_lexical"
    assert trace["final_output"]["retrieval_implementation"] == "deterministic_file_lexical"
    assert trace["final_output"]["planning_backend"] == "deterministic"
    assert trace["final_output"]["planning_implementation"] == "deterministic_test_plan_scaffold"
    assert trace["decision_trace"][-1]["status"] == "blocked_missing_context"


def test_agent_orchestrator_records_passed_login_trace() -> None:
    result = run_agent_task("data/inputs/sample_prd_login.md")

    assert result["final_status"] == "passed"
    assert result["script_path"] == "generated/tests/test_login_generated.py"
    assert result["artifact_paths"]["summary"].endswith("summary.json")

    trace = _load_trace(result["trace_path"])
    tool_names = [call["tool_name"] for call in trace["tool_calls"]]

    assert trace["status"] == "completed"
    assert trace["final_status"] == "passed"
    assert tool_names == SUCCESS_TOOL_SEQUENCE
    assert all(call["status"] == "succeeded" for call in trace["tool_calls"])


def test_agent_orchestrator_invokes_report_tool_for_failed_run(monkeypatch) -> None:
    def fake_parse_requirement(input_path: str) -> dict[str, object]:
        return {"resolved_input_path": input_path, "document": {"feature_name": "Fake"}}

    def fake_retrieve_testing_context(
        input_path: str,
        max_results: int = 5,
        source_types=None,
        query=None,
        backend: str = "file_lexical",
    ) -> dict[str, object]:
        return {
            "retrieval_backend": "file_lexical",
            "retrieval_implementation": "deterministic_file_lexical",
            "result_count": 1,
            "results": [{"source_type": "selector_contract", "source_path": "data/contracts/demo_app_selectors.json"}],
        }

    def fake_draft_test_plan(
        input_path: str,
        testing_context=None,
        information_needs=None,
        planning_backend: str = "deterministic",
    ) -> dict[str, object]:
        return {
            "feature_name": "Fake",
            "page_url": "/fake",
            "planning_strategy": "deterministic_scaffold",
            "planning_backend": "deterministic",
            "planning_implementation": "deterministic_test_plan_scaffold",
            "planner_provider": None,
            "retrieved_source_paths": ["data/contracts/demo_app_selectors.json"],
            "retrieved_sources": [{"source_type": "selector_contract", "source_path": "data/contracts/demo_app_selectors.json"}],
            "test_cases": [{"id": "TP-001", "title": "Fake case"}],
            "risks": [],
            "missing_inputs": [],
        }

    def fake_validate_test_plan(test_plan: dict[str, object]) -> dict[str, object]:
        return {"status": "passed", "missing_inputs": [], "can_generate": True, "reason": "test_plan_ready"}

    def fake_generate_test_from_plan(input_path: str, test_plan: dict[str, object], testing_context=None) -> dict[str, object]:
        assert testing_context["result_count"] == 1
        return {
            "script_path": "generated/tests/fake_failed_test.py",
            "generation_mode": "test_plan",
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

    def fake_collect_run_evidence(run_reference: str) -> dict[str, object]:
        return {
            "queried_tools": ["get_run_summary", "get_artifacts"],
            "run_summary": {"run_id": "fake_failed_run", "run_dir": run_reference, "summary": {"status": "failed"}},
            "queried_artifacts": {"run_id": "fake_failed_run", "run_dir": run_reference, "artifact_paths": {}},
        }

    monkeypatch.setattr(graph.tools, "parse_requirement", fake_parse_requirement)
    monkeypatch.setattr(graph.tools, "retrieve_testing_context", fake_retrieve_testing_context)
    monkeypatch.setattr(graph.tools, "draft_test_plan", fake_draft_test_plan)
    monkeypatch.setattr(graph.tools, "validate_test_plan", fake_validate_test_plan)
    monkeypatch.setattr(graph.tools, "generate_test_from_plan", fake_generate_test_from_plan)
    monkeypatch.setattr(graph.tools, "run_test", fake_run_test)
    monkeypatch.setattr(graph.tools, "create_report", fake_create_report)
    monkeypatch.setattr(graph.tools, "collect_run_evidence", fake_collect_run_evidence)

    result = run_agent_task("data/inputs/fake_failed_prd.md")

    assert result["final_status"] == "failed"
    assert result["report_path"] == "generated/reports/bug_report_fake_failed_run.md"
    assert result["report_draft_path"] == "generated/reports/bug_report_fake_failed_run.md"
    assert result["report_approved"] is True
    assert result["report_exported"] is True

    trace = _load_trace(result["trace_path"])
    tool_names = [call["tool_name"] for call in trace["tool_calls"]]

    assert tool_names == [
        "parse_requirement",
        "analyze_information_needs",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
        "generate_test_from_plan",
        "run_test",
        "collect_run_evidence",
        "create_report",
    ]
    assert trace["final_output"]["report_path"] == "generated/reports/bug_report_fake_failed_run.md"


def test_agent_orchestrator_runs_existing_script_failed_report_path() -> None:
    result = run_agent_task(
        "tests/assets/runner_fail_case.py",
        agent_run_id="existing_script_orchestrator_failed_report",
        script_path="tests/assets/runner_fail_case.py",
    )

    assert result["final_status"] == "failed"
    assert result["script_path"] == "tests/assets/runner_fail_case.py"
    assert result["report_draft_path"].startswith("generated/reports/")
    assert result["test_plan"] is None
    assert Path(result["report_draft_path"]).exists()

    trace = _load_trace(result["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == EXISTING_SCRIPT_FAILED_TOOL_SEQUENCE
    assert trace["final_output"]["script_path"] == "tests/assets/runner_fail_case.py"


def test_agent_orchestrator_manual_mode_pauses_and_resumes_login_flow() -> None:
    created = run_agent_task(
        "data/inputs/sample_prd_login.md",
        agent_run_id="manual_orchestrator_login_flow",
        approval_mode="manual",
    )

    assert created["final_status"] == "waiting_human_approval"
    assert created["pending_approval"]["gate"] == "test_plan"
    assert created["test_plan"]["feature_name"] == "User Login"
    assert created["test_plan_path"].endswith("/test_plan.json")
    assert Path(created["test_plan_path"]).exists()

    after_plan = continue_agent_run(
        created["agent_run_id"],
        gate="test_plan",
        decision="approved",
        reviewer="pytest",
        comment="plan ok",
    )

    assert after_plan["final_status"] == "waiting_human_approval"
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
    assert [call["tool_name"] for call in trace["tool_calls"]] == SUCCESS_TOOL_SEQUENCE


def test_agent_orchestrator_manual_failed_run_approves_report_draft(monkeypatch) -> None:
    def fake_parse_requirement(input_path: str) -> dict[str, object]:
        return {"resolved_input_path": input_path, "document": {"feature_name": "Fake", "page_url": "/fake"}}

    def fake_retrieve_testing_context(
        input_path: str,
        max_results: int = 5,
        source_types=None,
        query=None,
        backend: str = "file_lexical",
    ) -> dict[str, object]:
        return {
            "retrieval_backend": "file_lexical",
            "retrieval_implementation": "deterministic_file_lexical",
            "result_count": 1,
            "results": [{"source_type": "selector_contract", "source_path": "data/contracts/demo_app_selectors.json"}],
        }

    def fake_draft_test_plan(
        input_path: str,
        testing_context=None,
        information_needs=None,
        planning_backend: str = "deterministic",
    ) -> dict[str, object]:
        return {
            "feature_name": "Fake",
            "page_url": "/fake",
            "planning_strategy": "deterministic_scaffold",
            "planning_backend": "deterministic",
            "planning_implementation": "deterministic_test_plan_scaffold",
            "planner_provider": None,
            "retrieved_source_paths": ["data/contracts/demo_app_selectors.json"],
            "retrieved_sources": [{"source_type": "selector_contract", "source_path": "data/contracts/demo_app_selectors.json"}],
            "test_cases": [{"id": "TP-001", "title": "Fake case"}],
            "risks": [],
            "missing_inputs": [],
        }

    def fake_validate_test_plan(test_plan: dict[str, object]) -> dict[str, object]:
        return {"status": "passed", "missing_inputs": [], "can_generate": True, "reason": "test_plan_ready"}

    def fake_generate_test_from_plan(input_path: str, test_plan: dict[str, object], testing_context=None) -> dict[str, object]:
        return {"script_path": "generated/tests/fake_failed_test.py", "generation_mode": "test_plan", "test_point_count": 1}

    def fake_run_test(input_path: str) -> dict[str, object]:
        return {
            "run_id": "fake_manual_failed_run",
            "run_dir": "data/runs/fake_manual_failed_run",
            "status": "failed",
            "artifact_paths": {"summary": "data/runs/fake_manual_failed_run/summary.json"},
        }

    def fake_collect_run_evidence(run_reference: str) -> dict[str, object]:
        return {
            "queried_tools": ["get_run_summary", "get_artifacts"],
            "run_summary": {"run_id": "fake_manual_failed_run", "run_dir": run_reference, "summary": {"status": "failed"}},
            "queried_artifacts": {"run_id": "fake_manual_failed_run", "run_dir": run_reference, "artifact_paths": {}},
        }

    def fake_create_report(input_path: str) -> dict[str, object]:
        return {
            "generated": True,
            "run_id": "fake_manual_failed_run",
            "run_dir": input_path,
            "status": "failed",
            "report_path": "generated/reports/bug_report_fake_manual_failed_run.md",
        }

    monkeypatch.setattr(graph.tools, "parse_requirement", fake_parse_requirement)
    monkeypatch.setattr(graph.tools, "retrieve_testing_context", fake_retrieve_testing_context)
    monkeypatch.setattr(graph.tools, "draft_test_plan", fake_draft_test_plan)
    monkeypatch.setattr(graph.tools, "validate_test_plan", fake_validate_test_plan)
    monkeypatch.setattr(graph.tools, "generate_test_from_plan", fake_generate_test_from_plan)
    monkeypatch.setattr(graph.tools, "run_test", fake_run_test)
    monkeypatch.setattr(graph.tools, "collect_run_evidence", fake_collect_run_evidence)
    monkeypatch.setattr(graph.tools, "create_report", fake_create_report)

    created = run_agent_task(
        "data/inputs/fake_failed_prd.md",
        agent_run_id="manual_orchestrator_failed_report_flow",
        approval_mode="manual",
    )
    assert created["final_status"] == "waiting_human_approval"

    after_plan = continue_agent_run(created["agent_run_id"], gate="test_plan", decision="approved")
    assert after_plan["final_status"] == "waiting_human_approval"

    after_execution = continue_agent_run(created["agent_run_id"], gate="execution", decision="approved")
    assert after_execution["final_status"] == "report_draft_created"
    assert after_execution["report_draft_path"] == "generated/reports/bug_report_fake_manual_failed_run.md"
    assert after_execution["report_approved"] is False

    after_report = continue_agent_run(created["agent_run_id"], gate="report", decision="approved")
    assert after_report["final_status"] == "failed"
    assert after_report["report_draft_path"] == "generated/reports/bug_report_fake_manual_failed_run.md"
    assert after_report["report_approved"] is True
    assert after_report["report_exported"] is True
