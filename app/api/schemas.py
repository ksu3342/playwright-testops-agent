from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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
    input_path: Optional[str] = None
    task_text: Optional[str] = None
    target_url: Optional[str] = None
    module: Optional[str] = None
    constraints: list[str] = Field(default_factory=list)
    approval_mode: Literal["auto", "manual"] = "auto"

    @model_validator(mode="after")
    def require_input_path_or_task_text(self) -> "AgentRunRequest":
        if not self.input_path and not (self.task_text and self.task_text.strip()):
            raise ValueError("Provide either input_path or non-empty task_text.")
        return self


class AgentApprovalRequest(BaseModel):
    gate: Literal["test_plan", "execution", "report"]
    decision: Literal["approved", "rejected"]
    reviewer: Optional[str] = None
    comment: Optional[str] = None


class KbIngestRequest(BaseModel):
    source_type: Literal[
        "product_doc",
        "test_guideline",
        "selector_contract",
        "test_data_contract",
        "run_history",
        "bug_report",
        "note",
    ]
    source_path: Optional[str] = None
    content: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    task: Optional[dict[str, Any]] = None
    module: Optional[str] = None
    script_path: Optional[str] = None
    run_id: Optional[str] = None
    run_dir: Optional[str] = None
    run_status: Optional[str] = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    report_path: Optional[str] = None
    report_draft_path: Optional[str] = None
    report_approved: Optional[bool] = None
    report_exported: Optional[bool] = None
    trace_path: str
    information_needs: Optional[dict[str, Any]] = None
    retrieved_context: Optional[dict[str, Any]] = None
    retrieval_backend: Optional[str] = None
    test_plan: Optional[dict[str, Any]] = None
    planning_strategy: Optional[str] = None
    plan_validation: Optional[dict[str, Any]] = None
    run_summary: Optional[dict[str, Any]] = None
    queried_artifacts: Optional[dict[str, Any]] = None
    checkpoint_mode: Optional[str] = None
    approval_mode: Optional[str] = None
    pending_approval: Optional[dict[str, Any]] = None
    human_approvals: dict[str, Any] = Field(default_factory=dict)
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
    approval_requests: list[dict[str, Any]] = Field(default_factory=list)
    human_approvals: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class AgentRunTraceResponse(AgentRunSummaryResponse):
    tool_calls: list[dict[str, Any]]


class AgentRunListItemResponse(BaseModel):
    agent_run_id: str
    status: str
    final_status: Optional[str] = None
    task: Optional[dict[str, Any]] = None
    module: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    trace_path: str
    report_path: Optional[str] = None
    report_draft_path: Optional[str] = None


class AgentRunListResponse(BaseModel):
    agent_runs: list[AgentRunListItemResponse]


class KbIngestResponse(BaseModel):
    document_id: str
    source_type: str
    source_path: str
    indexed_at: str


class KbSearchResultResponse(BaseModel):
    source_type: str
    source_path: str
    score: int
    excerpt: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KbSearchResponse(BaseModel):
    query: str
    max_results: int
    result_count: int
    results: list[KbSearchResultResponse]
