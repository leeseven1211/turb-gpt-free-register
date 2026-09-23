# 浏览器流程省流量策略设计

## 现状与目标

当前 Roxy 打开参数在总开关打开时对全部流程禁用图片及可选字体，但 `BrowserDataSaver` 的 CDP 规则只在注册流程安装。刷新 AT、旧 AT 查活、独立 Codex OAuth 与账号操作仍加载完整页面资源。注册窗口复用做 Codex OAuth 时，注册阶段的 URL 规则会留在同一个 CDP target 中。

上游参考版本为 [myfanhua/turb-gpt-free-register `4e6ee0b`](https://github.com/myfanhua/turb-gpt-free-register/commit/4e6ee0be04468402b90c03e32fbad2cc14e8bcc9)：采用启动参数、按阶段拦截、浏览器流量汇总和静态资源缓存。本地 PostgreSQL、任务上下文与采集器实现不同，按本地调用链适配。

目标是复用现有采集器和拦截器，统一选择每个流程的规则并明确窗口所有权，不重做浏览器客户端或存储模型。浏览器流量仍是 CDP 可观测值，不代表代理商计费流量。

## 策略边界

- `BROWSER_DATA_SAVER_MODE` 仍是总开关；关闭时所有新流程均不安装拦截，打开参数也不加省流量标志。
- `BROWSER_DATA_SAVER_AUTH_FLOWS` 控制 `token_refresh`、`live_check`、`codex_oauth`、`account_action` 四类流程；默认全选。列表可逐项关闭。注册仍沿用总开关和已有规则。
- 注册保留现有资源类型及 URL 配置。注册之后复用同一窗口进入 Codex OAuth 时，重新安装认证安全规则，覆盖注册规则。
- 认证安全规则只允许图片、媒体类型及固定的、明确非认证用途的遥测 URL。忽略注册配置中的脚本、auth-cdn、session、sentinel、CES 注册接口等模式；不拦截文档、脚本、样式、XHR、fetch、WebSocket。
- 旧 AT 查活虽然只打开同源静态页，仍按认证安全规则处理。这样不会碰它的受控 fetch。
- 每个新开窗口在调用 Roxy `/browser/open` 时传入流程名，启动标志和随后安装的 CDP 规则使用同一选择。未知流程沿用旧行为，避免影响未覆盖的外部调用。
- 安装或切换规则失败只记录类别并继续浏览器业务。每个流程结束前记录拦截汇总；采集器继续保存现有摘要，不保存 URL、Cookie、响应体或认证值。
- 静态资源缓存留待单独验证：上游方案需要持久化响应内容与 CDP Fetch 代理，跨登录态隔离和流量核算尚未完成，不纳入本次默认路径。

## 流程接入

1. `core/browser_flow_policy.py` 负责流程名、可用性、资源规则、Roxy 打开参数选择、Selenium 安装及采集器关联。
2. `core/registration/roxy.py` 保留原注册拦截，并在同窗口 Codex OAuth 入口由 Codex 流程切换到认证安全规则。
3. `core/roxy_liveness.py` 在打开窗口后关联任务/账号上下文，构建 driver 后安装 `token_refresh` 规则。
4. `core/live_check_browser.py` 在 driver 建立后安装 `live_check` 规则。
5. `core/roxy_codex_oauth.py` 的独立授权与账号操作各自安装对应规则；复用注册窗口时覆盖旧规则，但不负责关闭注册窗口。

## 验证

先写策略单测：总开关、逐流程开关、认证规则排除脚本/认证请求、复用窗口覆盖规则、Roxy 启动参数一致性。再补入口测试，验证安装先于导航、结束时关闭统计且不改变 Profile 生命周期。跑相关既有测试及配置契约检查。实际代理商账单下降需要服务重启后的真实任务对照，不由单测推断。
