# 后端批量改造验证记录

对应 [设计](../superpowers/specs/2026-11-24-backend-bulk-operations-design.md)、[实施计划](../superpowers/plans/2026-11-24-backend-bulk-operations-plan.md) 和 [全站覆盖矩阵](2026-11-24-backend-bulk-coverage.md)。

## 验证环境与证据范围

后端使用本机独立 PostgreSQL 测试库 `turb_test`，每个存储测试使用隔离的 `test_*` schema。测试通过主 checkout 的 Python 虚拟环境执行 `tools/test_isolated.py --profile all`；连接参数从权限为 0600 的临时文件读取，没有写进报告或提交。网络调用使用替身，没有执行真实注册、认证、支付、租约领取或第三方写入。

下列测试组合存在重叠，不能把各组数字相加作为不同测试总数。SQL 数量测试衡量目标数增长时本地数据库往返是否有界，不等同于生产端到端延迟或吞吐验收。

## 跨域后端集成

主 agent 执行的 23 文件组合通过：**231 passed，76 subtests passed**，pytest 用时 534.33 秒，隔离执行器用时 545.544 秒。

```text
tests/operations/test_bulk_mutation_worker.py
tests/operations/test_bulk_command_recovery.py
tests/operations/test_bulk_mutations.py
tests/operations/test_bulk_submission_shared.py
tests/operations/test_bulk_terminate_command.py
tests/accounts/test_account_bulk_mutations.py
tests/accounts/test_account_bulk_reads.py
tests/accounts/test_account_bulk_submission.py
tests/accounts/test_email_change_bulk_submission.py
tests/accounts/test_inspection_cancel_collection.py
tests/codex/test_codex_bulk_mutations.py
tests/codex/test_codex_bulk_reads.py
tests/codex/test_codex_bulk_submission.py
tests/codex/test_codex_cancellation_collection.py
tests/email/test_email_return_collection.py
tests/email/test_email_deletion_snapshot.py
tests/email/test_email_pool_bulk_mutations.py
tests/extract_link/test_extract_managed_collections.py
tests/extract_link/test_extract_workbench_bulk.py
tests/bulk/test_native_retry_collection.py
tests/bulk/test_bulk_control_collection.py
tests/config/test_runtime_config_store.py
tests/webui/test_bulk_route_contracts.py
```

该组合覆盖普通变更的业务事实与块回执原子提交、跨 Run 恢复、不重复执行、完整分页、大整数身份、Web/Worker 装配分离、集合任务建立，以及各域的跳过、安全和回滚边界。

以下数量预算已在上述真实 PostgreSQL 组合验证；这里使用测试的约束上限，不将它们描述为生产性能：

| 场景 | 测试规模及集合 SQL 预算 | 测试文件 |
|---|---|---|
| 整份配置保存 | 501 个字段，两条配置写语句，整事务发布 | `tests/config/test_runtime_config_store.py` |
| 原生批次控制 | 100 个目标的 SQL 数不超过单目标加两条，且不超过 50 条 | `tests/bulk/test_bulk_control_collection.py` |
| 六类正常 managed 重跑 | 100 个目标，最多 16 条 | `tests/bulk/test_native_retry_collection.py` |
| 带普通父任务的 managed 重跑 | 20 个父任务，最多 32 条；无逐目标保存点 | 同上 |
| 注册 handoff 的 managed 重跑 | 20 个目标，最多 34 条；无逐目标保存点 | 同上 |
| 提链 managed 原单同步 | 20 个目标，最多 30 条，且不超过单目标加一条 | `tests/extract_link/test_extract_managed_collections.py` |
| 提链普通父任务同步 | 20 个父任务，最多 48 条 | 同上 |

## 任务中心补充回归

Sentinel 缓存身份分组改造后的组合通过：**53 passed，3 subtests passed**，pytest 用时 144.76 秒，隔离执行器用时 153.805 秒。

```text
tests/operations/test_task_center_sentinel_collection.py
tests/operations/test_task_center_retry_storage.py
tests/operations/test_task_center_cancel_collection.py
tests/operations/test_task_center_native_retries.py
tests/operations/test_task_center_actions.py
```

其中新增的同缓存回归先复现“首项拒绝导致后续合格项也拒绝”，修复后验证首个合格项排队、后续项复用、跨语句块复用以及存储失败时整波回滚。独立只读复核通过。后续混合来源受理的最终组合结果单独记录，不以此较早组合替代。

跨模块整合的第一轮 16 文件组合为 **201 passed，35 subtests passed，5 failed**，pytest 用时 371.70 秒。失败与后续处理保留如下：

- 四项测试仍替换旧单项受理入口，已经适配集合接口并继续验证来源优先级、输入顺序、归属、状态 CAS 和错误脱敏；注册入口对应 `53e21c7d`，取消路由对应 `a1b390a2`。取消路由整文件复测 **35 passed，23 subtests passed**。
- 一项真实并发失败显示两个请求分别持有父 Run 与父 Task，最终双方均返回 busy。`054ed71b` 限制只有取得该父 Run 的请求才尝试其父 Task，确定性双线程回归先复现失败后通过，关联六项 PostgreSQL 测试与三个子测试通过，独立复核通过。

架构职责约束整目录复测 **12 passed**，pytest 用时 0.53 秒。检查 HTTP 与执行代码的依赖方向、前端 HTTP 接缝、运行状态唯一拥有者及恢复服务边界。

修复后的第二轮相同 16 文件组合通过：**209 passed，37 subtests passed，0 failed**，pytest 用时 311.89 秒，隔离执行器用时 318.314 秒。该轮包括新增的 501 目标写入及整波回滚、managed 后置受理异常、混合来源顺序和确定性父锁交错回归。

```text
tests/operations/test_task_center_retry_storage.py
tests/operations/test_task_center_sentinel_collection.py
tests/operations/test_task_center_cancel_collection.py
tests/operations/test_task_center_native_retries.py
tests/operations/test_task_center_actions.py
tests/operations/test_task_center_legacy_retries.py
tests/operations/test_task_center_retry_wave.py
tests/operations/test_task_center_retry_wave_locks.py
tests/operations/test_task_center_legacy_codex_refresh.py
tests/registration/test_registration_retry_followups_store.py
tests/registration/test_registration_retry_followups_service.py
tests/registration/test_registration_retry_wave.py
tests/registration/test_registration_retry_bulk.py
tests/operations/test_registration_retry_bulk_actions.py
tests/operations/test_operations_route_migration_phase2.py
tests/webui/test_bulk_route_contracts.py
```

## 历史注册批次停止

主 agent 执行以下最终组合通过：**17 passed**，pytest 用时 31.10 秒，隔离执行器用时 37.943 秒。

```text
tests/registration/test_registration_batch_stop.py
tests/registration/test_batch_stop_projection_compat.py
```

覆盖 1,000 条以外的原批次定位、活跃执行的合作停止、停止快照后任务已结束的 CAS、历史缺失 Task/Run 补投影、来源集合解析、整事务回滚，以及 501 个同 root 历史 Job 跨语句块时 Run 编号与当前 Run 的一致性。缺失队列锚点时先建立锚点，再按队列、批次、Job 的顺序锁定，真实并发测试验证不会倒转旧投影器的锁序。

五项额外对照直接调用原单项 `sync_registration_job`，验证集合停止后的 Task 事实保持一致：已有 Task 缺少 Run 时补齐 Attempt/账号等关联；同 root 的历史 waiting 或 stopping 不抢占较新的 stopped Run；另一批次仍运行的 Run 保留错误和动作；已有子 Task 的 parent/root 恢复原关联。独立评审通过。

## 取消语句分块最终联测

主 agent 执行七文件组合通过：**89 passed，26 subtests passed，0 failed**，pytest 用时 142.76 秒，隔离执行器用时 149.309 秒。

```text
tests/operations/test_cancellation_chunk_bounds.py
tests/accounts/test_inspection_cancel_collection.py
tests/operations/test_bulk_terminate_command.py
tests/codex/test_codex_cancellation_collection.py
tests/bulk/test_bulk_control_collection.py
tests/operations/test_task_center_cancel_collection.py
tests/operations/test_operations_route_migration_phase2.py
```

普通及 managed 的 501 目标取消均使用 500+1 条写入，全波仍先取得原 target、账号、Task 和 Run 锁。取消、AT 阶段释放和 managed outbox 三处第二块故障分别验证：Run、Task、lease、账号、目标及 outbox 全部回滚，调用方在保存点之前写入的无关事实可以继续提交。IDLE 连接不提前提交，全部 CAS 跳过时仍按原 managed 规则发布一次；同 Task 跨块只由最大的已变更 Run 投影状态和完成时间。六项新增测试及三个子测试包含在上述组合内。

## 前端、契约和构建

执行 `npm run generate:api && npm run check && npm run build` 全部通过。前端 **92 个测试文件、1,099 项测试**通过；类型检查、API 生成一致性、任务类型及完成状态标签检查通过；Vite 构建 897 个模块成功。

合成数据的已构建页面通过真实 Chromium 点击：账号批量归档只发一次 POST，随后三次 GET 查询同一个大整数命令编号 `9007199254740993`；终态一项成功、一项跳过，成功项清除选择、跳过项保留。该检查验证前端提交及回执行为，没有连接真实业务数据。

任务中心批量终止的 API 和组件测试另覆盖 HTTP 202 后轮询完整分页、精确传递大整数 Task ID、查询失败保留命令编号与选择，以及成功项清除选择。生成静态产物已随对应源码更新。

最终收尾核对前端源码、契约及生成静态文件自已通过的 `e58f21d1` 构建后没有变化。全分支 172 个新增或修改的 Python 文件 Ruff 与编译检查通过，`git diff --check` 通过。

## 交付边界

本记录证明当前开发工作区的隔离测试及源码构建结果。没有将历史审计中的“未改代码”表述当成实施状态，也没有将本地测试、提交、推送、部署和真实业务验收混为一项。
