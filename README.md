# Playwright TestOps Agent

CLI-first TestOps Agent MVP for:
- parsing structured PRD markdown
- extracting test points
- generating Playwright test scaffolds
- running local scripts and collecting artifacts
- drafting bug report markdown for failed runs
- optionally normalizing free-text requirement notes before the deterministic pipeline

## Current Scope

The project remains intentionally CLI-first.

Current positioning:
- honest
- runnable
- demoable
- easy to explain in interviews

The current baseline pipeline is:
- `parse`
- `extract`
- `generate`
- `run`
- `report`

The only LLM-assisted step is `normalize`, which converts free-text notes into parser-compatible PRD markdown before the deterministic downstream flow.

This project is not:
- a multi-agent platform
- a full autonomous testing platform
- a confirmed RCA system

## Project Structure

```text
playwright-testops-agent/
|- app/
|  |- core/
|  |- llm/
|  |- schemas/
|  |- templates/
|  |- utils/
|  |- config.py
|  |- main.py
|- data/
|  |- inputs/
|  |- expected/
|  |- runs/
|- generated/
|  |- tests/
|  |- reports/
|- docs/
|- tests/
|- README.md
|- SPEC.md
|- TASKS.md
|- requirements.txt
|- .env.example
```

## How to Run

1. Create and activate a virtual environment
2. Install dependencies for the current parser milestone:

```bash
pip install -r requirements-core.txt
```

Playwright-related installation is only needed later for generation/execution stages:

```bash
pip install -r requirements-e2e.txt
```

3. Check the CLI:

```bash
python -m app.main --help
```

4. Try the sample workflow:

```bash
python -m app.main parse --input data/inputs/sample_prd_login.md
python -m app.main generate --input data/inputs/sample_prd_login.md
python -m app.main run --input tests/assets/runner_pass_case.py
```

5. Try free-text normalization with the deterministic mock provider:

```bash
python -m app.main normalize --input data/inputs/free_text_login_notes.md
python -m app.main normalize --input data/inputs/free_text_search_notes.md --provider mock
```

## Normalization Providers

`mock` remains the default provider. It is deterministic and safe for local tests.

`live` is optional and only applies to `normalize`. To enable it, set all of these environment variables explicitly before running `--provider live`:

```bash
LLM_LIVE_BASE_URL=...
LLM_LIVE_MODEL=...
LLM_LIVE_API_KEY=...
```

Example:

```bash
python -m app.main normalize --input data/inputs/free_text_login_notes.md --provider live
```

If the live provider configuration is missing, normalization fails clearly and does not pretend to succeed.
