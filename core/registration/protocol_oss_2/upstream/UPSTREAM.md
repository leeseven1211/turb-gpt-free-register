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
2. AuthFlow 的会话工厂接到本地 `runtime.create_http_session`，固定复用当前任务已领取代理；每次会话重建保留停止检查、受控任务抓包与协议流量关联；流式导航诊断不读取正文。
3. 新注册恢复原先的前置密码步骤：注册验证码落地页和 `passwordless_signup` 分支主动尝试创建密码，再重新发码；静态 HTML 密码链接不再作为必要条件。原身份续跑由原 Attempt/Run 的执行类型识别；CLI 仅预认证中断或仅生成候选时仍执行前置密码，不按执行次数降级。续跑按本轮实际密码入口、验证码、资料或回调继续，不从验证码页或资料页强制创建密码；复用原邮箱、候选密码和 TOTP。密码创建请求明确被拒时沿用邮箱验证回退并保留 HTTP 状态和白名单错误码；传输结果未知仍保留原请求事实。只有取得匹配 Token 且当前认证链创建或验证过密码，才确认密码；仅 OTP 取得 Token 时保存核心账号，密码保持候选，交给原生账号补全入口处理。不把邮箱判死或重新投入池中。
4. 邮箱验证后恢复原有资料及回调处理，资料沿用调用方姓名和生日，失败保留原诊断。完整 `/api/auth/session` 统一 Token 字段后交给本地 PostgreSQL 核心持久化入口；后续空响应不覆盖同一认证链已经核验的完整会话，身份或 Token 冲突仍明确拒绝。
5. 关闭上游凭据正文日志和直接输出；2FA、套餐查询、Codex OAuth 和其他后处理沿用本地实现。

HTTP 使用上游 wreq 适配器，Chrome152 画像与上游 `_turb_bridge.py` 的选择一致。该桥的文件数据库、全局环境补丁和日志不运行。上游关于通过率、优惠资格和因果的注释保留作来源记录，不能作为本项目实测结论。
