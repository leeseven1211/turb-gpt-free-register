# 全站按钮与后端集合操作覆盖矩阵

基于 2026-11-24 全站盘点的实施复核。范围：本工作区本次后端批量改造及现代 Vue、legacy 动态行菜单、壳模板可见入口。本文是源码覆盖检查，不表示已经推送、部署或进行真实业务验收。

## 口径与完整按钮索引

改造前的全站按钮源索引已归档到 [backend-bulk-button-inventory](backend-bulk-button-inventory/)，主报告为 [全站按钮与批量节点审计](backend-bulk-button-inventory/全站按钮与批量节点审计.md)。[button-source-inventory.json](backend-bulk-button-inventory/button-source-inventory.json)、[按钮源码逐项清单.csv](backend-bulk-button-inventory/按钮源码逐项清单.csv)、[supplemental-source-inventory.json](backend-bulk-button-inventory/supplemental-source-inventory.json)、[模板与动态按钮源码清单.csv](backend-bulk-button-inventory/模板与动态按钮源码清单.csv) 保留改造前逐入口文件、行号、文案和事件；这些历史行号不充当当前源码的精确定位。共识别 59 个 Vue 文件的 348 个入口（298 button、32 summary、18 个带 click 的其他元素），以及模板 31 个按钮、动态 JS 52 处声明点。该数量包含本地选择、筛选、导航和显示控件，不等于批量业务操作种类。

六份领域盘点 [accounts.md](backend-bulk-button-inventory/accounts.md)、[codex-tasks.md](backend-bulk-button-inventory/codex-tasks.md)、[email-proxy.md](backend-bulk-button-inventory/email-proxy.md)、[registration-bulk.md](backend-bulk-button-inventory/registration-bulk.md)、[config-extract-dashboard.md](backend-bulk-button-inventory/config-extract-dashboard.md)、[architecture.md](backend-bulk-button-inventory/architecture.md) 是同目录的改造前按钮索引；其中“当前逐条”的判断是改造前证据，实施状态以本矩阵与现有源码为准。共享筛选、分页、对话框、菜单、原生 confirm、details/summary 和 legacy `v-html` 行操作均在索引中，没有因不是工具栏 button 而排除。

“已集合”指本地批量准入、普通修改的自有数据库预取、判断和写入使用集合 SQL，Python 按目标组装受理结果不触发目标级 SQL/事务。运行中的强制安全结算及其恢复回执按后文边界保留逐 Run 事务。持久长操作保存命令或 batch/round/target/Run；短同步读写不强制制造长期 Task。外部响应后的即时事实保存另列，不能把它与本地逐项受理混为一谈。单条 URL 的兼容处理以及特殊历史路径在例外表明确列出。

## 已集合

| 页面与全部语义动作 | 当前入口 | 集合实现和边界 |
|---|---|---|
| 账号归档、恢复、删除、备注；邮箱失效、解除失效（含动态行菜单） | `webui/routes/accounts.py` 的 archive/delete/note/email-invalid 单条及 bulk 入口 | `core/storage/accounts/bulk_mutations.py`；长批量提交 `bulk_mutation` 命令，Worker 分块写业务事实及逐项回执。邮箱失效按账号、地址账本、母资源集合锁定和集合投影，保留 expected email 与 HME 共享资源保护 |
| 账号查活、查套餐、刷新 AT、补密码、补 2FA、修改密码、修改 2FA、补全 | `setup-bulk`、`action-bulk`、`complete-bulk`、`check-live-bulk`、`refresh-token-bulk`、`check-plan-bulk` | `core/accounts/bulk_submission.py` 集合预检、claim、普通 Task/Run/Event 建立；`core/storage/operations/bulk_submission.py:create_specs` 共享原语。每账号认证和后续步骤仍由原 handler 执行 |
| 账号 C2A 手动同步；Sub2API 账号/文件上传 | `c2a/sync-bulk`、`codex/upload-sub2-bulk`、`/api/codex/upload-sub2-bulk` | 账号集合受理与 `core/codex/bulk_submission.py`；一次捕获后端配置错误，保留每项资格与明确错误回执；原 AT、凭证行 ID、代际、backend 由 worker 再核验 |
| 批量换绑邮箱 | `/api/accounts/email-change-bulk` | `core/accounts/email_change/service.py:submit_email_change_bulk`；集合读与原子批次受理，幂等重放沿用原批次及快照，领取邮箱/OTP/换绑按原账号 worker 执行 |
| 查封号邮件、HME 别名共享扫描、unsupported 状态 | `/api/accounts/check-deactivation-mail-bulk` | `core/accounts/deactivation/mail_scan.py`、`core/storage/accounts/deactivation_mail.py`；集合准入、集合账号结果投影与 HME 结果事件，HME 共用一次邮箱扫描。Cloudflare 请求不再无条件取得全局 HME 锚点 |
| 一键巡检开始、停止全部活动子项 | `/api/accounts/inspections`、`/<id>/cancel` | `core/storage/accounts/inspections.py`、`core/accounts/inspection/service.py`；父子 Task/Run、ordinal、首 Run、batch 关联集合写入；直接父停止入口按原 Run 范围集合取消 queued/running 等全部活动状态，CAS 状态变化仅集合重读原范围；资源释放仍由原 Run 安全收尾 |
| 重跑注册（账号工具栏及行菜单） | `/api/accounts/registration-retry-bulk` | `core/accounts/registration_retry.py:retry_accounts` 一次把合格 source Job 集合交给 `registration_service.retry_jobs`；普通、历史无 Attempt 与套餐/Codex/账号配置后处理均交对应集合受理；保持原来源、父任务和冻结配置 |
| 账号提链 | `/api/accounts/extract-link-bulk` | `core/extract_link/account_bulk.py`、`core/storage/extract_link/account_submission.py`；集合固定候选、资格/claim、Task/Run 和账号排队投影，原 legacy handler/外部调用保持 |
| 账号复制 Token、复制行、复制邮箱、复制密码、复制 2FA、复制提链地址、TXT、Session、CPA 下载 | `secret-bulk`、`download-session-bulk`、`download-cpa-bulk` | `core/storage/accounts/bulk_reads.py`；账号/Session/本地凭证引用集合读取；成功导出的集合计数一次回写。ZIP 每文件写 entry、CPA 每文件远端下载属于产物/外部边界 |
| Codex 归档、恢复、删除、重置导出次数 | `webui/routes/codex.py` 对应单条及 bulk | `core/storage/codex/bulk_mutations.py`；集合读取/写入，长批量命令及完整分页回执 |
| Codex OAuth Token 刷新、重授权/补 Codex、Sub2 上传 | `refresh-token-bulk`、`retry-bulk`、上传 bulk | `core/codex/bulk_submission.py`、`core/storage/codex/bulk_submission.py`；集合凭证与关联账号准入、快照、Task/Run。OAuth refresh 与账号 AT refresh 是不同类型，未混用 |
| 停止选中 Codex | `/api/codex/stop-bulk` | 集合查账号与精确活动重授权 Run，`cancellation.cancel_runs_many` 集合 CAS 取消请求与事实、账号投影集合 CAS；外部信号和资源收口保留 |
| Codex 本地及 CPA 批量下载 | `download-bulk`、`download-bulk-from-cpa` | `core/storage/codex/bulk_reads.py` 一次读取全部本地凭证；保输入顺序、重复、缺失和坏内容的原结果语义，远端下载后成功项集合标记 |
| 邮箱批量标记、删除；本地粘贴导入、导入预览、复制素材 | `webui/routes/email_pool.py` 的 status/delete/import/secret bulk | `core/storage/email/bulk_mutations.py`、`local_imports.py`、`secrets.py`；按来源集合查/写、集合导入与 service fact 意图。删除保留 tombstone、原租约证据及母资源历史；安全快照与 return intent 集合同事务写入，外部安全退租由恢复 worker 处理 |
| Butler 新租约导入 | `/api/email-butler/imports` | `core/email/email_butler/manual_import_v2.py:create` 一次保存 batch 和全部 item intent；preview、request identity、恢复/取消沿用原节点；外部每次结果即时落库保留 |
| 任务中心批量删除、取消 | `/api/operations/bulk` | `bulk_facts.py`、`task_center_cancel.py` 与 `cancellation.cancel_runs_many` 集合读取/隐藏、精确 Run CAS、Task、lease 取消请求、events 写入；巡检子项保原范围；该批量 cancel 入口保持只取消 queued 的产品规则，直接巡检父停止及活动父终止另列 |
| 任务中心 Sentinel 重跑/取消 | 同上 retry/cancel | `task_center_sentinel.py` 按 cache key 集合互斥、活动 Run 复用及集合重跑；`task_center_cancel.py` 识别原 Sentinel cancel handler 并用集合 CAS，不更改维护执行和文件租约 |
| 任务中心再次巡检 | 同上 retry | `task_center_inspection.py`、`inspection_retry_many.py` 集合受理选中巡检父；保原“启动新全量巡检或复用活动巡检”语义，同波不再逐父新开本地事务 |
| 任务中心历史账号来源重跑 | 同上 retry | `task_center_legacy_retry.py` 集合读取 `account_action_tasks` 与账号，并归组到集合领域准入；历史 Codex OAuth refresh 使用 `task_center_legacy_codex_refresh.py`，保凭证代际、来源 Run 和父任务身份 |
| 任务中心普通原生重跑 | 同上 retry | `task_center_retry_wave.py`、`task_center_retry.py`、`bulk_retry_tasks.py`；原生、历史账号与 OAuth 刷新先完整集合预检，再按原选择顺序决定同账号/资源族的首个可受理目标；集合追加原 Task 的新 Run、Codex/账号投影、私有原单复制、普通父及注册 handoff 收口。父上下文先锁，账号/Task 锁冲突逐项 busy，父代次变化整波保存点重读 |
| 任务中心批量强制终止 | 同上 terminate | `bulk_terminate_command.py`、`bulk_terminate.py`；HTTP 202 保存命令与冻结 Run/巡检 child Run 范围，worker 独立安全结算、崩溃恢复和完整分页回执；Codex 投影 CAS 不覆盖后续代次 |
| 任务中心 managed 重跑 | 同上 retry | `core/operations/action_service.py:_accept_managed_retries` 按原 batch 合并 canonical selected targets，一来源 batch 一轮；不再一个选中目标一轮 |
| 任务中心注册重跑 | 同上 retry | `action_service` 将 selected source Job 集合交 `registration_service.retry_jobs`，保来源 Job、原 batch/workers、Attempt 和配置；历史回填及后处理均通过注册集合入口 |
| 新注册批次 | `/api/jobs` | `core/storage/registration/bulk_submission.py`；Job/Attempt/Run/投影按最多 500 行语句块集合创建，整份批次同一事务原子可见；不改变 Roxy、协议驱动步骤 |
| 注册普通重跑、排队取消、本地删除 | `/api/jobs/retry-bulk`、`cancel-pending`、`delete-bulk` | `core/registration/service.py:_prefetch_retry_facts` 与 `core/storage/registration/bulk_retry.py` 集合来源/根/Attempt/账号事实及受理；`bulk_retry_legacy.py` 集合回填历史缺失事实，`retry_followups.py` 集合受理套餐/Codex/账号配置；`bulk_facts` 集合取消/隐藏 |
| 提链工作台创建、同步原单、批次取消、批量复制支付入口 | `webui/routes/extract_workbench.py` | `core/storage/extract_link/bulk_create.py`、`bulk_cancel.py`、`workbench_bulk.py`；集合任务建立/状态快照/取消/原单新 Run 与支付产物读取；同步继续沿原任务身份和冻结配置，精确 owned source link 集合继承与 generation、ProviderJob 私有快照 SQL 内复制、普通/注册父收口；不新建远端单 |
| 注册批次停止 | `/api/jobs/batches/<batch_id>/stop` | `batch_stop.request_stops` 集合锁批次投影与 Job、集合读取/补齐 Attempt 和 Task/Run，CAS 本地停止请求及投影；覆盖原批次全部 Job，缺来源历史孤儿通过 `retained_sources` 集合解析；历史 Task 绑定、waiting/stopping current Run、其他活动 Run、child root 和父收口按原 `sync_registration_job` 逐字段对照保留；合作停止与真实资源释放保原执行器规则 |
| 原生 bulk cancel/stop | batch/round 控制按钮 | `bulk_control.py:settle_control` 集合 run links、取消 CAS、target facts/outbox/events；默认路径无逐目标本地取消 SQL，显式领域回调保独立执行边界 |
| 配置“保存全部”“保存 Roxy 选择” | `/api/config` | 配置与发布事实集合写入，同一原子配置事务。501 字段仍只需两次写入；热加载与配置版本回执沿原契约 |
| C2A “立即巡检”的修复上传 | `core/integrations/c2a/monitor.py:_submit_uploads` | `monitor_submission.queue_targets` 集合锁账号、查 source/活动 Run、创建 Task/Run；保 backend+remote ID+account+repair key 原摘要、`monitor_managed`、trigger 和崩溃后原 Task 最新 Run 复用 |
| Sub2API “立即巡检”的发现、续跑与子任务 | `core/integrations/sub2api/monitor.py:_run_once` | `monitor_collections.py` 与 `core/storage/sub2api_monitor.py`；集合 accounts/credentials/repair/Run/sync Job 快照、会话级账号互斥、内存状态机、集合 OAuth/sync admission 与阶段回写。锁冲突跳过当前波次保持可恢复，外部仍用原 handler |

## 原有集合与纯 UI / 只读单项

| 类别 | 所有相关入口 | 处理 |
|---|---|---|
| 原有集合 | 账号“删除已废”、列表/facets/统计/按筛选范围读取、邮箱导入预览跨池查重、bulk selection 的固定范围/物化/报告 | 保留集合仓储，未因已有集合 SQL 就改成逐目标任务 |
| 本地 UI | 全选/单选/清除选择，常用按钮排序，菜单/弹层打开关闭，Esc/遮罩，折叠、步骤筛选、列宽/恢复、草稿编辑/清 secret、多选项/国家/平台开关 | 不创建批量节点；业务确认只触发对应一次集合提交 |
| 导航与查询 | 侧栏、概览卡片、历史、详情、日志、分页/跳页/每页大小、筛选/清筛、刷新/读取失败重试、运行实例/事件页签、已有链接打开及已加载数据复制/CSV | 保留只读请求或本地动作，不能将轮询视为逐目标受理 |
| 配置单项探测 | Roxy 工作区读取、Butler/HME 连接探测、额度/余额查询、Sub2 分组列表、Sentinel 检查、固定一个 IP 的代理测试 | 原产品语义为一次读取或一个目标检查；没有隐藏的批量目标数组需要拆分。Sentinel 已有一个维护任务 |
| 代理页面 | 代理流量/历史/库存/详情、筛选、分页、列宽 | 现代页无批量检测或回收按钮。供应补货/回收是后台生命周期，不冒充本轮按钮改造完成项 |
| 历史派生邮箱 | 过滤、复制、分页、历史查看 | 当前只读；`/api/email-derivation/status-bulk` 保持 410（Email Butler 管理），未恢复废弃写能力 |
| 明确单项执行 | 手动 OTP、单任务诊断资源/释放调试浏览器、原支付单查询、单个支付入口/链接读取、人工确认恢复账号 | 单目标安全语义保留；未凭“所有按钮”发起额外支付、退租、认证或网络操作 |

## 外部逐响应持久化边界（保留）

| 边界 | 为什么保留 |
|---|---|
| 注册/OAuth/密码/2FA/查活/提链/换绑的账号 Worker | 不同账号有独立认证、OTP、浏览器、远端请求与资源归属；没有调研第三方等价批量 API 时不能合并外部行为。运行 checkpoint、凭证保存、未知结果和资源结算仍按真实执行落库 |
| Butler `manual_import_v2._finish` | 每个远端领取结果、租约、binding、receipt 必须在释放并发许可前立即短事务保存；一个慢请求不能使其他已返回租约只留在内存，取消后的迟到结果仍须保存 |
| Email Butler service fact worker | 对已持久本地删除/导入意图逐目标核对远端归属、安全事实与结果；这是领取/退租的恢复边界，不能延迟到整批外部请求完成 |
| C2A / Sub2 sync、OAuth 后补传结果 | 原 backend、remote target、credential ID/generation 和 Run fence 必须精确匹配；每个真实远端响应仍由原 handler 即时确认。集合化的是扫描/受理和子任务事实 |
| CPA 单文件下载与 ZIP 构建 | 本地账号与凭证已集合读，成功文件集合写导出标记；远端每文件下载及本地每 ZIP entry 无数据库逐目标事务，不假设远端提供批量下载协议 |
| 运行中停止/终止 | 本地取消请求、准确 Run CAS 和任务事实已集合；逐 Run 的协作信号、租约/claim/permit 归还、远端未知结果及 fence 仍按原安全结算规则执行，不能用一条 status UPDATE 强行替代 |

## 精确保留的兼容 fallback

`core/storage/operations/bulk_retry_native.py:_retry_chunk` 对同次重复 source Task、非六种 native 类型/operation 不符或账号身份不符的目标，不套用普通集合追加；这些不匹配合法按钮身份的异常历史记录继续交给 `core/bulk_operations/adapters.py:submit_chunk` 原有单项保存点、stage claim 与重试兼容逻辑。保留它们是为了不新增拒绝规则或猜测身份，不能把普通 100 目标集合预算解释为这些异常记录也已集合。

普通六类、`parent_task_id`、注册 `completion_handoff`、历史无 Attempt、注册套餐/Codex/账号配置、任务中心 Sentinel/巡检父/历史账号来源等合法按钮路径均有对应集合实现，详情见上表。全站“所有按钮”覆盖包括纯 UI 和明确单项目标，不表示每个按钮都创建持久长任务，也不表示认证/外部响应后的安全事实保存合并为一个大事务。

外部服务批量 API 能力调研、真实业务执行、推送和部署属于独立验收事项；本报告只确认当前工作区的源码覆盖及列出的隔离验证。

## 本轮验证证据使用方式

相关测试按账号/邮箱/Codex/注册/提链/任务中心/配置/monitor 分组，使用 `tools/test_isolated.py --profile all` 与独立测试数据库及 `test_*` schema；测试只构造合成账号和替身网络。源码覆盖报告不重复跑各 owner 已完成的全组测试，也不把其他 agent 的通过数字冒充本报告作者亲自执行。

本报告作者独立执行的 Sub2 monitor 新集合回归覆盖 SQL 数预算、20 个 OAuth 子任务、40 个原远端 target 的补传、Task 失败全事务回滚、取消优先、其他 resource family 不误阻塞、deactivated 不建新 Run，以及持账号锁时生产者不等待。最终 Sub2 monitor 联测 81 项通过，另有 14 个 subtest。Codex/C2A 子任务已提交并由各自执行者报告隔离测试结果，后续总验收应直接引用最终提交与命令输出。

提链 managed/parent 特殊路径由本报告作者完成，提交 `a147d547`。最终隔离 PostgreSQL 回归 16 项及 2 个 subtest 全部通过；受管 1/20 目标预算固定（最多 30 条 SQL），20 个父任务最多 48 条 SQL。覆盖精确 owned link、私有原单复制、generation、双 revision 边界、整波回滚及调用方捕获 Python 异常、IDLE 借用连接不提前提交、父 Run/账号反向锁真实死锁和逐项锁冲突。运行 ruff、compileall 与 diff check 均通过。

直接巡检停止提交 `46c7fb27`：实现者真实隔离 PostgreSQL 回归 33 项及 8 个 subtest 全部通过，独立审查通过。改造前 1/20 个运行子 Run 分别 14/109 条 SQL；改造后集合预算通过，并覆盖 queued→running CAS 后仅原范围重读、全部活动状态及整波回滚。

注册历史后处理提交 `6cb86a1c` 已由独立 reviewer 复核：源/根/Attempt 身份与永久废号、fresh 4 态资源互斥、原配置 Task 的 current Run 优先活动态、latest Run 用于新编号与数据、现存父关联保留、调用方事务及 Python 异常整波回滚均保原契约。相关测试结果及统一重跑最终联测见 [验证记录](2026-11-24-backend-bulk-validation.md)。

统一任务中心重跑提交 `cdd5f343` 的独立审查确认：用户 `task_ids` 顺序显式恢复后，原生、历史账号、OAuth 刷新与注册后处理先完整预检，再按真实账号及资源族选择首个有效目标；阶段忙碌或永久废号的前项不预占名额，OAuth 刷新按凭证邮箱解析实际账号，原生无账号任务不参与账号互斥。direct 事实提交后才创建 managed 新轮；归属查询或某一来源 batch 的轮次创建失败，只影响相应 managed 回执，不会抹掉已经提交的 direct 成功或其他 batch 结果。

注册批次停止的最终隔离验证为 17 项通过（停止 12 项及历史投影对照 5 项）；历史对照覆盖已有 Task 绑定、旧 waiting/stopping current Run、其他活动 Run 不改写、child root=self 及父收口，逐字段与旧同步投影一致。此组由主 agent 执行，报告作者未重复运行。

注册同源并发后处理补修提交 `054ed71b`：未取得父 Run 的事务不再抢取父 Task，避免两个相同请求分别持 Run/Task 后都返回 busy。确定性双线程交错测试先复现双拒绝，再经最小修复通过；相关 6 项 PostgreSQL 回归及 3 个 subtest 全部通过，独立审查通过。

主 agent 最终第二轮整合回归覆盖 16 个测试文件，209 项及 37 个 subtest 全部通过（311.89 秒，隔离执行器总时长 318.314 秒）；包含跨来源统一 wave、存储 prepare/commit、注册 current Run 及同源并发补修。该轮启动时取消原语的 501 分块尾修尚未应用，取消尾修另列专用及相关领域联测，不把此轮数字用于证明随后修改。完整命令和范围记录于 [验证记录](2026-11-24-backend-bulk-validation.md)。

取消原语尾修提交 `4248d7aa`，专用 6 项及 3 个 subtest 通过，独立 Spec/Quality 审查通过。修改后的主 agent 相关联测覆盖 7 个测试文件，89 项及 26 个 subtest 全部通过（142.76 秒，隔离执行器总时长 149.309 秒），包括 501 分块专用、巡检停止、持久终止、Codex 停止、bulk control、任务中心取消和路由。每条取消、claim 释放与 managed outbox 写入语句最多 500 项；全目标先按原序取得锁，全部语句块保持同一事务，后块错误回滚整波并保留调用方先前事实。
