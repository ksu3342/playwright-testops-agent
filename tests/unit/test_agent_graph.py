import json
from pathlib import Path

from app.agent import graph
from app.agent.graph import invoke_agent_graph
from app.agent.tracer import AgentRunTracer


def _load_trace(trace_path: str) -> dict[str, object]:
    return json.loads(Path(trace_path).read_text(encoding="utf-8"))


def _fake_retrieval() -> dict[str, object]:
    return {
        "retrieval_backend": "file_lexical",
        "retrieval_implementation": "deterministic_file_lexical",
        "result_count": 1,
        "results": [{"source_type": "selector_contract", "source_path": "data/contracts/demo_app_selectors.json"}],
    }


def _fake_test_plan() -> dict[str, object]:
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


def _patch_passed_plan_tools(monkeypatch) -> None:
    def fake_parse_requirement(input_path: str) -> dict[str, object]:
        return {"resolved_input_path": input_path, "document": {"feature_name": "Fake"}}

    def fake_retrieve_testing_context(
        input_path: str,
        max_results: int = 5,
        source_types=None,
        query=None,
        backend: str = "file_lexical",
    ) -> dict[str, object]:
        assert source_types is not None
        assert backend == "file_lexical"
        return _fake_retrieval()

    def fake_draft_test_plan(
        input_path: str,
        testing_context=None,
        information_needs=None,
        planning_backend: str = "deterministic",
    ) -> dict[str, object]:
        assert testing_context["result_count"] == 1
        assert information_needs["required_context_types"]
        assert planning_backend == "deterministic"
        return _fake_test_plan()

    def fake_validate_test_plan(test_plan: dict[str, object]) -> dict[str, object]:
        assert test_plan["feature_name"] == "Fake"
        return {"status": "passed", "missing_inputs": [], "can_generate": True, "reason": "test_plan_ready"}

    def fake_collect_run_evidence(run_reference: str) -> dict[str, object]:
        return {
            "queried_tools": ["get_run_summary", "get_artifacts"],
            "run_summary": {"run_id": Path(run_reference).name, "run_dir": run_reference, "summary": {"status": "passed"}},
            "queried_artifacts": {"run_id": Path(run_reference).name, "run_dir": run_reference, "artifact_paths": {}},
        }

    monkeypatch.setattr(graph.tools, "parse_requirement", fake_parse_requirement)
    monkeypatch.setattr(graph.tools, "retrieve_testing_context", fake_retrieve_testing_context)
    monkeypatch.setattr(graph.tools, "draft_test_plan", fake_draft_test_plan)
    monkeypatch.setattr(graph.tools, "validate_test_plan", fake_validate_test_plan)
    monkeypatch.setattr(graph.tools, "collect_run_evidence", fake_collect_run_evidence)


def test_langgraph_agent_graph_runs_passed_path_with_expected_nodes(monkeypatch) -> None:
    _patch_passed_plan_tools(monkeypatch)

    def fake_generate_test(input_path: str, testing_context=None) -> dict[str, object]:
        assert testing_context["result_count"] == 1
        return {
            "script_path": "generated/tests/fake_passed_test.py",
            "test_point_count": 1,
            "context_source_paths": ["data/contracts/demo_app_selectors.json"],
        }

    def fake_run_test(input_path: str) -> dict[str, object]:
        return {
            "run_id": "fake_passed_run",
            "run_dir": "data/runs/fake_passed_run",
            "status": "passed",
            "artifact_paths": {"summary": "data/runs/fake_passed_run/summary.json"},
        }

    monkeypatch.setattr(graph.tools, "generate_test", fake_generate_test)
    monkeypatch.setattr(graph.tools, "run_test", fake_run_test)

    tracer = AgentRunTracer.create(
        {"input_path": "data/inputs/fake_passed_prd.md"},
        agent_run_id="unit_graph_passed_path",
    )
    state = invoke_agent_graph("data/inputs/fake_passed_prd.md", tracer)

    assert state["final_status"] == "passed"
    assert state["final_output"]["run_id"] == "fake_passed_run"
    assert state["final_output"]["trace_path"] == "data/agent_runs/unit_graph_passed_path/trace.json"
    assert state["final_output"]["test_plan"]["feature_name"] == "Fake"
    assert state["final_output"]["plan_validation"]["status"] == "passed"
    assert state["final_output"]["planning_strategy"] == "deterministic_scaffold"
    assert state["final_output"]["planning_backend"] == "deterministic"
    assert state["final_output"]["planning_implementation"] == "deterministic_test_plan_scaffold"
    assert state["final_output"]["checkpoint_mode"] == "trace_resume_state"
    assert state["final_output"]["run_summary"]["run_id"] == "fake_passed_run"
    assert state["final_output"]["retrieval_backend"] == "file_lexical"
    assert state["final_output"]["retrieval_implementation"] == "deterministic_file_lexical"

    trace = _load_trace(state["final_output"]["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == [
        "parse_requirement",
        "analyze_information_needs",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
        "generate_test",
        "run_test",
        "collect_run_evidence",
    ]
    assert trace["checkpoint_mode"] == "trace_resume_state"


def test_langgraph_agent_graph_routes_failed_path_to_report(monkeypatch) -> None:
    _patch_passed_plan_tools(monkeypatch)

    def fake_generate_test(input_path: str, testing_context=None) -> dict[str, object]:
        return {"script_path": "generated/tests/fake_failed_test.py", "test_point_count": 1}

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

    monkeypatch.setattr(graph.tools, "generate_test", fake_generate_test)
    monkeypatch.setattr(graph.tools, "run_test", fake_run_test)
    monkeypatch.setattr(graph.tools, "create_report", fake_create_report)

    tracer = AgentRunTracer.create(
        {"input_path": "data/inputs/fake_failed_prd.md"},
        agent_run_id="unit_graph_failed_path",
    )
    state = invoke_agent_graph("data/inputs/fake_failed_prd.md", tracer)

    assert state["final_status"] == "failed"
    assert state["final_output"]["report_path"] == "generated/reports/bug_report_fake_failed_run.md"
    assert state["final_output"]["report_draft_path"] == "generated/reports/bug_report_fake_failed_run.md"
    assert state["final_output"]["report_approved"] is True
    assert state["final_output"]["report_exported"] is True

    trace = _load_trace(state["final_output"]["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == [
        "parse_requirement",
        "analyze_information_needs",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
        "generate_test",
        "run_test",
        "collect_run_evidence",
        "create_report",
    ]


def test_langgraph_manual_mode_pauses_before_generation(monkeypatch) -> None:
    _patch_passed_plan_tools(monkeypatch)

    def fail_generate_test(input_path: str, testing_context=None) -> dict[str, object]:
        raise AssertionError("generate_test should not run before plan approval")

    monkeypatch.setattr(graph.tools, "generate_test", fail_generate_test)

    tracer = AgentRunTracer.create(
        {"input_path": "data/inputs/fake_manual_prd.md"},
        agent_run_id="unit_graph_manual_plan_pause",
    )
    state = invoke_agent_graph("data/inputs/fake_manual_prd.md", tracer, approval_mode="manual")

    assert state["final_status"] == "waiting_for_test_plan_approval"
    assert state["pending_approval"]["gate"] == "test_plan"
    assert state["final_output"]["test_plan"]["feature_name"] == "Fake"

    trace = _load_trace(state["final_output"]["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == [
        "parse_requirement",
        "analyze_information_needs",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
    ]
    assert trace["approval_requests"][0]["gate"] == "test_plan"
    assert trace["pending_approval"]["gate"] == "test_plan"


def test_langgraph_blocks_invalid_plan_before_generation(monkeypatch) -> None:
    _patch_passed_plan_tools(monkeypatch)

    def fake_validate_test_plan(test_plan: dict[str, object]) -> dict[str, object]:
        return {
            "status": "blocked",
            "missing_inputs": ["page_url"],
            "can_generate": False,
            "reason": "test_plan_missing_required_inputs",
        }

    def fail_generate_test(input_path: str, testing_context=None) -> dict[str, object]:
        raise AssertionError("generate_test should not run after blocked plan validation")

    monkeypatch.setattr(graph.tools, "validate_test_plan", fake_validate_test_plan)
    monkeypatch.setattr(graph.tools, "generate_test", fail_generate_test)

    tracer = AgentRunTracer.create(
        {"input_path": "data/inputs/fake_blocked_prd.md"},
        agent_run_id="unit_graph_blocked_plan",
    )
    state = invoke_agent_graph("data/inputs/fake_blocked_prd.md", tracer)

    assert state["final_status"] == "blocked"
    assert state["final_output"]["plan_validation"]["missing_inputs"] == ["page_url"]

    trace = _load_trace(state["final_output"]["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == [
        "parse_requirement",
        "analyze_information_needs",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
    ]


def test_langgraph_existing_script_path_runs_without_requirement_planning(monkeypatch) -> None:
    def fake_run_test(input_path: str) -> dict[str, object]:
        assert input_path == "tests/assets/runner_pass_case.py"
        return {
            "run_id": "fake_existing_script_run",
            "run_dir": "data/runs/fake_existing_script_run",
            "status": "passed",
            "artifact_paths": {"summary": "data/runs/fake_existing_script_run/summary.json"},
        }

    def fake_collect_run_evidence(run_reference: str) -> dict[str, object]:
        return {
            "queried_tools": ["get_run_summary", "get_artifacts"],
            "run_summary": {"run_id": "fake_existing_script_run", "run_dir": run_reference, "summary": {"status": "passed"}},
            "queried_artifacts": {"run_id": "fake_existing_script_run", "run_dir": run_reference, "artifact_paths": {}},
        }

    monkeypatch.setattr(graph.tools, "run_test", fake_run_test)
    monkeypatch.setattr(graph.tools, "collect_run_evidence", fake_collect_run_evidence)

    tracer = AgentRunTracer.create(
        {
            "input_path": "tests/assets/runner_pass_case.py",
            "script_path": "tests/assets/runner_pass_case.py",
        },
        agent_run_id="unit_graph_existing_script_path",
    )
    state = invoke_agent_graph(
        "tests/assets/runner_pass_case.py",
        tracer,
        script_path="tests/assets/runner_pass_case.py",
    )

    assert state["final_status"] == "passed"
    assert state["final_output"]["script_path"] == "tests/assets/runner_pass_case.py"
    assert state["final_output"]["test_plan"] is None

    trace = _load_trace(state["final_output"]["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == [
        "prepare_existing_script_execution",
        "run_test",
        "collect_run_evidence",
    ]


def test_langgraph_existing_script_manual_mode_pauses_before_execution(monkeypatch) -> None:
    def fail_run_test(input_path: str) -> dict[str, object]:
        raise AssertionError("run_test should not run before execution approval")

    monkeypatch.setattr(graph.tools, "run_test", fail_run_test)

    tracer = AgentRunTracer.create(
        {
            "input_path": "tests/assets/runner_pass_case.py",
            "script_path": "tests/assets/runner_pass_case.py",
        },
        agent_run_id="unit_graph_existing_script_manual_pause",
    )
    state = invoke_agent_graph(
        "tests/assets/runner_pass_case.py",
        tracer,
        approval_mode="manual",
        script_path="tests/assets/runner_pass_case.py",
    )

    assert state["final_status"] == "waiting_for_execution_approval"
    assert state["pending_approval"]["gate"] == "execution"
    assert state["final_output"]["script_path"] == "tests/assets/runner_pass_case.py"

    trace = _load_trace(state["final_output"]["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == ["prepare_existing_script_execution"]


def test_langgraph_manual_mode_pauses_for_report_review_after_failed_run(monkeypatch) -> None:
    _patch_passed_plan_tools(monkeypatch)

    def fake_generate_test(input_path: str, testing_context=None) -> dict[str, object]:
        return {"script_path": "generated/tests/fake_failed_test.py", "test_point_count": 1}

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

    monkeypatch.setattr(graph.tools, "generate_test", fake_generate_test)
    monkeypatch.setattr(graph.tools, "run_test", fake_run_test)
    monkeypatch.setattr(graph.tools, "create_report", fake_create_report)

    tracer = AgentRunTracer.create(
        {"input_path": "data/inputs/fake_failed_prd.md"},
        agent_run_id="unit_graph_report_review_pause",
    )
    state = invoke_agent_graph(
        "data/inputs/fake_failed_prd.md",
        tracer,
        approval_mode="manual",
        approvals={
            "test_plan": {"decision": "approved"},
            "execution": {"decision": "approved"},
        },
    )

    assert state["final_status"] == "waiting_for_report_approval"
    assert state["pending_approval"]["gate"] == "report"
    assert state["final_output"]["report_path"] == "generated/reports/bug_report_fake_failed_run.md"
    assert state["final_output"]["report_draft_path"] == "generated/reports/bug_report_fake_failed_run.md"
    assert state["final_output"]["report_approved"] is False

    trace = _load_trace(state["final_output"]["trace_path"])
    assert trace["approval_requests"][0]["gate"] == "report"
