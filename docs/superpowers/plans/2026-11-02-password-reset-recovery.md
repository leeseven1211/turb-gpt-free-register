# Roxy 密码重置与资料续跑实施计划

> **代理执行要求：** 使用 `superpowers:subagent-driven-development` 按任务实施和审查，先复现失败再修改。

**目标：** 明确要求改密的 Roxy 原账号能持久保存新密码、完成改密并继续资料页，重启或重跑不丢凭据。

**架构：** 私有存储提供一次生成、执行围栏、版本推进及账号/Attempt 原子换密；浏览器复用现有忘记密码步骤，通过可选恢复对象保存动作与确认结果；Roxy 和手动改密分别提供真实执行身份。普通注册和协议驱动的调用行为保持原样。

**技术：** Python、Selenium、CDP、PostgreSQL、Fernet、pytest。

**设计：** [已确认设计](../specs/2026-11-02-password-reset-recovery-design.md)。

## 全局约束

- 中文文案；禁止递归删除，保留无关修改和原邮箱身份。
- 工作区：Codex 管理的 `password-reset-recovery`；测试库 `turb_test`、独立 `test_` schema。
- 使用 `tools/test_isolated.py --profile all -- <指定测试> -q`，不连接生产数据库。
- 候选、旧密码只在私有密文包中，不进入公开任务数据或日志；私有 dataclass 密码字段 `repr=False`。
- 注册与操作 execution_id 属于不同命名空间，分别校验；手动操作还必须验证账号 lease。
- 不放宽原有密码一致性、未决请求或邮箱租约保护。

## 冻结存储契约

模块：`core/storage/accounts/password_recovery.py`。

`PrivateCheckpoint` 字段：`recovery_id, state, version, account_id, email, purpose,
operation_run_id, operation_execution_id, attempt_id, registration_run_id,
registration_execution_id, account_password_version, old_password, password`。

所有函数以命名参数接收共同身份字段：

```python
owner = dict(
    email=email, account_id=account_id, purpose="registration",
    operation_run_id=operation_run_id,
    operation_execution_id=operation_execution_id,
    operation_lease_token=None,
    attempt_id=attempt_id, registration_run_id=registration_run_id,
    registration_execution_id=registration_execution_id,
)
checkpoint = prepare_password_recovery(**owner, candidate_factory=registration_password)
checkpoint = get_password_recovery(checkpoint.recovery_id, **owner)
checkpoint = transition_password_recovery(
    checkpoint.recovery_id, **owner, expected_version=checkpoint.version,
    state="started", confirmation=None,
)
checkpoint = transition_password_recovery(
    checkpoint.recovery_id, **owner, expected_version=checkpoint.version,
    state="confirmed", confirmation="candidate_login",
)
```

`prepare_password_recovery` 返回 `PrivateCheckpoint`，仅无待完成记录时调用 factory；
`resume_password_recovery(**owner)` 返回同账号待完成记录或 `None`，不创建候选，允许在旧执行结束后接管。
`get_password_recovery(recovery_id, **owner)` 与 `transition_password_recovery` 不自动接管。
`purpose` 只允许 `registration/manual`；状态为 `prepared/started/unknown/confirmed`；确认类型只允许
`password_change_response/candidate_login`。确认函数仍由浏览器提供精确配对证据，存储不能凭跳转推断。

## 任务 1：私有恢复存储

**文件：** 新增 `core/storage/accounts/password_recovery.py`、`tests/accounts/test_password_recovery_store.py`。

**产物：** 上述四个接口与 dataclass。使用独立私有表 `account_password_recoveries`，不复用诊断上下文表：
历史任务删除不应级联删除未完成候选。复用现有配置主密钥的 Fernet 能力，加用途及格式版本校验。

- [ ] 先编写真实隔离 PG 测试：factory 只调用一次，prepared 不改变当前密码，旧 worker/错邮箱/错版本被拒绝。
- [ ] 运行定向测试，确认缺少私有恢复能力而失败。
- [ ] 实现身份验证、私有密文行、按账号串行准备、失效执行接管和版本推进。
- [ ] 实现确认事务：CAS 旧密码，更新 Accounts 与同账号同邮箱关联 Attempt，保留旧密码及其他字段，进度不降级。
- [ ] 覆盖中途异常整笔回滚、重复确认幂等、无关套餐字段保留、公开投影不含凭据及主密钥缺失时提交前失败。
- [ ] 返回测试命令和真实结果，等待独立审查；不提交或重启服务。

## 任务 2：可恢复的浏览器重置能力

**文件：** `core/codex/roxy/oauth.py`；新增 `core/auth/browser/password_recovery.py`、`tests/auth/test_password_recovery_flow.py`；必要的固定端点元数据在 `core/network/response_diagnostics.py`，不得与注册适配器重复写同一文件。

**输入：** 任务 1 接口。**输出：** `PasswordRecoverySession` 以 owner 参数封装检查点，提供
`prepare(candidate_factory) -> str`、`mark_started()`、`mark_unknown()`、`confirm(confirmation) -> str`、
`checkpoint`；显式恢复方法只复用待完成候选。现有 reset helper 新增默认关闭参数
`recovery=None, allow_profile_handoff=False`，老调用者行为不变。

- [ ] 先写提交前保存失败不点击、候选只生成一次、提交后异常仍保留候选的测试并观察失败。
- [ ] 在填写/提交新密码前 `recovery.prepare(registration_password)`，派发前标记 started；异常按真实派发状态记 unknown。
- [ ] 给恢复路径增加明确密码变更响应或候选密码登录成功的确认；不能把“表单消失”当成功。
- [ ] 为默认关闭的资料交接识别可信同源、可见资料表单，返回交接给原资料步骤；不能标成完整会话成功。
- [ ] 待完成的 started/unknown 候选先用于恢复认证，不重新生成、重复提交原未知改密动作。
- [ ] 跑新测试及 `tests/auth/test_password_reset_flow.py`、`tests/auth/test_roxy_auth_challenge_flow.py`，返回测试记录供审查。

## 任务 3：注册与手动改密接入

**文件：** `core/registration/roxy/__init__.py`、`core/auth/browser/browser_submission.py`、`core/codex/retry_service.py`，必要的上层 owner 传递在 `webui/runtime.py`；测试在 `tests/registration/test_roxy_password_recovery.py`、`tests/accounts/test_account_change_actions.py`。

**输入：** 私有存储与 `PasswordRecoverySession`。**输出：** Roxy 原身份续跑的严格触发和手动改密共用恢复对象。

- [ ] 先测正确密码请求 HTTP401/reset_required 触发；其他401、错请求/目标、未派发、旧响应均保持原失败分支。
- [ ] 为本次密码请求保存 target/requestId/安全 auth_error，严格匹配，不改变其他请求的 guard。
- [ ] 当前密码请求明确拒绝后才启动一次已有重置步骤；准备新候选失败则不点击。
- [ ] 注册执行上下文从当前 RegistrationRun/Job 映射到真实 OperationRun，手动路径从 handler 传真实 execution fence。
- [ ] 原注册续跑开始时恢复已有 pending 候选，账户与 Attempt 确认同步后用新密码继续。
- [ ] 资料交接后走原资料提交与 Session 身份核验，2FA、套餐和最终写回沿用现有流程。
- [ ] 手动改密使用同一恢复存储并衔接资料页，修复按钮已在基线提交中，不重做或扩大存储脱敏白名单。
- [ ] 跑注册恢复、手动改密和现有 OTP/资料提交相邻测试，提交审查包。

## 任务 4：整体验证与真实恢复

**文件：** README 使用说明及存储架构相关章节按最终实现同步，计划勾选真实完成状态。

- [ ] 审查每项任务的设计符合性和代码质量，修复会影响正确性的发现。
- [ ] 统一隔离入口运行新增测试和密码、资料、原窗口恢复、操作派发相邻回归，Ruff、`git diff --check` 通过。
- [ ] 核对没有私有数据入暂存，提交隔离分支并整合回 main；保留用户已有改动。
- [ ] 等待实际运行任务收口后重启同一 launchd 服务，核对 PID/cwd/端口、新增日志和三个健康/登录接口。
- [ ] 先真实续跑一个明确要求重置的账号，验证密码安全保存、资料推进和最终 Token，再处理其余目标账号。
- [ ] 最终分别报告代码/提交/推送/重启/真实成功数；未到的新邮件或远端拒绝须据实保留原因。
