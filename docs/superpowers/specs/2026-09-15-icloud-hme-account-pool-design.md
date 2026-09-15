# iCloud HME 多账号资源池与自动创建轮换设计

## 背景

当前 turb 通过 `ICLOUD_HME_ACCOUNT_ID` 选择一个 sidecar 账号。别名同步、自动创建和领取都围绕这个单值展开。一个 iCloud 账号的 Hide My Email 别名达到约 750 个后，sidecar 仍会继续尝试该账号，导致后台创建任务无法继续使用新账号。

sidecar 已经具备多账号能力：

- `GET /api/accounts` 返回账号及其状态；
- `GET /api/aliases?account_id=...` 按账号列出别名；
- `POST /api/create` 接收明确的 `account_id`；
- CLI 已支持多个账号和显式账号创建。

turb 的 `email_pool_icloud_hide` 已保存每条别名的 `account_id`，并且领取操作是 PostgreSQL 原子抢占。因此需要调整的是账号发现、同步和创建调度，不需要迁移或重新绑定已有别名。

## 目标

1. 在动态模式下自动发现 sidecar 中所有 `active` iCloud 账号；完成一次配置迁移后，新增账号无需再次修改 turb 配置。
2. 将所有账号的别名同步到同一个本地 HME 别名池，注册任务从全局可用别名中领取。
3. 后台自动创建任务以单请求、限速方式在账号之间轮换；单个账号达到配额、被限流或认证异常时，不阻塞其他账号。
4. 既有别名继续按原 `account_id` 收取邮件，当前 Gmail/Email Butler 最终收件箱保持全局复用。
5. 在 WebUI 中能区分每个账号的总量、可用量、已用量、停用量和最近错误。
6. 保持旧版固定账号配置可用于排障和回滚。

## 非目标

- 不修改 Apple Cookie、App 专用密码或账号登录流程。
- 不改变已有隐藏邮箱的转发目标，不把旧账号别名迁移到新账号。
- 不并发创建别名，不试图突破 Apple 的账号级限制。
- 不把 750 写成 Apple 协议的绝对常量；它只作为已知软上限和监控参考，最终以 sidecar 返回的别名数量及创建错误为准。
- 不让 turb 注册任务和 sidecar 后台 worker 同时成为常态创建者。

## 方案与选择

### 方案 A：静态多 ID 配置

新增逗号分隔的账号 ID 配置，turb 和 worker 按配置列表轮询。实现量最小，但新增账号仍需要人工改配置，账号健康状态也只能保存在进程内。

### 方案 B：动态账号池（选定方案）

turb 和 sidecar worker 都从 sidecar 的账号 API 动态发现 active 账号。turb 负责多账号同步和全局领取；sidecar worker 负责持续创建、账号游标和账号级冷却。旧的单账号配置保留为固定账号兼容入口。

该方案利用现有的 sidecar 多账号 API 和 PostgreSQL 别名归属字段，改动集中、历史数据风险低，并且新账号可以自动接入。

### 方案 C：将全部调度集中到 sidecar

新增 sidecar 的“自动选择可创建账号”接口，turb 只做同步和领取。长期边界更清晰，但需要同时改变 sidecar API、worker、turb 及 WebUI，当前需求不需要一次性扩大到该范围。

## 详细设计

### 1. 账号选择与兼容配置

新增动态模式的内部选择器，返回本轮可用账号及其状态：

- 当 `ICLOUD_HME_ACCOUNT_ID` 为空时，从 `/api/accounts` 选择 `status=active` 的账号，并按稳定顺序保留账号游标；
- `ICLOUD_HME_ACCOUNT_ID` 非空时继续表示“固定账号模式”，传入显式账号时保持单账号行为；
- WebUI 将字段标为“固定账号 ID（留空自动发现全部 active 账号）”，提供一次性清空/切换操作；不静默忽略已有固定值；
- 固定模式只用于排障、收件验证或回滚，不参与自动轮换。

新配置和完成迁移后的正常运行使用动态模式。现有配置若保留非空 ID，则继续固定到旧账号，直到用户明确清空该字段。

### 2. 多账号同步

`core/icloud_hme_client.py` 的同步流程改为：

1. 请求 sidecar 账号列表；
2. 过滤动态模式下的 active 账号；
3. 逐账号请求 `/api/aliases?account_id=...`；
4. 对每个成功响应调用现有 `sync_icloud_hide_aliases(..., account_id)`，保留该账号历史领取状态；
5. 聚合返回 `accounts`、`remote_count`、`remote_usable`、`account_errors` 和全局池汇总。

单个账号同步失败不能让其他账号的成功同步回滚。只有成功拿到某账号的完整别名快照时，才允许对该账号执行 `remote_missing` 处理；网络、429、401 等失败不能把该账号现有别名批量标为失效。

同步缓存键必须包含最终选中的账号 ID 集合、收件模式和最终 Gmail 标识，避免新增账号仍命中旧的单账号缓存。已有别名的 `account_id` 永久保留。

### 3. 全局领取与 OTP

`pick_account()` 在动态模式下不再先绑定一个账号，而是：

1. 触发 TTL 内的多账号同步；
2. 调用 PostgreSQL 原子领取，从所有本轮 active 账号的 `available` 别名中抢占一条；
3. 无库存时强制多账号同步一次后重试；
4. 仅在显式开启 `ICLOUD_HME_AUTO_CREATE` 时，按账号轮询尝试创建一条，再回到全局领取。

领取结果仍携带别名自身的 `account_id`。sidecar 收件模式继续使用该账号 ID 读取邮件；`forward_imap`/`forward_butler` 仍按原始 HME 别名在同一个最终收件箱中匹配，不增加中间 Gmail 配置。

### 4. Sidecar 自动创建 worker

`/Users/lihongwei/code/personal/icloud/scripts/auto-create-worker.sh` 从固定 `ICLOUD_HME_AUTO_ACCOUNT_ID` 改为动态账号游标：

- 每轮开始刷新 active 账号列表，自动纳入新账号，移除非 active 账号；
- 每轮只发一个 `create(account_id, label)` 请求；
- 账号按稳定轮询游标选择，已耗尽、冷却中或认证失败的账号跳过；
- 成功后沿用当前全局成功间隔 `120–180 秒`；
- 普通失败沿用 `300 秒` 退避；
- 429/Retry-After 只冷却当前账号，若有其他候选账号则继续；
- “达到地址数量上限”标记为账号级 `quota_exhausted`，不再对该账号高频重试；
- Cookie/认证错误标记为 `auth_error`，日志中显示账号名称/ID和下一次检查时间，但不输出 Cookie、密码或 Token；
- 网络不可用仍暂停全局创建，网络恢复后重新刷新账号列表。

为避免两个创建者竞争，sidecar worker 是持续创建的唯一推荐入口；turb 的 `ICLOUD_HME_AUTO_CREATE` 仅保留为低频、按需补充和排障开关，默认关闭。

账号级冷却状态可先保存在 worker 进程内；重启后通过刷新别名数量和一次受控创建重新判断。若测试证明重启后重复探测代价过高，再增加 sidecar 数据目录中的非敏感 worker 状态文件，不写入 Cookie 或密码。

### 5. WebUI 与运维可见性

“连接并同步”接口在动态模式下返回：

- active 账号数量；
- 每个账号的名称、ID、远端别名数、远端 active 数、本地 available/used/disabled 数；
- 最近一次同步成功时间或错误类型；
- sidecar worker 的账号级冷却/耗尽状态继续以 sidecar 日志为准；本次不新增跨项目 worker 状态 API。

保留固定账号测试参数，允许只检测一个账号。普通列表接口不回显 Cookie、App 专用密码、API Token 或 Gmail 密码。

### 6. 错误分类

错误按影响范围分类：

| 类型 | 处理 | 是否影响其他账号 |
| --- | --- | --- |
| 网络/超时 | 当前账号退避，保留既有本地池状态 | 否 |
| HTTP 429/Retry-After | 当前账号冷却 | 否 |
| 达到别名数量上限 | 当前账号 `quota_exhausted` | 否 |
| Cookie/认证失效 | 当前账号 `auth_error`，告警 | 否 |
| sidecar 服务整体不可达 | 本轮同步失败，保留本地池，不创建 | 是，直到服务恢复 |
| 最终 Gmail/Email Butler 不可用 | 注册 OTP 失败并告警，不改变别名归属 | 是，收件链路全局影响 |

“账号没有可用别名”与“验证码收件失败”必须继续分开报告，不能把收件故障误判成别名耗尽。

## 数据与迁移

- 不新增或重建 `email_pool_icloud_hide`；继续使用现有 PostgreSQL 行级表和 `account_id` 字段。
- 为账号维度汇总增加查询/返回能力；若现有表结构不足，优先通过 SQL 聚合实现，不复制敏感 sidecar 账号数据。
- `ICLOUD_HME_ACCOUNT_ID` 的旧值可继续用于固定模式。迁移 UI 时提供一次性切换到动态模式的明确操作，不能静默改变用户正在排障的固定模式。
- 兼容导出 JSON 继续作为导出，不作为事实来源。

## 测试策略

### turb

- 多账号发现、过滤 active、稳定同步缓存键；
- 两个账号一成功一失败时，成功账号别名仍写入池；
- 全局领取优先返回任一账号的 available 别名；
- 一个账号 750/429/认证失败时，领取和按需创建转到下一个账号；
- 既有 `account_id` 在同步、释放、OTP 上下文解析中不改变；
- 固定账号模式的旧测试继续通过；
- WebUI 汇总不泄露敏感配置。

### sidecar

- worker 动态刷新账号列表并自动纳入新增账号；
- quota/429/auth/network 四类结果只影响对应账号；
- 单请求间隔、失败退避和网络暂停策略；
- worker 仍支持显式固定账号覆盖；
- 脚本测试使用假的 CLI/API，不创建真实 Apple 别名。

### 受控验收

1. 先只读同步两个已存在账号，确认旧账号历史别名和新账号别名均被正确归属。
2. 在不创建真实别名的情况下验证全局领取和 OTP 上下文保留。
3. 使用测试桩模拟旧账号 quota、429 和新账号成功，确认 worker 继续运行并只切换账号。
4. 最后再执行一次小范围真实创建，确认 sidecar 日志、turb 池写回和 Gmail/Email Butler 收件链路一致。

## 回滚与发布边界

- turb 可以通过固定 `ICLOUD_HME_ACCOUNT_ID` 回退到单账号模式；已有别名不需要迁移。
- sidecar worker 可以通过 `ICLOUD_HME_AUTO_ACCOUNT_ID` 回退到固定账号；保留现有成功/失败间隔。
- 多账号同步失败时不做破坏性全量禁用，只保留已有本地状态，因此重启或回滚不会丢失领取历史。
- 本次设计不包含生产部署、sidecar Cookie 更新、别名删除或远程发布；实现完成后分别报告代码、测试、提交和部署状态。

## 实施拆分

1. 先在 turb 实现动态账号发现、多账号同步、全局领取和测试。
2. 再在 sidecar 实现 worker 轮换、错误分类和脚本测试。
3. 更新两边 README/配置说明和 WebUI 状态展示。
4. 按上述受控验收执行，确认后再决定是否启用生产 worker。
