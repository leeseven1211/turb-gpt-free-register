# 统一任务日志、事件与详情展示设计

> 状态：已实施基础版本（2026-08-31）；本文同时保留后续增强项
>
> 日期：2026-08-31
>
> 范围：注册、注册恢复、查活、刷新 AT、套餐查询、Codex/2FA 补跑、封号邮件扫描等统一任务
>
> 关联文档：`unified-task-center-architecture.md`、`registration-state-refactor-design.md`

## 1. 结论

当前问题不能只按弹窗样式修复。需要把现在统称为“日志”的内容拆成三层，并让所有任务共用同一套写入协议：

1. **阶段状态**：回答“运行到哪一步、这一步是什么状态”，用于顶部进度条；
2. **任务事件**：回答“发生了什么、为什么重试或失败”，用于默认时间线；
3. **技术日志与诊断产物**：回答“代码和上游具体返回了什么”，用于排障，不参与阶段状态计算。

统一后的数据流为：

```text
业务执行器
  -> TaskReporter（唯一任务上报入口）
       ├─ PostgreSQL operation_events：结构化阶段和用户可读事件
       ├─ operation_runs / operation_tasks：当前状态投影
       ├─ 每个 Run 独立 JSONL 技术日志：详细排障信息
       └─ debug artifacts：截图、网络记录等失败诊断产物

WebUI
  -> 任务摘要
  -> 选中的 Run
  -> 阶段条（只读显式阶段状态）
  -> 事件时间线（默认）/ 运行日志 / 诊断产物
```

关键约束：

- 前端和兼容投影不得再根据中文消息中的“已选择”“完成”“跳过”等词猜阶段状态；
- 一条普通说明日志不能让某个阶段变成“执行中”；
- 同一个串行 Run 同一时刻最多只有一个主阶段为 `running`；
- 重跑增加新的 Run，日志和事件不得覆盖上一次运行；
- 注册领域检查点仍是业务事实，但不能和展示阶段重复平铺成两套“进度”；
- 密码、OTP、Token、Cookie、Authorization、完整代理凭据在进入任何持久化层前统一脱敏。

## 2. 本次现状核对

### 2.1 截图中的直接显示问题

截图对应现代账号任务详情弹窗。当前实现有三个确定的前端问题：

1. 弹窗高度按“标题 + 日志”计算，但实际又加入了错误摘要和阶段条。外层使用 `overflow: hidden`，日志区仍按旧公式占满高度，所以底部被裁切。
2. `.account-task-events` 同时继承通用 `.log` 的 `white-space: pre-wrap`。模板字符串中的换行和缩进也会产生可见空行，导致每张事件卡异常高。
3. JavaScript 通过 `event.detail ? ... : ''` 判断是否显示详情。空对象 `{}` 在 JavaScript 中为真，因此大量事件都会显示一块没有信息量的 `{}`。

这三个问题可以解释截图中的大块留白、空 `{}` 和最底部显示不完整，但不能解释阶段条同时出现多个“执行中”。后者来自事件写入语义。

### 2.2 任务 #25644 的只读证据

截图中的任务 #25644 在核对时为：

- 任务类型：`token_refresh`；
- 来源：旧 `account_action_tasks` 写模型投影到 `operation_*`；
- Run：第 1 次，状态 `running`；
- `operation_tasks.current_stage`：笼统的 `running`；
- 结构化事件共 4 条，全部被投影为 `stage.running`；
- 阶段分散在 `queued`、`login_password`、`network`；
- 其中 3 条详情为空对象。

因此顶部阶段条同时把“分配网络”和“账号登录”画成执行中。它不是前端随机显示，而是前端忠实消费了错误的阶段状态投影。

### 2.3 注册与账号任务目前确实不一致

注册任务通过 `report_job_progress(stage, state, detail)` 明确上报 `running/success/skipped/failed`。注册进度投影可以得到稳定的 `stage.*` 事件和开始/完成时间。

账号任务仍主要通过：

```text
account_task_store.append_event(stage, message, level, detail)
```

写自由文本。大多数调用没有传 `state`，兼容投影只能根据级别、阶段名和中文关键词推测状态。最近 7 天只读统计显示：

| 任务类型 | 事件数 | 被投影为 `stage.running` | 显式 `step_state` |
| --- | ---: | ---: | ---: |
| 刷新 AT | 54 | 47 | 0 |
| 查活 | 314 | 259 | 0 |
| 套餐查询 | 74 | 56 | 0 |
| 封号邮件扫描 | 376 | 约 282 | 0 |
| 账号配置补跑 | 136 | 60 | 52 |

这说明账号任务把“过程说明”大量误当成“阶段执行中”；注册流程已经接近目标协议，但仍同时存在注册进度和注册领域检查点两类事件，详情页需要分层而不是全部混排。

### 2.4 当前保存方式也不统一

现状同时存在：

- `registration_jobs.progress_steps`：注册阶段快照；
- `registration_events`：注册尝试的领域检查点；
- `account_action_events`：账号任务自由文本事件；
- `operation_events`：统一任务中心的兼容投影和原生事件；
- `注册日志/<job_uuid>.log`：注册任务文件日志；
- `注册日志/live-check-<email>.log`：按邮箱覆盖/追加的查活日志；
- `注册日志/codex-retry-<email>.log`：按邮箱保存的 Codex 日志；
- `注册日志/debug/<job_uuid>/`：失败诊断产物。

按邮箱命名的日志不能天然区分多次 Run；不同任务的文件格式和生命周期也不一致。统一任务详情虽然读取了 `operation_events`，但还没有统一“技术日志”的读取协议。

## 3. 统一概念

### 3.1 阶段状态 Stage State

阶段状态只用于回答进度，不承载任意说明文本。固定五态：

```text
pending -> running -> success
                   -> failed
pending/running    -> skipped
```

合法事件类型沿用现有统一任务协议：

- `stage.running`
- `stage.success`
- `stage.failed`
- `stage.skipped`

`pending` 是流程模板中的初始快照，不需要为了“尚未开始”额外写一条事件。

现有 `stage.running/success/failed/skipped` 直接保留；兼容期只补齐明确状态，不需要批量改写历史事件名。

每个阶段终态必须带：

- `stage`：稳定阶段键；
- `message`：用户可读结果；
- `duration_ms`：阶段耗时；
- `attempt_no`：阶段内部第几次尝试，可选；
- `error_category/error_code`：失败时必填；
- 经过脱敏的少量结果字段。

### 3.2 任务事件 Task Event

任务事件用于时间线，但不改变阶段状态。事件类型使用命名空间：

- `run.queued`、`run.running`、`run.success`、`run.failed`、`run.cancelled`、`run.interrupted`；
- `note.info`、`note.warning`、`note.error`；
- `resource.acquired`、`resource.rotated`、`resource.released`；
- `retry.scheduled`、`retry.exhausted`；
- `artifact.created`；
- `domain.checkpoint`：领域里程碑的只读摘要。

例如“已选择查活线路（第 1/4 次）”应拆为：

```text
resource.acquired(stage=network, attempt_no=1, detail=脱敏线路信息)
stage.success(stage=network, message=网络线路已就绪)
```

而不是一条由投影猜成 `stage.running` 的自由文本。

### 3.3 技术日志 Run Log

技术日志服务于排障，保留比任务事件更细的代码行为，例如请求重试、页面状态和调用栈摘要。它不直接进入阶段条，也不要求每行都展示在默认时间线。

每行使用 JSONL，字段最小集合为：

```json
{
  "ts": "2026-08-31T12:35:09.123+08:00",
  "level": "INFO",
  "task_id": 25644,
  "run_id": 25644,
  "stage": "network",
  "logger": "core.live_check_service",
  "message": "网络预检完成",
  "fields": {"attempt_no": 1, "network_route": "proxy"}
}
```

日志写入器必须先脱敏，再同时写文件和控制台；不能先写原文后依赖读取 API 脱敏。

### 3.4 诊断产物 Diagnostic Artifact

截图、页面快照、压缩网络记录和控制台抓取继续作为文件产物保存。`operation_events` 只保存产物类型、相对引用、大小、生成时间和脱敏状态，不把大文件内容写入 JSONB。

## 4. 统一写入接口

新增一个与存储实现解耦的 `TaskReporter`。注册、查活、刷新 AT、套餐查询、Codex/2FA 和邮件扫描只依赖这个接口，不直接写 `account_action_events` 或自行拼任务日志文件。

建议接口：

```python
reporter.run_started(message="开始刷新 AT")

with reporter.stage("network", message="准备网络线路") as stage:
    stage.event("resource.acquired", "已取得网络线路", detail=safe_route)
    stage.succeed("网络线路已就绪")

reporter.note("等待邮箱验证码", stage="email_otp")
reporter.warning("第一次网络预检失败，准备换线", stage="network", code="external.proxy")
reporter.artifact("page_snapshot", relative_path=path, stage="login")
reporter.run_succeeded(result_summary=safe_summary)
```

接口约束：

1. `stage()` 自动记录开始时间；正常退出但未显式结束时默认成功，异常退出时记录失败并继续抛出原异常。
2. 阶段状态必须由方法调用明确给出，禁止从 `message` 推断。
3. 同一串行 lane 开始新主阶段时，前一个 `running` 阶段必须先收口；违反时开发/测试环境直接报错，生产环境写告警并自动收口为失败或中断。
4. 每个 Reporter 固定绑定 `task_id/run_id/execution_id`，业务调用方不能漏掉关联字段。
5. 所有 `detail` 经过统一 schema 白名单和脱敏器；未知字段默认只进入技术日志，不默认进入用户时间线。
6. Run 终态与最后一条 `run.*` 事件在同一事务内更新，避免“任务已完成但时间线还在运行”。

## 5. 保存设计

### 5.1 PostgreSQL：长期、可查询的结构化事实

继续以 `operation_tasks -> operation_runs -> operation_events` 为任务中心事实链，不新增另一套日志数据库。

`operation_events` 建议补充或约束：

- `sequence_no`：同一 Run 内单调递增，UI 排序以它为准，时间仅用于展示；
- `event_type`：使用上面的命名空间；
- `stage`：统一阶段表中的稳定键；
- `level`：`DEBUG/INFO/WARNING/ERROR`；
- `message`：面向用户、已脱敏、长度受限；
- `detail`：只保存允许进入 UI 的结构化字段；
- `error_category/error_code`：错误分类；
- 可选 `visibility`：`summary/timeline/debug`，默认 `timeline`。

新原生事件按 append-only 写入：阶段开始和阶段终态是两条事件，不能用终态覆盖开始事件。迁移期兼容投影仍可按 `source_system/source_id` 幂等更新旧来源对应行，但新 TaskReporter 不复用旧事件 ID。阶段当前状态单独写入 `operation_runs.progress_steps`，不靠修改历史事件实现。

`operation_runs.progress_steps` 作为阶段快照保留，便于一次读取就画阶段条。它只能由 `TaskReporter` 在写阶段事件的同一事务中更新，不能由前端从事件文本重建。

`operation_tasks.current_stage` 投影所选最新 Run 的真实活动阶段；终态 Run 固定为 `complete/interrupted` 等终态，不再写笼统的 `running`。

### 5.2 文件：每个 Run 独立的技术日志

统一目录建议：

```text
注册日志/tasks/<task_uuid>/runs/<run_no>-<run_uuid>/
  run.jsonl
  artifacts/
    manifest.json
    ...
```

要求：

- 路径只使用 UUID，不使用邮箱、账号名或 Token；
- 每次重跑创建新目录，旧 Run 不覆盖；
- `operation_runs.log_file` 保存项目内相对路径或受控绝对路径；
- 单行和单文件都有大小上限，超限时滚动为 `run.1.jsonl` 等，并写 `log.rotated` 事件；
- 文件写失败不能改变远端业务结果，但必须写入 `operation_events` 告警并在 Run 摘要标记 `logging_degraded=true`；
- 清理程序按 manifest 逐文件删除，确认空目录后再移除目录，不做递归删除。

### 5.3 保留策略

- `operation_events`：跟随任务记录保留，不单独提前删除；
- Run 技术日志：默认保留 30 天，配置可调；
- 失败/未知状态的诊断产物：沿用注册调试的可配置保留策略；
- 被手工标记“保留诊断”的 Run 不参与自动清理；
- 清理结果写审计事件，只记录数量和字节数，不把已删文件路径重新暴露给前端。

### 5.4 脱敏规则

统一脱敏器覆盖数据库事件、JSONL、异常摘要和诊断 manifest：

- 键名包含 `password/otp/secret/token/authorization/cookie` 的值不保存；
- JWT、Bearer Token、刷新令牌按模式替换；
- 代理只保留 provider、region、route、是否使用，不保存用户名、密码和完整 URL；
- 邮件正文不保存；邮箱只在任务已有权限的摘要区展示，不进入日志文件名；
- HTTP 响应只保存状态码、已批准的字段和受限 preview；
- 脱敏后为空的 `detail` 统一保存为 `{}`，API 同时计算 `has_detail=false`，前端不展示空块。

## 6. 打日志规范

### 6.1 什么进入阶段条

只有对用户有稳定意义、能明确开始和结束的步骤进入阶段条。任务类型使用不同流程模板，但阶段词汇共用一张表。

建议流程：

| 任务类型 | 主阶段 |
| --- | --- |
| 注册 | 网络 -> 邮箱 -> 浏览器/协议 -> 提交邮箱 -> 认证 -> 邮箱验证 -> 资料 -> Token -> 后处理 -> 完成 |
| 注册恢复 | 网络 -> 登录 -> 邮箱验证/Authenticator -> 资料 -> Token -> 后处理 -> 完成 |
| 查活 | 网络 -> 校验现有 Token -> 完成 |
| 刷新 AT | 网络 -> 登录 -> 邮箱验证/Authenticator -> 获取并保存 Token -> 完成 |
| 套餐查询 | 网络 -> 请求套餐 -> 保存结果 -> 完成 |
| Codex 补跑 | 预检 -> 网络 -> 授权登录 -> 手机验证（可跳过）-> callback -> 凭证确认/保存 -> 完成 |
| 封号邮件扫描 | 邮箱连接 -> 扫描信号 -> 保存结果 -> 完成 |

驱动差异、代理轮换次数、接口重试次数是阶段内事件，不扩张成新的主阶段。只有业务分支真实未执行时才写 `stage.skipped`。

### 6.2 什么进入默认时间线

默认展示：

- Run 开始、结束、停止、中断；
- 主阶段开始和终态；
- 换代理、重试、回退驱动等影响路径的事件；
- 脱敏后的错误；
- 关键领域里程碑，如“远端账号创建结果待确认”“Token 后核心账号已落库”；
- 诊断产物可用提示。

不默认展示：

- 高频轮询；
- 完整请求/响应；
- 每次 DOM 查询；
- 空 detail；
- 与阶段事件重复的领域检查点。

### 6.3 注册领域事件如何处理

`registration_events` 继续维护注册 Attempt 的远端身份、账号和本地落库检查点，它的职责不是替代 Run 进度。

TaskReporter 在关键检查点发生时可以写一条 `domain.checkpoint` 摘要到 `operation_events`，但必须带稳定 `dedupe_key`。同一事实若已经由阶段终态表达，默认时间线只显示一次；完整领域审计放到“诊断/业务里程碑”视图。

这样既保留注册恢复所需的业务事实，也不会让用户看到两套重复时间线。

### 6.4 时间和顺序

- 数据库存储统一使用 `TIMESTAMPTZ`；
- 应用内部使用带时区时间，禁止把本地无时区字符串直接写入 `TIMESTAMPTZ`；
- API 返回 ISO 8601 带 offset 或 `Z`；
- 浏览器只转换一次到本地时间；
- 同一 Run 以 `sequence_no` 排序，`created_at` 只用于跨 Run 展示和人工判断。

这也避免历史注册进度、注册检查点和账号兼容事件因无时区字符串产生 8 小时错序。

## 7. API 设计（基础版本已落地）

任务摘要与长事件/日志读取已经拆开，详情页轮询摘要并按 Run 增量读取事件和技术日志：

```text
GET /api/operations/{task_id}
  -> 任务摘要、Run 摘要、最新阶段快照、错误摘要

GET /api/operations/{task_id}/runs/{run_id}/events?after_id=123&limit=200
  -> 增量结构化事件

GET /api/operations/{task_id}/runs/{run_id}/logs?cursor=...&limit=500
  -> 技术日志尾部或增量内容

GET /api/operations/{task_id}/runs/{run_id}/artifacts
  -> 诊断产物清单，不直接返回敏感文件内容
```

当前使用 2 秒增量轮询，尚未引入 WebSocket/SSE、级别/关键词过滤或独立 artifacts 路由。事件和日志响应包含：

- `next_after_id/next_cursor`；
- `has_more`；
- `run_terminal`；
- `available`（日志文件是否存在）；
- 每个事件的 `has_detail` 和服务端脱敏后的 `detail`。

前端只追加新事件，不再每两秒重建全部 DOM，也不会在用户向上查看历史时强制滚到底部。

## 8. 任务详情展示设计

### 8.1 弹窗结构

```text
┌ 任务 #25644 · 刷新 AT             [关闭]
│ 执行状态 / 目标状态 / 触发方式 / 总耗时
│ Run: [第 1 次 ▼]  当前阶段与错误摘要
│
│ ○ 网络 —— ○ 登录 —— ○ 邮箱验证 —— ○ 保存 Token —— ○ 完成
│
│ [事件时间线] [运行日志] [诊断产物]
│ ─────────────────────────────────
│ 可滚动内容区
└──────────────────────────────────
```

布局规则：

- 弹窗本身使用 `display:flex; flex-direction:column`；
- 标题、摘要、Run 选择和阶段条 `flex:none`；
- 内容区使用 `flex:1; min-height:0; overflow:auto`；
- 高度以 `min(92dvh, 860px)` 控制，不再用“固定减 74px”的公式猜内容高度；
- 桌面和窄屏都只有一个主滚动容器，底部必须留安全内边距；
- 关闭按钮和错误摘要始终可见，内容区滚动不带走标题。

### 8.2 事件时间线

- 默认按时间从旧到新，最新在底部；
- 每条事件采用紧凑行，不再把每条普通信息做成大卡片；
- 阶段终态、错误、换线和回退使用图标/颜色区分；
- 同一阶段连续的相同重试可折叠为“网络预检失败 3 次”；
- 重要结构化详情用键值列表展示；
- 原始 JSON 默认折叠到“查看技术详情”，空对象完全不渲染；
- 用户停留在底部时自动跟随；用户向上滚动后停止自动跟随，并显示“有 N 条新事件，回到底部”。

### 8.3 运行日志

- 使用真正的 `<pre>`/虚拟列表展示 JSONL 投影后的文本，不复用事件卡 CSS；
- 支持级别过滤、关键词搜索、复制当前可见内容和下载当前 Run 日志；
- 默认只加载尾部，向上滚动再按 cursor 取更早内容；
- ERROR 可跳回对应时间线事件或阶段；
- 日志文件不存在、已过期或写入降级时展示明确状态，不显示空白面板。

### 8.4 Run 选择

任务详情默认打开最新 Run。用户切换历史 Run 后：

- 阶段条、事件、日志、诊断产物全部随 Run 切换；
- 历史 Run 的失败不会污染最新 Run 的阶段条；
- 页面明确显示“第 N 次运行”和本次开始/完成时间；
- 新重跑开始时不强制把正在查看的历史 Run 切走，只提示“第 N+1 次运行已开始”。

## 9. 兼容迁移方案

### 阶段 0：显示修复，不改变任务语义

目标是先消除截图中的直接问题：

- 弹窗改为 flex 布局和单滚动区；
- 事件容器不再继承 `white-space: pre-wrap`；
- 空 detail 不渲染；
- 详情按 Run 分组，默认只画最新 Run 的阶段；
- 增加小屏和底部可见性回归测试。

这一阶段不改生产任务写入和数据库结构，风险最低。

### 阶段 1：冻结事件契约

- 在 `core/task_stages.py` 中确定阶段目录和事件命名空间；
- 建立 `TaskReporter` 接口、脱敏器和契约测试；
- 禁止新增没有 `state` 的阶段事件；
- 兼容投影只负责旧数据映射，停止继续扩展中文关键词规则。

### 阶段 2：先迁移账号任务写入

按问题最明显且风险较低的顺序迁移：

1. 查活与刷新 AT；
2. 套餐查询；
3. 封号邮件扫描；
4. 账号配置/2FA 补跑；
5. 旧 Codex 补跑路径。

每迁移一种任务都要验证：阶段只有一个主 `running`、终态完整、旧表与 operation 投影结果一致、敏感字段不入库。

### 阶段 3：收口注册展示

- 注册驱动继续用显式状态，但通过 TaskReporter 写统一 Run 事件；
- `registration_events` 只保留领域事实；
- 去掉默认时间线里的重复进度/检查点；
- 校正历史无时区时间的只读展示适配，新数据不再产生错序。

### 阶段 4：统一 Run 技术日志

- 所有新 Run 使用 UUID 目录和 JSONL；
- API 支持增量读取；
- 旧按邮箱和 job UUID 的日志保持只读兼容；
- 新 Run 验证稳定后，停止向按邮箱文件写新日志。

### 阶段 5：移除旧写模型

在对账观察期通过后：

- 账号任务原生写 `operation_tasks/runs/events`；
- `account_action_*` 只读兼容，再按独立迁移方案退役；
- 任务详情不再关心 `source_system`，所有任务表现一致。

## 10. 验收标准

### 10.1 数据契约

- 新建的所有任务都有 `run.queued`、`run.running` 和唯一 Run 终态；
- 串行任务任一时刻最多一个主阶段为 `running`；
- 每个 `stage.running` 最终有 `stage.success/stage.failed/stage.skipped` 之一；Run 被中断时，当前阶段以 `stage.failed` 和中断错误码收口；
- `operation_tasks.current_stage` 与最新 Run 阶段快照一致；
- 失败事件必有结构化错误分类，原始摘要仍保留且已脱敏；
- 事件排序不依赖消息文本或本地无时区字符串。

### 10.2 安全

- 用测试 Token、密码、OTP、Cookie 和带认证代理写事件/日志，数据库和文件全文搜索均找不到原值；
- API 不返回完整代理 URL、邮件正文或认证头；
- 空 detail 的 `has_detail=false`；
- 日志清理逐文件执行，不递归删除目录。

### 10.3 UI

- 在 768px 高度下打开含阶段条、错误摘要和 200 条事件的弹窗，底部内容和最后一条事件可完整看到；
- 不出现空 `{}`；
- 普通事件行没有由模板缩进造成的大块留白；
- 用户向上滚动时轮询不抢滚动位置；
- 切换 Run 后阶段、事件和日志同步切换；
- #25644 同类刷新 AT 任务只能显示一个当前主阶段，不再同时出现“分配网络”和“账号登录”都执行中。

### 10.4 兼容与运行

- 旧注册任务、旧账号任务仍可查看；
- 新旧投影在观察期按任务数、Run 数、终态、错误和事件数对账；
- 投影或文件日志失败不改变业务任务成功/失败结果；
- WebUI 重启后运行中 Run 收口为 interrupted，并保留此前事件和日志；
- 不自动触发任何历史任务重跑。

## 11. 后续增强顺序

基础版本已完成 UI 修复、事件契约、账号任务迁移和每 Run 技术日志。后续增强可拆为三个独立变更：

1. **诊断产物清单**：补充 `/artifacts` 只读接口和 manifest 展示；
2. **技术日志增强**：增加级别/关键词过滤、复制下载和向上翻页读取；
3. **注册写入收口**：让注册驱动也通过 TaskReporter 写统一 Run 事件，并逐步退役旧写模型。

不建议先把全部 Python `logger` 输出灌进 PostgreSQL，也不建议继续增强关键词推断。前者会把高频技术噪声变成长期数据库负担，后者无法从根本上区分“说明了一件事”和“阶段已经成功”。
