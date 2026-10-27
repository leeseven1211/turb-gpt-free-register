# Oracle 邮箱链路准备实施计划

> 执行方式：使用 superpowers:subagent-driven-development 并行完成两个独立仓库的改造，再统一审查和集成验证。

**目标：** 准备可迁移的 iCloud → Gmail → Email Butler → Turb 严格收件链路。

**架构：** 保留服务边界与当前运行配置。Butler worker 持久化实际邮件的原始收件证据，接口按完整地址匹配并返回版本化回执；Turb 仅在严格契约满足时接收子地址验证码。

**技术栈：** Python、PostgreSQL 16、unittest、psycopg/psycopg2。

**设计：** [准备设计](../specs/2026-10-27-oracle-mail-preparation-design.md)。

## 全局约束

- 新文档、代码注释和错误说明使用中文。
- 不执行 `rm -r` 或 `rm -rf`，保留用户原工作区全部修改。
- 不迁移数据、不修改实际 `.env`、不启停线上服务、不创建邮箱或发送验证码。
- 不使用生产数据库或 `public` schema 测试。
- 原始地址兼容旧协议；严格请求不得因旧服务或证据缺失退回母地址取码。
- 已有 profile 保留连接器与历史密钥引用，密钥只写 `.env`。

## 任务一：Butler 入站证据与兼容 API

工作区：`/Users/lihongwei/code/personal/.worktrees/email-butler-oracle-mail-preparation`，继承基线 `139bf25`。

文件：`services/email-butler/app/email_recipients.py`、`app/gmail_ingest.py`、`app/automation.py`、`app/handler.py`、`db/schema.sql`、新的 `db/migrations/0004_*.sql`、相关 `tests/test_*.py`、服务 README。

接口：消费原始 MIME 头部及 Gmail INTERNALDATE；产生设计规定的 `forwarded_exact_v1` 回执与 `inbound.recipient_evidence.v1` 能力。

- [ ] 先添加失败测试：把 To 改写为母地址、Received for 指向子 A 的邮件，仅允许 A 命中，拒绝子 B 和母地址；旧记录不能满足严格请求。
- [ ] 扩展 worker 的持久化字段和收件索引，保存完整证据并保持 UID 去重与通知事务。
- [ ] 实现增量 SQL、严格匹配、超时分类和兼容 API；限定变更在入站分支。
- [ ] 运行服务单元测试和隔离 PostgreSQL 集成测试，记录命令与输出；提交本任务。

## 任务二：Turb 严格取码与收件 profile

工作区：`/Users/lihongwei/.codex/worktrees/oracle-mail-preparation/turb-gpt-free-register`。

文件：`core/email_butler_client.py`、`core/forward_imap_client.py`、`core/icloud_hme_client.py`、`core/email_derivation.py`、必要的能力读取模块，以及相关 `tests/test_email_*.py`、`tests/test_forward_imap*.py`、`tests/test_icloud_hme.py`。

接口：生成设计规定的严格请求，验证服务端回执；支持显式创建 Butler profile，同时保留旧 IMAP profile。

- [ ] 先添加失败测试：旧服务缺能力、回执目标错误、子地址命中、母地址严格隔离、中转转发可用、旧 profile 不切换。
- [ ] 实现客户端参数、能力检查与回执核对，严格路径关闭 IMAP 绕过。
- [ ] 调整 HME 中转拓扑判断并支持新的 Butler profile，密钥引用沿用版本化 `.env` 机制。
- [ ] 运行最小单元测试与使用 `PostgresTestCase` 的隔离集成测试，记录命令与输出；提交本任务。

## 任务三：统一审查与准备说明

- [ ] 审查两个仓库的接口字段、证据版本和错误分类是否一致；审查失败后由原实现者修复。
- [ ] 在隔离环境把 worker 入库、Butler 查询和 Turb 客户端连起来，验证同母两个子地址、旧邮件和错误收件箱。
- [ ] 补充迁移准备与回滚说明，列明现网尚未切换、旧数据的证据回填条件和待执行的真实样本验收。
- [ ] 检查差异与 Markdown 链接，提交准备代码；保留隔离分支供后续部署，不推送、不重启。
