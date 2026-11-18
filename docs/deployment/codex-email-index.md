# Codex 列表账号邮箱索引

Codex 列表使用 `LOWER(BTRIM(COALESCE(email, '')))` 关联账号。账号表新增的
`idx_registered_accounts_normalized_email` 是非唯一 Btree 表达式索引。
它不合并历史邮箱、不改变查询与返回字段；统计信息帮助 PostgreSQL 选择关联计划。

新库初始化会创建索引并执行一次 `ANALYZE`。已存在且定义正确、有效的索引会直接复用，
重启不重复分析。现有大表应在切换代码前在线预建，避免普通初始化建索引期间阻塞写入。
本文是发布步骤，不能代替目标实例的部署授权或执行回执；本地与 Oracle 分别核验。

## 上线前预建

使用实例已有的受保护 PostgreSQL 连接配置，不在命令行输出密码。
先确认当前数据库、`TURB_DB_SCHEMA`、表规模、备份与运行负载。下面的 `app_schema`
需要设置为该实例实际 schema，不能直接沿用测试库的名字。

在 `psql` 中查看当前对象（不存在时返回零行）：

```sql
\set ON_ERROR_STOP on
\set app_schema public

SELECT current_database(), current_user;
SELECT c.relkind, i.indisunique, i.indisvalid, i.indisready,
       i.indislive, i.indnkeyatts, i.indnatts,
       pg_get_indexdef(c.oid) AS definition
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_index i ON i.indexrelid = c.oid
WHERE n.nspname = :'app_schema'
  AND c.relname = 'idx_registered_accounts_normalized_email';
```

只有没有同名对象时执行创建。正确且有效的已有索引跳过创建；错误定义、唯一索引、
无效索引或同名非索引对象应先处理原因，不能用 `IF NOT EXISTS` 掩盖。
下面各条命令在自动提交模式单独执行，不能放进 `BEGIN` 或迁移框架的事务里：

```sql
SET lock_timeout = '5s';
SET statement_timeout = '30min';
CREATE INDEX CONCURRENTLY idx_registered_accounts_normalized_email
ON :"app_schema".registered_accounts (LOWER(BTRIM(COALESCE(email, ''))));
ANALYZE :"app_schema".registered_accounts;
RESET statement_timeout;
RESET lock_timeout;
```

超时是本次构建失败，不能据此认定完成。`CONCURRENTLY` 避免持有阻塞正常写入的建索引锁，
但仍有扫描、CPU、IO 和等待旧事务的成本；30 分钟只是本步骤的执行上限，不是完成时间承诺。
`ANALYZE` 必须在创建成功后完成，不能只看到索引名字就切换版本。

再次运行上述元数据查询，确认索引有效、ready/live、非唯一且只有一个表达式键，
定义为账号表上的精确表达式、无谓词、无 INCLUDE 或额外排序/运算符类设置。
新版本初始化也会核对这些条件，不会自动删除不匹配的对象。
对已有非空表再检查表达式统计：

```sql
SELECT attname, null_frac, n_distinct
FROM pg_stats
WHERE schemaname = :'app_schema'
  AND tablename = 'idx_registered_accounts_normalized_email';

SELECT pg_size_pretty(pg_relation_size(
    format('%I.%I', :'app_schema', 'idx_registered_accounts_normalized_email')::regclass
)) AS index_size;
```

空表可能没有统计行；有历史数据却没有统计时，检查 `ANALYZE` 的执行结果和权限。
保存对象定义、有效性、统计、空间与构建耗时后，按[部署与运维](operations.md)切换版本。
上线后分别核对列表首屏、深页、归档、组合筛选、总数及关联 ID，并观察查询和写入延迟。
合成测试的数据分布与并发不能替代这些检查。

## 构建失败与回退

取消或超时可能留下 invalid 索引，它仍可能产生写入维护成本。
先确认没有正在执行的构建，再确认该对象就是本次失败创建的候选，保存定义与失败记录。
对已确认归本次构建的失败索引，在事务外逐个删除后重新执行创建和分析：

```sql
DROP INDEX CONCURRENTLY :"app_schema".idx_registered_accounts_normalized_email;
```

不要删除来源未知的同名对象，也不要同时启动两个构建。若失败原因尚不明确，保持旧代码，
先解决原因；新代码遇到同名错误或 invalid 索引会明确报错。

这是附加索引，回退应用代码通常可保留它，不需要回滚账号数据。
如确需移除，应先回退到不要求该索引的版本，再在维护流程中单独删除；当前版本的下一次
初始化会补建缺失索引。回退代码、删除索引和生产重启分别记录，不能由测试通过推断已执行。

依据：PostgreSQL 16 [表达式索引](https://www.postgresql.org/docs/16/indexes-expressional.html)、
[并发建索引及失败恢复](https://www.postgresql.org/docs/16/sql-createindex.html)。
