from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent import tools
from app.agent.status import AgentRunStatus, status_from_plan_validation, status_from_run_result
from app.agent.tracer import AgentRunTracer


ApprovalMode = Literal["auto", "manual"]
ApprovalRoute = Literal["continue", "end"]


class AgentGraphState(TypedDict, total=False):
    input_path: str
    script_path: str
    task: dict[str, Any]
    trace_path: str
    retrieval_backend: str
    planning_backend: str
    approval_mode: ApprovalMode
    approvals: dict[str, Any]
    parse_result: dict[str, Any]
    information_needs: dict[str, Any]
    retrieval_result: dict[str, Any]
    test_plan: dict[str, Any]
    test_plan_path: str
    plan_validation: dict[str, Any]
    generate_result: dict[str, Any]
    run_result: dict[str, Any]
    run_evidence: dict[str, Any]
    report_result: Optional[dict[str, Any]]
    report_approved: Optional[bool]
    report_exported: Optional[bool]
    pending_approval: Optional[dict[str, Any]]
    final_status: str
    final_output: dict[str, Any]


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


def _approval_decision(state: AgentGraphState, gate: str) -> Optional[str]:
    if state.get("approval_mode", "auto") != "manual":
        return "approved"

    approvals = state.get("approvals") or {}
    decision = approvals.get(gate)
    if isinstance(decision, dict):
        value = decision.get("decision")
        return str(value) if value in {"approved", "rejected"} else None
    if decision in {"approved", "rejected"}:
        return str(decision)
    return None


def _approval_summary(state: AgentGraphState) -> dict[str, Any]:
    approvals = state.get("approvals")
    return approvals if isinstance(approvals, dict) else {}


def _pending_payload(state: AgentGraphState, gate: str) -> dict[str, Any]:
    if gate == "test_plan":
        return {
            "test_plan": state.get("test_plan"),
            "plan_validation": state.get("plan_validation"),
        }
    if gate == "execution":
        generate_result = state.get("generate_result") or {}
        return {
            "script_path": generate_result.get("script_path") or state.get("script_path"),
            "generation_mode": generate_result.get("generation_mode"),
            "test_plan": state.get("test_plan"),
            "plan_validation": state.get("plan_validation"),
        }
    if gate == "report":
        report_result = state.get("report_result") or {}
        return {
            "report_path": report_result.get("report_path"),
            "run_result": state.get("run_result"),
        }
    return {}


def _build_final_output(state: AgentGraphState) -> dict[str, Any]:
    generate_result = state.get("generate_result") or {}
    run_result = state.get("run_result") or {}
    run_evidence = state.get("run_evidence") or {}
    report_result = state.get("report_result")
    task = state.get("task") or {}
    test_plan = state.get("test_plan") or {}
    retrieval_result = state.get("retrieval_result") or {}

    report_path = None
    if report_result:
        report_path = report_result.get("report_path")
    if report_path is None:
        report_path = run_result.get("report_path")
    report_draft_path = report_path

    return {
        "input_path": state["input_path"],
        "task": task or None,
        "module": task.get("module") or test_plan.get("feature_name"),
        "script_path": generate_result.get("script_path") or state.get("script_path"),
        "run_id": run_result.get("run_id"),
        "run_dir": run_result.get("run_dir"),
        "run_status": run_result.get("status"),
        "artifact_paths": run_result.get("artifact_paths", {}),
        "report_path": report_path,
        "report_draft_path": report_draft_path,
        "report_approved": state.get("report_approved"),
        "report_exported": state.get("report_exported"),
        "trace_path": state["trace_path"],
        "information_needs": state.get("information_needs"),
        "retrieved_context": _retrieved_context_summary(state.get("retrieval_result")),
        "retrieval_backend": retrieval_result.get("retrieval_backend"),
        "retrieval_implementation": retrieval_result.get("retrieval_implementation"),
        "test_plan": state.get("test_plan"),
        "test_plan_path": state.get("test_plan_path"),
        "planning_strategy": test_plan.get("planning_strategy"),
        "planning_backend": test_plan.get("planning_backend"),
        "planning_implementation": test_plan.get("planning_implementation"),
        "planner_provider": test_plan.get("planner_provider"),
        "plan_validation": state.get("plan_validation"),
        "run_summary": run_evidence.get("run_summary"),
        "queried_artifacts": run_evidence.get("queried_artifacts"),
        "checkpoint_mode": "trace_resume_state",
        "approval_mode": state.get("approval_mode", "auto"),
        "pending_approval": state.get("pending_approval"),
        "human_approvals": _approval_summary(state),
    }


def _route_input(state: AgentGraphState) -> Literal["requirement", "existing_script"]:
    return "existing_script" if state.get("script_path") else "requirement"


def _route_input_node(state: AgentGraphState) -> dict[str, Any]:
    return {}


def _parse_node(tracer: AgentRunTracer):
    def parse_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("parse_result"):
            return {}
        input_path = state["input_path"]
        parse_result = tracer.call_tool(
            "parse_requirement",
            {"input_path": input_path},
            lambda: tools.parse_requirement(input_path),
        )
        return {"parse_result": parse_result}

    return parse_node


def _retrieve_context_node(tracer: AgentRunTracer):
    def retrieve_context_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("retrieval_result"):
            return {}
        input_path = state["input_path"]
        information_needs = state.get("information_needs") or {}
        source_types = information_needs.get("required_context_types")
        if not isinstance(source_types, list):
            source_types = None
        retrieval_query = information_needs.get("retrieval_query")
        if not isinstance(retrieval_query, str):
            retrieval_query = None
        retrieval_backend = str(state.get("retrieval_backend") or "file_lexical")
        retrieval_result = tracer.call_tool(
            "retrieve_testing_context",
            {
                "input_path": input_path,
                "max_results": 5,
                "source_types": source_types,
                "query": retrieval_query,
                "backend": retrieval_backend,
            },
            lambda: tools.retrieve_testing_context(
                input_path,
                max_results=5,
                source_types=source_types,
                query=retrieval_query,
                backend=retrieval_backend,
            ),
        )
        tracer.record_decision(
            "retrieve_context",
            AgentRunStatus.PASSED.value,
            f"Retrieved {retrieval_result.get('result_count', 0)} testing context source(s).",
            "draft_test_plan",
        )
        return {"retrieval_result": retrieval_result}

    return retrieve_context_node


def _analyze_information_needs_node(tracer: AgentRunTracer):
    def analyze_information_needs_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("information_needs"):
            return {}
        input_path = state["input_path"]
        parse_result = state.get("parse_result")
        task = state.get("task")
        information_needs = tracer.call_tool(
            "analyze_information_needs",
            {"input_path": input_path, "task": task or {}},
            lambda: tools.analyze_information_needs(input_path, parse_result=parse_result, task=task),
        )
        return {"information_needs": information_needs}

    return analyze_information_needs_node


def _draft_test_plan_node(tracer: AgentRunTracer):
    def draft_test_plan_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("test_plan"):
            return {}
        input_path = state["input_path"]
        retrieval_result = state.get("retrieval_result")
        information_needs = state.get("information_needs")
        planning_backend = str(state.get("planning_backend") or "deterministic")
        test_plan = tracer.call_tool(
            "draft_test_plan",
            {
                "input_path": input_path,
                "information_needs": information_needs,
                "planning_backend": planning_backend,
            },
            lambda: tools.draft_test_plan(
                input_path,
                testing_context=retrieval_result,
                information_needs=information_needs,
                planning_backend=planning_backend,
            ),
        )
        test_plan_path = tracer.save_test_plan(test_plan)
        tracer.record_decision(
            "draft_test_plan",
            AgentRunStatus.PASSED.value,
            f"Saved reviewable test plan to {test_plan_path}.",
            "validate_test_plan",
        )
        return {"test_plan": test_plan, "test_plan_path": test_plan_path}

    return draft_test_plan_node


def _validate_test_plan_node(tracer: AgentRunTracer):
    def validate_test_plan_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("plan_validation"):
            return {}
        test_plan = state["test_plan"]
        plan_validation = tracer.call_tool(
            "validate_test_plan",
            {"test_plan": test_plan},
            lambda: tools.validate_test_plan(test_plan),
        )
        validation_status = status_from_plan_validation(plan_validation)
        next_action = "test_plan_approval" if validation_status == AgentRunStatus.PASSED else None
        tracer.record_decision(
            "validate_test_plan",
            validation_status.value,
            str(plan_validation.get("reason", "test_plan_validation_completed")),
            next_action,
        )
        return {"plan_validation": plan_validation}

    return validate_test_plan_node


def _prepare_existing_script_node(tracer: AgentRunTracer):
    def prepare_existing_script_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("generate_result"):
            return {}
        script_path = state["script_path"]
        generate_result = tracer.call_tool(
            "prepare_existing_script_execution",
            {"script_path": script_path},
            lambda: tools.prepare_existing_script_execution(script_path),
        )
        tracer.record_decision(
            "prepare_existing_script_execution",
            AgentRunStatus.PASSED.value,
            f"Prepared existing script for controlled execution: {generate_result['script_path']}.",
            "execution_approval",
        )
        return {"generate_result": generate_result, "script_path": generate_result["script_path"]}

    return prepare_existing_script_node


def _test_plan_approval_node(tracer: AgentRunTracer):
    def test_plan_approval_node(state: AgentGraphState) -> dict[str, Any]:
        if state["plan_validation"].get("status") == "blocked":
            final_status = status_from_plan_validation(state["plan_validation"]).value
            tracer.record_decision(
                "test_plan_approval",
                final_status,
                str(state["plan_validation"].get("reason", "test_plan_missing_required_inputs")),
                None,
            )
            next_state = {**state, "final_status": final_status, "pending_approval": None}
            return {"final_status": final_status, "pending_approval": None, "final_output": _build_final_output(next_state)}

        decision = _approval_decision(state, "test_plan")
        if decision == "approved":
            tracer.record_decision(
                "test_plan_approval",
                AgentRunStatus.PASSED.value,
                "Test plan approved or auto approval mode is active.",
                "generate_test_from_plan",
            )
            return {"pending_approval": None}
        if decision == "rejected":
            final_status = AgentRunStatus.BLOCKED_PLAN_NOT_APPROVED.value
            tracer.record_decision(
                "test_plan_approval",
                final_status,
                "Human reviewer rejected the generated test plan.",
                None,
            )
            next_state = {**state, "final_status": final_status, "pending_approval": None}
            return {"final_status": final_status, "pending_approval": None, "final_output": _build_final_output(next_state)}

        request = tracer.request_approval(
            "test_plan",
            "Review generated test plan",
            _pending_payload(state, "test_plan"),
        )
        final_status = AgentRunStatus.WAITING_HUMAN_APPROVAL.value
        tracer.record_decision(
            "test_plan_approval",
            final_status,
            "Human review is required before generation.",
            "approve_or_reject_test_plan",
        )
        next_state = {**state, "final_status": final_status, "pending_approval": request}
        return {
            "final_status": final_status,
            "pending_approval": request,
            "final_output": _build_final_output(next_state),
        }

    return test_plan_approval_node


def _generate_node(tracer: AgentRunTracer):
    def generate_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("generate_result"):
            return {}
        input_path = state["input_path"]
        retrieval_result = state.get("retrieval_result")
        test_plan = state["test_plan"]
        context_sources = _retrieved_context_summary(retrieval_result)["source_paths"]
        generate_result = tracer.call_tool(
            "generate_test_from_plan",
            {
                "input_path": input_path,
                "test_plan_path": state.get("test_plan_path"),
                "test_plan_case_count": len(test_plan.get("test_cases", [])) if isinstance(test_plan, dict) else 0,
                "context_source_paths": context_sources,
            },
            lambda: tools.generate_test_from_plan(input_path, test_plan, testing_context=retrieval_result),
        )
        tracer.record_decision(
            "generate_test_from_plan",
            AgentRunStatus.PASSED.value,
            f"Generated script from approved test plan: {generate_result.get('script_path')}.",
            "execution_approval",
        )
        return {"generate_result": generate_result}

    return generate_node


def _execution_approval_node(tracer: AgentRunTracer):
    def execution_approval_node(state: AgentGraphState) -> dict[str, Any]:
        decision = _approval_decision(state, "execution")
        if decision == "approved":
            tracer.record_decision(
                "execution_approval",
                AgentRunStatus.PASSED.value,
                "Execution approved or auto approval mode is active.",
                "run_test",
            )
            return {"pending_approval": None}
        if decision == "rejected":
            final_status = AgentRunStatus.BLOCKED_PLAN_NOT_APPROVED.value
            tracer.record_decision(
                "execution_approval",
                final_status,
                "Human reviewer rejected test execution.",
                None,
            )
            next_state = {**state, "final_status": final_status, "pending_approval": None}
            return {"final_status": final_status, "pending_approval": None, "final_output": _build_final_output(next_state)}

        request = tracer.request_approval(
            "execution",
            "Approve generated test execution",
            _pending_payload(state, "execution"),
        )
        final_status = AgentRunStatus.WAITING_HUMAN_APPROVAL.value
        tracer.record_decision(
            "execution_approval",
            final_status,
            "Human review is required before executing the script.",
            "approve_or_reject_execution",
        )
        next_state = {**state, "final_status": final_status, "pending_approval": request}
        return {
            "final_status": final_status,
            "pending_approval": request,
            "final_output": _build_final_output(next_state),
        }

    return execution_approval_node


def _run_node(tracer: AgentRunTracer):
    def run_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("run_result"):
            return {}
        script_path = str(state["generate_result"]["script_path"])
        run_result = tracer.call_tool(
            "run_test",
            {"input_path": script_path},
            lambda: tools.run_test(script_path),
        )
        run_status = status_from_run_result(run_result)
        tracer.record_decision(
            "run_test",
            run_status.value,
            str(run_result.get("reason", "run_completed")),
            "collect_run_evidence",
        )
        return {"run_result": run_result}

    return run_node


def _collect_run_evidence_node(tracer: AgentRunTracer):
    def collect_run_evidence_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("run_evidence"):
            return {}
        run_dir = str(state["run_result"]["run_dir"])
        run_evidence = tracer.call_tool(
            "collect_run_evidence",
            {"run_reference": run_dir},
            lambda: tools.collect_run_evidence(run_dir),
        )
        run_status = status_from_run_result(state["run_result"])
        next_action = "create_report" if run_status == AgentRunStatus.FAILED else "finalize"
        tracer.record_decision(
            "collect_run_evidence",
            run_status.value,
            f"Collected run summary and artifact evidence for {Path(run_dir).name}.",
            next_action,
        )
        return {"run_evidence": run_evidence}

    return collect_run_evidence_node


def _report_node(tracer: AgentRunTracer):
    def report_node(state: AgentGraphState) -> dict[str, Any]:
        if state.get("report_result"):
            return {}
        run_dir = str(state["run_result"]["run_dir"])
        report_result = tracer.call_tool(
            "create_report",
            {"input_path": run_dir},
            lambda: tools.create_report(run_dir),
        )
        tracer.record_decision(
            "create_report",
            AgentRunStatus.REPORT_DRAFT_CREATED.value if report_result.get("generated") else AgentRunStatus.FAILED.value,
            str(report_result.get("reason", "report_draft_created")),
            "report_approval",
        )
        return {"report_result": report_result}

    return report_node


def _report_approval_node(tracer: AgentRunTracer):
    def report_approval_node(state: AgentGraphState) -> dict[str, Any]:
        decision = _approval_decision(state, "report")
        if decision == "approved":
            tracer.record_decision(
                "report_approval",
                AgentRunStatus.FAILED.value,
                "Report draft approved or auto approval mode is active.",
                "finalize",
            )
            return {"pending_approval": None, "report_approved": True, "report_exported": True}
        if decision == "rejected":
            final_status = AgentRunStatus.BLOCKED_PLAN_NOT_APPROVED.value
            tracer.record_decision(
                "report_approval",
                final_status,
                "Human reviewer rejected the generated report draft.",
                None,
            )
            next_state = {
                **state,
                "final_status": final_status,
                "pending_approval": None,
                "report_approved": False,
                "report_exported": False,
            }
            return {
                "final_status": final_status,
                "pending_approval": None,
                "report_approved": False,
                "report_exported": False,
                "final_output": _build_final_output(next_state),
            }

        request = tracer.request_approval(
            "report",
            "Review generated defect draft",
            _pending_payload(state, "report"),
        )
        final_status = AgentRunStatus.REPORT_DRAFT_CREATED.value
        tracer.record_decision(
            "report_approval",
            final_status,
            "Report draft was created and requires human review.",
            "approve_or_reject_report",
        )
        next_state = {
            **state,
            "final_status": final_status,
            "pending_approval": request,
            "report_approved": False,
            "report_exported": False,
        }
        return {
            "final_status": final_status,
            "pending_approval": request,
            "report_approved": False,
            "report_exported": False,
            "final_output": _build_final_output(next_state),
        }

    return report_approval_node


def _finalize_node(tracer: AgentRunTracer):
    def finalize_node(state: AgentGraphState) -> dict[str, Any]:
        run_result = state.get("run_result") or {}
        final_status = (
            status_from_run_result(run_result).value
            if run_result
            else str(state.get("final_status", AgentRunStatus.ENVIRONMENT_ERROR.value))
        )
        tracer.record_decision(
            "finalize",
            final_status,
            "Agent run reached a terminal state.",
            None,
        )
        next_state = {**state, "final_status": final_status, "pending_approval": None}
        return {
            "final_status": final_status,
            "pending_approval": None,
            "final_output": _build_final_output(next_state),
        }

    return finalize_node


def _route_after_test_plan_approval(state: AgentGraphState) -> ApprovalRoute:
    return "end" if state.get("final_status") else "continue"


def _route_after_execution_approval(state: AgentGraphState) -> ApprovalRoute:
    return "end" if state.get("final_status") else "continue"


def _route_after_report_approval(state: AgentGraphState) -> ApprovalRoute:
    return "end" if state.get("final_status") else "continue"


def _route_after_run_evidence(state: AgentGraphState) -> Literal["report", "finalize"]:
    if state["run_result"].get("status") == "failed":
        return "report"
    return "finalize"


def build_agent_graph(tracer: AgentRunTracer):
    graph = StateGraph(AgentGraphState)
    graph.add_node("route_input", _route_input_node)
    graph.add_node("parse", _parse_node(tracer))
    graph.add_node("retrieve_context", _retrieve_context_node(tracer))
    graph.add_node("draft_test_plan", _draft_test_plan_node(tracer))
    graph.add_node("validate_test_plan", _validate_test_plan_node(tracer))
    graph.add_node("prepare_existing_script", _prepare_existing_script_node(tracer))
    graph.add_node("test_plan_approval", _test_plan_approval_node(tracer))
    graph.add_node("generate", _generate_node(tracer))
    graph.add_node("execution_approval", _execution_approval_node(tracer))
    graph.add_node("run", _run_node(tracer))
    graph.add_node("collect_run_evidence", _collect_run_evidence_node(tracer))
    graph.add_node("report", _report_node(tracer))
    graph.add_node("report_approval", _report_approval_node(tracer))
    graph.add_node("finalize", _finalize_node(tracer))

    graph.add_edge(START, "route_input")
    graph.add_conditional_edges(
        "route_input",
        _route_input,
        {"requirement": "parse", "existing_script": "prepare_existing_script"},
    )
    graph.add_node("analyze_information_needs", _analyze_information_needs_node(tracer))
    graph.add_edge("parse", "analyze_information_needs")
    graph.add_edge("analyze_information_needs", "retrieve_context")
    graph.add_edge("retrieve_context", "draft_test_plan")
    graph.add_edge("draft_test_plan", "validate_test_plan")
    graph.add_edge("validate_test_plan", "test_plan_approval")
    graph.add_conditional_edges(
        "test_plan_approval",
        _route_after_test_plan_approval,
        {"continue": "generate", "end": END},
    )
    graph.add_edge("prepare_existing_script", "execution_approval")
    graph.add_edge("generate", "execution_approval")
    graph.add_conditional_edges(
        "execution_approval",
        _route_after_execution_approval,
        {"continue": "run", "end": END},
    )
    graph.add_edge("run", "collect_run_evidence")
    graph.add_conditional_edges("collect_run_evidence", _route_after_run_evidence, {"report": "report", "finalize": "finalize"})
    graph.add_edge("report", "report_approval")
    graph.add_conditional_edges(
        "report_approval",
        _route_after_report_approval,
        {"continue": "finalize", "end": END},
    )
    graph.add_edge("finalize", END)
    return graph.compile()


def invoke_agent_graph(
    input_path: str,
    tracer: AgentRunTracer,
    approval_mode: ApprovalMode = "auto",
    approvals: Optional[dict[str, Any]] = None,
    resume_state: Optional[dict[str, Any]] = None,
    task: Optional[dict[str, Any]] = None,
    script_path: Optional[str] = None,
    retrieval_backend: str = "file_lexical",
    planning_backend: str = "deterministic",
) -> AgentGraphState:
    graph = build_agent_graph(tracer)
    initial_state: AgentGraphState = {
        "input_path": input_path,
        "trace_path": tracer.trace["artifact_paths"]["trace"],
        "retrieval_backend": retrieval_backend,
        "planning_backend": planning_backend,
        "approval_mode": approval_mode,
        "approvals": approvals or {},
    }
    if task:
        initial_state["task"] = task
    if script_path:
        initial_state["script_path"] = script_path
    if resume_state:
        initial_state.update(resume_state)
    return graph.invoke(initial_state)
