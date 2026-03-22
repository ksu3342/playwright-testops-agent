# SPEC

## Goal
Build an MVP TestOps Agent based on Playwright.

## Core workflow
1. Read a simple PRD or page description
2. Extract test points
3. Generate Playwright test scripts
4. Execute tests
5. Save screenshots and logs
6. Summarize failures
7. Draft a bug report

## Tech stack
- Python
- Playwright
- Jinja2 templates
- Optional FastAPI wrapper later

## Phase 1

Phase 1 is CLI-first and focused on scaffold quality.

Deliverables:
- simple command-line workflow
- readable modules with TODO boundaries
- sample inputs for demo
- generated test/report output folders
- lightweight tests for the placeholder pipeline

Non-goals for this phase:
- full LLM orchestration
- enterprise multi-agent architecture
- database/auth/queue systems
- production claims

## MVP scope for current scaffold
- Provide a CLI-based end-to-end MVP pipeline
- Accept a simple text PRD/page description
- Parse the input and extract basic test points
- Generate a placeholder Playwright test script
- Run a placeholder execution flow and save artifacts under `data/`
- Draft a simple bug report from the current run result
- Keep implementation modular and easy to extend

## Later stage
- Add a thin FastAPI wrapper only after the CLI workflow is stable
