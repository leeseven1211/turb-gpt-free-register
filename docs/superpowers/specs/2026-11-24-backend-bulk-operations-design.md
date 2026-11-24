# 后端批量操作与批量节点设计

日期：2026-11-24

## 背景与目标

当前很多“批量”按钮已经可以一次提交 ID 数组，但后端仍在请求内逐目标读取、逐目标开启事务、逐目标创建任务或逐目标更新状态。这样会造成连接、锁、事务提交和调度唤醒的线性开销；当目标数较大时，数据库压力会先于外部服务成为瓶颈。

本项目将后端批量入口统一为集合语义：一次请求固定并去重目标集合，后端集合预取和集合写入，按固定块提交事务，返回每个目标的明确结果。单条入口继续保留，但内部复用同一个批量服务并传入一个目标。

本阶段的重点是 Turb 自己控制的数据库事实、任务事实和批量控制事实。账号认证、邮箱 OTP、浏览器、Codex OAuth、C2A、Sub2API、提链平台和代理出口等外部调用继续按目标执行；它们只迁入批量节点的 worker 调度，不假设第三方已经提供批量 API，也不改变现有外部调用顺序。

注册主流程（包括 Roxy、proto2 及其他驱动）的步骤、请求参数、页面定位、关键分支、重试/超时和状态流转不在本项目中改变。注册任务的本地取消、删除和批量控制只能复用现有终止边界。

## 设计原则

1. **一次意图、一次批量请求**：前端和兼容客户端提交完整集合与幂等键；服务端不通过循环调用单条 HTTP 或单条应用服务来实现批量。
2. **集合预取、集合判断、集合写入**：同一连接内按目标 ID/filename/email 使用 `ANY`、`unnest`、`jsonb_to_recordset` 或集合 `UPDATE/DELETE ... RETURNING`；逐项 Python 循环只负责将集合查询结果映射成回执，不再触发独立查询或事务。
3. **分块事务**：默认每块 500 个目标，受领域上限约束；每块拥有独立事务。已提交块的结果保留，失败块明确标记，不假报全部成功。
4. **固定锁序与安全规则**：延续现有账号→邮箱账本→母资源、任务→运行、批次→目标的锁序；邮箱租约只有在业务事实允许时才能进入退租事实；注册成功或结果不明时不得释放邮箱。
5. **统一逐项回执**：每个输入目标最多一个最终结果，包含 `status`（`updated`、`skipped`、`failed`）、稳定 `reason_code`、中文 `reason` 和领域摘要。重复目标只执行一次，回执保留 `duplicate` 统计。
6. **单条复用批量服务**：单条 URL 不再拥有第二套写入逻辑；传入一个目标集合即可得到同一回执结构，路由层只负责单条 HTTP 的状态码和兼容字段。
7. **外部执行与数据库批量分离**：一个批量节点可以拥有 N 个目标 worker，但单账号认证或第三方请求仍是 N 次外部行为；本项目只消除请求线程中的 N 次预取、N 次独立事务和 N 次顶级任务提交。

## 统一接口契约

新增 `core/operations/bulk_mutations.py` 作为通用批量应用服务。它只负责目标规范化、大小限制、分块、幂等键、结果合并与异常分类；具体域的集合读写仍放在对应 `core/storage/*` 模块，避免存储层依赖 `webui`。

建议接口：

```python
@dataclass(frozen=True)
class BulkItemResult:
    key: str
    status: Literal["updated", "skipped", "failed"]
    reason_code: str | None = None
    reason: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class BulkMutationResult:
    operation: str
    requested_count: int
    unique_count: int
    duplicate_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    items: tuple[BulkItemResult, ...]
    chunks: tuple[Mapping[str, Any], ...]
```

HTTP 成功响应统一保留 `ok: true`，并返回上述计数和 `items`。输入非法、超过上限、幂等键冲突等请求级错误返回 4xx；数据库异常或块级异常返回 `ok: false`、已完成块回执和 `bulk_chunk_failed`，不把未提交目标标为成功。现有客户端依赖的 `updated`、`deleted`、`skipped` 等字段继续保留为兼容投影。

请求级幂等键按领域和操作生成，例如 `accounts:archive:<key>`。同一键、同一规范化请求可返回已有回执；同一键、不同目标集合或参数必须返回明确冲突，不能静默合并。

## 覆盖范围

### 本地集合写入

第一组接口直接以集合 SQL 替代逐目标事务：

- 账号：归档/恢复、删除、备注、邮箱失效/解除邮箱失效。邮箱失效继续在同一事务内锁定账号、地址分配和母资源，但改为集合预取与集合锁定，保留 expected email 和 iCloud HME 分组校验。
- Codex：归档/恢复、删除、重置导出计数、批量导出状态回写。文件打包或 CPA 单文件下载仍是外部/文件行为；数据库状态回写一次集合更新。
- 邮箱池：来源状态批量更新、删除/墓碑化、历史派生邮箱状态批量更新。每块事务一次集合读取与锁定；服务事实退租作为提交后的逐目标异步事实，不能在请求内重复开启 N 个数据库事务。
- 任务事实：任务中心删除的隐藏标记、注册任务本地删除、可安全取消的排队状态集合迁移。运行中终止仍使用已有运行控制与收尾语义，不直接用集合 UPDATE 强杀。

### 批量控制与任务创建

第二组接口把现有一次数组请求接入批量控制节点：

- 任务中心 retry/cancel/terminate：一次集合读取和状态分类；managed retry 按来源 batch、动作和参数边界合并成目标集合 round；不再对每个 task 单独创建单目标 round。
- 账号查活、查套餐、刷新 AT、补密码、补 2FA、补全、Codex 重授权、C2A、Sub2API、提链等：先集合固定目标、集合预检和分块创建 Task/Run；worker 中保留每账号外部行为。
- 注册创建和注册重跑只改提交层和本地批次控制时，必须保留每个驱动现有执行契约；不得在此设计下直接替换注册主流程。

### 只读和轻量动作

筛选、分页、关闭、展开、复制已加载值、列宽和导航不创建节点。需要批量读取的导出/复制接口使用集合查询和完整逐项清单；只有耗时、外部副作用或需要恢复时才建立短生命周期产物节点。

## 存储层方案

1. 在 `core/storage/records.py` 的通用集合函数之上补齐稳定排序、缺失目标回执和集合 `RETURNING` 投影；不在路由内重复拼 SQL。
2. 在账号、Codex、邮箱、任务和注册存储模块中提供 `*_bulk` 方法。方法签名接收已规范化目标与共享连接/事务上下文，返回集合行和缺失/保护原因，不自行创建外层循环事务。
3. 对需要逐项业务安全判断的域，先一次锁定候选集合，再在内存中做纯函数资格判断，最后对可更新集合执行集合 SQL；保护失败目标进入 `skipped`，不影响同块其他可更新目标。
4. 对邮箱删除、服务事实退租、任务终止等有外部收尾的操作，事务内只写本地事实和待处理事实；提交后由现有 worker/dispatch 读取事实并按目标执行。请求线程不得在每个目标上同步等待外部调用。
5. 所有批量查询和写入使用显式上限及分块；不使用 `public` schema 测试，不新增 SQLite 或文件回退。

## 路由兼容方案

保留现有 URL，先替换其内部实现，以免同时修改前端和旧客户端：

- `/api/accounts/archive-bulk`、`delete-bulk`、`email-invalid-bulk`、`note-bulk`
- `/api/codex/archive-bulk`、`delete-bulk`、`reset-export-bulk`
- `/api/outlook/status-bulk`、`delete-bulk` 与 `/api/email-derivation/status-bulk`
- `/api/operations/bulk` 的 `delete/cancel/terminate/retry` 分支
- `/api/jobs/cancel-pending`、`retry-bulk`、`delete-bulk` 只先改本地集合受理和任务事实写入；注册执行步骤保持原服务边界

后续新增接口只在现有 URL 无法表达集合范围、幂等键或批量节点查询时增加；新增接口必须同步 OpenAPI、schema 类型和路由契约测试。

## 错误与回执

错误码至少分为：`invalid_target`、`duplicate_target`、`not_found`、`already_applied`、`protected_by_registration`、`active_execution`、`email_changed`、`invalid_state`、`idempotency_conflict`、`bulk_chunk_failed`、`external_pending`。不能返回未分类错误；未知异常记录脱敏上下文后归入具体阶段的 `bulk_chunk_failed`，不把原因留成 `unknown`。

回执必须能回答：输入了哪些目标、去重后多少、哪个目标更新了、哪个跳过以及为什么、哪个块失败、已提交哪些块、是否需要重试。前端现有提示只显示摘要，详细逐项回执进入任务/批量详情或响应清单。

## 测试与验收

- 存储测试继承 `tests.support_pg.PostgresTestCase`，每个测试类使用独立 schema；验证集合更新只提交预期事务数量、重复目标只更新一次、缺失/保护/活动目标返回逐项原因。
- 路由测试覆盖输入上限、去重、兼容字段、幂等键、集合成功与部分跳过、块级失败回执、单条 URL 与 bulk URL 共用同一存储结果。
- 任务中心和批量控制测试验证同一原 batch 的多个目标只生成一个集合 round；取消/终止不绕过运行收尾；删除不隐藏活动任务。
- 不运行完整真实注册或第三方服务调用测试；涉及业务逻辑的测试使用隔离数据库和服务替身，只验证批量提交和本地事实。
- 完成后检查本地代码版本、提交、推送状态和相关健康接口；本轮不部署 Oracle，除非另行确认。

## 不在本设计内

- 不合并第三方 API 请求，不假设 Email Butler、OpenAI、C2A、Sub2API、提链平台或代理供应商有批量接口。
- 不改变注册驱动步骤、请求参数、页面定位、超时、重试和邮箱租约安全规则。
- 不把所有 UI 按钮变成持久任务；只读查询和本地展示继续走查询接口。
- 不删除兼容接口或兼容导出；先以同一批量服务替换内部实现，再按真实调用情况收敛旧入口。
