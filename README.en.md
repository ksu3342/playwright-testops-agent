# Playwright TestOps Agent

[简体中文](./README.md)

A local file-backed TestOps Agent workflow prototype that turns testing tasks into retrievable, reviewable, executable, and traceable test evidence.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](./app/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Routes-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Playwright](https://img.shields.io/badge/Playwright-Integration-2EAD33?logo=playwright&logoColor=white)](./app/core/generator.py)
[![Pytest](https://img.shields.io/badge/Pytest-Tests-0A9EDC?logo=pytest&logoColor=white)](./tests/)
[![GitHub Actions CI](https://github.com/ksu3342/playwright-testops-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/ksu3342/playwright-testops-agent/actions/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/Docker-Packaged-2496ED?logo=docker&logoColor=white)](./Dockerfile)

## Quick Start

```bash
python -m pip install -r requirements-core.txt
python -m pytest tests/integration/test_api.py -q
python -m uvicorn app.api.main:app --port 8000
```

For the fuller Chinese walkthrough, see [README.zh-CN.md](./README.zh-CN.md).

## What Real Testing Problem This Repo Handles

Test inputs often start as PRDs, rough notes, or half-structured requirement text. This repo turns those inputs into retrieved context, reviewable test plans, conservative Playwright scaffolds, recorded run artifacts, and draft bug reports derived from failed runs. The emphasis is not on platform language. The emphasis is on keeping the workflow concrete, inspectable, and easy to hand back to a human tester.

## Current Agent Path

```text
task_text / PRD
-> retrieve testing context
-> draft test_plan.json
-> human approval
-> generate Playwright test
-> run
-> classify passed / failed / blocked
-> create report draft or archive
-> save trace.json / decision_trace
```

## What Is Already Implemented

- Agent runs accept `input_path`, `task_text`, or `script_path`; record traces; analyze information needs; retrieve testing context; persist `test_plan.json`; and pause or stop through human approval gates.
- Approval gates cover approve / reject / `resume_state` semantics; traces save `trace.json`, `decision_trace[]`, `final_status`, and `trace.status`.
- Requirement-backed generation uses `generate_test_from_plan` with the approved test plan instead of bypassing the reviewed plan.
- KB retrieval is file-backed and covered by retrieval quality evals; optional `langchain_local` is a LangChain Core local adapter, not a vector database.
- The local demo web target, selector contract, test data contract, generated login test, runner artifacts, and failed-run report draft all have source or test evidence.
- The CLI exposes `normalize`, `parse`, `generate`, `run`, `report`, plus Agent commands: `agent-run`, `agent-approve`, and `agent-trace`.
- FastAPI is a thin wrapper over the same Python functions and exposes agent-runs, KB search, run lookup, and artifact lookup.
- Generated scaffolds, run summaries, and report drafts are written to `generated/tests/`, `data/runs/`, and `generated/reports/` at runtime. Those outputs are reproducible locally but are not committed as fixed public samples.
- The repo includes [Docker packaging](./Dockerfile), [docker-compose.yml](./docker-compose.yml), GitHub Actions CI, RAG retrieval evals, and an Agent golden demo.

## Underlying Deterministic Toolchain

The Agent path calls controlled tools instead of editing files directly:

```text
normalize -> parse -> extract -> generate -> run -> report
```

This toolchain still works through CLI / API on its own; inside the Agent path, it is the deterministic execution layer behind reviewable nodes.

## One Real Example

The example below is command-driven on purpose. Public README links point to tracked source files, tests, contracts, and input PRDs. The generated outputs under `generated/tests/`, `data/runs/`, and `generated/reports/` are runtime artifacts that you produce locally.

### Example A: PRD -> generated login test -> local run

1. Input PRD: [data/inputs/sample_prd_login.md](./data/inputs/sample_prd_login.md)

```md
## Feature Name
User Login

## Page URL
/login
```

2. Stable implementation evidence: [app/core/generator.py](./app/core/generator.py), [app/core/selector_contract.py](./app/core/selector_contract.py), [data/contracts/demo_app_selectors.json](./data/contracts/demo_app_selectors.json), [data/contracts/demo_app_test_data.json](./data/contracts/demo_app_test_data.json), and [tests/unit/test_generator.py](./tests/unit/test_generator.py)

3. Reproduce the generated login test locally:

```powershell
python -m app.main generate --input data/inputs/sample_prd_login.md
python -m pytest generated/tests/test_login_generated.py -q
python -m app.main run generated/tests/test_login_generated.py
```

The generated script and run directory are runtime outputs. They are intentionally not committed as fixed sample files in the public repository.

### Example B: separate failure-path run -> report draft

This step uses a different evidence path. It does not continue the `sample_prd_login.md` login-generation flow above.

1. Stable failure-path evidence: [tests/assets/runner_fail_case.py](./tests/assets/runner_fail_case.py), [app/core/runner.py](./app/core/runner.py), [tests/integration/test_pipeline.py](./tests/integration/test_pipeline.py), and [tests/integration/test_api.py](./tests/integration/test_api.py)

2. Reproduce the failure-path run and report locally:

```powershell
python -m app.main run --input tests/assets/runner_fail_case.py
python -m app.main report --input data/runs/<run_id>
```

The report path under `generated/reports/` is also a runtime output, not a fixed public sample file.

## Engineering Evidence

- [app/core/generator.py](./app/core/generator.py), [app/core/runner.py](./app/core/runner.py), and [app/core/selector_contract.py](./app/core/selector_contract.py) implement generation, run classification, and deterministic selector loading.
- [data/contracts/demo_app_selectors.json](./data/contracts/demo_app_selectors.json) and [data/contracts/demo_app_test_data.json](./data/contracts/demo_app_test_data.json) keep selector and fixture sources file-backed.
- [demo_app/main.py](./demo_app/main.py) is the local demo target used by the executable login flow.
- [app/rag/langchain_retriever.py](./app/rag/langchain_retriever.py) wraps the local KB documents with LangChain Core `Document` / `BaseRetriever` interfaces while preserving deterministic local scoring.
- [app/agent/tools.py](./app/agent/tools.py) exposes the controlled workflow functions as Python tools and provides a LangChain-compatible `StructuredTool` export for interface evidence.
- [app/agent/trace_explainer.py](./app/agent/trace_explainer.py) renders `trace.json` as a concise decision trace for CLI demos and review.
- Agent runs persist the reviewed plan as `data/agent_runs/<agent_run_id>/test_plan.json`; requirement-backed generation uses that approved plan through `generate_test_from_plan`.
- [docs/agent_demo_walkthrough.md](./docs/agent_demo_walkthrough.md) is the fixed golden demo for task text, approval, plan-driven generation, run evidence, report drafts, and trace review.
- Optional `planning_backend=llm_assisted` asks a configured planner provider for reviewable test-plan JSON only; generated scripts and execution still go through controlled deterministic tools.
- [tests/unit/test_generator.py](./tests/unit/test_generator.py), [tests/unit/test_runner.py](./tests/unit/test_runner.py), and [tests/demo/test_demo_app.py](./tests/demo/test_demo_app.py) verify generator, runner, and demo behavior.
- [tests/integration/test_api.py](./tests/integration/test_api.py) and [tests/integration/test_pipeline.py](./tests/integration/test_pipeline.py) cover the API-facing and pipeline-facing integration paths.

## Why It Is Designed This Way

- The current implementation remains CLI-first, and the FastAPI layer is only a light wrapper over the same Python core functions.
- `normalize` is intentionally optional and remains outside the deterministic execution chain.
- Optional LLM-assisted planning is opt-in through `planning_backend=llm_assisted`; the default remains deterministic.
- The deterministic core flow stays inspectable; requirement-backed Agent runs now use `retrieve -> test_plan.json -> approval -> generate_test_from_plan -> run -> report/trace`.
- Artifacts remain file-backed so run history and reports can be checked directly from the repository workspace.
- KB retrieval is file-backed by default: `data/kb/index.json` stores the index and `data/kb/uploaded/` stores API-ingested content. `backend=langchain_local` runs the same local KB through LangChain Core document/retriever interfaces, not embeddings.
- Agent checkpointing is local `trace.json + resume_state`, not LangGraph-native durable execution.
- `/api/v1/run` remains synchronous so run state and recorded outputs stay explicit.

## Boundaries / Non-goals

- The current implementation remains a `CLI-first TestOps Agent MVP + thin FastAPI wrapper`.
- Persistence is still file-backed, not Redis-backed, MySQL-backed, or otherwise database-backed.
- The API is intended for local prototype demos only; it has no authentication, execution sandboxing, permission isolation, or production-grade execution hardening.
- No frontend, authentication layer, multi-agent system, or production testing platform is claimed here.
- Local KB search is deterministic file retrieval. The optional `langchain_local` backend is a LangChain Core local `Document` / `BaseRetriever` adapter, not a production vector database, embedding pipeline, or LangChain vector store.
- Test-plan drafting is deterministic by default. Optional LLM-assisted drafting returns reviewable JSON only; it does not execute tests, choose selectors, or control the browser.
- Trace persistence is not a LangGraph-native durable checkpoint backend.
- This is not an autonomous browser-control agent, a queue-backed async execution system, or a production-grade platform.

## What run_id Now Proves

Each run's `run_id` records a complete evidence chain in `data/runs/<run_id>/summary.json`:

- `lineage.source_requirement`: Input PRD file path (e.g., `data/inputs/sample_prd_login.md`)
- `lineage.generated_script`: Generated test script path (e.g., `generated/tests/test_login_generated.py`)
- `artifact_paths`: Paths to command.txt, stdout.txt, stderr.txt, summary.json
- `artifact_paths.screenshot`: Screenshot path on Playwright failure (if any)
- `report_path`: Bug report path (if generated)

Query via API:

```bash
# Query run detail
GET /api/v1/runs/{run_id}

# Query artifacts
GET /api/v1/runs/{run_id}/artifacts
```

Responses include `lineage`, `artifact_paths`, and `report_path` fields.

Minimal agent and KB platform-style endpoints:

```bash
POST /api/v1/agent-runs
GET  /api/v1/agent-runs
GET  /api/v1/agent-runs/{agent_run_id}
GET  /api/v1/agent-runs/{agent_run_id}/trace
POST /api/v1/agent-runs/{agent_run_id}/approvals
POST /api/v1/agent-runs/{agent_run_id}/approve
POST /api/v1/kb/ingest
GET  /api/v1/kb/search?query=login%20selector&max_results=5&backend=langchain_local
```

`/approve` is a compatibility alias for `/approvals`. KB ingest accepts `source_type`, optional `source_path`, optional `content`, and optional `metadata`; content uploads are written under `data/kb/uploaded/` and indexed through `data/kb/index.json`. KB search and agent runs return retrieval metadata, and agent runs also return `planning_backend` / `planning_implementation` so the trace shows whether deterministic or LLM-assisted planning was used.

Agent runs can be created from a tracked PRD path, a task payload, or an existing test script:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/agent-runs" `
  -H "Content-Type: application/json" `
  -d '{"task_text":"Verify login happy path with valid credentials.","target_url":"/login","module":"login","constraints":["Use selector contracts"],"retrieval_backend":"langchain_local","planning_backend":"llm_assisted"}'

curl.exe -X POST "http://127.0.0.1:8000/api/v1/agent-runs" `
  -H "Content-Type: application/json" `
  -d '{"script_path":"tests/assets/playwright_login_failure_case.py","approval_mode":"manual","module":"playwright failure"}'
```

The same Agent flow can be demonstrated through CLI without a server:

```powershell
python -m app.main agent-run --task "Verify login happy path with valid credentials." --target-url /login --module login --approval-mode manual
python -m app.main agent-approve --agent-run-id <agent_run_id> --gate test_plan --decision approve
python -m app.main agent-approve --agent-run-id <agent_run_id> --gate execution --decision approve
python -m app.main agent-trace --agent-run-id <agent_run_id> --format summary
python -m app.main agent-run --script tests/assets/playwright_login_failure_case.py --approval-mode manual --module "playwright failure"
python -m app.main agent-trace --agent-run-id <agent_run_id> --format markdown
```

The CLI and API still accept legacy `approved` / `rejected`, but the approval semantics are described as approve / reject.

For the recommended demo, point to `data/agent_runs/<agent_run_id>/test_plan.json` first, then show the summary trace linking the approved plan, generated script, run summary, and defect draft when a failed run creates one.

The list endpoint reads local `data/agent_runs/*/trace.json` files and supports `status`, `final_status`, `module`, and `limit` filters.

Agent `final_status` uses a centralized business-status vocabulary: `passed`, `failed`, `blocked_missing_context`, `blocked_selector_missing`, `blocked_test_data_missing`, `blocked_plan_not_approved`, `waiting_human_approval`, `report_draft_created`, and `environment_error`. `trace.status` remains a lifecycle field such as `completed` or `waiting_for_approval`.

## CI Verification

[.github/workflows/ci.yml](./.github/workflows/ci.yml) runs on every push and PR to main:

- Install core and e2e dependencies
- Install Playwright Chromium
- Run demo app tests
- Run unit tests
- Run integration tests
- Run RAG retrieval evals
- Run Agent golden demo
- Generate login test
- Run generated login test
- Run generated login test via CLI runner

## Further Reading

- Chinese landing page: [README.md](./README.md)
- Fuller Chinese walkthrough: [README.zh-CN.md](./README.zh-CN.md)
- Technical spec: [SPEC.md](./SPEC.md)
- Historical roadmap: [TASKS.md](./TASKS.md)
- License: [LICENSE](./LICENSE)
