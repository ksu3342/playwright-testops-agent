from pathlib import Path
import shutil
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.collector import RUNS_DIR


client = TestClient(app)


def _create_run(input_path: str) -> dict[str, object]:
    response = client.post("/api/v1/run", json={"input_path": input_path})

    assert response.status_code == 200
    return response.json()


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
