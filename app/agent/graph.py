from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent import tools
from app.agent.tracer import AgentRunTracer


class AgentGraphState(TypedDict, total=False):
    input_path: str
    trace_path: str
    parse_result: dict[str, Any]
    retrieval_result: dict[str, Any]
    generate_result: dict[str, Any]
    run_result: dict[str, Any]
    report_result: Optional[dict[str, Any]]
    final_status: str
    final_output: dict[str, Any]


def _build_final_output(state: AgentGraphState) -> dict[str, Any]:
    input_path = state["input_path"]
    generate_result = state["generate_result"]
    run_result = state["run_result"]
    report_result = state.get("report_result")
    trace_path = state["trace_path"]

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
        "retrieved_context": _retrieved_context_summary(state.get("retrieval_result")),
    }


def _parse_node(tracer: AgentRunTracer):
    def parse_node(state: AgentGraphState) -> dict[str, Any]:
        input_path = state["input_path"]
        parse_result = tracer.call_tool(
            "parse_requirement",
            {"input_path": input_path},
            lambda: tools.parse_requirement(input_path),
        )
        return {"parse_result": parse_result}

    return parse_node


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


def _retrieve_context_node(tracer: AgentRunTracer):
    def retrieve_context_node(state: AgentGraphState) -> dict[str, Any]:
        input_path = state["input_path"]
        retrieval_result = tracer.call_tool(
            "retrieve_testing_context",
            {"input_path": input_path, "max_results": 5},
            lambda: tools.retrieve_testing_context(input_path, max_results=5),
        )
        return {"retrieval_result": retrieval_result}

    return retrieve_context_node


def _generate_node(tracer: AgentRunTracer):
    def generate_node(state: AgentGraphState) -> dict[str, Any]:
        input_path = state["input_path"]
        retrieval_result = state.get("retrieval_result")
        context_sources = _retrieved_context_summary(retrieval_result)["source_paths"]
        generate_result = tracer.call_tool(
            "generate_test",
            {"input_path": input_path, "context_source_paths": context_sources},
            lambda: tools.generate_test(input_path, testing_context=retrieval_result),
        )
        return {"generate_result": generate_result}

    return generate_node


def _run_node(tracer: AgentRunTracer):
    def run_node(state: AgentGraphState) -> dict[str, Any]:
        script_path = str(state["generate_result"]["script_path"])
        run_result = tracer.call_tool(
            "run_test",
            {"input_path": script_path},
            lambda: tools.run_test(script_path),
        )
        return {"run_result": run_result}

    return run_node


def _report_node(tracer: AgentRunTracer):
    def report_node(state: AgentGraphState) -> dict[str, Any]:
        run_dir = str(state["run_result"]["run_dir"])
        report_result = tracer.call_tool(
            "create_report",
            {"input_path": run_dir},
            lambda: tools.create_report(run_dir),
        )
        return {"report_result": report_result}

    return report_node


def _finalize_node(state: AgentGraphState) -> dict[str, Any]:
    run_result = state["run_result"]
    final_status = str(run_result.get("status", "environment_error"))
    return {
        "final_status": final_status,
        "final_output": _build_final_output(state),
    }


def _route_after_run(state: AgentGraphState) -> Literal["report", "finalize"]:
    if state["run_result"].get("status") == "failed":
        return "report"
    return "finalize"


def build_agent_graph(tracer: AgentRunTracer):
    graph = StateGraph(AgentGraphState)
    graph.add_node("parse", _parse_node(tracer))
    graph.add_node("retrieve_context", _retrieve_context_node(tracer))
    graph.add_node("generate", _generate_node(tracer))
    graph.add_node("run", _run_node(tracer))
    graph.add_node("report", _report_node(tracer))
    graph.add_node("finalize", _finalize_node)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "retrieve_context")
    graph.add_edge("retrieve_context", "generate")
    graph.add_edge("generate", "run")
    graph.add_conditional_edges("run", _route_after_run, {"report": "report", "finalize": "finalize"})
    graph.add_edge("report", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def invoke_agent_graph(input_path: str, tracer: AgentRunTracer) -> AgentGraphState:
    graph = build_agent_graph(tracer)
    return graph.invoke(
        {
            "input_path": input_path,
            "trace_path": tracer.trace["artifact_paths"]["trace"],
        }
    )
