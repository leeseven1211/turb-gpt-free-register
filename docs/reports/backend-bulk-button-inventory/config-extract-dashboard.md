# 配置、提链与总览按钮只读审计

审计日期：2026-11-24。仓库：`/Users/lihongwei/code/personal/gpt/turb-gpt-free-register`。以下 `路径:行号` 均相对此仓库；以当前工作区文件为准，包含用户已有未提交修改。只新建本报告，未修改业务文件、提交、推送、部署，未请求业务写 API；未运行真实注册、提链、支付、巡检或数据库写入。

## 主要结论

1. **提链「同步原单」是浏览器串行逐条提交**：`ExtractWorkbench.vue:63` → `useExtractWorkbench.ts:91–99`，第 97 行对选中 ID 执行 `for ... await api.action(id,'sync_status')`。每个 ID 单独 POST `/api/extract-workbench/tasks/{id}/actions`，后端对每个既有 Task 创建新 Run，前端只保留最后一个 receipt，没有本次选中集合的批次节点。应优先改为一次提交选择快照、一个批次操作节点统一调度与汇总。
2. **提链「复制支付链接」也是浏览器串行逐条请求**：同一按钮栏 → `useExtractWorkbench.ts:95`，对每行 POST `/api/extract-workbench/tasks/{id}/payment-entry`。该接口仅读取本地已经保存的支付产物，**不查询远端、不触发支付、不创建 Task**。应改成一次批量读取/下载，返回逐项成功、缺失、失败原因；无需强行制造长期后台任务。
3. **新建提链已有批次外壳，但执行仍按账号拆成 N 个 Task/Run**：一次 POST `/batches` → `create_workbench_batch` 保存候选账号快照和 `operation_batches`，后端每 500 个分段，再逐账号 `submit_durable_operation(task_type='extract_link')`。它不是完全没有批次，也不是一个批量节点自身处理全部目标。若未来“批量节点”指统一 selection/Batch/Node/Target 模型，仍需迁移；原有 `submission_id`、冻结配置、workers、资格检查应保留。
4. **取消当前提链批次是一请求、后端同步逐项取消**：前端没有 N 次网络提交；后端读取整批所有任务，再逐 Run 取消并同步账号状态。规模大时适合持久批量控制节点，不能误报成前端逐条请求。
5. **Sub2API 和 C2A「立即巡检」均已有单个持久扫描任务**。Sub2API 扫描后按账号调度刷新、重授权、补传；C2A 刷新 AT 已接统一 bulk selection/batch，上传仍按远端 target 调 `queue_target`。因此扫描入口、修复子流程、真正批量节点需分别评估。
6. **配置保存、开关、刷新、额度/状态查询、导航、复制、展开均不应一概任务化**。当前配置没有独立的「热加载」「修复」「清理」按钮；热加载在保存内部执行，修复由巡检推进，清理是保留期/预算等设置及说明。`navigation.ts` 名为 `actions` 的对象是字段分组，不是业务执行 action。
7. **重跑限制需单独报出**：详情按钮依赖 `safeReplay`，动作函数第 29 行会拒绝远端结果尚未确认的重跑；后端还可能把 retry 转为原单查询。与用户“远端未返回仍可重跑”的诉求存在差异，本轮只登记，未变更支付/提链行为。

## 分类与计数口径

- **L**：本地交互/导航/草稿/剪贴板，无业务 Task。
- **Q**：查询或本地导出，可一次请求读取多条，无需后台任务。
- **S**：一次短写/配置事务/单项测试，不属于多目标批量业务。
- **J**：已有单个后台任务。
- **W**：前端按选择集合逐条发请求，优先改批量入口。
- **A**：前端一次请求，后端接数组或筛选后仍逐项创建/控制；需要进一步统一批次节点。

交叉核对父审计的 `button-source-inventory.json`：配置 32 个源码入口、提链 44 个、总览 11 个，共 87 个源码入口，均覆盖于下表。此数字不是运行时按钮数：模板 v-for、schema secret 清除、国家/多选项、导航项、状态选项、7 个总览脉搏项等会动态展开；共享筛选/分页/结果展开组件与 `<a>` 支付入口另列。加载、禁用、错误重试状态按同一语义按钮记录；原生 confirm 的确认/取消也登记。

## 配置：所有语义按钮与生成式控件

前端简写 C=`frontend/src/features/config/`，API=`frontend/src/api/config.ts`。配置桥接只负责 mount、页面可见性、保存后失效缓存、导航任务；不含业务循环，见 `webui/static/js/pages/config/page.js:14–28`。

| 按钮/交互 | 处理函数、前端证据 | API / 请求次数 | 后端与节点粒度 | 分类与建议 |
|---|---|---|---|---|
| 切换配置分类（移动端） | `ConfigNavigation.vue:46`，expanded 切换 | 0 | 无 | L，保留 |
| 各配置菜单（动态） | `ConfigNavigation.vue:54` → select → `ConfigPage.vue:35` selectMenu | 0；进入 Sentinel/并发工具时触发对应查询 | 导航范围来自 schema 投影及 `navigation.ts:4–42` | L，菜单自身不任务化 |
| 各配置领域标签（动态） | `ConfigPage.vue:76` → selectDomain:36 | 0；工具挂载可能读状态 | 无 | L |
| 各配置子分类标签（动态） | `ConfigPage.vue:79` → selectSection:37 | 0 | 无 | L |
| 搜索配置 | `ConfigNavigation.vue:45` → `ConfigPage.vue:38` search | 0 | 本地检索 schema 字段与定位 | L |
| 重新读取配置 | `ConfigPage.vue:68` → owner.refresh；`useConfigDraft.ts:99` | 1 GET `/api/config` | `webui/routes/config.py:42` → `webui/config_editor.py:199` get_config，字段 schema/当前值 | Q |
| 首次加载失败「重新加载」 | 桥接 `webui/static/js/pages/config/page.js:40` → loadConfig/ensure | 重新 mount；GET schema，自动 types 查询按生命周期执行 | 同上 | Q，启动恢复按钮，不是修复任务 |
| 错误摘要中的字段按钮（动态） | `ConfigPage.vue:69` → owner.navigateField → focusField:46 | 0 | 定位当前字段 | L |
| 撤销修改 | `ConfigPage.vue:103` → discard:47 → 原生确认 → owner.reset | 0 | 仅清除草稿 | L；confirm 确认/取消不写配置 |
| 保存全部配置 | `ConfigPage.vue:103` → save:49 → `useConfigDraft.ts:145` save | 1 POST `/api/config`（updates 对象，多字段一次），成功后 1 GET schema；桥接还刷新 capabilities/邮箱来源 | `routes/config.py:127` → `config_editor.py:404` update_config；校验、数据库持久化、`reload_all`、版本回执；无 operation Task | S；本已批量配置事务，不改长期任务 |
| secret 字段「清除」（对所有 secret 动态生成） | `ConfigField.vue:85` → owner.clearSecret → `useConfigDraft.ts:46` setSecret | 点击 0；保存时随 updates 提交 | 草稿记录 clear，非立即删除凭据 | L → S；不得误当清理任务 |
| bool 开关（所有 schema bool） | `ConfigField.vue:78–81` input → setField | 点击 0；保存时 1 POST | 草稿；包含巡检开关、任务历史自动清理开关等 | L → S；开关不等于执行动作 |
| 普通选项、数字、字符串、多行输入 | `ConfigField.vue:28–50,71–84` | 编辑 0，统一保存 | schema 类型/readonly/editable 约束 | L → S |
| 等待/价格模式切换 | `ConfigField.vue:71–75` → setCompositeMode | 0 | 草稿，`useConfigDraft.ts:72` | L |
| 多选器展开/收起 | `ConfigChoicePicker.vue:20` summary | 0 | 无 | L |
| 多选选项按钮（国家/邮箱来源/随机 OS/节流资源类型/启用平台等所有动态项） | `ConfigChoicePicker.vue:27` → toggle；`ConfigField.vue:16–30,76`；启用平台 `ConfigPage.vue:84` → selectProviders:45 | 0，统一保存 | 只更新草稿，平台集合循环设置各 enabledKey，不发逐项网络请求 | L；不能误报成 W |
| 已选国家 × /多选项移除 | `ConfigChoicePicker.vue:24` → toggle | 0 | 草稿 | L |
| 多选器搜索 | `ConfigChoicePicker.vue:22` v-model query | 0 | 本地 options 过滤 | L |
| 高级提取与检测参数 | `ConfigPage.vue:87` summary | 0 | 展开已有字段 | L |
| 获取团队 | `ConfigActionTools.vue:61` → actions.loadRoxyWorkspaces；`configActions.ts:208` | 1 GET `/api/roxy/workspaces` | `routes/integrations.py:126` → `RoxyBrowserClient.list_workspaces` 同步查询 | Q，外部查询单项 |
| 团队/项目选择 | `ConfigActionTools.vue:60` → selectWorkspace:13 | 0 | 同时设置 workspace/project 草稿 | L |
| 保存选择 | `ConfigActionTools.vue:62` → saveWorkspace:19 → `configActions.ts:219` saveRoxySelection → owner.saveSubset | 1 POST `/api/config` 保存 2 字段，成功后 GET | 同配置原子保存 | S |
| 提取并测试 1 个 IP | `ConfigActionTools.vue:68` → `configActions.ts:231` testProxy | 1 POST `/api/proxy-provider/test` | `routes/integrations.py:254` → source.options、fetch_candidates(count=1)、release_proxy；当前路由同步执行、无 Task | S；明确单 IP 测试，非批量入口。前端可接 receipt 不代表当前后端已入队 |
| 测试连接与权限 | `ConfigActionTools.vue:71` → `configActions.ts:241` testButler | 1 POST `/api/email-butler/test-connection` | `routes/integrations.py:302` → `core/email/email_butler/client.py` test_connection | Q/S 单连接探测，保留 |
| 检查 Sentinel 更新 | `ConfigActionTools.vue:75` → `configActions.ts:274` sentinel(true) | 1 POST `/api/maintenance/sentinel/check`；可见时状态轮询 | `routes/config.py:75` → `core/maintenance/sentinel.py:394` start_check → `submit_durable_operation:401`，一个 `sentinel_maintenance_check`，同缓存活跃请求可复用 | J，已后台化，单资源维护，不需要多目标批次 |
| Sentinel 刷新状态 | `ConfigActionTools.vue:75` → refreshSentinel | 1 GET `/api/maintenance/sentinel` | `routes/config.py:69` → service.status | Q；不下载资源，不新建任务 |
| Sub2API 查看状态 | `ConfigActionTools.vue:80` → refreshSub2Api；`configActions.ts:289` | 1 GET `/api/sub2api/automation` | `routes/integrations.py:56` → jobs.status/monitor.status | Q |
| Sub2API 立即巡检 | `ConfigActionTools.vue:80` → checkSub2Api → sub2api(true) | 1 POST `/api/sub2api/automation/check`，空对象 | `routes/integrations.py:66` → monitor.run_once → `core/integrations/sub2api/monitor.py:346–355`，一个 `sub2api_scan`；内部按账号修复/补传，见后表 | J+A；扫描入口已后台化，修复粒度仍需统一 |
| C2A 查看状态 | `ConfigActionTools.vue:85` → refreshC2a；`configActions.ts:312` | 1 GET `/api/c2a/automation` | `routes/integrations.py:92` → monitor.status | Q |
| C2A 立即巡检 | `ConfigActionTools.vue:86` → checkC2a；`configActions.ts:334` | 1 POST `/api/c2a/automation/check`，空对象 | `routes/integrations.py:104` → `core/integrations/c2a/monitor.py:694`，一个扫描 Task；刷新批次、上传 target 见后表 | J+A；保留扫描节点，后续统一子节点 |
| 查询 Sub2API 分组 | `ConfigSub2ApiGroups.vue:15` → querySub2ApiGroups；`configActions.ts:305` | 1 GET `/api/sub2api/groups` | `routes/integrations.py:41` → `core/integrations/sub2api/client.py` list_configured_groups | Q；已有一次列表读取 |
| Sub2API 分组多选/直接填 ID | `ConfigSub2ApiGroups.vue:14,18–20` → toggle/emit change | 0，统一保存 | `SUB2API_MONITOR_GROUP_IDS` 草稿，空集合表示全部分组 | L → S；不是逐组远端动作 |
| 幻光提链 CDK 查询剩余次数 | `ConfigFieldActions.vue:6,16` → queryHuanguangQuota('extraction')；`configActions.ts:247` | 1 GET `/api/extract-link/huanguang/cdk-quota/extraction` | `routes/integrations.py:224` → service.query_huanguang_saved_cdk_quota | Q；使用已保存 CDK |
| 幻光支付扫码 CDK 查询剩余次数 | `ConfigFieldActions.vue:7,16` → quota('payment') | 1 GET `/api/extract-link/huanguang/cdk-quota/payment` | 同上 | Q |
| 幻光 XXSYUN Key 查询剩余次数 | `ConfigFieldActions.vue:8,16` → queryHuanguangXxsyun；`configActions.ts:258` | 1 POST `/api/extract-link/huanguang/xxsyun-quota` | `routes/integrations.py:170` → service.query_huanguang_xxsyun_quota；只读查询，草稿 key 不保存 | Q；POST 不等于业务任务 |
| 独立支付 XXSYUN 查询积分 | `ConfigFieldActions.vue:9,16` → queryXxsyunBalance；`configActions.ts:268` | 1 POST `/api/extract-link/payments/xxsyun/balance` | `routes/integrations.py:194` → `core/payments/runtime.py` query_xxsyun_balance | Q |
| 并发刷新状态 | `ConfigActionTools.vue:91` → refreshConcurrency；`configActions.ts:345` | 1 GET `/api/operations/concurrency`；首次额外 1 GET `/api/config/concurrency-preview`，独立并行查询 | `routes/config.py:56,46` → get_concurrency_status / get_concurrency_migration_preview | Q；并发视图可见时每 3 秒读取，无 target 循环 |
| 查看附加限制 | `ConfigActionTools.vue:91` → refreshConcurrency({details:true}) | GET `/api/operations/concurrency?details=1`，首次可能额外 preview | 同上 | Q |
| 填入迁移建议 | `ConfigActionTools.vue:94` → applyConcurrencyPreview；`configActions.ts:353` | 0 | 将预览 proposed_values 填草稿，仅未修改合法并发字段 | L；后续保存才生效 |
| 重试迁移预览 | `ConfigActionTools.vue:94` → loadConcurrencyPreview；`configActions.ts:342` | 1 GET `/api/config/concurrency-preview` | `routes/config.py:46` | Q |
| 并发字段/状态行「定位任务」（动态） | `ConfigField.vue:91`、`ConfigActionTools.vue:95` → locateConcurrencyTasks；`configActions.ts:365` | 当前动作 0；目标页自行查询 | 注册字段导航注册任务页；其他进入任务中心并设 type 筛选，桥接 page.js:21–27 | L，不启动任务 |
| 业务附加限制与计量说明 | `ConfigActionTools.vue:97` summary | 0 | 本地说明展开 | L |

### 配置 schema action、维护/修复/清理覆盖说明

- `config/schema.py`、`webui/config_editor.py` 以及前端 `contracts.ts:13–55`、`ConfigField.vue` 共同核对：没有通用 `type='action'/'button'` 或动态 endpoint 执行器。schema 生成的是各字段输入、bool 开关、options/country_codes 选项、secret 清除及并发字段定位；全部适用上表生成规则。四个字段级查询按钮由 `ConfigFieldActions.vue:5–10` 明确映射，七种工具由 `ConfigActionTools.vue:6` 明确列举。`navigation.ts:70` 的 `actions` 是配置字段分组定义。
- 保存时 `webui/config_editor.py:446–487` 在一个持久化事务里验证更新、写配置、`config_package.reload_all():481` 并发布版本；**没有额外「热加载」按钮**。Worker 应用状态通过保存回执展示，不能把 Web 已热加载视为 Worker 已应用。
- `config/schema.py:818–826` 的认证上下文保留、任务历史保留、清理归档保留及 `:883` 抓包保留属于配置；`ConfigActionTools.vue:97` 提及清理占用属于说明，均不是立即清理命令。配置页未发现独立「修复」按钮；「立即巡检」间接推动修复，粒度如下。
- 已废弃 `/api/mailcode/catalog`、`/api/cloudmail/gen-token`、`/api/cloudmail/domains`（`routes/config.py:96,117,122`）及 `/api/icloud-hme/test`（`routes/integrations.py:297`）返回 410，当前配置组件和桥接无对应按钮；不计入活跃按钮。
- `/api/config/snapshot`、组合 `/api/extract-link/huanguang/cdk-quota` 同样没有当前配置按钮直接调用；不把兼容 API 虚构为界面操作。

### 巡检之后的真实粒度

| 扫描入口 | 后端行为证据 | 当前粒度 | 后续批量建议 |
|---|---|---|---|
| Sub2API | `core/integrations/sub2api/monitor.py:346` 创建一个 scan；`:395–435` 远端邮箱映射并按账号 _process；`:147` queue_sync、`:177–195` enqueue_oauth，token refresh 分支见 _process；`core/integrations/sub2api/jobs.py:150–174` 提交补传任务 | 扫描 J；按账号/凭证持久修复，扫描结果不是一组统一 bulk target 节点 | 巡检保留单节点；把一轮发现的目标冻结为批量节点，按阶段汇总刷新/授权/上传，避免只能分别追踪子任务 |
| C2A | `core/integrations/c2a/monitor.py:694` 扫描；`:205–249` _submit_refresh 创建 bulk selection/batch，操作 account_refresh；`:464–485` _submit_uploads 逐 target 调 manual_sync.queue_target | 刷新 AT 已统一批次；上传按单 target Task，扫描回执附 child_tasks/batch refs | 复用已存在 AT bulk 节点；上传集合也接统一批量上传节点，保持远端单账号 API 适配在节点执行端 |
| Sentinel | `core/maintenance/sentinel.py:394–420` 受理；`:91–131` handler | 单缓存资源 J，检查可复用活跃请求 | 现粒度合理；不为单资源检查增加多账号批次 |

## 提链：所有业务、复制、筛选、分页、弹窗按钮

前端简写 E=`frontend/src/features/extract/`，API=`frontend/src/api/extract.ts`，后端路由 R=`webui/routes/extract_workbench.py`，服务 S=`core/extract_link/service.py`。桥接 `webui/static/js/pages/extract_link/page.js:1–36` 仅转发 Vue owner，未另做选择循环。

| 按钮/交互 | 前端处理函数与证据 | API / 浏览器请求数 | 后端、节点/循环 | 分类与建议 |
|---|---|---|---|---|
| 工作台刷新 / 任务读取失败重试 | `ExtractWorkbench.vue:56,77` → refresh:43 → load:38；`useExtractWorkbench.ts:83` | tasks GET 1 次，同时 summary/config/batches 或 batch detail 辅助查询（缓存/可见性约束，非按行） | R:430,562,277,324,344；S:2646 等 → workbench_queries → jobs.list_workbench_page | Q；保留页面读生命周期 |
| 导出当前筛选 | `ExtractWorkbench.vue:57` → `useExtractWorkbench.ts:107` exportRows(true) | 1 GET `/api/extract-workbench/export?...`，API:26 | R:600，后端 page_size=100 循环读，最多 5000，生成 CSV，无 Task | Q；一次导出已成立，若扩大量再考虑导出任务 |
| 新建批次（打开） | `ExtractWorkbench.vue:58` → openCreate:43 → batch.open + preview | GET config 至多 1 次（可复用已读），GET candidates 1 次 | R:277,288；S:2661 → workbench_queries:470 → batches.candidate_accounts | Q/L；尚未创建提链任务 |
| 选中栏：同步原单 | `ExtractWorkbench.vue:63` → `useExtractWorkbench.ts:91–99`，特别 :97 for-await | **N 个 POST `/api/extract-workbench/tasks/{id}/actions`**，API:21；随后刷新列表辅助查询 | R:680–709 → S:2920–3032 → operation.retry_runtime_task:3011；每个既有 Task 新 Run，选中集合无独立批次 | **W，优先统一一次 bulk 提交 + 选择快照 + 同步节点 + target 结果** |
| 选中栏：复制支付链接 | 同按钮栏 → `useExtractWorkbench.ts:95` for-await paymentEntry | **最多 N 个 POST `/api/extract-workbench/tasks/{id}/payment-entry`**，API:22，最后一次剪贴板写入 | R:711–729 → S:2884–2913；逐条读本地 provider_job.public_state / legacy link，0 Task/Run | **W/Q，改一次批量产物读取；按每项返回缺失/失败代码，无需持久长任务** |
| 选中栏：导出选中 | `ExtractWorkbench.vue:63` → exportRows(false):107 → selectedCsv | 0，浏览器 Blob 下载 | 只导出当前 items 中 selected 行，不另读详情或全库 | L/Q，保留本地批量导出 |
| 选中栏：清除选择 | `ExtractWorkbench.vue:63` → bulkAction('clear'):92 | 0 | Set.clear | L |
| 选择本页 / 各行复选框 | `ExtractWorkbench.vue:79,82` → all/toggle:43 | 0 | 只保存本页选择；新列表返回时 `useExtractWorkbench.ts:86` 移除不在当前页 ID | L；未来批量节点要冻结服务端集合，当前不支持跨页保留 |
| 清除全部筛选 | `ExtractWorkbench.vue:65` → resetFilters:12 → switchBatch | 一轮列表及辅助查询 | 仅查询范围变化 | Q/L |
| 各筛选标签 × | `ExtractWorkbench.vue:63` → ListFilterSummary @remove → changeFilter:11 | 一轮列表查询；batch 走 switchBatch | 无业务任务 | Q/L |
| 账号/平台/模式/状态/批次筛选打开与关闭；移动端筛选 | `ExtractWorkbench.vue:66,73,80–81` → ExtractFilters →共享 FilterPopover | 开关本身 0 | 展示本地 options | L |
| 选择筛选列（移动端 radio） | `ExtractFilters.vue:23` → setSelected:11 | 0 | 本地切换编辑列 | L |
| 账号搜索、各平台/模式/状态/批次选项 | `ExtractFilters.vue:25–29` → change → changeFilter:11 / switchBatch:39 | 一轮 tasks 查询和辅助查询；批次选择不逐 task 提交 | R 查询入口 | Q；动态选项均覆盖 |
| 清除此列 | `ExtractFilters.vue:34` → change('') | 同上 | 只读 | Q/L |
| 筛选完成 / 右上角关闭 / Escape / 外部关闭 | `ExtractFilters.vue:34`；共享 `FilterPopover.vue:9–29` | 0 | Popover 状态 | L |
| 批次列表读取失败重试 | `ExtractWorkbench.vue:69` → changeBatchPage:16 → loadBatchPage；useExtractWorkbench:58 | 1 GET `/batches?page=...&page_size=20` | R:324 | Q |
| 批次分页上一页/页码/下一页/跳转 | `ExtractWorkbench.vue:71` → ListPagination → changeBatchPage | 1 GET batches，0 业务 Task | R:324 | Q；共享组件每页固定 20 |
| 任务分页上一页/页码/下一页/跳转/每页条数 | `ExtractWorkbench.vue:88` → changePage/changeSize:13–14 | 一轮列表与辅助查询 | R:430 | Q；每页选项默认 20/50/100 |
| 取消当前批次 | `ExtractWorkbench.vue:74` → `useExtractWorkbench.ts:101–105` 原生 confirm → api.cancel | 1 POST `/api/extract-workbench/batches/{id}/cancel`，API:19 | R:359–377 → S:2750–2836，分页读整批，逐 Run request_run_cancel:2804，再同步账号状态；无独立取消 Task | **A，适合持久批量控制节点**；作用于整批排队项，不受当前表格分页/筛选限制 |
| 取消批次确认/取消 | 同上 confirm | 确认才 POST；取消 0 | 无额外节点 | L |
| 各行详情 | `ExtractWorkbench.vue:85` → `useExtractArtifacts.ts:11` openDetail | 1 GET `/tasks/{id}`；有支付产物时额外 POST payment-entry 1 次 | R:653 → S:2916 → queries:539 读详情/历史/事件；额外读取产物仍只读 | Q |
| 各行支付入口 / 详情读取支付入口 | `ExtractWorkbench.vue:85,112` → paymentEntry:28 → artifacts.showPaymentEntry:22 | 1 POST `/tasks/{id}/payment-entry` | R:711 → S:2884，本地读，无远端请求 | Q；按钮名不能误判为发起支付 |
| 行状态详情展开/收起 | `ExtractWorkbench.vue:84` → ListResult 的 details/summary | 0 | 已读消息/错误/进度展示 | L |
| 新建弹窗关闭 / 取消 / Escape / 点击遮罩外部 | `ExtractWorkbench.vue:90–91,105` → closeCreate:41 → batch.close | 0，取消未完成候选读取 | 本地 | L；未提交批次不需要取消后台 |
| 新建筛选/数量输入（来源/日期/状态/优惠/搜索） | `ExtractWorkbench.vue:93–98` → batch.invalidate；`useExtractBatch.ts:10` | 0；显式刷新匹配数量时才查询 | 废弃旧预览 | L |
| 平台/模式/链接类型/并发/标题输入 | `ExtractWorkbench.vue:99–102`，providerChanged:36 | 0 | 保存提交参数草稿 | L；三模式含只提链、人工扫码、自动支付 |
| 刷新匹配数量 | `ExtractWorkbench.vue:105` → `useExtractBatch.ts:15–18` preview | 1 GET `/candidates?...&limit=...`，API:18 | R:288 → S:2661 → batches.candidate_accounts；返回总数、计划数量、前 20 预览 | Q |
| 创建并运行 | `ExtractWorkbench.vue:105` → create:43 → `useExtractBatch.ts:19–26` submit | **1 POST `/api/extract-workbench/batches`**，API:19；成功后刷新并切批次 | R:379–428 → S:2665–2739 保存 runtime batch，分段 500，再 S:2572 逐账号 submit_durable_operation:2606；每账号 1 Task/Run | **A，已有批次外壳，后续接真正批量节点**；limit 1–5000、workers 1–50、submission_id 幂等、提交时冻结候选 |
| 自动支付批次确认/取消 | `useExtractBatch.ts:22` 原生 confirm | 确认进入上项提交；取消 0 | 同一批次参数中的 mode=auto_payment | L → A；不得把确认按钮计为独立支付 API |
| 任务详情关闭 / Escape / 遮罩 | `ExtractWorkbench.vue:107–108` → artifacts.closeDetail:39 | 0 | 取消只读 fetch、清除 drawer，不取消后台业务 | L |
| 详情同步状态 | `ExtractWorkbench.vue:112` → artifacts.taskAction(id,'sync_status'):27–32 | 1 POST `/tasks/{id}/actions`；详情已读时无需额外 detail，桥接隐藏调用缺详情时先 GET | R:680 → S:2920 → retry_runtime_task:3011，单 task 新 run | J 单条入口；与多选同步共用执行适配 |
| 详情重跑 | 同行 → taskAction(id,'retry') | 1 POST actions，前端先判 active/safeReplay | S:2955–2972 有原单时可能转 sync_status，否则 create；S:3002 claim；单 task 新 run | J 单条入口；用户要求可重跑与 safeReplay 限制另行列为设计议题 |
| 查询自动支付 | 同行，mode=auto_payment 且未 paid 才出现 → taskAction('auto_payment') | confirm 后 1 POST actions；不是批量支付请求 | S:2944–2947 独立支付分支，或 :2973–2997 原单 reference + mode 校验后 sync_status | J，查询/继续已有原单，单 task 新 run；UI/文案勿当创建新付款 |
| 查询自动支付确认/取消 | `useExtractArtifacts.ts:30` | 确认才提交；取消 0 | 同上 | L |
| 复制邮箱 | `ExtractWorkbench.vue:112` → artifacts.copy(id,'email'):35 | 已读详情 0；缺详情时 GET 1 | 本地详情 email → clipboard | L/Q |
| 复制 AT | 同行 → artifacts.copy(id,'at'):35 | 1 GET `/api/accounts/{account_id}/secret?field=access_token`，必要时先 GET detail；API:24 | 账号 secret 读取入口，无提链 Task | Q，按需读取，单项复制 |
| 复制提链链接 | 同行 → artifacts.showLink(id,'extract'):34 | 1 POST `/tasks/{id}/links`，API:23 | R:758 → S:2839，读 provider job/历史本地链接，0 Task | Q |
| 节点 A 重新读取 | `ExtractWorkbench.vue:118` → artifacts.loadNodeA:16 | 1 POST payment-entry | 同本地产物读取 | Q；“节点 A”此处是展示区名称，不是统一 bulk workflow 节点 |
| 节点 A 打开支付页面 / 打开支付入口（链接） | `ExtractWorkbench.vue:118` 两个动态 anchor | 0 Turb API，浏览器打开保存 URL | 外部导航 | L；后续外部付款不在本次静态审计内 |
| 节点 A 复制支付页面 / 复制支付入口 | 同行 → artifacts.copyNodeA:37 | 0 | 复制已经加载的字符串 | L |
| 节点 A 复制二维码 | 同行 → copyNodeA('qr_data') | 0 | clipboard | L |
| 平台原文 / 历史运行 / 完整任务记录展开 | `ExtractWorkbench.vue:119,121–122` details/summary | 0 | 已加载数据 | L |
| 支付弹窗关闭 / Escape / 遮罩 | `ExtractWorkbench.vue:125–126` → closePayment:40 | 0 | 本地关闭、不取消支付任务 | L |
| 支付弹窗重新读取 | `ExtractWorkbench.vue:127` → paymentEntry | 1 POST payment-entry | 本地产物读取 | Q |
| 支付弹窗支付页面/支付入口「打开」（两处链接） | `ExtractWorkbench.vue:131` anchor | 0 Turb API | 打开保存 URL | L |
| 支付弹窗支付页面/支付入口「复制」（两处动态按钮） | 同行 → artifacts.copyPayment:36 | 0 | 已读值 → clipboard | L |
| 支付弹窗复制二维码内容 | `ExtractWorkbench.vue:133` → copyPayment('qr_data') | 0 | clipboard | L |
| 提链统计近 7 / 30 / 90 天 | `ExtractStats.vue:28` → days + stats.load | 各 1 GET `/api/extract-workbench/analytics?days=...` | R:546 → `core/extract_link/workbench_analytics.py:7` → `core/storage/extract_link/analytics.py:55` 聚合 | Q，三按钮分别覆盖 |
| 提链统计平台选择 | `ExtractStats.vue:29` @change stats.load | 1 GET analytics（provider_id） | 同上 | Q |
| 提链统计刷新 / 错误重试 | `ExtractStats.vue:30,33` → `useExtractStats.ts:10` load | 各 1 GET analytics，abort 旧读取 | 同上 | Q |
| 查看每日明细数据 | `ExtractStats.vue:41` summary | 0 | 已加载统计表展开 | L |

### 提链 API 与批次存储核对

- 创建批次的持久候选冻结：`core/storage/extract_link/batches.py:250–281`，在同一事务锁 submission_id，保存 `submission_account_ids`、filters、workers、provider/mode/payment_source；然后服务按账号创建并关联 Task。`finish_submission:418–442` 更新提交统计并按实际子任务推导批次结果。因此不能把一次 HTTP 或 batch_id 当作“单批量执行节点”的充分证据。
- 列表/汇总/详情：`core/extract_link/workbench_queries.py:422–443,470–481,539` 分别转 `core/storage/extract_link/jobs.py:985,1065,1121` 与 `batches.candidate_accounts:152`。这些是只读投影，无 per-row 写操作。
- 当前 `frontend/src/api/extract.ts` 没有批量 actions、批量 payment-entry API。后端 `POST /api/extract-workbench/tasks`（R:492）接受 account_ids 数组，但现代工作台创建使用 `/batches`，不是这个旧数组 API；它也调用 S:2548 的逐账号持久提交，不能据其存在称多选同步已批量化。
- `/tasks/{id}/payment-query-credential`（R:731）是原卡查询凭据恢复 API，当前 Vue 及桥接未暴露按钮；不计为活跃按钮。
- `useExtractArtifacts.ts:28` 支持 `manual_payment`，桥接可调用它，但当前 Vue 无此独立按钮；`showLink(kind='payment')` 也属于程序入口兼容，现代界面采用支付入口弹窗。表中对当前可见入口与程序可调用入口作此区分。
- `safeReplay` 的限制位于 `frontend/src/features/extract/presentation.ts`，在按钮 disabled 与 `useExtractArtifacts.ts:29` 双重生效；本报告没有据一般批量化诉求修改其行为。

## 总览：所有入口（均为导航或只读）

| 按钮 | 函数/源码 | API、后端与数量 | 分类/建议 |
|---|---|---|---|
| 刷新 | `DashboardPage.vue:111` → owner.load；`useDashboard.ts:50` | 并行最多 3 个 GET：`/api/dashboard`、`/api/capabilities`、`/api/extract-workbench/summary`；capabilities 可加入共享请求，不按卡片/账号循环 | Q，不改后台任务 |
| 加载失败重试 | `DashboardPage.vue:120` → owner.load | 同上 | Q |
| 邮箱异常「检查邮箱池」 | `DashboardPage.vue:81,127` → go('outlook') | 该动作 0，目标页自行读 | L |
| 邮箱耗尽「添加邮箱库存」 | `DashboardPage.vue:82,127` → go('outlook') | 该动作 0，不直接导入/创建邮箱 | L |
| 脉搏：邮箱 | `DashboardPage.vue:70,138` → go('outlook') | 0 | L |
| 脉搏：账号 | `DashboardPage.vue:71,138` → go('accounts') | 0 | L |
| 脉搏：Codex | `DashboardPage.vue:72,138` → go('codex') | 0 | L |
| 脉搏：套餐 | `DashboardPage.vue:73,138` → go('accounts') | 0，不发套餐检测 | L |
| 脉搏：提炼 | `DashboardPage.vue:74,138` → go('extract-workbench') | 0，不启动提链 | L |
| 脉搏：代理 | `DashboardPage.vue:75,138` → go('proxy-traffic') | 0，不创建代理租约 | L |
| 脉搏：任务 | `DashboardPage.vue:76,138` → go('tasks') | 0，不提交任务 | L |
| 邮箱池卡片「管理」 | `DashboardPage.vue:151` → go('outlook') | 0 | L |
| 账号卡片「管理」 | `DashboardPage.vue:179` → go('accounts') | 0 | L |
| Codex 卡片「查看」 | `DashboardPage.vue:199` → go('codex') | 0 | L |
| 提炼卡片「工作台」 | `DashboardPage.vue:221` → go('extract-workbench') | 0 | L |
| 套餐卡片「账号」 | `DashboardPage.vue:242` → go('accounts') | 0 | L |
| 代理卡片「查看」 | `DashboardPage.vue:262` → go('proxy-traffic') | 0 | L |
| 任务卡片「任务中心」 | `DashboardPage.vue:281` → go('tasks') | 0 | L |

总览 API 链：`frontend/src/api/dashboard.ts:40–49` → `webui/routes/dashboard.py:101–164`。dashboard 路由调用 `core/storage/admin_repository.py:1547` 聚合账号/任务/Codex、邮箱供给展示与活跃代理租约；提链汇总由上述 extract summary 聚合提供。`useDashboard.ts:5,43–85` 每 20 秒可见时刷新、合并 inflight、Abort 旧读取。桥接 `webui/static/js/pages/dashboard/page.js:1–24` 调 activateTab，未增加业务写动作。

旧 `openOverviewCustomizer`、`resetOverviewLayout` 桥接仍存在，但 `DashboardPage.vue:95–98` 为兼容空操作，现代总览没有自定义/重置按钮；没有遗漏业务动作。

## 后续批量化范围建议（本轮未实施）

| 优先级 | 具体范围 | 建议粒度 | 需要保留的事实/边界 |
|---|---|---|---|
| P1 | 提链多选同步原单 | 1 selection 快照 + 1 批次同步节点 + N targets；前端只提交一次 | 每 target 原 task/run/provider 原单引用、独立失败分类、允许重跑策略按用户要求统一讨论 |
| P1 | 提链多选复制支付链接 | 一次批量本地产物读取，浏览器一次复制 | 不触发远端查询/支付；返回目标级缺失/错误，避免当前 catch 统一 skipped |
| P2 | 创建提链批次 | 将现 runtime_batch + N Task 映射到统一批量节点模型 | submission_id 幂等、候选冻结、配置冻结、workers、账号资格与资源占用检查、每注册/提链链路隔离 |
| P2 | 提链批次取消 | 一次持久批量控制节点，整批按 target 汇总 | 只取消尚未开始者，保留运行中/完成者，按现行 version 同步账号状态，可重试补齐 |
| P2 | Sub2API 巡检修复集合 | 扫描节点之后批次化刷新/重授权/补传阶段 | 扫描本身已 J；逐账号原地 API 调用可留在节点执行端，避免制造 N 个独立顶级业务任务 |
| P2 | C2A 巡检上传集合 | 复用已存在 AT bulk，新增上传阶段批量节点 | 不重复重建已存在 selection；保持 expected_backend、remote target、幂等 key |
| 保留 | 保存配置、Roxy 选择、代理单 IP 测试、Butler 探测、Sentinel 单资源检查、所有额度/状态/统计/列表/导出/本地交互 | 对应 S/J/Q/L | 不因按钮存在就改成长任务；只对真实批量业务与大规模控制做批次节点 |

## 覆盖与验证记录

- 已读取三功能目录所有 Vue 入口及 composable/action，三个 API 文件、三个桥接（提链另含 stats 桥接）、四路由文件和 owning service/storage。
- AST 87 个源码入口逐项交叉核对；额外覆盖 v-for 展开、schema bool/secret/options 控件、共享分页/筛选/summary、支付外链和原生 confirm。
- 源码层面已区分：前端 N 请求、前端一次请求后端逐项、已有持久 Task、已存在 bulk 子阶段、只读批量获取、本地交互。没有把“单 HTTP”“返回数组”“含 batch_id”“页面显示节点 A”直接等同真正的批量节点。
- 本报告为静态只读审计，未运行测试或浏览器真实写流程；不声称运行时每个按钮都已点击验收，也不声称线上版本与当前工作区一致。
