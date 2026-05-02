from __future__ import annotations

from typing import Any, Optional

from app.agent.graph import invoke_agent_graph
from app.agent.tracer import AgentRunTracer


def _build_final_output(
    input_path: str,
    generate_result: dict[str, Any],
    run_result: dict[str, Any],
    report_result: Optional[dict[str, Any]],
    trace_path: str,
) -> dict[str, Any]:
    report_path = None
    if report_result:
        report_path = report_result.get("report_path")
    if report_path is None:
        report_path = run_result.get("report_path")

    return {
        "input_path": input_path,
        "script_path": generate_result.get("script_path"),
        "run_id": run_result.get("run_id"),
        "run_dir": run_result.get("run_dir"),
        "run_status": run_result.get("status"),
        "artifact_paths": run_result.get("artifact_paths", {}),
        "report_path": report_path,
        "trace_path": trace_path,
    }


def run_agent_task(input_path: str, agent_run_id: Optional[str] = None) -> dict[str, Any]:
    tracer = AgentRunTracer.create({"input_path": input_path}, agent_run_id=agent_run_id)
    trace_path = tracer.trace["artifact_paths"]["trace"]

    try:
        graph_state = invoke_agent_graph(input_path, tracer)
        final_status = str(graph_state.get("final_status", "environment_error"))
        final_output = graph_state.get("final_output")
        if not isinstance(final_output, dict):
            final_output = _build_final_output(
                input_path,
                graph_state["generate_result"],
                graph_state["run_result"],
                graph_state.get("report_result"),
                trace_path,
            )
        tracer.finalize(final_status=final_status, final_output=final_output)
        return {
            "agent_run_id": tracer.agent_run_id,
            "final_status": final_status,
            **final_output,
        }
    except Exception as exc:
        tracer.finalize(final_status="environment_error", error=exc)
        return {
            "agent_run_id": tracer.agent_run_id,
            "final_status": "environment_error",
            "trace_path": trace_path,
            "error": str(exc),
        }
