# Playwright TestOps Agent（测试工程原型）

[English](./README.en.md)

一个范围清楚、能跑通、能解释清楚的 TestOps 工程原型：把需求输入收口为保守的 Playwright 测试脚手架、本地运行记录与缺陷报告草稿。

[![Python Backend](https://img.shields.io/badge/Python-Backend-3776AB?logo=python&logoColor=white)](./app/core/)
[![FastAPI Wrapper](https://img.shields.io/badge/FastAPI-Thin%20Wrapper-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Playwright Scaffold](https://img.shields.io/badge/Playwright-Scaffold%20Generation-2EAD33?logo=playwright&logoColor=white)](./app/core/generator.py)
[![Docker Packaged](https://img.shields.io/badge/Docker-Packaged-2496ED?logo=docker&logoColor=white)](./Dockerfile)
[![Pytest Integration Tested](https://img.shields.io/badge/Pytest-Integration%20Tested-0A9EDC?logo=pytest&logoColor=white)](./tests/integration/test_api.py)
[![Honest Scope MVP](https://img.shields.io/badge/MVP-Honest%20Scope-6B7280)](./SPEC.md)

## Quick Start / 快速开始

```bash
pip install -r requirements-core.txt
pytest tests/integration/test_api.py -q
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

更完整的中文说明见 [README.zh-CN.md](./README.zh-CN.md)，英文版说明见 [README.en.md](./README.en.md)。

## 这个项目在做什么

这是一个 `CLI-first TestOps Agent MVP + thin FastAPI wrapper`。它把需求输入收口到一条范围清楚的主流程里：可选的 `normalize` 之后，进入确定性核心流程 `parse -> extract -> generate -> run -> report`。重点不是尽可能堆功能，而是让流程可运行、可检查、可解释。

## 目前做到了什么

- CLI 已经覆盖 `normalize`、`parse`、`generate`、`run`、`report` 这些入口。
- FastAPI 包装层已经存在，包含健康检查、流程执行、run 查询和 artifact 查询。
- 运行产物仍然是文件型持久化，落在 [data/runs](./data/runs/) 和 [generated/reports](./generated/reports/)。
- `/api/v1/run` 仍然是同步执行，不依赖队列、worker 或数据库。
- 仓库里已经有 [Dockerfile](./Dockerfile)、[docker-compose.yml](./docker-compose.yml) 和 [API integration tests](./tests/integration/test_api.py)。

## 为什么这样设计

- `normalize` 被刻意限定为可选前置步骤，也是当前唯一的 LLM-assisted step，这样可以把不确定性收窄在流程入口。
- 真正的核心流程保持为 `parse -> extract -> generate -> run -> report`，便于解释和验证。
- run artifacts 和 reports 继续直接落盘，避免为了这个 MVP 引入额外基础设施。
- FastAPI 层只是 thin wrapper，直接复用同一套 Python core functions，而不是把项目重写成另一套系统。

## 工程证据

- [app/core/](./app/core/) 中已经有 parser、extractor、generator、runner、reporter、normalizer 这些核心模块。
- [app/api/main.py](./app/api/main.py) 中已经定义了 `/healthz`、`/api/v1/*`、run 查询和 artifact 查询路由。
- [tests/integration/test_api.py](./tests/integration/test_api.py) 覆盖了 health、normalize、generate -> run、run -> report、run lookup、坏 summary 跳过和 `404` 场景。
- [Dockerfile](./Dockerfile) 使用 `uvicorn app.api.main:app` 作为服务入口，[docker-compose.yml](./docker-compose.yml) 提供本地运行配置。
- [data/runs](./data/runs/) 与 [generated/reports](./generated/reports/) 是当前仓库里实际存在的 artifact 存储位置。

## 边界 / 不做什么

- 它是一个 CLI-first 的工程原型，不是 production-grade platform。
- `normalize` 是可选步骤，而不是把整个流程都改造成 LLM 驱动系统。
- `/api/v1/run` 仍然是同步执行，不是 queue-backed async execution service。
- 当前持久化仍然是文件系统，不是 Redis、MySQL 或其他数据库驱动的平台。
- 这里没有前端、认证层、多 Agent 编排或完整测试平台的声称。

## 进一步阅读

- 英文版说明：[README.en.md](./README.en.md)
- 更完整的中文说明：[README.zh-CN.md](./README.zh-CN.md)
- 技术规格：[SPEC.md](./SPEC.md)
- 历史路线图：[TASKS.md](./TASKS.md)
- 许可证：[LICENSE](./LICENSE)
