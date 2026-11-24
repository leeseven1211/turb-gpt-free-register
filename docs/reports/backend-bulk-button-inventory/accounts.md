# 账号域按钮与批量执行审计

审计日期：2026-11-24。根目录：`/Users/lihongwei/code/personal/gpt/turb-gpt-free-register`。只读检查当前工作区源码；开始时工作区已有大量用户修改（含 `setupActions.ts`、`useAccountEmailChange.ts`、`useC2aReimport.ts`、账号 bridge），以下结论对应当前磁盘内容。未修改仓库、未提交、未启动服务、未运行测试、未调用任何业务写接口。

## 判定口径与结论

- “一次请求”只指点击后一次业务提交，不把确认框、列表刷新、状态轮询、任务页查询计作逐账号提交。`Promise.all`/并发请求不等于真正批量。
- 统一 bulk 节点指 `core/bulk_operations` 的 batch/round/target 与原生批量目标编排；`operation_batches` 是已有运行批次；`account_action_batches` 是兼容汇总。三者不能混同。
- 本域当前已显示的批量业务动作均由前端一次数组 POST 提交，未发现账号 Vue 在前端循环 N 次业务 POST。大量逐条开销发生在后端读取、校验、建 durable task、事务及调度唤醒。
- **邮箱换绑、补 Codex、巡检有原生运行批次，但仍未成为统一 bulk 节点。** 换绑和补 Codex逐目标建任务且分别提交事务，最后统一唤醒；巡检同事务创建父任务和所有子任务，但逐条 SQL。
- **查活、查套餐、刷新 AT、提链、封号邮件的返回 `batch_id` 来自兼容 `account_action_batches`，通常不能关联原生 batch。** `core/account_task_store.py:1` 直接别名到 `legacy_task_store`；其 `create_batch:257` 产生 `uuid.uuid4().hex`。native 边界 `_numeric_batch_id` 只接受十进制字符串：`liveness/service.py:2214`、`plans/service.py:1088`、`extract_link/service.py:1850`、`deactivation/mail_scan.py:694`。通常含 a–f 的 UUID 会变成 `None`。这不是统一 bulk 节点，也不能仅凭响应有 `batch_id` 判为已有原生批次。
- **iCloud HME 封号邮件扫描已有真正共享扫描例外**：多个账号合为一个 durable run，读取一次共享邮箱，按别名分发结果；非 HME 仍逐账号任务。这个已有聚合能力应在后续整理方案中保留。
- 归档、删除、删除已废已有数据库集合 SQL；缺少节点≠逐条处理。邮箱失效标记同事务操作多个表，但逐行锁/写，属于数组接口但逐条数据库变更。

## 公共入口与源码约定

下表路径以仓库根为基准，冒号后是可复查的一基行号。缩写：`F=frontend/src/features/accounts/`，`R=webui/routes/accounts.py`，`L=webui/static/js/pages/accounts/page.js`。

动态工具栏的全部 34 个业务动作定义在 `F/accountToolbar.ts:8`；所有动作同时可能出现在“批量操作”菜单与按浏览器使用次数排序的五个常用按钮（`F/AccountsToolbar.vue:88–100`；`F/useAccountQuickActions.ts:3–12,32–35`）。二者是同一动作的多个 UI 位置，下面按语义合并。通用派发为 `AccountsToolbar.invoke:58` → `AccountsPageShell.invoke:53` → `actions.invoke:114` 或 legacy `invokeAccountAction:1689`；计数器只写 localStorage，不创建业务任务。

现代表格仍使用 legacy presenter：`F/presentation.ts:58–107` 把 `L` 的 cell/menu 转成 Vue `v-html`；`F/AccountsTable.vue:31–38,64–72` 统一事件委托；`F/presentation.ts:112–126` 识别动态 data 属性。因此下表中的 `L` 动态按钮仍是当前现代 UI 入口，不能当作废弃旧界面遗漏。

## 一、工具栏全部批量动作（34 个）

| 按钮/入口 | 处理函数 | API 与前端请求数 | 后端 bulk/batch/node/target 及逐条情况 | 归类与源码 |
|---|---|---|---|---|
| 查活；工具栏菜单/常用，行更多同语义 | `createQueuedAccountActions.invoke` kind=live | `POST /api/accounts/check-live-bulk {account_ids,driver}`，1 次；行更多也发单元素数组 | 路由先 `ANY` 一次读取账号，再逐账号 `enqueue_account_live_check`；service 再逐账号读账号、claim、建 task/run、逐次事务和唤醒。仅兼容批次，通常未关联原生 batch；无统一 bulk target/node。外部 Token 验证需按各账号凭证执行，可共享多目标编排 | **数组接口但逐条**；`F/accountToolbar.ts:9`，`F/queuedActions.ts:206–218`；`R:1017–1115`（循环1077）；`core/accounts/liveness/service.py:2627–2739,2447–2495` |
| 查套餐；工具栏，行更多“查套餐” | queued kind=plan | 工具栏 `POST /api/accounts/check-plan-bulk`，1 次；单行 `/api/accounts/check-plan`，1 次 | `ANY` 一次初读，但逐账号 service 再读、claim、native task 事务。兼容批次 UUID 转 numeric 失配。每账号套餐/优惠外部查询是账户业务，未实现统一多目标节点 | **数组接口但逐条**；`F/accountToolbar.ts:10`，`F/queuedActions.ts:190–205`；`L:964–972,1159`；`R:1204–1243,1245–1332`（循环1304）；`core/accounts/plans/service.py:1252–1358` |
| 刷新 AT；工具栏/行更多 | queued kind=token | `POST /api/accounts/refresh-token-bulk`，1 次；可先读缓存配置 `/api/config` | `ANY` 初读后逐账号 liveness enqueue(force_refresh=True)，各自读/claim/task/事务；兼容批次失配。登录、OTP、刷新必须按账号执行，批量目标编排可集中 | **数组接口但逐条**；`F/accountToolbar.ts:11`，`F/queuedActions.ts:220–238`；`L:1155`；`R:1117–1202`（1167）；`core/accounts/liveness/service.py:2627–2739` |
| 批量同步到 C2A（弹窗“提交并入队”） | `reimportSelectedC2a` → `useC2aReimport.open/submit` | 打开0次；确认 `POST /api/accounts/c2a/sync-bulk`，1 次 | 路由循环 `db.get_account` → `manual_sync.queue_account`，各自 UUID → durable task；无 batch/parent/bulk target，逐条读和事务。执行时各账号读取当前 AT、定位远端、写入/确认；非前端逐条 | **数组接口但逐条**；`F/accountToolbar.ts:12`；`F/C2aReimport.vue:44,66–67`；`F/useC2aReimport.ts:29–34,47–64`；`R:1599–1685`（1619/1642）；`core/integrations/c2a/manual_sync.py:97–121,360–429` |
| 批量换绑邮箱（弹窗“开始换绑”） | `openBulkEmailChangeForSelectedAccounts` → `useAccountEmailChange.openBulk/submit` | 打开1次 `GET /api/email-sources`；确认1次 `POST /api/accounts/email-change-bulk` | **已有 `operation_batches`**，逐账号 `submit_email_change(dispatch=False,batch_ordinal)`，每次单独读/校验/提交 task，再最终 `notify_dispatch`；无统一 bulk node/target。邮箱领取、OTP、换绑、成功后的查活子任务需每账号执行 | **已有批次，建任务仍逐条**；`F/accountToolbar.ts:13`；`F/EmailChange.vue:84–97`；`F/useAccountEmailChange.ts:68–97,108–112,118–149`；`R:422–440`；`core/accounts/email_change/service.py:1539–1611,1614–1674,1467` |
| 查封号邮件；工具栏/行内“复查” | queued kind=mail | 批量 `POST /api/accounts/check-deactivation-mail-bulk`，1次；行 `/api/accounts/<id>/check-deactivation-mail`，1次 | 兼容 batch；`enqueue_bulk` 逐账号读。**HME 多别名共享1任务/1次邮箱扫描**；非HME逐账号 `_submit_native_scan`、逐事务、逐账号状态写回。HME完成仍逐别名写结果。无统一 bulk target | **数组接口但逐条；HME 已有聚合扫描**；`F/accountToolbar.ts:14`，`F/queuedActions.ts:240–250`；`L:1100–1134`；`R:591–652`；`core/accounts/deactivation/mail_scan.py:912–1047,861–908,449–566` |
| 补密码 | `addPasswordSelectedAccounts` → setup invoke action=password | `POST /api/accounts/action-bulk {account_ids,action:'password'}`，1次；行 `/api/accounts/<id>/action` | 路由逐账号 `_account_action_result` → coordinator `enqueue_account_setup`；每账号独立读、配置快照/计划、capability、native submit；无批次/target/node。远端密码认证是每账号步骤 | **数组接口但逐条**；`F/accountToolbar.ts:15`，`F/setupActions.ts:29–31,157–162`；`L:1147`；`R:441–461,529–570`（544）；`core/accounts/operation_coordinator.py:53–153` |
| 补 2FA；含行内2FA“补充”/行更多 | setup action=twofa | `/api/accounts/action-bulk {action:'twofa'}` 1次；单行 `<id>/action` 1次 | 同上，无统一批次；每账号 2FA 认证/启用需独立执行 | **数组接口但逐条**；`F/accountToolbar.ts:16`，`F/setupActions.ts:25–31,157–162`；`L:1080–1086,1148`；`R:447,529–570`；`core/accounts/operation_coordinator.py:53–153` |
| 修改密码 | setup action=password_change | `/api/accounts/action-bulk` 1次；单行 `<id>/action` 1次；批量上限20 | 路由循环单账号 coordinator（强制密码重置）；无 batch/node。不能把后续外部忘记密码流程合并成一次共享账号操作 | **数组接口但逐条**；`F/accountToolbar.ts:17`，`F/setupActions.ts:133–135,157–162`；`L:1149`；`R:448–456,538,544–553`；`core/accounts/operation_coordinator.py:53–153` |
| 修改 2FA | setup action=twofa_change | 同上，1次数组POST，上限20 | 每账号单任务/事务，强制旧2FA关闭后开新2FA；无batch/node | **数组接口但逐条**；`F/accountToolbar.ts:18`；`F/setupActions.ts:133–135,157–162`；`L:1150`；`R:457–464,538–553`；`core/accounts/operation_coordinator.py:53–153` |
| 补全账号 | setup action=complete | 当前按钮实际 `/api/accounts/action-bulk {action:'complete'}` 1次；单行 `<id>/action` | 逐账号 `enqueue_account_completion`，各自查注册任务、算缺失步骤、建协调任务；无同次点击总批次。账号内会按计划编排多个步骤，这与多账号批量节点不同。另有 `/complete-bulk` 兼容接口，当前按钮未走它 | **数组接口但逐条**；`F/accountToolbar.ts:19`；`F/setupActions.ts:157–162`；`L:1151`；`R:465,487–527,529–570`；`core/accounts/operation_coordinator.py:155–235` |
| 重跑注册；行更多重跑 | `retryAccountRegistration` / setup isRetry | 多目标 `/api/accounts/registration-retry-bulk` 1次；只有1个目标改走 `<id>/registration-retry` 1次 | `retry_accounts` 先批量投影原注册来源，再逐账号 `registration_service.retry_job(source_job_id)`；沿用原任务/产生续跑，无本次点击的统一 batch/target。保留每账号来源和重跑链路，不能以此要求改注册流程 | **数组接口但逐条**；`F/accountToolbar.ts:20`；`F/setupActions.ts:183–192`；`L:1138–1142`；`R:246–266`；`core/accounts/registration_retry.py:189–229` |
| 补 Codex；行更多“补跑/重跑 Codex” | setup retrySelectedCodex/codex-retry | 批量 `POST /api/codex/retry-bulk {account_ids}` 1次；行 `/api/codex/retry {email}` 1次 | **已有 `operation_batches`**；`operation_service.submit_bulk` 逐账号读→`submit(...batch_id,ordinal,dispatch=False)`，分别事务，最后 `_dispatch_bulk`。无统一 bulk target。每账号 OAuth/OTP/手机验证需独立业务执行 | **已有批次，建任务仍逐条**；`F/accountToolbar.ts:21`，`F/setupActions.ts:163–173`；`L:1011–1020,1165`；`webui/routes/codex.py:538–557,559–624`；`core/codex/operation_service.py:705–766` |
| 提链；行更多“提链” | queued kind=extract | 批量 `POST /api/accounts/extract-link-bulk` 1次；单行 `/api/accounts/extract-link {account_id}` 1次 | 路由逐账号 `db.get_account` 资格筛选，再逐账号 enqueue→再读→claim→native task→更新账号；兼容 batch失配；无统一 bulk target。后续每账号向提链平台调用属外部业务分项 | **数组接口但逐条**；`F/accountToolbar.ts:22`，`F/queuedActions.ts:252–264`；`L:1001–1009,1160`；`R:1391–1481`；`core/extract_link/service.py:4420–4534` |
| 按当前筛选创建批次 | legacy `invokeAccountAction` → `BulkTasks.fromAccounts(false,'plan_check',snapshot)` | 当前点击0次业务提交，只预填/打开创建批次页；后续预览/确认由批量页控制 | 这是通往真正 `core/bulk_operations` batch/round/targets 的入口，但点击本身未创建批次。不能误认为直接“查套餐”等已自动转到此入口 | **纯交互；后续已有批次入口**；`F/accountToolbar.ts:23`；`L:1699`；`frontend/src/features/bulk/BulkPageShell.vue:66–75`；后续 `core/bulk_operations/service.py:160` |
| 用已选账号创建批次 | 同上 `fromAccounts(true,...)` | 0次业务提交，复制已选ID到批量页草稿 | 同上；跨页选择作为显式目标源；当前点击无逐条读/任务 | **纯交互；后续已有批次入口**；`F/accountToolbar.ts:24`；`L:1699`；`frontend/src/features/bulk/BulkPageShell.vue:71–75` |
| 一键巡检（打开启动窗口）→开始巡检 | `useAccountInspection.openStart/submit` | 打开0次；确认 `POST /api/accounts/inspections {workers,archived,idempotency_key}` 1次 | **已有原生 batch+父任务+账号子任务**，全部同事务快照；一次集合 SELECT FOR UPDATE 后逐账号查活跃run并多条INSERT task/run/batch_item，无统一 bulk target/node。AT本地有效无需网络，失效账号逐个刷新并复用会话查套餐 | **已有批次，事务内逐条创建**；`F/accountToolbar.ts:25`；`F/Inspection.vue:42–52`；`F/useAccountInspection.ts:48–62`；`R:123–142`；`core/accounts/inspection/service.py:146–158,31–103`；`core/storage/accounts/inspections.py:39–99` |
| 巡检历史 | `useAccountInspection.openHistory/refreshHistory` | `GET /api/accounts/inspections?page=1`，1次；打开后5秒轮询 | 分页只读巡检父任务和进度，不创建业务任务 | **纯交互只读**；`F/accountToolbar.ts:26`；`F/useAccountInspection.ts:64–80,114`；`R:114–121` |
| 复制 Token | actions bulkCopies `field=access_token` | `POST /api/accounts/secret-bulk` 1次 | 路由循环 `db.get_account` 读取 N 个账号；无任务/批次；返回值客户端一次拼接/复制 | **数组接口但逐条读取**；`F/accountToolbar.ts:27`；`F/actions.ts:43,109–112,137–141`；`R:687–721` |
| 复制行 | actions `field=account_credentials_line` | secret-bulk 1次 | 同上，N次账号读；与单行菜单 `copy_line` 字段不同，应保留字段语义 | **数组接口但逐条读取**；`F/accountToolbar.ts:28`；`F/actions.ts:44,109–112,137–141`；`R:687–721` |
| 复制提炼地址 | actions `field=extract_link` | secret-bulk 1次 | 同上，N次账号读；单行成功地址已有本地 cbtn 可0请求复制 | **数组接口但逐条读取**；`F/accountToolbar.ts:29`；`F/actions.ts:46,109–112`；`R:687–721`；`L:1161–1164` |
| 复制邮箱 | actions `field=email` | secret-bulk 1次 | 即使客户端有邮箱快照，当前实现仍走服务端逐账号取值；无任务 | **数组接口但逐条读取**；`F/accountToolbar.ts:30`；`F/actions.ts:45,109–112`；`R:687–721` |
| 复制密码 | actions `field=account_password_line` | secret-bulk 1次 | N次账号读取，缺失跳过；不启动补密码流程 | **数组接口但逐条读取**；`F/accountToolbar.ts:31`；`F/actions.ts:47,109–112`；`R:687–721` |
| 复制 2FA 密钥 | actions `field=totp_secret` | secret-bulk 1次 | N次账号读取；本按钮是密钥，不是每账号当前6位TOTP；无任务 | **数组接口但逐条读取**；`F/accountToolbar.ts:32`；`F/actions.ts:48,109–112`；`R:687–721` |
| 下载 TXT | actions downloadSelectedAccountTxt | secret-bulk `field=copy_line` 1次，浏览器 Blob下载0服务请求 | 后端N次读取；客户端一次拼接/生成文件，无批次 | **数组接口但逐条读取**；`F/accountToolbar.ts:33`；`F/actions.ts:153–159`；`R:687–721`；`F/browserDownloads.ts:21–23` |
| 下载 Session | actions downloadSelectedAccountSessions | `POST /api/accounts/download-session-bulk {prepare:true}` 1次 + 下载 URL GET 1次，与N无关 | 路由循环 `record_store.get_row` 每账号读取完整Session、检查、写ZIP entry；无持久批次/任务；下载暂存文件也不是任务节点 | **数组接口但逐条读取**；`F/accountToolbar.ts:34`；`F/actions.ts:160–165`；`R:723–803`（740）；`F/browserDownloads.ts:25–31` |
| 标记邮箱失效；含行更多同语义 | localMutations emailInvalid | `POST /api/accounts/email-invalid-bulk {account_ids,invalid:true,reason,expected_emails}` 1次；行亦单元素数组 | 单事务内集合读取账号/池/分配，再逐绑定和母资源锁、逐账号/分配/池 `patch_row`；无任务、外部邮件调用、bulk节点。原子事务≠一条批量写 | **数组接口但逐条写，同事务**；`F/accountToolbar.ts:35`；`F/localMutations.ts:53–63`；`R:805–872`；`core/storage/email/validity.py:103–235`（写循环211起） |
| 解除邮箱失效；含行更多 | 同上 invalid=false | 同上1次 | 同上；不是恢复OpenAI账号状态 | **数组接口但逐条写，同事务**；`F/accountToolbar.ts:36`；`F/localMutations.ts:53–63`；`R:805–872`；`core/storage/email/validity.py:103–235` |
| 下载 CPA | actions downloadSelectedCpa | `POST /api/accounts/download-cpa-bulk {prepare:true}` 1次 + 下载GET1次 | 先1次远端list auth-files、1次本地Codex列表，然后逐账号 `db.get_account`、匹配、远端下载、写ZIP、标导出。主HTTP内同步串行，未持久化任务/节点。各文件下载是外部实际分项，但本地取账号可集合化 | **数组接口但逐条读取/外部下载**；`F/accountToolbar.ts:37`；`F/actions.ts:166–173`；`R:1732–1897`（1762、1789、1822、1843） |
| 上传 sub2 | setup uploadSelectedCodexSub2 | `POST /api/accounts/codex/upload-sub2-bulk {account_ids}` 1次 | 路由逐账号读，`manual_upload.queue_account` 再按邮箱读凭证，再 `queue_filename` 多次本地读/校验，逐账号 durable task/事务，无 batch/parent/target。worker每账号上传1份凭证 | **数组接口但逐条**；`F/accountToolbar.ts:38`；`F/setupActions.ts:174–182`；`R:1504–1562`（1521）；`core/integrations/sub2api/manual_upload.py:48–108,151–181` |
| 停止 Codex | setup stopSelectedCodex | `POST /api/codex/stop-bulk {account_ids}` 1次 | 先逐id查账号转邮箱，再逐邮箱再查账号/是否补跑/`request_cancel`，逐run取消，无统一批次取消命令 | **数组接口但逐条**；`F/accountToolbar.ts:39`；`F/setupActions.ts:168–173`；`webui/routes/codex.py:454–496`（464/479） |
| 归档选中／归档页“恢复选中” | localMutations archiveSelectedAccounts | `POST /api/accounts/archive-bulk {account_ids,archived}` 1次 | 已有集合 `UPDATE ... WHERE id=ANY RETURNING`，一次事务；不是逐账号SQL。无持久任务/bulk节点 | **已有集合批量，无节点**；`F/accountToolbar.ts:40`；`F/AccountsToolbar.vue:25`；`F/localMutations.ts:77–86`；`R:903–925`；`core/storage/db_legacy.py:2456–2487`；`core/storage/records.py:1560–1584` |
| 删除选中 | localMutations deleteSelectedAccounts | `POST /api/accounts/delete-bulk {account_ids}` 1次 | 集合 `DELETE ... WHERE id=ANY RETURNING`；一次事务，无任务/节点 | **已有集合批量，无节点**；`F/accountToolbar.ts:41`；`F/localMutations.ts:77–86`；`R:938–971`；`core/storage/db_legacy.py:2500–2529`；`core/storage/records.py:1671` |
| 删除已废（整个归档范围） | localMutations deleteDeactivatedAccounts | `POST /api/accounts/delete-deactivated {archived}` 1次 | 服务端按范围集合DELETE RETURNING，不受当前页/勾选/高级搜索影响；无逐条SQL/任务 | **已有集合批量，无节点**；`F/accountToolbar.ts:42`；`F/localMutations.ts:64–69`；`R:165–176`；`core/storage/accounts/inspections.py:270–282` |

## 二、行内、行更多、详情及其余账号语义动作

上表已合并行更多的查活、刷新AT、套餐、提链、补密码/2FA/修改/补全、注册重跑、补/停止Codex、换绑、邮箱失效。下表补齐其单条实现和纯交互按钮。

| 按钮/入口 | 处理函数 | API / 前端请求数 | 后端/批量情况 | 归类与源码 |
|---|---|---|---|---|
| 行内 Token 状态（复制Token） | `account-copy-secret:access_token` → actions.invoke | `GET /api/accounts/<id>/secret?field=access_token` 1次 | 单账号读，剪贴板；无批次 | **单条只读**；`L:1052–1058`；`F/actions.ts:142–146`；`R:652–665` |
| 行内“复制”账号密码／更多“复制账号密码” | `account-copy-secret:account_password` | `<id>/secret?field=account_password` 1次 | 单账号读；无远端认证 | **单条只读**；`L:1060–1066,1146`；`F/actions.ts:142–146`；`R:652–665` |
| 行更多“复制整行” | `account-copy-secret:copy_line` | `<id>/secret?field=copy_line` 1次 | 单账号读取，和批量“复制行”的字段不同 | **单条只读**；`L:1144`；`F/actions.ts:142–146`；`R:652–665` |
| 行更多“复制 ChatGPT session” | `account-copy-secret:chatgpt_session` | `<id>/secret?field=chatgpt_session` 1次 | `db.get_account` 后单独读取 Session；无登录/刷新任务 | **单条只读**；`L:1145`；`F/actions.ts:142–146`；`R:194–200,652–665` |
| 行内2FA“复制”（当前6位TOTP） | `account-totp-copy` | `GET /api/accounts/<id>/totp-code` 1次 | 单账号读取本地密钥，服务端本地计算验证码；无外部请求/任务 | **单条只读**；`L:1080–1086`；`F/actions.ts:147–152`；`R:666–685` |
| 行更多“复制提炼地址” | `copy-id:<local key>` → `copyText(copyStore.get(value))` | 0次 | 使用已加载内容，纯剪贴板 | **纯交互只读**；`L:1161–1164,1742`；`F/presentation.ts:116,124–126` |
| 账号邮箱／详情／窄屏行点击 | `AccountsTable.handleRowClick` → AccountsList.detail → useAccountDetail.open/read | 通常 `GET <id>/plan-details` 1次（consumer合并/缓存）之后 `GET <id>/roxy-profile` 1次；无N目标 | 单账号只读；后者还可能查本地历史profile，再向Roxy读取当前窗口名称；详情正文无业务动作按钮 | **单条只读**；`F/AccountsTable.vue:31–38,67,71`；`F/AccountsList.vue:49–56`；`F/useAccountDetail.ts:52–72`；`frontend/src/api/accounts.ts:55–62`；`frontend/src/api/accountDetail.ts:13–24`；`R:268–295,306–319`；`L:1251–1313` |
| 行更多“已解封，恢复账号” | localMutations `account-restore` | `POST /api/accounts/<id>/restore` 1次 | 单条本地恢复状态，凭证需要后续重新验证；无批次 | **单条业务**；`L:1156`；`F/localMutations.ts:70–75`；`R:874–896` |
| 行更多“归档”／“恢复”（归档账号） | localMutations `account-archive:1/0` | `POST /api/accounts/<id>/archive` 1次 | 单条 patch；与批量集合SQL区分 | **单条业务**；`L:1166`；`F/localMutations.ts:77–86`；`R:896–902`；`core/storage/db_legacy.py:2445–2453` |
| 行更多“删除账号” | localMutations `account-delete` | `POST /api/accounts/<id>/delete` 1次 | 单条委派集合删除函数；无批次 | **单条业务**；`L:1167`；`F/localMutations.ts:77–86`；`R:929–936`；`core/storage/db_legacy.py:2490–2497` |
| 行更多“任务记录” | legacy invoke `account-task-history` → `TaskCenter.open` | 本按钮0次业务写；任务页统一GET查询 | 按邮箱筛选任务中心，无逐账号提交 | **纯交互只读**；`L:1158,1737` |
| 行更多“查看进行中的注册任务” | setup `account-registration-task:<job_id>` → openRegistrationTasks | 0次业务提交；单条任务详情/日志读由TaskCenter或原job日志承担 | 只导航，不能误计为重跑 | **纯交互只读**；`L:1138–1140`；`F/setupActions.ts:92–98,125` |
| 行更多“停止补跑”／“补跑Codex” | setup `codex-stop` / `codex-retry` | `/api/codex/stop` / `/api/codex/retry` 各1次 | 单条取消/入队；批量入口见上一表 | **单条业务**；`L:1011–1020`；`F/setupActions.ts:163–167`；`webui/routes/codex.py:440–452,538–557` |
| 行“更多” | PopoverRoot/openAction | 0次 | 展示同一账号动作菜单 | **纯交互**；`F/AccountsTable.vue:21,40,72` |
| 批量操作菜单／常用按钮排序 | details onToggle/dismiss；usage.record | 0次业务请求 | 展开折叠/localStorage计数；常用按钮重用同一动作 | **纯交互**；`F/AccountsToolbar.vue:39–64,88–100`；`F/useAccountQuickActions.ts:23–39` |
| 单行选择／当前页全选（含跨页保留） | list.toggle/togglePage | 0次 | 遍历当前页只更新本地Set与邮箱快照，无业务任务/请求 | **纯交互**；`F/AccountsTable.vue:59,65`；`F/useAccounts.ts:286–306` |
| 清筛／清空搜索／移除筛选标签／筛选列“全部/完成/清除此列” | list.resetFilters/clearSearch；AccountsList.clearFilter；AccountFilters.clear/toggle | 改变query触发一次分页GET（输入可能debounce）；完成/仅开关0次 | 列表只读，非账号批量动作；不用N次单账号请求 | **纯交互只读**；`F/AccountsList.vue:25–35,60,78–85`；`F/AccountFilters.vue:16–29`；`F/useAccounts.ts:138–161,240–282`；`frontend/src/api/accounts.ts:39–45` |
| 刷新／数据加载失败“重试”／空表“重试” | list.refresh | `GET /api/accounts?...` 通常1次；越界页修正允许最多额外2次整页查询 | 页面级分页/聚合查询，非N次账号读 | **纯交互只读**；`F/AccountsList.vue:85,90–91`；`F/AccountsTable.vue:74`；`F/useAccounts.ts:138–162`；`R:204–244` |
| 恢复列宽／列拖拽与键盘调整 | resetColumns/useColumnWidths | 0次 | localStorage/界面状态 | **纯交互**；`F/AccountsList.vue:61,85`；`F/AccountsTable.vue:17–20,62` |
| 列表分页／页容量 | list.setPage/setSize | 每次1次整页GET，越界修正例外同上 | 分页读取，无批量业务 | **纯交互只读**；`F/AccountsList.vue:92`；`F/useAccounts.ts:138–161` |
| 活跃账号／归档账号导航 | applyAccountsArchivedFilter → AccountsPage.setArchived | 切范围后1次列表GET | 切换查询条件，不归档/恢复数据 | **纯交互只读**；`webui/templates/index.html:90–93`；`L:1456–1459`；`F/AccountsList.vue:59` |
| 关闭账号详情（×／遮罩/Esc） | useAccountDetail.close | 0次业务请求 | 取消只读consumer/roxy读，不停止已入队任务 | **纯交互**；`F/AccountDetail.vue:45,52–58`；`F/useAccountDetail.ts:75–83` |
| 关闭/取消C2A；换绑关闭/取消/遮罩 | C2aReimport.close；EmailChange.close | 0次 | 仅关闭确认/来源读UI；不是取消服务器已受理任务；C2A提交中禁止手动关 | **纯交互**；`F/C2aReimport.vue:29–31,44,66`；`F/EmailChange.vue:78,82,96` |
| 查活日志“关闭” | closeLiveLogModal（全局modal helper） | 0次 | 停止该只读日志轮询；打开由操作受理后自动触发，GET日志每2秒一次 | **纯交互只读**；`webui/templates/index.html:264–268`；`L:1385–1411`；`R:1899–1919` |
| 账号组件加载失败“重新加载” | bridge ensure失败catch的click → setVisible | 重新初始化组件并读列表，无业务写 | 不属于批量处理节点 | **纯交互只读**；`webui/static/js/pages/accounts/bridge.js:116–126` |

## 三、巡检、回执弹窗按钮补齐

| 按钮/入口 | 处理函数 | API / 前端请求数 | 后端/批量情况 | 归类与源码 |
|---|---|---|---|---|
| 巡检历史刷新／上一页／下一页 | refreshHistory/changeHistoryPage | `GET /api/accounts/inspections?page=P` 每动作1次 | 分页只读；打开历史后5秒同类轮询 | **纯交互只读**；`F/Inspection.vue:56,70`；`F/useAccountInspection.ts:64–80,114`；`R:114–121` |
| 巡检失败详情／刷新／上一页／下一页 | openFailures/refreshFailures/changeFailuresPage | `GET /api/accounts/inspections/<id>/failures?page=P` 每动作1次 | 读历史快照，不重跑失败账号；5秒轮询 | **纯交互只读**；`F/Inspection.vue:64,73,80`；`F/useAccountInspection.ts:82–99,114`；`R:144–155` |
| 巡检任务编号 # | Inspection.task → deps.openTask | 0次业务写；任务页读 | 打开原生父任务，不逐账号导航 | **纯交互只读**；`F/Inspection.vue:36,61` |
| 巡检“停止” | view.stop | `POST /api/accounts/inspections/<id>/cancel` 1次 | `cancel_inspection` 读取全部活跃子run，循环每run `request_run_cancel`，然后reconcile父任务和notify；无集合取消/bulk节点停止 | **已有批次，但取消逐条**；`F/Inspection.vue:65`；`F/useAccountInspection.ts:101–104`；`R:157–163`；`core/accounts/inspection/service.py:106–112` |
| 巡检启动/历史/失败窗口“关闭” | Inspection.close | 0次 | 关闭对话框、取消GET；不取消巡检任务 | **纯交互**；`F/Inspection.vue:43,56,73`；`F/useAccountInspection.ts:106–109` |
| 操作回执“查询回执” | receipts.lookup | `GET /api/accounts/operation-receipt` 携request key，1次 | 按一次提交key找多个任务；这是关联回执，不是批量执行节点 | **纯交互只读**；`F/AccountOperationReceipts.vue:18`；`F/operationReceipts.ts:77–93`；`R:94–105` |
| 操作回执“移除此提示” | receipts.dismiss | 0次 | 仅本地entries/localStorage删除 | **纯交互**；`F/AccountOperationReceipts.vue:19`；`F/operationReceipts.ts:43–46` |
| 操作回执“任务 #/执行 #” | receipts.open | 0次业务写；任务详情GET | 导航查看task/run | **纯交互只读**；`F/AccountOperationReceipts.vue:22`；`F/operationReceipts.ts:95–97` |
| 回执展开“X次提交需核对回执” | details原生 | 0次 | 展开已加载本地回执 | **纯交互**；`F/AccountOperationReceipts.vue:11–12` |
| 注册重跑结果“打开任务中心” | RegistrationRetryReceipt.openTasks() | 0次业务提交；任务页查询 | 多结果只打开统一type/target筛选；不会循环N次打开任务 | **纯交互只读**；`F/RegistrationRetryReceipt.vue:30–34,44`；`F/setupActions.ts:92–98` |
| 注册重跑结果“查看任务 #” | openTasks([item]) | 0次业务写；单条任务详情/原注册日志读 | 查看指定任务，不重跑 | **纯交互只读**；`F/RegistrationRetryReceipt.vue:48`；`F/setupActions.ts:92–98` |
| 注册结果“查看任务及跳过原因” | details原生 | 0次 | 展示服务端返回的started/reused/skipped | **纯交互**；`F/RegistrationRetryReceipt.vue:45–49` |

## 四、存在调用契约但当前未发现显示按钮的入口

以下项目不能与当前可见按钮混为一谈，但清点动态dispatch时需要留档，避免后续漏掉复用入口。

| 动作 | 当前证据/处理 | API及批量情况 | 源码 |
|---|---|---|---|
| `account-setup`／`setupSelectedAccounts`（旧“补齐配置”，不执行Codex） | action dispatcher与legacy函数保留；当前 `accountToolbar.ts` 及 `_accountsV2MoreMenu` 未生成按钮 | `<id>/setup` 或 `/setup-bulk`，前端1次；后端逐账号 coordinator，无batch/node | `F/setupActions.ts:34,152–156`；`L:1425–1430,1638–1643`；`R:348–393`；`core/accounts/operation_coordinator.py:53` |
| `codex-reset-retrying`（重置补跑状态） | 支持descriptor及legacy resetOneAccountCodex；当前 `_codexAction`只生成stop/retry | `/api/codex/reset-retrying {email,status:'failed'}`，1次；单条业务 | `F/setupActions.ts:34,163–167`；`F/presentation.ts:116`；`L:1011–1020,1443–1448` |
| `qr-url`（二维码） | actionFromTarget和legacy invoke识别，但当前账号cell/menu未生成该data属性 | 0次业务写，openQrModal | `F/presentation.ts:116,124`；`L:1741` |
| `account-copy-secret:totp_secret` | secretLabels支持，但当前行按钮是6位TOTP，工具栏才复制密钥 | `<id>/secret?field=totp_secret`，1次只读 | `F/actions.ts:50–51,142–146` |
| C2A showResult/openTasks | owner仍暴露方法和receiptEntries，但当前 C2aReimport.vue 只渲染确认窗口，无结果列表/“查看任务”按钮 | 不产生批量提交；只有查看已有任务 | `F/useC2aReimport.ts:27–28,42–45`；`F/C2aReimport.vue:33–71`；`F/AccountsPageShell.vue:102–103` |
| 账号备注单条/批量、Roxy历史回填 | 路由存在，审计范围当前账户Vue/toolbars/menu/detail未找到对应触发按钮 | `/api/accounts/<id>/note` 单条；`/note-bulk` 已有集合UPDATE；`/roxy-profile/backfill-history` 不是当前账号可见按钮 | `R:297–304,974–1015`；`core/storage/db_legacy.py:2419–2442` |
| `/api/accounts/complete-bulk` | 当前“补全账号”按钮使用 `/action-bulk action=complete`；该接口单独存在 | 同样逐账号 `_account_action_result`，无batch | `R:487–527`，对照 `F/setupActions.ts:158` |
| `/api/accounts/<id>/c2a/sync`、`<id>/codex/upload-sub2` | 单条路由存在，但本域当前无“单账号C2A/sub2”可见按钮 | 每个都是单条durable任务，不可据此认为批量接口已有节点 | `R:1483–1502,1564–1597` |

## 五、后续统一成批量节点需要区分的边界（仅整理，未实施）

1. **多账号编排缺口**：直接批量动作没有统一 bulk batch/round/target 身份、目标快照、批量状态、目标集合重试/取消。应梳理为节点的优先对象是补密码/2FA/修改/补全、注册重跑、C2A/sub2、查活/套餐/刷新AT/提链、批量停止。
2. **已有运行批次≠已完成迁移**：邮箱换绑、Codex重授权、巡检各自已有运行批次，但没有统一bulk节点，且任务创建仍是循环。`submit_durable_operation` 是单项API（`core/operations/task_gateway.py:1275–1349`），没有传入公共连接的调用会在 `core/storage/operations/runtime.py:708–740` 按项开连接/事务。换绑 `dispatch=False` 只是延后调度，不使这些提交成为一次事务。
3. **兼容批次关联应单独核对**：查活/套餐/刷新AT/提链/封号邮件 `create_batch` 的uuid与native `_numeric_batch_id` 不同契约，是明确源码证据；本次未查生产库，不能声称线上某个既存批次已损坏。现有回执key能关联多个任务，但它也不是批量节点。
4. **可以集合处理的本地步骤**：账号预取/secret/session导出、批量凭证查找、批量任务构造、统一状态写入/取消。现有 `create_runtime_tasks_many` 已在 `core/storage/operations/store.py:1561` 暴露，但本表上述直达动作未调用；是否适配须另设计。
5. **外部按账号执行不等于需要逐条编排**：OpenAI登录/密码/2FA/套餐/换绑、C2A唯一邮箱目标写入、sub2逐凭证上传、CPA逐文件下载都有独立身份/状态，需要每目标执行/记录结果；可以由一个批量节点持有target并调度，不应把“不要逐条处理”理解为所有外部协议强行一个请求。
6. **已有真实共享能力**：HME一轮共享邮箱扫描要保留；归档/删除已有集合SQL不应回退成N个单账号任务。复制/导出虽可统一目标集合与集合读取，但仍是只读/导出交互，是否需要可重跑持久节点属于后续方案选择。
7. **注册保护**：注册重跑当前委派原 `retry_job`，后续若仅改变多目标提交层可先限定行为不变；如影响注册步骤、请求顺序、重试或状态流转，必须按用户规则详细方案确认，当前未改。

## 六、覆盖与遗漏风险

- 已逐条展开 `accountToolbar.ts` 34个动作（第9–42行），合并同动作常用按钮与菜单两个入口；已核对父任务提供的 `button-source-inventory.json` 中page=accounts的44个模板入口，并补上不在AST静态按钮中的动态cell/menu、legacy加载失败按钮和主HTML查活日志关闭。
- shared组件产生的分页、FilterPopover展开/关闭、ColumnResizer控件按账号页面用途归组；全局导航、通用二维码弹窗内部按钮由全局/其他域审计负责，不在此重复列其每一个DOM位置。
- 当前页只有一个账号选择Set；当前页全选只遍历本地页数据，不等于后端批量处理。两个“创建批次”按钮仅导航到草稿，确认落库在批量域；避免把它们与直接账号动作混为同一执行路径。
- 本次是静态审计，未在浏览器验收条件性按钮或在线部署包；feature gate、账号deactivated、状态queued/running、registered retry projection会影响按钮实际显示/禁用。编译产物 `webui/static/task-center/accounts.js` 未逐minify片段比对，结论以源码与bridge导入链为准。
- 现有未提交用户修改会导致行号随后变化；报告没有替用户提交、部署或执行任何操作。
