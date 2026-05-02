import json
from pathlib import Path

from app.agent import graph
from app.agent.graph import invoke_agent_graph
from app.agent.tracer import AgentRunTracer


def _load_trace(trace_path: str) -> dict[str, object]:
    return json.loads(Path(trace_path).read_text(encoding="utf-8"))


def test_langgraph_agent_graph_runs_passed_path_with_expected_nodes(monkeypatch) -> None:
    def fake_parse_requirement(input_path: str) -> dict[str, object]:
        return {"resolved_input_path": input_path, "document": {"feature_name": "Fake"}}

    def fake_generate_test(input_path: str) -> dict[str, object]:
        return {"script_path": "generated/tests/fake_passed_test.py", "test_point_count": 1}

    def fake_run_test(input_path: str) -> dict[str, object]:
        return {
            "run_id": "fake_passed_run",
            "run_dir": "data/runs/fake_passed_run",
            "status": "passed",
            "artifact_paths": {"summary": "data/runs/fake_passed_run/summary.json"},
        }

    monkeypatch.setattr(graph.tools, "parse_requirement", fake_parse_requirement)
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

    trace = _load_trace(state["final_output"]["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == ["parse_requirement", "generate_test", "run_test"]


def test_langgraph_agent_graph_routes_failed_path_to_report(monkeypatch) -> None:
    def fake_parse_requirement(input_path: str) -> dict[str, object]:
        return {"resolved_input_path": input_path, "document": {"feature_name": "Fake"}}

    def fake_generate_test(input_path: str) -> dict[str, object]:
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

    monkeypatch.setattr(graph.tools, "parse_requirement", fake_parse_requirement)
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

    trace = _load_trace(state["final_output"]["trace_path"])
    assert [call["tool_name"] for call in trace["tool_calls"]] == [
        "parse_requirement",
        "generate_test",
        "run_test",
        "create_report",
    ]
