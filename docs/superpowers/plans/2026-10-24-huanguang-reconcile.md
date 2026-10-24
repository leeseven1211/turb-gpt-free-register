# 幻光原单持续同步实施计划

**目标：** 原单与提交回执可恢复地持续同步，状态统计真实，避免重复提链和付款。
**架构：** 复用原生 durable 队列的同 Run 延迟执行和私有 provider JSONB；在现有容量内公平调度续查。
**技术栈：** Python、PostgreSQL、原生 JavaScript、pytest。
**设计：** [原单持续同步设计](../specs/2026-10-24-huanguang-reconcile-design.md)。

## 全局约束

- 仅使用隔离测试库与 `test_` schema，不连接生产库，不复制私有 `.env`。
- 保留所有私有文件；禁止递归删除、全量 git add、推送。
- 中文文案；不放宽支付和 Plus 核验；新恢复只查询原提交或已有子单。

## 任务

1. **队列 defer 与公平调度**：修改 `core/operations/task_gateway.py`、`core/storage/operation.py` 及对应 gateway/dispatcher 测试。增加 `context.defer(delay_seconds, reason, data, stage)`，同 Run 原子保存 continuation 并释放执行资源；候选两车道轮换，续查子预算最多二；覆盖 fence、取消、重启与单槽公平性。
2. **平台回执与子任务**：修改 `core/extract_link_providers/contracts.py`、`huanguang.py` 及 provider 契约测试。增加可选 `ExtractRequest.submission_checkpoint`，发送前保存回执凭据；支持空 ID 原提交恢复与稳定根 ID 子链查询，严格支付判据保持不变。
3. **状态展示和计数**：修改 `core/storage/extract_link_jobs.py` 的统计片段、`extract_link_batches.py`、前端工作台与相关 query/frontend 测试。运行中只计实际执行；旧快照和续查等待明确展示，排队任务不误归为失败。
4. **服务集成与恢复**：修改 `core/extract_link_service.py`、provider 存储的私有恢复和 fence 入口、flow/storage 测试。发送前 checkpoint、超时和临时失败后 defer、同 Run 重入只查询、历史 attention/interrupted 原单恢复、回执恢复和严格到账验证。
5. **交付**：更新 README 和既有监控预算帮助文案，运行聚焦及完整隔离回归、独立代码审阅、浏览器验收；仅提交本次文件到 main，重启托管服务并核验已有原单。

每项先增加能复现缺口的失败测试，再实施最小修改并验证通过；各代理不自行提交。

## 审阅重点

- 单次或整批提交无响应不能触发第二次提链 POST；旧无凭据未知不能冒充可恢复提交。
- 父退款、子成功、子失败及父未知不能混合拼接到账证据。
- 延迟续查释放 lease/线程，取消与过期执行不能覆盖新执行；超过64个续查也不能遮住新任务。
- 并发一、并发十、已满容量及进程恢复均不会重复创建或永久占位。
- 结果页、列表、SQL计数与普通 API 均不包含私有查询凭据。
