from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app.main", *args],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )


def _trace_path(agent_run_id: str) -> Path:
    return Path("data/agent_runs") / agent_run_id / "trace.json"


def _load_trace(agent_run_id: str) -> dict[str, object]:
    return json.loads(_trace_path(agent_run_id).read_text(encoding="utf-8"))


def _tool_names(trace: dict[str, object]) -> list[str]:
    tool_calls = trace.get("tool_calls")
    assert isinstance(tool_calls, list)
    return [str(call["tool_name"]) for call in tool_calls if isinstance(call, dict)]


def _decision_statuses(trace: dict[str, object]) -> list[str]:
    decisions = trace.get("decision_trace")
    assert isinstance(decisions, list)
    return [str(decision["status"]) for decision in decisions if isinstance(decision, dict)]


def test_golden_demo_login_manual_flow_generates_plan_trace_and_run_summary() -> None:
    agent_run_id = "golden_demo_login_manual"

    created = _run_cli(
        "agent-run",
        "--task",
        "Verify login happy path with valid credentials.",
        "--target-url",
        "/login",
        "--module",
        "login",
        "--approval-mode",
        "manual",
        "--agent-run-id",
        agent_run_id,
    )
    assert "final_status: waiting_human_approval" in created.stdout
    assert f"test_plan_path: data/agent_runs/{agent_run_id}/test_plan.json" in created.stdout

    after_plan = _run_cli(
        "agent-approve",
        "--agent-run-id",
        agent_run_id,
        "--gate",
        "test_plan",
        "--decision",
        "approved",
        "--reviewer",
        "pytest",
    )
    assert "final_status: waiting_human_approval" in after_plan.stdout
    assert "pending_approval: execution" in after_plan.stdout

    after_execution = _run_cli(
        "agent-approve",
        "--agent-run-id",
        agent_run_id,
        "--gate",
        "execution",
        "--decision",
        "approved",
        "--reviewer",
        "pytest",
    )
    assert "final_status: passed" in after_execution.stdout

    trace = _load_trace(agent_run_id)
    final_output = trace["final_output"]
    assert isinstance(final_output, dict)
    assert trace["final_status"] == "passed"
    assert trace["status"] == "completed"
    assert "generate_test_from_plan" in _tool_names(trace)
    assert "waiting_human_approval" in _decision_statuses(trace)
    assert Path(final_output["test_plan_path"]).exists()
    assert final_output["run_summary"]["summary"]["artifact_paths"]["summary"].endswith("summary.json")
    assert final_output["artifact_paths"]["summary"].endswith("summary.json")


def test_golden_demo_existing_script_failed_flow_generates_report_draft() -> None:
    agent_run_id = "golden_demo_failed_report"

    created = _run_cli(
        "agent-run",
        "--script",
        "tests/assets/runner_fail_case.py",
        "--approval-mode",
        "manual",
        "--module",
        "runner failure",
        "--agent-run-id",
        agent_run_id,
    )
    assert "final_status: waiting_human_approval" in created.stdout

    after_execution = _run_cli(
        "agent-approve",
        "--agent-run-id",
        agent_run_id,
        "--gate",
        "execution",
        "--decision",
        "approved",
        "--reviewer",
        "pytest",
    )
    assert "final_status: report_draft_created" in after_execution.stdout
    assert "pending_approval: report" in after_execution.stdout

    trace = _load_trace(agent_run_id)
    final_output = trace["final_output"]
    assert isinstance(final_output, dict)
    assert trace["final_status"] == "report_draft_created"
    assert trace["status"] == "waiting_for_approval"
    assert "create_report" in _tool_names(trace)
    assert "report_draft_created" in _decision_statuses(trace)
    assert Path(final_output["report_draft_path"]).exists()
    assert final_output["artifact_paths"]["summary"].endswith("summary.json")

    after_report = _run_cli(
        "agent-approve",
        "--agent-run-id",
        agent_run_id,
        "--gate",
        "report",
        "--decision",
        "approved",
        "--reviewer",
        "pytest",
    )
    assert "final_status: failed" in after_report.stdout


def test_golden_demo_search_prd_flow_records_blocked_status_and_trace_artifacts() -> None:
    agent_run_id = "golden_demo_search_blocked"

    result = _run_cli(
        "agent-run",
        "--input",
        "data/inputs/sample_prd_search.md",
        "--agent-run-id",
        agent_run_id,
    )
    assert "final_status: blocked_missing_context" in result.stdout

    trace = _load_trace(agent_run_id)
    final_output = trace["final_output"]
    assert isinstance(final_output, dict)
    assert trace["final_status"] == "blocked_missing_context"
    assert "generate_test_from_plan" in _tool_names(trace)
    assert "blocked_missing_context" in _decision_statuses(trace)
    assert Path(final_output["test_plan_path"]).exists()
    assert final_output["run_summary"]["summary"]["status"] == "blocked"
    assert final_output["artifact_paths"]["summary"].endswith("summary.json")
