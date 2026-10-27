# Mail Service Consumer Boundary Implementation Plan

> **For agentic workers:** Use the current delegated implementation tasks, then independent cross-review.

**Goal:** 邮箱管理运维归邮箱服务，Turb 仅安全导入、领取、取码并记录使用结果。

**Architecture:** 保留五个本地库存池和历史固定路由；退役管理入口。短效邮箱有效期由使用层强制，Butler 回执用持久 outbox 隔离外部故障。

**Tech Stack:** Python、Flask、PostgreSQL、原生 JavaScript。

**Spec:** docs/superpowers/specs/2026-10-27-mail-service-consumer-boundary.md

## Global Constraints

- 禁止 rm -r；不删除凭据/历史数据；不 push。
- 所有开发写入测试只使用 mail_prepare_20261027 临时 schema。
- 新领取仅本地；未知结果不换号；旧固定 profile 保留。

## Task 1: 管理入口边界

- [ ] HTTP 退役 iCloud 同步/账号运维、CloudMail token/domain运维入口；返回410及明确 reason_code。
- [ ] 管理型客户端 sync/create 函数 fail closed，历史读码函数保留。
- [ ] 配置页隐藏管理入口及历史供应配置，保留连接/导入/取码参数。
- [ ] 先测所有被退役入口不调用远端/写配置，再实现并运行相关前端和HTTP回归。

## Task 2: 短效邮箱使用

- [ ] 新模块 core/email_resource_lifetime.py 提供规范化期限与 require_usable(row)。
- [ ] 导入通用API可选 expires_at，summary/claim 共用期限条件，恢复/取码拒绝过期。
- [ ] 结构化时间/收件人拒绝不可fallback全文抽码；日志移除敏感正文/OTP。
- [ ] 先复现过期领取、同意图续跑、旧码与错误收件人，再验证兼容旧两段导入。

## Task 3: 结果回执隔离

- [ ] 新增持久 outbox 表与 core/email_usage_reports.py；record_outcome 同事务写状态及待报告事件。
- [ ] HME使用稳定operation_id、固定profile，不等待网络；worker有租约和重试间隔。
- [ ] 新worker在WebUI运行时启动；只读聚合可见待报告/失败情况。
- [ ] 测试事务回滚、重复收口、超时重试、迟到失败不能覆盖成功和未知结果不报告。

## Task 4: 审查与验收

- [ ] 修复空库存禁用历史账号邮箱扫描的错误判定。
- [ ] 记录完整调用边界、Butler消费包缺口及支持格式，交叉审查实际diff。
- [ ] 独立测试、浏览器核对、备份与空闲门禁、生产数据只读对账及健康验证。
