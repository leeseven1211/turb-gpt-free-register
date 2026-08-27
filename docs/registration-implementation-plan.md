# 注册流程重构实施方案

状态：Proposal（供并行开发窗口认领）  
原则：小步提交、每阶段可测试、数据库变更隔离、禁止把未完成存储代码直接用于生产。

## 1. 工作窗口和依赖

建议拆为五条工作流。每条工作流只修改自己负责的文件域，跨域改动先在任务评论中说明。

| 工作流 | 负责内容 | 主要文件域 | 依赖 |
| --- | --- | --- | --- |
| A | Roxy/Protocol 流程状态机与等待优化 | `core/registration/roxy.py`、`core/registration/protocol.py`、新建状态机模块 | 基线事件协议 |
| B | Attempt/Run/Checkpoint 和存储 | `core/record_store.py`、`core/storage/`、数据库迁移 | 无；使用独立开发库 |
| C | 后处理、恢复、重试和资源租约 | `core/registration_service.py`、2FA/Codex/plan/proxy/email | B 的状态契约 |
| D | 诊断、事件、耗时和错误分类 | `core/registration_debug.py`、`core/task_stages.py`、`core/task_errors.py` | A 的阶段状态契约 |
| E | 统一任务中心投影和前端展示 | `core/storage/operation.py`、`core/operation_task_store.py`、`webui/routes/jobs.py`、任务页面 | B/D 的事件字段 |

并行规则：A、B、D 可先并行；C 依赖 B 的字段和状态契约；E 依赖 B、D 的事件协议。任何人不得顺手修改其他工作流的大文件。

## 2. 阶段 0：基线冻结

交付物：

- 当前完整测试结果、Roxy/Protocol 关键测试结果。
- 最近 10 个任务和历史调试任务的回放 fixture。
- 阶段事件字段和错误字段的契约测试。
- 驱动范围约束：新任务只允许 Roxy 主流程，Protocol 只能作为辅助通道。

禁止：修改业务行为、修改生产库、运行真实注册。

完成标准：所有窗口使用同一套阶段名、状态名、错误字段和测试命令。

## 3. 阶段 1：驱动入口收敛

内容：

- dispatcher 将注册主入口固定到 Roxy 编排器。
- 保留 Protocol client 作为阶段级辅助。
- 从新任务配置和 WebUI 中移除 Browser Use、Skyvern、Cloak、本地指纹浏览器。
- 历史记录保留旧驱动名称。
- 不删除旧模块，先进入观察期。

完成标准：新任务不会选择废弃驱动；Roxy + Protocol 调用链和 CLI/WebUI 兼容契约通过。

## 4. 阶段 2：统一 Attempt/Run/Checkpoint

内容：

- 为现有注册任务补充 `attempt_id`。
- 建立 `registration_attempts`、`registration_runs`、`registration_events` 的增量字段/表。
- 不可逆请求前写检查点。
- Token 后立即保存核心账号。
- 重试创建新 Run，不创建新 Attempt。

完成标准：进程中断、请求未知和 Token 后崩溃都有可恢复路径；数据库 verify 通过。

## 5. 阶段 3：Roxy 状态机和 Protocol 协同

内容：

- 页面状态统一为 `EMAIL_FORM`、`AUTH_TRANSIENT`、`PASSWORD_CREATE`、`PASSWORD_LOGIN`、`OTP_EMAIL`、`PROFILE`、`AUTHENTICATED`、`AUTH_ERROR`、`LOGGED_OUT`、`UNKNOWN`。
- 邮箱提交只保留一个阶段总等待器。
- 密码页以实际表单状态为准。
- OTP 已验证和邮箱已验证成为显式终态。
- Protocol 与 Roxy fallback 共享总超时。
- Session 退出态快速结束。

完成标准：现有 710、713、709 场景可以用 fixture 重放，并得到预期状态和下一步动作。

## 6. 阶段 4：后处理和恢复

内容：

- 2FA、Codex、套餐查询转为独立后处理任务。
- 生成 `next_action`，如 `retry_twofa`、`reconcile_session`、`resume_email_verification`。
- 资源租约和后处理任务绑定 Attempt/Account。
- 不因后处理失败回滚注册核心。

完成标准：注册核心和能力状态独立；部分成功可以补跑，不会重复注册。

## 7. 阶段 5：异步任务中心投影

内容：

- 注册事件异步投影到 `operation_tasks/operation_batches`。
- 禁止每个任务更新时刷新全表批次。
- 按 batch 加锁、固定顺序更新、失败重试。
- 增加投影延迟和事实/投影对账指标。

完成标准：并发测试无死锁；注册事实不受投影失败影响；批次最终计数一致。

## 8. 阶段 6：诊断和性能

内容：

- 取消所有脱敏逻辑。
- 诊断覆盖核心失败、部分成功和后处理失败。
- 增加邮箱证据和最后确认状态。
- 记录每个阶段的单调耗时和等待原因。
- 普通模式不改变功能，只消除重复/无效等待。

完成标准：诊断与任务、邮箱、Attempt 一一对应；普通流程耗时可以拆分为内部/外部因素。

## 9. 每个提交的固定检查

```text
目标模块测试
相关领域测试
完整测试
路由/接口契约测试
数据库迁移 verify（涉及存储时）
git diff --check
确认没有修改 .env、logs、run、.venv、账号和 Token
```

每个窗口提交必须说明：改动范围、测试命令、未覆盖风险、是否需要其他窗口配合。
