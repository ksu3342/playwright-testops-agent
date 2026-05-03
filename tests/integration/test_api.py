from pathlib import Path
import shutil
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.collector import RUNS_DIR


client = TestClient(app)


AGENT_SUCCESS_TOOL_SEQUENCE = [
    "parse_requirement",
    "analyze_information_needs",
    "retrieve_testing_context",
    "draft_test_plan",
    "validate_test_plan",
    "generate_test_from_plan",
    "run_test",
    "collect_run_evidence",
]

AGENT_EXISTING_SCRIPT_FAILED_TOOL_SEQUENCE = [
    "prepare_existing_script_execution",
    "run_test",
    "collect_run_evidence",
    "create_report",
]


def _create_run(input_path: str) -> dict[str, object]:
    response = client.post("/api/v1/run", json={"input_path": input_path})

    assert response.status_code == 200
    return response.json()


def _create_agent_run(input_path: str) -> dict[str, object]:
    response = client.post("/api/v1/agent-runs", json={"input_path": input_path})

    assert response.status_code == 200
    return response.json()


def _create_manual_agent_run(
    input_path: str,
    retrieval_backend: str = "file_lexical",
    planning_backend: str = "deterministic",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/agent-runs",
        json={
            "input_path": input_path,
            "approval_mode": "manual",
            "retrieval_backend": retrieval_backend,
            "planning_backend": planning_backend,
        },
    )

    assert response.status_code == 200
    return response.json()


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_kb_ingest_then_search_api_returns_indexed_document() -> None:
    unique_token = f"p5apisearch{uuid4().hex}"

    ingest_response = client.post(
        "/api/v1/kb/ingest",
        json={
            "source_type": "note",
            "content": f"{unique_token} should be retrievable through the KB search API.",
            "metadata": {"test": "integration"},
        },
    )
    ingest_payload = ingest_response.json()

    assert ingest_response.status_code == 200
    assert ingest_payload["document_id"].startswith("kb_")
    assert ingest_payload["source_type"] == "note"
    assert ingest_payload["source_path"].startswith("data/kb/uploaded/")
    assert ingest_payload["indexed_at"]

    search_response = client.get(
        "/api/v1/kb/search",
        params={"query": unique_token, "max_results": 5},
    )
    search_payload = search_response.json()

    assert search_response.status_code == 200
    assert search_payload["query"] == unique_token
    assert search_payload["max_results"] == 5
    assert search_payload["retrieval_backend"] == "file_lexical"
    assert search_payload["retrieval_implementation"] == "deterministic_file_lexical"
    assert search_payload["result_count"] >= 1
    assert any(item["source_path"] == ingest_payload["source_path"] for item in search_payload["results"])


def test_kb_search_api_supports_langchain_local_backend() -> None:
    response = client.get(
        "/api/v1/kb/search",
        params={"query": "login selectors fixture data", "max_results": 5, "backend": "langchain_local"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["retrieval_backend"] == "langchain_local"
    assert payload["retrieval_implementation"] == "langchain_local_documents"
    assert payload["result_count"] >= 2
    source_paths = [item["source_path"] for item in payload["results"]]
    assert "data/contracts/demo_app_selectors.json" in source_paths
    assert "data/contracts/demo_app_test_data.json" in source_paths


def test_kb_search_api_rejects_invalid_backend() -> None:
    response = client.get(
        "/api/v1/kb/search",
        params={"query": "login", "backend": "not_a_backend"},
    )

    assert response.status_code == 400
    assert "Unsupported retrieval backend" in response.json()["detail"]


def test_normalize_endpoint_accepts_inline_content() -> None:
    source_content = Path("data/inputs/free_text_login_notes.md").read_text(encoding="utf-8")

    response = client.post(
        "/api/v1/normalize",
        json={
            "content": source_content,
            "filename": "free_text_login_notes.md",
            "provider": "mock",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["provider_used"] == "mock"
    assert payload["parser_validation_passed"] is True
    assert payload["resolved_input_path"].startswith("data/api_inputs/")
    assert payload["output_path"].startswith("data/normalized/")


def test_generate_then_run_endpoint_preserves_blocked_status() -> None:
    source_content = Path("data/inputs/sample_prd_search.md").read_text(encoding="utf-8")

    generate_response = client.post(
        "/api/v1/generate",
        json={
            "content": source_content,
            "filename": "sample_prd_search.md",
        },
    )
    generate_payload = generate_response.json()

    assert generate_response.status_code == 200
    assert len(generate_payload["test_points"]) == 2
    script_content = Path(generate_payload["script_path"]).read_text(encoding="utf-8")
    assert '# selector-contract: search.input -> search-input' in script_content
    assert "Locate the relevant input selector" not in script_content

    run_response = client.post(
        "/api/v1/run",
        json={"input_path": generate_payload["script_path"]},
    )
    run_payload = run_response.json()

    assert run_response.status_code == 200
    assert run_payload["status"] == "blocked"
    assert "incomplete" in run_payload["reason"].lower()


def test_generate_then_run_endpoint_passes_executable_login_script() -> None:
    source_content = Path("data/inputs/sample_prd_login.md").read_text(encoding="utf-8")

    generate_response = client.post(
        "/api/v1/generate",
        json={
            "content": source_content,
            "filename": "sample_prd_login.md",
        },
    )
    generate_payload = generate_response.json()

    assert generate_response.status_code == 200
    assert len(generate_payload["test_points"]) == 1
    script_content = Path(generate_payload["script_path"]).read_text(encoding="utf-8")
    assert '# selector-contract: login.email_input -> login-email-input' in script_content
    assert '# test-fixture: login.valid_email -> demo@example.com' in script_content
    assert "import uvicorn" in script_content
    assert "from demo_app.main import app" in script_content
    assert "threading.Thread(target=server.run, daemon=True)" in script_content
    assert "server.should_exit = True" in script_content
    assert "subprocess.Popen" not in script_content
    assert "DEMO_SERVER_COMMAND" not in script_content
    assert "REUSE_EXISTING_DEMO_SERVER" not in script_content
    assert "TODO" not in script_content

    run_response = client.post(
        "/api/v1/run",
        json={"input_path": generate_payload["script_path"]},
    )
    run_payload = run_response.json()

    assert run_response.status_code == 200
    assert run_payload["status"] == "passed"


def test_generated_login_run_lineage_and_artifacts_accessible_via_api() -> None:
    # Use input_path directly to get fixed source_requirement path
    generate_response = client.post(
        "/api/v1/generate",
        json={"input_path": "data/inputs/sample_prd_login.md"},
    )
    assert generate_response.status_code == 200
    generate_payload = generate_response.json()
    script_path = generate_payload["script_path"]

    run_response = client.post(
        "/api/v1/run",
        json={"input_path": script_path},
    )
    run_payload = run_response.json()

    assert run_response.status_code == 200
    assert run_payload["status"] == "passed"

    run_id = run_payload["run_id"]

    detail_response = client.get(f"/api/v1/runs/{run_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()

    assert detail["status"] == "passed"
    assert detail["lineage"] is not None
    assert detail["lineage"].get("source_requirement") == "data/inputs/sample_prd_login.md"
    assert detail["lineage"].get("generated_script") == script_path
    assert "summary" in detail["artifact_paths"]
    assert detail.get("report_path") is None

    artifacts_response = client.get(f"/api/v1/runs/{run_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()

    assert artifacts["lineage"] is not None
    assert artifacts["lineage"].get("source_requirement") == "data/inputs/sample_prd_login.md"
    assert artifacts["lineage"].get("generated_script") == script_path
    assert "summary" in artifacts["artifact_paths"]
    assert artifacts.get("report_path") is None


def test_run_then_report_endpoint_generates_bug_report_for_failed_run() -> None:
    run_payload = _create_run("tests/assets/runner_fail_case.py")
    assert run_payload["status"] == "failed"
    assert run_payload["run_dir"].startswith("data/runs/")

    report_response = client.post(
        "/api/v1/report",
        json={"input_path": run_payload["run_dir"]},
    )
    report_payload = report_response.json()

    assert report_response.status_code == 200
    assert report_payload["generated"] is True
    assert report_payload["status"] == "failed"
    assert report_payload["report_path"] is not None
    assert report_payload["report_path"].startswith("generated/reports/")


def test_run_then_report_endpoint_generates_bug_report_with_screenshot_for_playwright_failure() -> None:
    run_payload = _create_run("tests/assets/playwright_login_failure_case.py")
    assert run_payload["status"] == "failed"
    assert run_payload["run_dir"].startswith("data/runs/")
    assert run_payload["artifact_paths"]["screenshot"].endswith("screenshots/login_failure.png")
    assert Path(run_payload["artifact_paths"]["screenshot"]).exists()

    report_response = client.post(
        "/api/v1/report",
        json={"input_path": run_payload["run_dir"]},
    )
    report_payload = report_response.json()

    assert report_response.status_code == 200
    assert report_payload["generated"] is True
    assert report_payload["status"] == "failed"
    assert report_payload["report_path"] is not None
    assert report_payload["report_path"].startswith("generated/reports/")

    report_content = Path(report_payload["report_path"]).read_text(encoding="utf-8")
    assert run_payload["artifact_paths"]["screenshot"] in report_content


def test_runs_endpoint_lists_summary_backed_runs() -> None:
    run_payload = _create_run("tests/assets/runner_pass_case.py")

    response = client.get("/api/v1/runs")
    payload = response.json()

    assert response.status_code == 200
    matched_runs = [item for item in payload["runs"] if item["run_id"] == run_payload["run_id"]]
    assert matched_runs
    assert matched_runs[0]["artifact_paths"]["summary"].endswith("/summary.json")
    assert matched_runs[0]["run_dir"] == run_payload["run_dir"]


def test_runs_endpoint_skips_invalid_run_summaries() -> None:
    run_payload = _create_run("tests/assets/runner_pass_case.py")
    bad_run_id = f"bad_run_{uuid4().hex}"
    bad_run_dir = RUNS_DIR / bad_run_id
    bad_run_dir.mkdir(parents=True, exist_ok=True)
    (bad_run_dir / "summary.json").write_text("{invalid json", encoding="utf-8")

    try:
        response = client.get("/api/v1/runs")
        payload = response.json()
    finally:
        shutil.rmtree(bad_run_dir, ignore_errors=True)

    assert response.status_code == 200
    assert any(item["run_id"] == run_payload["run_id"] for item in payload["runs"])
    assert all(item["run_id"] != bad_run_id for item in payload["runs"])


def test_run_detail_endpoint_returns_saved_summary() -> None:
    run_payload = _create_run("tests/assets/runner_fail_case.py")

    response = client.get(f"/api/v1/runs/{run_payload['run_id']}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["run_id"] == run_payload["run_id"]
    assert payload["status"] == run_payload["status"]
    assert payload["target_script"] == run_payload["target_script"]
    assert payload["artifact_paths"] == run_payload["artifact_paths"]


def test_run_artifacts_endpoint_returns_saved_artifact_paths() -> None:
    run_payload = _create_run("tests/assets/runner_pass_case.py")

    response = client.get(f"/api/v1/runs/{run_payload['run_id']}/artifacts")

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_payload["run_id"]
    assert data["run_dir"] == run_payload["run_dir"]
    assert data["artifact_paths"] == run_payload["artifact_paths"]
    assert data["lineage"] == {"source_requirement": None, "generated_script": None}
    assert data["report_path"] is None


def test_run_lookup_endpoints_return_404_for_missing_run() -> None:
    missing_run_id = "missing_run_for_api_lookup"

    detail_response = client.get(f"/api/v1/runs/{missing_run_id}")
    artifacts_response = client.get(f"/api/v1/runs/{missing_run_id}/artifacts")

    assert detail_response.status_code == 404
    assert artifacts_response.status_code == 404


def test_agent_run_endpoint_executes_login_flow_and_returns_trace_path() -> None:
    payload = _create_agent_run("data/inputs/sample_prd_login.md")

    assert payload["final_status"] == "passed"
    assert payload["script_path"] == "generated/tests/test_login_generated.py"
    assert payload["run_id"]
    assert payload["run_dir"].startswith("data/runs/")
    assert payload["artifact_paths"]["summary"].endswith("summary.json")
    assert payload["trace_path"].startswith("data/agent_runs/")
    assert payload["test_plan_path"].startswith("data/agent_runs/")
    assert payload["test_plan_path"].endswith("/test_plan.json")
    assert payload["retrieved_context"]["result_count"] >= 1
    assert payload["test_plan"]["feature_name"] == "User Login"
    assert payload["plan_validation"]["status"] == "passed"
    assert payload["planning_strategy"] == "deterministic_scaffold"
    assert payload["planning_backend"] == "deterministic"
    assert payload["planning_implementation"] == "deterministic_test_plan_scaffold"
    assert payload["retrieval_backend"] == "file_lexical"
    assert payload["retrieval_implementation"] == "deterministic_file_lexical"
    assert payload["run_summary"]["run_id"] == payload["run_id"]
    assert payload["queried_artifacts"]["run_id"] == payload["run_id"]
    assert payload["checkpoint_mode"] == "trace_resume_state"
    assert Path(payload["trace_path"]).exists()
    assert Path(payload["test_plan_path"]).exists()


def test_agent_run_endpoint_accepts_langchain_local_retrieval_backend() -> None:
    response = client.post(
        "/api/v1/agent-runs",
        json={
            "input_path": "data/inputs/sample_prd_login.md",
            "retrieval_backend": "langchain_local",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["final_status"] == "passed"
    assert payload["retrieval_backend"] == "langchain_local"
    assert payload["retrieval_implementation"] == "langchain_local_documents"

    trace_response = client.get(f"/api/v1/agent-runs/{payload['agent_run_id']}/trace")
    trace = trace_response.json()

    assert trace_response.status_code == 200
    assert trace["input"]["retrieval_backend"] == "langchain_local"
    assert trace["final_output"]["retrieval_backend"] == "langchain_local"
    assert trace["final_output"]["retrieval_implementation"] == "langchain_local_documents"
    assert trace["final_output"]["test_plan_path"] == payload["test_plan_path"]


def test_agent_run_endpoint_rejects_invalid_retrieval_backend() -> None:
    response = client.post(
        "/api/v1/agent-runs",
        json={
            "input_path": "data/inputs/sample_prd_login.md",
            "retrieval_backend": "not_a_backend",
        },
    )

    assert response.status_code == 400
    assert "Unsupported retrieval backend" in response.json()["detail"]


def test_agent_run_endpoint_rejects_invalid_planning_backend() -> None:
    response = client.post(
        "/api/v1/agent-runs",
        json={
            "input_path": "data/inputs/sample_prd_login.md",
            "planning_backend": "not_a_backend",
        },
    )

    assert response.status_code == 400
    assert "Unsupported planning backend" in response.json()["detail"]


def test_agent_run_endpoint_accepts_llm_assisted_planning_backend(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    response = client.post(
        "/api/v1/agent-runs",
        json={
            "input_path": "data/inputs/sample_prd_login.md",
            "approval_mode": "manual",
            "planning_backend": "llm_assisted",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["final_status"] == "waiting_human_approval"
    assert payload["run_id"] is None
    assert payload["planning_strategy"] == "llm_assisted_reviewable_plan"
    assert payload["planning_backend"] == "llm_assisted"
    assert payload["planning_implementation"] == "llm_assisted_reviewable_json"
    assert payload["planner_provider"] == "mock"
    assert payload["test_plan"]["risks"]
    assert payload["test_plan_path"].endswith("/test_plan.json")

    trace_response = client.get(f"/api/v1/agent-runs/{payload['agent_run_id']}/trace")
    trace = trace_response.json()

    assert trace_response.status_code == 200
    assert trace["input"]["planning_backend"] == "llm_assisted"
    assert trace["final_output"]["planning_backend"] == "llm_assisted"
    assert trace["final_output"]["planning_implementation"] == "llm_assisted_reviewable_json"


def test_agent_run_endpoint_accepts_task_text_and_lists_by_module() -> None:
    module = f"P6 Login {uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/agent-runs",
        json={
            "task_text": "Verify that a valid user can submit the login form and reach the dashboard.",
            "target_url": "/login",
            "module": module,
            "constraints": ["Use stable selector contracts", "Check recent failure history"],
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["final_status"] == "passed"
    assert payload["task"]["module"] == module
    assert payload["task"]["generated_input_path"].startswith("data/api_inputs/")
    assert payload["module"] == module
    assert payload["information_needs"]["required_context_types"]
    assert "run_history" in payload["information_needs"]["required_context_types"]
    assert payload["test_plan"]["planning_strategy"] == "deterministic_scaffold"
    assert Path(payload["test_plan_path"]).exists()

    list_response = client.get(
        "/api/v1/agent-runs",
        params={"module": module, "final_status": "passed", "limit": 5},
    )
    list_payload = list_response.json()

    assert list_response.status_code == 200
    assert any(item["agent_run_id"] == payload["agent_run_id"] for item in list_payload["agent_runs"])
    matched = [item for item in list_payload["agent_runs"] if item["agent_run_id"] == payload["agent_run_id"]][0]
    assert matched["module"] == module
    assert matched["trace_path"] == payload["trace_path"]


def test_agent_run_endpoint_accepts_script_path_for_manual_failed_report_flow() -> None:
    create_response = client.post(
        "/api/v1/agent-runs",
        json={
            "script_path": "tests/assets/playwright_login_failure_case.py",
            "approval_mode": "manual",
            "module": "playwright failure",
        },
    )
    created = create_response.json()

    assert create_response.status_code == 200
    assert created["final_status"] == "waiting_human_approval"
    assert created["script_path"] == "tests/assets/playwright_login_failure_case.py"
    assert created["run_id"] is None
    assert created["pending_approval"]["gate"] == "execution"

    execution_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approvals",
        json={"gate": "execution", "decision": "approved", "reviewer": "pytest"},
    )
    after_execution = execution_response.json()

    assert execution_response.status_code == 200
    assert after_execution["final_status"] == "report_draft_created"
    assert after_execution["run_status"] == "failed"
    assert after_execution["report_draft_path"].startswith("generated/reports/")
    assert after_execution["artifact_paths"]["screenshot"].endswith("screenshots/login_failure.png")
    assert Path(after_execution["artifact_paths"]["screenshot"]).exists()
    assert Path(after_execution["report_draft_path"]).exists()
    assert after_execution["pending_approval"]["gate"] == "report"

    report_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approvals",
        json={"gate": "report", "decision": "approved", "reviewer": "pytest"},
    )
    after_report = report_response.json()

    assert report_response.status_code == 200
    assert after_report["final_status"] == "failed"
    assert after_report["report_approved"] is True
    assert after_report["report_exported"] is True

    trace_response = client.get(f"/api/v1/agent-runs/{created['agent_run_id']}/trace")
    trace = trace_response.json()

    assert trace_response.status_code == 200
    assert [call["tool_name"] for call in trace["tool_calls"]] == AGENT_EXISTING_SCRIPT_FAILED_TOOL_SEQUENCE
    assert trace["input"]["script_path"] == "tests/assets/playwright_login_failure_case.py"
    assert trace["human_approvals"]["execution"]["decision"] == "approved"
    assert trace["human_approvals"]["report"]["decision"] == "approved"


def test_agent_run_summary_endpoint_returns_saved_trace_summary() -> None:
    payload = _create_agent_run("data/inputs/sample_prd_login.md")

    response = client.get(f"/api/v1/agent-runs/{payload['agent_run_id']}")
    summary = response.json()

    assert response.status_code == 200
    assert summary["agent_run_id"] == payload["agent_run_id"]
    assert summary["status"] == "completed"
    assert summary["final_status"] == "passed"
    assert summary["final_output"]["run_id"] == payload["run_id"]
    assert summary["final_output"]["trace_path"] == payload["trace_path"]
    assert summary["artifact_paths"]["trace"] == payload["trace_path"]


def test_agent_run_trace_endpoint_returns_tool_calls() -> None:
    payload = _create_agent_run("data/inputs/sample_prd_login.md")

    response = client.get(f"/api/v1/agent-runs/{payload['agent_run_id']}/trace")
    trace = response.json()

    assert response.status_code == 200
    assert trace["agent_run_id"] == payload["agent_run_id"]
    assert trace["final_status"] == "passed"

    tool_calls = trace["tool_calls"]
    assert [call["tool_name"] for call in tool_calls] == AGENT_SUCCESS_TOOL_SEQUENCE
    assert all(call["status"] == "succeeded" for call in tool_calls)
    assert trace["final_output"]["artifact_paths"]["summary"].endswith("summary.json")
    assert trace["final_output"]["checkpoint_mode"] == "trace_resume_state"
    assert trace["final_output"]["test_plan_path"] == payload["test_plan_path"]
    assert trace["final_output"]["retrieval_backend"] == "file_lexical"
    assert trace["final_output"]["retrieval_implementation"] == "deterministic_file_lexical"
    assert trace["final_output"]["planning_backend"] == "deterministic"
    assert trace["final_output"]["planning_implementation"] == "deterministic_test_plan_scaffold"


def test_agent_run_manual_approval_flow_pauses_and_resumes() -> None:
    created = _create_manual_agent_run("data/inputs/sample_prd_login.md", retrieval_backend="langchain_local")

    assert created["final_status"] == "waiting_human_approval"
    assert created["pending_approval"]["gate"] == "test_plan"
    assert created["test_plan"]["feature_name"] == "User Login"
    assert Path(created["test_plan_path"]).exists()
    assert created["retrieval_backend"] == "langchain_local"
    assert created["retrieval_implementation"] == "langchain_local_documents"
    assert created["planning_backend"] == "deterministic"
    assert created["run_id"] is None

    plan_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approvals",
        json={
            "gate": "test_plan",
            "decision": "approved",
            "reviewer": "pytest",
            "comment": "plan approved",
        },
    )
    after_plan = plan_response.json()

    assert plan_response.status_code == 200
    assert after_plan["final_status"] == "waiting_human_approval"
    assert after_plan["pending_approval"]["gate"] == "execution"
    assert after_plan["script_path"] == "generated/tests/test_login_generated.py"
    assert after_plan["retrieval_backend"] == "langchain_local"
    assert after_plan["run_id"] is None

    execution_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approvals",
        json={
            "gate": "execution",
            "decision": "approved",
            "reviewer": "pytest",
            "comment": "execute",
        },
    )
    after_execution = execution_response.json()

    assert execution_response.status_code == 200
    assert after_execution["final_status"] == "passed"
    assert after_execution["run_id"]
    assert after_execution["retrieval_backend"] == "langchain_local"
    assert after_execution["retrieval_implementation"] == "langchain_local_documents"

    trace_response = client.get(f"/api/v1/agent-runs/{created['agent_run_id']}/trace")
    trace = trace_response.json()

    assert trace_response.status_code == 200
    assert trace["status"] == "completed"
    assert trace["approval_requests"][0]["gate"] == "test_plan"
    assert trace["approval_requests"][0]["status"] == "approved"
    assert trace["approval_requests"][1]["gate"] == "execution"
    assert trace["approval_requests"][1]["status"] == "approved"
    assert trace["human_approvals"]["test_plan"]["decision"] == "approved"
    assert trace["human_approvals"]["execution"]["decision"] == "approved"
    assert trace["input"]["retrieval_backend"] == "langchain_local"
    assert trace["final_output"]["retrieval_backend"] == "langchain_local"


def test_agent_run_manual_task_text_flow_uses_approve_alias() -> None:
    module = f"P6 Manual Login {uuid4().hex[:8]}"
    create_response = client.post(
        "/api/v1/agent-runs",
        json={
            "task_text": "Verify login happy path with valid credentials.",
            "target_url": "/login",
            "module": module,
            "approval_mode": "manual",
        },
    )
    created = create_response.json()

    assert create_response.status_code == 200
    assert created["final_status"] == "waiting_human_approval"
    assert created["task"]["module"] == module
    assert created["pending_approval"]["gate"] == "test_plan"

    plan_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approve",
        json={"gate": "test_plan", "decision": "approved", "reviewer": "pytest"},
    )
    after_plan = plan_response.json()

    assert plan_response.status_code == 200
    assert after_plan["final_status"] == "waiting_human_approval"

    execution_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approve",
        json={"gate": "execution", "decision": "approved", "reviewer": "pytest"},
    )
    after_execution = execution_response.json()

    assert execution_response.status_code == 200
    assert after_execution["final_status"] == "passed"
    assert after_execution["task"]["module"] == module
    assert after_execution["run_summary"]["run_id"] == after_execution["run_id"]
    assert after_execution["test_plan_path"] == created["test_plan_path"]


def test_agent_run_manual_approve_alias_completes_approval_flow() -> None:
    created = _create_manual_agent_run("data/inputs/sample_prd_login.md")

    plan_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approve",
        json={
            "gate": "test_plan",
            "decision": "approved",
            "reviewer": "pytest",
            "comment": "plan approved through alias",
        },
    )
    after_plan = plan_response.json()

    assert plan_response.status_code == 200
    assert after_plan["final_status"] == "waiting_human_approval"
    assert after_plan["pending_approval"]["gate"] == "execution"
    assert after_plan["script_path"] == "generated/tests/test_login_generated.py"

    execution_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approve",
        json={
            "gate": "execution",
            "decision": "approved",
            "reviewer": "pytest",
            "comment": "execute through alias",
        },
    )
    after_execution = execution_response.json()

    assert execution_response.status_code == 200
    assert after_execution["final_status"] == "passed"
    assert after_execution["run_id"]
    assert after_execution["human_approvals"]["test_plan"]["decision"] == "approved"
    assert after_execution["human_approvals"]["execution"]["decision"] == "approved"


def test_agent_run_manual_rejects_plan_without_generation() -> None:
    created = _create_manual_agent_run("data/inputs/sample_prd_login.md")

    reject_response = client.post(
        f"/api/v1/agent-runs/{created['agent_run_id']}/approvals",
        json={
            "gate": "test_plan",
            "decision": "rejected",
            "reviewer": "pytest",
            "comment": "needs more detail",
        },
    )
    rejected = reject_response.json()

    assert reject_response.status_code == 200
    assert rejected["final_status"] == "blocked_plan_not_approved"
    assert rejected["script_path"] is None
    assert rejected["run_id"] is None

    trace_response = client.get(f"/api/v1/agent-runs/{created['agent_run_id']}/trace")
    trace = trace_response.json()
    assert [call["tool_name"] for call in trace["tool_calls"]] == [
        "parse_requirement",
        "analyze_information_needs",
        "retrieve_testing_context",
        "draft_test_plan",
        "validate_test_plan",
    ]


def test_agent_run_lookup_endpoints_return_404_for_missing_agent_run() -> None:
    missing_agent_run_id = "missing_agent_run_for_api_lookup"

    summary_response = client.get(f"/api/v1/agent-runs/{missing_agent_run_id}")
    trace_response = client.get(f"/api/v1/agent-runs/{missing_agent_run_id}/trace")

    assert summary_response.status_code == 404
    assert trace_response.status_code == 404
