# 控制台前端

任务中心是首个迁移模块，使用 Vue 3、TypeScript、Vite。全站继续使用现有导航外壳与同域 API；没有第二套任务中心入口。[架构收敛](../docs/architecture/convergence.md)描述职责、交互与后续模块迁移。

## 开发与生成

Node.js 22.12+，推荐当前 22 LTS。依赖以 `package-lock.json` 为准。错误目录的生成检查使用 Python 3 标准库，无需安装后端依赖或连接数据库。

```bash
npm ci
npm run generate:api
npm run generate:labels
npm run check
npm run build
```

OpenAPI 类型源为 `contracts/task-center.openapi.json`。生成的 `src/api/schema.d.ts` 不手工维护。运行时 API 与错误处理集中在 `src/api/`；组件通过显式类型调用，不调用旧页面全局函数。

错误短语源为 `core/operations/error_labels.py`；修改后运行 `npm run generate:labels`，将生成的 `src/generated/task-error-labels.json` 一同提交。构建会校验目录一致性，分类依据与覆盖清单见[错误分类目录](../docs/architecture/task-error-catalog.md)。

任务筛选位于表头，`FilterPopover` 使用 Reka UI Popover 统一处理浮层定位与焦点；任务字段映射集中在 `filterDefinitions.ts`，桌面列标题与手机紧凑筛选入口共用编辑器。筛选状态仍由任务列表拥有。

后续列表按[统一交互规范](../docs/architecture/list-ui.md)复用 `ListCell`（默认两行）、`ListResult`（短摘要与展开明细）、`ListPagination`（范围、页码、跳页）和 `FilterPopover`。任务结果默认可见文案合计不超过 10 字，完整错误码与证据保留在展开区。短错误词典由后端展示目录生成，前端不按原始报错自行重判。

产物固定写入 `webui/static/task-center/task-center.js` 和 `task-center.css`，保持随 Git 发布；构建不清空目录。Flask 模板使用产物版本作为缓存参数。源码、锁文件、生成类型及产物应一起提交，CI 重建后检查差异。

## 合成预览

从项目根目录运行：

```bash
python tools/diagnostics/preview_task_center.py --port 8017
```

打开 `http://127.0.0.1:8017/`。预览仅使用内存合成任务，不加载 `.env`、不连接数据库、不启动 Worker，也不发送外部业务请求；重跑、停止、删除仅修改当前预览进程的合成数据。可以验证完整导航壳层、任务筛选、分页、批量动作、Run 详情、进度、事件、日志、窄屏和键盘行为。

`npm run dev` 用于模块热更新，默认代理 `/api` 与 `/static` 到 `http://127.0.0.1:8000`，应自行确认目标是开发服务。热更新预览不作为生产接口验收结果。

## 验证范围

`npm run check` 校验生成契约、TypeScript 和 Vitest 行为测试。后端相关测试从项目根目录用 `tools/test_isolated.py --profile all -- tests/operations/test_task_center_queries.py -q` 执行，必须提供非生产测试库。

浏览器验收覆盖任务入口、筛选/分页、多选/原动作、跨页详情、Run 切换、步骤过滤、最近/从头游标、失败重试与页面隐藏轮询。合成预览与隔离测试不能证明真实注册、外部服务或两端生产性能。
