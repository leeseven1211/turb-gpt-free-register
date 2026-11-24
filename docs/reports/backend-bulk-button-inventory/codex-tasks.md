# Codex 凭证、任务中心全按钮只读审计

审计日期：2026-11-24。对象：当前本地工作区 `main`，HEAD `f9548737`，包括已有未提交修改；不能据此断言 Oracle 或当前运行服务行为。未修改业务文件、未调用业务写接口、未提交、未部署、未执行真实授权/上传/刷新。

路径均相对 `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register`。下文“一次”专指用户动作的一次业务 HTTP；操作成功后的列表刷新、详情轮询另列。`N` 是选择目标数，`M` 是实际成功目标数。

## 判断口径

- **本地交互**：展开、关闭、勾选、列宽、步骤筛选，无业务批量执行需求。
- **集合读取**：一次列表/分页查询；不需要把页面筛选变成执行节点。
- **数组包装**：前端一次 HTTP，后台仍 `for target → 单条服务/单条事务`，不算用户所要求的批量节点。
- **旧批次分组**：有 `account_action_batches` 或 `operation_batches` 分组，但无新批量系统固定目标、轮次与控制模型；依然需迁移。
- **新批量节点**：`core.bulk_operations` 的 batch/round/canonical target/target round 模型，集合准入与持久调度；每个目标的正常远端调用仍可独立执行，不应把 N 次 OAuth grant 等价为低效逐条处理。

## 关键结论

1. Codex 的 7 个批量业务按钮前端均只发一次 HTTP，没有前端循环 N 次请求；问题主要在后端。归档/恢复、删除、本地导出、CPA 导出仍逐条访问数据库；上传逐条创建 durable task，且无批次归属。
2. Codex Token 刷新创建的是字符串 UUID 的旧 `account_action_batches`。刷新服务仅将正整数放入 native `batch_id`，字符串写入 `data.legacy_batch_id`，所以这里连 native 分组外键都没有接上；不是新批量节点。
3. Codex 重授权创建旧 native `operation_batches`，然后逐条查账号、逐条 `submit`/建 task/run/回写状态；已有新批量 `codex_retry` action 可复用，却没有由凭证页接入。
4. 任务中心批量重跑/取消/终止是数组接口内串行调用单条动作。批量重跑同批次 managed task 时，每条会创建一个“单目标新轮次”，一次选择 N 条可能形成 N 个 round，不是同批次一次目标集合的新轮次。
5. 任务中心删除已有一次事务、一次 `ANY` 锁定读取，但仍逐条 UPDATE；单条删除已经复用 `delete_tasks([id])`。它比每条独立事务好，但仍不是新批量控制节点，也不是集合 UPDATE。
6. 新批量适配器已有 `codex_retry`；`catalog.py` 中 `token_refresh` 是“刷新 AT”，不能误当作 Codex OAuth Token 刷新。后者与手动上传需要独立 action/适配。

## Codex 所有语义按钮

主入口与行菜单：`frontend/src/features/codex/CodexCredentials.vue:20-48`、`CodexTable.vue:48-85`。同一语义在直接按钮与更多菜单重复出现时合并列出。

| 编号 | 按钮/出现位置 | 处理函数及 API | 前端与后端实况 | 分类/建议 |
|---|---|---|---|---|
| C01 | 批量“刷新 OAuth Token”；行菜单同名 | `actions.run('refreshToken')` → `codexApi.refreshToken(names)`，POST `/api/codex/refresh-token-bulk`；`actions.ts:92-97`、`api/codex.ts:94` | 一次 POST，单条也传一元素数组；后端建旧字符串 batch 后 `for filename → enqueue_refresh`，各凭证独立读、fence、active 查询及 durable submit | 旧批次分组+数组包装；迁入独立 `codex_token_refresh` 节点，集合定位/准入/建任务，保留逐凭证远端 grant |
| C02 | 批量“重跑 Codex 授权”；行菜单“重跑授权” | `actions.run('reauthorize')` → `codexApi.reauthorize(names)`，POST `/api/codex/retry-bulk`；`actions.ts:92-97`、`api/codex.ts:95` | 一次 POST，单条也传一元素数组；路由先全量列凭证，再逐条按邮箱找账号；服务建旧 runtime batch，再逐条 `get_account` 和 `submit` | 旧批次分组；复用已有新批量 `codex_retry`，凭证选区集合解析到账号，N=1 走同一路径 |
| C03 | 批量“下载凭证” | `actions.run('downloadBulk')` → `downloadBulk(names,false)`，POST `/api/codex/download-bulk`；`actions.ts:70-76`、`api/codex.ts:99` | 一次 POST；同步循环读凭证和逐条标记导出；返回一个聚合 JSON；成功后再一次列表刷新 | 数组包装；批量导出节点/产物，集合读取、集合更新导出计数，保留逐文件序列化与失败清单 |
| C04 | 行“下载凭证”，直接按钮+更多菜单重复 | `actions.run('download',[filename])` → GET `/api/codex/download/<filename>`；`CodexTable.vue:67,72`、`api/codex.ts:97` | 一次 GET，读取+计数递增；成功后一次列表刷新 | 单条专用接口；可共用 C03 的集合服务、以 N=1 生成 CPA 兼容单 JSON，保留下载格式差异 |
| C05 | 批量“从 CPA 下载” | `actions.run('downloadBulkCpa')` → POST `/api/codex/download-bulk-from-cpa`；`actions.ts:70-76`、`api/codex.ts:99` | 一次 POST；CPA 列表最多一次（已有共享）；随后顺序下载每文件、逐条读本地凭证并更新导出状态；同步产出 ZIP/manifest | 数组包装且外部下载串行；改为导出节点，集合本地读取/回写，远端单文件请求采用受控并发，保留共享 CPA 列表 |
| C06 | 行“从 CPA 下载” | `actions.run('downloadCpa')` → GET `/api/codex/download-from-cpa/<filename>`；`CodexTable.vue:74`、`api/codex.ts:97` | 一次 GET；单文件 CPA 定位/下载+导出计数，完成后一次列表刷新 | 单条专用；共用 C05 节点/集合服务，N=1 可直接下载文件 |
| C07 | 批量/行菜单“上传 sub2api” | `actions.run('uploadSub2')` → POST `/api/codex/upload-sub2-bulk`；`actions.ts:99-111`、`api/codex.ts:96` | 一次 POST，单条也数组；路由 `for filename → manual_upload.queue_filename`；每目标读凭证/账号/引用并单独提交 durable task，无 batch 参数 | 数组包装，无批量节点；新增 `sub2api_manual_upload` 批量 action，集合前置读取/建目标，目标 worker 保留凭证代际与远端回执 |
| C08 | 批量“归档选中/恢复选中” | `actions.run('archiveBulk')` → POST `/api/codex/archive-bulk`；`actions.ts:78-82`、`api/codex.ts:90` | 一次 POST；后端循环 `db.archive_codex`，每项先单条读再单条 patch，不共用一个事务 | 数组包装；批量状态节点+集合 UPDATE RETURNING，单条归档共享服务 |
| C09 | 行“归档/恢复” | `actions.run('archive',[filename])` → POST `/api/codex/archive`；`CodexTable.vue:78`、`api/codex.ts:89` | 一次 POST；相同单条 `archive_codex`，完成后列表刷新 | 单条专用接口，可将 C08 作为唯一业务实现，N=1 复用 |
| C10 | 批量“删除选中” | `actions.run('deleteBulk')` → POST `/api/codex/delete-bulk`；`actions.ts:84-89`、`api/codex.ts:92` | 一次 POST；循环 `db.delete_codex_credential`，每项先读再开启单条删除事务 | 数组包装；批量删除节点、一次集合定位/删除/回执；保留不存在等逐项结果 |
| C11 | 行“删除凭证” | `actions.run('delete',[filename])` → POST `/api/codex/delete`；`CodexTable.vue:79`、`api/codex.ts:91` | 一次 POST；同一单条存储函数，完成后列表刷新 | 单条专用接口，可共用 C10 服务，N=1 复用 |
| C12 | 行“重置标记”（仅 exported_count>0） | `actions.run('reset',[filename])` → POST `/api/codex/reset-export`；`CodexTable.vue:77`、`actions.ts:91`、`api/codex.ts:93` | 一次 POST，仅一个 filename，读后 patch exported_count/at；刷新列表 | 只有单条入口；若将来增加批量按钮直接用数组节点，当前可先使单条成为 N=1 集合服务；不擅自新增 UI |
| C13 | “查看上传进度” | `actions.showProgress` → `callbacks.openTasks()`；`actions.ts:118`、`CodexCredentials.vue:44`、`webui/static/js/pages/codex/page.js:30` | 导航到任务中心；不发上传请求，任务页按需发列表 GET；目前打开的是全部任务，未携带上传 batch | 导航；批量迁移后可定位上传批次/节点详情 |
| C14 | 刷新、错误“重试”、空态“重新加载” | `refresh → list.refresh → codexApi.list`；`CodexCredentials.vue:31,44,46-47`、`CodexTable.vue:85`、`useCodexList.ts:44-77` | 通常一次 GET `/api/codex?...`；删除末页等页码越界最多补一次纠正查询 | 集合读取；保留，不创建批量节点 |
| C15 | 行“更多”及收起 | Popover `setActionOpen`；`CodexTable.vue:30-38,69` | 0 HTTP，仅控制弹层；选择业务菜单后转 C01-C12 | 本地交互 |
| C16 | 工具栏“筛选”、8 个列筛选触发、关闭、完成 | `CodexFilters`/`FilterPopover` 的 open 更新；`CodexFilters.vue:21-45`；列定义 `filterDefinitions.ts:11-20` | 单纯开/关/完成 0 HTTP；实际改值触发列表 GET（文本 250ms 防抖）；字段为邮箱/文件、Plan、状态、OAuth 状态、Account ID、Sub2API ID、更新时间、过期时间 | 本地交互/集合查询 |
| C17 | 筛选“全部”和动态单选项；文本/日期更改 | `change/finishPointerChoice → list.updateFilters`；`CodexFilters.vue:21-42`、`useCodexList.ts:103-112` | 每次生效查询一次列表；不是遍历每凭证；无变化不查询 | 集合查询 |
| C18 | “清除此列”、筛选 chip ×、“清除筛选” | `clear`/`removeFilter`/`list.resetFilters`；`CodexFilters.vue:22,45`、`CodexCredentials.vue:33,43-44` | 更改筛选后一次 GET；chip 可动态生成 | 集合查询 |
| C19 | “恢复列宽”、各列鼠标/键盘调宽 | `table.resetColumns`、`useColumnWidths`；`CodexCredentials.vue:44`、`CodexTable.vue:16`、共享 `ColumnResizer` | 0 业务 HTTP，浏览器本地列宽状态 | 本地交互 |
| C20 | 单行勾选、全选当前页 | `list.toggle/togglePage`；`CodexTable.vue:48,57`、`useCodexList.ts:119-127` | 0 HTTP，仅 Set；Codex 可累积跨页选择（筛选/归档切换按规则清理） | 本地选择 |
| C21 | 上一页、下一页、动态页码、跳转、每页条数 | `ListPagination` → `setPage/setSize`；`CodexCredentials.vue:48`、`components/ListPagination.vue:34-75` | 查询一次页数据；无效/同页不请求；条数 10/20/30/50/100 | 集合读取 |
| C22 | 页面模块加载失败“重新加载” | DOM click → `CodexCredentials.setVisible(visible)` → `ensure`；`webui/static/js/pages/codex/page.js:36-47` | 重载 Vue 模块并按可见性请求列表；非逐项业务 |
| C23 | 侧栏“Codex 授权”“活跃账号/归档账号” | `webui/templates/index.html:95-104`、`webui/static/js/shared/common.js:1434` → `setArchived/setVisible` | 范围切换清理选择并一次 GET；无归档写入 | 导航/集合读取 |

### Codex 后端证据与复用边界

- Token 刷新：`webui/routes/codex.py:78-120`；旧 batch UUID：`core/storage/operations/legacy_task_store.py:257-266`；逐项读取/围栏/active 查询：`core/codex/token_refresh_service.py:1661-1784`；legacy/native batch 分叉：`:1788-1814`；durable 单任务提交：`:1599-1625`。
- 重授权凭证解析：`webui/routes/codex.py:575-599`，`db.list_codex_accounts(archived='all')` 全量加载与逐条 `get_account_by_email`；提交：`core/codex/operation_service.py:705-768`，旧 batch 创建 `:729`，逐账号循环 `:737`，`submit` 内第二次按邮箱读账号与单条创建/回写 `:593-675`。`_dispatch_bulk` 只是一次唤醒共享调度器（`:506-510`），不代表集合建任务。
- 归档/恢复：`webui/routes/codex.py:122-167` → `core/storage/db_legacy.py:3225-3238` 的 `_patch_codex` 先单条读再 patch。
- 本地下载：`webui/routes/codex.py:169-184,328-383`；读取：`core/storage/db_legacy.py:3240-3246`；计数：`:3249-3282` 每次新连接、原子单条递增。
- CPA 下载：`webui/routes/codex.py:219-325`，共享 auth-files 列表 `:262-271`，串行逐文件下载 `:251,275-291`；CPA 外部接口只提供单文件下载路径，`core/codex/oauth.py:462-468,517-543`。正常 N 个文件下载不可直接省成 1 次，但并发度与本地集合读取/回写可以优化。
- 手动上传入口实际位于 `webui/routes/accounts.py:1687-1730`，不在 codex.py。逐项提交 `:1704-1720`；`core/integrations/sub2api/manual_upload.py:49-96` 每次 `_read` 及引用读取、`submit_durable_operation`，没有 batch 参数；worker 的真实上传 `:151-181`。
- 删除：`webui/routes/codex.py:398-438` → `core/storage/db_legacy.py:3317-3327`；每目标单条读+transaction+delete_rows，1000 条意味着约 N 次独立删除事务，不能将 `delete_rows(...,[id])` 的数组形状当成批量执行。
- 已有集合凭证定位可直接复用：`core/storage/codex/__init__.py:37-44` 的 `get_codex_accounts_by_filenames`，一次 `filename=ANY(...)`；当前上述批量入口未使用它。
- 可复用新批量能力：`core/bulk_operations/catalog.py:13` 的 `codex_retry`；`core/bulk_operations/adapters.py:144-156,316-325`；集合 Task/Run/Event 创建 `core/storage/operations/runtime.py:864-944`。`catalog.py:11` 的 `token_refresh` 属于 AT，不能串错操作。
- 旧 `/api/codex/retry`、`stop`、`stop-bulk`、`reset-retrying`、`retry-log` 路由仍存在（`webui/routes/codex.py:440-645`），但本次 Codex Vue 界面和迁移 page.js 没有按钮引用这些 API；不能把遗留路由算成当前凭证页按钮。账号页的对应按钮由账号审计负责。

## 任务中心所有语义按钮

主入口：`frontend/src/features/tasks/TaskCenter.vue:102-121`、`TaskTable.vue:29-59`；任务详情 `detail/TaskDetail.vue:127-180`。任务中心没有更多行菜单，行操作为条件直接按钮。

| 编号 | 按钮/出现位置 | 处理函数/API | 前端与后端实况 | 分类/建议 |
|---|---|---|---|---|
| T01 | 批量“重跑” | `bulk('retry') → tasksApi.bulk` → POST `/api/operations/bulk`，`{action:'retry',task_ids}`；`TaskCenter.vue:74-98`、`api/tasks.ts:84-87` | 一次 POST，Idempotency-Key；服务逐条读任务后调用单条 perform；managed task 每条调用 `retry_managed_task → create_round(selection单目标)` | 数组包装；按所属批次/动作分组，一批一次目标集合 round；非 managed 历史任务也转新批量节点，不循环单条重跑 |
| T02 | 行“重跑” | `action(task,'retry') → tasksApi.action` → POST `/api/operations/<id>/retry`；`TaskTable.vue:54`、`TaskCenter.vue:53-72` | 一次 POST，Idempotency-Key；与 T01 最终共用单条业务；managed task 合理地生成一目标新轮次 | 将单条视为 N=1 的同一批量动作，不另建行为分支；保留历史来源解析 |
| T03 | 批量“取消排队” | `bulk('cancel')` → POST `/api/operations/bulk`；`TaskCenter.vue:78-95` | 一次 POST；逐任务只接受 queued，再读取一次任务调用 cancel handler，逐任务事务与通知 | 数组包装；批量控制节点/集合任务锁定+状态迁移；逐目标保留竞争状态复查和回执 |
| T04 | 批量“终止运行” | `bulk('terminate')` → 同一 bulk API | 一次 POST；逐任务要求 native active 且非 queued，再单条 terminate handler | 数组包装；按批次/类型/资源域集合处理，统一控制节点；正常远端请求回执与清理仍按 Run |
| T05 | 行“取消/终止”（queued 显示取消） | `TaskTable.vue:54` 无论文案均 emit `terminate` → POST `/api/operations/<id>/terminate`；`TaskCenter.vue:53-72` | 一次 POST；单条 terminate 允许 queued 按取消收口；不同于 T03 的 cancel 端点 | 单条与批量语义应统一为显式 queued cancel / active terminate，N=1 复用，保留状态竞争保护；本轮只记录 |
| T06 | 批量“删除” | `bulk('delete') → tasksApi.bulk` → POST `/api/operations/bulk` | 一次 POST；`delete_tasks(ids)` 单事务一次集合 SELECT FOR UPDATE，但每条 UPDATE；保留审计、隐藏记录 | 部分集合化，尚无节点；可以一次集合 UPDATE RETURNING 并产生整批回执/节点；不物理删除审计 |
| T07 | 行“删除” | `action(task,'delete') → POST /api/operations/<id>/delete`；`api/tasks.ts:81-83` | 一次 POST；`delete_operation → delete_tasks([id])`，已共用集合存储函数 | 保留 N=1 复用，后续只升级集合实现 |
| T08 | 行 ID、“详情” | `openDetail → detail.open`；`TaskTable.vue:44,54`、`TaskCenter.vue:41` | 首次详情通常 3 次只读 GET：detail，再并行 progress+events；非 N 目标遍历 | 必要组合读取；可考虑快照聚合但无需批量执行节点 |
| T09 | 动态“查看批次/批次标题” | `emit('batch',id,round)` → shell onBatch → `BulkTasks.navigate('detail',...)`；`TaskTable.vue:25-26,49`、`webui/static/js/pages/operations/page.js:38` | 导航到批量任务详情，由批量页读取；无写入 | 导航 |
| T10 | 列筛选、移动“筛选”、关闭、完成 | `TaskFilters/TaskColumnFilter/TaskFilterFields/FilterPopover`；`TaskFilters.vue:15-17`、`TaskColumnFilter.vue:12-15`、`TaskFilterFields.vue:68-70` | 开/关通常本地；打开需 facets 的列时可能一次列表 GET 更新 facets；完成仅关闭 | 本地/集合读取；不是按任务发查询 |
| T11 | 动态筛选“全部/各选项”、文本/日期值 | `update/choose → updateFilters`；`TaskFilterFields.vue:25-35,40-65`、`useTaskList.ts:99-114` | 一次列表 GET（文本260ms防抖）；条件为 ID、类型、目标、执行状态、目标状态、批次/触发、运行次数、当前步骤、创建/完成、结果/错误 | 集合读取 |
| T12 | “清除此列”、筛选 chip ×、“清除全部筛选” | `clear`/`removeFilter`/`list.applyFilters({})`；`TaskFilterFields.vue:33-35,69`、`TaskCenter.vue:37-40,107-110` | 一次列表 GET（若条件不变则没有）；无业务状态修改 | 集合读取 |
| T13 | “恢复列宽”、调宽控件 | `table.resetColumns`、ColumnResizer；`TaskCenter.vue:112`、`TaskTable.vue:20,39` | 0 HTTP | 本地交互 |
| T14 | 列表错误“重试”、空态“重新加载” | `list.refresh`；`TaskCenter.vue:116-117`、`TaskTable.vue:56` | 一次 GET `/api/operations`，必要时 facets 再刷新一次；平时可见页每5秒一次列表 GET | 集合读取；不能把轮询算作逐项执行 |
| T15 | 行勾选、全选当前页 | `toggle/togglePage`；`TaskTable.vue:35,43`、`useTaskList.ts:93-98` | 0 HTTP；批量 targets 取当前页 selectedRows，换页/筛选会清理选择 | 本地选择；当前单次 API 上限100，与最大页100对应，不是全筛选范围批量 |
| T16 | 上一页、下一页、页码、跳转、每页条数 | 共享 ListPagination；`TaskCenter.vue:118`、`components/ListPagination.vue:34-75` | 一次页查询；每页20/50/100 | 集合读取 |
| T17 | 结果/错误折叠摘要、跳过原因摘要 | `TaskResultCell → ListResult` 原生 details；`TaskCenter.vue:116`、`TaskResultCell.vue:24`、`components/ListResult.vue:12-15` | 0 HTTP，展开已载入文本 | 本地交互 |
| T18 | 任务中心模块加载失败“重新加载” | `TaskCenter.setVisible → ensure`；`webui/static/js/pages/operations/page.js:42-52` | 重载模块后一次列表 GET | 壳层重试 |
| T19 | 侧栏“任务中心” | `webui/templates/index.html:115-118` → shell setVisible | 导航后一次列表 GET | 导航 |

### 任务详情、步骤详情及动态控件

| 编号 | 按钮/位置 | 处理函数/API | 请求与执行分类 |
|---|---|---|---|
| D01 | 详情“刷新”、读取失败“重试” | `detail.refresh → readDetail`；`TaskDetail.vue:135-137`、`useTaskDetail.ts:145-182` | 一次 detail GET，然后并行 progress+events；日志页额外logs，共3/4 GET。活跃任务每2秒同样读取；请求合并 pendingRefresh，0业务写入 |
| D02 | 详情“关闭”、Esc | `close/finishClose → detail.close`；`TaskDetail.vue:53-60,129,135` | 0 HTTP；停止轮询、终止在途读取、恢复焦点 |
| D03 | “运行”选择执行实例 | `selectRun → detail.selectRun`；`TaskDetail.vue:72-75,134`、`useTaskDetail.ts:199-206` | 新 Run 的 detail+progress+events，日志页可加logs；单目标诊断读取 |
| D04 | “事件时间线/运行日志/诊断资源”3个页签 | `selectTab`；`TaskDetail.vue:76-89,146`、`useTaskDetail.ts:208-211` | 日志页一次logs GET；其他页本地切换，无写入 |
| D05 | “从头加载/最近记录” | `loadWindow('start'/'tail')`；`TaskDetail.vue:91-98,148` | 按当前事件/日志页分别一次 `/events?...` 或 `/logs?...` GET；不是循环读取全部历史 |
| D06 | 事件/日志错误“重试” | `detail.loadEvents()/loadLogs()`；`TaskDetail.vue:152,162` | 对应一次增量 GET |
| D07 | “继续加载后续事件/继续加载后续日志” | `loadWindow('next')`；`TaskDetail.vue:159,168` | 每点击一页一次 GET，limit500；合理分页读取 |
| D08 | “有N条新记录，回到底部” | `scrollLatest`；`TaskDetail.vue:100,177` | 0 HTTP，仅滚动 |
| D09 | 动态步骤按钮、再次点击取消步骤筛选、“清除步骤筛选” | `TaskProgress emit filter` / `stepFilter=null`；`TaskProgress.vue:72-79`、`TaskDetail.vue:143,147` | 0 HTTP；过滤已经读取的事件/日志 |
| D10 | 每步“查看阶段关系与证据”图标 | `inspect(step)`；`TaskProgress.vue:44-49,80` | 0 HTTP；打开已载入 progress 的步骤弹窗 |
| D11 | 步骤详情“关闭”、Esc/遮罩 | `closeInspector`；`TaskProgress.vue:50-54,91-92` | 0 HTTP |
| D12 | 动态“独立子任务 #ID” | `emit child → TaskDetail.open`；`TaskProgress.vue:90`、`TaskDetail.vue:143` | 打开子任务，按 D01 读取；是显式单任务查看，非批量任务逐条发起 |
| D13 | “下载 HAR/下载页面现场/查看失败截图” | 原生链接 `/api/operations/{task}/runs/{run}/debug/{har|page-state|screenshot}`；`TaskDetail.vue:171`、`webui/routes/operations.py:94-123` | 各点击一次只读产物 GET；无需批量节点，未来整批产物下载则走节点 |
| D14 | 事件/日志“技术详情”、执行结果字段、失败详情折叠、依赖与执行记录、阶段实例、阶段事件、技术字段、子步骤、步骤证据 | 原生 details/summary；`TaskDetail.vue:157,166,174`、`TaskFailure.vue:47`、`TaskProgress.vue:85`、`StepEvidence.vue:20-39` | 0 HTTP，仅展开已读取数据；覆盖所有动态 summary |

### 任务中心后端证据

- API 映射：`frontend/src/api/tasks.ts:73-87`；路由单条 `webui/routes/operations.py:159-187,216-224`，bulk `:189-214`；bulk 上限100。
- `core/operations/action_service.py:185-250`：delete 分支共享存储；其余 `for task_id` 在 `:209`，第一次 `_get_operation_action_task` 在 `:210`，调用 `perform_operation_action` 在 `:225`；该函数又在 `:48` 读取同一任务。取消/终止已避免加载 events（`:29-33`），仍有 N 次重复元数据读取；重跑默认读取完整 task/events。
- managed 重跑：`action_service.py:62-71` → `core/bulk_operations/service.py:228-249`，每次 `selection.target_ids` 只有一个 canonical target。因此任务中心一批勾选同批次多个任务时仍逐个新 round；建议先集合解析其 batch/target，再按 batch 生成一个集合 round，跨 batch 则每个来源 batch 一个 round。
- 删除：`action_service.py:170-181,193-205` 共用 `delete_tasks`；`core/storage/operations/store.py:739-805` 一次事务、一次 ANY 查询，`:775` 开始逐目标校验，`:788` 附近逐行 UPDATE。内存逐目标分类合理，SQL逐条更新可集合化。
- 行停止文案/API：`TaskTable.vue:54` 对 queued 显示“取消”，实际动作参数始终 `terminate`；bulk cancel 则仅 queued，bulk terminate 跳过 queued（`action_service.py:215-223`）。后续统一批量 service 时应保留明确状态分流，避免换接口后改变用户语义。
- 单条与批量任务动作现共用的是“单条业务函数”，即反向复用；目标应该是集合应用服务统一处理，单条传 `[id]`，不把批量实现成循环调用单条 HTTP/服务。
- 幂等：`frontend/src/api/tasks.ts:35-61` 只为重跑保存网络请求意图，成功或确定性4xx后清理；不是人为阻断用户再次发起重跑。迁入批量节点应保留此区分。

## 建议实施顺序（仅建议，本轮未实施）

1. **先统一创建执行节点**：凭证重授权复用已有 `codex_retry` action；Codex OAuth Token 刷新、Sub2API 手动上传增加独立 action，固定选择范围后集合准入/建 Task/Run/目标，N=1 同用。不能把 AT `token_refresh` 当作 OAuth Token 刷新。
2. **修正任务中心批量控制**：集合解析 selected task，managed 重跑按 batch 聚合 target_ids 一次 create_round；取消/终止统一成批量控制请求，集合读取/锁定、集合状态迁移，保留每 Run 的回执、停止清理与竞争复查。
3. **集合化数据动作**：Codex 归档/恢复/删除/重置标记，本地导出读与导出计数均用集合仓储及 RETURNING 产生逐目标分类；业务按钮从单条/数组包装迁入同一批量节点。
4. **导出作为批量产物**：本地 JSON/CPA ZIP 用批量节点记录进度、成功/失败与产物。CPA auth-files 列表共享机制保留，每文件下载受控并发；本地集合回写计数。单条下载保留原格式，调用同一服务。
5. **保持 UI 本地操作轻量**：筛选、分页、选择、详情阅读和列宽恢复保持本地/集合查询；这些不是批量业务动作。只对真正执行/改变业务状态的批量操作引入节点，不把每个“关闭/完成”按钮变成任务。

正常每凭证 OAuth grant、完整授权流程、单文件 CPA 下载和上传请求在目标 worker 内执行属于必要个体操作；需要消除的是请求线程逐条准入/建任务、多次重复全量读取、每条独立事务与同一批量操作拆 N 个控制 round。涉及注册主链路的后续方案仍应独立说明并获得用户确认；本审计未改任何执行行为。
