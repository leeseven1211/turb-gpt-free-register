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
3. 密码提交前后调用本地检查点钩子；失败重跑使用原 Attempt 的邮箱、密码和 TOTP，已有账号可进入认证分支，不把邮箱判死或重新投入池中。
4. 资料提交沿用调用方姓名和生日；完整 `/api/auth/session` 响应交给本地 PostgreSQL 核心持久化入口。
5. 关闭上游凭据正文日志和直接输出；2FA、套餐查询、Codex OAuth 和其他后处理沿用本地实现。

HTTP 使用上游 wreq 适配器，Chrome152 画像与上游 `_turb_bridge.py` 的选择一致。该桥的文件数据库、全局环境补丁和日志不运行。上游关于通过率、优惠资格和因果的注释保留作来源记录，不能作为本项目实测结论。
