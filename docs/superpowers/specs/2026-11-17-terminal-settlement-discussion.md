# 任务终态与资源补偿：完整方案讨论稿

日期：2026-11-17。状态：**用户已批准 B，已进入实施；尚未完成修复或验收**。

本文最初按用户“先分析完整终态与资源补偿方案，再确认实施”形成并完成设计审查。用户随后明确选择“B可以”，授权本批 B 产品实现与隔离验证；[实施计划](../plans/2026-11-17-terminal-settlement-b.md)已建立。下文保留方案依据与 A/B/C 对比，选定范围为 B；它不代表实现或验收已完成，提交、推送、生产重启和部署仍未执行。

## 1. 建议与需要确认的选择

**推荐 B：统一收尾责任，加入数据库精确回执和持久补偿记录，保留现有业务执行与保守恢复。**

实际效果是：数据库短暂故障时，任务不会因为“保存结果失败”被改写成另一种业务结果；恢复后只补做原任务的本地收尾，不再次注册、登录、刷新 Token、创建订单或付款。账号租约、执行许可、实际线程和资源分别确认，全部必要收尾完成后才报告干净停止。

| 选项 | 内容 | 保障与代价 |
| --- | --- | --- |
| A：局部收尾修复 | 修正租约释放状态、冻结结果，并在原调用内进行有限重试和精确确认 | 改动较少；不形成统一后台补偿、进程退出和跨重启清理责任，不能作为完整 F16 收口方案 |
| **B：统一收尾与 PostgreSQL 回执（推荐）** | 原执行责任、不可变结果、精确回执、持久清理义务、受生命周期管理的补偿组件、退出及恢复整体验证 | 解决进程存活期间的完整补偿，以及数据库确认后尚未做完的清理；数据库断开且结果尚未持久化时进程再死亡，仍按已有证据保守恢复 |
| C：B 加独立加密本地日志 | 数据库不可写时，将结果另存到持久目录，再按同身份补写 | 能保留已完成本地持久化的结果，但增加第二种恢复输入、密钥、备份、容量和迁移责任；持久化前被杀仍有边界，本批不推荐默认加入 |

以下设计整体已纳入获准的 B 实施范围。其他慢 SQL、五十万混载复测、Linux 原生管理器和生产部署继续单列，不因选择 B 自动纳入。

## 2. 当前失败已经证明了什么

F16 固定端点真实 PostgreSQL 重启轮仍然失败。保存的 v7 观察中，数据库恢复后原 Run 保持 `running`，执行许可已经为 0，原账号租约仍有效；Worker 最后由夹具兜底回收。事件记录明确遇到 `AdminShutdown`，后续出现清理异常链；截断日志不足以逐条证明后继 DELETE/finish 的具体 SQLSTATE。

源码和原生方法最小复现确认了这些独立问题：

1. `OperationLease.release()` 在数据库确认删除前先标记本地已释放；删除异常后，第二次调用不会重试。context 手动释放还会先清空唯一引用。
2. `context.finish()` 仅在数据库正常返回后保存结果；finish-only 异常可能进入通用业务错误分支，改写原结果。部分领域适配器也有相同的外层 catch。
3. `finish_run()` 已经把 Run、Task、终态事件、父任务收口和账号租约删除放在同一数据库事务里。问题不是缺少这一原子性。
4. 它先校验活跃租约、再判断已有终态。若事务已提交但回包丢失，原租约已经删除，直接携原 token 重试可能被拒绝；去掉 token 则是在绕过保护。
5. 现有“已有终态”分支仍可能触发父任务收口、受管事实、文件日志和通知，不能充当无副作用的精确回执读取。
6. 外层 `finally` 和 future 完成回调都可以释放 permit；permit 恢复还会根据业务线程已退出释放占用。因此只删除一个 finally 不足以保留补偿责任。
7. `defer` 成功会把同一 Run 放回队列、清空旧 execution；父任务 `waiting` 也是合法协调状态，均不能按普通终态处理。

主要证据为当前 `core/operations/task_gateway.py`、`core/storage/operations/runtime.py`、`core/operations/concurrency.py`、`core/storage/operations/permits.py`，以及[失败判断](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/faults/storage-v7-defect-decision.md)。分专题源码核验见文末。

## 3. 收敛后的职责

| 组件 | 唯一职责 |
| --- | --- |
| 业务 handler / 领域适配器 | 执行现有业务、确认必要业务写回、明确产出最终结果或延期请求 |
| Operation context | 捕获原身份，深复制冻结一次结果；把业务结果与提交/清理进度分开 |
| settlement repository | 精确确认与原子本地转换；保存回执和清理义务，不导入业务 handler |
| 统一收尾组件 | 按依赖重试原本地提交、原资源清理和原许可释放；受现有 ManagedRuntime 管理 |
| 现有 dispatcher / dependency scanner | 在合法准入下继续已有队列、子任务与原单续查 |
| 现有 recovery | 处理确已退出或失效的执行；没有可信持久结果时保持保守分类 |

收尾组件不形成第二套业务执行器，不调用 handler、远端写操作或为原执行自动创建重试 Run。领域业务写回不纳入通用自动重放。原流程已有的本地后续任务交接，只允许按第 9 节明确白名单和原幂等键可靠投递。

## 4. 原身份与结果屏障

### 4.1 准入时先确定收尾责任

复用现有 permit 行的元数据，在 claim 与 permit 的同一准入事务中写入不可变 `settlement_ticket`：版本、ticket ID、原数据库域、operation/permit schema、Task/Run UUID、execution、permit、原进程身份。它只代表这次执行的收尾责任，**不代表业务结果已经产生或持久化**。

准入返回后、业务 callback 进入前，由本进程统一登记同一 ticket。所有 participating 路径的 finally、future 回调和 permit recovery 都通过这份责任判断是否能够释放。非 participating 的注册、Butler 等许可路径保留其原语义，并做共享接口兼容验证。

同数据库不同 schema 使用捕获的显式表域；若 operation 与 permit 实际指向不同数据库，本协议不能假装具备同一准入事务，应拒绝为该执行启用完整保障并报告域不兼容。重试不得从后来变化的环境变量重新选择数据库。

### 4.2 明确结果后冻结一次

在现有 `finish` 或明确 handler return 的边界，把 status、message、error、summary 和既有业务/远端回执引用递归复制并规范化，生成固定 transition ID。禁止只保存 frozen dataclass 中仍可变的 dict 引用。

完整不可变信封还包括 transition kind/subtype、原 domain/ticket/Task/Run/execution/permit、已声明 lease scope ID/kind/代次、请求版本、允许的尾部义务及其固定幂等身份。defer 的 delay/reason/stage/data patch 首次确定后也冻结，确认重试不根据当前配置重算。提链代理的步骤结果不能封存整次 Run 的信封。

“业务结果已形成”“数据库已确认”“清理已完成”是三个字段。存储异常只改变提交状态，不能把已冻结 success 改成 failed，也不能把原失败原因改成数据库异常。重复相同请求返回同一确认；第二个不同结果产生稳定冲突，不能覆盖首个意图。

已封存意图的优先级高于后来的取消、lease lost、deactivated、generic catch 和 finally；这些分支只能继续确认/记录独立处置，不能生成第二意图覆盖它。使用明确的 settlement-pending 控制信号并逐个透传，不使用继承 BaseException 的技巧绕过审查。确认后的 context 返回、成功 hook 和 marker/dependency 条件以数据库回执的实际结果为准；requested success 被原安全规则收为待对账时不能仍运行成功 hook。pending 不能伪装成已确认 success 或普通业务 failed。

业务写回、读回尚未确认时不得冻结成功。HTTP 受理、Token 回调、provider 创建订单和单一步骤成功均不是整个任务成功证据。结果形成前的日志/报告故障继续按实际业务证据分类；本批不根据局部变量或“曾有成功步骤”猜测成功。

### 4.3 提交与交权类型分开

```text
已准入的原执行责任
    → 业务运行
    → 冻结 terminal 或 defer 意图
    → 本地转换待确认 / 正在确认
    → 同一转换精确确认
    → 必要尾部义务和精确资源清理
    → 原 permit 释放确认
    → 收尾完成

身份冲突、租约失效或证据不足
    → 保留原证据并进入 fenced / reconciliation
    → 不伪造原结果已提交，不重新执行业务
```

父任务 `waiting` 继续由原生 child reconciliation 管理；它不是需要封成 success/failed 的第三种业务结果。

提交 executor 失败、future 取消、执行前准入已关闭的回退定义为 `defer` 的 `unstarted_rollback` 子型。它必须在同一责任屏障内证明 callback 尚未开始，按原 execution 原子回队并写同代回执，确认后才释放 permit；回退失败不能在 finally 提前释放。callback 已开始后禁止使用此子型。登记责任、设置 callback_started 和回退竞争使用同一同步协议。

## 5. PostgreSQL 精确回执与持久清理

### 5.1 存储选择

B 使用独立的转换回执与清理义务表，避免不断扫描 Run JSON；Run 仅保存关联引用，不复制维护多份权威结果。这里确定数据契约，不执行 DDL。

| 记录 | 最小内容与约束 |
| --- | --- |
| 转换回执 | domain、Run UUID/ID、原 execution、transition ID/type、原 ticket/permit、请求规范版本与摘要、实际存储结果摘要、提交时间、终态事件 ID/UUID、Task 投影是否仍对应原 Run |
| 清理义务 | 精确资源/permit 身份、依赖的回执、动作类型、状态、尝试次数、下次时间、稳定错误码、claim owner/token/version、确认时间 |
| 原准入 ticket | 复用 permit 元数据，保存原执行责任；不另外新建无结果 slot 表 |

一代 execution 只能进行一次最终交权，terminal 与 defer 不能各写一份。回执按原 domain/Run/execution 追加并唯一约束；另约束 transition ID，type 和 payload 摘要用于匹配校验。不能使用 `UNIQUE(run_id)`：同一 Run 可以多次 defer 后被不同 execution 认领。终态回执还要保证同 Run 只有一次有效终态转换。

请求摘要覆盖冻结的请求，不含存储层生成的时间和事件 UUID；实际结果另存完整的最小必要结果快照及摘要，保留现有远端安全分类可能将请求结果收为 `attention_required/request_unknown` 的事实。不能拿请求 success 的摘要去比较规范化后的实际结果。实际结果保存在不可变回执中，不指向随后可能被投影补充或 defer 新代更新的实时 Run JSON；旧回执有效性不因这些合法变化而消失。

回执/待办只存所需内部引用和脱敏内容，不存账号密码、OAuth token、完整远端响应或可重放的 lease token。需要跨进程清理的资源必须能从原资源记录和可信回执证明归属；无法恢复所需凭据/身份时明确待对账，不能执行宽泛删除。

### 5.2 精确确认协议

1. 首先从捕获的原数据库域读取该 transition 的权威回执。原身份、请求摘要和版本匹配即确认此前提交；该路径严格只读，不依赖已被正常删除的租约，不重新发事件、父任务收口或通知。
2. 没有回执时，进入现有锁序的事务并重新检查，处理“读完后另一个补偿者已提交”的竞争。锁后发现已有匹配回执也必须无副作用返回。
3. 首次写入必须校验原 Run/execution、原参与 ticket/未释放 permit，以及该阶段声明需要的有效原 lease。合法没有取得 lease 的 preflight、无账号任务和父编排不能被强制要求新申请一个 lease。
4. 同一事务内完成原 Run/当前 Task/终态事件/父任务/受管事实，以及新回执、清理义务和原账号 lease 的精确删除。Task 仅在 `last_run_id` 仍为原 Run 时更新。
5. COMMIT 报错或回包丢失先回读精确回执。不存在回执且原执行 fence 仍有效，才重试同一本地转换；数据库不可达则继续 pending；身份不符则停止写入并保留冲突证据。
6. 旧 defer 的确认读取匹配旧回执中的 execution，不要求当前 Run 还属于旧 execution；当前 Run 可能已被合法再次认领。旧确认绝不把它重新置回 queued。
7. 同 Run 已有别的终态、同 ID 不同摘要、旧行没有可证明本请求的回执，都不能当作本请求已成功。保留权威结果，按冲突/已被其他收口明确处置。

正常终态删除 lease 的原子性保留；不得为“幂等”省略 token。没有原 token 的分支不得按 run_id 清空其他 scope/代次的租约。

## 6. 租约、资源与执行许可的顺序

### 6.1 步骤租约和最终租约显式区分

租约记录 `held → release_pending → release_confirmed`；scope 退出与数据库确认释放分开。异常后保留原引用和 domain/run/token 身份，释放并发串行化。带原 token 的 DELETE 提交确认后，即使 0 行也可证明旧 token 不在；未知提交不能当作已删除。

每个账号 lease scope 有固定 ID、kind 与代次。同 context 最多一个活跃或释放未确认的账号 scope；未确认释放不得再 acquire。完整 registry 保留原责任，不能仅因为 `_lease` 指针为空就把丢失 token 伪装成合法 no-lease preflight。

步骤租约仍在步骤结束时释放并确认，才能执行后续步骤。最终租约保留到终态/延期转换，作为原执行 fence，再由同事务精确删除。不得把全部 `with context.lease()` 的 exit 统一延迟。

独立支付真实存在“提链 scope → 释放 → 支付 scope”；提链代理 `finish()` 仅是步骤结果。该流程必须显式标注，不能误当整个 Run 已完成，也不能因保留第一个 token 导致第二次申请自冲突。

步骤释放失败后，禁止开始下一步远端动作；有界同步确认未完成时退出业务，保存已做步骤事实并转入收尾/对账，不能落入“尚未执行业务”的普通 requeue 分支。补偿者不会从断点重新进入 handler。

步骤 DELETE 也可能已提交而回复丢失，此时没有最终 token 可供普通终态校验。新增严格受限的受阻收口分支：要求原准入 ticket、原 Run/execution、未释放 permit、原步骤身份，以及原 token 确已不在、无后继业务/新 token 的证明。若尚未形成整次执行的终态意图，只能冻结保守的 `attention_required` 与 `step_lease_release_unconfirmed`，保留已完成步骤，禁止写普通 success 或账号业务数据。它不证明此前 DELETE 曾成功，只证明旧 token 当前已不在。已有完整冻结结果绝不被替换；若其正常 fence 已不成立，转入保留原意图的独立 reconciliation disposition，明确 `original_intent_committed=false`，不得冒充同请求回执。异代或新 token 存在就拒绝，只精确清理旧 token。单纯释放未知不构造远端 `request_unknown`；释放后来成功也不自动继续下一业务步骤。

### 6.2 资源不能继续动作后才交还容量

默认依赖为：冻结结果 → 必要的安全本地清理/停止账号动作 → 原子 terminal/defer 确认及原 lease 删除 → 剩余受审计本地尾部义务 → 原 permit 释放。

handler 中已调用 finish 不代表 callback 已返回。终态可先被确认，但 callback 的真实退出、尾部工作和 cleanup carrier 都要单独计数；原 permit 不能因此提前释放。

同 family 的通用账号准入已有账号容量 scope，保留原 permit 可继续阻止相同 scope 新执行。这个结论不扩展到不同 family 或绕过准入的旧入口。任何可能继续对账号发出动作的本地句柄，须在删除最终账号 lease 前停止/隔离；不能只依赖 permit 覆盖全部入口。

浏览器、代理、邮箱、支付等资源各有自己的归属和回执。`operation_resources=reconciliation_required` 只是待对账标记，不能声称资源已释放。本批自动清理只使用已审计、限定原实例的本地动作或已有幂等清理适配器；没有安全协议的外部释放保留待对账，不新增远端自动调用。

### 6.3 许可最后确认，保留现有锁序

当前 permit release 自开短事务、先拿 admission 锁；不能在 finish 已持业务行锁时直接调用，形成反向等待。B 不把 permit release 硬塞进终态事务。

终态事务使用同连接读取/锁定原 permit 身份，不再申请 admission 锁；不得从终态持有锁反向调用准入或另一连接的 release。具体与 admission、bulk、recovery 的并发锁序必须通过定向测试。

统一收尾责任拦截 outer finally、future 回调、retry loop、`_LOCAL_EXITS` 和 permit recovery。对 participating permit，业务线程结束不等于责任结束；跨进程按原 host/PID/process_start 核验原进程，callback thread 只作诊断；本进程再核验责任 registry 与真实 cleanup carrier，不伪称业务线程仍在运行。缺失/未知责任是可观察异常，不能判为已经退出。旧 `_LOCAL_EXITS` 标记不能越过这一门；非 participating permit 保留原恢复与释放规则，不改变通用 owner_liveness 对其他领域的含义。

责任交接不得先调用现有 `release_execution()`，因为它会提前写 `_LOCAL_EXITS`。callback 已退出、责任已交接、终态已确认分别记录；协调器也不能同时操作 callback 仍拥有的句柄。进程活着但 carrier 已死或 registry 缺失时，阻止准入并保留占用，不能根据退役的 callback 线程判退出。新进程的 cleanup 扫描/claim 必须先于会释放 permit 的恢复扫描，且受同一恢复屏障保护。

确认原结果/持久交接、实际账号动作停止、必要清理完成后，才标记责任可退出，按原 permit/execution 在独立短事务释放。进程确已死亡时转入有权的恢复流程；未知主机、权限不足或仅心跳过期不算死亡证明。

## 7. owner 丢失、延期与崩溃恢复

**owner lost 关闭新业务准入，不自动否定仍有效的原 Run 本地收尾。** 当前 finish 没有检查 lifecycle owner 或 permit，只检查可选 execution/lease；不能把新的更强 ticket 合约描述成已有保护。

新设计允许准入时已登记的原责任封存其已有业务结果，并在原 execution/permit/必要 lease 仍有效时执行窄化的本地终态 CAS。不得重新获取 owner、租约、资源、执行许可，或认领其他补偿工作。原 owner 状态保持 lost、readiness 保持 false；心跳恢复不能解除 owner_lost、draining 或 settlement 阻塞。

本地 lease heartbeat 的 lost 标记不因补偿被清除。若结果已明确封存，收尾权限仍需独立核验数据库中的原 token 有效；如果结果未形成，不能用收尾模式继续业务或推断成功。原 token 已过期/变化时，只有既有精确回执可确认此前提交；没有回执就保留 fenced 证据，不能补取 token 写原 success。

| 故障时刻 | B 的承诺 |
| --- | --- |
| 原进程存活、原结果在内存、数据库恢复且原 fence 有效 | 同一 intent 本地补写和原资源收尾，无 handler/远端重放 |
| terminal/defer 已提交但回复丢失 | 读取同一回执确认，不重复事件或交权，不影响新 execution |
| 回执已提交，剩余清理时进程被杀 | 新健康 owner 按原身份、真实退出证明和新 cleanup claim 接手持久义务 |
| 数据库不可写、结果仅在内存时进程被杀 | 不保证找回原 success；沿用已持久证据保守恢复 |
| 原 execution/lease 被替换或已过期 | 不越权写成功；精确回读、保留冲突/待对账，与已有恢复协调 |

没有可信持久结果的崩溃恢复保留现有默认：心跳 stale 900 秒，并且无活跃许可、无有效 lease，还需要健康恢复者实际运行。未排除远端写入时保持 `attention_required/request_unknown`，其他按既有 `interrupted` 分类；不缩短 TTL 或 stale 阈值制造通过。

如果行政终止、取消或已有 recovery 已先完成权威收口，原请求返回 superseded，而不是伪造自己的终态回执。原责任在真实 callback/账号动作停止、精确资源清理完成并取得权威处置证明后，才允许释放自己的 permit；无法证明安全时继续保留待对账。不能因为“已不是我的结果”永久盲重试，也不能据此删除新代资源。

延期成功继续使用原 Run 和原单续查；回执确认后释放旧代资源，由现有合法 dispatcher 继续。父子 waiting、child 重试新建父 Run、partial_success、依赖快速完成竞态均保留原语义。补偿不重放 child 业务；既有 child 身份的依赖登记和第 9 节已声明的本地 followup 投递分别处理。

## 8. 运行时、退出与重试边界

统一收尾组件作为现有 ManagedRuntime 的受管服务，在正常业务期间就运行，并在关闭业务 executor 前能够推进 pending；不能只放到当前 idle 之后的 `settle()`，否则会互相等待。

准入/执行责任向收尾责任的交接和 active 计数下降使用同一屏障，避免“业务计数已 0、pending 尚未登记”的空窗。participating permit 的原释放 daemon 职责并入该组件，不保留两个互相竞争的后台释放循环；非 participating 的旧释放重试明确分流保留，并继续如实计入它自身的停止责任，不能顺带丢弃。

停止沿用第一次信号的总截止时间：

1. 关闭新准入，停止 producer/claimer；已有业务、收尾和必需支持继续。
2. 等待业务及本进程 pending 一起排空；然后真实 join executor，核验交接屏障。
3. 运行投影收口并停止其他组件，收尾组件仍可接收这些 stop hook 产生的本地清理。
4. 再次排空收尾，停止并 join 其真实线程，确认所有 finalizer/retry 线程完成。现有 dependency/followup 若已确认持久交权、没有剩余物理资源和执行责任，可由未来健康 owner 继续投递；它从本进程 owned 计数移交，不宣称全局待办为 0。阻塞资源、未确认终态和仅在内存的结果不能这样移交。
5. 完成 export/heartbeat，关闭池和 owner。未确认的工作、活线程或期限耗尽均返回 `stop_incomplete`，不得假报干净退出。

增加独立整数计数：terminal/defer 待确认、资源待确认、permit 待释放、补偿 inflight、尚未持久化。状态还需年龄、稳定错误码和恢复阶段，沿本地/远端 Worker 状态、heartbeat 与 `/readyz` 传递；不能只存在内部队列。`/healthz` 继续表示进程存活。

初始采用保守准入策略：存在未确认/受阻收尾时阻止新业务准入；收尾线程可继续工作。采用单个受管消费者、有界内存索引、按需分页和退避，不为每项创建线程；持久待办按状态/到期时间索引，不全表扫描。短队列满时先持久化并待扫描，不丢弃；无法持久化时保留真实占用和异常，不伪装 durable。

本机 55 秒是共享总预算，每次尝试、重试及重复 stop 不获得新预算。B 需要为**收尾所调用的存储路径**补可传递截止时间：有界借池/建连、事务内 statement/lock timeout、回滚和连接状态恢复，不能每个剩余时间创建新池。不能把 Python join 返回视为 SQL/网络 I/O 已终止；未退出线程仍使停止不完整。承诺是在期限内返回真实停止结果，不能承诺任何不可中断业务线程都能使整个解释器在 55 秒内退出；60 秒管理器强制结束与应用正常退出分别验收。

这项有限的 deadline 支持属于 B 必要范围；不等于已经解决 F18 的全项目普通 SQL 等待问题，也不自动更改所有业务查询的超时策略。

## 9. 必须覆盖的入口及不扩大的范围

| 类别 | B 的必要范围 |
| --- | --- |
| 通用 Operation | context finish/defer、全部 lease scope、gateway 异常优先级、execute_admitted、future 回调及原 domain 捕获 |
| 存储/运行时 | 回执和清理 schema/facade、terminal/requeue 精确协议、permit 责任/恢复、受管补偿、状态传播与停止顺序 |
| 账号查询/配置/巡检/换邮等通用 handler | 保留原业务分类，审核 finish 外层 catch 和 scope；不能因 settlement pending 进入失败、重排队或二次 finish |
| Codex | 原生 refresh 的 scope/catch/终态后 marker；旧 direct guard 共享精确释放和统一责任，不再绕过许可保护 |
| 提链/支付 | provider/legacy finish 外层 catch、显式步骤与最终 scope、defer、多代续查、提链代理结果；订单创建、付款、到账确认仍分开 |
| 补全/父子 | 无账号 lease 的编排、已有持久 handoff/dependency、partial/waiting、新父 Run、终态后必要义务 |
| 注册、Butler、Sentinel 旧路径 | 验证共享 permit、owner、drain 和状态接口兼容；未接入统一 context 的领域收尾不宣称已完成迁移 |

终态后仍存在的 marker、依赖或本地业务写回必须逐一处理：必要业务写回在明确结果屏障前确认；已有 child/handoff 使用精确持久引用；允许延后的本地义务以原 Run/version CAS 注册。不能把这些动作作为无身份的匿名 callable 交给补偿，也不能简单把所有后置动作前移或自动重做。

具体白名单仅保留现有行为：

- completion 已经得到 child ID 后的依赖登记，必须在父结果冻结前声明原 child/source/payload，并同事务保存幂等登记义务，不再次 enqueue 该 child。持久责任必须覆盖普通 native 及 bulk；不能把当前仅 bulk 使用的 save_handoff 当作普通父任务已有耐久交接。
- Codex 终态后的 refresh marker 清理，只能按原 credential 引用、Run/version CAS，不能清掉新任务已写的 marker。本批需要补原版本条件；当前只按 filename 的清理 helper 不具备这项保证，不能直接作为跨代补偿调用。
- 提链现有付款后套餐核验：在结果冻结前声明是否需要投递，并与终态同事务存原条件、trigger 和既有 `extract-workbench:{task_id}:payment-success` 幂等键。健康 owner 经现有本地 enqueue/dispatcher 投递一次；原 lost owner 仅保存义务，不创建执行或调用远端。套餐子任务、付款、Plus 确认仍是独立事实。provider 状态回写也按原 Run/version 确认，不能覆盖新轮。

这项本地投递是现有步骤的可靠交权，属于 B 明确提出的适配范围；不是允许任意 cleanup job 创建业务任务。没有在冻结前声明的后续动作不在白名单中。需 Token 等私密数据时只保存已有账号/凭据引用，由原入口读取，不把秘密复制到回执。

原有 HTTP 接口、业务状态枚举、任务步骤、远端请求及 UI 布局不随本方案改变。新增技术状态内部可观测，不在列表加入一组未经讨论的新业务状态。

## 10. 验收及交付方式

批准 B 后可并行准备四条边界清楚的工作线：存储回执/清理、context/领域兼容、permit/运行时、故障夹具/独立审查。先冻结接口，再分文件写入；真实 PG 和性能测量由 root 串行调度，避免并发测试互相污染。这里是实施切片建议，尚未启动产品实现。

必须覆盖原生方法确定性故障、独立 PG 的事务与回包丢失、固定端点真实重启、进程 kill/replacement、55 秒停止和原有 child/defer 回归。每例核对原 Task/Run/execution、唯一回执/事件、业务 callback/远端调用次数、原 token/permit、其他代次不变、真实线程和退出回执。

| 必测组 | 通过条件 |
| --- | --- |
| 真实 F16 | DB 恢复后原进程按同一意图收口、原 lease/permit 和本进程 pending 为 0；不靠默认 900 秒 orphan recovery 替代实时补偿 |
| 提交回复丢失/并发重复 | 精确同回执；不要求已删除 lease；不重复事件、事实、父任务或业务 |
| 结果保护 | success/failed/cancelled/request_unknown 不被技术异常替换；嵌套 payload 后续修改不改变冻结结果 |
| 资源/容量 | 释放失败可重试；旧 token 晚到不删新 token；callback 退出不提前释放补偿占用；没有仅凭 permit=0 的通过 |
| 旧代/恢复竞争 | ownerlost 仅处理原责任；旧 Run 不覆盖新 Task 投影；lease 过期、摘要冲突不绕 fence |
| 交接 | defer 多代、父 waiting、child 重试、独立支付多 scope 和关键尾部义务语义一致 |
| 停止/持续故障 | 两次排空屏障、真实 join、同一 55 秒预算；不完整如实失败，保留事实和诊断 |
| 崩溃 | 持久化前保守恢复、持久化后精确补偿分别验收，不能合并成一种“自动恢复通过” |
| 成本与兼容 | 现有组合/分离运行方式和旧入口回归；用三十万/五十万历史规模检查新索引/待办扫描和有限批次成本，不先承诺性能指标 |

执行前部署顺序只准备为设计约束：先 schema/读取兼容，再启用新 ticket/回执。启用前要求同一执行域排空旧工作、停止旧执行进程及其自动拉起服务，再以唯一新 owner 启用；不允许新旧 Worker 混跑。持久化协议版本与所需能力，启动读到不支持的版本时拒绝执行；真正不认识此闸门的旧二进制必须由服务/发布闸门阻止启动，不能指望它自行拒绝。回退需先停止新 owner、排空未完责任/许可/清理义务并确认兼容，或保留禁止旧版本消费的围栏；有未完待办时不得直接用旧 Worker 回退。已完成历史回执保留，不要求删除新表历史来“排空”。实际部署仍另行讨论。

当前 F16 仍为失败，第六阶段仍未完成。分析完成与修复完成分别汇报；B 的实现、定向测试、真实恢复、整组回归和部署也分别验收。

## 11. 分专题分析与证据

以下是本轮只读核验报告；主稿已统一选择与边界，分稿中的替代选项或早期建议不自动进入方案：

- [业务结果](</Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/settlement-design/business.md>)、[终态与延期](</Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/settlement-design/outcome.md>)。
- [存储与锁序](</Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/settlement-design/storage.md>)、[租约与多步骤](</Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/settlement-design/leases.md>)。
- [运行时和停止](</Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/settlement-design/runtime.md>)、[崩溃与持久性](</Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/settlement-design/crash.md>)。
- [恢复反向审查](</Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/settlement-design/recovery-review.md>)、[故障验收矩阵](</Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-predeploy-20261117/settlement-design/acceptance.md>)。
