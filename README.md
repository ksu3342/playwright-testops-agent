# Playwright TestOps Agent

[English](./README.en.md)

一个面向真实测试流程的 Playwright TestOps workflow backend：把需求输入转成可生成、可运行、可追踪、可报告的测试证据链。

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](./app/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Routes-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Playwright](https://img.shields.io/badge/Playwright-Integration-2EAD33?logo=playwright&logoColor=white)](./app/core/generator.py)
[![Pytest](https://img.shields.io/badge/Pytest-Tests-0A9EDC?logo=pytest&logoColor=white)](./tests/)
[![GitHub Actions CI](https://img.shields.io/badge/GitHub%20Actions-CI-2088FF?logo=github&logoColor=white)](./.github/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/Docker-Packaged-2496ED?logo=docker&logoColor=white)](./Dockerfile)

## Quick Start / 快速开始

```bash
python -m pip install -r requirements-core.txt
python -m pytest tests/integration/test_api.py -q
python -m uvicorn app.api.main:app --port 8000
```

更完整的中文 walkthrough 见 [README.zh-CN.md](./README.zh-CN.md)，英文版说明见 [README.en.md](./README.en.md)。

## 这个项目解决什么真实测试问题

真实测试流程里的输入往往来自 PRD、自由文本笔记或半结构化需求说明。这个仓库把这些输入收口成三类可检查产物：保守的 Playwright 测试脚手架、可追溯的运行产物，以及基于运行结果生成的缺陷报告草稿。重点不是堆平台概念，而是让每一步都有文件证据、状态诚实、便于人工接手。

## 目前已经做成了什么

- 可选 `normalize` 之后，主流程已经能走通 `parse -> extract -> generate -> run -> report`。
- CLI 已覆盖 `normalize`、`parse`、`generate`、`run`、`report` 这些入口。
- FastAPI 已提供 health、流程执行、run 查询和 artifact 查询接口。
- 生成脚手架、运行摘要与报告草稿都会在运行时落盘到 `generated/tests/`、`data/runs/` 和 `generated/reports/`。这些输出可以本地复现，但不会作为固定公开样例提交。
- 仓库里已经有 [Dockerfile](./Dockerfile)、[docker-compose.yml](./docker-compose.yml) 和 [API integration tests](./tests/integration/test_api.py)。

## 一个真实样例

下面的样例刻意改成“命令可复现”而不是“仓库里已有固定产物可点开”。公开 README 只链接已提交的源码、测试、contract 和输入 PRD。`generated/tests/`、`data/runs/`、`generated/reports/` 下的内容属于运行时产物，需要你本地生成。

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

- [app/core/generator.py](./app/core/generator.py)、[app/core/runner.py](./app/core/runner.py)、[app/core/selector_contract.py](./app/core/selector_contract.py) 实现了生成、运行状态判定和 selector contract 加载。
- [data/contracts/demo_app_selectors.json](./data/contracts/demo_app_selectors.json) 与 [data/contracts/demo_app_test_data.json](./data/contracts/demo_app_test_data.json) 让 selector 和 fixture 来源保持 file-backed。
- [demo_app/main.py](./demo_app/main.py) 是 executable login flow 使用的本地 demo target。
- [tests/unit/test_generator.py](./tests/unit/test_generator.py)、[tests/unit/test_runner.py](./tests/unit/test_runner.py)、[tests/demo/test_demo_app.py](./tests/demo/test_demo_app.py) 验证 generator、runner 和 demo app 行为。
- [tests/integration/test_api.py](./tests/integration/test_api.py) 与 [tests/integration/test_pipeline.py](./tests/integration/test_pipeline.py) 覆盖 API 和 pipeline 层集成路径。

## 为什么这样设计

- 当前实现仍然是 CLI-first，FastAPI 层只是对同一套 Python 核心函数的轻量包装。
- `normalize` 被刻意限定为可选前置步骤，也是当前唯一的 LLM 辅助步骤。
- 真正的确定性核心流程保持为 `parse -> extract -> generate -> run -> report`，便于解释和验证。
- 运行产物和报告继续直接落盘，避免为了这个仓库的当前范围引入额外基础设施。
- `/api/v1/run` 仍然保持同步执行，run 状态和 artifact 更容易核对。

## 范围与边界

- 当前实现仍然是 `CLI-first TestOps Agent MVP + thin FastAPI wrapper`。
- 当前持久化仍然是文件系统，不是 Redis、MySQL 或其他数据库驱动的平台。
- 这里没有前端、认证层、多 Agent 编排或完整测试平台的声称。
- KB 检索默认是 deterministic file-backed；可选 `langchain_local` 只是 LangChain Core `Document` / `BaseRetriever` 本地适配层，不是生产级向量库或 embedding pipeline。
- 这也不是队列驱动的异步执行系统或生产级平台。

## run_id 现在能证明什么

每个 run 产生的 `run_id` 在 `data/runs/<run_id>/summary.json` 中记录了完整证据链：

- `lineage.source_requirement`: 输入的 PRD 文件路径（如 `data/inputs/sample_prd_login.md`）
- `lineage.generated_script`: 生成的测试脚本路径（如 `generated/tests/test_login_generated.py`）
- `artifact_paths`: command.txt、stdout.txt、stderr.txt、summary.json 的路径
- `artifact_paths.screenshot`: Playwright 失败时的截图路径（如果有）
- `report_path`: bug report 的路径（如果生成了）

通过 API 查询：

```bash
# 查询 run 详情
GET /api/v1/runs/{run_id}

# 查询 artifacts
GET /api/v1/runs/{run_id}/artifacts
```

响应中会包含 `lineage`、`artifact_paths` 和 `report_path` 字段。

## CI 验证

[.github/workflows/ci.yml](./.github/workflows/ci.yml) 在每次 push 和 PR 到 main 时运行：

- 安装 core 和 e2e 依赖
- 安装 Playwright Chromium
- 运行 demo app tests
- 运行 unit tests
- 运行 integration tests
- 生成 login test
- 运行 generated login test
- 通过 CLI runner 运行 generated login test

## 进一步阅读

- 英文版说明：[README.en.md](./README.en.md)
- 更完整的中文 walkthrough：[README.zh-CN.md](./README.zh-CN.md)
- 技术规格：[SPEC.md](./SPEC.md)
- 历史路线图：[TASKS.md](./TASKS.md)
- 许可证：[LICENSE](./LICENSE)
