# 上游来源

- 仓库：<https://github.com/myfanhua/turb-gpt-free-register>
- 固定提交：`83721dc33a83b3e09dfdf7d91cc511b0124d9b4c`
- 许可证：MIT，见本目录 `LICENSE`
- 上游注册入口：`main.py`
- 本次同步源码：`main.py`、`core/chatgpt_auth.py`、`core/openai_auth.py`、`config/openai_protocol.py`

`main.py` 保留为未修改的流程基线，不在本系统运行。`core/chatgpt_auth.py` 与
`core/openai_auth.py` 的请求实现来自上游；本地补丁仅将协议配置导入改为本目录快照，
并继续使用本地 `BrowserSession`、Sentinel 公共组件和任务取消/流量上下文。实际调用由
`core.registration.protocol_oss` 适配器组织；邮箱 OTP、代理分配、Attempt/Run、密码与
TOTP 检查点、账号持久化、套餐、2FA、Codex、Flow 和任务收口均使用本地服务。

## 更新步骤

1. 在临时 checkout 中检出目标上游 commit，记录 commit 与许可证变化。
2. 对照本目录记录的同步文件，查看上游 `main.py`、`core/chatgpt_auth.py`、
   `core/openai_auth.py` 和 `config/openai_protocol.py` 的差异。
3. 只同步注册协议需要的源码与配置，不导入上游邮箱池、账号导出、SQLite、日志、抓包或账号数据。
4. 保留 `LICENSE`；重新应用且只应用本地配置导入补丁，确认认证 helper 仍通过本地会话和 Sentinel 公共组件运行。
5. 更新本文件的 commit、文件清单和本地差异说明，运行 vendor、adapter、dispatcher 及本地 Protocol 回归测试。

不得将上游 `main.py` 的账号保存、邮箱回收、Codex、2FA 或 Flow 逻辑接入本地任务链。
