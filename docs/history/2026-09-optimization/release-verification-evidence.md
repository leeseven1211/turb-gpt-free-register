# 优化版本测试与发布检查

## 支持矩阵与依赖锁

项目仍在 `pyproject.toml` 声明 `requires-python = ">=3.10"`。当前提交的
`requirements.txt` / `requirements-dev.txt` 是用 Python 3.12.13 resolver 根据
已验证基准生成的版本锁；已验证运行点是 **CPython 3.12.13、macOS
x86_64**。它不是从主环境 `pip freeze` 导出的跨平台 wheel 锁，也不宣称
Python 3.10--3.13 或其他操作系统无需重新解析。迁移到其他解释器或平台时，
应先更新 `requirements.in` 输入并在目标平台独立 resolver 环境重新生成、安装和
执行 `pip check`。

依赖输入和锁的关系由 `tools/check_dependencies.py` 检查：直接输入必须是
`name==version`，锁必须覆盖直接依赖、没有冲突版本、不得包含 editable/VCS/本地
路径，开发锁必须完整继承运行锁。检查不读取正在运行的虚拟环境。

## 统一隔离测试入口

本地优化验证使用协调器 launcher（它从共享服务获得测试 DSN，并改写到
`turb_opt_20260914`，不会把生产 `.env` 注入测试进程）：

```bash
/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python \
  /tmp/turb-optimization-20260914.mJ7Y6R/run.py \
  YOUR_OPTIMIZATION_WORKTREE \
  -m pytest -q
```

`tools/test_isolated.py` 是仓库内的统一入口实现：静态收集应用配置环境键，清除
继承的配置后显式设置 `PYTHON_DOTENV_DISABLED=1`、`TURB_ALLOW_PRODUCTION_DB=0`
和 `TURB_DB_SCHEMA=test_*`，先对非生产 PostgreSQL 执行 `SELECT 1`，连接失败直接
失败而不是 skip 或回退文件。配置测试用 `patch.dict`/`monkeypatch` 明确表达
环境 override；诱饵 `.env` 回归确保锁定环境不会加载它。

数据库目标先经过 psycopg `parse_conninfo` 语义解析，生产库拒绝同时覆盖 URI
percent 编码数据库名与 query 中的 `dbname` 覆写；错误输出只保留脱敏的主机、端口、
数据库名标签。测试表使用 `PostgresTestCase` 临时 schema，禁止 `public` 和生产库。

CI 使用 GitHub Actions 临时 PostgreSQL service；不在本项目创建常驻 compose 服务。
数据库 service 缺失、不可连接或 schema 初始化失败都会使测试 job 失败，不能以 skip
伪装成功。

## 启动与 readiness

`/healthz` 是不访问数据库的公开 liveness 接口；`/readyz` 同时检查只读
`SELECT 1` 和 runtime。Goodall 提供的 `runtime_status()` 结构为：

```text
ready, started, pid, started_at,
executor, codex_dispatcher, dependency_dispatcher, projection_worker
```

`codex_dispatcher`、`dependency_dispatcher`、`projection_worker` 都必须是包含
`started=true` 与 `alive=true` 的状态对象（可使用明确的 `healthy=true` 兼容字段）。
缺失、error、未启动或线程不活跃均返回 HTTP 503；executor 可以 lazy 尚未创建，
但其 error 仍返回 503。顶层 `ready` 只表示启动流程完成，不能替代线程 liveness。

`webui.sh start` 在记录进程存活后轮询 `/healthz` 和 `/readyz`，只有 HTTP、数据库和
必需 worker 全部就绪才成功；`webui.sh check` 只做一次只读检查。超时会终止本次
启动的进程并清理 PID 文件，不影响已有服务。

## 固定版本发布目录与回退

`tools/release.py` 默认是 `check`，不会部署或触碰当前服务：

```bash
python tools/release.py check
python tools/release.py prepare --source . --releases-dir /srv/turb/releases --release-id 20260914.1
python tools/release.py switch --releases-dir /srv/turb/releases \
  --release-id 20260914.1 --current-link /srv/turb/current
python tools/release.py rollback --releases-dir /srv/turb/releases \
  --current-link /srv/turb/current
```

`prepare` 只接受干净 Git 工作树中的 tracked 文件，先复制到随机 staging 目录，
写入固定 `release-manifest.json`（commit、Python 声明、文件大小/SHA-256、两份锁
摘要），校验通过后才原子改名为 release id。`.env`、账号、Token、代理、日志、
`logs/run/`、`.venv/`、数据库/JSONL 运行产物和符号链接不会进入发布目录。已存在 release
不覆盖。

`switch` 会先完整校验目标 manifest 和依赖锁，再用同目录临时符号链接执行原子替换，
记录 previous release 到 state 文件；旧目录保留。`rollback` 只切回已校验的 state
目标或显式 release id。两个命令都不调用 systemd、launchd、WebUI 或数据库迁移，
因此本轮不会真实部署。

## 性能检查边界

```bash
/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python \
  /tmp/turb-optimization-20260914.mJ7Y6R/run.py \
  YOUR_OPTIMIZATION_WORKTREE \
  tools/test_performance.py --rows 1000 --history-rows 2000 --samples 20 \
  --workers 3 --queue-tasks 32 --json
```

脚本在显式测试库的随机 `test_` schema 中生成至少 1000 条合成账号，并在列表测量
之前通过一次 PostgreSQL bulk SQL 事务 seed 至少 2000 条终态 synthetic
operation task/run 历史。历史行使用独立 source system 且状态为终态，不会被 durable
dispatcher 再次领取；它们仍是任务中心真实读模型消费的行。脚本只删除自己生成的
schema，不读取或修改生产数据。

列表测量覆盖两个真实 `Flask test_client` HTTP 路由，且分别报告 SQL 次数和每次请求
latency p95（不构造 baseline）：

- 账号列表 `/api/accounts?paged=1&page_size=50`，由
  `core.admin_repository.list_accounts` 返回，至少 1000 条账号数据。
- 任务中心 `/api/operations?page=1&page_size=50`，由
  `core.storage.operation.list_tasks` 与 `list_batches` 返回，至少 2000 条终态
  task/run 历史。

当前发布门禁中，账号列表最多 3 条 SQL、任务中心最多 10 条 SQL，两个路由 p95 均须
不超过 250ms；报告会保留真实的 per-request query count、p95 和 max，超出即阻断，
不会通过改变阈值掩盖历史负载结果。

调度测量通过 `submit_durable_operation` 提交并用
`register_operation_handler` 注册一个 `synthetic_no_network` handler，经真实共享
`AccountOperationExecutor` 和 durable `task_gateway` scanner 执行。helper 先完成
PostgreSQL claim，再调用 handler；脚本在真实 enqueue、handler entry、完成点采集单调
时钟，因此 `queue_wait_ms` 是 enqueue 到实际执行开始的等待，而不是按序号生成的数字。
测试会先
用 gate 形成真实拥堵，报告实际吞吐与 observed max concurrency；随后在 scanner 停止
时把恢复任务保留为 PostgreSQL `queued` 行，再启动新的 scanner，确认相同 durable
行恢复完成。该“restart”是进程内 dispatcher scanner 的可控重启，不重启当前服务，
也不声称覆盖进程崩溃后的所有恢复语义；负载明确不产生网络请求。

首轮 `queue_wait_samples=[(index*7)%43]` 及据此得出的“40ms”结论均已撤销、未验收，
不得作为可比较 baseline。若列表真实 query/p95、并发上限或 durable recovery 不满足
报告阈值，应保留真实结果并在发布评审中阻断，而不是调高阈值。

benchmark 的清理位于嵌套 `finally` 中：即使 shared executor shutdown、隔离 schema
删除或连接池关闭失败，也会尽力按顺序恢复调用方原有的 `TURB_DB_SCHEMA`、
`ACCOUNT_BATCH_WORKERS` 与 `OPERATION_TASK_DB_SCHEMA`。

## 任务中心历史负载读路径优化证据

此前的真实 20-sample 结果在同一 launcher、同一路径、1000 个合成账号和 2000 条
终态 task/run 历史上为任务中心 p95 **1453.913 ms**（max 1462.994 ms，8 条
SQL），因此是有效的 250 ms 门禁失败，不是被缩小历史或改阈值得出的结论。

只读定位链为 `webui/routes/operations.py:api_operations` ->
`core.storage.operation.list_tasks`/`list_batches`。在 `turb_opt_20260914` 的随机
`test_diag_*` schema 上做的 `EXPLAIN (ANALYZE, BUFFERS)` 显示，最贵的是
`core/storage/operation.py` 原 `list_tasks` 的 `run_count` facet：执行约
**895.077 ms**，其中按 task 的相关 `COUNT(operation_runs)` 被重复用于 facet
表达式和过滤，且每个列表关系还重复执行 current-run LATERAL 兼容投影。批次列表
本身的计划约 0.568 ms，不是瓶颈。

当前最小写集只涉及任务中心只读查询：`DISTINCT ON (task_id)` 按原有
active-first/run number/id 顺序一次选择 current run；按 task 聚合一次 run count；
count 与各 facet 只加入实际需要的派生关系。没有改变任务、运行、reconciliation、
dispatcher 或 recovery 写路径。

同样的 20-sample benchmark 在该读路径优化后实测为：任务中心 p95 **43.229 ms**、
max 45.053 ms、每次仍为 8 条 SQL；账号列表 p95 17.633 ms、max 19.716 ms、每次
3 条 SQL。随后在独立锁定环境 `/tmp/turb-opt-release-lock-20260914` 同样运行 20
samples，任务中心 p95 51.983 ms、max 53.025 ms，账号列表 p95 17.071 ms；门禁仍
通过。历史 seed、HTTP route、PostgreSQL schema 和 250 ms 门禁均不变；结果是
真实合成负载观测，不是生成的 baseline，集成后的机器仍需重新记录前后实测值。

## 路由契约摘要

路由快照仍由 `tests/test_route_contract.py` 的显式数量和 SHA-256 固化。相对于
`1006937` 到 `f33e523`，`/api/extract-link/types` 是已评审的既有新增；本提交再
明确加入公开 `GET /healthz` 与 `GET /readyz`，以及单条已核对的
`GET /api/config/snapshot` delta。当前固定快照为 113 条路由，数量与 SHA 都写死在
测试中，不能用运行时 `len(app.url_map)` 代替预期值。
