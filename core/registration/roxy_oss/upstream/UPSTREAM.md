# 上游来源

- 仓库：<https://github.com/myfanhua/turb-gpt-free-register>
- 固定提交：`9a0c55baa9b7d2f9c09ba6eea8cdec200a44eb5e`
- 许可证：MIT，见本目录 [LICENSE](LICENSE)
- 上游源码：[roxy_registration.py](roxy_registration.py)，来自 `core/roxy_registration.py`，仅清除尾随空白，其余保持原样，仅供对照，禁止导入或执行其注册入口。
- 实际运行文件：[browser_helpers.py](browser_helpers.py)，从上述固定源码提取九个页面辅助函数，函数体保持一致。

## 运行边界和本地差异

`roxy_oss` 是独立注册方式，使用上游邮箱入口 DOM 定位、邮箱入口选择、资料页识别、
姓名/生日/年龄填写和同意项处理；不运行完整上游注册入口。提取的函数为：
`_email_entry_state`、`_find_visible_email_input_js`、`_is_oauth_consent_like`、
`_click_email_entry_option`、`_is_profile_like`、`_set_element_value`、
`_select_or_type`、`_fill_birthday_or_age`、`_accept_profile_consents`。

提取模块只修改模块说明和依赖导入：`_find_any`、`_human_click`、`_human_type_text`、
`_log_prefix` 接本地共享能力，`time` 接本地 `time_proxy`。认证取消和阶段预算由本地外层
循环与共享浏览器能力检查；上游 spinbutton 内部固定短暂等待本身没有独立硬截止。
每个注册调用创建独立 provider，在邮箱和资料阶段通过已有 ContextVar
能力覆盖调用上游 DOM 函数；结束或异常均恢复覆盖范围，不修改进程全局函数绑定。

本地 Roxy 编排继续负责代理池、邮箱来源、Profile 生命周期、流量、省流量、任务进度、
Attempt/Run、原窗口恢复、密码准备与提交检查点、邮箱 OTP 收取与提交事实、资料提交确认、
完整会话及邮箱身份核验、核心账号持久化和套餐/2FA/Codex 后处理。特别保留本地先填年龄
后填姓名的顺序，避免当前 about-you 页面重渲染清空姓名。

上游原版自带的邮箱领取/释放、密码/OTP 提交循环、可能输出验证码或凭据的日志、账号文件
保存、后处理和失败清理均不接入本地运行。账号 `extra.registration_driver`、认证结果的
`auth_method`、独立入口的驱动身份都记录为 `roxy_oss`。

## 2026-10-30 本地目录迁移

已启用的 `browser_helpers.py` 仅随共享认证能力归位调整三个 import 目标：
`core.registration.auth_context` → `core.auth.browser.auth_context`、
`core.registration.selenium_dom` → `core.auth.browser.selenium_dom`、
`core.registration.selenium_resource` → `core.auth.browser.selenium_resource`。
导入符号、别名、位置、顺序及函数体保持原样。来源对照 `roxy_registration.py` 继续逐字保留，禁止导入或执行；不为它修复旧依赖，许可证和其他来源文件不变。

## 更新步骤

1. 在临时 checkout 核对目标 commit 和许可证，更新基线与本文件固定提交；只清除尾随空白。
2. 对照九个页面辅助的变更，仅提取这些完整函数，保留上述本地依赖适配。
3. 不引入上游配置、账号数据、邮箱管理、存储、密码/OTP 日志或原版运行入口。
4. 运行 vendor、provider 并发与异常恢复、dispatcher 以及本地 Roxy 相邻回归测试。
