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

## 2026-10-30 本地目录迁移

本地共享能力按业务归位后，只调整以下已启用接缝的 import 目标路径：

| 运行文件 | 旧模块 → 现模块 |
| --- | --- |
| `core/chatgpt_auth.py` | `core.session` → `core.auth.protocol.session` |
| `core/openai_auth.py` | `core.session` → `core.auth.protocol.session`；`core.sentinel` → `core.auth.protocol.sentinel`；`core.sentinel_runner` → `core.auth.protocol.sentinel_runner`；`core.registration_service` → `core.registration.service` |

导入符号、别名、所在位置、顺序及延迟时机保持原样；本次目录迁移不改请求实现、取消检查或函数体的其他内容。上面的 `core/` 相对路径指本 upstream 目录内的运行文件，模块目标指本地项目。`main.py` 继续逐字保留为禁止运行的来源对照，不修复它的旧依赖，也不接入本地任务链；许可证和其他来源文件不变。

## 更新步骤

1. 在临时 checkout 中检出目标上游 commit，记录 commit 与许可证变化。
2. 对照本目录记录的同步文件，查看上游 `main.py`、`core/chatgpt_auth.py`、
   `core/openai_auth.py` 和 `config/openai_protocol.py` 的差异。
3. 只同步注册协议需要的源码与配置，不导入上游邮箱池、账号导出、SQLite、日志、抓包或账号数据。
4. 保留 `LICENSE`；保留已有本地接缝差异，并应用上表中的共享能力导入路径；不得把目录迁移混为上游请求逻辑更新，确认认证 helper 仍通过本地会话和 Sentinel 公共组件运行。
5. 更新本文件的 commit、文件清单和本地差异说明，运行 vendor、adapter、dispatcher 及本地 Protocol 回归测试。

不得将上游 `main.py` 的账号保存、邮箱回收、Codex、2FA 或 Flow 逻辑接入本地任务链。
