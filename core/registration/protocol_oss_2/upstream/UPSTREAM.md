# 开源protocol-2 来源与本地适配

- 仓库：[wangshen233/turb-gpt-free-register-oss-20260928](https://github.com/wangshen233/turb-gpt-free-register-oss-20260928)
- 固定提交：`7df094e05e48a74eeacc4ff6e3c27165def21cae`
- 同步日期：2026-10-20
- 原目录：`vendor/gpt-register-tool/协议/`
- 组件许可证：AGPL-3.0，原文保留于 [LICENSE](LICENSE)。上游主项目的 MIT 许可证不替代组件许可证。
- 原文件校验值：[SOURCE_SHA256.json](SOURCE_SHA256.json)，用于核对同步前内容。

仅引入 AuthFlow、指纹、HTTP/wreq、Sentinel 和必要类型。`environment.py` 仅保留上游出口比较纯函数；`mail_provider.py` 只提供类型接口。未引入上游 WebUI、SQLite、邮箱领取器、套餐结算检查器或批次代理调度。

本地适配修改了以下接缝：

1. 所有内部导入改为此包的完整路径，不改写 `sys.path` 或顶层 `config`、`webui` 模块。
2. AuthFlow 的会话工厂接到本地 `runtime.create_http_session`，复用当前任务已领取代理；当前注册关键请求的 403 和最终传输失败交给注册业务层统一预算换线，不在驱动自行领取代理。明确可重放动作在原调用栈继续；业务拒绝继续换线时直接退出上游重试，不让关键 403 被预热循环吞掉。每次换线先严格停止旧连接，关闭失败时保留旧租约并报告 `registration_route_close_failed`；重建 wreq Client 时复用原生 Cookie Jar 和同一画像，保留同名跨域 Cookie 及 path、secure、HttpOnly、SameSite、expiry，并同步父会话、当前代理和新租约流量关联；流式导航诊断不读取正文。
3. 新注册恢复原先的前置密码步骤：注册验证码落地页和 `passwordless_signup` 分支主动尝试创建密码，再重新发码；静态 HTML 密码链接不再作为必要条件。原身份续跑由原 Attempt/Run 的执行类型识别；CLI 仅预认证中断或仅生成候选时仍执行前置密码，不按执行次数降级。续跑按本轮实际密码入口、验证码、资料或回调继续，不从验证码页或资料页强制创建密码；复用原邮箱、候选密码和 TOTP。密码创建请求明确被拒时沿用邮箱验证回退并保留 HTTP 状态和白名单错误码；传输结果未知仍保留原请求事实。只有取得匹配 Token 且当前认证链创建或验证过密码，才确认密码；仅 OTP 取得 Token 时保存核心账号，密码保持候选，交给原生账号补全入口处理。不把邮箱判死或重新投入池中。
4. 邮箱验证后恢复原有资料及回调处理，资料沿用调用方姓名和生日，失败保留原诊断。完整 `/api/auth/session` 统一 Token 字段后交给本地 PostgreSQL 核心持久化入口；后续空响应不覆盖同一认证链已经核验的完整会话，身份或 Token 冲突仍明确拒绝。
5. 关闭上游凭据正文日志和直接输出；2FA、套餐查询、Codex OAuth 和其他后处理沿用本地实现。
6. 密码创建、资料提交无响应以及一次性回调不直接重放。换线后在同一 AuthFlow 先读取完整 Session，再使用严格原身份登录入口：复用原邮箱、唯一候选密码和 TOTP，不允许退回 signup 或重新创建密码。原资料提交未知时禁止再次创建资料；原密码未知但资料从未提交时，仅在实际登录落点明确要求资料时补交。已派发未知动作追加原 Attempt/Run 的提交事实，后续登录成功也不改写原创建回执。底层有限传输重试保留于明确安全请求，未知写入及一次性回调直接交还受控恢复。
7. 注册 2FA 仅在本地 `setup_2fa_protocol` 调用期间使用当前驱动的换线作用域。403 可在原栈继续；无响应换线后只读 `mfa_info`，不重复 enroll 或 activate。远端 MFA 已启用不能证明本地候选密钥可用，候选继续保持待确认并明确报告；套餐、独立 AT、独立 2FA 和 Codex 不获得此恢复策略。
8. 资料接受后返回受信的 `/verify-your-identity` 时，明确分类为尚需身份验证，并保留原任务供重跑。已有账号分支透传该原因；不继续读取空 Session 或重新提交资料，也不把 HTTP 200 当成完整注册成功。

HTTP 使用上游 wreq 适配器，Chrome152 画像与上游 `_turb_bridge.py` 的选择一致。该桥的文件数据库、全局环境补丁和日志不运行。上游关于通过率、优惠资格和因果的注释保留作来源记录，不能作为本项目实测结论。
