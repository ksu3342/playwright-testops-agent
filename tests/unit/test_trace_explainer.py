from pathlib import Path

from app.agent.trace_explainer import (
    load_agent_trace,
    render_trace_json,
    render_trace_markdown,
    render_trace_summary,
    write_decision_trace_markdown,
)
from app.agent.tracer import AgentRunTracer


def _sample_trace() -> dict[str, object]:
    return {
        "agent_run_id": "unit_trace_explainer",
        "status": "completed",
        "final_status": "failed",
        "input": {"input_path": "tests/assets/runner_fail_case.py", "script_path": "tests/assets/runner_fail_case.py"},
        "tool_calls": [
            {
                "sequence": 1,
                "tool_name": "prepare_existing_script_execution",
                "status": "succeeded",
                "duration_seconds": 0.001,
            },
            {"sequence": 2, "tool_name": "run_test", "status": "succeeded", "duration_seconds": 0.5},
            {"sequence": 3, "tool_name": "create_report", "status": "succeeded", "duration_seconds": 0.01},
        ],
        "approval_requests": [{"gate": "execution", "status": "approved", "reviewer": "pytest"}],
        "artifact_paths": {
            "trace": "data/agent_runs/unit_trace_explainer/trace.json",
            "test_plan": "data/agent_runs/unit_trace_explainer/test_plan.json",
        },
        "final_output": {
            "input_path": "tests/assets/runner_fail_case.py",
            "script_path": "tests/assets/runner_fail_case.py",
            "run_id": "fake_failed_run",
            "run_status": "failed",
            "artifact_paths": {"summary": "data/runs/fake_failed_run/summary.json"},
            "test_plan_path": "data/agent_runs/unit_trace_explainer/test_plan.json",
            "report_draft_path": "generated/reports/bug_report_fake_failed_run.md",
            "information_needs": {"required_context_types": ["selector_contract"]},
            "retrieved_context": {"source_paths": ["data/contracts/demo_app_selectors.json"]},
            "plan_validation": {"status": "passed", "reason": "test_plan_ready"},
        },
    }


def test_trace_explainer_renders_summary_json_and_markdown() -> None:
    trace = _sample_trace()

    summary = render_trace_summary(trace)
    json_output = render_trace_json(trace)
    markdown = render_trace_markdown(trace)

    assert "Agent run: unit_trace_explainer" in summary
    assert "prepare_existing_script_execution" in summary
    assert "Test plan: data/agent_runs/unit_trace_explainer/test_plan.json" in summary
    assert "Run summary: data/runs/fake_failed_run/summary.json" in summary
    assert "Report draft: generated/reports/bug_report_fake_failed_run.md" in summary
    assert '"agent_run_id": "unit_trace_explainer"' in json_output
    assert markdown.startswith("# Agent Decision Trace: unit_trace_explainer")


def test_trace_explainer_writes_decision_trace_markdown() -> None:
    tracer = AgentRunTracer.create({"input_path": "tests/assets/runner_fail_case.py"}, agent_run_id="unit_trace_markdown_write")
    tracer.finalize(
        final_status="failed",
        final_output={
            "input_path": "tests/assets/runner_fail_case.py",
            "script_path": "tests/assets/runner_fail_case.py",
            "run_id": "fake_failed_run",
            "run_status": "failed",
            "trace_path": "data/agent_runs/unit_trace_markdown_write/trace.json",
        },
    )

    output_path = write_decision_trace_markdown("unit_trace_markdown_write")
    trace = load_agent_trace("unit_trace_markdown_write")

    assert output_path == Path("data/agent_runs/unit_trace_markdown_write/decision_trace.md").resolve()
    assert output_path.exists()
    assert trace["agent_run_id"] == "unit_trace_markdown_write"
    assert "Agent Decision Trace" in output_path.read_text(encoding="utf-8")
