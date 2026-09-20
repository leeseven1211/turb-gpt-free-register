# 邮箱换绑与代理流量 v1 规格

## 目标

为当前 PostgreSQL + durable operation 架构增加协议换绑邮箱能力，并增加独立的“代理与流量”运维页面。邮箱换绑不使用可见浏览器兜底；账号列表保持现有形状，代理和流量不塞入账号页。

## 已确认边界

- 邮箱换绑只走现有 `BrowserSession` HTTP 协议客户端。
- 复用公开仓库的 ChatGPT `change_email/begin`、`change_email/verify` 请求顺序和 Recent Login 按需触发逻辑。
- 保留本地的 `identity`、账号 lease、用途化代理、PostgreSQL、durable run、remote intent/receipt 和任务投影。
- 协议换绑不打开 Roxy/Selenium。协议失败必须进入明确失败或 `request_unknown`，禁止浏览器兜底和盲目重复提交。
- 任务中心新增每账号 `email_change` 任务；批量换绑使用现有 operation batch 关联，不新增第二套任务表。
- 自动获取新 AT 使用现有协议查活能力作为子任务或可核验后续任务，不能在释放父 lease 前并发占用同一账号。
- 新增顶层“代理与流量”页面。完整出口 IP 只在认证后的该页面展示；代理 URL、用户名、密码始终隐藏。
- 浏览器流量仅统计 Roxy/CDP 可观测的 HTTP/WebSocket 字节，不宣称等同于代理供应商计费流量。协议任务显示为未采集。
- PostgreSQL 是运行时事实来源，不新增 SQLite、文件任务表或生产数据兼容副本。

## 邮箱换绑状态

`email_change` 的业务步骤为：准备新邮箱、分配账号线路、按需 Recent Login、发送新邮箱验证码、验证新邮箱、写回本地账号、换绑后协议查活/刷新 AT、完成。

提交 `begin` 和 `verify` 前分别写入 remote intent；HTTP 响应只代表观察到响应，只有远端成功、账号本地写回和本地读回都确认后才标记成功。换绑请求发生后连接中断、lease 丢失或本地写回不确定时进入 `request_unknown`/`attention_required`，不自动重试。

成功写回时更新当前邮箱和邮箱来源，保留原始邮箱素材字段，清空失效 AT 并由后续协议查活写回新 AT。验证码、密码、AT、代理认证信息不得进入普通 operation event、任务列表或前端响应。

## 代理与流量页面

页面至少提供三个视图：当前租约、线路历史、浏览器流量。运行数据从持久化 `proxy_leases`、operation runs、registration jobs 和流量摘要联合查询；不能只读进程内 `_ACTIVE_ENDPOINTS`。

代理记录需要能关联账号、用途、operation task/run、注册 job 和重试序号。静态 `PROXY_POOL` 仍是配置资源，不伪装成动态租约历史。

## UI 原则

- 账号页面不增加代理流量列。
- 邮箱换绑入口可以属于账号操作，但状态和日志以任务中心为准。
- “代理与流量”是独立运维菜单，桌面端优先密度和筛选，移动端允许表格横向滚动或降级为可读详情。
- 非脱敏 `exit_ip` 只出现在代理与流量 API/page；其他通用账号和任务 compact API 不扩散原始 IP。
- 复用当前模板、颜色、间距、状态标签和图标体系，不引入新 UI 框架。

## 迁移与验收

数据库迁移必须幂等、只增不删，并在独立测试 schema 验证。完成单元测试、任务中心 API 测试、页面/响应式检查和现有 focused suite 后，再在本机运行时迁移。迁移后选取一个可控邮箱账号执行一次真实换绑，观察任务中心、账号状态、代理与流量页面和后续 AT 查活，确认无误后才合并 `main` 并 push。
