# 协议改密闭环实施与可行性验证

> **当前状态（2026-11-27）：** P1 实现、直接相关定向回归和本地真实账号/API 验收已完成。应用版本 `dc43d65e` 已在本地上线并完成健康检查；代码未推送远端，未部署 Oracle。P2/P3 只做离线 probe，不启动真实采集或严格重放开发。
> **执行约定：** 使用 superpowers:subagent-driven-development 分工实施，先运行会失败的相关测试，再完成实现；每项完成后审查，最后做整体审查与真实账号验收。

**目标：** 单次协议改密任务完成新密码认证、完整凭据保存和保存后业务核验，中断重跑只补未完成阶段。

**架构：** 复用现有密码四态、共享调度与账号租约。协议改密独立启用收尾标记，标记加密存于既有 recovery，不改变补密码、注册与 Roxy 契约。业务网络核验在存储事务之外执行。

**技术栈：** Python、PostgreSQL、现有协议/Rust 刷新驱动、pytest。

**依据：** [设备画像复用与协议改密方案](../../architecture/device-profile-reuse.md)，本次首先实施 P1；P2/P3 仅做离线可行性验证。

## 全局约束

- 使用隔离 worktree 与非生产 `turb_test`；存储用例继承 `PostgresTestCase`。
- 不改变注册步骤、生成器、Rust 依赖及 Roxy 行为，不新增配置或后台调度系统。
- 未知结果沿用同一候选；密码确认不回退；收尾未完成不得报告整体成功。
- 不使用 `rm -r`，不输出或提交私有凭据和运行资料。
- v1/legacy 账号在改密后的密码验证阶段显式调用现有 `protocol_v2`；普通 AT 刷新继续沿用原有驱动与调用顺序。
- 先审查与定向验证，再提交和本地部署；Oracle 保持独立部署。

## 任务 1：密码确认后的持久收尾

**文件：** `core/storage/accounts/password_recovery.py`、`core/auth/browser/password_recovery.py`、`core/storage/accounts/protocol_sessions.py`、`tests/accounts/test_password_change_completion_store.py`。

**接口：**

```python
PrivateCheckpoint.completion_pending: bool
PasswordRecoverySession.confirm(confirmation, *, completion_pending=None) -> str
PasswordRecoverySession.resume_manual_password_change() -> bool
save_manual_password_change_session(recovery_id, *, access_token, session_info, protocol_session, auth_method="", **owner) -> None
complete_manual_password_change(recovery_id, *, expected_version, access_token, **owner) -> PrivateCheckpoint
```

- [x] 写并运行失败测试：confirmed 待收尾可接管，普通 confirmed 不恢复；旧 owner 与密码冲突不能写回。
- [x] 实现仅协议改密启用的密文收尾标记及恢复；默认四态语义不变。
- [x] 实现围栏内账号 AT/session 与私有 Cookie 同事务保存；默认会话仓储调用行为不变。
- [x] 验证收口失败保留标记，成功才清除；定向运行新增存储测试与相关既有回归。

## 任务 2：收尾与业务核验

**文件：** `core/accounts/password_setup/reset_completion.py`、`tests/accounts/test_password_reset_completion.py`。

**接口：**

```python
validate_password_session(account: dict, email: str, auth: dict) -> dict
complete_password_reset(*, recovery, owner, account, email, auth, proxy=None, checkpoint=None, report=None) -> dict
```

- [x] 写并运行失败测试：缺完整会话、身份冲突、写回不一致与业务拒绝不能报成功。
- [x] 使用任务 1 接口保存、读回；业务请求必须使用读回的 AT。
- [x] 复用只读业务接口核验身份，明确区分撤销、限流、安全拦截、传输和格式原因。
- [x] 成功后调用 `complete_manual_password_change`；失败保持密码与收尾事实。

## 任务 3：邮箱、候选与远端错误

**文件：** `core/accounts/password_setup/reset_support.py`、`tests/accounts/test_password_reset_support.py`。

```python
generate_reset_password(old_password: str = "") -> str
check_reset_mailbox(email: str) -> None
check_reset_response(response, *, stage: str, result_unknown: bool = False) -> dict
```

- [x] 写并运行失败测试：固定注册密码不影响改密候选，临时邮箱故障不能变永久失效。
- [x] 复用原邮箱资源；不领取邮箱，不建立失败缓存，不发测试邮件。
- [x] 远端错误保留阶段、具体原因、可重试性与未知结果，摘要不带原始正文。

## 任务 4：执行链路整合与验收

**文件：** `core/accounts/password_setup/reset.py`、相关配置快照调用入口、`tests/accounts/test_password_reset_protocol.py` 及新闭环用例。

- [x] 先补失败用例：未知候选先认证；confirmed 收尾不发 reset OTP；发码前记录时间锚点；完整会话验证失败不确认密码。
- [x] 正常流程串接任务 1–3；在登录回调关闭前取得新 Cookie，保留选定驱动与设备资料。
- [x] 只运行受影响回归；独立审查共享存储与执行边界。
- [x] 在独立环境验证最小闭环；本轮真实验收范围限定为 protocol reset 与当前配置的 Rust 路径。
- [x] 完成代码审查、提交、本地部署及健康检查；通过现有任务 API 验收单账号改密，无需再发刷新 AT 任务。

本轮尚未覆盖 `password_driver=protocol` 与 `at_refresh_driver=browser_roxy` 的组合。复用已登录 Roxy Profile 但没有明确密码提交证据时不得报成功；不改变 Roxy 默认行为。

本地真实验收记录：

- 账号 `#8714`，任务 `task536056`，最后运行 `run539466`，时间为 `2026-11-27 20:25:33+08`：`send OTP → 新密码重新登录 → 密码/AT/完整 session 与私有 Cookie 保存读回 → 新 AT 业务身份验证` 全部成功，`completion_pending=false`。`verified.json` 确认密码和 AT 已变化、session AT 一致、`email/user/account` 身份匹配，仅有一项 `password_change`，没有额外 refresh 任务。详细回执保存在 ignored 的 `logs/run/` 运行资料中，可用 `task536056`、`run539466` 和 `verified.json` 定位。
- 账号 `#8713`，任务 `task536034`，最后运行 `run539464`：在 `send_otp` 阶段收到 `invalid_auth_step`；同账号原生浏览器携 `auth_page` 也得到相同拒绝，未提交新密码。该结果不称为封禁，也不宣称已经确认远端根因。

本轮未对真实任务注入进程中断；候选恢复、确认后补收尾与失效执行围栏由隔离数据库测试覆盖。

最后修正后的定向结果：入口与闭环整合 55 项及 6 个子测试；默认恢复调用与入口 36 项；业务响应解析与收尾 31 项及 16 个子测试；新旧恢复仓储 58 项及 24 个子测试。更早一轮中刷新驱动及相关既有用例通过，发现的 6 个默认调用契约失败已在上述 36 项中复验修正。上述用例存在交集，不累加为唯一用例总数。

验证命令通过根仓库 `.venv/bin/python tools/test_isolated.py --profile all -- <上述直接相关测试> -q` 执行；连接仅使用显式非生产库。真实账号操作通过本地服务的受管任务/API 执行，不用开发脚本绕过生产库保护。
