# 发布与验证

> 本文维护现行验证规则；单次测试结果、性能数字和部署回执通过 Git 历史追溯。

## 1. 验证范围

非重大架构调整仅运行与本次改动直接相关的测试。重大架构调整按受影响的模块和契约扩大
验证范围。涉及 PostgreSQL 行为时运行对应的隔离数据库测试。大多数 UI 改动在部署后
使用真实浏览器验收受影响的现代页面和交互，业务逻辑或接口契约的改动同时运行直接相关的
测试。入口路由改动需核对旧 `?ui=legacy` 链接和 `ui_mode=legacy` Cookie 仍返回现代页面。
文档改动检查标题、相对链接、重复内容和现行代码引用。

统一测试入口是 `python tools/test_isolated.py`，由它启动 pytest 并收集已有的
`unittest.TestCase`。运行前在进程环境提供独立测试库的 `DATABASE_URL`；入口会禁用项目
dotenv、清除业务环境配置并探测测试库。`TURB_DB_SCHEMA` 必须以 `test_` 开头，未指定时
由入口生成。profile 只决定 marker 筛选，不代替测试路径：

| profile | 实际选择 | 适用范围 |
|---|---|---|
| `default` | `not extended`，只选非扩展测试 | 日常基础回归，包含保留在默认集中的关键数据库契约 |
| `extended` | `extended`，只选扩展测试 | 按风险补充低频回归；不包含 default |
| `all` | 不添加 marker 筛选 | 对指定路径同时运行普通与扩展测试 |

三个 profile 都保留调用者指定的文件、目录、用例节点以及 `-k` 等 pytest 筛选条件。
例如 `all -- tests/config/test_config_ui.py` 只验证该文件；不指定路径时，pytest 按项目配置从
`tests/` 收集，只有此时 `all` 才覆盖整个测试目录。profile 不与 pytest `-m`/`--markexpr`
混用。

```bash
# 按实际改动选择测试文件
python tools/test_isolated.py --profile all -- tests/config/test_config_ui.py tests/webui/test_dashboard_api.py -q

# 重大架构调整需要覆盖整个测试目录时
python tools/test_isolated.py --profile all -- -q
```

测试进程不得连接生产库、不得使用 `public` schema，也不能依赖 `.env`、账号、Token 或
运行日志作为测试输入。若隔离数据库不可用，应报告验证未执行或失败，不能把 skip 说成
通过。已有测试数量多不是删除依据；先确认其保护的行为、是否重复和耗时来源，再决定
合并重复检查、缩小 fixture 或调整测试分组，保留关键业务与数据安全约束。

本地前端行为测试按实际改动从 Vue 或外壳脚本中选取。以下是仓库根目录下的定向命令示例。

```bash
npm --prefix frontend test -- src/features/bulk/BulkPageShell.test.ts
node --test tests/bulk/test_page_bridge.cjs
```

CI 的 `frontend` job 分别运行 Vue 工程检查、现有 Node 行为回归和前端构建。共享依赖或
展示入口迁移时，把相关夹具和业务断言迁到当前模块。构建步骤见[前端说明](../../frontend/README.md)。

## 2. 提交与发布前检查

```text
与改动直接相关的测试
  -> 重大架构调整按影响补充回归
  -> git diff --check
  -> 检查暂存范围不含私有数据
  -> 确认提交与远端推送状态
```

提交、推送、部署和服务重启是独立事实：本地提交不代表已推送，推送不代表进程已加载新
代码，进程启动也不代表数据库和 worker 已就绪。未被请求的操作不得隐含执行。

验证结果记录实际命令、profile、所选路径、通过/失败/跳过数量及耗时；扩大范围时附上
原因。指定路径的 `--profile all` 不能写成“项目全量通过”。相关检查通过后，仅在新增
修改、失败或仍有未覆盖风险时重复或扩大测试。

## 3. 服务运行时验收

当任务明确要求启动、重启或部署时，依次核对：

1. 实际进程 PID、工作目录和监听端口；
2. PostgreSQL 可用性及启动日志；
3. `GET /healthz` 的 liveness；
4. `GET /readyz` 的数据库和 runtime 就绪；
5. `GET /login` 或相关页面/API 的真实响应；
6. 涉及 UI 的现代界面交互和浏览器控制台结果；入口路由变更另核对旧链接与 Cookie 均返回现代页面。

`/healthz` 通过不等于 `/readyz` 通过。若 supervisor 自动拉起旧进程，必须确认它加载的
工作目录和代码版本，不能仅依据启动脚本输出声明成功。

## 4. 数据与日志安全

验证输出只保留排障必要字段并脱敏。不得提交或展示 `.env`、账号、Token、Cookie、OTP、
完整代理、邮箱池、`logs/`、`accounts/` 或 `codex_accounts/` 内容。兼容文件的
存在或生成成功不能替代 PostgreSQL 行级数据的正确性。

可重复的服务切换、配置迁移及回滚步骤见[部署与维护](../deployment/operations.md)。

## 5. 任务中心性能基准复现

API 与浏览器基准分别衡量查询接口和页面操作，不能合并成一个“整体提速”数字。比较时
使用同一主机、相同规模与参数，并暂停其他测试、构建和浏览器性能采样；不同轮次保留
全部结果，不选择最好的一轮，也不直接混合计算 P95。以下命令从仓库根目录执行，输出
放在独立临时目录；本节只维护方法，不保存某次运行的性能结论。

### 规模与数据分布

账号容量按几十万条验证，涉及账号与批量平台的性能改动至少保留 **30 万合成账号**的
规模档位。小规模用于功能回归和快速定位，不能代替这个容量档位。账号总量、实际命中
目标数、批次数、历史轮次、Task / Run 数和账号 JSON 大小分别记录；仅扩充未参与查询
的账号表，不能声称验证了大批次或大量历史的性能。

批次读取至少覆盖少量 / 大量目标、现代 / 历史结果混合、多次所属运行、部分目标重试、
非首页以及完整筛选范围的摘要。查询当前结果时保留逐目标最新请求轮，历史轮不得被
后续重试覆盖。背景数据与测量目标分别报告，记录实际表行数、数据和索引大小，以及
执行计划中的扫描、排序、临时文件和缓冲区情况。

30 万账号库存不改变当前单次选择最多 10 万目标的业务上限；测量每次请求的命中规模
必须遵守原契约。库存容量、单次请求延迟、并发吞吐和真实远端任务完成时间分别验收，
不能由一个指标替代其他指标。

改前 / 改后对照使用同一数据和参数，常规对照每场景每版本至少 30 个有效主样本，交替
执行顺序。若旧路径极慢且代表场景已有 30 样本，可在新一轮开始前固定非对称容量采样：
新版仍至少 30 个有效主样本，旧版减少样本只用于诊断与完整结果对照；分别记录实际
样本数及配对 / 未配对阶段，旧版不足 30 时不报告 p95，不据此宣称尾延迟改善。中止轮
独立保留，不与新轮拼接。保留原始样本、p50 / 可用的 p95 / 最大值、SQL 次数、完整
结果等价和源码哈希。SQL 分段计时、
等待采样和 `EXPLAIN (ANALYZE, BUFFERS)` 属于额外诊断，单独记录探针开销，不混入
主耗时；查询次数下降不等于数据库工作量下降。出现尾延迟回升必须保留并调查，不能
删除慢样本或仅按中位数宣称所有指标改善。确认自有测试 schema 已清理。

### API 与真实 SQL

[API 基准脚本](../../tools/benchmarks/benchmark_task_center_api.py)通过 Flask `test_client`
向旧、新路由发送相同 GET 请求，覆盖常规列表、带筛选统计和批次的列表、组合筛选、
不带事件的详情及带事件的详情。计时包含路由、真实 PostgreSQL 查询和 JSON 序列化，
不包含鉴权、TCP/TLS、浏览器渲染或外部业务。

运行前在环境中配置本机 `turb_test` 的 `DATABASE_URL`，不要把 DSN 写进命令或文档。
脚本复用 `tools/test_isolated.py`，禁用 dotenv 和生产放行，只允许 `turb_test`，每次生成
独立的 `test_task_api_` schema，并在结束时清理。不要手动传入内部 `--isolated` 参数。

```bash
TURB_BENCH_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/turb-task-center.XXXXXX")"
TURB_BENCH_REF=2fe57ac

python tools/benchmarks/benchmark_task_center_api.py \
  --compare-ref "$TURB_BENCH_REF" \
  --rows 2000 --accounts 1000 --events 200 \
  --samples 30 --warmups 3 \
  --output "$TURB_BENCH_ROOT/task-center-api.json"
```

`--rows` 是终态 Task 和 Run 各自的数量，至少 2000；`--accounts` 至少 1000；`--events`
是选定详情的合成事件数；`--samples` 至少 20，`--warmups` 至少 1。上述命令使用脚本的
默认规模。需要核对尾延迟时可另用 `--samples 60` 和新的输出文件名，保留原始轮次。
基准不启动 dispatcher，不执行真实任务或外部请求。

只核对旧 `/api/account-tasks` 查询收口时，加 `--suite legacy-account`，输出使用独立文件：

```bash
python tools/benchmarks/benchmark_task_center_api.py \
  --suite legacy-account --compare-ref "$TURB_BENCH_REF" \
  --rows 2000 --accounts 1000 --events 200 --samples 25 --warmups 3 \
  --output "$TURB_BENCH_ROOT/legacy-account-api.json"
```

该场景至少 25 样本，使用旧账号任务表的混合终态数据，核对列表、组合筛选、含事件详情
和不存在详情的 404。每对样本同时比较完整 JSON、响应正文 SHA-256、HTTP 状态和 SQL
次数。仅固定调度信息的展示时钟以使完整响应可比较，真实刷新配置读取与 SQL 不替换。
默认 `operations` 场景保持不变。两类场景不混算；工作区尚未提交时，应选择包含旧路由
实现的基线 ref，不能把已经收口的提交又当成“改造前”。

旧路由从 `--compare-ref` 的 `webui/routes/operations.py` 通过 `git show` 加载，新路由取
当前工作区；两版共用当前仓储和其他依赖。脚本要求任务仓储与指定基线一致，因此测到
的是路由及查询服务变化，不能当作完整旧版本与新版本进程对照。结果记录基线 SHA、
当前 HEAD、工作区是否有修改及相关源码 SHA-256，并检查测量期间源码未变化。

每个场景逐样本交替旧、新顺序，检查完整 JSON 等价，并保留每个样本的耗时、客户端
SQL 次数和未压缩响应字节数；P50/P95 使用 nearest-rank。SQL 计数不包括数据库函数
内部语句。确认输出中的 `schema_cleaned` 为 true；合成成功终态数据不能替代注册兼容
来源、多 Run、深页、运行中争用或生产规模验收。

### 真实浏览器与合成 API

[浏览器基准](../../tools/benchmarks/benchmark_task_center_browser.py)使用同一个 Chromium
浏览器会话，逐样本新建页面，通过 CDP 禁用缓存，并交替旧、新页面顺序。
[预览服务](../../tools/benchmarks/task_center_ui_preview.py)给两版提供同一固定内存数据，
不加载 `.env`、业务服务、数据库或 worker。旧版只替换静态资源与模板，不运行旧后端。

先将基线的 `webui/static`、`webui/templates` 两个目录导出到独立非 Git 暂存目录。
不要把整个源码工作区或私有数据复制进去。当前版直接读取待测工作区的模板和已构建
产物；运行前先按[前端说明](../../frontend/README.md)完成构建。

```bash
TURB_BENCH_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/turb-task-center.XXXXXX")"
TURB_BENCH_REPO="$PWD"
TURB_BENCH_REF=2fe57ac
TURB_BENCH_SESSION=task-center-benchmark
TURB_BENCH_CLI="${CODEX_HOME:-$HOME/.codex}/skills/playwright/scripts/playwright_cli.sh"

mkdir "$TURB_BENCH_ROOT/baseline"
git archive --format=tar --output="$TURB_BENCH_ROOT/baseline-assets.tar" \
  "$TURB_BENCH_REF" webui/static webui/templates
tar -xf "$TURB_BENCH_ROOT/baseline-assets.tar" -C "$TURB_BENCH_ROOT/baseline"
git rev-parse "$TURB_BENCH_REF" > "$TURB_BENCH_ROOT/baseline-ref.txt"
git rev-parse HEAD > "$TURB_BENCH_ROOT/current-head.txt"
shasum -a 256 "$TURB_BENCH_ROOT/baseline-assets.tar" > "$TURB_BENCH_ROOT/baseline-assets.sha256"

python tools/benchmarks/task_center_ui_preview.py \
  --asset-root "$TURB_BENCH_ROOT/baseline" --port 8018 --tasks 2000 \
  > "$TURB_BENCH_ROOT/baseline-preview.log" 2>&1 &
TURB_BENCH_BASELINE_PID=$!
python tools/benchmarks/task_center_ui_preview.py \
  --asset-root "$TURB_BENCH_REPO" --port 8019 --tasks 2000 \
  > "$TURB_BENCH_ROOT/current-preview.log" 2>&1 &
TURB_BENCH_CURRENT_PID=$!
```

确认两个预览进程正常启动，8018 和 8019 都是本次预览服务。两版均固定为 2000 个任务、
每页 20 条、详情 500 条事件和同一个合成时间。当前采样脚本按这一夹具的任务 ID 与分页
结果等待渲染，不能只改 `--tasks` 就把报告描述为另一个有效规模。

`TURB_BENCH_CLI` 可改为本机 Playwright CLI 包装脚本的位置，需要 Node/npm 与可用的
Chromium 浏览器。先启动同名会话，再运行采样；若环境设置了 `PLAYWRIGHT_CLI_SESSION`，
应清除或设为同一会话，避免包装脚本选择其他会话。

```bash
"$TURB_BENCH_CLI" --session "$TURB_BENCH_SESSION" open about:blank

python tools/benchmarks/benchmark_task_center_browser.py \
  --cli "$TURB_BENCH_CLI" --session "$TURB_BENCH_SESSION" \
  --baseline-ref "$TURB_BENCH_REF" --baseline-port 8018 --current-port 8019 \
  --samples 20 --warmups 2 \
  --output "$TURB_BENCH_ROOT/task-center-browser.json"

"$TURB_BENCH_CLI" --session "$TURB_BENCH_SESSION" close
kill "$TURB_BENCH_BASELINE_PID" "$TURB_BENCH_CURRENT_PID"
```

收尾只停止本次启动的两个进程；保留输出用于对照，不使用递归删除命令。完整执行后，
报告保留两版各 20 个样本和各 2 次预热，汇总排除预热。预热与正式样本都验证页面没有
脚本异常，正式数据就绪后再等待两次 `requestAnimationFrame`，各字段范围如下：

| 字段 | 计时起点与终点 | 不包含的范围 |
| --- | --- | --- |
| `cold` | 新页面导航开始，到首屏任务行显示并等待两帧 | 不是新浏览器进程冷启动，不等待所有无关后台请求完成 |
| `filter` | 点击“失败”筛选选项，到筛选后的首行显示并等待两帧 | 打开筛选浮层之前的操作时间 |
| `page` | 点击下一页，到目标页首行显示并等待两帧 | 用户阅读和选择页码的时间 |
| `detail` | 点击同一任务的详情，到 500 条事件与阶段组件可见并等待两帧 | 未读取的其他 Run、日志或诊断资源 |
| `reentry` | 关闭详情、切到总览后再次点击任务导航，到已有列表数据重新可见并等待两帧 | 不等待重新进入时的后台刷新完成，不能当作最新数据刷新耗时 |

每个动作另记录已在计时窗内完成的 API、列表、证据和资源请求数量，响应与传输字节、
长任务累计时间及 DOM 节点数；仍未完成的请求不在该窗口统计内。浏览器 P50/P95 使用
线性插值，与 API 基准的 nearest-rank 不同，不混合两种原始样本汇总。

报告的 `baseline_sha` 对应导出基线，`source_sha256` 指纹覆盖当前采样脚本、预览脚本、
模板、桥接及任务中心 JS/CSS 产物，并检查测量前后相同；原始样本记录浏览器版本。
导出的基线目录不得手工改动，归档 SHA-256 和基线 SHA 与报告一起保留。当前工作区未
提交时，用当前 HEAD 加文件指纹定位实际待测内容，不能仅用 HEAD 表示新版。脚本不
验证端口背后的资源目录，启动命令和进程归属也必须随复现记录保留。

此基准只证明指定桌面视口、合成 API 和固定数据下的操作成本，不证明真实数据库性能、
生产网络、Oracle、全部用户旅程或移动端布局。真实兼容行为仍由定向回归和浏览器验收
覆盖，不能因为性能样本完成就跳过。
