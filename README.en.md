# Playwright TestOps Agent

[简体中文](./README.md)

A Playwright-based test workflow project that turns requirement inputs into inspectable test scaffolds, local run records, and draft bug reports.

[![Python Backend](https://img.shields.io/badge/Python-Backend-3776AB?logo=python&logoColor=white)](./app/core/)
[![FastAPI Routes](https://img.shields.io/badge/FastAPI-Routes-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Playwright Scaffolds](https://img.shields.io/badge/Playwright-Scaffolds-2EAD33?logo=playwright&logoColor=white)](./generated/tests/)
[![File-Backed Artifacts](https://img.shields.io/badge/File--Backed-Artifacts-4B5563)](./data/runs/)
[![Pytest Integration Tested](https://img.shields.io/badge/Pytest-Integration%20Tested-0A9EDC?logo=pytest&logoColor=white)](./tests/integration/test_api.py)
[![Docker Packaged](https://img.shields.io/badge/Docker-Packaged-2496ED?logo=docker&logoColor=white)](./Dockerfile)

## Quick Start

```bash
python -m pip install -r requirements-core.txt
python -m pytest tests/integration/test_api.py -q
python -m uvicorn app.api.main:app --port 8000
```

For the fuller Chinese walkthrough, see [README.zh-CN.md](./README.zh-CN.md).

## What Real Testing Problem This Repo Handles

Test inputs often start as PRDs, rough notes, or half-structured requirement text. This repo turns those inputs into three inspectable outputs: conservative Playwright scaffolds, recorded run artifacts, and draft bug reports derived from run results. The emphasis is not on platform language. The emphasis is on keeping the workflow concrete, inspectable, and easy to hand back to a human tester.

## What Is Already Implemented

- After an optional `normalize` step, the implemented flow is `parse -> extract -> generate -> run -> report`.
- The CLI already exposes `normalize`, `parse`, `generate`, `run`, and `report`.
- FastAPI already exposes health checks, pipeline execution, run lookup, and artifact lookup.
- Generated scaffolds, run summaries, and report drafts are written to [generated/tests](./generated/tests/), [data/runs](./data/runs/), and [generated/reports](./generated/reports/).
- The repo already includes [Docker packaging](./Dockerfile), [docker-compose.yml](./docker-compose.yml), and [API integration tests](./tests/integration/test_api.py).

## One Real Example

The files below are split into two separate evidence paths. They are not one continuous end-to-end run. Together they show both "PRD -> generated scaffold -> blocked run" and "failure-path run -> bug report draft".

### Example A: PRD -> generated scaffold -> blocked run

1. Input PRD: [data/inputs/sample_prd_login.md](./data/inputs/sample_prd_login.md)

```md
## Feature Name
User Login

## Page URL
/login
```

2. Generated scaffold: [generated/tests/test_login_generated.py](./generated/tests/test_login_generated.py)

```python
# Generated from: Login Page PRD
target_url = BASE_URL.rstrip("/") + "/login"
page.goto(target_url)
# TODO: Locate the relevant input selector before implementing...
```

3. Honest run gating for the generated scaffold: [data/runs/20260422T143848670135Z_test_login_generated/summary.json](./data/runs/20260422T143848670135Z_test_login_generated/summary.json)

```json
"status": "blocked",
"reason": "Script contains incomplete implementation markers (TODO) and is not ready for honest execution."
```

### Example B: separate failure-path run -> bug report draft

This step switches to a different evidence path. It does not continue the `sample_prd_login.md` / `test_login_generated.py` chain above.

1. Recorded failure run: [summary.json](./data/runs/20260422T143848683010Z_runner_fail_case/summary.json)

2. Matching report draft: [bug report draft](./generated/reports/bug_report_20260422T143848683010Z_runner_fail_case.md)

```text
status: failed
FAILED tests/assets/runner_fail_case.py::test_minimal_fail_case - assert 1 == 2
```

## Engineering Evidence

- [app/core/](./app/core/) contains the parser, extractor, generator, runner, reporter, and normalizer modules.
- [app/api/main.py](./app/api/main.py) defines `/healthz`, `/api/v1/*`, run lookup, and artifact lookup routes.
- [tests/integration/test_api.py](./tests/integration/test_api.py) covers health, normalize, generate -> run, run -> report, run lookup, invalid summary skipping, and `404` cases.
- [data/runs](./data/runs/) and [generated/reports](./generated/reports/) are real artifact directories in the repo.
- [Dockerfile](./Dockerfile) uses `uvicorn app.api.main:app` as the service entrypoint, and [docker-compose.yml](./docker-compose.yml) provides a local container run path.

## Why It Is Designed This Way

- The current implementation remains CLI-first, and the FastAPI layer is only a light wrapper over the same Python core functions.
- `normalize` is intentionally optional and remains the only LLM-assisted step.
- The deterministic core flow stays `parse -> extract -> generate -> run -> report`, which keeps behavior easier to inspect and explain.
- Artifacts remain file-backed so run history and reports can be checked directly from the repository workspace.
- `/api/v1/run` remains synchronous so run state and recorded outputs stay explicit.

## Boundaries / Non-goals

- The current implementation remains a `CLI-first TestOps Agent MVP + thin FastAPI wrapper`.
- Persistence is still file-backed, not Redis-backed, MySQL-backed, or otherwise database-backed.
- No frontend, authentication layer, multi-agent system, or full testing platform is claimed here.
- This is not a queue-backed async execution system or a production-grade platform.

## Further Reading

- Chinese landing page: [README.md](./README.md)
- Fuller Chinese walkthrough: [README.zh-CN.md](./README.zh-CN.md)
- Technical spec: [SPEC.md](./SPEC.md)
- Historical roadmap: [TASKS.md](./TASKS.md)
- License: [LICENSE](./LICENSE)
