# 独立 Web 与 Worker 运行入口

本变更提供代码与未安装模板。真实服务安装、启用、生产切换、本机与 Oracle 部署均需在代码测试完成后另行决定；本页中的路径是模板约定，不是已部署事实。已有 `deploy/systemd/turb-gpt-free-register.service` 保持 combined。

现有 `python web.py` 和不带角色的 `./webui.sh start` 仍默认 combined/Flask。独立方式是前台运行一个 `python web.py --mode web --server waitress` 与一个 `python worker.py`。Waitress 精确锁定 3.0.2，单应用进程、4 HTTP 线程，无 prefork/preload/reloader。Web 只查询和持久受理，Worker 执行现有业务 owner；Web 重启不发信号给 Worker。

## 本地显式角色

先为同一实例配置稳定 `TURB_INSTANCE_ID` 和绝对 `TURB_RUNTIME_DIR`；两个角色使用同一代码 revision、DB/schema、配置主密钥与任务日志目录。解释器先选项目 `.venv/bin/python`。控制脚本自身不读取 `.env`，子进程仍遵循现有受控 bootstrap。环境中的启动配置不要与角色含义冲突。

固定发布目录不能保存运行数据。通过服务环境指定包外绝对 `TURB_BOOTSTRAP_ENV_FILE` 后，配置读取、保存与文件锁都使用这一份 bootstrap；不要用 `PYTHON_DOTENV_DISABLED=1` 代替，它属于测试隔离开关。`TASK_RUN_LOG_ROOT` 指向共享日志目录，任务历史归档和调试文件也在该目录下。浏览器登记、公共资源缓存与仍启用的兼容导出使用稳定 `TURB_RUNTIME_DIR`；未指定外置路径的旧 combined 命令保持原目录规则。

升级接续历史任务日志或调试材料时，可将已经核实的旧日志根写入 `TURB_LEGACY_LOG_ROOTS`，值为绝对路径的 JSON 数组。该白名单只允许读取旧材料，新写入仍落共享目录。归档仍按原来的先压缩、回读验证、再清理历史流程执行，任务历史默认保留 7 天、归档文件默认保留 30 天。接续文件时保留原修改时间，独立部署备份不加入自动到期清理目录。

```sh
TURB_INSTANCE_ID=example TURB_RUNTIME_DIR=/absolute/runtime ./webui.sh start worker
TURB_INSTANCE_ID=example TURB_RUNTIME_DIR=/absolute/runtime PORT=8000 ./webui.sh start web
TURB_INSTANCE_ID=example TURB_RUNTIME_DIR=/absolute/runtime PORT=8000 ./webui.sh check all
TURB_INSTANCE_ID=example TURB_RUNTIME_DIR=/absolute/runtime PORT=8000 ./webui.sh restart web
```

支持 `start/stop/restart/status/check/logs [combined|web|worker|all]`。没有角色时仍为 combined；端口、HOST、OPEN_BROWSER、VERBOSE、STARTUP_CHECK_TIMEOUT 沿用环境参数。`AUTH_CODE` 仅传入子进程环境，不写 argv；不再对 `EXTRA_ARGS` 做不安全空白切分，需要其它参数时显式运行前台 Python。

角色身份是运行目录中原子写入的 `combined.json/web.json/worker.json`，绑定 PID、process_start、cwd、command、release 和实例。脚本不按进程名/端口收养其它进程。旧 `webui.pid` 不足以证明身份，不会被拿来发信号；原来由旧脚本启动且尚无新身份文件的进程应由原托管方式按已核实 PID 停止，再切换。

`start web` 在 `/healthz` 成功时可返回 `alive_not_ready`，不会因为独立 Worker 暂不可用而杀掉 Web。`check` 只有完整 `/readyz` 或持久 Worker 证据成立才返回 0。`start all` 先 Worker ready，再 Web ready；Web 失败保留仍运行的 Worker，并返回非零。`status` 同时报告 alive 与 ready；PID/监听不等于业务就绪。

`stop web` 只向精确 Web 身份发 TERM；`stop all` 先 Web 后 Worker。默认等待最多 90 秒，不自动发送 SIGKILL。超时返回非零并保留身份。进程退出但缺少对应 nonce 的清理回执属于 unknown，返回 3，不能输出优雅成功。`restart` 只有 stop 的清理回执为成功才重新启动。被 systemd/launchd 标记的身份禁止用此脚本旁路启动或停止，必须先通过 manager 控制，避免自动重拉。

## HTTP 和业务收尾

Waitress adapter 先关监听与后续 keepalive 受理，丢弃尚未进入应用的排队/部分上传请求并计数；已开始调用和响应继续排空。确认实际 HTTP 工作线程、响应 iterable/file wrapper、channel 和 loop 全退出后，才停止 Web config observer、导出和连接池等 runtime 资源。默认 HTTP 预算最多 20 秒，随后 runtime 使用同一总停止 deadline 的剩余预算且单阶段最多 60 秒。托管边界与应用裕量分别按实际 manager 设置，见下文。线程数不是 DB 连接预算。

`stop()` 的 True 来自实际线程/资源证据，不采用 Waitress `shutdown()` 的返回值。HTTP 超时会记录 `http_stop_incomplete`、保留未结束的 runtime/端口身份并以 3 退出；此时不谎报完整排空。runtime 停止不完整也退出 3。两个入口支持有限正数 `--shutdown-timeout`：Web 默认 80 秒、Worker 默认 60 秒，并保留 runtime 单阶段最多 60 秒。首次停止信号建立一个 monotonic deadline；异常或正常返回未收到信号时，在进入清理时建立一次。HTTP 使用 `min(http-drain-timeout, 剩余预算)`，随后 runtime 只得到剩余预算，重复信号不更新 deadline，也不打断已进入的清理。长阻塞应用和慢下载可能在硬停止时断连；一次性下载已 pop 的 token 不因断连自动恢复。

Waitress 仍完整缓冲请求体，保留 1 GiB 上限；Web spool 位于 `<runtime>/web-spool`，权限 0700。Oracle Nginx 原 20 MiB 限制不变；此变更没有增加 ProxyFix 或信任任意代理头。不要把页面可观测流量当作代理账单。

## 只读检查与数据库边界

`tools/check_runtime.py` 比对 expected instance/release/PID/process_start、fresh generation/owner nonce、running/ready、配置 revision 与全部必需组件。探针使用只读事务，不建表、不启动组件、不接管 lease/permit，不把 absent 当 ready；输出只含固定状态字段，退出前关闭探针连接池。probe 可能单独占用连接，应计入容量峰值。真实 Worker/PG 恢复和跨角色任务不重放的证据由隔离 PG 验证提供；纯 HTTP/注入测试不能替代它。

连接上限应按实际 `(DSN, kwargs)` 池键求和：Web 各池 max + Worker 各池 max + owner 专用连接 + 独立 probe 峰值。现有每池默认 12 不是每进程或全实例总量 12；不能写成全实例 25。容量测试需要记录各角色实际池键、PG 峰值、等待/timeout、线程/FD/RSS/spool 序列。

独立 Worker 在执行归属永久丢失后停止接单，并沿原总停止预算收尾，以非零状态退出，由托管服务启动新进程；当前进程不重新获取归属。配置监听或心跳的临时阻塞继续按各自恢复规则处理。归属丢失和心跳失败首次发生或原因变化时记录固定原因码，异常只记录类名，便于区分连接断开、探针超时和状态采集失败。历史账号代理上下文由独立维护线程分批补齐，受准入、取消和数据库等待预算约束，在排空任务前停止并确认线程退出。

独立 Worker 的执行归属探针间隔为 1 秒。距最近一次成功验证满 30 秒时暂停接单，满 60 秒仍未恢复则判定归属永久丢失。确认专用连接断开或执行锁丢失时仍立即判定丢失。心跳与配置新鲜度保留各自时限；combined 与 standalone 的归属验证默认时限仍为 5 秒。

## 未安装的模板

新增 `turb-web@.service` 和 `turb-worker@.service` 使用 `/srv/turb/<instance>/current`、`/etc/turb/<instance>/bootstrap.env`、独立角色与同一稳定运行目录。模板没有 BindsTo/PartOf/Requires，停止 Web 不传播到 Worker。`Type=exec` 只证明 exec 成功；`After=network-online.target` 不证明应用 readiness。manager 直接运行前台 Python，失败重启、90 秒硬停止、UMask0077；原 combined unit 未被覆盖。

launchd 的 `local.turb.web.plist.example`、`local.turb.worker.plist.example` 必须替换所有 `/ABSOLUTE/...` 与 INSTANCE，占位值不能安装。两 label 独立，环境值全为字符串，分别 stdout/stderr，RunAtLoad 与失败重启。本机实测声明 ExitTimeOut90 时 launchd 实际显示 60；因此模板显式使用 ExitTimeOut60，并向两个角色传 `--shutdown-timeout 55`，为退出回执、解锁和解释器退出预留 5 秒。Web 若 HTTP 用满 20 秒，runtime 仅剩最多 35 秒；HTTP 提前完成则可使用更多剩余预算。此为本机验证后的设置，目标机器仍须核对实际加载值；不能把模板声明当生效证明，也不要设为 0 无限等待。systemd 模板继续采用 90 秒硬边界，须单独做实际管理器验收。manager 标记由进程写入身份记录。要停止自动重拉必须先 bootout/manager stop，不能只 kill 子进程。模板没有读取或修改任何真实 label。

切换前先确认精确已提交/推送 SHA、解释器/目标平台依赖、配置和密钥、队列/active Task/Run/permit/lease/unknown 清单；紧邻停止时再核对。暂停旧 combined 自动重拉并等其真实退出，才启动新 Worker、验证 ready，再启动 Web。回退先停 Web，再排空 Worker，确认 owner 释放后恢复 combined；任何 stop 超时停止推进，不强制回收未知远端事实。Web 起不来而 Worker 仍执行时不自动杀 Worker。部署与业务验收分别报告，本机成功不代表 Oracle。
