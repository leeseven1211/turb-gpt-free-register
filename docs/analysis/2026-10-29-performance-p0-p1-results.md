# P0/P1 性能优化实施结果

日期：2026-10-29（Asia/Shanghai）。
状态：实现、隔离集成验证、独立审查和合成环境真实浏览器验收已完成；提交部署记录见第 6 节。

## 1. 范围与结果

本轮依据用户对 P0/P1 的授权，处理代理池重复维护、提链批量提交、展示统计缓存和现代 WebUI 列表轮询。原始调查保留在[批量执行与任务提交性能分析](2026-10-29-performance-analysis.md)，本文只记录实施结果，不改写调查时点的生产观测。

原调查曾观察到多个连接等待代理池容量锁，以及部分 GET 请求秒级返回；本轮数值对照主要来自隔离库合成数据，不能据此宣称生产接口 P95、供应商吞吐或长时间稳态表现已经改善到某个数值。

本轮没有引入异步批次提交状态机，没有修改注册执行步骤、调用参数与顺序、重试或超时策略，也未实施 P2 的批次汇总增量投影、历史事件增量重放或 P3 候选改造。Codex 和账号巡检批量入口保持原实现。

## 2. 最终实现

### 2.1 P0：代理池维护合并与缩短容量事务

- 进程内重复维护在借数据库连接前合并；后台 worker 共用原一秒空闲节拍，供应商供给和健康检查仍独立并发。
- 存储维护使用 `pg_try_advisory_xact_lock`，重复维护可以跳过；容量预留仍用原阻塞容量事务锁。活动资源和关联锚点按原资源→锚点顺序使用 `FOR UPDATE SKIP LOCKED`，忙碌对象交给后续维护。
- 忙碌 LIVE 行仍由独立权威 COUNT 纳入容量；最小 ready 底数只使用本事务已锁定且仍满足 TTL、锚点和健康条件的资源。同锚点跨 profile 别名同步失效，避免把已关闭锚点误计为库存。
- 终态修复与每轮最多 200 条到期历史整理移至独立历史事务，不持容量锁。仍重新确认终态、子租约和所有权，有活跃 child 时保留历史对象。
- 复用同 profile 的可用资源集合，新增活动维护、到期终态与活跃子租约部分索引。诊断区分借连接、容量锁 SQL、持锁及提交耗时；历史异常分类为 `proxy_pool_history_maintenance_failed`，不丢失已提交的活动退役结果。

### 2.2 P1：提链批量提交减少重复读取和事务

- 同一批次只调用一次 `get_config_snapshot()`，保存**原始配置快照**，每项仍由 gateway 按既有 `EXTRACT_CONFIG_ALLOWLIST` 投影。Task 和 Run 保存同一 revision 及实际配置值；最终实现没有提前投影后再投影的路径。
- 每账号使用独立短事务：当前账号 `FOR UPDATE` 读取资格、原 claim 条件更新、未决付款检查、Task/Run/Event 创建与账号排队状态回写使用同一连接。保持最终资格与占用原子确认，不依赖陈旧预取快照，不锁整块账号。
- gateway 在已有事务内使用保存点，单项 SQL/唯一约束失败只回滚本项创建；保留失败/忙碌分类、账号失败回写和后续项继续处理。
- 批次提供连续 ordinal，跳过或失败不产生空洞；首次 Run 使用刚创建 Task 的 UUID，省去重复 SELECT；事务内状态回写省去重复账号存在性查询。
- `submission_id` 幂等、候选保留、原有中断表示、unknown、未付款历史重跑与恢复语义保持原样。接口继续等待整批同步提交，不宣称已实现快速后台接单。

### 2.3 P1：列表轮询与按需详情

- 现代账号状态请求使用可选 `compact=1`，返回 Plus 展示摘要、详情 revision 和可清空字段集合；完整优惠、Go、逐国结果及结账信息由只读按需详情接口提供。非 compact 默认接口及首次完整列表保持兼容。
- 摘要保留国家、历史 `stale` 与旧 `plus_*` 回退；空数组、null 和缺失状态字段会清除旧展示。详情请求合并，并在等待期间 revision 改变时补读最新版本，旧响应不能覆盖新状态。
- 统一任务批次导航采用字段白名单；`include_batches=0` 不读批次，`include_facets=False` 跳过五条 facet SQL。默认任务列表保持七条查询和原 facets 契约，精简轮询为两条查询。
- 统一任务 facets/导航自动刷新间隔为 30 秒；筛选改变立即刷新，手动刷新绕过间隔，加载中的手动刷新意图会保留到下一次请求。相同列表 revision 不重绘任务表。
- 注册任务表的自动只读轮询可省略 facets/status_counts；换筛选、换页和主动刷新立即更新 metadata，响应序列保护保持不变。此处没有修改注册创建或执行行为。
- 提链批次导航自动刷新间隔为 30 秒；翻页、切换批次和主动刷新立即更新。当前批次摘要仍每轮更新，内容不变时保留任务 DOM；错误后恢复时重新渲染。

### 2.4 P1：展示库存统计缓存

`/api/summary` 与 `/api/dashboard` 在同一应用内共享最多 15 秒的库存展示快照，并合并同时发生的同 key 请求。返回副本隔离调用者修改，异常不缓存，成功 HTTP mutation 后失效；进行中失效通过 generation 阻止旧结果回填。最早库存绝对有效期可提前终止缓存，并显示统计更新时间。

缓存仅位于展示接口。库存领取、任务提交资格和 `feature_availability` 仍读取权威条件；dashboard 自身其他账号/任务聚合没有全部缓存。后台变化仍可能带来最多 15 秒的展示延迟。

## 3. 隔离基准与证据边界

所有数据库测试经项目隔离入口，仅使用 `turb_test` 和 `test_` schema，没有将合成基准提交到生产账号或真实供应商。以下均为本机短窗口样本，不是生产 P95。

### 3.1 代理池合成并发维护

基准：[bench_proxy_pool_maintenance.py](../../tests/bench_proxy_pool_maintenance.py)。数据为 500 个非终态资源（409 cooldown、91 idle ready）及 40,000 个终态历史，保留 91 个 ready 底数。对照期间没有退役写入或供应商网络请求；并发触发维护，同时运行普通 ready COUNT。

| worker | 维护执行次数：前→后 | 维护 SQL：前→后 | 总耗时：前→后 | 容量持锁及提交最大：前→后 | 普通查询最大：前→后 |
|---:|---:|---:|---:|---:|---:|
| 2 | 2→1 | 1,190→8 | 2,440.86→188.12 ms | 1,176.37→39.04 ms | 26.90→18.76 ms |
| 10 | 10→1 | 5,950→8 | 11,286.99→42.65 ms | 1,278.32→32.83 ms | 169.25→3.22 ms |
| 20 | 20→1 | 11,900→8 | 22,849.33→45.26 ms | 1,419.15→32.20 ms | 9,326.65→3.80 ms |

维护 SQL 计数均排除普通 COUNT、建表和造数，包含活动及历史事务。20 worker 原借连接最长 9,314.97 ms，优化后 0.08 ms；容量锁 SQL 累计 170,456.55→2.86 ms。锁 SQL 耗时包含网络与执行，不能解释为纯数据库锁等待；持锁统计包含提交。

40,000 条历史尚未到期时，新增终态索引实际扫描 0 行、0.035 ms；改为八天前后，同一索引扫描 200 行、0.101 ms。一次维护删除 200 条，保留活动资源，总耗时 357.68 ms。生产首次创建索引的时间与占锁影响尚未测量，不能用此隔离计划替代部署验证。

### 3.2 提链合成同步提交

基准：[test_extract_submission_performance.py](../../tests/test_extract_submission_performance.py)，通过 `TURB_EXTRACT_SUBMISSION_BENCHMARK=1` 显式运行。provider、dispatcher 唤醒和日志落盘被屏蔽；计时不含造数、初始化和断言查询。

| 项数 | SQL：前→后 | 借连接：前→后 | 配置捕获：前→后 | MAX ordinal 查询：前→后 | 耗时：前→后 |
|---:|---:|---:|---:|---:|---:|
| 10 | 151→121 | 53→13 | 10→1 | 10→0 | 1,066.35→395.76 ms |
| 100 | 1,411→1,111 | 503→103 | 100→1 | 100→0 | 5,015.25→2,469.81 ms |
| 500 | 7,011→5,511 | 2,503→503 | 500→1 | 500→0 | 20,526.29→9,753.29 ms |
| 1,000 | 14,011→11,011 | 5,003→1,003 | 1,000→1 | 1,000→0 | 45,859.86→21,329.59 ms |

千项业务 SQL 减少约 21.4%，借连接减少约 80.0%，最终版本该次合成耗时减少约 53.5%。SQL 计数来自 `Cursor.execute`，不含驱动内部 BEGIN/COMMIT/SAVEPOINT，不能当作完整协议往返数；借连接次数也不是同时活跃连接数。

上表“改后”为当前最终版本重跑结果，包含原始配置快照捕获修正与 `active_run_for_account` 连接复用；原始基线保留。重跑仅执行显式基准：

```text
TURB_EXTRACT_SUBMISSION_BENCHMARK=1 python /tmp/turb-perf-tests-20261029.py tests/test_extract_submission_performance.py::ExtractSubmissionPerformanceTests::test_synthetic_benchmark -q -s
```

结果 **1 passed，51.24 秒**（测试耗时含造数；表中计时仅含提交）。最终配置内容另由非默认七项值、Task/Run 精确一致和白名单回归验证。该合成用例全部正常提交，连接复用的 busy 冲突分支由专项回归覆盖，不把它计作本表额外收益。千项仍需同步创建完整 Task/Run/Event，不能把约 21 秒合成时间视为交互预算已经达标。

### 3.3 合成响应体积与重复查询

十个账号、每号十个国家结果，每个优惠携带大摘要及快照；使用与 HTTP 相同的紧凑 JSON 分隔符：

| 数据 | 兼容状态响应 | compact 响应 |
|---|---:|---:|
| 10 行十国 | 549,325 B | 16,923 B |
| 其中一行清空国家/优惠后 | 494,766 B | 15,906 B |

这是专项实现阶段合成序列化测量。最终增加 `stale` 后的体积预算仍由十行 `<20,000 B` 回归约束，不将前一阶段的精确字节数当作最终生产响应。账号 SQL 仍读取当前页详情以生成摘要和 revision，并未消除数据库对这些详情的读取。

任务列表合成用例覆盖 20 个各约 1.2 KB 的任务与 50 个含 5 KB data 的批次：白名单后的导航 `<10 KB`、组合响应 `<50 KB`。默认/省略 facets 的 SQL 预算为 7→2。库存缓存并发用例证明八个同时请求共用一次 loader，不是整站数据库压力测试。

## 4. 专项验证与审查修复

测试结果来自多个有重叠的专项轮次，不相加为单一“总通过数”。统一集成结果另填第 6 节。

| 范围 | 已记录结果 |
|---|---|
| 代理策略、统一入口、维护、资源、最小 ready、轮转 | 104 passed |
| 静态代理与 711 相邻回归 | 15 passed、7 subtests passed |
| 代理独立审查隔离回归 | 40 passed |
| 最终配置修正后的提交、批次、锁顺序 | 50 passed、1 skipped、55 subtests passed |
| 原生运行时、durable gateway、巡检兼容 | 73 passed、39 subtests passed |
| UI 修复后的 admin repository 及两个只读 API | 33 passed、44 subtests passed |
| 账号轻量轮询、邮箱状态、提链前端 | 74 passed；随后新增真实按钮绑定断言，轻量轮询文件 6 passed |
| 展示缓存与路由独立审查 | 9 passed |
| 注册任务只读刷新前端独立审查 | 15 passed |

提交专项的一个 skip 为需显式启用的合成基准，基准此前已单独通过。Python 编译、相关 JS 语法和 `git diff --check` 已通过专项检查，最终统一检查待填写。

审查发现并修正：

1. 批次先投影 target 键、gateway 再按 source 键投影，导致只保存 revision。最终保留一次捕获的原始快照，由 gateway 唯一投影；新增两个账号、七个非默认源配置及无关字段过滤测试，Task/Run 都必须精确保存七值与 revision。
2. compact 白名单遗漏 `stale`，导致历史国家优惠在轮询后看起来成为当前结果。已保留该字段，并验证完整列表与 compact 合并后的真实渲染一致。
3. 详情 v1 请求期间出现 v2 摘要时，旧请求虽被正确拒绝写回，却吞掉当前打开详情动作。已在旧响应完成后补读最新版本，原调用链等待最新完整明细。
4. 手动刷新共用自动 metadata 节流，30 秒内点击无法更新 facets/批次数。已增加 force metadata，保留加载中点击的强制刷新意图，并验证实际按钮绑定。
5. gateway 冲突分支在外层账号事务尚未释放时再次借连接，两个并发请求即可耗尽两连接池并互等超时。冲突查找现在复用保存点回滚后的外层连接；真实两连接池回归验证 busy 分类、原 Task/Run 链接、后续写入和无残留任务。

代理独立审查未发现需要阻塞合入的容量超发、活跃租约误释放、最小 ready 失守或新增死锁。展示缓存/注册只读轮询独立审查未发现阻塞性兼容问题。专项测试不替代真实浏览器、生产索引建立或多进程长期运行验收。

## 5. 已有失败基线

专项完整 UI Python 首轮为 108 passed、9 failed（含 source 子用例）；筛除 7 个已定位失败方法后为 108 passed、7 deselected、104 subtests passed。排除仅用于区分已有基线，不表示完整套件全部通过：

- dashboard 邮箱来源/库存断言：当前本地收件依赖下 `icloud_hide` 不可用，旧断言期望可用；一例总量期望 11，实际 8。
- jobs 三个旧接口测试：隔离 schema 的 `account_action_tasks` 未创建，或旧响应语义断言不一致。
- modern UI 静态过滤器数：旧断言期望 53，当前 60。
- Butler lease 旧测试未提供当前必需 profile：期望 200，实际 400。
- `test_account_promotions_frontend.cjs` 的历史优惠 HTML 正则要求国家占位 `—：` 紧邻，而 HEAD 实现包含“历史”节点；用 HEAD 原 JS 重新执行同样失败（58 passed、1 failed）。该既有断言本轮未修改。

本轮没有通过修改业务模型、放宽生产数据库保护或忽略新失败来使这些基线变绿。root 统一集成测试若发现额外失败，应在下节另列，不能自动归为已有基线。

## 6. 统一集成与运行验收

### 6.1 最终集成测试与基准

最终集成以 `853a222` 为基线，针对共享存储事务、列表接口与展示缓存组合执行：

```bash
python /tmp/turb-perf-tests-20261029.py tests/test_display_statistics_cache.py tests/test_display_statistics_routes.py tests/test_extract_submission_performance.py tests/test_extract_workbench_batches.py tests/test_extract_batch_lock_order.py tests/test_admin_repository.py tests/test_dashboard_api.py tests/test_extract_workbench_routes.py -k 'not dashboard_email_sources and not dashboard_returns_aggregates and not jobs_column_filters and not jobs_query_and_email and not jobs_status_filter and not modern_ui_contains and not create_lease' -q
node --test tests/test_account_polling_performance.cjs tests/test_account_email_invalid_frontend.cjs tests/test_extract_workbench_frontend.cjs tests/test_registration_refresh_frontend.cjs tests/test_registration_jobs_frontend.cjs
ruff check .
git diff --check
```

Python 结果：167 passed、1 skipped、7 deselected、159 subtests passed，197.72 秒。skip 是显式合成基准，随后单独运行最终版本通过；deselected 为第 5 节的七个已有失败方法。Node 92 项通过，ruff 全仓和差异空白检查通过。最后的连接复用修复另经提交/锁/gateway 54 项及 33 子测试通过，主 agent 又独立执行双连接并发与保存点冲突两项回归通过。没有新增未解释的失败。不是全项目测试全量通过。

临时启动器使用源仓库虚拟环境，仅从本地连接配置派生 `turb_test`，随后调用项目 `tools/test_isolated.py --profile all`；它不保存在 Git 中。P0 主/相邻及独立审查结果见第 4 节。

### 6.2 真实浏览器验收

使用 `localhost:8017` 的独立 Flask 实例、`test_perf_browser_20261029` schema 与 25 个合成账号、15 个排队任务、3 个批次，不启动业务 worker。在真实浏览器完成：

- 账号列表首轮及随后 `compact=1` 轮询均正确显示国家与折扣；当时十行轮询 14,793 B。
- 悬浮后实际发出 `/api/accounts/25/plan-details`（2,570 B），tooltip 与抽屉恢复三个国家的银行卡/UPI 和完整优惠说明。
- 仅修改该隔离 fixture，清空优惠/国家后等待正常轮询，原有优惠消失并显示“待查询”。
- 账号翻到第二页成功；任务中心自动请求省略 metadata，手动刷新请求 `include_facets=1&include_batches=1`。
- 提链当前批次持续读取任务和批次详情；批次列表按较低频率更新。切换到第二批次、筛选运行中后显示零条空状态。
- 保存账号第二页截图，浏览器捕获的 error 级控制台日志为空。

Chrome 扩展曾断开且用户正在使用前台窗口，后续验收改用独立内置浏览器，避免干扰。详情迟到响应、历史标记渲染、DOM 不重绘和注册任务表兼容性由相应动态回归验证。未发起真实注册、提链或支付，不将合成浏览器验收称为真实业务执行验收。

### 6.3 提交、推送与部署

待 root 分别填写：

- 集成到 main 的提交号及本地工作区状态；远端是否推送。
- 服务重启前后 PID、工作目录、代码版本、监听端口与启动方式。
- 新索引初始化和日志检查结果；`/healthz`、`/readyz`、`/login` 状态。
- 服务加载变更的证据，以及上线后只读短样本/错误与锁等待观察。

截至本文整理时，仅有本地实现和专项隔离验证证据；未在本节确认的提交、推送、重启或生产验收不得视为完成。
