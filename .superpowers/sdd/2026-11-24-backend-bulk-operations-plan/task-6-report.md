# Task 6 实施报告

状态 DONE_WITH_CONCERNS。契约提交 `7ee24978`，实现提交 `a3dd26e0`。

- `webui/routes/operations.py:214` 调用 `accept_bulk_operation_action`。`core/operations/action_service.py:205` 按集合快照分流，`core/storage/operations/bulk_facts.py:77` 每个选中任务读取最新和当前 Run，用于保留当前活跃优先和历史来源回退。无需加载事件、资源或父任务详情。
- `core/operations/action_service.py:277` 集合查询托管目标，按真实来源 batch 聚合且去重 canonical target。每个 batch 一条持久化 round。目标 ID 排序使同一幂等键和同一选择按不同顺序重发仍复用。
- `core/storage/operations/bulk_facts.py:12` 按任务 ID 锁定，终态目标使用一条 UPDATE 隐藏，活动任务与审计数据保留。
- `core/operations/action_service.py:205` 批量 cancel 只处理排队任务，Codex、默认运行控制和 `core/operations/action_service.py:505` 的 WebUI runtime 路径会用 expected status 防止已开始的 Run 被误停。批量 terminate 继续调用选中 Run 的既有领域结算。非托管重跑、特定领域的取消和运行中结算保留逐目标服务调用，其中 Codex 还同步局部账号状态。整批或整轮控制无法表达选中集合。
- `webui/routes/jobs.py:395` 和 `:401` 调用 `core/storage/operations/bulk_facts.py:136`，单事务更新排队 Job 和 queued RegistrationRun，再以集合刷新兼容投影。批次投影命令按受影响批次登记。
- `webui/routes/jobs.py:534` 和 `:550` 使用 `core/storage/operations/bulk_facts.py:174`。真实 PG 发现旧物理删除会被 `registration_runs_job_fk` 拒绝。新事务只选择可以删除的 Job，收口仍排队的 RegistrationRun，在 Run 的 JSON 保存 `deleted_job_id` 并解除 Job 外键，保留 Run、Attempt、事件和未选择的同批 Job。日志和调试产物根据实际删除的 Job 逐文件清理。
- `contracts/task-center.openapi.json:825` 描述任务批量动作、返回结构和可选重跑幂等键，`frontend/src/api/schema.d.ts` 已重新生成。

测试先在隔离 `turb_test` PostgreSQL 中复现旧实现的 2 次删除 UPDATE、同原批次 2 个独立轮次、注册取消的逐 Job 投影、注册删除的逐 Job 回读与外键 500。最终使用 `tools/test_isolated.py --profile all` 运行以下三文件，共 `79 passed, 88 subtests passed`。

- `tests/operations/test_operations_route_migration_phase2.py:57` 以语句级触发器验证单次集合 UPDATE 和保留 Run。`:86` 验证同批归组、跨批隔离和反序重放。`:774` 与 `:842` 验证排队状态竞争和按运行状态分流。
- `tests/registration/test_registration_retry_driver.py:25` 验证注册批次的待执行 Job 和 Run、未选择 Job、运行中 Job 和 Attempt。`:51` 验证删除后的本地事实、日志产物使用实际删除的行及历史 Run。
- `tests/operations/test_task_center_actions.py` 保留单条契约并验证批量集合读取、运行状态校验与空 Run 回执。
- `npm --prefix frontend run generate:api`、`npm --prefix frontend run check:api` 和 Task 6 路径的 `git diff --check` 均通过。

注册 `/api/jobs/retry-bulk` 仍调用既有驱动分支与原重跑服务。`/api/jobs/batches/<batch_id>/stop` 保留运行中逐 Job 的协作取消。注册本次验收使用本地事实和隔离数据库，涵盖历史归属与选中范围。
