# 文档信息架构整理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将仓库文档分为可核验的当前指南、技术参考和历史记录，使注册及账号操作的现行流程不再被过期方案混淆。

**Architecture:** 使用 `git mv` 保留每份已跟踪文档的历史，在 `docs/README.md` 给出唯一导航和权威顺序。当前资料收敛到按职责划分的目录，历史设计按时间和改造主题归档；通过源码入口、配置 schema 与路由测试校准四份核心流程文档，不改动业务实现。

**Tech Stack:** Markdown、Git、Python/Flask 源码、PostgreSQL 存储契约、现有 unittest 路由与配置测试。

**Spec:** `docs/superpowers/specs/2026-09-21-documentation-information-architecture-design.md`

## Global Constraints

- 不删除任何既有文档、数据库记录、日志或私有运行文件。
- 不修改注册、账号、Codex、数据库、WebUI 或部署逻辑。
- PostgreSQL 仍是唯一事实来源；文档不得把 JSON/TXT/兼容输出写成运行时回退。
- 当前流程的事实必须能追溯到现行代码、配置 schema 或测试契约。
- `docs/superpowers/specs/` 和 `docs/superpowers/plans/` 保持原路径，不移动、不重命名。
- 不暂存或覆盖既有未跟踪的 `core/` 私有运行文件。
- 所有新增和改写文档使用中文；配置键、API 路径、类名和函数名保持原始拼写。

## Review Focus

- README 或 Markdown 中任一旧路径必须在迁移后仍可解析到文件；此项由任务 4 的全仓 Markdown 链接扫描覆盖。
- 标为“当前”的注册说明必须反映 `webui/routes/jobs.py`、`core.registration_service` 与 dispatcher 的真实两驱动分发；此项由任务 2 的源码锚点检查覆盖。
- 标为“当前”的账号操作说明必须说明 durable operation 与 `account_action_*` 投影的兼容边界；此项由任务 2 的运行时和存储锚点检查覆盖。
- `core/chatgpt_bootstrap.py` 的协议参考路径必须在移动 HAR 文档与 JSON 后仍有效；此项由任务 4 的精确引用检查覆盖。
- 归档不得改变历史设计结论或验收数值，更不得误称为本次测试结果；此项由任务 3 的移动前后文件内容检查覆盖。

---

### Task 1: 建立文档导航和目标目录

**Files:**
- Create: `docs/README.md`
- Create: `docs/architecture/.gitkeep`
- Create: `docs/workflows/.gitkeep`
- Create: `docs/development/.gitkeep`
- Create: `docs/reference/.gitkeep`
- Create: `docs/history/2026-08-project-refactor/.gitkeep`
- Create: `docs/history/2026-08-registration-design/.gitkeep`
- Create: `docs/history/2026-09-account-auth-design/.gitkeep`
- Create: `docs/history/2026-09-optimization/.gitkeep`

**Interfaces:**
- Consumes: 规格第 3、4 节的权威顺序和目录映射。
- Produces: 所有后续文档可链接的稳定目录，以及当前资料和历史资料的首页入口。

- [ ] **Step 1: 验证当前缺少文档导航**

Run: `test -f docs/README.md`

Expected: 退出码为非零，证明尚无目录级导航。

- [ ] **Step 2: 创建目录和 `docs/README.md`**

首页必须包含“当前/参考/历史”的含义、代码优先的冲突裁决顺序、注册/账号操作/Codex/存储/开发验证的当前入口，以及 `history/` 与 `superpowers/` 的保留理由。不得列出私有运行目录、真实账号或凭据文件。

- [ ] **Step 3: 验证导航完整性**

Run: `rg -n '^# |当前资料|历史记录|superpowers|权威顺序' docs/README.md && find docs -type d | sort`

Expected: 首页含有标题和三类文档说明；九个目标目录均存在。

### Task 2: 迁移并重写当前架构与业务流程文档

**Files:**
- Move: `docs/current-architecture.md` -> `docs/architecture/current-architecture.md`
- Move: `docs/storage-architecture.md` -> `docs/architecture/storage-architecture.md`
- Move: `docs/code-conventions.md` -> `docs/architecture/code-conventions.md`
- Move: `docs/compatibility-inventory.md` -> `docs/architecture/compatibility-inventory.md`
- Move: `docs/core-registration-flow.md` -> `docs/workflows/registration.md`
- Move: `docs/registration-auth-support-matrix.md` -> `docs/workflows/account-auth-support-matrix.md`
- Move: `docs/codex-operation-architecture.md` -> `docs/workflows/codex-oauth-operation.md`
- Move: `docs/optimization-release.md` -> `docs/development/release-verification.md`
- Create: `docs/workflows/account-operations.md`

**Interfaces:**
- Consumes: Task 1 的首页路径，`webui/routes/jobs.py:api_jobs_create`，`core/registration_service.submit_registration`，`core/registration_service._run_one_job`，`core/registration/dispatcher.run_registration`，`webui/runtime.start_runtime`，`core/operations/task_gateway.py`，`core/storage/operation.py` 与 `core/codex_operation_service.py`。
- Produces: 首页可引用的现行架构、注册、账号操作、认证、Codex 和发布指南。

- [ ] **Step 1: 固化现行代码锚点**

Run: `rg -n 'def (api_jobs_create|submit_registration|_run_one_job|run_registration|start_runtime)' webui/routes/jobs.py core/registration_service.py core/registration/dispatcher.py webui/runtime.py && rg -n 'operation_tasks|operation_runs|account_action_' core/storage/operation.py core/operations/task_gateway.py`

Expected: 能定位注册入口、运行时恢复入口和 durable/兼容任务存储边界。

- [ ] **Step 2: 使用 `git mv` 移动八份当前文档**

按本任务 Files 列表移动，保留 Git 历史。不得采用复制后删除的方式，不得移动 `docs/superpowers/` 的任意文件。

- [ ] **Step 3: 重写当前架构与注册流程的易漂移内容**

`architecture/current-architecture.md` 删除 2026-08-26 的规模统计、96 条路由和过期测试数量，改写为稳定的分层、入口、数据事实来源与兼容边界；明确当前路由契约由 `tests/test_route_contract.py` 固定为 121 条。`workflows/registration.md` 必须描述 `/api/jobs` -> `submit_registration` -> `_run_one_job` -> dispatcher -> Roxy 或 Protocol 的链路，保留注册续跑、邮箱来源、代理租约和可选后置步骤的边界。

- [ ] **Step 4: 写入当前账号操作与 Codex 说明**

新建 `workflows/account-operations.md`，定义逻辑任务、run、事件、资源和恢复的关系，说明 `account_action_*` 仍为兼容来源并投影到 operation 表。校准 `workflows/codex-oauth-operation.md`：`core.codex_operation_service` 是新操作入口，`core.codex_retry_service` 是保留的兼容入口；成功凭证、执行状态和最近结果分离，重跑新增 run。

- [ ] **Step 5: 校准认证和开发验证文档**

`workflows/account-auth-support-matrix.md` 保持公开配置唯一矩阵，明确 `OPENAI_PROTOCOL_VERSION` 是现行配置，`ACCOUNT_TOKEN_REFRESH_DRIVER`、`ACCOUNT_AUTH_V2_ENABLED` 和 `protocol_v2` 是历史兼容名称。`development/release-verification.md` 只保留可复用验证方法；一次性性能数字改成历史证据链接，不能表述为此次执行结果。

- [ ] **Step 6: 验证当前文档与源码锚点一致**

Run: `rg -n 'api_jobs_create|submit_registration|_run_one_job|run_registration|REGISTRATION_DRIVER|operation_runs|account_action_|start_runtime|OPENAI_PROTOCOL_VERSION' docs/architecture docs/workflows docs/development`

Expected: 当前注册、账号、Codex 和认证文档均包含可定位的真实入口；不再出现“96 条路由”或“未修改业务代码”。

### Task 3: 归档历史设计、实施计划和验收记录

**Files:**
- Move to `docs/history/2026-08-project-refactor/`: `admin-data-architecture.md`, `refactor-roadmap.md`, `ui-audit-2026-08-14.html`
- Move to `docs/history/2026-08-registration-design/`: `registration-implementation-plan.md`, `registration-parallel-workstreams.md`, `registration-refactor-master-design.md`, `registration-refactor-plan-index.md`, `registration-retry-progress-and-otp-design.md`, `registration-state-refactor-design.md`, `registration-test-migration-rollout.md`, `task-log-unification-design.md`, `unified-task-center-architecture.md`
- Move to `docs/history/2026-09-account-auth-design/`: `account-auth-liveness-fingerprint-design.md`, `account-auth-liveness-fingerprint-implementation-design.md`, `account-auth-protocol-staged-rollout-checklist.md`, `registration-account-config-redesign.md`
- Move to `docs/history/2026-09-optimization/`: `optimization-auth.md`, `optimization-config.md`, `optimization-maintenance.md`, `optimization-status.md`, `optimization-storage.md`, `optimization-tasks.md`, `optimization-token-refresh.md`

**Interfaces:**
- Consumes: Task 1 的历史目录和规格第 4.3、5 节的归档清单。
- Produces: 位置明确、不再参与当前行为裁决的历史资料包。

- [ ] **Step 1: 捕获归档前的内容指纹**

Run: `git ls-files 'docs/*.md' 'docs/*.html' | sort | xargs shasum -a 256`

Expected: 获得移动前每份已跟踪根目录资料的 SHA-256，用于验证归档只改变允许添加的历史标记和链接。

- [ ] **Step 2: 使用 `git mv` 按四个历史主题移动文件**

严格按本任务 Files 列表执行，逐份移动文件。不删除目录，不执行任何递归删除命令。

- [ ] **Step 3: 为每份历史 Markdown 添加统一状态说明**

在标题后添加一行说明：该文件是历史设计、实施计划或验收记录，不作为现行运行规则；现行入口为 `docs/README.md`。已有明确状态、日期、测试数值和设计结论保持原文不改。

- [ ] **Step 4: 验证归档边界**

Run: `find docs/history -type f | sort && rg -L '历史.*不作为现行' docs/history --glob '*.md'`

Expected: 四个历史目录包含清单中的文件；第二条命令无输出，证明每份归档 Markdown 有状态说明。

### Task 4: 移动协议参考并修复全仓文档链接

**Files:**
- Move: `docs/protocol_fingerprint_har_analysis.md` -> `docs/reference/protocol-fingerprint-har-analysis.md`
- Move: `docs/protocol_har_summary.json` -> `docs/reference/protocol-har-summary.json`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `core/chatgpt_bootstrap.py`
- Modify: `tools/analyze_har_protocol.py`
- Modify: all moved Markdown files whose relative links change

**Interfaces:**
- Consumes: Task 1 的导航、Task 2 的当前路径和 Task 3 的历史路径。
- Produces: 全仓库不含已移动 `docs/` 旧路径的有效交叉引用，且 HAR 参考路径仍可定位。

- [ ] **Step 1: 验证协议参考的当前代码依赖**

Run: `rg -n 'protocol_fingerprint_har_analysis|protocol_har_summary' core/chatgpt_bootstrap.py tools/analyze_har_protocol.py README.md docs`

Expected: 显示 `core/chatgpt_bootstrap.py` 和 HAR 工具的现有引用，作为迁移后更新目标。

- [ ] **Step 2: 使用 `git mv` 移动 HAR Markdown 与 JSON**

移动到 `docs/reference/`，更新 `core/chatgpt_bootstrap.py` 的说明注释和工具默认输出路径，使文件名与实际新路径一致。

- [ ] **Step 3: 更新 README、AGENTS 和所有相对链接**

README 保持面向操作的说明，更新其存储、认证矩阵和发布验证链接。AGENTS 的存储架构链接改为新路径。所有 moved Markdown 中的绝对工作区路径改为相对链接；历史文档中的原始决策文字保持不变，仅调整链接目标。

- [ ] **Step 4: 执行全仓内部 Markdown 链接检查**

Run the following read-only command from the repository root:

```bash
python - <<'PY'
from pathlib import Path
import re

root = Path.cwd()
bad = []
for source in [root / 'README.md', root / 'AGENTS.md', *root.glob('docs/**/*.md')]:
    text = source.read_text(encoding='utf-8')
    for target in re.findall(r'\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)', text):
        if target.startswith(('http://', 'https://', 'mailto:')):
            continue
        path = Path(target)
        resolved = path if path.is_absolute() else (source.parent / path)
        if not resolved.exists():
            bad.append(f'{source.relative_to(root)} -> {target}')
if bad:
    raise SystemExit('\n'.join(bad))
PY
```

Expected: 退出码为 0；不存在失效的仓库内 Markdown 链接。

### Task 5: 全量文档审阅与最小回归验证

**Files:**
- Modify: `docs/README.md` only if Task 4 reveals a changed target path
- Test: `tests/test_route_contract.py`
- Test: `tests/test_config_defaults.py`
- Test: `tests/test_release_checks.py`

**Interfaces:**
- Consumes: Tasks 1-4 产出的最终路径、流程说明和链接图。
- Produces: 可交付的文档结构、验证证据和明确的未执行范围。

- [ ] **Step 1: 检查当前与历史资料的边界**

Run: `find docs -maxdepth 2 -type f | sort && rg -n '96 条路由|未修改业务代码|唯一.*入口.*codex_retry_service' docs README.md AGENTS.md || true`

Expected: 当前目录中没有过期架构统计、过期注册索引结论或把兼容 Codex 服务称为唯一入口的表述。

- [ ] **Step 2: 运行链接、格式和重复标题检查**

Run: Task 4 的 Markdown 链接检查命令; then `git diff --check`; then `rg -n '^# ' docs README.md AGENTS.md | sort`

Expected: 链接检查和 `git diff --check` 均成功；一级标题能清楚区分当前入口、参考和历史资料。

- [ ] **Step 3: 运行文档所依据的最小代码契约测试**

Run: `python -m unittest tests.test_route_contract tests.test_config_defaults tests.test_release_checks -v`

Expected: 三个模块通过，证明文档引用的当前路由数量、配置矩阵和健康/就绪发布门槛仍由测试保护。

- [ ] **Step 4: 核对 Git 变更范围和私有文件边界**

Run: `git status --short && git diff --name-status HEAD~1..HEAD && git diff --name-status`

Expected: 本次工作只包含 README、AGENTS、`docs/` 和用于修正参考路径的 `core/chatgpt_bootstrap.py` / `tools/analyze_har_protocol.py`；既有 `core/` 未跟踪私有文件保持未暂存、未修改。

- [ ] **Step 5: 提交文档整理变更**

Run: `git add README.md AGENTS.md docs core/chatgpt_bootstrap.py tools/analyze_har_protocol.py && git commit -m "docs: 整理当前流程与历史设计文档"`

Expected: 只提交本计划列出的追踪文件；不推送、不重启服务、不执行真实注册或数据库迁移。
