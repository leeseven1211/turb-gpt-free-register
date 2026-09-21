# 文档导航

本目录只承载项目的设计、流程、开发约束和历史决策。日常操作先读根目录
[`README.md`](../README.md)，代理执行约束见 [`AGENTS.md`](../AGENTS.md)。

## 文档状态与权威顺序

- **当前资料**：说明已运行的代码、公开配置和开发/发布规则；修改前仍应核对代码与测试。
- **技术参考**：保存协议分析等可复用背景材料，不单独定义运行行为。
- **历史记录**：保存当时的方案、实施计划、验收和界面快照，不作为当前规则。

同一主题出现冲突时，按以下顺序判断：已运行代码、配置 schema、数据库表定义和测试契约；
根目录 README 的操作说明；本目录的当前资料；技术参考；历史记录和 `superpowers/` 的
规格/计划。历史文件的结论不能覆盖当前代码事实。

## 当前资料

### 架构与存储

- [当前项目架构](architecture/current-architecture.md)：应用入口、分层边界、运行时恢复和兼容层。
- [存储架构](architecture/storage-architecture.md)：PostgreSQL 事实来源、隔离测试和兼容导出边界。
- [代码与目录规范](architecture/code-conventions.md)：依赖方向、私有数据保护和开发约定。
- [兼容入口清单](architecture/compatibility-inventory.md)：兼容门面、观察期和逐文件删除条件。

### 业务流程

- [注册流程](workflows/registration.md)：注册提交、资源领取、Roxy/Protocol 驱动、续跑与后置步骤。
- [账号操作](workflows/account-operations.md)：账号操作任务、运行实例、事件、资源、取消和恢复。
- [账号认证支持矩阵](workflows/account-auth-support-matrix.md)：注册、查活、刷新 AT、补密码和 2FA 的公开配置边界。
- [Codex OAuth 操作](workflows/codex-oauth-operation.md)：Codex 补跑、凭证确认和原生 operation 模型。

### 开发与参考

- [发布与验证](development/release-verification.md)：隔离测试、发布检查和运行时验收方法。
- [协议指纹 HAR 参考](reference/protocol-fingerprint-har-analysis.md)：纯协议链路和指纹分析背景。

## 历史记录

[`history/`](history/) 按改造主题归档旧设计、迁移计划、验收记录和视觉快照。它们保留
决策上下文与审计证据，但不应被当作本次运行或当前流程的说明。

## Agent 工作规格与计划

[`superpowers/specs/`](superpowers/specs/) 和 [`superpowers/plans/`](superpowers/plans/)
保留其原始路径。它们分别是历史设计输入和实施输入，便于回溯决策，不与当前操作指南
混合。
