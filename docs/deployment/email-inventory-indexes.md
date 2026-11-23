# 邮箱库存资格索引

邮箱来源资格查询使用九个非唯一 Btree 表达式索引。索引只改变 PostgreSQL 的查询计划，
不改变 `_eligibility`、领取、注册和重跑行为。账号表原有的规范邮箱索引继续保留。

目标索引为：

- `registered_accounts(lower(email))`
- `local_email_claims(lower(address_norm))`
- `email_address_allocations(lower(address_norm))`
- `email_pool_outlook(lower(email))`
- `email_pool_generic_api(lower(email))`
- `email_pool_domain(lower(email))`
- `email_pool_icloud_hide(lower(email))`
- `email_pool_butler(lower(email))`
- `email_butler_claim_intents(lower(COALESCE(address_norm, data->'mailbox'->>'email', '')))`

最后一个索引带谓词：`status NOT IN ('prepared', 'rejected')`。所有目标均要求
非唯一、单个表达式键、Btree、默认 `text_ops`、源字段 collation 正确，并且
`indisvalid`、`indisready`、`indislive` 均为真。

## 检查与在线预建

维护工具默认只读检查，按服务的 `override=False` 规则解析 bootstrap；显式进程变量优先，不修改 `.env`：

```bash
.venv/bin/python tools/maintenance/prepare_email_inventory_indexes.py \
  --source-root /绝对/部署源码目录
```

在目标实例已完成记录存储 v1、备份和维护窗口确认后，显式 `--apply` 才在线创建
缺失索引。工具使用受保护的 `DATABASE_URL`、`TURB_DB_SCHEMA` 和生产库 guard，
连接为自动提交模式，每个 `CREATE INDEX CONCURRENTLY` 独立执行，成功后对九张目标
表执行 `ANALYZE`，全部校验通过才写入记录存储 v2 标记：

```bash
.venv/bin/python tools/maintenance/prepare_email_inventory_indexes.py \
  --source-root /绝对/部署源码目录 --apply
```

工具会校验当前数据库和 schema 与 bootstrap 目标一致；未检测到 v1 标记、目标不匹配、
同名对象定义错误、索引无效或并发创建失败时返回分类错误，不标记 v2。部分索引已经
成功时可在原因排除后重复执行，正确对象会复用，并再次刷新统计。在线预建使用独立的排他迁移 gate；启动迁移先尝试共享 gate，再等待原 schema 锁。遇到在线迁移或其他迁移占用时，工具返回 `schema_migration_busy`，避免锁等待和并发建索引的快照互相阻塞。

## 应用启动迁移

新库初始化会创建记录存储 v1 后补齐 v2 索引。已有库如果已经记录 v1，启动时只执行
索引增量迁移，不重跑 `_apply_record_schema`。v2 已完成时直接短路。普通启动迁移适合
空库或小表；已有在线大表应先使用上面的维护工具。

索引构建失败可能留下无效索引。先确认没有仍在运行的构建，再核对对象确实属于本次
操作，必要时在事务外逐个 `DROP INDEX CONCURRENTLY` 后重试；不要删除来源未知的同名
对象。索引是附加对象，应用回滚不要求删除。
