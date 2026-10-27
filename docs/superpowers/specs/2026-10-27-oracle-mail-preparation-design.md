# Oracle 邮箱链路迁移准备设计

## 目标与范围

为后续 Oracle 部署准备可验证的邮箱链路：iCloud HME 管理 Apple 会话与别名，Email Butler 的 Gmail 入站 worker 保存邮件证据，Turb 通过 Butler 获取按完整地址隔离的验证码。本次只准备代码、隔离测试和切换说明，不迁移数据、不修改实际配置、不启停线上服务、不创建隐藏邮箱、不发送验证码。

本机无法连接 Oracle 时仍需独立运行，属于后续双 PostgreSQL 同步与本机收码方案；本次不把本机切到 Oracle 数据库。

## 当前基线

- Turb 使用独立工作区，起点为 `ab4c2a9`；现有 `forward_imap` 保持默认行为。
- Email Butler 实际开发仓库为 `/Users/lihongwei/code/personal/web-tools-suite`。该目录已有未提交的模块化服务及 Gmail 增量 worker，复制到独立工作区后以 `139bf25` 固化继承基线；原工作区保持不变。
- Oracle Butler 也是模块化版本，但尚未部署本地新 worker。线上只读审计发现入站缓存缺少按来源保存的原始收件头；直接地址数组不足以判断母子地址。

## 邮件处理边界

1. iCloud 原账号 ID、别名 ID、Turb 邮箱租约及使用状态不变。
2. Apple 转发到中转 Gmail 再到最终 Gmail 是有效拓扑，不能只因直接目标与最终邮箱不同就停用别名；真正收码必须核对邮件的完整目标地址。
3. 邮件证据沿用 Turb 已验证的 `core/email_recipients.py` 规则：完整地址、iCloud 的 Received for、HME p 字段和受限的 OpenAI SPF/VERP 模板；不按子串或最新邮件猜测。
4. 同母子地址冲突、证据缺失、收件箱不匹配分别分类。不能用母地址验证码代替子地址。
5. 已有固定收件 profile 保持原连接器，不因全局模式变化而切换；后续新 profile 才能显式使用 Butler。

## Butler 兼容契约

保留 `POST /v1/inbound/code` 的旧请求格式。严格请求新增：

```json
{"email":"alias+child@icloud.com","since":"2026-10-27T00:00:00Z","timeout_seconds":15,"recipient_mode":"forwarded_exact_v1","strict_family":true,"mailbox_email":"final@example.test"}
```

服务端仅使用入站 worker 从实际邮件解析并保存的头部证据进行匹配。Gmail INTERNALDATE 作为收件时间，UID/UIDVALIDITY 保留为稳定消息身份；在通知事务提交前完成入库。旧记录缺少证据时不能满足严格请求。`GET /v1/me` 声明 `inbound.recipient_evidence.v1`。

严格成功响应保留原验证码字段，并增加：

```json
{"recipient_mode":"forwarded_exact_v1","recipient_match":{"email":"alias+child@icloud.com","strict_family":true,"mailbox_email":"final@example.test"},"recipient_evidence":{"original_recipients":["alias+child@icloud.com"]}}
```

Turb 核对模式、完整目标、strict 标志及请求指定的收件箱。旧服务不支持严格契约时明确返回 `recipient_contract_unsupported`；缺少回执、目标不符或证据不足不得静默降级。普通原始地址的旧请求继续兼容。

新入库字段必须通过可重复运行的增量 SQL 添加，并保留原表和旧数据。服务端无证据或歧义时继续等待同一时间窗口内的新邮件，在超时结果中保留具体分类。

## Turb 适配

- 扩展 Butler 客户端的严格收件请求与响应校验。
- `forward_butler` 的子地址、以及具有子地址历史的母地址，使用严格契约；不调用 Gmail IMAP 兜底绕过校验。
- 普通地址现有 Butler 与 IMAP 兜底保持兼容。
- 新建 Butler 收件 profile 固定 API 地址、最终邮箱及版本化密钥引用；密钥只写 `.env`，不能写入 PG profile 或任务快照。
- 既有 IMAP profile 和历史密钥引用保持不变。

## 验证与交付

- 先运行基线，再为中转、同母两个子地址、母地址歧义、旧邮件、错误收件箱、旧服务和重复投递编写失败测试。
- Butler 验证头部解析、持久化、严格 SQL 查询、通知、API 回执。数据库测试只使用明确隔离的测试库或临时 schema，不连接 `turb_console`、`email_butler` 或 `public`。
- Turb 复用 `tests.support_pg.PostgresTestCase`，显式指定非生产测试数据库。
- 新文档包含准备版部署顺序、增量 SQL、原始邮件证据回填策略、样本验收及回滚边界；不宣称真实收码已验收。
