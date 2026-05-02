from __future__ import annotations

from typing import Any, Optional

from app.agent.graph import ApprovalMode, invoke_agent_graph
from app.agent.tracer import AgentRunTracer


APPROVAL_GATES = {"test_plan", "execution", "report"}
APPROVAL_DECISIONS = {"approved", "rejected"}


def _retrieved_context_summary(retrieval_result: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not retrieval_result:
        return {"result_count": 0, "source_paths": []}

    results = retrieval_result.get("results")
    if not isinstance(results, list):
        return {"result_count": 0, "source_paths": []}

    source_paths = [
        result.get("source_path")
        for result in results
        if isinstance(result, dict) and isinstance(result.get("source_path"), str)
    ]
    return {
        "result_count": int(retrieval_result.get("result_count", len(source_paths))),
        "source_paths": source_paths,
    }


def _build_final_output(
    input_path: str,
    retrieval_result: Optional[dict[str, Any]],
    test_plan: Optional[dict[str, Any]],
    plan_validation: Optional[dict[str, Any]],
    generate_result: Optional[dict[str, Any]],
    run_result: Optional[dict[str, Any]],
    report_result: Optional[dict[str, Any]],
    trace_path: str,
    approval_mode: str,
    pending_approval: Optional[dict[str, Any]],
    approvals: Optional[dict[str, Any]],
) -> dict[str, Any]:
    generate_result = generate_result or {}
    run_result = run_result or {}

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
        "retrieved_context": _retrieved_context_summary(retrieval_result),
        "test_plan": test_plan,
        "plan_validation": plan_validation,
        "approval_mode": approval_mode,
        "pending_approval": pending_approval,
        "human_approvals": approvals or {},
    }


def _resume_state_from_graph_state(graph_state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "parse_result",
        "retrieval_result",
        "test_plan",
        "plan_validation",
        "generate_result",
        "run_result",
        "report_result",
    )
    return {key: graph_state[key] for key in keys if key in graph_state}


def _trace_status_for(final_status: str) -> str:
    if final_status.startswith("waiting_for_"):
        return "waiting_for_approval"
    return "completed"


def _run_with_tracer(
    tracer: AgentRunTracer,
    input_path: str,
    approval_mode: ApprovalMode,
    approvals: Optional[dict[str, Any]] = None,
    resume_state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    trace_path = tracer.trace["artifact_paths"]["trace"]
    approvals = approvals or {}
    tracer.mark_running()

    try:
        graph_state = invoke_agent_graph(
            input_path,
            tracer,
            approval_mode=approval_mode,
            approvals=approvals,
            resume_state=resume_state,
        )
        final_status = str(graph_state.get("final_status", "environment_error"))
        final_output = graph_state.get("final_output")
        if not isinstance(final_output, dict):
            final_output = _build_final_output(
                input_path,
                graph_state.get("retrieval_result"),
                graph_state.get("test_plan"),
                graph_state.get("plan_validation"),
                graph_state.get("generate_result"),
                graph_state.get("run_result"),
                graph_state.get("report_result"),
                trace_path,
                approval_mode,
                graph_state.get("pending_approval"),
                approvals,
            )

        resume_state_payload = _resume_state_from_graph_state(graph_state)
        tracer.finalize(
            final_status=final_status,
            final_output=final_output,
            trace_status=_trace_status_for(final_status),
            resume_state=resume_state_payload,
        )
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


def run_agent_task(
    input_path: str,
    agent_run_id: Optional[str] = None,
    approval_mode: ApprovalMode = "auto",
) -> dict[str, Any]:
    tracer = AgentRunTracer.create(
        {"input_path": input_path, "approval_mode": approval_mode},
        agent_run_id=agent_run_id,
    )
    return _run_with_tracer(tracer, input_path, approval_mode=approval_mode)


def continue_agent_run(
    agent_run_id: str,
    gate: str,
    decision: str,
    reviewer: Optional[str] = None,
    comment: Optional[str] = None,
) -> dict[str, Any]:
    if gate not in APPROVAL_GATES:
        raise ValueError(f"Unknown approval gate: {gate}")
    if decision not in APPROVAL_DECISIONS:
        raise ValueError("Approval decision must be either 'approved' or 'rejected'.")

    tracer = AgentRunTracer.resume(agent_run_id)
    if tracer.trace.get("status") != "waiting_for_approval":
        raise ValueError(f"Agent run '{agent_run_id}' is not waiting for approval.")

    final_output = tracer.trace.get("final_output")
    if not isinstance(final_output, dict):
        raise ValueError(f"Agent run '{agent_run_id}' does not have a resumable final output.")

    pending_approval = final_output.get("pending_approval")
    if not isinstance(pending_approval, dict) or pending_approval.get("gate") != gate:
        raise ValueError(f"Agent run '{agent_run_id}' is not waiting for gate '{gate}'.")

    input_payload = tracer.trace.get("input")
    if not isinstance(input_payload, dict) or not isinstance(input_payload.get("input_path"), str):
        raise ValueError(f"Agent run '{agent_run_id}' trace does not contain input_path.")

    tracer.record_approval_decision(gate, decision, reviewer=reviewer, comment=comment)

    approvals = tracer.trace.get("human_approvals")
    if not isinstance(approvals, dict):
        approvals = {}

    resume_state = tracer.trace.get("resume_state")
    if not isinstance(resume_state, dict):
        resume_state = {}

    return _run_with_tracer(
        tracer,
        str(input_payload["input_path"]),
        approval_mode="manual",
        approvals=approvals,
        resume_state=resume_state,
    )
