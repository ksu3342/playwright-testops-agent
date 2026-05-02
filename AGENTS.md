# AGENTS.md

本文件是这个仓库的长期执行上下文。每次在本项目里工作前先读它；如果它和当前源码冲突，以当前源码和测试为准，并在必要时更新本文件。

## 1. 工作方式

- 默认用中文回复，除非用户明确要求英文或需要写英文文档。
- 先做批判性判断，再执行。不要为了迎合用户而扩大能力描述；没有证据就写“无证据表明”。
- 先确认仓库根目录，再改文件。不要假设外层目录就是仓库。
- 不要静默切换仓库、解释器、模型或运行环境。
- 保护用户已有改动。`git status --short` 里已有的修改默认视为用户资产，不能回滚、覆盖或格式化无关文件。
- 如果上下文变长，优先把状态压缩到文件或 handoff 摘要，而不是硬撑长线程。

## 2. 仓库身份

- 真实仓库根目录是：
  `D:\AI agent\playwright-testops-agent\playwright-testops-agent`
- 外层目录：
  `D:\AI agent\playwright-testops-agent`
  不是 git 仓库，只是容器目录。
- 开始任何实质修改前，优先运行：

```powershell
git rev-parse --show-toplevel
Get-Location
git status --short
Resolve-Path app/main.py
```

- 如果 `rg.exe` 出现 `Access is denied`，直接改用 PowerShell：
  `Get-ChildItem -Recurse`、`Select-String`、`Get-Content -Encoding UTF8`。

## 3. 项目定位

- 项目名称：`Playwright TestOps Agent`
- 当前最稳妥表述：`CLI-first TestOps Agent MVP + thin FastAPI wrapper`。
- 核心价值不是“生产级测试平台”，而是把 PRD / 自由文本需求收口成可检查的测试证据链。
- 确定性主流程：
  `parse -> extract -> generate -> run -> report`
- `normalize` 是可选前置步骤，也是当前唯一允许的 LLM 辅助步骤。
- 对外包装时可以说：
  “保守生成、诚实执行状态、文件化 artifact、缺陷报告草稿、人工可接手。”
- 不要声称：
  生产级平台、多 Agent 平台、全自动测试决策、数据库驱动平台、队列调度系统、认证/权限系统、完整前端测试平台。

## 4. 主要目录

- `app/main.py`：CLI 入口，提供 `normalize`、`parse`、`generate`、`run`、`report`。
- `app/core/`：稳定核心流程。
  - `parser.py`：按固定 markdown heading 解析 PRD。
  - `extractor.py`：确定性抽取 happy path / 支持的 negative path。
  - `selector_contract.py`：加载 file-backed selector contract。
  - `generator.py`：生成 Playwright 脚手架；`/login` happy path 可生成可执行脚本。
  - `runner.py`：运行 pytest，输出 `passed` / `failed` / `blocked` / `environment_error`。
  - `collector.py`：保存 command/stdout/stderr/summary，并发现 screenshot/trace artifact。
  - `reporter.py`：只基于 failed run 生成 bug report draft。
- `app/api/`：FastAPI 薄包装层，直接调用核心函数。
- `app/agent/`：当前工作区已有 LangGraph 单流程编排层；本质是工具编排、审批 gate 和 trace，不要包装成多 Agent 平台。
- `app/rag/retriever.py`：确定性的本地文件检索，不是向量数据库，也不是外部 RAG 服务。
- `app/llm/`：`mock` 默认；`live` 只用于 normalize，配置不完整必须明确失败。
- `demo_app/main.py`：本地 demo target，提供 `/login`、`/dashboard`、`/search`。
- `data/contracts/`：selector 和 fixture 的唯一可信来源。
- `data/inputs/`：稳定样例 PRD / 自由文本输入。
- `data/runs/`、`data/api_inputs/`、`data/normalized/`、`data/agent_runs/`：运行时或本地生成产物。
- `generated/tests/`、`generated/reports/`：生成产物；README 中不要把它们当成稳定公开证据链来链接。
- `tests/`：真实约束主要在测试里，修改行为前先读相关测试。

## 5. 关键合同

- selector 必须来自 `data/contracts/demo_app_selectors.json`。不要动态读取 `demo_app/main.py` 来猜 locator。
- fixture 必须来自 `data/contracts/demo_app_test_data.json`。不要在 generator 里硬猜用户名、密码或业务数据。
- selector 缺失时使用显式阻塞标记：`SELECTOR_CONTRACT_MISSING`。
- 有 TODO、不完整 marker、缺失 selector contract 时，runner 应返回 `blocked`，不能假装执行成功。
- 环境缺依赖、缺浏览器、缺 pytest fixture 等返回 `environment_error`。
- 只有真实执行失败的 run 才生成 product bug report draft；`blocked`、`passed`、`environment_error` 不生成正常缺陷报告。
- run summary 里应保留 `artifact_paths`、`lineage`、`report_path` 等证据字段。
- API 层应保持薄包装，直接复用 Python core；不要绕过核心逻辑重新实现一套流程。

## 6. Agent 编排层边界

- `app/agent/tools.py` 将 core、retriever、reporter 包成可追踪工具。
- `app/agent/graph.py` 当前流程：
  `parse_requirement -> retrieve_testing_context -> draft_test_plan -> validate_test_plan -> generate_test -> run_test -> create_report(仅 failed)`
- manual 模式有三个审批 gate：
  `test_plan`、`execution`、`report`。
- trace 保存在 `data/agent_runs/<agent_run_id>/trace.json`。
- agent-run API 当前包括：
  - `POST /api/v1/agent-runs`
  - `POST /api/v1/agent-runs/{agent_run_id}/approvals`
  - `GET /api/v1/agent-runs/{agent_run_id}`
  - `GET /api/v1/agent-runs/{agent_run_id}/trace`
- 这层可以称为“human-in-the-loop workflow orchestration”，不要称为多智能体系统。

## 7. 本地命令

优先使用仓库虚拟环境，尤其是跑测试时：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

如果只需要安装依赖或写 README 命令，使用 PATH 稳定形式：

```powershell
python -m pip install -r requirements-core.txt
python -m pip install -r requirements-e2e.txt
python -m pytest -q
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Demo app：

```powershell
.\.venv\Scripts\python.exe -m demo_app.main
.\.venv\Scripts\python.exe -m pytest tests\demo\test_demo_app.py -q
```

## 8. 验证策略

- 改 core parser/extractor/generator/runner/reporter：
  先跑对应 `tests/unit/test_*.py`，再跑相关 integration。
- 改 API：
  跑 `tests/integration/test_api.py`。
- 改 agent 编排：
  跑 `tests/unit/test_agent_graph.py`、`tests/unit/test_agent_tools.py`、`tests/integration/test_agent_orchestrator.py`、`tests/integration/test_api.py`。
- 声称 generated login flow 可执行时，至少验证：

```powershell
.\.venv\Scripts\python.exe -m app.main generate --input data/inputs/sample_prd_login.md
.\.venv\Scripts\python.exe -m pytest generated/tests/test_login_generated.py -q
.\.venv\Scripts\python.exe -m app.main run generated/tests/test_login_generated.py
```

- 对 executable generated-test claim，不要只靠一次绿。优先重复跑，确保不是端口、线程或本地服务复用导致的偶然成功。
- 做 normalize 相关验证时，顺序必须串行：
  `normalize -> parse -> generate -> pytest`
  不要在新 normalized markdown 写完前读取旧 parser 结果。

## 9. README / 对外包装规则

- README 要证据优先：源码、测试、contract、可复现命令。
- 不要把 `generated/tests/`、`data/runs/`、`generated/reports/` 当成稳定公共证据来链接；这些是 runtime output。
- 登录样例和失败报告样例是两条独立证据链，不要写成一个假的连续端到端流程。
- HR / 业务主管第一眼最容易质疑的是“像玩具”，所以要优先修复可见证据链，而不是堆架构名词。
- 简历或面试表述要保守：强调测试流程数字化、结构化输出验证、artifact 追踪、FastAPI 薄包装、可选 LLM normalize。不要写“企业级平台”“多 Agent 自动测试系统”。

## 10. 禁止默认引入

除非用户明确要求，不要引入：

- Redis / MySQL / PostgreSQL
- 队列、worker、异步任务平台
- 登录认证、权限系统
- 前端 dashboard
- 多 Agent 重构
- 外部向量数据库
- 为了“显得企业级”的架构层

奥卡姆剃刀：如果文件系统 artifact、同步 API 和确定性工具链已经能解释需求，就不要加基础设施。

