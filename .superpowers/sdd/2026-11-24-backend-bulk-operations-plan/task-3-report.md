# Task 3 报告

状态：已完成。

实现：

- 新增 `core/storage/accounts/bulk_mutations.py`，提供 `archive_many`、`delete_many`、`update_note_many`、`set_email_invalid_many`，均支持调用方的 `conn`，返回 Task 1 `BulkItemResult` 序列。
- 归档、删除、备注稳定去重并保留目标首次输入顺序；账号行按 ID 固定顺序锁定，一次集合写入并使用 `RETURNING`。不存在目标为 `account_not_found`；邮箱身份变化为 `account_email_changed`。
- 邮箱失效保留现有邮箱协调锁、账号→地址账本→母资源锁序、真实副号关联范围和资源 scopes，使用 `jsonb_to_recordset` 每张关联表一次集合写入，保持 OpenAI/Codex/Token/资源使用状态不变。
- 单条归档、删除、备注直接复用新 storage 方法；bulk 路由仅提交一个 durable command，返回 202 和 task/run/command ID，兼容结果列表及 count 字段保持为空或 0，未伪造执行完成。
- 暴露 `register_handlers()`，操作名为 `account_archive`、`account_delete`、`account_note`、`account_email_invalid`；handler 固定接受共享连接，parameters 使用显式 allowlist。Worker 启动安装由集成任务处理。
- 更新授权范围内的 `test_account_email_invalid_api.py`，对齐 202 异步受理并确认未调用旧同步命令。

TDD：

- 首先新增测试并运行，因新模块不存在而失败。
- 隔离 PostgreSQL 首轮运行发现邮箱池的失效事实非 promoted 列，修正为按表字段定义合并 JSONB 后验证通过。
- 新增测试覆盖实际 HTTP 受理→完整 command 参数持久化→claim→handler→逐项回执，确认邮箱快照映射完整且 JSON key 为字符串。

验证：

- 使用主 checkout `.venv/bin/python`、`/tmp/turb_backend_bulk_test.env` 中非生产 `turb_test` 连接运行 `tools/test_isolated.py --profile all -- tests/accounts/test_account_bulk_mutations.py tests/accounts/test_account_email_invalid_api.py tests/accounts/test_account_note.py tests/accounts/test_email_invalid_storage.py -q`：39 passed、37 subtests passed；无 skip。
- `python -m compileall -q core/storage/accounts/bulk_mutations.py webui/routes/accounts.py tests/accounts/test_account_bulk_mutations.py`：通过。
- `git diff --check`（Task 3 路由和旧 API 测试文件）：通过。

风险与边界：

- 未修改注册、Roxy、Proto2、Codex 业务执行流程，没有新增账号删除保护或业务限制。
- 副号组是一个命令目标，组回执的数据包含真实账号 IDs/updated_count 和关联资源 counts；没有账号但存在邮箱池资源时仍会更新并报告资源数量。
- 原同步 bulk HTTP 调用方需要消费 202 并查询命令回执；UI 和 Worker assembly 安装由后续集成任务统一处理。
- 复用现有邮箱 validity 私有纯函数和行查询辅助，以保持现有 scopes 和关联语义一致；后续若该模块内部接口变更需同步维护。

## 审查修复

- 本地账号 bulk 路由保留原始输入中的重复项及非法目标，仅将规范数字字符串 canonical 为整数；命令持久化完整 `input_targets`，统一回执恢复 requested/duplicate/skipped 统计。
- 邮箱失效入口同样保留原始目标；`expected_emails` 的完整对应约束只针对合法账号 ID，非法目标由逐项回执说明，不丢失请求。
- storage 数字字符串限制为规范 1–19 位正整数，超长数字、前导零和非整数文本返回 `invalid_target`，不会让合法成员所在块失败。
- 同幂等键异内容冲突返回 409；202 的 command/task/run ID 输出十进制字符串。route 不再逐请求注册，registry 由 Web/Worker 组装显式安装。
- 新增真实 POST→command→claim→Worker→持久结果测试，验证 `[1,"1","bad",true,null,{},[],99]` 的 requested=8、duplicate=1、updated=1、skipped=6、failed=0，及同键复用/冲突；邮箱快照链路也覆盖重复与非法目标。
- 使用相同隔离 `turb_test` 路线运行四个相关测试文件：42 passed、33 subtests passed，无跳过；`compileall` 和 Task 3 文件 `git diff --check` 通过。
