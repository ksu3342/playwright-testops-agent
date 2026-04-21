# TASKS

Historical roadmap for implemented milestones and remaining MVP gaps.

## Phase 1: Scaffold Cleanup
- [x] Initialize project structure
- [x] Add CLI-first phase-1 scaffold
- [x] Add sample input files
- [x] Add starter schemas and placeholder modules
- [x] Improve README

## Phase 2: Core MVP Pipeline
- [x] Build PRD/page description parser
- [x] Extract test points
- [x] Generate conservative Playwright test scaffolds
- [x] Execute local test assets and preserve honest `passed` / `failed` / `blocked` / `environment_error` statuses
- [ ] Execute generated Playwright browser flows for real

## Phase 3: Execution Artifacts and Bug Report
- [x] Save command/stdout/stderr/summary artifacts for local runs
- [x] Draft bug report markdown from failed runs
- [ ] Save screenshots and trace artifacts from real browser runs

## Phase 4: Thin FastAPI Wrapper (Optional after CLI)
- [x] Add thin FastAPI wrapper that calls existing core functions directly
- [x] Add API endpoints for run history and artifact lookup
- [x] Add API integration tests for health, pipeline endpoints, and run queries
- [x] Add Docker packaging for API deployment
