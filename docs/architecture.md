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

## Design principles
- Deterministic parse/extract/generate/run/report flow
- Selector contract prevents guessed locators
- Test data contract provides fixture values
- File-backed persistence (no database required)
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
