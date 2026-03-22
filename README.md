# Playwright TestOps Agent

MVP project for:
- reading simple product/page descriptions
- extracting test points
- generating Playwright test scripts
- executing tests
- collecting screenshots/logs
- drafting bug reports

## Phase 1 Scope

This phase is intentionally CLI-first.

The goal is to keep the project:
- honest
- runnable
- demoable
- easy to explain in interviews

Current scaffold includes placeholder modules for:
- parsing a simple PRD/page description
- extracting test points
- generating a Playwright test file
- running a placeholder pipeline
- collecting run artifacts
- drafting a simple bug report

It does not yet implement real LLM reasoning or full browser execution logic.

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
python -m app.main run --input data/inputs/sample_prd_login.md
python -m app.main report --run-id latest
```
