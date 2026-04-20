from typing import Optional

from pydantic import BaseModel


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
