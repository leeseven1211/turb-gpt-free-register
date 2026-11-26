# 总览每日注册统计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. 步骤用复选框记录。

**Goal:** 总览按日展示注册任务量、套餐分布，并预填现有查套餐批量新建页，验证和 review 后合并本地 main。

**Architecture:** 新增只读注册日聚合模块，复用 PostgreSQL 的任务、账号和优惠投影。账号高级搜索增加注册任务创建日条件，使聚合和批量名单使用同一服务端范围，无需下载账号 ID。Vue 独立统计组件复用现有总览轮询与批量新建桥。

**Tech Stack:** Python / Flask / PostgreSQL / Vue 3 / TypeScript / Vitest。

**Spec:** `docs/superpowers/specs/2026-11-26-dashboard-daily-registration-design.md`

## Global Constraints

- 中文文案；不修改注册主流程；不覆盖其他工作区修改。
- 禁止 `rm -r`、`rm -rf`；测试只使用独立 `turb_test` 数据库和 `test_` schema。
- 日期统一北京时间，账号去重、归档统计与新建范围按设计区分。
- 只打开预填的新建页，不自动创建或执行批量。
- 复用 `promotion=["none"]`，不新增历史失败或远端无回执的重跑阻断。
- 提交前运行直接相关测试和构建，合并前独立 review；不推送、不部署。

## 任务 1：聚合与共享范围

文件：新增 `core/storage/registration/analytics.py`、`tests/storage/test_registration_daily_analytics.py`；修改 `core/accounts/search.py`、`core/storage/admin_repository.py`、`webui/routes/dashboard.py`；增加对应搜索与路由测试。

接口：`GET /api/dashboard/registration-daily?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`；缺省近 7 天。返回：

```json
{"ok":true,"timezone":"Asia/Shanghai","date_from":"2026-11-20","date_to":"2026-11-26","updated_at":"2026-11-26T12:00:00+08:00","rows":[{"date":"2026-11-26","total":0,"counts":{},"accounts_total":0,"plans":{},"unpromoted_count":0,"query":{}}],"summary":{"total":0,"accounts_total":0,"unpromoted_count":0,"query":{}}}
```

`query` 是规范化 AccountQuerySpec，`archived="0"`、`filters.promotion=["none"]`，`q="注册任务日期:2026-11-20..2026-11-26"`。日期条件通过共享 SQL 范围关联有效账号，保持归属校验；套餐分类复用现总览投影。接口错误返回中文 message 和固定 error_code。

- [x] 先增加测试并观察失败：跨北京时间零点、显式重跑与补全排除、账号去重/归档、空日期、优惠范围一致、错误日期与接口只读。
- [x] 实现聚合、搜索解析及共享账号范围谓词；SQL 查询次数不随任务/账号数增长，不扫描完整凭据 JSON。
- [x] 使用统一隔离入口运行新增测试及直接相关账号查询测试，记录输出。

## 任务 2：统计展示

文件：新增 `frontend/src/features/dashboard/DailyRegistrationStats.vue` 和定向测试；修改 dashboard API、contracts、useDashboard、DashboardPage 及对应测试。

接口：使用任务 1 的响应；`DashboardDeps.onBulkPlanCreate?(value:{name:string;query:AccountQuerySpec}):void`，批量名为“日期/区间 无优惠账号查套餐”。日期初始值采用服务端响应；显式区间读取和轮询保持筛选，不让旧响应覆盖新选择，隐藏/卸载停止读取。

- [x] 先验证日期切换请求、每天数量/套餐、错误重试及点击仅调用预填回调的失败测试。
- [x] 实现近 7/30 天、自定义日期、可访问的柱状图和每日明细；移动端内容可读，零值/待查显示准确。
- [x] 定向 Vitest 覆盖上述交互、轮询与取消，运行 typecheck。

## 任务 3：批量新建对接与文档

文件：修改 `webui/static/js/pages/dashboard/page.js`、bulk bridge 与 `frontend/src/features/bulk/BulkPageShell.vue` 等必要契约/测试；更新 README 的总览说明。

接口：dashboard bridge 将 `{name,query}` 交给现有 `BulkTasks.fromAccounts(false,"plan_check",snapshot)`；snapshot 可带可选 `name`，现有入口不传时保持原行为。新建页保留日期条件、优惠条件和名字，未调用 selections/batches 写接口。

- [x] 先增加桥接和新建预填的行为测试，观察失败。
- [x] 扩展可选名称透传，保留查询规范化和筛选标签；更新中文 README，说明当前套餐和归档口径。
- [x] 运行直接相关桥接/Vue 测试，记录输出。

## 任务 4：整体验证与合并

- [x] 阅读所有 diff，运行直接相关后端测试、Vue/桥接测试和生产构建。
- [x] 用独立合成数据和真实浏览器验收统计、日期和预填入口，不触发业务执行。
- [x] 独立 agent review；修复发现并验证。
- [ ] 提交本分支，确认 main 状态后合并本地 main，验证提交包含关系和工作区状态。

## 验证结果

- 集成基线为本地 main `a7ee3dc0`，保留同期批次浮窗、列表统计与静默刷新改动。
- PostgreSQL 隔离测试：60 项通过、194 项子测试通过；新增路由测试 3 项通过。
- Vue 定向测试：8 个文件、48 项通过；Node 桥接测试 18 项通过。
- 生产构建通过，包括 API 与错误目录检查、类型检查及 Vite 构建。
- 真实浏览器使用合成数据验证 7 天、30 天、自定义日期、套餐分布及新建表单预填；未触发批量创建或执行。
- 独立 review 已通过。已修复日期查询前推、历史数据归属与时间兼容、无优惠数量一致性、GET 只读，以及真实任务状态展示。
