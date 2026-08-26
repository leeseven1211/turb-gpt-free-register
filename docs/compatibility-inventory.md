# 兼容入口与孤儿代码清单

> 更新时间：2026-08-26
>
> 本清单只记录已经完成调用审计的对象。兼容入口在观察期内继续保留，删除前需要再次
> 执行全仓库调用搜索和完整测试。

## 当前保留的兼容入口

| 入口 | 真实实现 | 保留原因 | 删除条件 |
| --- | --- | --- | --- |
| `core.roxy_registration` | `core.registration.roxy` | 外部脚本、历史测试和旧日志工具可能导入旧路径 | 连续一个稳定版本无源码/工具/部署脚本调用，并完成导入兼容检查 |
| `core.browser_use_registration` | `core.registration.browser_use` | BrowserUse/Skyvern 历史调用路径 | 连续一个稳定版本无调用，并完成 BrowserUse/Skyvern 运行验收 |
| `core.db` | `core.storage.db_legacy` 及领域仓储 | 业务模块、工具和测试仍使用统一旧 façade | 账号/任务/邮箱/Codex 调用全部迁移到领域仓储，完成字段对账 |
| `core.operation_task_store` | `core.storage.operation` | 统一任务中心旧导入和测试 patch 点 | 所有运行时调用改用 storage operation 子模块，并完成观察期对账 |
| `core.account_task_store` | `core.operations.legacy_task_store` | 旧 `account_action_*` 任务在兼容观察期内继续写入 | 统一 operation 原生 run 覆盖全部任务类型至少一个稳定版本 |
| `main.run_registration` | `core.registration.dispatcher.run_registration` | CLI/外部调用兼容 | CLI 和外部工具全部切换 dispatcher 后再删除 |

## 已清理对象

| 对象 | 审计结果 | 处理 |
| --- | --- | --- |
| `core/mail_password_change.py` | 全仓库无调用；依赖的 `core.mailcom_client` 不存在；README/运行入口均无启用说明 | 2026-08-26 单文件删除 |

删除只针对已确认的单个文件，没有递归删除目录，也没有触碰运行时数据、账号、Token、
邮箱池、日志或数据库表。

## 任务模型观察期

- Codex OAuth 已使用原生 `operation_tasks/operation_runs`；
- 查活、套餐、AT 刷新、封号扫描、账号配置和注册后置步骤经 `task_gateway` 写入旧任务
  兼容模型，再由 `operation_projection` 幂等映射到统一模型；
- `operation.verify()` 必须保持注册任务、账号任务、事件映射数量一致，且不得出现孤儿
  run/event、重复活跃账号资源族、终态租约或终态 acquired resource；
- 观察期内不删除 `account_action_*` 表，不重排任务 ID，不覆盖历史 run/event。
