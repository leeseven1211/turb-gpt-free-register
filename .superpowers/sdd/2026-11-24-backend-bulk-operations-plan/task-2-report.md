# Task 2 报告

状态：已完成。

Commit：`b842436d`（`feat: 增加批量命令 Worker 执行入口`）。

实现内容：

- 新增 `core/operations/bulk_mutation_worker.py`，提供 `register_bulk_mutation_handler`、`submit_bulk_mutation`、`run_bulk_mutation`。
- 批量命令统一使用 `bulk_mutation` durable task type，并登记到现有 `task_gateway` dispatcher；通过已有 `maintenance_check` 并发策略别名，不新增未审计的并发配置键。
- 提交入口将幂等键哈希到稳定 `source_id`，重复请求复用同一 durable task；命令 `data` 只保存目标、脱敏参数和幂等键摘要。
- Worker 调用 Task 1 的 `execute_chunked_bulk`；每个成功处理的分块先写 `bulk.chunk.completed` operation event，重启或重复领取时从事件恢复并跳过已完成分块。
- 逐项目结果写入统一 `BulkMutationResult` summary，失败目标保留 handler 返回的稳定 `reason_code`。
- `task_gateway.py` 增加批量入口的惰性转发函数；`core/runtime/assembly.py` 在 operation dispatcher 启动前安装通用 bulk handler。
- 新增 `tests/operations/test_bulk_mutation_worker.py` 覆盖注册、幂等提交、按块执行、重复领取恢复和稳定失败原因。

验证：

- `python -m pytest tests/operations/test_bulk_mutation_worker.py tests/operations/test_bulk_mutations.py -q`：11 passed。
- `python -m pytest tests/operations/test_durable_operation_gateway_phase2.py -q`：44 skipped；本机未配置 PostgreSQL `DATABASE_URL`，测试自身依赖数据库后跳过。
- `python -m compileall -q core/operations/bulk_mutation_worker.py core/operations/task_gateway.py core/runtime/assembly.py`：通过。
- `git diff --check`：通过。
- `tests/runtime/test_runtime_composition.py tests/runtime/test_runtime_drain_boundaries.py tests/webui/test_webui_runtime.py`：组合运行 68 passed、4 subtests passed、5 failed；失败均为现有 WebUI/恢复测试在本机缺少 PostgreSQL 或旧测试未隔离数据库导致，首个失败栈在 `recover_participating_executions()` 初始化统一任务 schema，未进入批量 Worker 代码。

风险：

- 批量 handler 约定优先支持 `(chunk, parameters)`，同时兼容 `(operation, chunk, parameters)`、`(chunk)` 和无参 callable；业务 handler 的外部副作用仍由调用方负责幂等。
- 已完成分块以 operation event 作为恢复证据；若进程在外部副作用完成后、事件提交前崩溃，该块会再次执行，调用方应让单块操作自身幂等。
- 本地未配置 PostgreSQL，未做真实 durable claim/lease/投影端到端验收。

## 审查后必要架构修复（2026-11-24）

上一版基于 operation event 的恢复实现已经被本次专用存储替换；上文该设计和无真实 PostgreSQL 验证的风险不再描述当前代码。

- 新增 `core/storage/operations/bulk_mutations.py`，专用 `operation_bulk_mutation_commands` / `operation_bulk_mutation_receipts` 表完整保存原始目标、规范化目标、参数、参数指纹、去重计数和完整逐项回执。专用 JSON 序列化仅接收已验证的非敏感 JSON，不修改通用 `_scrub`，不截断数组或对象。
- Run data 只保存 `command_id` / `operation` / `bulk_mutation`。完整命令与 durable task/run 在同一连接、同一事务创建；同键并发受 advisory xact lock 和唯一约束保护，同键异 payload 明确 `idempotency_key_conflict`。
- 每块在一个事务内锁定 command 与当前 Run，验证 task/command/execution/status/cancel fence，再调用固定签名 `handler(chunk, parameters, *, conn)`。业务变更和完整 receipt 共同提交；异常共同回滚。恢复按 command_id 跨 Run 读取 receipt，已完成块不再调用业务 handler。
- 未知 operation 提交前拒绝；参数按注册的 `parameter_allowlist` 显式校验并拒绝敏感字段、凭据模式、非 JSON 对象；`chunk_size` 注册时限制 1..500。漏报目标返回 `bulk_result_missing`，取消、lease/fence 和 settlement 控制异常不会被普通块异常捕获吞掉。每块前及收口前检查取消与当前 execution。
- `run_bulk_mutation` 在 admission 前校验 task_type/source_system/command_id。业务注册和提交不安装 execution handler，Web 不执行 Worker 注册。
- 注册接口新增可选 `after_commit(chunk, parameters, items)`；已与邮箱实现者协调用于提交后幂等 compat export 调度。该通知在块提交后运行，重入已提交 receipt 时可补发；通知异常不覆盖已提交业务事实。

定稿注册接口：

```python
register_bulk_mutation_handler(
    operation, handler, *, parameter_allowlist=(), chunk_size=500, after_commit=None,
)
# handler(chunk, parameters, *, conn)
# after_commit(chunk, parameters, items)  # 可选，只做幂等提交后调度
```

TDD RED 证据：

- 新增真实 `PostgresTestCase` 后运行 Worker 测试，因专用 `core.storage.operations.bulk_mutations` 模块尚不存在而收集失败。
- 专用存储实现后，首次真实 PostgreSQL `--profile extended` 运行：5 failed、3 passed；断言明确暴露回执 `key` 被误判为敏感参数造成块整体回滚。修正契约字段与任意参数的验证边界后同组 8 passed。

GREEN 验证（安全测试库：独立 turb_test、隔离 test_ schema；通过 0600 环境文件加载 DSN，未输出连接秘密）：

- `tools/test_isolated.py --profile all -- tests/operations/test_bulk_mutation_worker.py tests/operations/test_bulk_mutations.py -q`：18 passed；随后新增提交后通知真实读回测试后 Worker+Task1 共 19 passed。
- 新测试覆盖：5001 目标与回执完整、写后 crash 回滚、已提交块跨新 Run 重入不重复 counter、并发同键仅一个 command/task、同键异 payload 冲突、块间取消、缺失结果与稳定 reason_code、旧 execution fence 拒写、提交事务同时回滚命令与 Task、after_commit 只能读到已提交业务数据及重入补发。
- 额外运行 `tests/runtime/test_web_action_catalog.py` 暴露 assembly 中上一版无条件 Worker 注册；runtime integration 实现者已独占接手该修正，Worker 注册/提交入口本身已移除自动 execution 注册。

当前边界：本 Worker 只执行本地数据库 handler；领域 handler 必须使用传入 conn，不能自行提交外部副作用。自动将 interrupted Run 接续到新 Run、查询分页和 runtime readiness 由后续 integration 任务接入；专用命令 receipt 已支持跨 Run 恢复。
