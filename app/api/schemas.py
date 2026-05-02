from typing import Any, Optional

from pydantic import BaseModel, Field


class TextInputRequest(BaseModel):
    input_path: Optional[str] = None
    content: Optional[str] = None
    filename: Optional[str] = None


class NormalizeRequest(TextInputRequest):
    provider: Optional[str] = None


class RunRequest(BaseModel):
    input_path: str


class ReportRequest(BaseModel):
    input_path: str


class AgentRunRequest(BaseModel):
    input_path: str


class HealthResponse(BaseModel):
    status: str


class PRDDocumentResponse(BaseModel):
    title: Optional[str]
    feature_name: Optional[str]
    page_url: Optional[str]
    preconditions: list[str]
    user_actions: list[str]
    expected_results: list[str]
    raw_text: str
    missing_sections: list[str]


class TestPointResponse(BaseModel):
    id: str
    title: str
    type: str
    preconditions: list[str]
    steps: list[str]
    expected_result: str
    source_sections: list[str]
    rationale: str


class NormalizeResponse(BaseModel):
    resolved_input_path: str
    output_path: str
    provider_used: str
    parser_validation_passed: bool
    missing_sections: list[str]
    normalized_markdown: str


class ParseResponse(BaseModel):
    resolved_input_path: str
    document: PRDDocumentResponse


class GenerateResponse(BaseModel):
    resolved_input_path: str
    document: PRDDocumentResponse
    test_points: list[TestPointResponse]
    script_path: str


class RunResponse(BaseModel):
    run_id: str
    target_script: str
    status: str
    reason: str
    command: str
    start_time: str
    end_time: str
    duration_seconds: float
    return_code: Optional[int]
    execution_readiness: str
    notes: list[str]
    artifact_paths: dict[str, str]
    run_dir: str
    lineage: Optional[dict[str, Optional[str]]] = None
    report_path: Optional[str] = None


class ReportResponse(BaseModel):
    generated: bool
    report_path: Optional[str]
    run_dir: str
    run_id: str
    status: str
    target_script: str
    reason: str


class RunListResponse(BaseModel):
    runs: list[RunResponse]


class RunArtifactsResponse(BaseModel):
    run_id: str
    run_dir: str
    artifact_paths: dict[str, str]
    lineage: Optional[dict[str, Optional[str]]] = None
    report_path: Optional[str] = None


class AgentRunResponse(BaseModel):
    agent_run_id: str
    final_status: str
    input_path: Optional[str] = None
    script_path: Optional[str] = None
    run_id: Optional[str] = None
    run_dir: Optional[str] = None
    run_status: Optional[str] = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    report_path: Optional[str] = None
    trace_path: str
    error: Optional[str] = None


class AgentRunSummaryResponse(BaseModel):
    agent_run_id: str
    status: str
    final_status: Optional[str] = None
    input: dict[str, Any]
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    final_output: Optional[dict[str, Any]] = None
    artifact_paths: dict[str, str]
    error: Optional[str] = None


class AgentRunTraceResponse(AgentRunSummaryResponse):
    tool_calls: list[dict[str, Any]]
