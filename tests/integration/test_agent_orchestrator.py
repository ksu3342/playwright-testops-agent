import json
from pathlib import Path

from app.agent import orchestrator
from app.agent.orchestrator import run_agent_task


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
    assert tool_names == ["parse_requirement", "generate_test", "run_test"]
    assert trace["final_output"]["run_id"] == result["run_id"]
    assert trace["final_output"]["artifact_paths"]["summary"].endswith("summary.json")


def test_agent_orchestrator_records_passed_login_trace() -> None:
    result = run_agent_task("data/inputs/sample_prd_login.md")

    assert result["final_status"] == "passed"
    assert result["script_path"] == "generated/tests/test_login_generated.py"
    assert result["artifact_paths"]["summary"].endswith("summary.json")

    trace = _load_trace(result["trace_path"])
    tool_names = [call["tool_name"] for call in trace["tool_calls"]]

    assert trace["status"] == "completed"
    assert trace["final_status"] == "passed"
    assert tool_names == ["parse_requirement", "generate_test", "run_test"]
    assert all(call["status"] == "succeeded" for call in trace["tool_calls"])


def test_agent_orchestrator_invokes_report_tool_for_failed_run(monkeypatch) -> None:
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

    monkeypatch.setattr(orchestrator.tools, "parse_requirement", fake_parse_requirement)
    monkeypatch.setattr(orchestrator.tools, "generate_test", fake_generate_test)
    monkeypatch.setattr(orchestrator.tools, "run_test", fake_run_test)
    monkeypatch.setattr(orchestrator.tools, "create_report", fake_create_report)

    result = run_agent_task("data/inputs/fake_failed_prd.md")

    assert result["final_status"] == "failed"
    assert result["report_path"] == "generated/reports/bug_report_fake_failed_run.md"

    trace = _load_trace(result["trace_path"])
    tool_names = [call["tool_name"] for call in trace["tool_calls"]]

    assert tool_names == ["parse_requirement", "generate_test", "run_test", "create_report"]
    assert trace["final_output"]["report_path"] == "generated/reports/bug_report_fake_failed_run.md"
