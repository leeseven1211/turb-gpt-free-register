# 邮箱与代理按钮审计（2026-11-24）

范围：`frontend/src/features/email`、`frontend/src/features/proxy`、`frontend/src/api/email.ts`/`proxy.ts`、`webui/static/js/pages/email/page.js`/`proxy/traffic.js`、`webui/routes/email_pool.py`/`proxy_traffic.py`，以及对应的 `core/email`、`core/storage/email`、`core/email/email_butler`、`core/proxy`、`core/storage/proxy`。本报告为只读源码审计；未启动服务、未调用业务写接口、未改仓库业务文件。

## 结论先行

- 邮箱库存页已经有“批量标记”和“批量删除”按钮，前端各发 **1 个 bulk POST**；后端却在请求内 `for` 逐邮箱查行、逐邮箱事务/更新和逐邮箱同步排队，**没有批次节点、批次状态、统一事务边界或批量 SQL**（`webui/routes/email_pool.py:609-673,707-769`）。这正是后续应改成批量节点的主要对象。
- Butler “从 Butler 导入”已是完整持久化批次：预览令牌 → `request_id` 幂等批次 → item 行 → 后台恢复/重试/取消/轮询；数据库事务会一次创建批次及全部 item，但 v2 每个 item 仍独立远端租约请求，属于**批次编排 + 逐目标网络行为**（`core/email/email_butler/manual_import_v2.py:104-153,207-270,273-314`）。
- 兼容“粘贴导入”是单次请求解析数组；Outlook、通用 API、Butler 均在一次数据库事务中按地址排序逐条插入，Butler 仅恢复已有租约，不随机新领地址；没有导入批次节点（`webui/routes/email_pool.py:391-421,514-573`; `core/storage/email/local_imports.py:93-192`）。
- 代理流量页当前全部是只读查询、筛选、分页、详情和列宽操作，没有代理检测/回收按钮。代理供应商检测按钮位于配置动作页，固定提取并测试 **1 个 IP** 后立即释放测试租约（`frontend/src/features/config/ConfigActionTools.vue:68`; `webui/routes/integrations.py:254-295`）。代理池的批量候选验证、回收、复检由后台维护/供应层完成，非页面批量按钮。

## 邮箱按钮与处理链

### 概览与导航

| UI 按钮/操作 | 源码 | 处理函数 | API/请求次数 | 批次/逐目标语义 |
|---|---|---|---|---|
| 刷新资源、错误重试 | `EmailOverview.vue:16-18` | `overviewRead.refresh()` | GET `/api/dashboard`，单次；`inventoryChanged()` 还并发刷新 capabilities、registration sources、summary | 只读，无批次 |
| 显示/隐藏未启用来源 | `EmailOverview.vue:18` | `overview.expanded=!overview.expanded` | 无网络 | 纯展示 |
| 点击来源卡片 | `EmailOverview.vue:20` | `EmailPageShell.source()` | 导航并带筛选；随后库存 GET | 只读 |
| 从 Butler 导入 | `EmailOverview.vue:28`、`EmailInventory.vue:60` | `openButlerImport()` → `useButlerImport.open()` | GET options + POST preview（各 1 次，预览筛选变化 400ms 防抖） | Butler 批次入口 |
| 粘贴导入/导入邮箱 | `EmailOverview.vue:28`、`EmailInventory.vue:61` | `openImport()` → `useLocalImport.open()` | 无网络，打开弹窗 | 兼容导入入口 |

### 本地兼容导入弹窗

| UI 按钮/操作 | 源码 | 处理函数 | API/请求次数 | 批次/逐目标语义 |
|---|---|---|---|---|
| 关闭/取消 | `EmailLocalImport.vue:11-12,20` | `close()` | 无 | 中止预览 AbortController |
| 导入类型、内容、通用 API 有效期 | `EmailLocalImport.vue:14-18` | `update()` | 无；更新即清空旧预览并 abort | 纯表单 |
| 解析预览 | `EmailLocalImport.vue:20`；`useLocalImport.ts:17-23` | `preview()` | POST `/api/outlook/import-preview`，每次 1 次 | 服务端解析整段文本；最多 5000 行；无持久批次 |
| 导入到邮箱池 | `EmailLocalImport.vue:20`；`useLocalImport.ts:25-45` | `submit()` | 预览有效时 POST `/api/outlook/import`，1 次；预览失效会先补 1 次 preview | 单请求数组；响应未确认时保留原素材，不自动重提 |

后端兼容回退细节：`email_pool.py:514-573` 接受 `----`/`====` 分隔符；Outlook 4 段、通用 API 2 段（可带有效期）、Butler 每行完整地址。`local_imports.import_resources()` 在**单事务**中按邮箱排序逐条取地址锁、冲突检查、插入；非 Butler 逐条 enqueue import service fact（`core/storage/email/local_imports.py:104-192`）。Butler 粘贴导入调用 `handoff_for_import()`，只恢复本人既有完整长期租约；v2 旧回执只作兼容验证，不调用退役随机分配接口（`core/email/email_butler/inventory_handoff.py:110-115`; `local_imports.py:149-169`）。

### Butler 批量导入弹窗

| UI 按钮/操作 | 源码 | 处理/API | 批次语义 |
|---|---|---|---|
| 查看导入进度（恢复条） | `EmailButlerImport.vue:14` | `open()`，GET `/api/email-butler/imports/{batch_id}` | 从 localStorage 恢复批次并轮询 |
| 关闭（后台继续） | `EmailButlerImport.vue:16,35` | `close()` | 仅关弹窗；后台批次继续 |
| 刷新可用数量 | `EmailButlerImport.vue:38`；`useButlerImport.ts:70-79` | POST `/api/email-butler/import-preview`，1 次 | 生成 15 分钟 preview token；仅计数 |
| 开始导入 N 个 | `EmailButlerImport.vue:38`；`apply()` | localStorage 持久 `request_id`/token 后调用 `retry()` → POST `/api/email-butler/imports`，1 次，202 | 创建持久 batch + 全部 item；request_id 幂等 |
| 重试原请求/继续原批次 | `EmailButlerImport.vue:39`；`retry()` | POST `/api/email-butler/imports` 或 `/imports/{id}/retry`，1 次 | 不新建地址意图；恢复原 item，保留已导入结果 |
| 终止批次 | `EmailButlerImport.vue:36`；`cancel()` | POST `/imports/{id}/cancel`，1 次 | 只停止后续导入；已发请求、租约和已导入邮箱保留，不自动退租 |
| 新建导入 | `EmailButlerImport.vue:37`；`reset()` | 清 localStorage，重新 preview | 仅在批次结束/取消且不可重试时允许 |
| 自动进度轮询 | `useButlerImport.ts:52,110` | GET `/imports/{id}` 每 2 秒 | 读操作；导入数量变化后刷新库存 |

服务端路由：`webui/routes/email_pool.py:490-512`。`manual_import_v2.create()` 在一个事务内校验 preview/config、插入 batch、循环插入 item、写 execution handoff（`core/email/email_butler/manual_import_v2.py:104-153`）。后台 `_run_batch` 使用持久 worker；v2 `run_batch()` 最多 4 个并发 future，每个 `_item()` 独立调用 `get_lease`/`create_lease`/绑定/本地落库（`manual_import_v2.py:207-270,273-314`）。因此：**批次数据库节点已有；远端领取仍是逐 item 网络语义，不能简单合并成一条请求，除非 Butler API 提供等价批量幂等接口。**

### 库存列表按钮

| UI 按钮/操作 | 源码 | API/请求次数 | 当前实现分类 |
|---|---|---|---|
| 全选当前页、单行勾选 | `EmailInventory.vue:72,79` | 无 | 选择集合，最多当前页；后续 bulk 请求携带数组 |
| 批量“标记未使用/停用/标失败” | `EmailInventory.vue:55`；`useEmailInventory.ts:32-35` | POST `/api/outlook/status-bulk`，前端 1 次 | 已有 bulk API，但后端 `for` 每项 `_pool_row_for_source` + `set_*`/`release_*`；每个 Butler 项独立事务，非批次节点 |
| 批量删除选中 | `EmailInventory.vue:55`；`useEmailInventory.ts:28-31` | POST `/api/outlook/delete-bulk`，前端 1 次 | 已有 bulk API；后端 `for` 每项保护检查、删除、同步回执，非批次节点 |
| 复制当前页 | `EmailInventory.vue:59`；`useEmailInventory.ts:51` | POST `/api/outlook/secret-bulk`，1 次，最多 500 项 | API 一次读取数组，但后端逐项查 secret；读取型批量，无持久批次 |
| 单行复制素材 | `EmailInventory.vue:87` | GET `/api/outlook/secret`，1 次 | 必须逐目标读取 |
| 单行删除 | `EmailInventory.vue:87` | POST `/api/outlook/delete`，1 次 | 单目标事务；Butler 删除先写 tombstone，再 enqueue return |
| 单行更多：恢复可用/停用/标失败 | `EmailInventory.vue:87` | POST `/api/outlook/status`，1 次 | 单目标事务 |
| 刷新/错误重试/派生摘要重试 | `EmailInventory.vue:63-67` | 库存 GET + summary GET；并行/独立读 | 只读 |
| 清筛、恢复列宽、分页/每页 | `EmailInventory.vue:58,62,分页` | 触发 GET；无写 | 只读 |
| 邮箱单元“查看历史子地址” | `EmailInventory.vue:80` | 导航到 derivations，GET allocations（已有库存摘要用于展示母资源入口） | 只读历史 |

后端批量状态精确证据：`email_pool.py:609-673` 校验最多 5000 项、去重后逐项读取当前行并调用来源专用 release/set 函数；异常仅记录到 `skipped`，没有整体事务或 batch id。批量删除：`email_pool.py:707-769` 同样逐项调用 `delete_butler_email`/`db.delete_*`。单项 Butler 状态在 `core/storage/email/local_imports.py:243-263` 使用独立 transaction；单项删除 `:266-286` 使用独立 transaction、tombstone + enqueue return。

删除安全与回收：只有确认注册成功才拦截本地删除（`local_imports.py:227-240`; `core/storage/email/deletion.py:14-60`）。Butler 退租是异步 service fact worker；只有证明确未使用且无注册/任务/领取事实才允许原租约 return，否则记录 `registration_result_unverified` 等原因（`service_facts.py:321-382`; `deletion.py:63-116`）。这属于**逐目标外部退租**，不能在 UI 上无条件合并为“批量回收”。

### 历史派生邮箱页

`EmailHistory.vue:33-50` 按钮/操作：清筛、复制选中/当前页、恢复列宽、全选/单选、列筛选（子邮箱/母邮箱/来源/状态/关联账号任务/日期范围）、移除筛选、错误重试、分页。复制不调用后端，仅把当前已读行拼接后写剪贴板（`useEmailHistory.ts:18`）；历史接口 GET `/api/email-derivation/allocations`，每次单页请求；状态均只读，服务端明确返回 410“由 Email Butler 管理”（`email_pool.py:334-341`）。

## 代理与流量按钮、处理链

### 代理流量现代页

`ProxyTrafficPage.vue:85-120,133-163` 只有视图切换（current/history/traffic）、筛选弹窗、清筛、恢复列宽、重试、详情、分页和每页大小；`ProxyFilters.vue:62-78` 是搜索/状态/用途/时间范围选项及清除此列/完成。无“测试、检测、回收、恢复、删除、批量操作”按钮。

`useProxyTraffic.ts:91-180,187-310`：一次刷新并行 GET current/history/traffic 页面、summary、pool；筛选/分页按视图单次 GET；30 秒轮询。API：`frontend/src/api/proxy.ts:46-83` → `/api/proxy-traffic/current|history|traffic`、`/summary`、`/api/proxy-pool`。后端 `webui/routes/proxy_traffic.py:34-211` 仅读 `proxy_lease_store.list_page_with_total/list_page`、`browser_traffic.list_summaries_with_total`、`proxy_pool.snapshot`；没有写接口。

代理池库存页 `ProxyPool.vue` 只有库存摘要、国家统计、脱敏表格、分页；无按钮写操作（`ProxyPool.vue:1-175`）。

### 代理测试按钮（配置页，不属于流量页）

`frontend/src/features/config/ConfigActionTools.vue:68` → `configActions.ts:230` POST `/api/proxy-provider/test`。`webui/routes/integrations.py:254-295` 固定 `fetch_candidates(..., count=1)`：提取 1 个候选、由供应适配器检测，成功后立即 `release_proxy(reason="webui_test")`；失败 finally 释放未完成租约。它是**必须逐目标网络检测**且当前产品语义明确为“1 个 IP”，无批量节点。

### 代理后台批量/逐目标能力

- 1024Proxy 供应实现可一次请求窗口候选并用 `ThreadPoolExecutor` 并行验证（`core/proxy/provider.py:698-791`），适合后台批量候选检测；每条候选仍独立出口验证和 lease 状态更新。
- 通用 `core/proxy/supply.fetch_candidates()` 先一次候选窗口请求，再逐候选 `reserve_pending`、出口验证、`activate`，重复候选跳过；502 时按窗口→64→1 回退（`core/proxy/supply.py:71-205`）。这已有“候选窗口批量 + 逐目标网络行为”，不是页面批次。
- 代理池维护 `core/proxy/pool.maintain_once()` 先 `take_check` 逐条复检，再按槽位批量补货；`core/storage/proxy/pool.maintenance()` 在事务内锁定资源，逐行过期/冷却/隔离回收并关闭 anchor（`core/proxy/pool.py:704-812`; `core/storage/proxy/pool.py:433-515`）。回收/复检是后台生命周期动作，无用户按钮或持久“回收批次”。

## 建议按“批量节点”改造的优先级

1. **邮箱状态 bulk / 删除 bulk**：保留一次 HTTP bulk 入口，新增持久 `operation/batch` 节点（请求快照、去重目标、每目标结果、完成数、重试/取消）；服务端用统一事务或分块事务执行本地状态变更，service fact 退租仍按目标异步执行并逐目标记录。
2. **本地兼容导入**：大于小规模时增加导入批次节点、分块事务和进度；Butler 兼容回退必须继续“只恢复已存在租约”，不能把回退改成随机新租。
3. **批量复制**：可保留无状态 bulk 读取；若需要审计/重试，再引入短生命周期读取批次，敏感值仍只在响应/剪贴板边界出现。
4. **代理测试/回收**：页面现状无批量按钮；若未来增加，测试必须保留逐线路出口检测，外层只做批次编排、并发上限、取消、逐目标结果和释放回执，不能把网络检测伪装成单一原子请求。

## 覆盖与未发现项

已覆盖现代邮箱概览/库存/历史/本地导入/Butler 导入全部按钮、选择/筛选/列宽/分页/复制/状态/删除/取消/重试/恢复；邮箱 API 与 `email_pool.py` 全部相关路由；Butler v2 批次、兼容回退、租约绑定、service fact 退租；现代代理流量/库存所有交互、代理 API/路由、供应候选批量验证与后台维护回收；配置页单 IP 代理测试按钮。旧 `webui/static/js/pages/email/page.js` 与 `proxy/traffic.js` 仅负责挂载、导航和可见性桥接，不再自行实现业务按钮（`email/page.js:1-73`; `proxy/traffic.js:1-15`）。

## 通用交互补充与已确认风险

- 所有分页控件完整语义包含：上一页、下一页、数字页码（含首尾）、跳转页码输入/跳转按钮、每页数量选择（`frontend/src/components/ListPagination.vue:34-75`）。邮箱库存和历史分页触发相应 GET；代理记录分页触发单视图 GET；代理池库存分页只切已读快照的内存 `slice`，零网络（`ProxyPool.vue:14-26,160-167`）。页码超出范围可额外补读一次纠正页（邮箱 `useEmailInventory.ts:10-14`; 代理 `useProxyTraffic.ts:91-101`），因此只读刷新不总是严格 1 次。
- 邮箱筛选弹窗的打开/关闭、全部/具体选项、文本/日期/日期范围、清除条件（`EmailColumnFilter.vue:14-34`）均已纳入；打开/关闭零请求，条件变化触发读请求。代理筛选包含全部/列筛选、选项、清除此列、完成（`ProxyFilters.vue:35-78`）；完成只关闭弹窗。
- 邮箱凭证/活动/原因/导入回执和代理池错误说明的展开/收起采用原生 `<details><summary>`，零网络（`frontend/src/components/ListResult.vue:12-15`; `EmailReceipt.vue:6`; `EmailInventory.vue:84-86`; `ProxyPool.vue:92-100,145-151`）。列宽拖动/键盘移动/恢复为本地展示状态，不触发业务 API。
- 代理历史详情/请求流量详情使用已读行 JSON 深拷贝，无详情接口；关闭按钮、Esc、点击遮罩都仅清本地 snapshot（`ProxyRecordsTable.vue:98-100,171-179,204-212`; `useProxyTraffic.ts:181-185,260-263`; `ProxyDetail.vue:47-68`）。当前线路视图没有详情按钮。
- 邮箱批量状态接口逐项捕获异常，能返回部分成功；批量删除接口 `for` 没有逐项 `try`，中途异常可令整个 HTTP 返回失败，但前面邮箱事务已经提交（`email_pool.py:627-667` 对比 `:721-759`）。未来批量节点必须持久逐项结果，防止“响应失败但部分已删除”无法回看。
- 批量状态前端在回执后对**全部提交项**清除勾选，包括服务端 skipped；状态回执固定 `success` tone（`useEmailInventory.ts:32-35`）。这不会消除服务端 skipped 原因，但批量节点应让失败/跳过对象可再次定位与重跑。
- Butler preview 的前端单次 POST 在后端对应 `me + availability` 两次外部读请求并持久 preview（`manual_import_v2.py:70-101`）；新导入每批启动另有一次 preflight `me`（`:286-294`），其后每 item 通常一次 create lease。旧租约恢复通过 `lease_bindings.resolve()` 每邮箱执行 `me + get_lease/list_leases`，列表恢复存在分页（`lease_bindings.py:95-152`; `v2.py:182-217`）。`handoff_selected_batch()` 虽名 batch，内部第二个 `for` 仍逐 item 恢复（`inventory_handoff.py:59-91`），不等价远端批量能力；本次检查未发现 v2 多租约 create/release 批量客户端方法，不声称 Butler 服务端绝对不支持。
- 邮箱“校验”在当前邮箱页仅表现为导入解析/预览和批量标记/删除前的状态保护检查；**未发现独立邮箱连通性校验/批量检查按钮**。API 兼容入口 `as_registered`（旧客户端）仍存在，但新 UI 不传该字段（`email_pool.py:527-545`; `useLocalImport.ts:14`）。

验证边界：本报告依据工作区当前源码，未运行测试/真实浏览器或调用线上服务，因此“路由/循环/事务/按钮存在性”为静态证据，不构成部署状态或实际第三方能力验收。仓库开始审计时已有多处用户未提交修改，审计没有覆盖这些修改或改变提交状态。

## 其它兼容 API 与分类索引

- `/api/email-service-sync`、`/api/email-service-sync/retry` 是服务事实只读/单条重试入口（`email_pool.py:196-227`），当前现代邮箱组件与 `api/email.ts` 没有调用按钮；不把它误记为可见批量重试。
- `/api/domain-pool`、`/status`、`/delete` 是旧域名池兼容 API（`email_pool.py:771-794`），现代邮箱页统一使用 `/api/outlook*` 并按 source 分发；没有额外独立“域名池批量按钮”。
- 本地解析预览的查重已经是 **SQL 集合操作**：`admin_repository.email_pool_existing_emails()` 用 UNION ALL + `email = ANY(%s)` 一次查跨来源/历史冲突（`core/storage/admin_repository.py:1231-1251`），无需把已是集合 SQL 的预览误改成逐条。

| 类别 | 本次识别的操作 | 优先级 |
|---|---|---|
| R：本地 UI/只读 | 打开关闭、筛选、清筛、全选、分页、列宽、详情、刷新、历史复制 | 保留 UI 状态语义，无需强制持久任务 |
| S：单目标写 | 行状态、行删除、同步原意图重试、单 IP 测试 | 单目标操作可作为未来批次节点的一个 target |
| A：数组包装、同步循环 | 状态 bulk、删除 bulk、secret bulk、兼容粘贴 import | 状态/删除最应节点化；复制为无状态读取；import 需考虑批次与分块 |
| B：已有持久批次 | Butler 新租约导入及继续/取消/恢复 | 复用编排思想，避免再包装一层同义批次 |
| N：必须逐目标的网络行为 | 租约 get/create/release/恢复映射、代理出口检测 | 由批次统一准入与收口，网络目标独立执行 |
| L：后台生命周期 | 代理池维护/检查/补货、邮箱异步退租 | 无可见批量按钮；若暴露操作需独立节点及逐目标回执 |
