# Playwright TestOps Agent

[简体中文](./README.md)

A narrow, explainable TestOps engineering prototype that turns requirement inputs into conservative Playwright scaffolds, local run records, and draft bug reports.

[![Python Backend](https://img.shields.io/badge/Python-Backend-3776AB?logo=python&logoColor=white)](./app/core/)
[![FastAPI Wrapper](https://img.shields.io/badge/FastAPI-Thin%20Wrapper-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Playwright Scaffold](https://img.shields.io/badge/Playwright-Scaffold%20Generation-2EAD33?logo=playwright&logoColor=white)](./app/core/generator.py)
[![Docker Packaged](https://img.shields.io/badge/Docker-Packaged-2496ED?logo=docker&logoColor=white)](./Dockerfile)
[![Pytest Integration Tested](https://img.shields.io/badge/Pytest-Integration%20Tested-0A9EDC?logo=pytest&logoColor=white)](./tests/integration/test_api.py)
[![Honest Scope MVP](https://img.shields.io/badge/MVP-Honest%20Scope-6B7280)](./SPEC.md)

## Quick Start

```bash
python -m pip install -r requirements-core.txt
python -m pytest tests/integration/test_api.py -q
python -m uvicorn app.api.main:app --port 8000
```

For the Chinese default landing page and the fuller Chinese walkthrough, see [README.md](./README.md) and [README.zh-CN.md](./README.zh-CN.md).

## What This Repo Does

This repo is a `CLI-first TestOps Agent MVP + thin FastAPI wrapper`. After an optional `normalize` step, the deterministic core flow is `parse -> extract -> generate -> run -> report`. The goal is not feature breadth. The goal is to keep the workflow runnable, inspectable, and explicit about what is not implemented.

## What Is Implemented

- CLI entry points already cover `normalize`, `parse`, `generate`, `run`, and `report`.
- A thin FastAPI wrapper exposes health checks, pipeline execution, run history lookup, and artifact lookup.
- Run artifacts stay file-backed under [data/runs](./data/runs/) and generated reports stay under [generated/reports](./generated/reports/).
- `/api/v1/run` is still synchronous and does not depend on a queue, worker, or database.
- The repo already includes [Docker packaging](./Dockerfile) and [API integration tests](./tests/integration/test_api.py).

## Why It Is Designed This Way

- `normalize` is optional and intentionally narrow, so LLM usage stays at the edge of the workflow.
- The core flow remains deterministic, which makes the behavior easier to explain and verify.
- Artifacts remain file-backed so the MVP stays easy to inspect without extra infrastructure.
- The FastAPI layer is a thin wrapper over the same Python core functions instead of a rewritten service architecture.

## Engineering Evidence

- [app/core/](./app/core/) contains the parser, extractor, generator, runner, reporter, and normalizer modules.
- [app/api/main.py](./app/api/main.py) defines `/healthz`, `/api/v1/*`, run lookup, and artifact lookup routes.
- [tests/integration/test_api.py](./tests/integration/test_api.py) covers health, normalize, generate -> run, run -> report, run lookup, invalid summary skipping, and `404` cases.
- [Dockerfile](./Dockerfile) uses `uvicorn app.api.main:app` as the service entrypoint, and [docker-compose.yml](./docker-compose.yml) provides a local container run path.
- [data/runs](./data/runs/) and [generated/reports](./generated/reports/) are real artifact locations in the repo.

## Boundaries / Non-goals

- This is a CLI-first engineering prototype, not a production-grade platform.
- `normalize` is optional and is the only LLM-assisted step.
- `/api/v1/run` remains synchronous, not a queue-backed async execution service.
- Persistence is file-backed, not Redis-backed, MySQL-backed, or otherwise database-backed.
- No frontend, authentication layer, or multi-agent platform is claimed here.

## Further Reading

- Chinese default landing page: [README.md](./README.md)
- Fuller Chinese walkthrough: [README.zh-CN.md](./README.zh-CN.md)
- Technical spec: [SPEC.md](./SPEC.md)
- Historical roadmap: [TASKS.md](./TASKS.md)
- License: [LICENSE](./LICENSE)
