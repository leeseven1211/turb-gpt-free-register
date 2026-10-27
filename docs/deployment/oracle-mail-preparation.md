# Oracle 邮箱准备说明

本页保留最初准备阶段的记录。后续已完成[生产切换](2026-10-27-email-butler-production-cutover.md)、[母子收件验收](2026-10-27-hme-receipt-validation.md)和[Butler 子邮箱统一管理部署](2026-10-27-butler-derived-inventory.md)，当前状态以这些验收记录为准。

## 当前交付边界

本轮完成邮箱链路代码准备与隔离验证，保留在 `codex/oracle-mail-preparation` 分支。没有迁移 iCloud、切换真实配置、推送代码、部署或重启现有服务，也没有创建邮箱或发送验证码。设计见[准备设计](../superpowers/specs/2026-10-27-oracle-mail-preparation-design.md)，执行范围见[实施计划](../superpowers/plans/2026-10-27-oracle-mail-preparation.md)。

iCloud sidecar 继续负责 Apple 会话、隐藏邮箱管理和别名库存；Email Butler 负责最终 Gmail 的入站保存与取码。Turb 保留账号、租约、完整业务地址和固定收件 profile。Apple Cookie、App 专用密码不进入 Turb 数据表。

目标链路允许中转：

```text
iCloud HME → 中转邮箱（可选）→ 最终 Gmail
                                  ↓ Oracle mail-pipeline
                              Email Butler PostgreSQL
                                  ↓ 严格收件 API
                                  Turb
```

本轮没有实现双 PostgreSQL 同步或离线邮件复制。本机保留自己的数据库和已有 IMAP profile；未来若把所有新任务统一接到 Oracle Butler，断网时如何领取邮箱、收取新验证码仍需单独设计。

## 已准备的行为

Butler 保存原始 MIME 头部字节、实际收件邮箱、Gmail `INTERNALDATE`、UID/UIDVALIDITY、结构化收件证据和 family 索引。普通旧请求保持兼容；严格请求使用 `forwarded_exact_v1`，要求完整目标地址、布尔 `strict_family`、最终 `mailbox_email` 和有效时间窗口。能力由 `/v1/me` 的 `inbound.recipient_evidence.v1` 声明。

Turb 先核对能力，再核对成功回执中的协议版本、完整地址、family 标志、最终邮箱，并用相同解析规则重验收件证据。两个同母子地址不能互取验证码，严格母地址不能取得子地址的验证码；无证据、歧义和错误邮箱各自分类。严格路径不通过 IMAP 兜底绕过校验，失败仍可沿原任务身份重跑。

worker 与严格 API 共享 OpenAI 来源判断，严格 API 会重验入库器保存的原始头，因此现有 pipeline 的旧筛选不会跳过消费端检查。仅有 Reply-To 自称 OpenAI，或已有认证通过的身份均属其他域且没有独立 OpenAI 通过时，返回 `source_untrusted`；OpenAI 身份相关的显式失败或矛盾认证返回 `source_authentication_failed`。为兼容现有转发模板，无认证头的 OpenAI From/Sender/Return-Path 仍可使用；这属于来源筛选规则，不等于完整的邮件认证验收。

已有 profile 保留原连接器与凭据版本。只有后续新建的 Butler profile 才固定 API 地址、最终邮箱及版本化密钥引用；PG 不保存 API Key。所需全局字段沿用 `EMAIL_BUTLER_API_BASE`、`EMAIL_BUTLER_API_KEY`、`ICLOUD_HME_INBOX_MODE=forward_butler` 和 `ICLOUD_HME_FORWARD_IMAP_EMAIL`，最后一项在此模式表示最终邮箱，无需 Gmail IMAP 密码。本轮没有修改这些真实配置，也没有增加配置表。

本次严格契约覆盖取码，尚未扩展固定 Butler profile 的封号邮件批扫。混合扫描时，只对这类目标返回 `email_scan_connector_unsupported`（`MAIL-SCAN-001`），同批旧 IMAP 地址继续扫描，不借用当前全局 IMAP 配置。

## 后续部署顺序

1. 记录两端代码版本、进程工作目录及健康状态，备份 Butler 数据库、现有入库器源码和实际配置。先确认将要发布的 Butler 基线：本地开发仓库原有模块化改动已在准备工作区固化为 `139bf25`，它是继承内容，不应把整个分支当作单个新增功能直接覆盖现网。
2. 核对目标库已有迁移记录，按依赖补齐 `0002`、`0003`、`0004_recipient_evidence.sql`。`0004` 的索引依赖 `0003` 创建的 `imap_received_at`，不能跳过前置迁移。增量 SQL 保留已有表和旧记录，不要求重建数据库。
3. 准备 Butler 后端文件和证据解析模块。Oracle 现有入库者是 `mail-pipeline`，它还承担主邮件表、通知和 outbox；不能直接停用并换成仅写验证码缓存的新 Gmail worker。使用 Butler 的 `scripts/prepare_mail_pipeline_patch.py` 对已审计源码离线生成 patch，先审阅、dry-run 和确认模块指纹，再决定应用。该工具不修改输入或自动部署；未知函数结构拒绝生成。
4. 保留原通知流程，为真实入库器增加证据字段和 `INTERNALDATE`。缺失或无效到达时间不能用邮件 `Date` 或本机时间冒充，保留游标以便重跑。避免两个写入器同时争用同一游标或形成未经核对的重复通知。
5. 在独立测试 schema 验证真实样本：最终邮箱、原始头、UIDVALIDITY/UID、到达时间、子地址隔离及旧请求兼容均符合预期。入库器证据验证后再发布 Butler API，用受保护 API Key 核对 `/v1/me` 能力和严格成功回执。
6. 发布 Turb 适配代码，显式准备新的 Butler profile 和密钥引用。已有 IMAP 绑定不自动迁移；历史绑定的切换须另行制定迁移步骤，不能直接改表或删除旧凭据。

Butler 配套细节位于其仓库 `services/email-butler/docs/oracle-mail-pipeline-preparation.md`，包括 patch 生成、依赖指纹、应用与回滚检查。

## 历史数据与回滚

旧记录没有原始收件头时，不能用 `recipients_json` 或母地址反推完整子地址。只能在原邮件仍存在时，核对实际邮箱、UIDVALIDITY、UID 和 `INTERNALDATE` 后重新解析真实头部，或者等待新邮件。`0003` 将旧 `received_at` 兼容回填到 `imap_received_at` 不等于获得真实投递证据；证据版本和原头仍缺失的记录不能满足严格请求。

增量字段可保留，不需要删除表或旧数据来回退应用。回滚入库器时保留已保存证据、原通知/outbox 和旧 profile；回滚到不支持严格契约的 Butler 后，新严格路径会明确报告契约不支持，不会自动取得母地址验证码。若要继续使用历史 IMAP 绑定，应保留对应连接器和凭据版本。

## 验证证据与待验收事项

Turb 最终相关回归通过 338 项测试和 234 个子测试，覆盖固定 profile、库存 SQL、路由恢复、严格客户端、混合批扫和任务错误分类。Butler 最终隔离全量测试通过 142 项，没有跳过，覆盖幂等增量 SQL、真实 PG 入库/查询、事务通知、重复 UID 及 API 回执；其中现网补丁准备器的 16 项测试另验证源码不变、未知结构拒绝、patch dry-run、通知保留和时间缺失时不推进游标。worker 与现网补丁均支持 IMAP literal 前后返回的元数据，不从正文读取 UID 或到达时间；必要元数据缺失时保留游标以便重跑。

跨仓库联调使用真实隔离 PostgreSQL、Butler HTTP Handler 和 Turb 客户端，合成 MIME 经 worker 解析后入库。7 项检查通过：同母两个子地址各取各码、完整 To 子地址配 HME 母资源、严格母地址拒绝、错误最终邮箱拒绝、旧邮件排除、旧无证据记录拒绝；重复 UID 不新增记录，严格路径未调用 IMAP 兜底。数据库限定独立 `mail_prepare_20261027`，每次使用临时测试 schema，不读取生产业务表。

这些结果不等于真实 Apple/Gmail 收码验收。上线前仍需检查实际转发头模板、真实到达时间、入库延迟及既有通知流程，并完成一组同母子地址的真实收码样本。iCloud 迁移、账号数据同步、配置入库和 Oracle 无 Roxy 的界面能力控制属于后续工作。
