from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from json import JSONDecodeError
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import ValidationError

from app.agent.orchestrator import continue_agent_run, run_agent_task
from app.agent.tracer import AGENT_RUNS_DIR
from app.api.schemas import (
    AgentRunRequest,
    AgentRunListResponse,
    AgentRunResponse,
    AgentRunSummaryResponse,
    AgentRunTraceResponse,
    AgentApprovalRequest,
    GenerateResponse,
    HealthResponse,
    KbIngestRequest,
    KbIngestResponse,
    KbSearchResponse,
    NormalizeRequest,
    NormalizeResponse,
    ParseResponse,
    ReportRequest,
    ReportResponse,
    RunArtifactsResponse,
    RunListResponse,
    RunRequest,
    RunResponse,
    TestPointResponse,
    TextInputRequest,
)
from app.core.collector import REPO_ROOT, RUNS_DIR
from app.core.extractor import extract_test_points
from app.core.generator import generate_test_script
from app.core.normalizer import NormalizationError, normalize_requirement_file
from app.core.parser import parse_prd
from app.core.reporter import create_bug_report_from_run
from app.core.runner import run_test_script
from app.rag.ingest import ingest_document
from app.rag.retriever import retrieve_testing_context, validate_retrieval_backend


API_INPUTS_DIR = REPO_ROOT / "data" / "api_inputs"

app = FastAPI(
    title="Playwright TestOps Agent API",
    version="0.2.0",
    description="Thin FastAPI wrapper around the CLI-first TestOps Agent core pipeline.",
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "input"


def _relative_to_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _write_inline_input(content: str, filename: str | None, prefix: str, default_suffix: str) -> Path:
    safe_name = Path(filename or f"{prefix}{default_suffix}").name
    safe_stem = _slugify(Path(safe_name).stem or prefix)
    suffix = Path(safe_name).suffix or default_suffix
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    API_INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = API_INPUTS_DIR / f"{timestamp}_{safe_stem}{suffix}"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _format_agent_task_markdown(request: AgentRunRequest) -> str:
    task_text = (request.task_text or "").strip()
    module = (request.module or "").strip()
    title = module or "Agent Test Task"
    target_url = (request.target_url or "").strip()
    constraints = [constraint.strip() for constraint in request.constraints if constraint and constraint.strip()]

    preconditions = ["Task submitted through Agent API"]
    if constraints:
        preconditions.extend(constraints)

    lines = [
        "# Title",
        f"{title} PRD",
        "",
        "## Feature Name",
        module or task_text.splitlines()[0][:80] or "Agent Test Task",
        "",
        "## Page URL",
    ]
    if target_url:
        lines.append(target_url)
    lines.extend(
        [
            "",
            "## Preconditions",
            *[f"- {item}" for item in preconditions],
            "",
            "## User Actions",
            f"1. {task_text}",
            "",
            "## Expected Results",
            "- The described behavior can be verified against the target page.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _resolve_agent_run_input(request: AgentRunRequest) -> tuple[str, dict[str, object]]:
    task_payload: dict[str, object] = {}
    if request.task_text and request.task_text.strip():
        task_payload["task_text"] = request.task_text.strip()
    if request.target_url:
        task_payload["target_url"] = request.target_url
    if request.module:
        task_payload["module"] = request.module
    if request.constraints:
        task_payload["constraints"] = request.constraints

    if request.input_path:
        return request.input_path, task_payload

    output_path = _write_inline_input(
        _format_agent_task_markdown(request),
        "agent_task.md",
        prefix="agent_task",
        default_suffix=".md",
    )
    task_payload["generated_input_path"] = _relative_to_repo(output_path)
    return _relative_to_repo(output_path), task_payload


def _resolve_text_input(request: TextInputRequest, prefix: str, default_suffix: str = ".md") -> str:
    if request.input_path:
        return request.input_path

    if request.content and request.content.strip():
        output_path = _write_inline_input(request.content, request.filename, prefix, default_suffix)
        return _relative_to_repo(output_path)

    raise HTTPException(status_code=400, detail="Provide either input_path or non-empty content.")


def _raise_bad_request(exc: Exception) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_run_dir(run_id: str) -> Path:
    run_dir = (RUNS_DIR / run_id).resolve()
    if run_dir.parent != RUNS_DIR.resolve() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' was not found.")
    return run_dir


def _load_run_summary_payload(run_id: str) -> dict[str, object]:
    run_dir = _resolve_run_dir(run_id)
    summary_path = run_dir / "summary.json"

    if not summary_path.is_file():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' does not have a summary.json artifact.")

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Run '{run_id}' summary could not be read.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail=f"Run '{run_id}' summary is invalid.")

    artifact_paths = payload.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        artifact_paths = {}

    normalized_artifact_paths = {str(key): str(value) for key, value in artifact_paths.items()}
    normalized_artifact_paths.setdefault("run_dir", _relative_to_repo(run_dir))
    normalized_artifact_paths.setdefault("summary", _relative_to_repo(summary_path))

    payload["artifact_paths"] = normalized_artifact_paths
    payload["run_dir"] = normalized_artifact_paths["run_dir"]
    return payload


def _load_run_response(run_id: str) -> RunResponse:
    payload = _load_run_summary_payload(run_id)

    try:
        return RunResponse(**payload)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Run '{run_id}' summary is missing required fields.") from exc


def _resolve_agent_trace_path(agent_run_id: str) -> Path:
    agent_run_dir = (AGENT_RUNS_DIR / agent_run_id).resolve()
    agent_runs_root = AGENT_RUNS_DIR.resolve()
    trace_path = agent_run_dir / "trace.json"

    if agent_run_dir.parent != agent_runs_root or not trace_path.is_file():
        raise HTTPException(status_code=404, detail=f"Agent run '{agent_run_id}' was not found.")

    return trace_path


def _load_agent_trace_payload(agent_run_id: str) -> dict[str, object]:
    trace_path = _resolve_agent_trace_path(agent_run_id)
    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except (JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Agent run '{agent_run_id}' trace could not be read.") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail=f"Agent run '{agent_run_id}' trace is invalid.")

    return payload


def _agent_artifact_paths(payload: dict[str, object]) -> dict[str, str]:
    artifact_paths = payload.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        return {}
    return {str(key): str(value) for key, value in artifact_paths.items()}


def _agent_summary_payload(payload: dict[str, object]) -> dict[str, object]:
    input_payload = payload.get("input")
    if not isinstance(input_payload, dict):
        input_payload = {}

    final_output = payload.get("final_output")
    if final_output is not None and not isinstance(final_output, dict):
        final_output = {"value": str(final_output)}

    approval_requests = payload.get("approval_requests")
    if not isinstance(approval_requests, list):
        approval_requests = []

    human_approvals = payload.get("human_approvals")
    if not isinstance(human_approvals, dict):
        human_approvals = {}

    return {
        "agent_run_id": str(payload.get("agent_run_id", "unknown_agent_run")),
        "status": str(payload.get("status", "unknown")),
        "final_status": payload.get("final_status"),
        "input": input_payload,
        "start_time": str(payload.get("start_time", "")),
        "end_time": payload.get("end_time"),
        "duration_seconds": payload.get("duration_seconds"),
        "final_output": final_output,
        "artifact_paths": _agent_artifact_paths(payload),
        "approval_requests": approval_requests,
        "human_approvals": human_approvals,
        "error": payload.get("error"),
    }


def _agent_run_list_item(payload: dict[str, object]) -> dict[str, object]:
    input_payload = payload.get("input")
    if not isinstance(input_payload, dict):
        input_payload = {}
    task = input_payload.get("task")
    if not isinstance(task, dict):
        task = None

    final_output = payload.get("final_output")
    if not isinstance(final_output, dict):
        final_output = {}

    artifact_paths = _agent_artifact_paths(payload)
    return {
        "agent_run_id": str(payload.get("agent_run_id", "unknown_agent_run")),
        "status": str(payload.get("status", "unknown")),
        "final_status": payload.get("final_status"),
        "task": task,
        "module": (task or {}).get("module") or final_output.get("module"),
        "start_time": str(payload.get("start_time", "")),
        "end_time": payload.get("end_time"),
        "trace_path": artifact_paths.get("trace", ""),
        "report_path": final_output.get("report_path"),
        "report_draft_path": final_output.get("report_draft_path"),
    }


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/v1/runs", response_model=RunListResponse)
def list_runs() -> RunListResponse:
    runs = []
    for run_dir in sorted(RUNS_DIR.iterdir(), key=lambda path: path.name, reverse=True):
        if not run_dir.is_dir() or not (run_dir / "summary.json").is_file():
            continue
        try:
            runs.append(_load_run_response(run_dir.name))
        except HTTPException as exc:
            if exc.status_code >= 500:
                continue
            raise

    return RunListResponse(runs=runs)


@app.get("/api/v1/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    return _load_run_response(run_id)


@app.get("/api/v1/runs/{run_id}/artifacts", response_model=RunArtifactsResponse)
def get_run_artifacts(run_id: str) -> RunArtifactsResponse:
    payload = _load_run_summary_payload(run_id)
    lineage = payload.get("lineage")
    if not isinstance(lineage, dict):
        lineage = None
    return RunArtifactsResponse(
        run_id=str(payload["run_id"]),
        run_dir=str(payload["run_dir"]),
        artifact_paths={key: str(value) for key, value in dict(payload["artifact_paths"]).items()},
        lineage=lineage,
        report_path=payload.get("report_path"),
    )


@app.post("/api/v1/agent-runs", response_model=AgentRunResponse)
def create_agent_run(request: AgentRunRequest) -> AgentRunResponse:
    input_path, task = _resolve_agent_run_input(request)
    try:
        retrieval_backend = validate_retrieval_backend(request.retrieval_backend)
    except ValueError as exc:
        _raise_bad_request(exc)
    result = run_agent_task(
        input_path,
        approval_mode=request.approval_mode,
        task=task or None,
        retrieval_backend=retrieval_backend,
    )
    return AgentRunResponse(**result)


@app.get("/api/v1/agent-runs", response_model=AgentRunListResponse)
def list_agent_runs(
    status: Optional[str] = None,
    final_status: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
) -> AgentRunListResponse:
    items: list[dict[str, object]] = []
    if not AGENT_RUNS_DIR.is_dir():
        return AgentRunListResponse(agent_runs=[])

    trace_paths = sorted(
        AGENT_RUNS_DIR.glob("*/trace.json"),
        key=lambda path: (path.stat().st_mtime, path.as_posix()),
        reverse=True,
    )
    for trace_path in trace_paths:
        if len(items) >= limit:
            break
        try:
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
        except (JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue

        item = _agent_run_list_item(payload)
        if status and item["status"] != status:
            continue
        if final_status and item.get("final_status") != final_status:
            continue
        if module and item.get("module") != module:
            continue
        items.append(item)

    return AgentRunListResponse(agent_runs=items)


def _continue_agent_run_response(agent_run_id: str, request: AgentApprovalRequest) -> AgentRunResponse:
    try:
        result = continue_agent_run(
            agent_run_id,
            gate=request.gate,
            decision=request.decision,
            reviewer=request.reviewer,
            comment=request.comment,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AgentRunResponse(**result)


@app.post("/api/v1/agent-runs/{agent_run_id}/approvals", response_model=AgentRunResponse)
def approve_agent_run(agent_run_id: str, request: AgentApprovalRequest) -> AgentRunResponse:
    return _continue_agent_run_response(agent_run_id, request)


@app.post("/api/v1/agent-runs/{agent_run_id}/approve", response_model=AgentRunResponse)
def approve_agent_run_alias(agent_run_id: str, request: AgentApprovalRequest) -> AgentRunResponse:
    return _continue_agent_run_response(agent_run_id, request)


@app.get("/api/v1/agent-runs/{agent_run_id}", response_model=AgentRunSummaryResponse)
def get_agent_run(agent_run_id: str) -> AgentRunSummaryResponse:
    payload = _load_agent_trace_payload(agent_run_id)
    try:
        return AgentRunSummaryResponse(**_agent_summary_payload(payload))
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Agent run '{agent_run_id}' trace is missing required fields.") from exc


@app.get("/api/v1/agent-runs/{agent_run_id}/trace", response_model=AgentRunTraceResponse)
def get_agent_run_trace(agent_run_id: str) -> AgentRunTraceResponse:
    payload = _load_agent_trace_payload(agent_run_id)
    trace_payload = _agent_summary_payload(payload)
    tool_calls = payload.get("tool_calls")
    if not isinstance(tool_calls, list):
        raise HTTPException(status_code=500, detail=f"Agent run '{agent_run_id}' trace is missing tool calls.")
    trace_payload["tool_calls"] = tool_calls

    try:
        return AgentRunTraceResponse(**trace_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail=f"Agent run '{agent_run_id}' trace is missing required fields.") from exc


@app.post("/api/v1/kb/ingest", response_model=KbIngestResponse)
def ingest_kb_document(request: KbIngestRequest) -> KbIngestResponse:
    try:
        result = ingest_document(
            source_type=request.source_type,
            source_path=request.source_path,
            content=request.content,
            metadata=request.metadata,
        )
    except (FileNotFoundError, JSONDecodeError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KbIngestResponse(**result)


@app.get("/api/v1/kb/search", response_model=KbSearchResponse)
def search_kb(
    query: str = Query(..., min_length=1),
    max_results: int = Query(5, ge=1, le=20),
    backend: str = Query("file_lexical"),
) -> KbSearchResponse:
    try:
        result = retrieve_testing_context(query=query, max_results=max_results, backend=backend)
    except ValueError as exc:
        _raise_bad_request(exc)
    items = [
        {
            "source_type": item["source_type"],
            "source_path": item["source_path"],
            "score": item["score"],
            "excerpt": item["excerpt"],
            "metadata": item.get("metadata", {}),
        }
        for item in result["results"]
    ]
    return KbSearchResponse(
        query=query,
        max_results=max_results,
        retrieval_backend=str(result["retrieval_backend"]),
        retrieval_implementation=str(result["retrieval_implementation"]),
        result_count=int(result["result_count"]),
        results=items,
    )


@app.post("/api/v1/normalize", response_model=NormalizeResponse)
def normalize(request: NormalizeRequest) -> NormalizeResponse:
    resolved_input_path = _resolve_text_input(request, prefix="normalize")

    try:
        result = normalize_requirement_file(resolved_input_path, provider_name=request.provider)
    except (NormalizationError, FileNotFoundError, OSError, ValueError) as exc:
        _raise_bad_request(exc)

    return NormalizeResponse(
        resolved_input_path=resolved_input_path,
        output_path=_relative_to_repo(result.output_path),
        provider_used=result.provider_name,
        parser_validation_passed=result.parser_validation_passed,
        missing_sections=result.missing_sections,
        normalized_markdown=result.normalized_markdown,
    )


@app.post("/api/v1/parse", response_model=ParseResponse)
def parse(request: TextInputRequest) -> ParseResponse:
    resolved_input_path = _resolve_text_input(request, prefix="parse")

    try:
        document = parse_prd(resolved_input_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _raise_bad_request(exc)

    return ParseResponse(
        resolved_input_path=resolved_input_path,
        document=asdict(document),
    )


@app.post("/api/v1/generate", response_model=GenerateResponse)
def generate(request: TextInputRequest) -> GenerateResponse:
    resolved_input_path = _resolve_text_input(request, prefix="generate")

    try:
        document = parse_prd(resolved_input_path)
        test_points = extract_test_points(document)
        script_path = generate_test_script(document, test_points, input_path=resolved_input_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _raise_bad_request(exc)

    return GenerateResponse(
        resolved_input_path=resolved_input_path,
        document=asdict(document),
        test_points=[TestPointResponse(**asdict(test_point)) for test_point in test_points],
        script_path=script_path.as_posix(),
    )


@app.post("/api/v1/run", response_model=RunResponse)
def run(request: RunRequest) -> RunResponse:
    result = run_test_script(request.input_path)
    return RunResponse(**result)


@app.post("/api/v1/report", response_model=ReportResponse)
def report(request: ReportRequest) -> ReportResponse:
    result = create_bug_report_from_run(request.input_path)
    return ReportResponse(**result)
