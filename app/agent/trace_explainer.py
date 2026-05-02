from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agent.tracer import AGENT_RUNS_DIR


def _relative_trace_path(agent_run_id: str) -> Path:
    run_dir = (AGENT_RUNS_DIR / agent_run_id).resolve()
    if run_dir.parent != AGENT_RUNS_DIR.resolve():
        raise FileNotFoundError(f"Agent run was not found: {agent_run_id}")
    trace_path = run_dir / "trace.json"
    if not trace_path.is_file():
        raise FileNotFoundError(f"Agent run trace was not found: {agent_run_id}")
    return trace_path


def load_agent_trace(agent_run_id: str) -> dict[str, Any]:
    trace_path = _relative_trace_path(agent_run_id)
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Agent run trace is not a JSON object: {agent_run_id}")
    return payload


def _string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item) for item in items if item is not None]


def _source_paths(final_output: dict[str, Any]) -> list[str]:
    retrieved_context = final_output.get("retrieved_context")
    if not isinstance(retrieved_context, dict):
        return []
    return _string_list(retrieved_context.get("source_paths"))


def _tool_call_lines(trace: dict[str, Any]) -> list[str]:
    tool_calls = trace.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []

    lines: list[str] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        sequence = call.get("sequence")
        tool_name = call.get("tool_name", "unknown_tool")
        status = call.get("status", "unknown")
        duration = call.get("duration_seconds")
        if isinstance(duration, (int, float)):
            lines.append(f"{sequence}. {tool_name}: {status} ({duration}s)")
        else:
            lines.append(f"{sequence}. {tool_name}: {status}")
    return lines


def _approval_lines(trace: dict[str, Any]) -> list[str]:
    requests = trace.get("approval_requests")
    if not isinstance(requests, list):
        return []

    lines: list[str] = []
    for request in requests:
        if not isinstance(request, dict):
            continue
        gate = request.get("gate", "unknown_gate")
        status = request.get("status", "unknown")
        reviewer = request.get("reviewer")
        suffix = f" by {reviewer}" if reviewer else ""
        lines.append(f"{gate}: {status}{suffix}")
    return lines


def render_trace_summary(trace: dict[str, Any]) -> str:
    final_output = trace.get("final_output")
    if not isinstance(final_output, dict):
        final_output = {}

    input_payload = trace.get("input")
    if not isinstance(input_payload, dict):
        input_payload = {}

    information_needs = final_output.get("information_needs")
    if not isinstance(information_needs, dict):
        information_needs = {}

    plan_validation = final_output.get("plan_validation")
    if not isinstance(plan_validation, dict):
        plan_validation = {}

    lines = [
        f"Agent run: {trace.get('agent_run_id', 'unknown_agent_run')}",
        f"Trace status: {trace.get('status', 'unknown')}",
        f"Final status: {trace.get('final_status', 'unknown')}",
        f"Input path: {input_payload.get('input_path') or final_output.get('input_path')}",
    ]
    if input_payload.get("script_path") or final_output.get("script_path"):
        lines.append(f"Script path: {input_payload.get('script_path') or final_output.get('script_path')}")
    if final_output.get("module"):
        lines.append(f"Module: {final_output.get('module')}")

    required_context = _string_list(information_needs.get("required_context_types"))
    if required_context:
        lines.append(f"Information needs: {', '.join(required_context)}")
    sources = _source_paths(final_output)
    if sources:
        lines.append(f"Retrieved context: {len(sources)} source(s)")
        lines.extend(f"- {source_path}" for source_path in sources)

    if plan_validation:
        lines.append(f"Plan validation: {plan_validation.get('status')} ({plan_validation.get('reason')})")
    if final_output.get("run_id"):
        lines.append(f"Run: {final_output.get('run_id')} [{final_output.get('run_status')}]")
    if final_output.get("report_draft_path"):
        lines.append(f"Report draft: {final_output.get('report_draft_path')}")
    if final_output.get("pending_approval"):
        pending = final_output["pending_approval"]
        if isinstance(pending, dict):
            lines.append(f"Pending approval: {pending.get('gate')}")

    tool_lines = _tool_call_lines(trace)
    if tool_lines:
        lines.append("Tool calls:")
        lines.extend(f"- {line}" for line in tool_lines)

    approval_lines = _approval_lines(trace)
    if approval_lines:
        lines.append("Approvals:")
        lines.extend(f"- {line}" for line in approval_lines)

    return "\n".join(lines) + "\n"


def render_trace_markdown(trace: dict[str, Any]) -> str:
    summary = render_trace_summary(trace).strip().splitlines()
    if not summary:
        return "# Agent Decision Trace\n"

    heading = summary[0].replace("Agent run: ", "# Agent Decision Trace: ")
    body = ["", "## Summary", *summary[1:]]
    return "\n".join([heading, *body]) + "\n"


def write_decision_trace_markdown(agent_run_id: str) -> Path:
    trace = load_agent_trace(agent_run_id)
    output_path = _relative_trace_path(agent_run_id).with_name("decision_trace.md")
    output_path.write_text(render_trace_markdown(trace), encoding="utf-8")
    return output_path


def render_trace_json(trace: dict[str, Any]) -> str:
    return json.dumps(trace, ensure_ascii=False, indent=2) + "\n"
