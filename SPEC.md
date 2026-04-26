# SPEC

## Goal
Build a portfolio-grade AI-assisted TestOps workflow backend based on Playwright.

## Current stage
Bounded TestOps workflow - from PRD to executable test with artifact-backed bug report.

## Core workflow
1. Read a simple PRD or page description
2. Extract test points (selector contract + test data contract)
3. Generate Playwright test scripts from templates
4. Execute tests locally
5. Collect screenshots and trace artifacts when produced
6. Draft a bug report referencing artifact paths

## Implemented features
- PRD parsing with Pydantic validation
- Test point extraction with selector contract
- Test data contract for fixture values
- Demo app as local web target (demo_app.py)
- Executable generated login test
- CLI run artifacts (command/stdout/stderr/summary)
- Failed-run screenshot artifact capture
- Bug report draft referencing artifact path
- FastAPI run/artifact lookup endpoints
- GitHub Actions CI

## Tech stack
- Python
- Playwright
- Jinja2 templates
- FastAPI (thin wrapper over CLI core)

## Non-goals (out of scope)
- production-grade platform
- autonomous agent / LLM orchestration
- multi-agent orchestration
- database-backed platform
- queue-backed async execution
- frontend/dashboard/auth
