# 任务阶段与依赖展示审计

审计日期：2026-11-13。范围是只读进度投影、公开 API 契约及纯输入/输出测试；未改动注册主流程、驱动、执行模板顺序、worker、分派和重试策略，未连接生产数据库、邮箱或远端账号服务。

## 展示契约

保留 `flow_version`、`main_steps`、稳定 `id`、`raw_stages`、原有 `depends_on`、`observed_order`、`attempts` 和线路历史。新增 `structure` 与每个顶层步骤的 `execution`，由 `core/operations/progress.py` 生成。

| 字段 | 含义与证据边界 |
| --- | --- |
| `structure.order_basis` | `observed_events`；沿用阶段开始时间与首条事件的观察排序。缺少记录的模板项依旧保留。没有严格先后保证。 |
| `execution.kind` | 普通阶段、条件阶段、子任务分派、结果、未知。类型来自展示定义，不表明已经执行。 |
| `execution.condition` | 条件文字与 `met/not_met/unknown`。读取本 Run 保存的配置、计划；真实子任务引用可确认分派条件已触发，实际阶段运行/成功/失败证据优先。无条件证据保留未知，不能用当前账号状态补猜；子任务引用不补造事件、顺序或时间。 |
| `depends_on` | 沿用已存在的明确本地依赖；不追加模板邻接关系，不据此推断并行。 |
| `execution.dependency_state` | 子任务等待必须有本 Run 的 `waiting` 或 `awaiting_steps` 证据；分派成功不代表 child 完成。子任务成功、失败分别表达依赖满足或受阻。普通已观测阶段不因剩余计划被泛化成等待。 |
| `execution.waits_for` | 只保留子任务 ID、Run ID、类型、状态及来源；明确等待但缺少 child ID 时返回空 ID，不编造引用。 |
| `execution.parallel_group` | 只接受本 Run、所选线路的显式 `parallel_group`，同组至少有两个阶段。模板相邻、无依赖、时间重叠、两个 running 都不能证明并行。当前审计的执行器没有承诺发出该字段，因此通常为 null。 |
| `execution.retry` | 失败后同一阶段再次进入，或既有恢复判据确认回退成功，才给出 observed/recovered。正常子阶段数量、事件数量、不同国家查询、晚到 running 及多个成功实例不算重试。缺少证据时次数为 null；原失败事件继续保留。 |
| `execution.source` | `runtime_contract` 仅表示有展示定义，不代表执行器写出了运行证据；动态未知阶段有事件时为 `event`。 |

子任务等待不新增 `depends_on` 边，也不改变步骤状态或父任务结果。`refresh_at` 是补全协调器真实保存的子任务摘要键，本次补充读取该旧字段；native 账号配置分派被旧计划过滤时，仅依据实际 child 引用或分派事件补回已有的 `account_setup_dispatch` 稳定展示节点。

## 18 类现有模板

以下审查服务入口、条件分支和事件写入处；它不是对所有浏览器页面状态机的端到端验证。实际顺序仍从该 Run 的证据读取，不将下表转成固定流程图。

| 模板 | 主要运行时来源 | 已核对的分支或关系 |
| --- | --- | --- |
| registration | `core/registration/service.py`、`standalone.py`、`postprocess.py` | 冻结 Codex/2FA/套餐开关；协议/浏览器差异；后处理结果独立保存。认证内部顺序由 raw 事件保留。 |
| registration_resume | `webui/runtime.py`、`core/registration/service.py` | 复用原身份并恢复注册；条件开关沿用当前 Run 快照，不把模板位置视为恢复点。 |
| codex_retry | `core/codex/operation_service.py` | 协议路径跳过 browser；工作区、手机验证由页面需要触发；确认凭证后按配置上传 Sub2API。 |
| twofa_retry | `core/codex/retry_service.py` | 请求的套餐/密码/2FA 子集；协议 2FA 失败可按配置回退浏览器，回退是否实际发生看事件。 |
| account_setup_retry | `webui/runtime.py`、`core/codex/retry_service.py` | 套餐先独立查询；按请求选择密码/2FA；browser 是否需要取决于驱动与回退。 |
| password_setup | 同上及 `core/accounts/password_setup/service.py` | 密码计划、协议或浏览器路径；既有密码检查点可能省略实际设置。 |
| password_change | 同上 | 强制重置参数影响浏览器和认证分支；模板顺序不能代替密码重置事件。 |
| twofa_setup | `core/codex/retry_service.py` | 可直接使用 AT 走协议；需要认证或浏览器回退时保留对应实际 raw 阶段。 |
| twofa_change | `webui/runtime.py`、`core/codex/retry_service.py` | 强制更改选择浏览器；重认证及已确认结果保留原始证据。 |
| account_completion | `webui/runtime.py:_run_account_completion_worker`、`core/storage/operations/store.py:_reconcile_parent_task_cur` | AT 子任务、native 配置子任务和 Codex 子任务提交后交接并等待；保存 continuation_steps 后续接。legacy 配置也可内联执行，不能一概认为并行或 child。 |
| live_check | `core/accounts/liveness/service.py` | token 检查与认证恢复受驱动、Token 状态及配置控制；保留已有明确预检/网络依赖。 |
| token_refresh | 同上 | 认证子阶段由实际驱动回报；保留已有依赖，未把全部认证子阶段串成固定链。 |
| codex_token_refresh | `core/codex/token_refresh_service.py` | 预检后刷新与凭证保存；远端错误/重新授权分支不能由模板判为成功。 |
| c2a_session_reimport | `core/integrations/c2a/manual_sync.py` | 定位账号、策略核验、原位更新；存在有界远端重试 note，但未完整发出 stage 转移，因此缺少阶段证据时继续未知。 |
| plan_check | `core/accounts/plans/service.py`、`at_recovery.py` | AT 失效可刷新再查询；多国家重复查询不是自动重试证明，未观察到刷新时继续沿用现有隐藏行为。 |
| deactivation_mail | `core/accounts/deactivation/mail_scan.py` | 不支持的邮箱来源跳过预检；支持来源进入扫描；HME 复用批量读缓存。 |
| extract_link | `core/extract_link/service.py:_run_extract` | 预检可关闭；刷新只在允许且 AT 失效时进入；AT 校验与刷新发生在预检内部，模板顺序不是执行顺序。 |
| email_change | `core/accounts/email_change/service.py` | 发送新邮箱验证码时可能插入 Recent Login；验证后本地写回；认证条件由事件确认。 |

## 当前模板覆盖缺口

运行时还有 `sub2api_manual_upload`、`sub2api_sync`、`sub2api_scan`、`sentinel_maintenance_check`、`account_inspection`，以及聚合任务 `account_inspection_batch`；它们不在这 18 个 `TASK_TEMPLATES` 中。本次不新增执行模板或推断其固定关系，保持已有动态 raw 节点和未知展示，结果仍来自 Run 状态。对应来源为 `core/integrations/sub2api/{manual_upload,jobs,monitor}.py`、`core/maintenance/sentinel.py`、`core/accounts/inspection/service.py` 与 `core/storage/accounts/inspections.py`。

## 验证

`tests/operations/test_task_progress_structure.py` 用合成 Run 和事件验证全部 18 个模板、冻结条件与实际事件优先级、child 等待与终态、缺失 child ID、稳定分派 ID、普通子阶段/多实例不误算重试、恢复保留失败记录、显式并行与未知回退、Run/线路隔离、公开契约必填字段/枚举以及输入不变。与既有 `tests/operations/test_task_progress.py` 一并运行。API 类型由 `contracts/task-center.openapi.json` 生成到 `frontend/src/api/schema.d.ts`。

这次没有触发真实注册、认证、验证码、密码更改、2FA、支付或远端上传；未验证的运行时页面与并行关系保持未知。
