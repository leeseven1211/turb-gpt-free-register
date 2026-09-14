# 认证能力拆分与合同

本次拆分把注册、Codex OAuth、账号操作/查活共用的 Selenium 认证能力按实际职责分开。`roxy.py` 只保留 Roxy 生命周期、注册阶段编排、检查点与任务进度；它不再承载 DOM、邮箱验证码、密码、会话或 MFA 的具体实现。

## 模块边界

```text
registration/roxy.py              注册编排、Roxy profile/任务检查点
roxy_codex_oauth.py               OAuth/账号操作编排
codex_retry_service.py             补跑编排、持久化检查点、有限重试
        │
        └── registration/selenium_auth.py      稳定公开入口（兼容薄层）
                │
                └── registration/auth_capabilities.py  小型 facade/兼容边界
                        ├── selenium_resource.py  driver、导航、浏览器资源
                        ├── selenium_dom.py       页面识别、快照、通用 DOM 交互
                        ├── email_otp.py         邮箱入口、邮箱 OTP、提交后状态
                        ├── password_auth.py     注册密码、登录密码、资料页
                        ├── session_auth.py      ChatGPT session/accessToken
                        └── mfa_auth.py           TOTP、邮箱 re-auth、安全设置
```

共享模块只能依赖领域合同、外部邮箱/协议/浏览器资源；不能导入 `registration_service`、`roxy_codex_oauth` 或 `registration.roxy`。应用层把自己的停止信号和截止预算注入 `AuthExecutionContext`，因此共享能力不需要反向调用任务服务。

## 执行上下文与兼容

`AuthExecutionContext` 支持：

- 可调用取消探针或 `Cancellation`；
- `StageBudget` 与单调时钟 deadline；
- OAuth 登录挑战的 detector/submitter/resolver 回调；
- 只读 metadata。

上下文和旧 monkeypatch 覆盖都通过 `ContextVar` 按调用/线程隔离。Roxy 注入 `registration_service.StopRequested`，OAuth 注入 `OperationCancelled`，Codex 补跑注入 `CodexRetryStopped`。兼容层不会在每次调用时重绑定共享模块全局，也不会让共享能力导入这些编排器。

`selenium_auth` 保留原公开名称；`roxy.py` 保留旧私有名称为薄包装，包装只负责收集当前调用显式覆盖并进入一次兼容上下文。新的调用方应使用公开名称或直接使用职责模块，不应依赖私有实现。

## 步骤结果与安全边界

`core.auth_challenge.StepResult`/`AuthStepResult` 和 `AuthErrorCode` 是跨注册、OAuth、账号操作的结构化步骤合同。结果包含 stage、错误码、下一状态、检查点、远端身份、是否已 dispatch、是否收到远端响应及安全 evidence。原始 URL 查询参数、响应体、密码、OTP、TOTP、Token 和邮箱值不会进入 evidence。

只要密码/OTP/MFA 请求已经发出但没有收到远端响应，结果会被规范化为 `request_unknown`，下一动作是 `manual_reconcile` 且不可自动重试。提交前检查点仍先落本地；远端已成功但页面未确认的路径不会被改写为普通失败或扩大重试。既有注册的 `request_unknown`、邮箱验证待确认和远端已存在边界继续由原任务/存储层投影。

## 验证范围

测试只通过隔离 launcher 运行，连接独立的 `turb_opt_20260914` 数据库；真实账户、生产 dotenv、生产库和远程浏览器操作均不启用。覆盖合同/ContextVar 并发隔离、取消与预算、密码、邮箱 OTP、TOTP、电话国家选择、邮箱恢复、账号补跑、账号级登录、注册后置和 dispatcher。

本次没有改写 `run_roxy_registration`、`run_twofa_worker` 或 Codex 补跑任务入口，也没有扩大自动重试策略。
