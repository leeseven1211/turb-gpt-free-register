# 文档导航

日常安装、配置和功能操作先读[项目 README](../README.md)。本目录只保留现行架构、关键业务流程、开发规则和维护步骤；同一主题尽量只有一个维护入口。

## 阅读入口

| 需要了解 | 文档 |
| --- | --- |
| 入口、业务目录、依赖方向和兼容模块 | [当前架构](architecture/current-architecture.md) |
| 数据表、事务、租约、运行配置与恢复 | [存储架构](architecture/storage-architecture.md) |
| 功能入口、公共组件和测试选择 | [功能地图](architecture/functional-map.md)及其[结构化数据](architecture/functional-map.json) |
| 代码、配置、API 和前端约定 | [代码规范](architecture/code-conventions.md) |
| Run、线路、阶段、错误和日志关联 | [任务观测契约](architecture/task-observation.md) |
| 五种注册驱动、核心账号、后处理与续跑 | [注册流程](workflows/registration.md) |
| 查活、刷新 AT、密码和 2FA 的驱动支持 | [认证支持矩阵](workflows/account-auth-support-matrix.md) |
| 账号任务、取消、恢复及账号解封 | [账号操作](workflows/account-operations.md) |
| Codex OAuth 补跑、凭据和待确认结果 | [Codex OAuth](workflows/codex-oauth-operation.md) |
| 本地邮箱库存、Butler 交接与严格取码 | [邮箱资源](workflows/email-resources.md) |
| 隔离测试、验证范围和交付检查 | [发布与验证](development/release-verification.md) |
| 托管服务、备份、配置和收件迁移 | [部署与维护](deployment/operations.md) |
| 协议会话一致性及离线 HAR 排查 | [协议参考](reference/protocol-fingerprint-har-analysis.md) |

## 维护规则

当前代码、配置 schema、数据库定义和测试契约是核对文档的依据。行为变化更新对应现行文档，不以设计稿或单次验收结果替代运行事实；凭据、业务数据和诊断产物不入文档。

旧设计、已完成计划、历史性能测量、部署回执和页面快照已从当前目录移除，历史版本仍可通过 Git 查询：

```bash
git log --all -- docs/
git log --all -- docs/原路径.md
git show <历史提交>:docs/原路径.md
```

新任务的临时计划和验收材料放在忽略的 `.superpowers/` 工作目录；完成后把仍有效的知识合入上述文档，避免继续堆积按日期命名的记录。代理执行约束由工作区的 `AGENTS.md` 维护。
