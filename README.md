# Playwright TestOps Agent

[English](./README.en.md)

一个面向真实测试流程的 Playwright 工作流项目：把需求说明收口为可检查的测试脚手架、本地运行记录和缺陷报告草稿。

[![Python Backend](https://img.shields.io/badge/Python-Backend-3776AB?logo=python&logoColor=white)](./app/core/)
[![FastAPI Routes](https://img.shields.io/badge/FastAPI-Routes-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Playwright Scaffolds](https://img.shields.io/badge/Playwright-Scaffolds-2EAD33?logo=playwright&logoColor=white)](./generated/tests/)
[![File-Backed Artifacts](https://img.shields.io/badge/File--Backed-Artifacts-4B5563)](./data/runs/)
[![Pytest Integration Tested](https://img.shields.io/badge/Pytest-Integration%20Tested-0A9EDC?logo=pytest&logoColor=white)](./tests/integration/test_api.py)
[![Docker Packaged](https://img.shields.io/badge/Docker-Packaged-2496ED?logo=docker&logoColor=white)](./Dockerfile)

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
- 生成脚手架、运行摘要与报告草稿都会直接落盘到 [generated/tests](./generated/tests/)、[data/runs](./data/runs/) 和 [generated/reports](./generated/reports/)。
- 仓库里已经有 [Dockerfile](./Dockerfile)、[docker-compose.yml](./docker-compose.yml) 和 [API integration tests](./tests/integration/test_api.py)。

## 一个真实样例

下面用两条独立证据链展示当前仓库里的真实输出。它们不是同一条连续的 end-to-end run，而是分别证明“PRD -> 脚手架生成 -> blocked run”与“failure-path run -> bug report draft”这两段行为。

### 样例 A：PRD -> generated scaffold -> blocked run

1. 输入 PRD：[data/inputs/sample_prd_login.md](./data/inputs/sample_prd_login.md)

```md
## Feature Name
User Login

## Page URL
/login
```

2. 生成脚手架：[generated/tests/test_login_generated.py](./generated/tests/test_login_generated.py)

```python
# Generated from: Login Page PRD
target_url = BASE_URL.rstrip("/") + "/login"
page.goto(target_url)
# TODO: Locate the relevant input selector before implementing...
```

3. 对生成脚手架的诚实运行状态：[data/runs/20260422T143848670135Z_test_login_generated/summary.json](./data/runs/20260422T143848670135Z_test_login_generated/summary.json)

```json
"status": "blocked",
"reason": "Script contains incomplete implementation markers (TODO) and is not ready for honest execution."
```

### 样例 B：独立 failure-path run -> bug report draft

这一步已经切换到另一条独立证据链，不再沿用上面的 `sample_prd_login.md` / `test_login_generated.py` 链路。

1. 失败 run 的记录：[summary.json](./data/runs/20260422T143848683010Z_runner_fail_case/summary.json)

2. 对应的报告草稿：[bug report draft](./generated/reports/bug_report_20260422T143848683010Z_runner_fail_case.md)

```text
status: failed
FAILED tests/assets/runner_fail_case.py::test_minimal_fail_case - assert 1 == 2
```

## 工程证据

- [app/core/](./app/core/) 中已经有 parser、extractor、generator、runner、reporter、normalizer 这些核心模块。
- [app/api/main.py](./app/api/main.py) 中已经定义了 `/healthz`、`/api/v1/*`、run 查询和 artifact 查询路由。
- [tests/integration/test_api.py](./tests/integration/test_api.py) 覆盖了 health、normalize、generate -> run、run -> report、run lookup、坏 summary 跳过和 `404` 场景。
- [data/runs](./data/runs/) 与 [generated/reports](./generated/reports/) 是当前仓库里实际存在的产物目录。
- [Dockerfile](./Dockerfile) 使用 `uvicorn app.api.main:app` 作为服务入口，[docker-compose.yml](./docker-compose.yml) 提供本地运行配置。

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
- 这也不是队列驱动的异步执行系统或生产级平台。

## 进一步阅读

- 英文版说明：[README.en.md](./README.en.md)
- 更完整的中文 walkthrough：[README.zh-CN.md](./README.zh-CN.md)
- 技术规格：[SPEC.md](./SPEC.md)
- 历史路线图：[TASKS.md](./TASKS.md)
- 许可证：[LICENSE](./LICENSE)
