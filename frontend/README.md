# 控制台前端

当前生产构建只包含只读总览页，使用 Vue 3、TypeScript、Vite；继续使用现有导航外壳、样式和同域 API。通用表格组件在此目录独立维护和测试，尚未挂接的组件不会进入总览产物。

## 安装与验证

要求 Node.js 22.12 或更高版本。依赖版本以 `package-lock.json` 为准，保留候选架构版本的锁文件，以便复用同版本的通用组件。

```sh
npm ci
npm run check
npm run build
```

`check` 执行 TypeScript 检查与 `src/**/*.test.ts` 行为测试。测试使用合成数据和请求替身，不连接数据库或生产服务。

`build` 只从 `src/dashboard.ts` 生成以下固定地址，并保留输出目录内的其他文件：

- `webui/static/dashboard/dashboard.js`
- `webui/static/dashboard/dashboard.css`

源码、锁文件和这两个产物一同发布。在相同工具链下重复构建，两份产物应保持一致。构建不依赖其他业务页面、API 类型生成器或错误目录。

## 外壳接口

模块导出 `mountDashboard(element, dependencies)`。外壳传入导航、通知、能力更新和就绪回调，通过返回句柄控制可见性、刷新、自定义布局与卸载。挂载时默认不可见，由外壳调用 `setVisible(true)` 后开始读取。

页面只读取 `/api/dashboard` 和 `/api/capabilities`，卡片按钮仅调用导航回调。布局偏好继续保存在 `gpt_console_overview_preferences_v1`，不提交服务端修改。页面隐藏或卸载时停止读取，并丢弃未完成响应。

页面沿用现有 `shell.css` 与基础样式；产物 CSS 包含总览 Vue 的局部样式及原生弹窗必需的背景滚动锁。

`npm run dev` 默认代理 `/api` 与 `/static` 到 `http://127.0.0.1:8000`；仅连接已确认的本地开发服务。它提供模块开发服务，不代替现有 Flask 导航外壳。
