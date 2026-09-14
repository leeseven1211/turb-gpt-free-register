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
  /Users/lihongwei/code/personal/gpt/turb-gpt-free-register-opt-release-20260914 \
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
`run/`、`.venv/`、数据库/JSONL 运行产物和符号链接不会进入发布目录。已存在 release
不覆盖。

`switch` 会先完整校验目标 manifest 和依赖锁，再用同目录临时符号链接执行原子替换，
记录 previous release 到 state 文件；旧目录保留。`rollback` 只切回已校验的 state
目标或显式 release id。两个命令都不调用 systemd、launchd、WebUI 或数据库迁移，
因此本轮不会真实部署。

## 性能检查边界

```bash
python tools/test_performance.py --rows 1000 --samples 20 --json
```

脚本在显式测试库的随机 `test_` schema 中生成千级账号，测量
`core.db.list_accounts_page(limit=50)` 的 SQL 次数和 latency p95，并输出标记为
`synthetic_queue_samples` 的队列等待 p95。它会只删除自己生成的 schema，不读取或
修改生产数据。队列样本是可复现合成指标，不冒充真实 worker 排队观测；若 API 的
实际 query/p95 超过报告中的阈值，应保留真实结果并在发布评审中阻断，而不是调高阈值。

## 路由契约摘要

路由快照仍由 `tests/test_route_contract.py` 的显式数量和 SHA-256 固化。相对于
`1006937` 到 `f33e523`，`/api/extract-link/types` 是已评审的既有新增；本提交再
明确加入公开 `GET /healthz` 与 `GET /readyz`。当前快照为 112 条路由，更新理由和
摘要保留在测试注释中，不能用运行时 `len(app.url_map)` 代替预期值。
