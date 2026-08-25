# 管理后台数据架构

## 目标

WebUI 不直接调用“加载整个集合”的业务函数。账号、注册任务、账号操作任务、邮箱池、
Codex 凭证和总览全部通过统一的管理仓储读取，并遵守以下约束：

- PostgreSQL 是唯一事实来源；JSON/TXT/HTML/Codex 文件都是兼容输出。
- 列表查询必须在 SQL 中完成筛选、排序、计数和分页。
- 关联数据按页批量读取，禁止逐行查询。
- 写操作只修改目标行；跨表状态变更必须在一个事务中提交。
- 列表响应统一返回 `items`、`total`、`page`、`page_size`、`facets` 和 `revision`。
- 轮询使用 `revision` 判断是否需要重新渲染；同一列表只允许一个在途请求，手动刷新会排队。
- 迁移、启动恢复和兼容导出不能改变业务行数。

## 分层

```
WebUI routes
    |
    +-- admin_repository.py   管理列表的 SQL 读模型、分页、facets、revision
    +-- db.py / services      业务命令、状态机、行级 CRUD、跨表事务
            |
            +-- record_store.py       关系表、部分更新、原子抢占
            +-- compat_export.py      去抖兼容导出
```

`admin_repository` 只负责读取，不触发迁移、同步文件或远程调用。业务命令不能通过
“读全表 -> 改 Python list -> 写回”实现。

## 数据表

现有关系表继续保留：

- `registered_accounts`
- `registration_jobs`
- `email_pool_outlook`
- `email_pool_generic_api`
- `account_action_batches` / `account_action_tasks` / `account_action_events`
- `proxy_leases`

新增关系表：

- `email_pool_domain`：Cloudflare 域名邮箱。
- `email_pool_icloud_hide`：iCloud Hide My Email 别名。
- `codex_credentials`：CPA 兼容凭证内容、归档/导出/刷新元数据。

稀疏字段继续存放在每行的 `data JSONB`，用于筛选和关联的稳定字段提升为普通列。
新表切换前必须运行幂等迁移并逐字段验证；运行时不从旧 blob 或文件静默回退。

## 列表读模型

### 注册任务

- 过滤、状态投影、计数、分页在 SQL 中完成。
- `display_status` 由任务和关联账号共同投影。
- 当前页的重试链和账号信息分别批量查询一次，禁止调用 N 次 `get_retry_info`。
- 状态 facets 使用聚合查询；批次进度只读取最新批次相关行。

### 账号

- SQL 处理归档、日期、邮箱、来源、套餐、Token、密码、试用、TOTP、风险和 Codex 状态。
- facets 使用聚合，不为生成下拉选项加载完整账号 JSON。
- 套餐/提链轻量轮询只查询当前页所需列及全局 revision。

### 邮箱池

- 四张来源表通过 `UNION ALL` 形成统一只读视图。
- 先按来源和条件分页，再只为当前页关联账号 Token/TOTP。
- 更新、删除按 `(source, id/email)` 定位具体表并执行行级命令。

### Codex

- `codex_credentials` 是事实来源，列表、汇总、Token 刷新调度均从表读取。
- `codex_accounts/codex-*.json` 和导出状态 JSON 由数据库变更生成，不参与列表读取。
- 单凭证下载直接从数据库内容生成；需要 CPA 文件时按需刷新兼容文件。

### 总览

- 账号、任务、邮箱池和 Codex 指标使用 SQL 聚合。
- 不加载业务完整行，不扫描凭证目录。

## CRUD 约束

- Create：数据库生成主键；需要关联邮箱池/账号时使用同一事务。
- Read：单行按主键/唯一键读取；列表必须使用管理仓储。
- Update：`PATCH` 语义，只更新明确字段；批量更新使用 `UPDATE ... WHERE id = ANY(...)`。
- Delete：先解析并验证精确目标，再删除单行/明确 ID 集合；运行中任务受状态守卫保护。
- Archive/stop/retry 等领域动作保留专用命令，不伪装成任意字段更新。

## 性能门槛

测试数据至少覆盖 1000 个账号、2000 个注册任务、2500 个账号任务、1000 个邮箱和
500 个 Codex 凭证。每个 20 行列表需满足：

- SQL 次数不随总行数线性增长。
- 注册任务列表不超过 8 次 SQL；其他列表不超过 12 次 SQL。
- 本机隔离数据库端到端目标低于 150 ms。
- 列表响应不得包含未请求的完整 Token、密码或 refresh token。

## 上线切换

迁移必须在维护窗口执行，且先备份数据库；兼容文件不能作为回滚依据。推荐顺序：

1. 在与生产同版本的独立数据库运行 `--dry-run`，确认来源、数量和重复键。
2. 暂停 WebUI、CLI worker 和定时任务，避免迁移期间继续写旧集合。
3. 备份 PostgreSQL 后运行 `--apply`；该步骤幂等，保留历史主键并同步序列。
4. 运行 `--verify` 做逐条字段对账，只有返回 0 才允许启动新版本。
5. 启动服务后检查总览计数、四类列表分页、单行更新和兼容导出，再恢复 worker。

若验证失败，不启动新版本；恢复数据库备份并继续运行旧版本。不要通过复制根目录
JSON/TXT 或 `codex_accounts/` 回写数据库，它们只是可能滞后的兼容输出。
