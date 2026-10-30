# 运行配置数据库迁移 Implementation Plan

> **For agentic workers:** 使用 superpowers:subagent-driven-development，并行任务按文件所有权实施，主代理集成、审查和验收。

**Goal:** 将运行配置及历史收码密钥迁到 PostgreSQL，.env 仅保留启动配置和部署身份。
**Architecture:** 密文配置表 + 延迟加载 facade + 保持原配置读取契约 + 显式可恢复迁移。
**Tech Stack:** Python、PostgreSQL、psycopg、现有 cryptography/Fernet、Flask。
**Spec:** docs/superpowers/specs/2026-10-30-runtime-config-database.md

## Global Constraints

- 不执行 rm -r/rm -rf，删除只能逐个文件。
- 开发与测试仅用非生产库独立 schema；不得输出实际配置值或凭据。
- 不改注册主流程，保留默认值、空值、别名、超时和重试语义。
- 保护主仓库原有修改，不推送远端。
- 用户已批准实施；常规实现、测试、迁移与重启不重复请求确认。

### Task 1: 配置密文仓库

**Files:** 创建 core/runtime_config_store.py、tests/test_runtime_config_store.py。
**Interfaces:** 按 Spec 的 read_values / transaction / ensure_tables / write_values / current_revision；主密钥名 TURB_CONFIG_ENCRYPTION_KEY；三表 runtime_config_values/meta/history。

- [x] 写隔离PG测试：缺表只读None、激活读回原字符串、数据库不含明文、错误/缺少主密钥报错、写入回滚、幂等与并发更新。
- [x] 在独立schema运行测试，确认缺功能失败。
- [x] 实现仓库和脱敏异常。激活数据库不可静默回退，生产保护走 postgres_store。
- [x] 运行仓库测试与lint，给主代理接口与验证记录；不单独提交。

### Task 2: 配置 facade 与全入口接入

**Files:** 创建 config/runtime.py、tests/test_runtime_config_loading.py；修改 config/env_loader.py、config/schema.py、config/__init__.py、webui/config_editor.py、core/email_derivation.py、core/email_usage_reports.py、core/butler_inventory_handoff.py；必要时改对应测试。
**Interfaces:** 消费Task1仓库；提供Spec facade；bootstrap与运行配置分流。

- [x] 先测试数据库优先级、旧环境兼容、空列表、动态密钥不落盘、WebUI成功/失败回滚与稳定快照。
- [x] 实现bootstrap保留键与延迟加载，避免import递归及测试意外接生产。
- [x] 配置页运行值写数据库、bootstrap写文件，候选校验通过才发布；提交失败也完整恢复内存。
- [x] 历史邮箱凭据读写改用 facade，原引用及协议行为不变。
- [x] 更新schema存储来源及文案，跑相关配置/邮箱测试，给主代理验证记录；不单独提交。

### Task 3: 显式迁移工具

**Files:** 创建 tools/migrate_runtime_config.py、tests/test_runtime_config_migration.py。
**Interfaces:** 使用Task1仓库与Task2 bootstrap集合和物理env parser；CLI --source-root / --dry-run / --apply。

- [x] 测试dry-run无副作用、值和身份保留、加密主密钥和0600备份、重复执行、冲突拒绝、失败不精简文件、动态历史引用迁移。
- [x] 实现可恢复迁移，原子文件替换，输出只含统计及错误分类。
- [x] 比较迁移前后原值；现有不同库值禁止覆盖，未知字段不丢失。
- [x] 跑隔离迁移测试和lint，给主代理使用方法；不单独提交。

### Task 4: 集成、文档与实际切换

**Files:** 修改 .env.example、README.md、docs/architecture/storage-architecture.md、tests相关夹具和工具隔离配置（必要时）。

- [x] 审查三个任务的接口、一致性和失败路径，并修复集成缺陷。
- [x] 精简.env.example为真正bootstrap字段，README与存储文档解释数据库配置、密钥备份、显式迁移、回滚和启动参数。
- [x] 运行相关后端/前端测试、lint、语法及Markdown链接检查；受控临时库启动与浏览器验收。
- [x] 独立审查全变更，完成必要修复与定向回归。
- [x] 生产dry-run、检查活跃任务、备份PG和.env，停止服务、应用迁移、对账、合入main并重启（保持原端口）。
- [x] 检查健康/就绪/登录、配置读取和保存；确认业务数据无迁移改动、.env精简、服务版本与提交状态。提交到本地，明确未推送。

### 交付验证（2026-10-30）

- 实现经独立审查通过，已合入本地 `main`；未推送远端，原有及并行修改均保留。
- 实际部署将 220 项运行配置加密迁入 PostgreSQL，`.env` 保留 7 项启动配置。全部原始值与模块生效值一致，历史收码密钥引用和部署身份保留。
- 暂停 launchd 自动拉起后完成新的完整备份；停服状态下重复迁移新增写入为 0，前后 49 张业务表完整行摘要一致。恢复原 launchd 托管与 `127.0.0.1:8000` 监听。
- 健康、就绪和登录接口均返回 200，迁移前后非敏感配置快照一致；实际配置接口确认运行字段的存储和来源均为 `database`。
- 集成前联合回归 253 测试、1334 子断言通过；合入后定向回归 125 测试、1310 子断言通过，47 项前端测试通过，ruff、JavaScript 语法和差异检查通过。未将已独立复现的旧字段/邮箱契约失败计为本次通过项。
- 隔离真实浏览器完成登录、修改保存、整页刷新持久化验收，临时 `.env` 字节未变；测试服务、目录和 schema 已清理。实际服务另完成浏览器登录与配置页只读验收。
- 数据库完整备份、原 `.env` 与含主密钥的精简 `.env` 已按受限权限配套保留。
