# 邮箱资源与取码

Turb 负责导入、领取、取码和使用结果；Email Butler 及其邮箱服务负责邮箱创建、母号、别名生成、同步和投递维护。新注册只使用已导入的本地库存，空库存由用户手动补充。

## 本地库存与导入

五个本地池为 `outlook`、`generic_api`、`cloudflare_domain`、`icloud_hide` 和 `email_butler`。统计与原子领取共用可用性条件，已注册、已使用、无效、过期、归档或结果未知的身份不能作为新库存领取。邮箱域名不决定收码方式，来源和固定收件连接才决定实际路由。

| 来源 | 导入格式与条件 |
| --- | --- |
| Outlook | `email----password----clientId----refreshToken` |
| 通用 API | `email----code_url`；可加第三段绝对有效期，或在导入时指定批次有效期 |
| 域名邮箱、iCloud 隐藏邮箱 | 保留既有本地池和历史身份；当前统一粘贴导入不接受这两个来源，新增 HME 素材通过 Butler 入口导入 |
| Butler 导入邮箱 | 当前支持 `icloud_hme`，每行一个完整 `@icloud.com` 母地址或 plus 子地址；需确认永久库存交接及固定 Butler profile |

有效期使用带时区的 ISO8601，单行值优先于批次值；省略时沿旧格式处理，不猜测供应商期限。统计、领取、恢复和每轮取码共用有效期规则。过期保留原占用，不自动换号。

Butler 普通账号导出缺少永久归属及固定读取授权，不能直接当作 HME 库存导入。其他 provider 可使用明确的 Outlook 或通用 API 材料；不能因域名相同就伪装成 HME 转发路由。

当前统一粘贴导入接受 Outlook、通用 API 和 Butler HME，预览及导入单次最多 5000 行。另一个「从 Butler 导入」候选入口按每批 1–200 项处理，先冻结候选、解析完整身份，再登记归属。失败或超时后继续原批次、原候选和原请求身份；已成功项保留，不重新生成一批邮箱。导入窗口重新打开会恢复原批次，可继续检查未完成项。

## 稳定身份与永久交接

领取在 PostgreSQL 事务内保存 acquisition、owner、完整地址及任务关联。重跑恢复原地址；跨来源导入、已注册账号、历史分配、本地领取和未决远端意图共同参与去重。重新导入、重置状态或删除展示记录都不能让已发行地址再次分配。

Butler HME 导入使用稳定消费者 `TURB_MAIL_CONSUMER_ID` 和原请求身份，交接到本地库存后远端归属持续保留，短读租约过期不解除归属。远端已交接、本地事务失败时，只能恢复同一次交接，不能回收或换领。恢复环境和回滚时必须保留原消费者、owner 和 acquisition。

固定 Butler HME 的新领取要求有效交接证明；旧 claim 的恢复和已使用邮箱的固定读取仍按历史上下文处理。直接固定 IMAP profile 沿自己的连接和凭据契约，不套用 Butler 交接。

子邮箱在 Butler 手动生成，额度与后缀由对应类型策略决定。Turb 不自动补号、生成或同步新库存；已存在母子身份、累计生成历史和使用状态不能被新的策略覆盖。

## 固定收件连接与严格 OTP

`email_inbox_profiles` 保存实际收件身份、连接器、版本和 `credential_ref`。已绑定地址优先读取该 profile，不根据当前全局 Gmail/Butler 配置猜测路由；历史 `EMAIL_DERIVATION_IMAP_SECRET_*`、`EMAIL_DERIVATION_BUTLER_SECRET_*` 的凭据引用必须保留。

| 项目 | 要求 |
| --- | --- |
| Butler 能力 | 严格转发收件要求 `inbound.recipient_evidence.v1` |
| 身份与模式 | `forwarded_exact_v1`、完整目标地址和适用的 `strict_family` |
| 收件证据 | 实际最终 mailbox、完整母/子地址证据、可信消息来源 |
| 时间 | 按挑战的 `after_ts` 及消息真实到达时间筛选，不用邮件正文猜收件时间 |
| 消息身份 | 保存稳定消息 ID、cursor、候选及提交状态，防止旧码和重复候选串用 |

母地址、plus 子地址和同母兄弟地址严格隔离，错误最终邮箱、缺少收件证据、旧邮件或不匹配的结构化候选都应明确拒绝。严格路径失败不降级到 IMAP 或正文正则绕过验证；显式绑定的历史 IMAP profile 则按自己的连接器执行。

通用 API 的结构化收件人和时间存在时必须匹配；拒绝的候选不能再经全文正则接受。纯文本接口保持兼容，但不据此宣称具备结构化收件证明。TLS、请求时限、验证码筛选和提交 fence 各有独立边界，取到验证码不表示认证已完成。

`email_otp_requests` 协调同一完整地址的认证租约与递增 fence，保留 challenge、发码代次和候选事实。旧执行不能覆盖新事实；未知提交保留原记录，不能先清空再重新领取。

## 使用结果与恢复

使用结果和持久回执在同一 PostgreSQL 事务保存，后台按原 operation、原连接及原凭据引用报告 Butler。断网不撤销已经确认的注册成功；晚到失败不能覆盖成功；未知结果不报告成功，也不把整个上游邮箱永久停用。

新注册不使用旧普通 Butler lease 路径。历史租约、付费邮箱订单和旧子地址只按原意图恢复：Remail 查询原订单或复用已保存凭据，不能因 prepared/rejected 或传输异常重新购买。

邮箱失效和 OpenAI 账号封禁是不同事实。已有账号的封号邮件扫描根据读取连接判断能力，本地新库存为零不代表不能扫描；单个 profile 失败也不能抹去其他地址的结果。邮件列表、正文和 OTP 查询均必须保持原身份隔离。

## 维护与排查

- 空库存：查看所选本地池与导入批次，不查询远端容量或自动换来源。
- 导入未确认：检查原批次和交接回执，继续原请求，不换号或删除归属。
- 取码失败：核对完整目标、固定 profile、凭据版本、最终 mailbox、能力与时间证据。
- 已用邮箱读取失败：保留原账号和历史身份，修复对应连接，不重新开放库存。
- 配置迁移：连同主密钥、消费者身份和数据库成套备份，步骤见[部署与维护](../deployment/operations.md)。

代码入口为 [inventory.py](../../core/email/inventory.py)、[provider.py](../../core/email/provider.py)、[Butler client.py](../../core/email/email_butler/client.py)、[bridge.py](../../core/email/email_butler/bridge.py) 和 [邮箱仓储](../../core/storage/email/__init__.py)。按[功能地图](../architecture/functional-map.md)选择本地库存、导入恢复、收件隔离和任务资源测试，使用[独立测试库](../development/release-verification.md)验证。
