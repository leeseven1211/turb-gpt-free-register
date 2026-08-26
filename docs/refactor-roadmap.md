# 项目结构整理路线图

> 开始日期：2026-08-26
>
> 工作分支：`codex/refactor-project-structure`
>
> 工作目录：`/Users/lihongwei/code/personal/gpt/turb-gpt-free-register-refactor`

## 1. 总目标

在不改变现有业务语义、HTTP 契约和数据库事实来源的前提下，把当前平铺单体整理为
边界明确、可以渐进维护的模块化单体。

本次整理不是技术栈重写，不引入新的前端框架，也不通过一次性移动全部文件制造大规模
不可审查 diff。

## 2. 执行原则

1. 先固化契约，再移动代码。
2. 先解除错误依赖，再调整目录。
3. 先保留兼容门面，再迁移调用方。
4. 一次只改一个领域或一组路由。
5. 数据库、任务状态机和业务功能修改不得混在同一个结构提交中。
6. 每一阶段都必须可独立测试、提交和回滚。
7. 存储层变更只能使用独立开发数据库，并执行 dry-run/apply/verify。

## 3. 阶段状态

| 阶段 | 内容 | 状态 | 完成门槛 |
| --- | --- | --- | --- |
| 0 | 隔离环境和基线 | 已完成 | 独立 worktree、测试基线、路由契约、三份治理文档 |
| 1 | 文档校准和工具规范 | 已完成 | README/旧文档准确，低风险静态检查可运行 |
| 2 | 注册分发移出 `main.py` | 已完成 | `core` 不再导入 `main`，五类驱动契约不变 |
| 3 | Flask Blueprint 拆分 | 已完成 | 路由契约不变，`app.py` 只保留应用装配 |
| 4 | 前端静态模块拆分 | 已完成 | HTML/CSS/JS 分离，页面行为不变 |
| 5 | `core/` 领域边界整理 | 已完成 | 不再跨驱动导入私有 helper |
| 6 | 存储层内部拆分 | 待开始 | façade 兼容、逐字段对账、行数不变 |
| 7 | 账号任务统一 operation | 待开始 | 新任务原生写入 runs/events，旧表可回滚 |
| 8 | 历史兼容和孤儿代码清理 | 待开始 | 有调用证据、观察窗口和逐文件删除记录 |

## 4. 分阶段实施

### 阶段 0：隔离环境和基线

交付物：

- 独立 worktree 和 `codex/refactor-project-structure` 分支；
- `turb_dev` 开发数据库隔离确认；
- 未修改代码的完整测试结果；
- Flask URL、HTTP 方法和 endpoint 的契约测试；
- `current-architecture.md`、本路线图和 `code-conventions.md`。

禁止：修改业务实现、数据库 schema 或兼容文件格式。

### 阶段 1：文档和工程规范

- 修正 README 项目结构和存储描述；
- 修正 `webui/app.py` 等过期模块注释；
- 明确当前文档与历史设计文档的优先级；
- 增加 `pyproject.toml`，先启用语法错误和未定义名称的阻断检查；更宽的未使用 import/变量等历史问题先作为 advisory 报告；
- 不执行全仓库自动格式化；
- 评估依赖约束文件，但不在本阶段升级第三方库。

完成门槛：文档与代码一致，静态检查不引入大面积格式 diff，完整测试通过。

### 阶段 2：注册分发出入口层

- 新建 `core/registration/dispatcher.py`；
- 将驱动选择和公共签名移出 `main.py`；
- 逐步将纯协议注册主体放入 `core/registration/protocol.py`；
- `main.py` 保留兼容 re-export；
- `registration_service` 直接调用 dispatcher；
- 为 protocol/roxy/cloak/browser_use/skyvern 添加分发契约测试。

完成门槛：`core` 中不存在 `from main import` 或 `import main`，CLI/WebUI 返回语义不变。

### 阶段 3：Flask 路由拆分

按 `dashboard -> config -> email_pool -> accounts -> jobs -> operations -> codex -> integrations`
顺序拆为 Blueprint。一次只移动一组路由，不顺手重写领域逻辑。

随后把启动恢复和后台 worker 从 `create_app()` 移入显式 runtime 生命周期模块。

完成门槛：路由契约测试不变，关键 API 契约测试通过，`webui/app.py` 只保留应用装配。

本阶段实际落地：

- 新增 `webui/blueprint.py` 的兼容注册器，保留旧 endpoint 名称，不让 Flask Blueprint 默认前缀改变内部契约；
- 新增 `webui/routes/`，按上述八个领域注册 Blueprint，路由函数只迁移原有参数校验、service 调用和响应转换；
- 新增 `webui/route_helpers.py`，集中复用账号/任务列表脱敏、分页、邮箱来源和功能可用性辅助函数；
- 新增 `webui/runtime.py`，承载短期下载缓存、账号操作 worker、启动恢复和周期 worker，并由 `web.py` 显式、幂等调用；
- 保留 `webui.app` 中既有 core/service 导入作为测试和外部集成的兼容属性，不改变业务对象身份；
- 完整测试 514 项通过，路由契约仍为 96 条，阻断 Ruff、编译检查和 `git diff --check` 通过。

### 阶段 4：现代前端拆分

- 内联 CSS 移入静态 CSS；
- 公共 API、转义、Toast、分页和轮询逻辑先提取；
- 再按 dashboard/accounts/jobs/operations/email/codex/config 拆 JS；
- 第一轮保留全局函数和现有事件接口，不引入构建工具；
- 后续再把内联事件迁移为事件委托。

完成门槛：功能、分页、批量选择和轮询一致，浏览器控制台无错误。

本阶段实际落地：

- 将现代页、兼容页和登录页的内联 CSS 外置为 `webui/static/css/modern.css`、`legacy.css` 和 `login.css`，保留 foundation/bridge 的加载顺序；
- 将现代页和兼容页 JavaScript 按 `common -> dashboard -> jobs -> accounts -> email -> codex -> config -> bootstrap` 拆分，使用普通 `<script>` 顺序加载，保留全局函数和 HTML 事件接口；
- 删除模板中的内联 CSS/JavaScript，测试改为同时读取模板和真实静态资源，覆盖静态资源 200 响应与 UI 字符串契约；
- 静态脚本全部通过 Node 语法检查，`ruff check .`、`git diff --check` 和完整测试 514 项通过；
- 本地浏览器验收现代页和 `?ui=legacy` 兼容页：资源全部返回 200，页面初始化和 API 加载正常，控制台错误为 0；
- 迁移中曾因先移 CSS 导致模板行号变化，按旧行号删除脚本后残留半截内联脚本；已重启模板缓存、清理残留并用真实浏览器复验，未进入最终结果。

### 阶段 5：核心领域边界

先抽取跨驱动共享的登录挑战、OTP、profile 和 session 获取能力，再移动驱动文件。
保留旧模块作为薄转发层，让调用方分批迁移。

完成门槛：不存在跨驱动私有 helper 导入；`core` 不依赖 `main`/`webui`；所有驱动通过
统一 contract tests。

本阶段第一批实际落地：

- 新增 `core/registration/selenium_auth.py` 和 `browser_use_auth.py`，建立 Selenium 与
  Browser Use/Skyvern 的公开能力边界；能力包含邮箱登录跳转、OTP、资料页、session 和
  登录密码/2FA 等调用方已经共享的入口；
- Cloak、Roxy 查活、Roxy Codex、Browser Use Codex 和 Codex 补跑服务改从能力边界取函数，
  `core` 不再直接从注册驱动模块导入私有 helper；
- 门面采用懒解析，保留旧模块作为兼容实现源，现有测试对旧函数的 patch 点继续有效；
- 新增能力边界契约测试，静态检查 `core` 中不得出现从 Roxy/BrowserUse 注册模块导入私有函数；
- 本批完整测试：345 项通过、41 项跳过；`ruff check .`、模块编译和 `git diff --check` 通过。

本批已完成实现物理归位：`core/registration/roxy.py` 和 `browser_use.py` 承载真实驱动，
`core/roxy_registration.py`、`core/browser_use_registration.py` 只保留模块级兼容别名。
五类注册驱动的公共分发契约继续由 dispatcher contract tests 固化；后续不再新增旧路径调用。

### 阶段 6：存储内部拆分

- `db.py` 按 accounts/jobs/email/codex 拆 repository，旧函数名继续转发；
- `operation_task_store.py` 按 schema/migration/query/command/runtime 拆分；
- 一次迁移一个领域；
- 每次执行计数、ID、JSONB、幂等、抢占和兼容导出验证。

禁止：删除旧表、重排 ID、使用根目录兼容文件回写数据库。

### 阶段 7：统一任务运行模型

按查活、套餐、AT 刷新、Codex Token 刷新、封号扫描、账号配置、注册任务的顺序迁移。
旧 `account_action_*` 在观察期内继续保留，历史不覆盖，重跑只新增 run。

### 阶段 8：兼容清理

每个待删除对象必须记录调用方、兼容原因、替代入口、观察期和删除条件。文件逐个删除，
数据库表至少跨一个稳定版本再讨论删除。

## 5. 每阶段固定验证

```text
目标模块测试
  -> 相关领域测试
  -> 完整 unittest
  -> Flask 路由契约
  -> Git diff 和运行时文件检查
  -> 涉及数据库时执行行数/迁移 verify
  -> 涉及 UI 时执行浏览器验收
```

## 6. 风险与应对

| 风险 | 应对 |
| --- | --- |
| 移动文件形成循环导入 | 先增加兼容 façade，再迁移调用方；每次只移动一个依赖方向 |
| Blueprint 改变 endpoint | 路由契约同时锁定 URL、方法和 endpoint |
| `create_app()` 副作用导致测试/worker 重复 | 将恢复和 worker 启动放入显式、幂等 runtime 生命周期 |
| 前端拆分破坏全局函数 | 第一轮使用普通 script 并保留现有全局 API |
| 存储改造造成数据损坏 | 独立库、备份、幂等迁移、逐字段 verify、禁止生产连接 |
| 旧任务和新 operation 状态不一致 | 保留旧写入口和对账工具，观察期后再停止双写 |
| 兼容文件滞后 | 数据库保持唯一事实来源，兼容导出可重新生成 |

## 7. 完成定义

- `core` 不导入 `main` 或 `webui`；
- `webui/app.py` 只负责 app 装配；
- 现代模板不再内联数千行 JavaScript；
- 不同驱动不导入彼此私有函数；
- 数据读取、业务命令、运行时编排和外部 client 边界明确；
- 所有长任务具备恢复、取消和资源收口；
- 路由和兼容导出在迁移期保持可用；
- 完整测试、路由契约和数据库验证全部通过；
- README、架构文档和代码保持一致。

## 8. 进度汇报格式

每次完成一个可验证工作包后统一汇报：

1. 本次完成了什么；
2. 验证结果；
3. 下一步做什么；
4. 遇到的问题和风险；
5. 是否需要调整原方案，以及调整原因。

## 9. 实施记录

### 2026-08-26：阶段 0 完成

- 从 `main@8985fff` 创建独立 worktree 和 `codex/refactor-project-structure` 分支；
- 确认共享 PostgreSQL 健康，后续测试只使用独立数据库 `turb_dev`；
- 未修改代码基线：501 项测试，66.502 秒，全部通过；
- 新增 Flask 路由契约保护，固化 96 条 URL/方法/endpoint；
- 加入契约测试后：502 项测试，65.032 秒，全部通过；
- 新增当前架构、路线图和代码规范文档；
- 未修改业务实现、数据库 schema、运行时配置或兼容数据。

### 2026-08-26：阶段 1 完成

- 校准 README、`CLAUDE.md`、存储架构、注册流程和任务中心文档，明确行级表是正常业务事实来源，`app_collections` 与 JSON 文件是兼容/辅助数据；
- 更新 README 项目结构和运行时私有目录说明，修正 WebUI、Codex 凭证和迁移入口的描述；
- 新增最小 `pyproject.toml` Ruff 配置：`ruff check .` 阻断 `E9` / `F821`，完整 advisory 报告保留 50 个历史问题；
- 修复 `core/registration_service.py` 中 `_disable_job_email()` 函数体错位导致的未定义变量问题，并新增 2 个回归测试；
- 完整测试：504 项通过，约 58 秒；`git diff --check` 和阻断 Ruff 检查通过；
- 未升级依赖、未执行全仓库格式化、未修改数据库 schema 或运行时私有数据。

### 2026-08-26：阶段 2 完成

- 新增 `core/registration/dispatcher.py`，统一承接五类注册驱动的选择、别名和公共参数签名；
- 新增 `core/registration/protocol.py`，迁移原 `main.py` 中的纯协议注册主体和 OAuth 回调收口逻辑；
- `main.py` 保留 `run_registration()` 兼容门面，CLI 行为不变；`core/registration_service.py` 直接调用 dispatcher，不再反向导入 `main.py`；
- 新增 8 项注册分发契约测试，覆盖 protocol/roxy/cloak/browser_use/skyvern、别名、参数透传、恢复密码限制和未知驱动错误；
- 完整测试：513 项通过，约 58 秒；阻断 Ruff 和模块编译检查通过；
- 未修改路由、数据库 schema、驱动内部流程或运行时私有数据。

### 2026-08-26：阶段 3 完成

- 按 dashboard/config/email_pool/accounts/jobs/operations/codex/integrations 建立 `webui/routes/` Blueprint 路由组，`webui/app.py` 从 3,613 行收敛为 70 行应用装配代码；
- 新增 endpoint 兼容 Blueprint，路由契约保持 96 条 URL、HTTP 方法和 endpoint 哈希不变；
- 将下载缓存、账号配置 worker 和账号任务重试的闭包依赖收敛到 `WebUIContext`，原有 service 调用和接口响应语义不变；
- 将启动恢复、Codex 队列恢复、SMS 取消 worker 和周期刷新 worker 收敛到 `webui.runtime.start_runtime()`，由 `web.py` 显式且幂等调用；
- 新增 runtime 幂等启动回归测试；关键 WebUI 测试 120 项通过，完整测试 514 项通过（52.337 秒），Ruff、编译检查和 `git diff --check` 通过；
- 迁移脚本首轮漏取函数装饰器，导致路由暂未注册；已改为从 Git 基线按 AST 同时提取 decorator 和函数体，最终契约验证通过。该问题未进入提交结果；
- 未修改数据库 schema、业务状态机、前端模板或运行时私有数据。

### 2026-08-26：阶段 5 完成

- 新增 Selenium 和 Browser Use/Skyvern 浏览器能力公共边界，迁移 Cloak、查活、Codex
  OAuth 和账号补跑服务，解除跨驱动私有 helper 直连；
- 将 Roxy、BrowserUse 实现物理迁移到 `core/registration/`，旧文件改为模块级兼容别名，
  既有测试 patch 点和运行时流程保持有效；
- 新增能力边界回归测试，并在完整测试中验证 345 项通过、41 项跳过；Ruff、编译检查和
  `git diff --check` 通过；
- `core` 中仅保留注册 dispatcher 对各驱动公开入口的导入，不再跨驱动导入私有 helper。
