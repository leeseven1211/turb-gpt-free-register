# 邮箱资源与取码

Turb 负责本地导入、领取、取码与使用事实；Email Butler 负责来源、别名、投递和服务租约。注册只使用本地已导入库存，空库存由用户手动补充。

## 本地库存与导入

五个本地来源为 `outlook`、`generic_api`、`cloudflare_domain`、`icloud_hide` 和 `email_butler`。统计与领取共用资格条件；已有账号、历史领取、无效、过期、归档、已使用及结果未知的地址不能作为新库存。母地址与 plus 地址分别登记。

| 来源 | 导入方式 |
| --- | --- |
| Outlook | `email----password----clientId----refreshToken` |
| 通用 API | `email----code_url`，可附带绝对有效期 |
| 域名邮箱、iCloud 隐藏邮箱 | 保留原本地库存和历史路由；新增素材通过对应邮箱服务维护 |
| Butler | 人工选择 HME、Outlook / Hotmail、Cloudflare、mail.com 或全部来源及数量，确认后由 v2 分配长期 OpenAI 租约；粘贴已有完整地址只恢复本人有效长期租约 |

有效期使用带时区的 ISO8601；过期保留原占用，不自动换号。普通素材导入在本地事务保存永久 `openai` 历史标签与证据，状态为 `local_only`。v2 没有外部素材永久事实写接口，不等待退役接口，也不把本地证据写成远端送达。旧待同步导入由 worker 恢复为本地完成。

## Butler v2 导入与恢复

API 根地址为 `https://email-butler.leeseven.com/v2`。预览仅 GET 可用量，不冻结具体地址、不占远端库存，也不保证确认时容量仍相同。不支持旧身份类型、域名、分组筛选。

确认导入后，先在 PostgreSQL 保存原批次及每项的 `Idempotency-Key`、`external_ref`，再请求 `POST /leases`，显式 `service=openai`、`ttl_seconds=null`。远端成功、本地失败时保留原回执；超时、进程重启、批次部分完成均继续原项。超过 Butler 幂等结果保留期，只能按原 `external_ref` 查询，不能再提交可能分配新地址的请求。本地冲突保留租约和未确认项，不自动退租。

`email_inbox_profiles` 保存固定连接及版本化 `credential_ref`，`email_butler_lease_bindings` 保存完整地址、服务、稳定客户端与 `lease_id` 的映射。旧 profile 不覆盖；已知旧入口在访问时规范为 v2。恢复不按域名猜路由，不改 owner 或 acquisition，不申请替代邮箱。

原 Key 必须保留稳定 client，授权 `openai`。读取需要 `leases.read`、`codes.read`；新长期租约需要 `leases.create`、`leases.long_term`；显式退租需要 `leases.release`；限时续租需要 `leases.renew`。连接测试显示认证与缺少权限。新长期租约不依赖客户端保存最终物理收件箱。

## OTP 与身份隔离

取码定位 `/leases/{id}/code`；先核对原地址、服务、客户端和租约状态，再使用挑战 `since` 和稳定事件 `code_id`。单次等待最长 20 秒，按原总预算分段；`pending` 继续等待，`ambiguous` 明确多候选，不任取最新邮件。OpenAI 仍只接受六位数字及不早于挑战的真实接收时间。

服务端按来源验证完整收件人与可信发件域；Turb 保存 v2 租约授权和事件回执，不伪造旧 MIME 收件证据。错误地址、服务、客户端、过期或已退租租约均拒绝，不降级到其他路由。显式历史 IMAP profile 和独立 Outlook、通用 API 继续按自己的契约读取。

`email_otp_requests` 保留同一完整地址的独占认证、发码代次、候选、提交状态与递增 fence。旧执行不能覆盖新事实，未知结果保留原意图。原密码、Roxy、proto2 注册步骤均不因邮箱服务升级而更改。

## 使用结果、删除与巡检

使用结果和成功防回退证据在原 PostgreSQL 事务记录为 `local_only`，v2 没有业务结果上报接口。历史 delivered 回执保留；旧未送达报告保留原证据并转为本地记录。失败和未知不能覆盖成功。

任务结束不等于退租。成功、结果未知以及仍需后续 OTP 的账号保留长期读取权。符合原删除规则的未使用邮箱，先同事务保存本地删除和原退租意图，后台定位原 `lease_id` 退租；超时沿原意图继续。旧合并迁移仅能确认读取、不能确认原释放操作时，显示 `lease_original_mapping_required`，不能结束后来的新租约。

本地永久导入历史不随删除或退租消失；Butler 当前服务标签由其有效租约派生，退租后移除。来源故障不自动退租。旧后台事件保留原 operation、固定凭据及代际 fence，进程重启恢复，不伪造远端成功。

v2 公开 API 没有封号邮件扫描。Butler 路由返回 `signal_scan_unsupported`，不报告阴性或猜测账号状态，自动巡检跳过该能力；独立 IMAP 等来源继续按原规则扫描。

## 维护与验证

- 空库存检查所选本地池和导入批次，不在注册时远端补号或切换来源。
- 导入未确认继续原批次；保留原幂等键、回执及远端归属。
- 取码失败检查原 client、权限、完整地址、固定 profile、租约状态和挑战时间。
- 旧租约读取失败不将邮箱重新投入库存；过期与已退租分别分类。
- 配置与数据库连同主密钥、消费者身份成套备份；见[部署与维护](../deployment/operations.md)。旧 v1 永久事实工具属于历史迁移，不再用于现网 v2 写入。

代码入口：[v2 传输](../../core/email/email_butler/v2.py)、[原租约映射](../../core/email/email_butler/lease_bindings.py)、[人工导入](../../core/email/email_butler/manual_import_v2.py)、[库存资格](../../core/email/inventory.py)。使用[隔离测试库](../development/release-verification.md)验证；真实邮件投递与注册需要单独验收。
