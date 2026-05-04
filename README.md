# Playwright TestOps Agent

[English](./README.en.md)

一个本地 file-backed 的 TestOps Agent workflow 原型：将测试任务转为可检索、可审核、可执行、可追踪的测试证据链。

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](./app/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Routes-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Playwright](https://img.shields.io/badge/Playwright-Integration-2EAD33?logo=playwright&logoColor=white)](./app/core/generator.py)
[![Pytest](https://img.shields.io/badge/Pytest-Tests-0A9EDC?logo=pytest&logoColor=white)](./tests/)
[![GitHub Actions CI](https://img.shields.io/badge/GitHub%20Actions-CI-2088FF?logo=github&logoColor=white)](./.github/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/Docker-Packaged-2496ED?logo=docker&logoColor=white)](./Dockerfile)

## 当前 Agent 主线

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

## 当前已实现

- local demo web target
- selector contract and test data contract
- file-backed KB retrieval and retrieval quality evals
- approved `test_plan.json` drives Playwright test generation
- approve / reject / `resume_state` based human approval gate
- generated login test and runner artifacts
- failed run report draft
- `trace.json` / `decision_trace`
- FastAPI thin wrapper
- GitHub Actions CI

## 底层确定性工具链

Agent 不直接操作文件，而是调用受控工具链：

```text
normalize -> parse -> extract -> generate -> run -> report
```

这条工具链仍然可以作为 CLI / API 单独使用；在 Agent 路径里，它是可审查节点背后的确定性执行能力。

## Quick Start / 快速开始

```bash
python -m pip install -r requirements-core.txt
python -m pytest tests/integration/test_api.py -q
python -m uvicorn app.api.main:app --port 8000
```

更完整的中文 walkthrough 见 [README.zh-CN.md](./README.zh-CN.md)，英文版说明见 [README.en.md](./README.en.md)，固定 Agent demo 见 [docs/agent_demo_walkthrough.md](./docs/agent_demo_walkthrough.md)。

## 这个项目解决什么真实测试问题

真实测试流程里的输入往往来自 PRD、自由文本笔记或半结构化需求说明。这个仓库把这些输入收口成可检索上下文、可审核测试计划、保守的 Playwright 测试脚手架、可追溯运行产物，以及基于失败运行生成的缺陷报告草稿。重点不是堆平台概念，而是让每一步都有文件证据、状态诚实、便于人工接手。

## 一个真实样例

下面的样例刻意改成“命令可复现”而不是“仓库里已有固定产物可点开”。公开 README 只链接已提交的源码、测试、contract、docs 和输入 PRD。`generated/tests/`、`data/runs/`、`generated/reports/` 下的内容属于运行时产物，需要你本地生成。

### 样例 A：PRD -> generated login test -> 本地运行

1. 输入 PRD：[data/inputs/sample_prd_login.md](./data/inputs/sample_prd_login.md)

```md
## Feature Name
User Login

## Page URL
/login
```

2. 稳定实现证据：[app/core/generator.py](./app/core/generator.py)、[app/core/selector_contract.py](./app/core/selector_contract.py)、[data/contracts/demo_app_selectors.json](./data/contracts/demo_app_selectors.json)、[data/contracts/demo_app_test_data.json](./data/contracts/demo_app_test_data.json)、[tests/unit/test_generator.py](./tests/unit/test_generator.py)

3. 在本地复现 generated login test：

```powershell
python -m app.main generate --input data/inputs/sample_prd_login.md
python -m pytest generated/tests/test_login_generated.py -q
python -m app.main run generated/tests/test_login_generated.py
```

生成出的脚本和 run 目录都是 runtime output，公开仓库不会把它们作为固定样例文件提交。

### 样例 B：独立 failure-path run -> report draft

这一步切换到另一条独立证据链，不再沿用上面的 login 生成链路。

1. 稳定失败路径证据：[tests/assets/runner_fail_case.py](./tests/assets/runner_fail_case.py)、[app/core/runner.py](./app/core/runner.py)、[tests/integration/test_pipeline.py](./tests/integration/test_pipeline.py)、[tests/integration/test_api.py](./tests/integration/test_api.py)

2. 在本地复现 failure-path run 和报告生成：

```powershell
python -m app.main run --input tests/assets/runner_fail_case.py
python -m app.main report --input data/runs/<run_id>
```

`generated/reports/` 下的报告文件同样属于 runtime output，而不是公开仓库里的固定样例。

## 工程证据

- [app/agent/tools.py](./app/agent/tools.py)、[app/agent/graph.py](./app/agent/graph.py)、[app/agent/tracer.py](./app/agent/tracer.py) 实现 Agent tools、workflow graph、trace / resume_state。
- [app/rag/retriever.py](./app/rag/retriever.py)、[tests/evals/test_rag_retrieval_quality.py](./tests/evals/test_rag_retrieval_quality.py) 覆盖 file-backed retrieval 和 retrieval quality eval。
- [data/contracts/demo_app_selectors.json](./data/contracts/demo_app_selectors.json) 与 [data/contracts/demo_app_test_data.json](./data/contracts/demo_app_test_data.json) 让 selector 和 fixture 来源保持 file-backed。
- [demo_app/main.py](./demo_app/main.py) 是 executable login flow 使用的本地 demo target。
- [docs/agent_demo_walkthrough.md](./docs/agent_demo_walkthrough.md) 是固定 golden demo，覆盖 task text、approval、plan-driven generation、run evidence、report draft 和 trace review。
- [tests/integration/test_agent_golden_demo.py](./tests/integration/test_agent_golden_demo.py)、[tests/integration/test_api.py](./tests/integration/test_api.py)、[tests/integration/test_pipeline.py](./tests/integration/test_pipeline.py) 覆盖 Agent、API 和 pipeline 层集成路径。

## 范围与边界

- 当前实现仍然是 `CLI-first TestOps Agent MVP + thin FastAPI wrapper`。
- 当前持久化仍然是文件系统，不是 Redis、MySQL 或其他数据库驱动的平台。
- 当前 retrieval 是 deterministic file-backed；可选 `langchain_local` 只是 LangChain Core `Document` / `BaseRetriever` 本地适配层，不是向量数据库或 embedding pipeline。
- 当前 checkpoint 是 `trace.json + resume_state`，不是 LangGraph-native durable execution。
- 可选 LLM-assisted planning 只生成可审核 JSON；不执行测试、不选择 selector、不控制浏览器、不自动发布缺陷。
- 当前 API 仅用于本地原型演示，不包含认证、执行沙箱、权限隔离或生产级执行安全加固。
- 这里没有前端、认证层、多 Agent 编排、队列 worker 或 autonomous browser-control agent 的声称。

## CI 验证

[.github/workflows/ci.yml](./.github/workflows/ci.yml) 在每次 push 和 PR 到 main 时运行 demo app tests、unit tests、integration tests、RAG retrieval evals、Agent golden demo、generated login test 和 CLI runner 验证。

## 进一步阅读

- 英文版说明：[README.en.md](./README.en.md)
- 更完整的中文 walkthrough：[README.zh-CN.md](./README.zh-CN.md)
- Agent golden demo：[docs/agent_demo_walkthrough.md](./docs/agent_demo_walkthrough.md)
- 技术规格：[SPEC.md](./SPEC.md)
- 历史路线图：[TASKS.md](./TASKS.md)
- 许可证：[LICENSE](./LICENSE)
