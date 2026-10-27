# Butler 子邮箱统一管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Butler 管理子地址；Turb 只持久记录消费意图、导入、领取与收码。

**Architecture:** Butler 新增 PostgreSQL 权威账本和事务生成/领取，兼容现有邮箱展示与转发收码。Turb 保存远程身份和领取意图，复用完整地址 OTP fence，保留历史账本。

**Tech Stack:** Python、PostgreSQL、现有原生 HTML/JS。

**Spec:** `docs/superpowers/specs/2026-10-27-butler-derived-inventory.md`

## Global Constraints

- 独立测试库 mail_prepare_20261027，临时 schema；生产仅受控迁移与验收。
- 旧 192 子地址与 OTP unknown 不改状态、owner、source 或完整地址。
- 禁止 rm -r；不 push；保留 MailCom 现网差异、私密文件及回滚材料。
- HME 默认累计 3 个，后缀 6 位；发行过的地址永不重新作为新库存。

### Task 1: Butler 权威库存和 HTTP 契约

**Files:** Butler `app/derived_inventory.py`, `db/migrations/0005_derived_inventory.sql`, `db/schema.sql`, `app/automation.py`, `app/icloud_pool.py`, `app/handler.py`, `tests/test_derived_inventory.py`。

**Interfaces:** 管理 GET `/api/derived-addresses`，POST `/api/derived-addresses/generate` 与 `/api/derived-addresses/policy`；消费沿用 `/v1/mailboxes`，acquisition_id + owner_kind + owner_id，响应 identity_type/parent_email/identity_id。后台独立模块暴露迁移 import 方法。管理端复用既有访问边界；v1 consumer 从认证 key 注入不可覆盖。

- [x] 写真实 PG 多连接/进程测试，复现同母并发生成超过 3、同地址重复分配、旧快照覆盖。
- [x] 用隔离 wrapper 运行，确认因缺少 authority 接口失败。
- [x] 创建账本、事务生成/领取/恢复/结果登记与展示合并；已发行 tombstone 永久保留。保留 Outlook/MailCom 原路径。
- [x] 运行新测试及 Butler 全套回归，记录证据。

### Task 2: Turb 消费合同与历史兼容

**Files:** `core/email_butler_client.py`, 新 consumer intent storage, `core/email_auth_guard.py`, `core/email_provider.py`, `core/registration_service.py`, `core/email_change_service.py`, `main.py`, `core/feature_availability.py`, `webui/routes/jobs.py`, `core/email_derivation.py`, `webui/routes/email_pool.py`, `config/schema.py`, 相关现有 UI HTML/JS、测试。

**Interfaces:** 领取前存稳定 acquisition，调用失败未知只恢复同 ID；新 Butler HME child 持久固定身份/profile，OTP guard 使用完整地址和 nullable local binding。历史 local allocation 优先恢复。

- [x] 写领取超时/重启恢复、remote child fence、所有本地生成入口拒绝的新测试，观察失败。
- [x] 实现持久消费意图、明确 request_unknown、贯通稳定 owner 与恢复。
- [x] 本地生成配置/操作退出 UI、历史只读保留，桥接可用性以 Butler 为准。
- [x] 隔离运行相关测试及跨仓 HTTP 契约联调。

### Task 3: Butler 管理界面

**Files:** Butler `static/index.html`, `static/derived.html`, `static/derived.js`；界面沿用已有样式。

**Interfaces:** 调用 Task 1 管理接口；request_id 在未知时保留，参数变化创建新 ID；显示累计数、可用数、已领取数与上限，disabled/loading/error 可访问。

- [x] 在既有导航添加独立“子邮箱”管理页，固定标签与简洁说明。
- [x] 真实 UI 验证库存读取、策略保存、幂等生成与母子筛选；不在生产为测试大量生成。

### Task 4: 受控迁移、生产部署与验收

**Files:** ignored 私密 migration/deployment receipts；公开 deployment 文档与 README。

- [x] 只读导出本地 192 条历史分配与父策略，不含凭据；生成 dry-run 摘要、指纹和 0600 回执。
- [x] 独立库导入验证历史 144 used/48 reserved 与 owner 完全一致，不能新领取；恢复同 acquisition。
- [x] 基于 Oracle 最新 snapshot 最小合成应用变更，运行现网衍生回归，备份 hash 和数据库。
- [x] 在 Oracle 创建增量表并导入历史事实，受控重启并检查六项服务。Turb 空闲窗口升级重启。
- [x] 验证真实 API/UI 及严格收码路径、记录本机/Oracle 性能，独立审查并修复阻断项。
- [x] 更新文档、本地 commit 和生产快进，不 push。

完成记录见 [生产验收](../../deployment/2026-10-27-butler-derived-inventory.md)。真实验证码性能沿用上一轮收件验收，本轮重新验证严格取码的隔离 HTTP/PG 合同和生产身份路由，不向外部触发新验证码。
