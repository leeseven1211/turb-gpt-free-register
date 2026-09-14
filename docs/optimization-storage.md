# 存储一致性优化

本文记录 2026-09-14 的 P0 行级存储改造边界。PostgreSQL 行表仍是事实来源，根目录
JSON/TXT 和 `accounts_viewer.html` 只由兼容导出任务生成。

## 写入不再使用全表快照

普通业务写入口不再执行 `_load_X -> 修改 list -> _save_X`：

- `insert_account` 使用数据库 identity 生成账号 ID，并在一个事务中 patch/insert 账号和
  Outlook 邮箱池；同一邮箱通过事务级 advisory lock 串行化。
- `update_account_*`、Token 元数据同步和启动恢复使用目标行的字段 patch；恢复只把
  `queued/running` 改成失败，不增删业务行。
- `create_job` 使用数据库 identity；`create_retry_job` 在同一任务链上使用事务级
  advisory lock，拿锁后重新读取状态和活跃子任务，因此并发重复请求只会创建一个 retry。
- 首次访问新 schema 时，行表 DDL 也在数据库事务级 advisory lock 内执行，多个 worker
  同时触发 `create_job`/`insert_account` 不会竞争 PostgreSQL 的表类型创建。
- 任务进度、批量导入、邮箱回收和 iCloud HME 同步均只更新命中的行。账号与邮箱池的
  关联状态在同一事务内提交。
- Codex 凭证继续使用按身份的 advisory lock、数据库 upsert 和原子计数更新。

`_sync_table` 现在只是迁移期/旧测试的兼容接缝，不是业务写 API：

1. 没有 `id` 的记录由数据库生成 ID；快照中缺失的当前行永远不会被删除。
2. 带 `__record_version` 的现有行使用 PostgreSQL `xmin` 校验；版本变化时抛出
   `SnapshotConflictError`，不会静默返回成功。
3. 没有版本的现有行只有完全相同才是 no-op；内容不同会显式抛出
   `SnapshotConflictError`，避免陈旧快照全字段覆盖当前行。

当前仍存在的 `_load_*`/`_save_*` 名称全部属于兼容层：

- `_load_*` 被静态导出、查看器/列表读取和迁移期只读逻辑使用；这些路径不写业务表。
- `_save_outlook`、`_save_generic_api_emails`、`_save_accounts`、`_save_jobs`、
  `_save_domain_pool`、`_save_icloud_hide_pool` 只保留给兼容测试/显式迁移调用，底层
  已拒绝无版本的现有行快照覆盖，且没有正常业务调用方。
- `_save_together` 也没有正常业务调用方；业务跨表写入已分别在目标事务内完成。

## JSONB 边界

`data` 是 JSONB 扩展片段，不是第二份完整扁平记录。写入时会过滤提升列、派生列、`id`、
`data` 以及 `copy_line`、`account_copy_line`、`__record_version`；平面字段仍按提升列
优先处理。这样任务的 `config_snapshot` 等稀疏数据可以保留在 JSONB，同时不会让展示字段、
快照版本或提升字段在 `data` 中制造第二个事实来源。JSONB 合并沿用 PostgreSQL `||`
的浅层 merge 语义，未触及的顶层键继续保留。

### 合并复审补充：嵌套元数据与派生列

浅层 JSONB merge 不能保护 `extra_json` 内部的并发修改。密码、密码能力、MFA
设置/轮换/清理、2FA 状态和会话回写现在通过同一个事务内的账号行锁读取并更新
最新元数据；TOTP 与邮箱池仍一起提交，任一写入异常会整体回滚。注册账号重入
只合并明确提供的 extra 键。Sub2API 同步也改为读取当前锁定行，不再从最多
5000 条的预取列表判断是否存在，避免把现有账号误判为新账号并覆盖凭证检查点。

无关字段 upsert 不再把派生 `deactivated` 重置为默认值；生成列无论在顶层还是
嵌套 data 中都不会重复存入 JSONB。Identity 校准与表写入互斥且不回退序列。
Token 元数据写回时在 SQL 中复查当前 Token，避免旧 Token 的解析结果覆盖新会话。

`tests/test_account_metadata_concurrency.py` 使用两个真实数据库连接与数据库锁
等待，确定性制造“业务调用开始后、读取锁释放前另一事务提交检查点”的交错。
用首轮 b8c790f 的相关函数在隔离进程中对照运行，12 项测试中 11 项失败；修复后
包含新增导入、序列及 Token CAS 场景的回归重新执行，不把并发安全仅建立在内存
锁或 mock 成功返回上。

## 验证

新增 `tests/test_storage_snapshot_safety.py` 覆盖：

- 全新 schema 首次调用 `create_job`/`insert_account` 会先初始化表；
- 版本化和无版本陈旧快照的显式冲突；
- 兼容快照不会删除未提及的新行；
- 嵌套 `data` 的保留、浅层 merge、保留字段过滤；
- 数据库生成 ID 的真实并发插入、不同字段并发更新、重复 retry 创建；
- 启动恢复前后业务表行数不变。

测试通过指定的隔离 launcher 执行，使用独立 `turb_opt_20260914` 数据库和测试 schema；
没有读取生产 dotenv 到测试运行环境，也没有修改 `tests/conftest.py` 或
`tests/support_pg.py`。
