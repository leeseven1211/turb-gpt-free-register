# Task 2 报告

状态：已完成。

Commit：`252487da`（`feat: 增加批量命令 Worker 执行入口`）。

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
