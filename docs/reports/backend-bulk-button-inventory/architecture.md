# 全站按钮审计：公共批量架构与遗漏补充

审计日期：2026-11-24。静态阅读当前工作区；已有未提交修改被保留。本报告不代表线上部署版本，不修改业务、不连接生产数据库、不运行真实流程。路径均相对仓库 `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register`。

## 一、用于后续统一讨论的“真批量”分层标准

“批量按钮”至少应分别标记以下四层，不能因为 URL 带 bulk、界面一次点击，便认定已经完成全部批量化。

| 层次 | 判定口径 | 不能混淆的实现 |
|---|---|---|
| 前端与 API | 一次用户意图提交完整 ID 集合或查询描述；确认前固定选择；一个幂等请求身份；前端不循环调用单条写接口 | `Promise.all(ids.map(singleAction))` 仍是 N 个单条请求；分页取数、结果渲染循环不属于这个问题 |
| 批量控制节点 | 后端拥有本次操作的固定目标集合、动作与参数/配置版本、受理状态、结果清单；异步执行需要持久化进度、恢复、控制和重跑 | 一个 batch ID 加 N 次旧 submit，只能证明分组存在，不能证明集合执行或集合存储；目标/Run 也不是批量节点本身 |
| 集合存储与调度 | 以集合查询、集合资格判定、分块集合创建/更新/控制为主体，SQL/事务数量按块增长；允许内存映射目标和生成结果清单 | 同一事务内循环 N 次 UPDATE、逐条调用有独立事务的领域服务，仍属逐条处理；“只有一个事务”不等于集合 SQL |
| 外部目标执行 | 平台没有多目标 API 时，每账号认证、发信、浏览器环境或远端请求仍须按目标执行；在统一批量控制和并发配额下调度 | 不能为了“没有循环”把不同账号身份合并成一个外部会话；外部逐目标执行不应成为前面三层逐条入队/查询的理由 |

这里是审计分类，不是已经确认的改造方案。同步动作也可拥有轻量的“批量节点/批量回执”语义，但不必因统一节点概念，为每个复制、备注或归档目标建立持久 Task/Run。是否需要落库恢复，应按耗时、外部副作用与结果恢复要求决定。

## 二、当前已有平台的真实边界

现有 `core/bulk_operations` 是持久批量平台，已具有名单、批次、轮次、目标、Run 归属、控制命令和投影。结构来自 `core/storage/operations/bulk_schema.py:13,42,57,79,105,134,153,169`。

- `operation_selections`：保存请求、查询/来源、动作、参数、配置修订、固定名单状态和租约。
- `operation_selection_targets`：固定目标、显示/匹配证据与基线，保存 canonical target；schema 虽允许 account/credential（45 行），当前名单生成 SQL 固定插入 account（`bulk_selections.py:255-258`）。
- `operation_batch_controls`：一个批次的动作、配置、并发、控制版本、计数与暂停状态。
- `operation_batch_rounds`：初次执行/人工重跑轮次；其作用是执行轮次，不等于独立工作流节点。
- `operation_batch_target_rounds`、`operation_batch_run_links`：各目标在本轮的状态及 owned root/child/continuation Run 的精确归属。
- `operation_batch_control_commands`、`operation_projection_outbox`：可恢复控制与结果投影。

**未发现独立 node 实体或通用 DAG/多操作节点模型。** 当前 batch 固定一个 `action_key`，可把它理解为一个动作的控制边界，但不能宣称通用“批量节点架构”已经存在。组合补全会传播子 Run 归属，属于账号执行链，不代表任意跨领域节点图。

公开目录只支持 6 类账号操作：`plan_check`、`token_refresh`、`password_setup`、`twofa_setup`、`codex_retry`、`account_completion`（`core/bulk_operations/catalog.py:8-15`）；catalog 的 target_kind 固定 account（185 行）。显式 ID 上限 10,000、固定目标上限 100,000、并发上限 128（192-193 行）。当前不能直接宣称已经覆盖普通查活、邮箱变更、C2A、Sub2API、凭证资产、邮箱库存、注册、提链和同步本地写入。

前端创建不是“一次 HTTP 完成所有阶段”：`useBulkCreate.ts:148` 先提交 selection，准备完成后 `:130-131` 再提交 batch；这是固定集合的两阶段受理，不是对 N 个目标发 N 个请求。详情重跑提交一个 round 并携带目标集合/结果条件（`useBulkDetail.ts:144`），控制提交一个 batch/round scope（151 行）。

### 已有集合处理可复用能力

| 能力 | 证据 | 静态结论 |
|---|---|---|
| 固定名单 | `bulk_selections.py:253-263` | `INSERT … SELECT` 一次固定匹配集合；非特殊路径每 5,000 个批量读预检，使用 jsonb_array_elements 集合回写（277-300 行） |
| 新轮固定成员 | `bulk_batches.py:410-425` | 集合插入本轮成员，并保留原 canonical target、源轮次与源 Run |
| 分块物化 | `bulk_batches.py:553-598` | 每块最多 100 目标，`INSERT … SELECT` 与游标推进 |
| 集合预检 | `adapters.py:56-95` | 批量读账号、活跃 Run、注册占用；后面的 Python 循环主要生成判定，不是逐账号查库 |
| 新目标集合建任务 | `adapters.py:268-327`、`runtime.py:864-923` | 集合 claim/patch 账号阶段；jsonb_to_recordset 集合创建 Task、Run、queued event，并集合关联 last_run_id |
| 集合归属回写 | `bulk_runtime.py:337-397` | 批量保存回执、归属关系和目标状态 |
| 结果投影 | `bulk_projection.py:223-247` | 目标、canonical root、审计事件集合写；258-265 行仍逐 round 更新汇总，规模按受影响轮次数增长 |
| 旧列表查批次归属 | `execution.py:19-49` | 当前页 Run ID 一次集合关联；无须每条查询完整批次历史 |
| 集合准入观察 | `task_gateway.py:1992-2016` | 多 Run 观察时一次读取受管 batch 配额；真实 Run 的执行仍逐目标进入执行器 |

### 平台内部尚存逐条路径

| 优先级 | 位置 | 当前行为与影响 |
|---|---|---|
| 高 | `core/bulk_operations/adapters.py:196-264` | 新目标走 `_submit_fresh`；带 source_task_id 的历史重跑目标仍逐个进入 savepoint、claim stage、`retry_runtime_task`、`patch_row`。已同外层块事务，但 SQL 数量随目标数增长 |
| 高 | `core/storage/operations/bulk_control.py:207-227` | 每目标先查 owned Run，再逐 Run 调 `cancel_run`，没有 Run 时逐目标 UPDATE，最后逐目标 `record_managed_change`；单块上限 100（204 行）限定了一次影响范围，但没有变成集合控制 |
| 中 | `core/storage/operations/bulk_projection.py:258-265` | 目标写已集合化，round 汇总仍每轮一次 UPDATE；碎轮次会放大这里的工作 |
| 中 | `core/bulk_operations/execution.py:181-204` 附近的 `repair_pending_handoffs` | 补登记 handoff 逐父 Run 调依赖注册；属于启动/维护修复而非按钮主提交，不应混计为前端批量失败，但可能影响大规模恢复 |

上表仅描述静态结构，未测量当前线上耗时。平台的 fencing、精确 Run 归属、账号锁顺序、外部回执及取消收尾语义均是必要边界，后续集合化不可省略。

## 三、任务中心是最明确的公共薄包装路径

`webui/routes/operations.py:189-218` 的 `/api/operations/bulk` 一次接收至多 100 个 task_id，支持 retry/cancel/terminate/delete；当前实现没有创建一个批量控制节点。

1. `action_service.py:209-210` 每 task_id 先 `_get_operation_action_task`。
2. `:225-231` 再调用单条 `perform_operation_action`，其 `:48` 再读同一 task。
3. retry 对 managed task 调 `retry_managed_task`（`:67`），request key 还拼入 task_id。
4. `bulk_operations/service.py:245-247` 的 selection.target_ids 固定是只有一个 canonical_target_id 的数组，再 `create_round`。

因此同一个原批次选 N 个 managed task 并均被接受，当前会创建 N 个单目标新轮次。它不是“同批一次重跑一个目标集合”；跨原批次时也分别走各原批次。这会增加轮次、名单、协调与汇总负担。与之对照，批量详情页原本已经能一次携带多个 target_ids 建立一个 round（`useBulkDetail.ts:144`）。

后续口径宜按原 batch、动作/参数等不可混合边界分组讨论一次新轮承载一个目标集合；不应机械地给每条 task 再包一个 batch/node。此处只是问题归因和讨论边界，不是获准实施的设计。

删除路径有区别：`store.py:757-771` 集合查询并锁定所选任务，但 `:772-795` 仍逐条 UPDATE 隐藏状态，同一事务也不是集合写。它是同步本地元数据更新，适合维持同步批量语义、集合校验/更新和完整跳过清单；没有证据要求每个删除都建立执行 Run。

`task_gateway.submit_durable_operation` 本身是单目标网关：`task_gateway.py:1329-1346` 只调用一次 `create_runtime_task`。把它放进 for 循环并传同一个 batch_id 不会自动成为集合提交。已有 `create_runtime_tasks_many` 的集合入口目前限定必须带 bulk_target_round_id（`runtime.py:871-872`），不是任意领域均可无适配直接调用的通用接口。

## 四、哪些动作需要控制节点，哪些适合轻量同步批量

| 动作类别 | 适用的批量语义 | 后续讨论时必须保留的领域边界 |
|---|---|---|
| 账号认证、补全、刷新、邮箱变更、外部系统同步等 | 固定集合、持久批量控制/回执、分块集合入队、受控逐目标远端执行 | 身份、账号锁、配置快照、幂等键、远端回执、外部结果与本地保存分别记录 |
| 注册批量创建/重跑 | 需要批次目标与恢复，但不得凭当前全站审计直接更换注册执行策略 | 所有注册驱动主流程受保护；先提详细方案并获明确确认 |
| 提链与支付 | 具有独立批次和订单生命周期，不能只套 account 操作目录 | provider、原单、支付/到账、额度及恢复语义独立；新旧平台是否融合需单独方案 |
| 备注、归档、状态标记、本地移除、隐藏历史 | 一次集合请求、集合读写、准确逐目标结果；可用轻量批量节点/回执 | 删除、归档、释放邮箱租约是不同业务；不为了统一而改变安全/占用规则 |
| 复制/导出、下载本地 session/凭证 | 集合查询后统一生成剪贴板文本/文件/manifest；大文件或远程下载才考虑持久后台准备 | 每项无数据、读取失败和导出失败需清晰分类；无需为纯读取复制建立 N 个 Run |
| 筛选、分页、列宽、展开/收起、刷新、关闭、导航、登录 | 界面/会话行为；无需批量执行节点 | 这类控件应纳入“全站按钮”清单，但不要当作业务批量改造缺口 |

## 五、公开 API 的 bulk 命名不能作为完成度依据

除原生 `/api/bulk/selections`、`/batches`、`/batches/:id/rounds`、`/control`（`webui/routes/bulk.py:217-292`）外，以下是静态定位到的跨模块批量入口族，需与各页面审计按调用链核对；此表不替代各领域明细。

| 领域 | 路由文件与代表位置 | API 族 |
|---|---|---|
| 账号 | `webui/routes/accounts.py:256-1733` | registration-retry、setup、email-change、complete、action、check-deactivation-mail、secret、download-session、email-invalid、archive、delete、note、check-live、refresh-token、check-plan、extract-link、upload-sub2、c2a/sync、download-cpa |
| Codex 凭证 | `webui/routes/codex.py:78-560` | refresh-token、archive、download-bulk-from-cpa、download、delete、stop、retry |
| 邮箱资源 | `webui/routes/email_pool.py:339,360,609,707` | email-derivation/status、outlook/secret、outlook/status、outlook/delete；Butler imports 创建/重试/取消另有独立批次 |
| 注册 | `webui/routes/jobs.py:400,406,466,551` | batch cancel/stop、retry-bulk、delete-bulk |
| 提链 | `webui/routes/extract_workbench.py:359,379` | 按 batch_id 取消、创建批次 |
| 任务中心 | `webui/routes/operations.py:189` | operations/bulk（retry/cancel/terminate/delete） |

## 六、前端循环不能只靠 grep 定性

已检查的当前 Vue 公共动作中，`TaskCenter.vue:84`、`accounts/queuedActions.ts:192,212`、`accounts/actions.ts:109-112`、`email/useEmailInventory.ts:30,35,51` 都向集合 API 提交一次所选集合。不能把这些当前路径描述成前端逐条调用单条 API。

以下循环是正常集合构建或只读协调，不应被误报：

- `accounts/useAccounts.ts:303-307` 本页勾选与清除已处理选择；309-326 行构建冻结账号/邮箱/查询上下文。
- `accounts/queuedActions.ts:142-151` 对已受理扫描目标读取刷新结果；不是重新提交扫描。
- `bulk/useBulkDetail.ts:124` 本页选择、36 行合并分页轮次；不写业务。
- `accounts/useAccounts.ts:361-374` 详情修订失效后的只读重取；不是批量按钮实现。

这些证据说明主要短板可以位于 HTTP 之后；“前端没有循环”也不代表后端、存储已经集合化。

## 七、壳、共享控件、诊断入口防遗漏

全站清单不能只扫描 `.vue`。`index.html:312-325` 仍加载共享 JS 与多个桥接/遗留宿主，动态按钮也可能藏在 JS 字符串中。

| 来源 | 容易漏计的动作 | 证据与分类 |
|---|---|---|
| `webui/templates/index.html` | 所有一级菜单及子菜单；移动导航；历史返回；退出登录 | 70-151、160-177 行。界面/会话级动作 |
| 同上 | 查活日志关闭、支付二维码关闭、外部二维码入口 | 264-268、305-309 行。弹窗/跳转；二维码链接同样是操作入口 |
| `webui/templates/login.html` | 显示/隐藏授权码、进入控制台 | 47、67 行。会话/本地输入操作 |
| `webui/static/js/shared/common.js` | 上/下一页、页码、跳转；列筛选选项、清筛、清除全部、日期清除、完成；复制按钮 | 267-318、676-785、939 行。动态生成，不能只统计模板静态 button |
| `webui/static/js/shared/account-filters.js` | 移除筛选 chip、筛选完成 | 51、86 行。只读筛选交互 |
| `RegistrationPage.vue` 日志/诊断 | 与同批成功任务对比、下载 HAR、结束调试并收口；打开失败截图、展开完整诊断 | 164-165 行；其中结束调试有写入/资源收尾，不应和纯下载合并 |
| `tasks/detail/TaskDetail.vue` | 事件/日志/诊断页签、从头/最近/继续读取、失败重试、诊断 HAR/页面现场下载、查看截图、回到底部、关闭 | 135-177 行；171 行的下载为 a 标签，summary/链接也应纳入动作审计 |
| `webui/templates/partials/extract_stats.html` | 统计页面宿主 | 当前为 Vue root 宿主，不另含静态 button；实际按钮由前端统计组件提供 |

未在当前仓库找到独立 diagnostics.html 或 Diagnostics.vue 页面；诊断目前主要嵌入注册详情和任务详情。不能据此说“没有诊断按钮”。服务端存在注册 diagnostics/screenshot 入口（`jobs.py:617,687`）以及任务 Run 归属校验诊断下载（`operations.py:96`）。

README 的“功能地图”引用位于 `README.md:154`，对应 `docs/architecture/functional-map.md/json` 是链路/测试影响地图，不是按钮目录。Markdown 只列约 10 条主链，JSON 虽把 TaskCenter.vue 加到任务中心 entrypoints（89 行），没有独立全站按钮表，也未给原生 bulk 平台独立链路。不能以地图“路径存在”检查通过证明按钮审计无遗漏。

## 八、建议最终统一结论口径

1. 已有可复用的持久批量基础和集合创建能力，但当前目录仅覆盖六类账号操作，并且没有独立通用 node 模型。
2. 以“前端集合意图、批量控制节点、集合存储调度、逐目标远端执行”四层逐项标记；URL 名称、批次字段或一次点击都不能替代证据。
3. 优先讨论公共任务中心逐条调用与 managed retry 的单目标碎轮次，以及原生平台历史重跑和控制结算的逐项 SQL；同时保留原领域锁序、回执、恢复和错误分类。
4. 同步集合读写也纳入批量节点/回执的一致口径，但避免默认建 N 个 Task/Run 或强制变成长任务；注册、支付、邮箱租约等领域行为变更必须单独确认方案。
5. 本报告只有静态定位和架构归类；没有提交、推送、重启、部署、性能测试或真实流程验收。
