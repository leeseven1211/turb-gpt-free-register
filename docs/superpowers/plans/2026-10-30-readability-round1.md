# 第一轮代码阅读整理实施计划

> 代理执行要求：使用 `superpowers:subagent-driven-development`，按任务验证并独立审查。

**目标：** 补齐功能阅读导航，归位提链查询展示实现，拆分账号页独立功能块。

**架构：** 保留现有分层和公共入口；纯查询展示进入 `core/extract_link/`；前端沿用普通脚本。
后端、前端、文档按互不重叠的文件范围并行实现，由协调者统一提交与验证。

**技术栈：** Python 3.10+、Flask、PostgreSQL、普通 JavaScript、pytest、Node.js。

**设计：** [第一轮设计](../specs/2026-10-30-readability-round1-design.md)。

## 全局约束

- 所有新增说明、注释、文案使用中文；不执行 `rm -r` 或 `rm -rf`。
- 不修改注册主流程、业务执行行为、任务重跑规则、存储实现、配置及私有数据。
- 保持公共函数参数、返回字段、HTTP 契约、查询次数、事件绑定及页面交互。
- 所有 Python 测试使用统一隔离入口、非生产数据库和 `test_` schema。
- 工作者只修改任务拥有的文件，不提交，不重启服务，不派生代理；协调者串行提交。
- 优先复用已有行为测试；本轮是行为保持的重构，不新增只验证文件拆分方式的测试。

## Task 1: 提链工作台查询展示归位

**文件：** 新增 `core/extract_link/__init__.py`、`core/extract_link/workbench_queries.py`；
修改 `core/extract_link_service.py`，必要时调整现有 `tests/test_extract_workbench_*.py`。

**接口：** 保留 `list_workbench_tasks`、`preview_workbench_candidates`、
`list_workbench_batches`、`workbench_batch_detail`、`extract_workbench_task_detail` 的原签名。
保持已有私有展示函数兼容调用，不通过新模块反向导入服务来获得依赖。

- [x] 运行查询、状态、错误详情、批次与路由定向测试，记录基线。
- [x] 按 AST 函数边界移动查询/展示函数及其纯依赖，保留原函数的入口委托。
- [x] 保留 `_provider_status_label` 等若仍被执行逻辑调用的旧入口；对跨模块依赖显式导入。
- [x] 检查新模块无创建任务、更新状态、调用平台或启动 worker 的逻辑。
- [x] 重跑定向测试并检查变动函数的行为等价性，报告行数、命令和结果。

验证命令（使用协调者提供的测试连接环境）：

```bash
python tools/test_isolated.py --profile all -- tests/test_extract_workbench_query.py tests/test_extract_workbench_status_semantics.py tests/test_extract_workbench_error_details.py tests/test_extract_workbench_batches.py tests/test_extract_workbench_routes.py -q
```

## Task 2: 账号页面功能块拆分

**文件：** `webui/static/js/modern/accounts.js`、新增 `account-tasks.js`、
`account-email-change.js`、`account-inspection.js`、`webui/templates/index.html`；
维护读取上述脚本的现有 `.cjs`/Python 测试及必要的测试读取辅助文件。

**接口：** 原全局函数名、共享状态、HTML 事件和 API 调用保持一致。
新脚本位于账号列表脚本之后、bootstrap 之前；版本标识使用 `20261030-readability-v1`。

- [x] 盘点函数和顶层语句依赖，先运行相关 Node/Python 行为测试。
- [x] 按任务中心、换邮箱、巡检移动完整功能块，保留原逻辑；说明各文件职责和共享依赖。
- [x] 更新模板加载顺序和缓存版本。确认没有跨文件顶层声明初始化顺序错误。
- [x] 将受影响测试的源码读取调整为页面实际加载组合，保留现有断言，避免复制实现进测试。
- [x] 运行所有受影响 `.cjs` 测试以及账号筛选、操作取消、换邮箱、巡检、脚本与页面契约测试。
- [x] 报告原/新文件行数、覆盖范围及浏览器待验收清单。

基础验证命令：

```bash
python tools/test_isolated.py --profile all -- tests/test_webui_script.py tests/test_account_search_api.py tests/test_account_multi_filters.py tests/test_account_task_cancel_ui.py tests/test_email_change_ui.py tests/test_account_inspection.py tests/test_task_dialog_layout.py -q
```

## Task 3: 完善现有阅读与测试导航

**文件：** `README.md`、`docs/README.md`、`docs/architecture/functional-map.md`、
`docs/architecture/functional-map.json`、`docs/architecture/code-conventions.md`。

**接口：** 沿用 JSON version 1 的 flow 字段，新增工作台/账号页/任务中心的实际路径。
只记录已存在或本轮确认新增的实现；不把兼容门面描述为已独立的真实实现。

- [x] 补齐提链与账号页面从入口到实现、存储和测试的阅读路线。
- [x] 更新 README 路由/前端树、docs 索引和代码规范中的脚本加载说明。
- [x] 保留既有功能地图条目，新增条目按当前配置 schema 和真实测试路径填写。
- [x] 运行功能地图测试，检查修改 Markdown 的标题、相对链接、重复描述和旧引用。

```bash
python tools/test_isolated.py --profile all -- tests/test_functional_map.py -q
```

## 整体验证与交付

- [x] 分别审查三个任务的需求符合性和代码质量，再审查跨模块集成。
- [x] 执行 `ruff check .`、定向与相邻回归，检查前端语法及模板脚本依赖。
- [x] 用真实浏览器验证只读交互及控制台错误，记录证据。
- [ ] 对本轮文件创建 Conventional Commits 提交，保留主工作区已有修改并合回 main。
- [ ] 使用现有服务管理方式重启，核对 PID、cwd、端口、日志、healthz/readyz/login。
- [ ] 最终区分本地修改、测试、提交、推送、重启与真实流程验收；归档已完成工作区。

## 已完成的验证记录

- 基线为 `42d3298`；已合入同时期 main 的 `53c3a47`，保留其独立改动。
- 后端查询归位前后均通过 114 项测试和 171 项子测试；相邻执行路径通过 88 项测试和 45 项子测试。
- 合并后的最终定向 Python 验证通过 134 项测试和 174 项子测试；Node.js 前端回归通过 378 项；`ruff check .` 与 `git diff --check` 通过。
- 13 个搬迁的查询/展示函数经过 AST 等价核对，原服务其余 90 个函数保持不变。基线与当前实际路由均为 167 条，路径、方法和 endpoint 摘要一致。
- 三个任务及最终集成均完成独立审查。前端审查发现的 Escape 捕获顺序问题已修正，新增回归在修正前失败、修正后通过。
- 真实浏览器在独立测试数据库中验证账号列表、搜索、详情、换邮箱弹窗、巡检弹窗及历史、任务详情与日志、提链批次/筛选/详情；最终刷新无新增控制台错误。未提交真实注册、提链或支付任务。
- 扩展验证存在 10 项既有失败（dashboard 9 项、路由计数契约 1 项），均在原始 `42d3298` 复现。涉及邮箱源可用性/数量、隔离夹具缺少旧任务表、列筛选数量旧预期、邮箱租约接口旧预期和路由数旧预期；不计作本轮通过，不扩大本轮改造范围。
- 阅读导航同时修正存储入口说明：`core/db.py` 和 `core/account_task_store.py` 是兼容别名，实际实现分别位于 `core/storage/db_legacy.py` 和 `core/operations/legacy_task_store.py`。
