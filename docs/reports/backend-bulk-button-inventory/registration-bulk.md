# 注册与批量平台按钮只读审计

审计日期：2026-11-24。仓库：`/Users/lihongwei/code/personal/gpt/turb-gpt-free-register`。仅阅读源码并新建本报告；未调用业务写接口、未运行注册、未改业务文件、未提交/推送/重启服务。工作区已有大量用户修改，本报告以当前磁盘内容为准。表中路径均相对该仓库，行号为本次读取位置。

## 结论与分类

- **注册页不是用户所要求的批量节点执行。** 创建、重试、停止虽然都是一次 HTTP 请求，但后端仍逐个创建/重试/停止 job；注册 `batch_id` 是字符串分组、同批并发和快照，不是批量平台的 selection/round/target/control。尤其 `retry-bulk` 直接循环 `svc.retry_job`，没有整批原子提交。
- **现有批量平台具有真实的持久化批量管理和部分集合写入。** 固定名单、批次、轮次、目标、控制命令、恢复租约、投影 outbox 都存在。新目标正常路径用 `create_runtime_tasks_many` 集合创建 Task/Run/排队事件；旧 Task 重跑和停止仍逐个处理。
- **现有平台没有独立的批量 node 实体。** 一个批次固定一种 operation，一个 target 对应一个账号；组合补全沿每账号的执行链继续。若要求“一个节点对整份名单执行某种操作”，现有 batch/round 只能作为基础，不能声称已经具备节点 DAG 或按节点整批执行。
- **现有注册与账号批量管理是两套边界。** 批量目录仅开放查询套餐、刷新 AT、补密码、补 2FA、补 Codex、组合补全；没有注册、注册任务删除、OTP、调试释放等 operation，名单 target_kind 也仅 account/credential，不能直接覆盖尚未生成账号的注册任务。

分类：`读/本地`＝查询、展示、导航或选择；`单条`＝一个明确对象；`接口批量`＝一次请求后逐条领域处理；`集合批量`＝集合 SQL 或分块事务；`受管批量`＝有持久化名单/轮次/目标/控制，可能仍有逐项动作。HTTP 次数只统计该按钮主请求，随后刷新和轮询另记。

## 注册页按钮清单

本表 Vue/TS 组件路径省略 `frontend/src/features/registration/`；`jobs.py` 指 `webui/routes/jobs.py`，注册 `service.py` 指 `core/registration/service.py`。

| 编号 | 语义按钮/控件 | 处理函数与 API | 次数、对象与分类 | 证据及未来归属建议 |
|---|---|---|---|---|
| R01 | 开始注册 | `start → owner.create → api.create`；POST `/api/jobs` | 前端 1 次，后端 N 次 `create_job/_enqueue_job`；字符串 batch_id，非 bulk target/node；接口批量 | `RegistrationPage.vue:66,114`、`useRegistration.ts:227`、`api/registration.ts:48`、`webui/routes/jobs.py:271`、`core/registration/service.py:3297`；未来属于“注册创建”批量节点，但须先确认受保护方案 |
| R02 | 邮箱来源读取失败的“重试” | `owner.ensureMeta(true)`；GET `/api/email-sources` | 1 次，只读 | `RegistrationPage.vue:132`、`api/registration.ts:44`；保留页面查询 |
| R03 | 批次“停止运行” | `executeAction('stopBatch')`；POST `/api/jobs/batches/{batch}/stop` | 1 次，后端逐 job `request_stop_job`；接口批量 | `RegistrationBatchPanel.vue:229`、`useRegistration.ts:283`、`jobs.py:406`、`service.py:4695`；迁为持久控制命令，不能更改检查点停止语义 |
| R04 | 批次“取消排队” | `executeAction('cancelBatch')`；POST `/api/jobs/batches/{batch}/cancel` | 1 次，job/Run 取消同事务集合更新，之后逐条同步统一任务投影；集合批量 | `RegistrationBatchPanel.vue:230`、`jobs.py:400`、`core/storage/db_legacy.py:3649`；可由节点/批次控制统一包装 |
| R05 | 批次“重跑失败” | `batchCandidates → executeAction('retryBatch')`；POST `/api/jobs/retry-bulk`，job_ids 来自当前批次响应里的 retryable 失败项 | 1 次，后端 N 次 `retry_job`；接口批量，无独立 round | `RegistrationBatchPanel.vue:231`、`useRegistration.ts:248,284`、`jobs.py:505`；未来由服务端按固定时点结果选名单并新建轮次，不能直接改变重试资格和协议 |
| R06 | 选中任务“重试” | `executeAction('retryBulk')`；同 R05，传 selected IDs/debug_enabled | 1 次，后端 N 次；最多 500 个；接口批量 | `RegistrationPage.vue:145`、`useRegistration.ts:286`、`jobs.py:482,505`；应成为节点重跑而非前端逐条请求 |
| R07 | 选中任务“删除” | `executeAction('deleteBulk')`；POST `/api/jobs/delete-bulk` | 1 次；集合删除 job，N 次预读取，日志/调试文件逐条清理；非统一事务 | `RegistrationPage.vue:145`、`jobs.py:551,575,581`、`db_legacy.py:4399`；若纳入节点，需区分数据库删除与文件清理回执 |
| R08 | 任务表“取消排队” | `executeAction('cancelAll')`；POST `/api/jobs/cancel-pending` | 1 次；作用于全部 pending，非当前筛选/选中范围；集合批量 | `RegistrationPage.vue:145`、`jobs.py:394`、`db_legacy.py:3649`；范围需明确归入全局控制 |
| R09 | 行/批次卡片“重试”及动态 retry_label | `executeAction('retry',job)`；POST `/api/jobs/{id}/retry` | 单条；根据事实分流注册、继续邮箱验证、账号配置、Codex、套餐等 | `RegistrationPage.vue:157`、`RegistrationBatchPanel.vue:268`、`jobs.py:426`、`service.py:4253,4366,4401,4446,4467,4562`；保留单目标入口或送一目标节点，分流规则不变 |
| R10 | 行“停止” | `executeAction('stop',job)`；POST `/api/jobs/{id}/stop` | 单条；pending 取消、running 协作停止 | `RegistrationPage.vue:157`、`jobs.py:418`、`service.py:4608`；未来可统一控制契约，不改终态收口/邮箱保留语义 |
| R11 | 行“删除” | `executeAction('delete',job)`；POST `/api/jobs/{id}/delete` | 单条；调用 `delete_jobs([id])` 后清调试产物 | `RegistrationPage.vue:157`、`jobs.py:534`；可复用删除节点的单目标形式 |
| R12 | 提交验证码 | `submitOtp → owner.action`；POST `/api/manual-otp`，email/code/job_id | 单条人工输入；无 batch/node | `RegistrationPage.vue:96,157`、`jobs.py:375`；属于目标交互输入，不应把不同账号验证码合成一个值 |
| R13 | 刷新/错误“重试”/刷新批次 | `queryLoad` 或 `owner.load`；GET `/api/jobs` | 每次 1 个列表请求；只读 | `RegistrationPage.vue:145,150`、`RegistrationBatchPanel.vue:235`、`api/registration.ts:46`；保留查询 |
| R14 | 批次下拉选择 | `chooseBatch → owner.setBatch`；GET `/api/jobs` | 1 次批次查询；只读 | `RegistrationPage.vue:94,141`、`RegistrationBatchPanel.vue:226`；保留查询 |
| R15 | 表格选择本页/单行、调试模式开关 | `toggleAll/toggle`、本地 debug ref | 0 次业务请求；选择跨刷新保存在本地 Set，本页全选排除 running/stopping | `RegistrationPage.vue:26,91,92,113,151,153`；只生成节点目标名单/参数，不等于执行 |
| R16 | 表头/移动端筛选触发、完成、清除此列、清筛、筛选 chip 移除 | `openFilter/changeFilter/resetFilters`；GET `/api/jobs` | 打开/完成 0，值变化/清筛 1 次列表读取；只读 | `RegistrationFilters.vue:14,22`、`RegistrationPage.vue:34,89,148,151`；保留查询 |
| R17 | 分页上一页/下一页/数字页码（含首尾页）/跳转/页大小 | `ListPagination → owner.load(applyFilterParams())` | 页码/跳转 1 次列表读取；页大小组件连续发 page=1 与 size 两个事件，父级两个 handler 都调用 load，是否合并由 hook 决定；只读 | `RegistrationPage.vue:159`、`frontend/src/components/ListPagination.vue:47`；保留查询 |
| R18 | 恢复列宽、拖动/键盘调列宽 | `resetColumns`、`columnWidths.resize/resizeWithKeyboard` | 0 次；本地展示 | `RegistrationPage.vue:22,148,151` |
| R19 | 批次全部/成功/失败/进行中/其他状态筛选 | `setFilter` | 0 次；已加载批次内容过滤；失败仅一项时自动展开会读单项 progress | `RegistrationBatchPanel.vue:124,242`；保留展示，避免误认服务端全量失败名单 |
| R20 | 阶段（展开/收起）、重试读取阶段 | `toggleDetails/loadProgress`；GET `/api/jobs/{id}/progress` | 单项读取；展开后活动目标可随批次刷新再次读 | `RegistrationBatchPanel.vue:134,151,266,275`、`api/registration.ts:47`；保留目标证据 |
| R21 | 日志/阶段日志、点击阶段 | `owner.openLog`；有 operation_task_id 则 `openTask(task,run,step)`，否则读取 log/debug/diagnostics | 单目标导航/读取；旧日志弹窗 2–3 次串行 GET，运行中每 2 秒再读 | `RegistrationPage.vue:157`、`RegistrationBatchPanel.vue:267,279`、`RegistrationProgress.vue:22,43,69`、`useRegistration.ts:295,316` |
| R22 | 步骤详情/阶段详情、依赖与执行记录/原始错误/尝试线路折叠、详情关闭 | 本地 `inspected/selectedId/details` | 0 次业务请求；读/本地 | `RegistrationProgress.vue:53,68,74,77`、`RegistrationBatchPanel.vue:281,285` |
| R23 | 日志弹窗关闭/取消/点击背景 | `owner.closeDetail` | 0 次，停止该详情轮询 | `RegistrationPage.vue:65,162,163`、`useRegistration.ts:322` |
| R24 | 与同批成功任务对比 | `compareDebug → owner.compare`；GET `/api/jobs/{id}/debug/compare` | 1 次只读 | `RegistrationPage.vue:164`、`useRegistration.ts:323`、`jobs.py:730` |
| R25 | 下载脱敏 HAR | 浏览器 GET `/api/jobs/{id}/debug/har` | 单任务导出；没有整批 HAR 导出 | `RegistrationPage.vue:164`、`jobs.py:712`；导出可做批量报告/归档节点，不改变调试执行 |
| R26 | 结束调试并收口 | `owner.action(...,{action:'finish'})`；POST `/api/jobs/{id}/debug/release` | 单条运行现场控制 | `RegistrationPage.vue:164`、`jobs.py:703`；若要批量释放需专门目标控制能力；会改变运行现场，不能当只读展示重构直接实施 |
| R27 | 打开失败截图、完整诊断证据 | GET `/api/jobs/{id}/diagnostics/screenshot` / 本地 details | 单条只读/0 次 | `RegistrationPage.vue:165`、`jobs.py:687`；保留诊断查询 |

说明：注册页面 `setView('launch'/'tasks')` 有宿主入口契约（`RegistrationPage.vue:64`），具体导航按钮由外层宿主维护，不在此 Vue 组件渲染；其作用是加载相应视图，不是批量操作。所有写操作后 `action` 会刷新列表，打开旧日志详情时还刷新详情（`useRegistration.ts:206`）。

## 批量平台按钮清单

以下路径省略前缀 `frontend/src/features/bulk/`；所有请求由 `frontend/src/api/bulk.ts:8` 加 `/api/bulk`。

| 编号 | 语义按钮/控件 | 处理函数/API | 次数、对象与分类 | 证据与建议 |
|---|---|---|---|---|
| B01 | 批次列表/返回批次列表、新建批次（顶栏/空态） | `navigate/newBatch/openDraft` | 导航本地；首次进入创建页读 catalog/query-facets；不提交任务 | `BulkPageShell.vue:66,77,101`、`BulkCreate.vue:43`、`BulkList.vue:380` |
| B02 | 顶栏刷新 | `refresh(true)` 分发给当前 list/create/detail | 列表 1 GET；创建 catalog+facets/selection；详情 batch+targets，报告打开时附 report | `BulkPageShell.vue:38,101`、`useBulkCreate.ts:155`、`useBulkDetail.ts:97`；只读 |
| B03 | 找回原请求（全局/创建页） | `recover → intents.recover`，原路径原 body 原 Idempotency-Key 重放 | 1 次原 POST；幂等回执，不是业务重跑；未决请求本地持久化 | `BulkPageShell.vue:79,105`、`BulkCreate.vue:89`、`useBulkIntent.ts:17`；可复用，但与“新一轮重跑”分开 |
| B04 | 操作类型选择（六种）、名称/并发设置 | `setOperation/setDraftField` | 本地草稿；无 node；每批一个 operation | `BulkCreate.vue:44,56,57`、`useBulkCreate.ts:78`；未来操作选择落在节点参数 |
| B05 | 创建并执行 | `createBatch(false)` → POST `/selections`，ready 后 POST `/batches` | 2 次写请求，中间异步 GET selection；受管批量，有 selection/batch/initial round/targets | `BulkCreate.vue:40,90`、`useBulkCreate.ts:122,137`、`webui/routes/bulk.py:217,228`；可复用名单冻结/幂等/分块入队 |
| B06 | 创建并暂停 | 同 B05，`execution.start_paused=true` | 2 次写；存在批次但未开始目标等待继续 | `BulkCreate.vue:90`、`useBulkCreate.ts:130`；未来对应节点或批次初始暂停 |
| B07 | 查看已存在批次 | `navigate('detail',{batch_id:existingBatchId})` | 导航+详情 GET；没有再次提交 | `BulkCreate.vue:88` |
| B08 | 清空条件/改为按条件筛选/条件 chip 删除 | `clearFilters/clearFilter` | 本地失效旧 selection，节流后 1 query-facets GET；无写接口 | `BulkCreate.vue:61,62,78`、`useBulkCreate.ts:75,84` |
| B09 | 日期/更多查询/列筛选开关、完成/ESC；操作/状态/日期筛选值变化 | `switchFilter/closeFilter/setQueryField` | 开关 0；值变化本地保存+节流 GET `/query-facets?query=...` | `BulkCreate.vue:16,66,67,70`、`useBulkCreate.ts:64,81`；没有独立“预览并冻结”按钮，计数只是查询预览，提交才固定名单 |
| B10 | 列表筛选触发、查询、清除此列、清除筛选、筛选 chip 移除 | `search/filter/removeFilter/list.applyFilters/resetFilters`；GET `/batches` | 开关 0，应用筛选 1 GET；只读 | `BulkList.vue:131,182,210,226,247,276,304,310`、`useBulkList.ts:122,186` |
| B11 | 列表错误重试、返回首页、上一页、正常列表上一页/下一页/首页 | `list.refresh/first/previous/next`；GET `/batches` | 每次 1 GET，游标分页；只读 | `BulkList.vue:186,192,200,384`、`useBulkList.ts:127` |
| B12 | 批次名称、成功数、失败数 | `open(id,resultState?) → navigate(detail)` | 读 batch+targets；成功/失败附 result_state | `BulkList.vue:142,320,348,356`；目标结果钻取 |
| B13 | 查看报告（列表/详情） | `report/showReport/state.openReport`；GET `/batches/{id}/report?view=...` | 报告 1 GET，详情首次进入还读 batch/targets；受管批量汇总 | `BulkList.vue:149,369`、`BulkDetail.vue:30,70`、`useBulkDetail.ts:62` |
| B14 | 暂停批次 | `control('pause')`；POST `/batches/{id}/control` | 1 次，scope=batch；持久 control 命令+revision；已开始账号继续收尾 | `BulkDetail.vue:24,87`、`useBulkDetail.ts:147`、`webui/routes/bulk.py:289`；可复用生命周期，不等于立即暂停每个远端步骤 |
| B15 | 继续批次 | `control('resume')`；同 B14 | 1 次，恢复未开始目标入队；受管批量 | 同 B14；不存在额外独立“开始”按钮，创建即执行或暂停后继续 |
| B16 | 取消排队账号 | `control('cancel_not_started')`，确认后 POST control | 1 次；scope=batch/当前 round；持久命令分块处理，内部按目标/run 取消 | `BulkDetail.vue:24,87`、`useBulkDetail.ts:151`、`bulk_control.py:112,207`；保留目标收尾边界 |
| B17 | 停止正在执行 | `control('request_stop')`，确认后 POST control | 1 次；scope=batch/当前 round；内部逐 run `cancel_run`，非集合业务中断 | 同 B16、`bulk_control.py:215`；仍非批量节点级停止执行器 |
| B18 | 重跑失败/部分成功/未执行/已取消/全部未成功 | `retry(false,choice)`；POST `/batches/{id}/rounds` | 1 次写，服务端按结果固定新名单；有 source revision/新 round，不覆盖历史 | `BulkDetail.vue:23,95`、`useBulkDetail.ts:140`、`webui/routes/bulk.py:284`；可复用轮次与冻结时点 |
| B19 | 重跑勾选 | `retry(true)`；同 B18，`selection.kind=targets,target_ids=[...]` | 1 次写，跨页 selected Set；非 N 次前端请求 | `BulkDetail.vue:95`、`useBulkDetail.ts:144`；可复用目标选择 |
| B20 | 重跑范围下拉、单个目标勾选/本页全选/清空选择 | `retryChoice/toggleTarget/selectPage/clearSelection` | 0 次；只生成名单意图 | `BulkTargets.vue:31,32`、`BulkDetail.vue:95`、`useBulkDetail.ts:123` |
| B21 | 确认弹窗“返回”/关闭、确认操作 | `cancelConfirmation/confirm → execute` | 返回 0；确认执行上面的 1 次 POST，然后刷新 | `BulkDetail.vue:101`、`useBulkDetail.ts:127`；≥10 个重跑或全部未成功需确认，pause/resume 直接提交，停止/取消固定确认 |
| B22 | 同一名单再次执行 | `copyBatch(true) → copyBatch callback` | 只开新草稿，source=batch_targets；再次提交才新建 selection/batch | `BulkDetail.vue:71`、`useBulkDetail.ts:154`；复用固定目标、另起批次 |
| B23 | 复制条件新建 | `copyBatch(false)` | 只开新草稿；未来按当时数据重新冻结；不是同一名单 | `BulkDetail.vue:72`、`useBulkDetail.ts:154` |
| B24 | 结果视图下拉：当前结果/首轮/重跑轮 | `setRound → change`；GET batch/targets | 2 GET，报告已打开可加 report；只读 | `BulkDetail.vue:63`、`useBulkDetail.ts:122,158` |
| B25 | 更多轮次 | `moreRounds`；GET `/batches/{id}/rounds?page_size=20&cursor=...` | 1 GET | `BulkDetail.vue:69`、`useBulkDetail.ts:108` |
| B26 | 结果/阶段筛选触发、全部/各结果选项、清除筛选 chip | `filter → state.setFilter`；GET `/batches/{id}/targets` | 开关 0；变化 1 GET；不改固定名单 | `BulkTargets.vue:30`、`BulkDetail.vue:97`、`useBulkDetail.ts:121` |
| B27 | 明细首页/上一页/下一页 | `first/previous/next → loadTargets` | 1 GET，50 个/页；只读 | `BulkDetail.vue:99`、`useBulkDetail.ts:118` |
| B28 | 重试读取批次/重试读取明细/报告“重试” | `refresh(true)/loadTargets/refreshReport(true)` | batch+targets / targets / report GET；只读 | `BulkDetail.vue:43,93,98`、`BulkTargets.vue:29`、`BulkReportView.vue:25` |
| B29 | ID/账号/阶段/完整结果摘要/错误分类明细按钮、弹窗关闭 | `show(row)/DialogClose` | 0，展示当前页面已得快照 | `BulkTargets.vue:21,32,37`；不是单账号业务执行按钮 |
| B30 | 查看执行/查看占用 | `task → props.openTask(taskId,runId?)` | 目标关联任务导航；本组件无业务写请求 | `BulkTargets.vue:25,32`；owned task 和 external blocker 已区分，可复用 |
| B31 | 范围与设置折叠、报告“更多查询统计”折叠 | 原生 details/summary | 0 次业务请求；只读 | `BulkDetail.vue:50`、`BulkReport.vue:271`；保留展示 |

**报告导出核查：** `BulkReport.vue`、`BulkReportView.vue` 和 `/api/bulk` 路由中没有下载/CSV/JSON 导出按钮或导出 API。现有“查看报告”是只读展示；不能把 R25 的单任务 HAR 下载误记成批次报告导出。批量详情没有目标级暂停/继续/停止/取消业务按钮；目标行只有证据弹窗、查看执行/占用，重跑通过勾选后统一提交。`request_control` 只支持 batch/round scope，没有 target scope（`bulk_schema.py:173`、`service.py:207`）。

## 集合批量与逐项处理证据

| 流程 | 当前真实执行方式 | 事务/恢复与限制 |
|---|---|---|
| 新注册创建 | `service.py:3307` 循环 create_job，`3329` 每个 job 入队 | 只有 Python `_executor_lock` 和共享配置快照；本函数没有包住整批创建/入队的数据库事务。可产生已创建子集；无独立幂等请求和持久创建命令 |
| 注册失败重跑 | `jobs.py:505` 循环 retry_job；每个 job 会分别判定注册/Codex/套餐/配置补跑 | 无整批事务；结果 started/reused/skipped。服务端上限 500，前端 batchCandidates 来自已加载批次内容。现有注册接口没有 bulk round 记录 |
| 注册批次停止 | `service.py:4701` 只读最近 1000 jobs 再按 batch_id 过滤，`4712` 循环单 job 停止 | 不是全批次数据库查询，老批次/超过最近窗口可能遗漏；这是审计风险，未修改。变更扫描范围可保持停止语义，但注册调度/状态流转改造仍须具体方案确认 |
| 注册批量取消 | `db_legacy.py:3658` 事务内集合更新 JOBS 和取消 queued registration Run | 事务后逐条 `_sync_operation_job`；持久事实批量、投影仍逐项 |
| 注册批量删除 | `db_legacy.py:4408` 集合条件 DELETE | `jobs.py:575` N 次预读取，之后文件清理逐个；job 删除/统一任务来源标记/日志和调试产物不是一个整体原子过程 |
| 批量名单冻结 | `bulk_selections.py:180` 事务；`254` INSERT SELECT 固定名单；`277` 每 5000 个纯数据库预检 | 有 selection/revision/config snapshot/idempotency；不是调用远端预跑。容量 100000（`268`） |
| 批次与轮次 | `bulk_batches.py:66` 事务创建 batch_controls/initial round；`313` 新建重跑 selection/round；`374` 冻结重跑名单 | 具备独立生命周期/历史轮次；current 视图取每个目标最新请求轮次，round 视图保留历史 |
| 分块展开与入队 | `service.py:365` 每批 process_batch(limit=100)；`bulk_runtime.py:249` 单批事务、advisory 锁、control/target/account 锁 | 接收完整逐目标回执，`320` 同事务落 run links/目标状态/outbox；不在此事务发远端请求 |
| 首次目标正常提交 | `adapters.py:268` 集合账号状态领取；`310` `create_runtime_tasks_many` | `runtime.py:864` 使用 jsonb_to_recordset 一次 INSERT Task、一次 INSERT Run、集合更新 Task、一次 INSERT events；SQL 数量不随目标数线性增加 |
| 旧任务重跑 | `adapters.py:196` 遍历 prepared，`208` 每项目 savepoint，`229` retry_runtime_task，后续逐账号投影 | 在调用方 chunk 事务内，但有 N 次 task/run 领域操作；所以现有平台不能叫“所有操作都无逐条处理” |
| 批量停止/取消 | `bulk_control.py:112` settle_control；`199` 每 100 目标、`207/215` 目标/run 双循环 cancel_run | 持久 command/settlement_cursor，租约 fence 可接续；控制受管但底层仍逐执行取消 |
| 运行结果汇总 | `bulk_runtime.py:95` 事实变更写 outbox；`bulk_projection.py` 异步消费 | 可复用增量投影/计数和报告；属于最终一致展示，不是节点级一条远端调用 |
| 后台恢复 | `bulk_control.py:243` claim_work/renew_work，lease_until/fence；`service.py:398` 启动 selection/expand/project workers | 持久状态+过期租约重新领取；前端原请求用 `useBulkIntent.ts` 保存 key/body 幂等恢复 |

## 可复用抽象与批量节点缺口

| 抽象 | 可复用程度 | 缺口/设计边界 |
|---|---|---|
| 批次 batch | 已有 operation_batch_controls、配置快照、并发、暂停/结束、control_revision | 每批只一个 action；若新需求是一个批次多个操作节点，需明确 batch 与 node 的层级，不能把旧 batch 直接重命名 node 后认为完成 |
| 固定目标名单 selection | 高：query/ids/batch_targets/retry_members、revision、快照、稳定 target identity | 当前目标面向已存在 account/credential；注册 slot/job/邮箱租约的固定身份需独立设计；不能在冻结时偷偷提前领取邮箱或开始注册 |
| 轮次 round | 高：initial/manual_retry、按结果/勾选固定名单、历史结果与当前结果 | node 执行轮次与整批重跑轮次关系尚不存在；所有失败/未执行/结果不明目标均应有明确可重跑策略，不能新增等待人工核对门槛 |
| 目标 target_round | 高：admission/chain/outcome、blocker、owned run links | 有逐账号执行链，不等于批量 node；target 级错误分类和证据必须保留 |
| 节点 node | 当前无 | 需新增节点身份、operation/依赖/输入名单/节点级状态与统计、批量执行器契约（prepare_many/submit_chunk/apply_many 或同义）；不要只增加 UI 节点盒子，内部继续循环单条 API |
| 控制与恢复 | 高：command、scope、revision、租约 fence、结算 cursor、outbox | 当前 scope 仅 batch/round；node/target scope 若需要应扩展明确契约。目标取消仍调用单 run 领域实现，不能简单强杀替代 |
| 批量适配器 | 部分：prepare_many/submit_chunk/retry_many、集合 fresh path | 已有 old-task retry/stop 的逐项段；用户要求全批量节点时需逐操作确认哪些是集合 DB、分块 I/O、逐目标必须远端交互，而非“一个请求”即完成 |
| 报告/导航 | 高：目标归属、历史轮、当前汇总、报告懒加载 | 缺导出接口、无节点报告；可先用现有报告展示层，但未授权实现 |

建议优先清晰划分：业务写按钮进入持久批量命令/节点；控制按钮作用于批次/节点/轮次/选中目标；读/本地按钮维持查询和展示。单条写入口可以用一个目标走同一提交契约，但不应把查询、分页、日志弹窗也错误地排进执行队列。

## 注册主流程保护边界

本报告不提出直接修改 Roxy、proto2 或任何其他协议的请求参数、步骤顺序、页面定位点击、关键分支、重试次数/超时、邮箱租约释放和注册状态流转。复用批量平台也不构成修改这些行为的授权。

可先继续只读取证/形成设计：按钮到节点映射、现有批次身份对齐、集合入队写法、报告与日志展示、错误分类证据。若拟将注册创建/重跑/停止迁入新执行框架，需要先单独汇报具体代码位置、行为是否变化、旧链路隔离、影响范围和验证方案，得到用户明确确认后实施。尤其不得为了统一节点把不同注册驱动共享一套新的步骤/重试策略；不能把 `request_unknown` 等结果不明当成禁止重跑理由。

## 已知风险与证据限度

1. 注册批次停止只从最近 1000 条取目标；该实现可能漏掉窗口外同批任务（`service.py:4701`）。
2. 注册批量重跑仍是逐条提交；bulk 平台旧 Task 重跑/控制也有逐项数据库调用，上述差异必须计入后续工作量。
3. `jobs.py:670` 诊断 GET 仍有 `category=unknown/category_label=未分类` 回退，与“无未分类错误”要求存在文案/诊断契约缺口；本次仅标记，未据此改注册行为。
4. `useBulkIntent.ts:20` 在原回执未确认时对不同内容有 `request_receipt_pending` 阻断；它防止重复原请求，与创建新轮次是不同语义。后续需结合用户“不随便阻断重跑”的要求审视交互，不能直接将所有未决请求混同远端业务失败。
5. 只做源码静态审计，没有对本地/Oracle 部署版本和真实按钮逐个点击验收；不声称线上已具备或已修复上述能力。
