from __future__ import annotations

from typing import Any, Optional

from app.agent import tools
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
        tracer.call_tool(
            "parse_requirement",
            {"input_path": input_path},
            lambda: tools.parse_requirement(input_path),
        )
        generate_result = tracer.call_tool(
            "generate_test",
            {"input_path": input_path},
            lambda: tools.generate_test(input_path),
        )
        script_path = str(generate_result["script_path"])
        run_result = tracer.call_tool(
            "run_test",
            {"input_path": script_path},
            lambda: tools.run_test(script_path),
        )

        report_result = None
        if run_result.get("status") == "failed":
            report_result = tracer.call_tool(
                "create_report",
                {"input_path": run_result["run_dir"]},
                lambda: tools.create_report(str(run_result["run_dir"])),
            )

        final_status = str(run_result.get("status", "environment_error"))
        final_output = _build_final_output(input_path, generate_result, run_result, report_result, trace_path)
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
