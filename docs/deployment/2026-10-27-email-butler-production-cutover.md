# 2026-10-27 邮箱生产统一切换

## 已确认的目标

用户要求将准备代码投入生产，并确认完整统一到 Email Butler，停用本机 iCloud 服务。Oracle 负责 iCloud 会话和自动补库，Butler 统一库存、领号、收码与结果登记；Turb 只保留 Butler 新任务入口，并为历史 iCloud 完整地址保留恢复通道。

## 数据和运行边界

- 不删除本机账号、邮箱池、任务、Apple 会话备份或旧收件 profile，不改完整业务地址和原 owner/acquisition 身份。
- Butler 同步已有别名；领取接口不能创建新别名。原自动补库 worker 独立迁移，保留节流与最近创建窗口，先停止本机 worker 再启动 Oracle worker。
- 使用和排除状态单向合并。已消耗、保留、替换、未知结果或已注册身份不能重新成为新号库存；历史收码无需重新租用邮箱。
- Apple 管理会话失效时按账号分类，禁止该账号新领；不能删除该账号已知库存，也不阻止已有地址按真实邮件证据取码。
- Oracle 既有 MailCom、Cloudflare、Outlook 和邮件通知/outbox 均保留。部署采用现网源码的最小合成差异，不能覆盖为本地旧开发基线。
- 数据库测试只用独立测试库/schema；生产迁移和库存导入有数据库与配置备份，路由迁移使用 dry-run、CAS 和回执回滚。

## 执行顺序

1. 备份 Oracle Butler 数据库、服务源码和配置，以及本机 Turb 数据库、环境和 launchd 配置。
2. 升级 Oracle 入库表与现有 mail-pipeline，保持原通知职责。
3. 部署 Oracle loopback iCloud sidecar，逐账号对比本机与 Oracle 的会话/别名结果。
4. 停止本机自动补库，Oracle 接管原活跃账号 worker；补齐 Butler provider 与同步入口。
5. 合并本机完整母子地址、历史使用和排除元数据，验证库存不能重复分配。
6. 部署 Turb 历史桥接与受控 profile 路由迁移；本机新任务仅选择 Butler。
7. 验证 API、既有邮件严格取码、历史报告、重启恢复及本机界面后，停用本机 sidecar。

## 真实环境已发现的情况

共五个 Apple 账号。四个账号在本机和 Oracle 同样返回 401，属于原有会话失效；一个账号可正常同步。凭据与历史别名均保留，后续需更新失效账号的 Apple 会话才能恢复它们的管理功能。现有收码只依赖 Butler 缓存和最终收件箱，不依赖 Apple 管理会话。

已从真实只读 IMAP 核对两条未过期缓存，按实际邮箱、UIDVALIDITY、UID、Message-ID 和 INTERNALDATE 补齐原始收件证据。没有发送验证码或登录新账号。这两条均为普通原始地址，不能代表真实子地址验收。

各阶段实际版本与结果见下文；私密备份、逐文件哈希与操作回执保留在本轮部署资料目录。

## Oracle 实际发布与验收

- Butler provider 源提交 `b2399e7`，同步 CLI/timer 提交 `4dd43f7`。应用为基于现网的最小八文件合成包，保留现网 MailCom，完整哈希清单保存在私密部署资料目录 `final-manifest.json`。
- `email-butler`、`mail-pipeline`、`icloud-hme`、`icloud-hme-auto-create` 均 active；库存同步 timer enabled/active，首次 oneshot `Result=success`。
- 导入 3,793 个历史身份，sidecar 当前另有 25 个别名，库存共 3,818；已消耗/保留 3,708、排除 516 均与迁移清单一致，可新领 110。同步是单向状态合并，不会将已用地址变成新号。
- 除四个当前 Apple 会话失效账号外，另有一个历史来源账号未在当前 sidecar 会话中。共五组来源不可用，全部禁止新领；历史身份和收码保留。
- 两条真实缓存逐一通过严格 API 比对，验证码、消息身份、完整收件地址和原始证据均一致；重复只读查询不消耗验证码，账号/运行状态指纹不变。未发送新邮件或注册账号；真实子地址仅完成隔离 MIME/HTTP 契约验收。
- 独立库验证：Butler 170 tests；现网衍生相关套件 129 tests（含原 MailCom 行为）；跨仓库 16 项真实 HTTP 联调通过。完整现网衍生套件 169/170，唯一差异为既有 Cloudflare provider 缺少本地基线的库存方法，本次未修改该 provider。

本机切换完成。首次短暂停服务前已确认所有业务当前运行、未确认请求和有效账号租约均为空；23 个未提交提链任务只暂缓调度，之后按回执全部恢复。后续工作台新重试任务保持运行。

## 本机切换版本与回滚依据

Turb 邮箱运行代码为 `05bcd06`（包含 `bea3879`、`66dfb2c`），最终 main 另包含仅迁移工具修复 `09d5f38`，作者最终定向 215 项测试和 135 个子测试通过；独立限定复审 9 项通过；最终跨仓库 16 项 HTTP 联调通过。HME 结果使用稳定身份报告，报告失败保留重试，重启恢复原固定连接和 acquisition；远端已有租约按原 TTL 自然到期，已消耗身份不能重新领取。

原本机 main 为 `ab4c2a9`。备份包括生产 PostgreSQL 自定义格式 dump、原 `.env`、iCloud 会话和 launchd plist；不删除本机历史资料。固定路由迁移执行前只读预览，执行回执 0600，回滚可使用同一工具的 `--rollback` 选项。

## 本机最终状态

- 新任务来源为 `email_butler`；`ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True`，历史收件模式 `forward_butler`。Chrome 实际页面确认只启用 Email Butler，并显示历史 HME 由 Butler 管理的提示，本机 sidecar 连接工具已隐藏。
- 固定路由实际迁移 192 个 allocation、172 个母地址配置，均为 `forward_butler`。全部 allocation 与 3,601 个母地址记录的业务指纹验证通过：除路由引用外，地址、归属、使用状态和时间戳均未变。私密回执位于原仓库 `run/oracle-mail-production/turb-profile-cutover.json`，权限 0600。
- 本机 `com.xiaozhou26.icloud-hme` 已 disable/bootout，8081 无监听，本机 iCloud 自动补库启动项均未加载。原会话、数据和 plist 仅保留作回滚；Oracle sidecar、自动补库和同步 timer 接管运行。
- 本机 WebUI PID `37830`，`/healthz`、`/readyz`、`/login` 全部 200；公网 Butler `/me` 200 且声明严格收件证据能力。
- 23 个暂缓提链 Run 按 hold2→hold1 回执逆序恢复，各 23/23 成功、0 冲突；未取消任务、释放配额或修改上游付款/请求结果。

生产迁移首次冷进程触发初始化自锁，该事务已精确取消并完整回滚，未生成回执；`09d5f38` 将 DDL 初始化放到迁移事务之前，保留 dry-run 只读。真实冷子进程先复现后验证修复，52 项定向测试/5 个子测试及独立 3 项 cold PG 复审通过；随后实际 apply 成功。该修复仅涉及迁移命令，无需再次重启 WebUI。

本机 sidecar 停用后，使用生产历史完整地址经 Turb 原桥接入口真实取码：缓存行 17315 的验证码匹配、固定 Butler 路由与严格上下文均正确，取码时本机 8081 确认无监听。没有发送邮件、创建别名或执行注册。
