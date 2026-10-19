# 存储架构

## 为什么改

项目源自上游 `xiaoguzuiniu/gpt-free-register`，最初是纯文件存储——`core/db.py` 在
`d40fbb3 Initial open source release` 就存在。PostgreSQL 是 `480461a`（2026-08-13）
才接进来的，接法是把**整个集合存成一行 JSONB blob**（`app_collections` 表，
按旧文件名做键）。

这个接法留下三个问题：

**写放大。** 改一个字段要 `_load_accounts()` 读全量 → 改 → `_save_accounts()` 写全量。
而 `_save_accounts` 连锁做四件事：写 2.1 MB JSON、PG 整块覆盖、重建
兼容快照和静态查看页。刷新一个账号的 AT
过期时间，实际写入 7 MB。

**丢更新。** `db._LOCK` 是 `threading.RLock`，只在进程内有效。CLI（`main.py`）和
WebUI 是两个进程，都通过 `db.insert_account` 写同一份数据，读改写会互相覆盖。

**抢占失效。** 三个 `claim_*` 函数号称"原子占用"，实现是"读出来判断状态再写回"，
跨进程根本不互斥——两边都会读到 idle，然后都以为抢到了。

## 现在的结构

```
core/postgres_store.py   连接、schema、app_collections（调度状态、兼容集合和
                         迁移期旧数据）
core/record_store.py     全部正常业务行级表：可行级 UPDATE、可跨进程原子抢占、可跨表事务
core/compat_export.py    兼容文件的去抖导出器（后台，不在写入主路径上）
core/db.py               业务数据层，建在上面三者之上
core/account_task_store.py  账号操作任务的三张关系表（更早就已拆表）
core/proxy_pool_store.py  代理库存与独占/共享子租约的 PostgreSQL 协调
core/proxy_supply.py      代理供应商后台补货、出口检测和固定供给参数适配
core/remail_order_coordinator.py  Remail 意图 CAS、原订单恢复和交付收口
```

### 表

| 表 | 内容 |
|---|---|
| `registered_accounts` | 注册成功的账号 |
| `registration_jobs` | 注册/Codex 任务 |
| `registration_attempts` / `registration_runs` | 原始注册意图、检查点与每次执行实例；CLI 与 WebUI 都持久化恢复事实 |
| `registration_batch_email_claims` | 注册批次内邮箱领取历史；失败任务释放邮箱后仍保留去重记录 |
| `email_pool_outlook` | Outlook 邮箱池 |
| `email_pool_generic_api` | 通用 API 邮箱池 |
| `email_pool_domain` | 域名邮箱池 |
| `email_pool_icloud_hide` | iCloud Hide My Email 别名池 |
| `codex_credentials` | Codex OAuth 凭证 |
| `proxy_leases` | 1024Proxy endpoint、出口 IP、出口代次、所有权和隔离期的跨进程租约 |
| `proxy_pool_resources` | 独立代理库存的 profile、后台提取/检测状态、容量和生命周期事实；全局容量由数据库协调 |
| `remail_order_intents` | Remail 付费领取意图、供应商订单关联、CAS 提交状态、核验结果和私有恢复凭据 |
| `mail_provider_orders` | MailCode/Xigua 的稳定领取身份、幂等购买键、供应商订单、已购邮箱和私有取码游标 |
| `account_action_batches` / `_tasks` / `_events` | 账号操作任务（早于本次改造） |
| `app_collections` | 调度状态、兼容集合、迁移期旧数据；不是正常账号/邮箱/Codex 列表的事实来源 |

### 独立代理库存

`proxy_pool_resources` 是独立的 PostgreSQL 库存事实，容量按所有供应商 profile 全局计算。默认策略为：最少可用库存 2、最大容量 20、领取等待 60 秒、领取最低剩余寿命 300 秒、后台复检间隔 60 秒、空闲回收 300 秒、后台 worker 2 个。预热 profile 取默认注册国家、`PROXY_POOL_COUNTRIES` 额外国家，以及独立查套餐实际使用来源时的 `PLAN_CHECK_COUNTRIES` 并集；额外预热不改变注册国家或套餐业务国家。WebUI 启动时预热；CLI 在第一次领取时懒启动。凡启用代理的注册、账号功能和套餐查询任务只领取已经检测通过的库存，供应商提取、出口检测和补货都在后台执行。数据库不可用时直接失败，不降级为直连；显式配置的 `direct` 路线仍保持直连。worker 数量支持热加载，但 WebUI 展示的 worker 数只代表当前进程，库存容量和租约由 PostgreSQL 跨进程协调。快照按来源/地区返回 `ready`、使用中、`checking`、`rotation_wait`、故障等计数，并提供 `min_ready_total`；合计底数超过全池容量时只给容量提示，不虚构可用库存。

资源状态和任务租约分开保存。注册及认证任务创建独占 `pool_leased` 子租约；套餐查询只有在显式允许复用时才创建 `shared_leased` 子租约。正常释放进入 cooldown，冷却结束后可以重新领取；明确的线路传输故障在无活跃子租约且寿命足够时进入有界的 `rotation_wait`，由后台复检同一 endpoint，等待出口变化。轮换使用原资源的 `expires_at`，新 IP 通过国家、全局 IP 隔离和次数检查后才发布；复检或换代不会延长寿命。没有变化时继续等待，连续失败达到上限或剩余寿命不足时退役。容量缩减只退役 `ready`/`rotation_wait` 等无活跃子租约资源，不驱逐仍在使用的租约；有 profile 等待者时，维护任务可以回收其他 profile 的空闲资源。供应商 `time` 是固定粘性窗口，不代表一定更换会话或出口 IP，系统只把实际检测结果写入租约。

代理租约的 endpoint 所有权与出口 IP 隔离分别记录。`proxy_leases.endpoint_owner` 默认 `TRUE`，只允许当前出口代次持有 endpoint 唯一所有权；轮换后旧锚点改为 `endpoint_owner=false` 并保留 `recent`、原出口 IP、关联任务和到期时间，新增锚点继承原 endpoint 的 `expires_at`。endpoint 唯一索引使用 `endpoint_owner=true` 条件，出口 IP 的唯一约束、占用统计和复用次数仍跨 endpoint/profile/进程生效；迟到释放或迟到复检必须匹配原 token 与锚点，不能改写新代。旧索引迁移必须幂等执行，不能把改变谓词写进 `CREATE INDEX IF NOT EXISTS` 后就假定已有索引已更新。

代理池的 WebUI 入口是只读快照，返回脱敏状态、统计和生命周期信息，不承载领取/释放操作。完整供应商地址和凭据仍属于环境私密配置。旧 `PROXY_1024_MAX_ATTEMPTS`、`PROXY_1024_ROTATE_SESSION_TIME` 以及 batch/rotate 参数仅为诊断兼容保留，正常库存补货不按任务派生 `time`，也不按注册批次把 `num` 预取后分配。

本机浏览器中继的恢复资料保存在原 `proxy_leases.data.browser_relay`，只记录 Profile、监听端口、域名规则和开放状态；原代理地址沿用该租约已有的私有字段。服务重启后，有恢复资料的保留窗口重建原端口与原线路；端口冲突明确失败，不改用新端口或新租约。续跑的任务与 Run 可更新，线路流量仍归原租约；确认窗口关闭后才撤销对应恢复资格。此元数据不改变租约状态，也不进入普通租约列表。

### Remail 订单意图

付费邮箱领取不以 HTTP 返回值作为唯一事实。`remail_order_intents` 先记录 `prepared`，再由数据库 CAS 选出唯一执行者写入 `submitting`；只有该执行者可以发出付费 POST。POST 返回订单号后立即持久化 `order_created`，再在有限时间内 GET 原订单补齐凭证。异常退出或网络结果未知时保持 `submitting`/`request_unknown`，恢复流程只能查询同一 `acquisition_id` 对应的原订单，不能因为幂等请求头而自动重放未知 POST。

订单私有凭证写入 `private_json`，普通查询只返回显式安全字段白名单。只有订单号、供应商/项目/模式/库存策略匹配，且 durable 状态为 `delivered` 并已保存完整私有凭证时，协调器才向注册或换绑流程交付邮箱。`owner_kind`、`owner_id` 和稳定 `acquisition_id` 将 root 任务与 retry/resume 子任务绑定，缺少身份上下文时拒绝付费下单。核验接口只能恢复当前操作所属意图，并返回脱敏订单摘要。

### 其他邮箱订单与账号巡检

MailCode/Xigua 的领取按供应商和稳定任务身份唯一绑定，在 PostgreSQL advisory lock 下恢复原订单；商品请求、幂等键在付费请求前落库，已购邮箱和取码游标随后按行合并。MailCode 的游标与私有候选验证码原子保存，恢复时重新检查时间、有效期和取码请求身份；客户端准备返回不等于远端验证成功。订单锁使用独立连接池，先在池外按阶段预算排队，避免慢供应商占满普通读写连接。客户端内存缓存只用于加速，不负责重启恢复。新供应商不改写 Remail 已有订单状态机，也不把上游文件缓存引入主存储。

账号巡检复用统一任务中心的 `operation_batches`、`operation_tasks`、`operation_runs` 和 `operation_batch_items`：父任务协调、每账号子任务走共享执行预算，清单保留最初 Run 关联用于历史读取；停止操作使用子任务当前活动 Run，单独取消子任务后同步收口父任务。AT 和套餐写回同时验证当前执行 fence 与账号邮箱/Token 快照，防止旧执行覆盖后续登录或换绑结果；套餐保存失败不覆盖已经确认的新 AT。巡检不新增 SQLite 或全量 JSON 集合。

### 字段策略：提升列 + JSONB

账号有 85 个字段且**高度稀疏**——`live_check_*` 只覆盖 11/240，`codex_agent_*` 只有
1 条——而且还在持续新增。全拆成列会让"加个功能"变成"写一次 migration"，正是
blob 方案当初被选中的原因。

所以只把进 `WHERE` / `ORDER BY` / 抢占条件的字段提升为真列，其余留在 `data jsonb`：

```sql
CREATE TABLE registered_accounts (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    deactivated BOOLEAN NOT NULL DEFAULT FALSE,   -- 派生列，见下
    plan_check_status TEXT,
    live_check_status TEXT,
    ...
    chatgpt_session JSONB,                     -- 完整 /api/auth/session，恢复用
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

加一个稀疏字段不需要改表，直接写进 `data` 即可。需要按它筛选时才提升为列。

Plus 优惠属于高频筛选字段，因此 `plus_promo_kind`、折扣比例、活动标识和展示元数据会
提升为 `registered_accounts` 真列；`account_promotion_value` 是 PostgreSQL 自动维护的
存储生成列，将折扣进一步区分为 `half_price` 与 `other_discount`。账号列表使用
`(archived, account_promotion_value, id)` 复合索引，历史 `plus_trial_*` JSONB 只在幂等
回填时解析，不进入日常列表查询热路径。

`registered_accounts.chatgpt_session` 是例外：它保存完整 `/api/auth/session` 响应，和
`access_token` 分开维护，供后续登录态恢复/续期使用；管理列表、兼容导出和普通账号读模型
均不返回该敏感字段。

独立多国家套餐查询在账号 `data` 中保存 `plan_check_countries`、`plan_check_country_results` 和
`plan_check_partial`，不新增全表迁移。`core/storage/plan_countries.py` 在同一短事务内先锁定并
校验当前 Run、执行实例和账号租约，再以账号行锁逐国合并检查点，阻止失去租约的旧执行
覆盖新结果；成功写入该国白名单结果及成功时间，失败保留该国上次成功结果。执行 Run 的
`data.plan_country_progress` 按国家保存 `wait_used`、等待切片开始/截止时间、`http_attempts`、
`pending`/`success`/`history`、重试时刻和原 Run 截止时间。首轮领取切片默认为 5 秒，单国累计等待
沿用入队时冻结的 60 秒预算；换线不重置该国 HTTP 尝试次数。初始化与每次进度更新都在执行
fence 校验下写回 Run 和账号投影；恢复先结算中断切片，已成功国家不会在同一 Run 内重查。
旧无 fence 的测试或兼容入口仍可工作，但不能借此访问生产库。公开列表和轮询均经过同一白名单
投影，不返回账号凭据、原始响应或完整代理地址。现有 Plus 优惠筛选字段由国家快照汇总更新，
各国的本次响应另外保存在任务事件中，后续查询不会覆盖旧 Run 证据。
注册查询不清空国家历史；国家列表留空后的独立查询使用原单次路径，页面不把历史国家
快照当作这次单次结果。多国家任务的 `plan_check_deadline_at` 按国家数和等待、请求预算
计算，轮询与恢复共用该期限。启动恢复在同一事务收口账号与未完成国家状态，已完成快照
和账号行数保持不变。

`registration_attempts.private_context` 保存协议注册的原密码及私有恢复上下文，仅内部恢复接口读取；普通 Attempt/Run、operation 读模型与事件投影不返回该列。公开检查点只暴露 `has_password` 和 `password_state` 等阶段信息，区分准备、开始提交和远端确认；写入必须匹配当前 Run/执行实例。CLI 按规范化邮箱绑定稳定 Attempt，不能接管已有 WebUI 意图或正在运行的实例。2FA 待确认密钥不会写成已启用的 `totp_secret`，核心账号和完整 session 在后处理前保存。

**派生列** 由 `TableSpec.derived` 声明：`deactivated` 从 `account_status` 推导。
部分更新时，只有来源字段出现在本次改动里才重算，避免无关更新把它连带清零。

**永不入库的派生字段**（`_NEVER_PERSIST`）：`copy_line`、`account_copy_line`。
读路径由 `_decorate_account` 现算，兼容文件由导出时补上。在 `record_store._split`
这个唯一收口处拦掉，好过指望十几个调用点都记得。

## 关键机制

### 接缝：`_load_X` / `_save_X`

`db.py` 里六十多处调用方是"读全量 → 改 → 写全量"的形状。这对函数是天然接缝：
换掉它们底下的实现，调用方不必动。`_sync_table` 保留整表进出的形状，但落库时
只写签名变化的行（`_row_signature` 排除派生字段，免得它自己触发写入）。

只改一行的热路径不走接缝，直接用 `_patch_account` / `_patch_job`——读全表加逐行
比对签名，243 个账号约 210 ms，只改一行时没必要。

### 原子抢占

`_stage_claim_guard` 把"未被占用，或占用已超时"整条判据翻译成 SQL，配合
`UPDATE ... WHERE ... RETURNING`，由数据库保证互斥：

```sql
UPDATE registered_accounts SET live_check_status='queued', data = data || %s::jsonb
WHERE id = %s AND deactivated = FALSE
  AND (COALESCE(live_check_status,'') NOT IN ('queued','running')
       OR (live_check_status = 'queued' AND (... < %s)))
RETURNING id
```

`rowcount == 0` 即抢占失败。时间戳是 ISO 字符串，字典序即时间序。**缺失或损坏的
时间戳一律放行**——保留原实现"解析失败就放行"的语义，否则一行脏数据会让这个账号
永远无法再被领取。

### 跨表事务

`insert_account`、`import_registered_email_accounts`、
`recover_interrupted_registration_jobs` 三个操作同时改多张表。`_save_together`
把它们并进同一个 PG 事务——原先是两次独立落盘，中间失败会留下"账号已创建但邮箱
没标记 used"，那个邮箱之后会被再领一次、重复注册。

### 兼容导出

通用 API、域名邮箱和 Codex 的兼容产物由 `core/compat_export.py` 在后台去抖生成。
账号、注册任务、Outlook 和 iCloud 邮箱池不生成根目录快照，WebUI/API 直接查询 PostgreSQL：

- 导出器只接收"种类"名，到点自己从库里重读当前状态。合并因此天然正确——最后
  一次渲染写的一定是最新状态，也不必在内存里留几 MB 的快照。
- 渲染失败只记日志不重试。兼容文件不是事实来源，不能让它拖垮业务写入；持续
  失败时重试只会刷屏。
- 进程退出前 flush。`webui.sh stop` 发 SIGTERM，Python 默认直接终止进程，
  `finally` 和 `atexit` 都不执行，所以 `web.py` 把 SIGTERM 转成 `SystemExit`
  走正常退出路径。

内部环境变量（性能开关，不进 WebUI 配置页，与 `ACCOUNT_TASK_DB_SCHEMA` 同类）：

```dotenv
COMPAT_EXPORT_MODE=debounced|sync|off      # 默认 debounced
COMPAT_EXPORT_DEBOUNCE_SECONDS=5.0
```

### 没有纯文件模式

`DATABASE_URL` 缺失或库连不上时，`postgres_store.require_ready()` 在入口直接终止
进程（`web.py` / `main.py` 各调一次）。**不再有"PG 读失败就回退兼容文件"的降级**——
静默降级会让两份副本悄悄分叉：读到旧文件、写回 PG，中间的变更就没了。

## 效果

| 指标 | 改造前 | 改造后 |
|---|---|---|
| 一次账号备注更新 | 631 ms / 写 7 MB | 19 ms / 写几百字节 |
| API 端到端 | — | 27 ms |
| 连续 20 次写入 | 渲染 20 次 | 合并成 1 次 |
| 并发改不同字段 | 互相覆盖 | JSONB `\|\|` 服务端合并，都保留 |
| 跨进程抢占 | 失效 | 由数据库保证 |

## 迁移与回滚

```bash
python tools/migrate_collections_to_tables.py --dry-run   # 只报告
python tools/migrate_collections_to_tables.py --apply     # 导入（幂等）
python tools/migrate_collections_to_tables.py --verify    # 逐字段对账
```

- 这是历史/一次性迁移工具：只从 `app_collections` 读取迁移期集合并写入行级表。
  根目录快照不再作为运行时或迁移回退来源。
- **id 原样保留**：现有 id 被 `codex_accounts/` 的文件名和
  `account_action_tasks.account_id` 引用，重排会打断这些引用。导入后
  `sync_identity` 把序列推到 `max(id)` 之后。
- 幂等：重复执行不会翻倍。
- 回滚：旧的 `app_collections` blob 仍在，可作为迁移审计落点；生产备份以 PostgreSQL 为准。

## 开发约定

**这些约定的由来是一次真实事故**：未完成的存储层代码留在了线上服务的工作目录里，
服务重启后加载了它，启动恢复读到一张空表，又把空快照当成全量写了回去，361 条
注册任务只剩 5 条。

1. **存储层改造在 worktree 里做**，线上目录常驻 `main`，重启不会加载改造中的代码。
2. **开发连独立数据库** `turb_dev`（生产数据的拷贝），不碰 `turb_console`。
3. **硬护栏**：`postgres_store.connect()` 拒绝连接 `turb_console`，挂在唯一的连接
   出口上，任何代码路径都绕不过。确需对生产库执行（正式迁移当天）要显式设
   `TURB_ALLOW_PRODUCTION_DB=1`。
4. **测试用一次性 schema**：继承 `tests.support_pg.PostgresTestCase`，每类一个
   `test_xxx_<uuid>` schema，每用例清空，结束即销毁。用 public schema 会被
   `_guard_production_schema()` 响亮拦下。
5. **启动恢复只允许改状态，绝不允许改变行数**——`tests/test_db_storage_backend.py`
   的 `StartupRecoveryTests` 锁死了这条。

判断"哪些行被物理写入"用 `xmin`（PostgreSQL 记录最后写入该行的事务号），
不要用 `updated_at`：后者是秒级精度，同一秒内的写入看不出差别。

## 后续

仍保留文件形态、但不作为 Codex 凭证事实来源的兼容产物：

- `codex_accounts/*.json` —— PostgreSQL `codex_credentials` 的 CPA 兼容输出。有真实外部
  消费者（CPA 按此格式读），因此必须保留按需生成和导出能力。
- `logs/run/sms_cancel_queue.json` —— 待取消的接码订单队列，带退避重试。这是**欠外部
  平台的动作**，崩溃后必须恢复，本质上和 `account_action_tasks` 同类。
- `logs/run/roxy_active_profiles.json` —— 孤儿浏览器环境登记表，崩溃恢复用。

**应当继续留在文件系统**的：`logs/`（WebUI、任务日志和运行时恢复状态，追加写 + 尾读）、sentinel 的子进程传参
临时文件、`.env`（装着 `DATABASE_URL` 本身，先有鸡先有蛋）、`logs/run/webui.pid`。
