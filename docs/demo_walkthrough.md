# Demo Walkthrough

Start the local demo app:

```powershell
.\.venv\Scripts\python.exe -m demo_app.main
```

Run the demo smoke test:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\demo\test_demo_app.py -q
```

Fixed demo behaviors:

1. `GET /login` renders email and password inputs plus a submit button.
2. `POST /login` with `demo@example.com` / `password123` redirects to `/dashboard`.
3. `POST /login` with invalid credentials shows an inline error on the page.
4. `GET /search?q=playwright` returns a visible results list.
5. `GET /search?q=no-hit` returns an empty state.

## Agent CLI Demo

Run a task-text Agent flow with human approval:

```powershell
.\.venv\Scripts\python.exe -m app.main agent-run --task "Verify login happy path with valid credentials." --target-url /login --module login --approval-mode manual
.\.venv\Scripts\python.exe -m app.main agent-approve --agent-run-id <agent_run_id> --gate test_plan --decision approved --reviewer demo
.\.venv\Scripts\python.exe -m app.main agent-approve --agent-run-id <agent_run_id> --gate execution --decision approved --reviewer demo
.\.venv\Scripts\python.exe -m app.main agent-trace --agent-run-id <agent_run_id> --format summary
```

Recommended talk track for this demo:

1. `task_text` is normalized into a parser-compatible input.
2. The Agent retrieves file-backed testing context from product docs, contracts, guidelines, run history, and reports.
3. The Agent writes the reviewable plan to `data/agent_runs/<agent_run_id>/test_plan.json`.
4. Human approval of `test_plan` unlocks generation from that approved plan, not from a fresh implicit extraction.
5. Human approval of `execution` runs the generated script, then the trace links the generated script, run summary, report draft when present, and decision state.

Run an existing-script failure path through the Agent and render a markdown decision trace:

```powershell
.\.venv\Scripts\python.exe -m app.main agent-run --script tests/assets/playwright_login_failure_case.py --approval-mode manual --module "playwright failure"
.\.venv\Scripts\python.exe -m app.main agent-approve --agent-run-id <agent_run_id> --gate execution --decision approved --reviewer demo
.\.venv\Scripts\python.exe -m app.main agent-approve --agent-run-id <agent_run_id> --gate report --decision approved --reviewer demo
.\.venv\Scripts\python.exe -m app.main agent-trace --agent-run-id <agent_run_id> --format markdown
```

The Agent trace is still file-backed (`trace.json + resume_state`). KB retrieval is local lexical retrieval or the optional LangChain Core local adapter, not a production vector database or embedding pipeline. Execution is synchronous and file-system backed; this demo is an Agent MVP, not a queue-backed durable platform.
