# 控制台前端

总览、代理与流量、提链历史统计和历史子邮箱使用 Vue 3、TypeScript 和 Vite，沿用现有导航外壳、样式和同域 API。

## 安装与验证

要求 Node.js 22.12 或更高版本。依赖版本以 `package-lock.json` 为准，保留候选架构版本的锁文件，以便复用同版本的通用组件。

```sh
npm ci
npm run check
npm run build
```

`check` 执行 TypeScript 检查与 `src/**/*.test.ts` 行为测试。测试使用合成数据和请求替身，不连接数据库或生产服务。

`build` 从 `src/dashboard.ts`、`src/proxy.ts`、`src/extractStats.ts` 和 `src/emailHistory.ts` 分别生成页面模块。

- `webui/static/dashboard/dashboard.js`
- `webui/static/dashboard/dashboard.css`
- `webui/static/proxy/proxy.js`
- `webui/static/proxy/proxy.css`
- `webui/static/extractStats/extractStats.js`
- `webui/static/extractStats/extractStats.css`
- `webui/static/emailHistory/emailHistory.js`
- `webui/static/emailHistory/emailHistory.css`

源码、锁文件和这八个产物一同发布。在相同工具链下重复构建，产物应保持一致。

## 外壳接口

总览模块导出 `mountDashboard(element, dependencies)`。外壳传入导航、通知、能力更新和就绪回调，通过返回句柄控制可见性、刷新、自定义布局与卸载。挂载时默认不可见，由外壳调用 `setVisible(true)` 后开始读取。

总览页读取 `/api/dashboard` 和 `/api/capabilities`。卡片按钮调用导航回调，布局偏好保存在 `gpt_console_overview_preferences_v1`。

代理模块导出 `mountProxyTraffic(element, dependencies)`。左栏在库存与记录间切换时调用 `setView('pool' | 'records')`。页面通过 GET 读取 `/api/proxy-pool` 和 `/api/proxy-traffic/` 下的 `current`、`history`、`traffic`、`summary`。两个页面隐藏或卸载时均会停止轮询并丢弃未完成响应。

历史统计模块导出 `mountExtractStats`。打开「提链统计」按选定的平台和时间范围读取报表，统计时间使用北京时间。

历史子邮箱模块导出 `mountEmailHistory`，在邮箱子菜单或库存行的「查看历史」打开后读取已有记录。母邮箱范围可从列表的筛选条件中移除。

页面沿用现有 `shell.css` 与基础样式；产物 CSS 包含总览 Vue 的局部样式及原生弹窗必需的背景滚动锁。

`npm run dev` 默认代理 `/api` 与 `/static` 到 `http://127.0.0.1:8000`；仅连接已确认的本地开发服务。它提供模块开发服务，不代替现有 Flask 导航外壳。
