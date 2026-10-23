# 协议注册密码主链路 Implementation Plan

> 历史说明：本文记录当时的设计或实施计划，不代表当前运行状态；现行行为与约束以 README、AGENTS.md 和当前代码为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Protocol 驱动覆盖 Roxy 成功注册样本中的密码、邮箱 OTP、OAuth session、2FA 和后处理主链路，并用一次真实脱敏抓包验收。
**Architecture:** 复用 `core/openai_auth.py` 已有协议 helper，在 `core/registration/protocol.py` 增加密码阶段；把邮箱验证中间态保存抽成驱动无关 helper，保持 Roxy profile 绑定信息为可选元数据；未知结果继续走现有 durable `request_unknown` 与邮箱保留规则。
**Tech Stack:** Python 3、PostgreSQL、pytest、现有 BrowserSession/Protocol v2、Roxy CDP 脱敏抓包。
**Spec:** `docs/superpowers/specs/2026-09-21-protocol-registration-password-flow-design.md`

## Global Constraints

- 所有新增文档、注释、日志和界面文案使用中文；配置键、函数名、协议字段保留原拼写。
- 不读取、输出或提交 `.env`、账号、Token、Cookie、OTP、密码、完整代理地址、原始 HAR、`logs/`、`run/` 和未跟踪私有文件。
- 不执行 `rm -r`/`rm -rf`；不重置或检出工作区，不覆盖已有用户修改。
- PostgreSQL 是唯一事实来源；测试使用项目隔离测试工具或 `PostgresTestCase`，不写 `public` schema。
- 不自动合并、推送、部署、重启服务；最终分别报告文件修改、测试、提交、推送和运行时验收证据。

## Task 1: 建立协议密码阶段的红灯测试

- [ ] 检查 `tests/test_openai_auth_registration_flow.py` 和现有 Protocol 测试的 mock 约定，新增一个针对 Protocol 密码阶段的测试。
- [ ] 测试断言密码开启时先请求含 `username_password_create` 的 Sentinel bundle，再调用 `register_user`，随后调用 `navigate_email_otp_send`；当前代码应因缺少调用而失败。
- [ ] 新增密码关闭测试，确保不改变现有邮箱 OTP 入口。
- [ ] 运行最小测试并保留失败输出：
  `PYTHON_DOTENV_DISABLED=1 python -m pytest -q tests/test_protocol_registration_password.py`

## Task 2: 实现 Protocol 密码注册编排

- [ ] 在 `core/registration/protocol.py` 引入现有 `request_password_sentinel_bundle`、`generate_registration_password`、`register_user`、`navigate_email_otp_send` helper。
- [ ] 添加小范围的密码阶段函数，明确传递同一 Sentinel bundle 的上下文，解析并校验注册响应中的继续地址。
- [ ] 在 `run_protocol_registration` 的 authorize 后接入该阶段；密码关闭时保持现有分支。
- [ ] 对超时、缺失继续地址、异常响应分类为现有 unknown/attention 语义，不自动换邮箱或重复注册。
- [ ] 运行 Task 1 测试并补充现有 OpenAI auth 测试。

## Task 3: 抽取并保护邮箱验证中间态

- [ ] 先为驱动无关 checkpoint helper 写失败测试：新账号创建、待验证账号更新、已完成账号拒绝覆盖。
- [ ] 实现 helper，并让 Roxy 适配为传入可选 profile 元数据；Protocol 在注册请求成功、进入邮箱验证前保存密码 checkpoint。
- [ ] 确保现有 access token、邮箱租约和 account binding 不被空 token 覆盖或降级。
- [ ] 运行相关 Roxy、存储和 Protocol 测试。

## Task 4: 补齐协议续跑边界与端到端编排测试

- [ ] 检查 dispatcher 对 `existing_password`/待邮箱验证 checkpoint 的分流，保证 Protocol 不会静默回退 Roxy。
- [ ] 若已有信息足够，接入 Protocol 的同账号续跑；若信息不足，返回明确的可审计 attention/unknown 结果并保留原任务链。
- [ ] 覆盖 OTP 成功、OTP 失败、OAuth callback/session 缺失、2FA 成功和未知结果保护。
- [ ] 运行最小相关回归：
  `PYTHON_DOTENV_DISABLED=1 python -m pytest -q tests/test_protocol_registration_password.py tests/test_openai_auth_registration_flow.py tests/test_registration_twofa_auto.py tests/test_twofa_flow.py tests/test_roxy_twofa.py`

## Task 5: 真实单任务 Protocol 脱敏抓包验收

- [ ] 只在确认当前配置、代理、邮箱池和数据库状态后，选择一个明确的单任务，不启动批量注册，不启用 Codex。
- [ ] 打开 Protocol debug capture，记录脱敏端点、状态码、阶段事件和 request id；不输出原始响应或凭证。
- [ ] 验证端点顺序至少包含密码注册、邮箱 OTP send/validate、create_account、callback/session、MFA（若启用）和最终后处理；若外部 Auth 或收件线路阻断，记录已确认前缀及精确阻塞点，不把 Roxy 恢复结果冒充 Protocol 结果。
- [ ] 从 PostgreSQL 核对同一任务的最终状态、账号绑定、密码 checkpoint 清理/保留、邮箱 lease 和 `request_unknown` 情况。
- [ ] 若真实请求失败，先区分控制面、代理、邮箱 OTP、协议响应和持久化原因；不得盲目重试或换邮箱。

## Task 6: 最终验证与交付

- [ ] 运行 fresh 的最小测试与必要扩展测试，保存命令和结果。
- [ ] 检查 `git diff --check`、工作区状态和未跟踪私有文件，确保没有敏感数据进入补丁。
- [ ] 如用户未明确要求，不提交、不推送、不重启服务。
- [ ] 最终报告明确区分代码修改、测试通过、真实抓包、数据库终态，以及尚未验证的边界。

## Review Focus

- 是否真正执行了 `POST /api/accounts/user/register`，而不是只增加 challenge 字段。
- Sentinel/`SO` 是否来自同一次有效 bundle，continue URL 是否经过校验。
- unknown、已有 token、邮箱租约和待验证密码是否 fail-closed。
- Protocol 与 Roxy 是否共享正确的业务状态，但没有互相静默回退。
- 测试是否包含失败/未知分支，真实抓包是否脱敏并与 PostgreSQL 任务证据对应。
