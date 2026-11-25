# 后端批量操作 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将本地批量写入和批量任务受理统一为一次集合命令，由 Worker 执行，数据库采用集合 SQL 和分块事务，单条入口复用同一服务。

**Architecture:** UI 继续只负责展示和提交集合；`webui/routes` 只做 HTTP 适配、校验、幂等和批量命令受理；`core/operations` 负责批量用例与 Worker handler；`core/storage` 负责集合查询、锁、分块事务和回执事实。Worker 是 `core/operations` 的运行入口，不复制业务规则。

**Tech Stack:** Python 3、Flask、PostgreSQL、psycopg、现有 `core/operations` durable runtime、现有 `core/bulk_operations` selection/batch/round/target 投影、`unittest`/`PostgresTestCase`。

**Spec:** `docs/superpowers/specs/2026-11-24-backend-bulk-operations-design.md`

## 实施与验证记录

原七项工作及后续全按钮覆盖补充的实际实现，分别记录在 [覆盖矩阵](../../reports/2026-11-24-backend-bulk-coverage.md) 和 [验证记录](../../reports/2026-11-24-backend-bulk-validation.md)。[原始按钮索引](../../reports/backend-bulk-button-inventory/README.md) 保留全部业务与纯交互入口。

以下复选框保留最初的执行步骤，不补填无法追溯的历史失败输出。领域扩展包括注册后处理与历史来源、任务中心特殊 handler、普通父链、managed 控制、提链同步、配置发布及两个同步巡检器；不能仅用原七项计划判断“所有按钮”是否完成。最终整合状态以覆盖矩阵及对应测试证据为准。

## Global Constraints

- PostgreSQL 是唯一事实来源，不新增 SQLite 或文件主存储。
- 存储测试必须继承 `tests.support_pg.PostgresTestCase` 或使用项目隔离 schema，禁止使用 `public` schema。
- API 不在请求线程逐目标建任务、逐目标开事务或调用外部服务；批量命令由 Worker 领取。
- Worker 通过 `core/operations` 和 `core/storage` 执行，不在 Worker 文件中复制领域规则或绕过 Storage 拼业务 SQL。
- 默认每块最多 500 个目标；领域上限更小的接口继续使用原上限；重复目标只执行一次并返回 `duplicate_count`。
- 每个目标必须返回 `updated`、`skipped` 或 `failed`，并带稳定 `reason_code` 和中文 `reason`；禁止未分类错误。
- 不改变 Roxy、proto2 或其他注册驱动的步骤、请求参数、页面定位、关键分支、重试/超时和状态流转。
- 不执行 `rm -r` 或 `rm -rf`；删除文件时逐个删除。
- 中文代码注释、日志和接口文案；配置键、API 字段、类名、函数名保留原始拼写。

---

### Task 1: 批量命令契约、规范化和统一回执

**Files:**
- Create: `core/operations/bulk_mutations.py`
- Modify: `core/operations/contracts.py`
- Test: `tests/operations/test_bulk_mutations.py`

**Interfaces:**
- Produces `BulkItemResult`, `BulkMutationResult`, `normalize_bulk_targets`, `execute_chunked_bulk`。
- `execute_chunked_bulk(operation, targets, apply_chunk, *, max_targets=5000, chunk_size=500, idempotency_key=None)` 对每块调用 `apply_chunk(chunk)`，只负责分块和结果合并，不触发数据库或外部服务。

- [ ] **Step 1: Write the failing test**

在 `tests/operations/test_bulk_mutations.py` 覆盖：重复目标去重、无效目标分类、500 个一块的分块边界、块级异常只把当前块标为 `bulk_chunk_failed`、结果按首次输入顺序返回。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/operations/test_bulk_mutations.py -q`
Expected: FAIL，因为契约函数尚不存在。

- [ ] **Step 3: Write minimal implementation**

实现不可变 dataclass、稳定去重、`duplicate_count`、逐项结果映射和块级错误分类；不在该文件引入 Flask、数据库或 Worker。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/operations/test_bulk_mutations.py -q`
Expected: PASS，所有契约测试通过。

- [ ] **Step 5: Commit**

```bash
git add core/operations/bulk_mutations.py core/operations/contracts.py tests/operations/test_bulk_mutations.py
git commit -m "feat: 增加批量命令统一回执契约"
```

### Task 2: Durable Worker 批量命令执行入口

**Files:**
- Create: `core/operations/bulk_mutation_worker.py`
- Modify: `core/operations/task_gateway.py`
- Modify: `core/runtime/assembly.py`
- Test: `tests/operations/test_bulk_mutation_worker.py`

**Interfaces:**
- Consumes Task 1 的 `BulkMutationResult` 和 `execute_chunked_bulk`。
- Produces `register_bulk_mutation_handler(operation, handler)`、`submit_bulk_mutation(operation, targets, parameters, *, idempotency_key, trigger)`、`run_bulk_mutation(run_id)`。

- [ ] **Step 1: Write the failing test**

测试 handler 注册、重复幂等键不创建第二个批量命令、Worker 领取后按块调用 handler、重启/重复领取不会重复提交已完成块、失败目标写入稳定 `reason_code`。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/operations/test_bulk_mutation_worker.py -q`
Expected: FAIL，因为 bulk mutation handler 尚未接入 durable runtime。

- [ ] **Step 3: Write minimal implementation**

复用现有 `task_gateway` 的 durable task/run、lease、dispatch 和恢复机制；批量命令参数存入非敏感 `data`，外部敏感值不得进入命令 payload。Worker 只读取命令并调用注册 handler，结果通过现有 operation event/projection 写回。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/operations/test_bulk_mutation_worker.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add core/operations/bulk_mutation_worker.py core/operations/task_gateway.py core/runtime/assembly.py tests/operations/test_bulk_mutation_worker.py
git commit -m "feat: 增加批量命令 Worker 执行入口"
```

### Task 3: 账号本地批量事实

**Files:**
- Create: `core/storage/accounts/bulk_mutations.py`
- Modify: `webui/routes/accounts.py`
- Test: `tests/accounts/test_account_bulk_mutations.py`

**Interfaces:**
- Consumes Task 1/2 的统一命令和回执。
- Produces `archive_many(account_ids, archived)`, `delete_many(account_ids)`, `update_note_many(account_ids, note)`, `set_email_invalid_many(...)`，均接收共享连接或在 Worker 块事务中运行。

- [ ] **Step 1: Write the failing test**

使用 `PostgresTestCase` 验证归档、删除、备注一次集合写入；重复 ID 只修改一次；不存在、已保护、邮箱已变更目标分别返回 `skipped`；单条路由与 bulk 路由调用同一方法。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/accounts/test_account_bulk_mutations.py -q`
Expected: FAIL，因为新 storage bulk 方法不存在。

- [ ] **Step 3: Write minimal implementation**

在新 storage 模块中使用 `ANY`、集合 `RETURNING` 和固定锁序；路由移除逐账号 `db.get_account`/`enqueue` 循环，改为提交一个 bulk mutation command。保留现有兼容字段和 skipped 结构；不改注册执行流程。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/accounts/test_account_bulk_mutations.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add core/storage/accounts/bulk_mutations.py webui/routes/accounts.py tests/accounts/test_account_bulk_mutations.py
git commit -m "feat: 将账号本地写入改为批量命令"
```

### Task 4: Codex 凭证本地批量事实

**Files:**
- Create: `core/storage/codex/bulk_mutations.py`
- Modify: `webui/routes/codex.py`
- Test: `tests/codex/test_codex_bulk_mutations.py`

**Interfaces:**
- Produces `archive_many(filenames, archived)`, `delete_many(filenames)`, `reset_exported_many(filenames)`、`mark_exported_many(filenames)`。
- 所有方法在集合查询/集合 `UPDATE/DELETE ... RETURNING` 后返回逐文件回执。

- [ ] **Step 1: Write the failing test**

隔离 schema 中验证凭证归档、删除、重置导出计数、批量标记导出只产生集合 SQL 语义；缺失/重复/非法文件名分类稳定；单条路由复用同一方法。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/codex/test_codex_bulk_mutations.py -q`
Expected: FAIL，因为新 bulk storage 方法不存在。

- [ ] **Step 3: Write minimal implementation**

移除路由中的逐文件 `db.archive_codex`、`db.delete_codex_credential`、`db.mark_codex_exported` 循环；文件内容读取和 ZIP 生成保留原有单文件/外部文件语义，数据库状态回写统一使用集合方法。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/codex/test_codex_bulk_mutations.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add core/storage/codex/bulk_mutations.py webui/routes/codex.py tests/codex/test_codex_bulk_mutations.py
git commit -m "feat: 将 Codex 本地状态改为集合批量写入"
```

### Task 5: 邮箱池批量状态和墓碑事实

**Files:**
- Create: `core/storage/email/bulk_mutations.py`
- Modify: `webui/routes/email_pool.py`
- Test: `tests/email/test_email_pool_bulk_mutations.py`

**Interfaces:**
- Produces `update_status_many(items, status, note)`, `delete_many(items)`、`update_derivation_status_many(ids, state)`。
- 每块事务内一次读取并锁定目标，按来源分组执行集合更新；退租/服务事实只写本地待处理事实，外部回收仍由既有 worker 完成。

- [ ] **Step 1: Write the failing test**

覆盖多个来源、重复邮箱、不存在、tombstone、registered protection、混合成功/跳过，以及删除中途块失败时已提交块可回查且未提交块不标成功。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/email/test_email_pool_bulk_mutations.py -q`
Expected: FAIL，因为新 bulk storage 方法不存在。

- [ ] **Step 3: Write minimal implementation**

路由只做集合解析和批量命令受理；Worker handler 在共享块事务中调用来源分组 storage 方法。保留邮箱租约安全规则，不把注册成功或结果不明邮箱重新投入池中。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/email/test_email_pool_bulk_mutations.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add core/storage/email/bulk_mutations.py webui/routes/email_pool.py tests/email/test_email_pool_bulk_mutations.py
git commit -m "feat: 将邮箱池状态和删除改为批量命令"
```

### Task 6: 任务事实、注册本地控制和 API 契约

**Files:**
- Create: `core/storage/operations/bulk_facts.py`
- Modify: `core/storage/operations/store.py`
- Modify: `webui/routes/operations.py`
- Modify: `webui/routes/jobs.py`
- Modify: `contracts/task-center.openapi.json`
- Modify: `tests/operations/test_operations_route_migration_phase2.py`
- Modify: `tests/registration/test_registration_retry_driver.py`

**Interfaces:**
- Produces `delete_tasks_many(task_ids)`, `cancel_pending_jobs_many(job_ids)`, `accept_bulk_operation_action(action, task_ids, ...)`。
- 运行中 terminate 仍走现有 run cancel/settlement，不用集合 UPDATE 强杀；注册主流程执行函数不改。

- [ ] **Step 1: Write the failing test**

覆盖任务删除集合更新、活动任务跳过、批量 cancel/terminate 的状态分流、同一原 batch 的 managed retry 只创建一个集合 round、注册删除/取消只改变本地受理层。验证 OpenAPI 仍和生成类型一致。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/operations/test_operations_route_migration_phase2.py tests/registration/test_registration_retry_driver.py -q`
Expected: FAIL，现有 bulk action 仍逐条调用单条 service。

- [ ] **Step 3: Write minimal implementation**

将任务中心 bulk action 从“循环调用单条 action”改为集合读取、按来源 batch 分组并统一创建 round/控制命令；删除使用集合 UPDATE；注册 pending cancel/delete 只改本地受理事实，不改注册 driver、页面步骤或重试策略。同步更新 OpenAPI 契约和必要生成检查。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/operations/test_operations_route_migration_phase2.py tests/registration/test_registration_retry_driver.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add core/storage/operations/bulk_facts.py core/storage/operations/store.py webui/routes/operations.py webui/routes/jobs.py contracts/task-center.openapi.json tests/operations/test_operations_route_migration_phase2.py tests/registration/test_registration_retry_driver.py
git commit -m "feat: 将任务和注册本地控制改为批量事实"
```

### Task 7: 全链路契约、恢复和回归验证

**Files:**
- Modify: `core/runtime/assembly.py`
- Modify: `core/runtime/readiness.py`
- Create: `tests/operations/test_bulk_command_recovery.py`
- Create: `tests/webui/test_bulk_route_contracts.py`
- Modify: `docs/architecture/convergence.md`

**Interfaces:**
- Consumes Tasks 1–6 的批量命令、Storage 和 Worker handler。
- Produces Worker readiness、启动恢复、批量接口路由契约和架构文档。

- [ ] **Step 1: Write the failing test**

验证 Worker 进程重启后未完成批量命令可重新领取；readiness 暴露 bulk worker；所有 bulk URL 的方法、上限、202/回执字段与 OpenAPI/路由契约一致。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/operations/test_bulk_command_recovery.py tests/webui/test_bulk_route_contracts.py -q`
Expected: FAIL，恢复和路由契约尚未覆盖。

- [ ] **Step 3: Write minimal implementation**

接入现有 runtime assembly/readiness，不新增第二套 Worker 线程；补齐恢复扫描、健康状态和文档中的 UI/API/Operations/Storage/Worker 关系。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/operations/test_bulk_command_recovery.py tests/webui/test_bulk_route_contracts.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add core/runtime/assembly.py core/runtime/readiness.py tests/operations/test_bulk_command_recovery.py tests/webui/test_bulk_route_contracts.py docs/architecture/convergence.md
git commit -m "test: 补齐批量命令恢复和路由契约"
```
