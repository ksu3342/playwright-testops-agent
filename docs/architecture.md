# Architecture

This bounded TestOps workflow is designed for portfolio demonstration.

## Core components

1. **CLI-first core** (`app/core/`)
   - `parser.py` reads a simple PRD/page description
   - `extractor.py` extracts test points with selector contract + test data contract
   - `generator.py` writes Playwright test scripts from Jinja2 templates
   - `runner.py` executes generated tests and records command/stdout/stderr/summary
   - `collector.py` discovers produced screenshot/trace artifacts under the run directory
   - `reporter.py` drafts bug report from run summary and artifact paths

2. **Optional normalize step** (`app/core/normalizer.py`)
   - Requirement normalization before deterministic extraction

3. **Demo app** (`demo_app/main.py`)
   - Local web target for testing generated scripts

4. **FastAPI wrapper** (`app/api/`)
   - Thin wrapper over the same core modules
   - Provides run execution and artifact lookup endpoints

5. **Agent/RAG platform-facing layer** (`app/agent/`, `app/rag/`)
   - Wraps parse/retrieve/plan/generate/run/report as traceable agent steps
   - Stores agent traces under `data/agent_runs/`
   - Persists the reviewed test plan as `test_plan.json` and generates requirement-backed scripts from that approved plan
   - Accepts PRD file paths, API/CLI-submitted task text, or existing Python test scripts
   - Records deterministic information-need analysis before retrieval
   - Uses `data/kb/index.json` and `data/kb/uploaded/` for local file-backed KB ingest/search
   - Keeps KB search deterministic; it is not a production vector database
   - Uses `trace.json + resume_state` as a local checkpoint record; it is not LangGraph-native durable execution
   - Renders readable decision traces from `trace.json` for CLI demos and human review
   - Uses centralized Agent `final_status` values while preserving core runner statuses inside run summaries

## Design principles
- Deterministic parse/extract/generate/run/report flow
- Selector contract prevents guessed locators
- Test data contract provides fixture values
- File-backed persistence (no database required)
- Human approval gates for high-risk agent steps
- Deterministic planning and retrieval boundaries are recorded explicitly
- Artifacts discovered only when actually produced by test execution

## Output structure
```
data/runs/<run_id>/
  command.txt    # executed command
  stdout.txt     # stdout
  stderr.txt     # stderr
  summary.json   # run summary
  screenshots/   # captured screenshots (if any)
  trace.zip      # Playwright trace (if any)
```

```
data/agent_runs/<agent_run_id>/trace.json
  # agent tool calls, approvals, final output, and resume state

data/agent_runs/<agent_run_id>/test_plan.json
  # reviewable plan consumed by generate_test_from_plan after approval

data/agent_runs/<agent_run_id>/decision_trace.md
  # optional human-readable trace rendered by `python -m app.main agent-trace --format markdown`

docs/agent_demo_walkthrough.md
  # fixed golden demo commands and expected trace evidence

data/kb/index.json
  # local KB index written by POST /api/v1/kb/ingest

data/kb/uploaded/<document_id>.md
  # content uploaded through KB ingest API
```
