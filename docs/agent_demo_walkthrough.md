# Agent Golden Demo Walkthrough

This walkthrough is the fixed, reproducible proof path for the local file-backed TestOps Agent MVP. It uses deterministic `agent_run_id` values so the trace and plan paths are stable across runs.

## One-Command Verification

Run the golden demo integration test:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_agent_golden_demo.py -q
```

The test creates these local, gitignored artifacts:

```text
data/agent_runs/golden_demo_login_manual/trace.json
data/agent_runs/golden_demo_login_manual/test_plan.json
data/agent_runs/golden_demo_failed_report/trace.json
data/agent_runs/golden_demo_search_blocked/trace.json
```

## Manual Passed Flow

Run a task-text Agent flow with human approval:

```powershell
.\.venv\Scripts\python.exe -m app.main agent-run --task "Verify login happy path with valid credentials." --target-url /login --module login --approval-mode manual --agent-run-id golden_demo_login_manual
.\.venv\Scripts\python.exe -m app.main agent-approve --agent-run-id golden_demo_login_manual --gate test_plan --decision approved --reviewer demo
.\.venv\Scripts\python.exe -m app.main agent-approve --agent-run-id golden_demo_login_manual --gate execution --decision approved --reviewer demo
.\.venv\Scripts\python.exe -m app.main agent-trace --agent-run-id golden_demo_login_manual --format summary
```

Expected proof points:

- `data/agent_runs/golden_demo_login_manual/test_plan.json` exists.
- `trace.json` contains `retrieve_testing_context`, `draft_test_plan`, `generate_test_from_plan`, `run_test`, and `collect_run_evidence`.
- `final_status` is `passed`.
- `final_output.artifact_paths.summary` points to the run summary.

## Failed Report Flow

Run an existing failing script through execution and report approval:

```powershell
.\.venv\Scripts\python.exe -m app.main agent-run --script tests/assets/runner_fail_case.py --approval-mode manual --module "runner failure" --agent-run-id golden_demo_failed_report
.\.venv\Scripts\python.exe -m app.main agent-approve --agent-run-id golden_demo_failed_report --gate execution --decision approved --reviewer demo
.\.venv\Scripts\python.exe -m app.main agent-trace --agent-run-id golden_demo_failed_report --format summary
.\.venv\Scripts\python.exe -m app.main agent-approve --agent-run-id golden_demo_failed_report --gate report --decision approved --reviewer demo
```

Expected proof points:

- Before report approval, `final_status` is `report_draft_created`.
- `trace.json` contains `create_report`.
- `final_output.report_draft_path` points to a generated bug report draft.
- `final_output.artifact_paths.summary`, `stdout`, and `stderr` point to saved run artifacts.
- After report approval, `final_status` is `failed`.

## Blocked Flow

Run the search PRD through the Agent:

```powershell
.\.venv\Scripts\python.exe -m app.main agent-run --input data/inputs/sample_prd_search.md --agent-run-id golden_demo_search_blocked
.\.venv\Scripts\python.exe -m app.main agent-trace --agent-run-id golden_demo_search_blocked --format summary
```

Expected proof points:

- `data/agent_runs/golden_demo_search_blocked/test_plan.json` exists.
- `trace.json` contains `generate_test_from_plan`.
- `final_status` is `blocked_missing_context` because the generated search scaffold is intentionally not execution-ready.
- `final_output.run_summary.summary.status` remains the core runner status `blocked`.

## Status Vocabulary

`trace.status` is the trace lifecycle status, such as `completed` or `waiting_for_approval`.

`final_status` is the Agent business status and is restricted to:

- `passed`
- `failed`
- `blocked_missing_context`
- `blocked_selector_missing`
- `blocked_test_data_missing`
- `blocked_plan_not_approved`
- `waiting_human_approval`
- `report_draft_created`
- `environment_error`
