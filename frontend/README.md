# 控制台前端

控制台使用 Vue 3、TypeScript 和 Vite，十二个页面入口覆盖总览、注册、账号、Team 管理、贩卖区、任务中心、批量任务、邮箱、代理与流量、Codex 凭证、配置和提链。各页面沿用现有导航外壳、样式和同域 API。[架构收敛](../docs/architecture/convergence.md)描述各层职责。

## 安装、生成与验证

要求 Node.js 22.12 或更高版本，依赖以 `package-lock.json` 为准。错误目录生成检查使用 Python 3 标准库，无需连接数据库。

```sh
npm ci
npm run build
```

`build` 包含生成契约、错误目录和 TypeScript 校验。非重大架构调整使用 `npm test -- <路径>` 运行与改动直接相关的行为测试。测试使用合成数据和请求替身，不连接数据库或生产服务。OpenAPI 类型源位于 `contracts/`，生成的 `src/api/*schema.d.ts` 不手工维护。运行时 API 与错误处理集中在 `src/api/`，页面通过显式类型和依赖回调连接外壳。

错误短语源为 `core/operations/error_labels.py`；修改后运行 `npm run generate:labels`，将生成的 `src/generated/task-error-labels.json` 一同提交。构建会校验目录一致性，依据与覆盖清单见[错误分类目录](../docs/architecture/task-error-catalog.md)。

列表按[统一交互规范](../docs/architecture/list-ui.md)复用 `ListCell`、`ListResult`、`ListPagination` 和 `FilterPopover`。筛选从表头打开，桌面与手机入口共用编辑器；筛选、分页、选择、数据和轮询状态由各 Vue 页面拥有。完整错误码与证据保留在展开区。

## 构建与外壳接口

`build` 一次生成十二个模块到 `webui/static/task-center/`：`dashboard.js`、`registration.js`、`accounts.js`、`teams.js`、`sales.js`、`task-center.js`、`bulk.js`、`email.js`、`proxy.js`、`codex.js`、`config.js`、`extract.js`，共用 `task-center.css` 与按内容命名的共享模块。构建不清空目录；源码、锁文件、生成类型和产物一同发布。Flask 模板对外壳、桥接脚本及所有页面产物使用统一内容版本作为缓存参数。

外壳负责导航和可见性，各模块导出显式挂载函数，返回刷新、范围切换、弹窗关闭和销毁方法。页面隐藏、导航切换或销毁时停止相应读取与轮询，并丢弃已失效的迟到响应。账号与 Codex 的归档范围仍通过原菜单进入。

Team 管理挂载在 `#tab-teams > #teams-page-root`，侧栏使用 `data-tab="teams"`。页面直接使用 `contracts/teams.openapi.json` 生成的类型；绑定探测与加入回执按后端状态轮询。账号子菜单保留「活跃账号」，并提供「Team 账号」和「归档账号」视图；高级筛选通过固定名单返回指定 Team，回执受理与远端成员事实分别展示。

总览读取 `/api/dashboard` 和 `/api/capabilities`，卡片动作使用导航回调，布局偏好保存在 `gpt_console_overview_preferences_v1`。代理库存和记录通过 `setView('pool' | 'records')` 切换；提链统计从提链工作台的二级菜单进入，按北京时间统计；历史子邮箱由邮箱页面管理，可筛选和复制已有记录。

贩卖区从「账号 → 贩卖区」进入，`mountSales` 通过 `window.SalesPage` 接收外壳可见性、刷新和关闭弹窗通知。账号列表的「加入贩卖区」提交来源账号 ID；贩卖区的选择、改状态和上架使用销售条目 ID。请求和回执类型集中在 `src/api/sales.ts`，店铺与来源管理只填写凭据环境变量名。

页面继续沿用 `shell.css` 与基础样式，Vue 局部样式和原生弹窗滚动锁包含在共用 CSS 中。`npm run dev` 默认代理 `/api` 与 `/static` 到 `http://127.0.0.1:8000`，仅连接已确认的本地开发服务。

## 合成预览与验收范围

从项目根目录运行：

```sh
python tools/diagnostics/preview_task_center.py --port 8017
```

预览使用内存合成任务，不加载 `.env`、不连接数据库、不启动 Worker，也不发送外部业务请求。可检查导航、筛选、分页、详情、进度、日志、窄屏和键盘行为。

后端相关测试通过 `tools/test_isolated.py` 在非生产测试库执行。合成预览和隔离测试不代表真实注册、外部服务或生产性能验收。
