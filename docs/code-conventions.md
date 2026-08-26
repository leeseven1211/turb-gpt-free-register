# 项目代码与目录规范

## 1. 基本风格

- Python 最低版本为 3.10。
- 代码、注释、日志、错误提示和 UI 文案以中文为主。
- 模块、函数、变量使用 `snake_case`；类使用 `PascalCase`；常量使用 `UPPER_CASE`。
- 新模块默认使用 `from __future__ import annotations`。
- 公共函数必须有清晰名称和 docstring；以下划线开头的函数不应跨模块复用。
- 优先使用 `pathlib.Path`、上下文管理器和明确的类型标注。
- 不以大面积格式化混入业务或目录调整提交。
- `pyproject.toml` 中的 `ruff check .` 是阻断检查，当前只阻断语法错误和未定义名称（`E9` / `F821`）；`ruff check --select E4,E7,E9,F --exit-zero .` 用于观察历史 lint 问题。
- 不使用自动修复一次性清理全仓库；扩大阻断规则前先按领域分批处理并补测试。

## 2. 依赖方向

统一依赖方向：

```text
CLI / Web routes
  -> application service
  -> domain capability / repository
  -> external client / PostgreSQL
```

禁止：

- `core` 导入 `main`；
- `core` 导入 `webui`；
- repository/store 调用外部网络服务；
- route 直接实现长流程或跨表事务；
- driver 绕过 service 直接修改任务终态；
- 一个 driver 导入另一个 driver 的私有 helper；
- GET 请求执行迁移、导出同步或远程副作用。

## 3. 模块职责

| 后缀/目录 | 职责 |
| --- | --- |
| `webui/routes/` | 按领域注册 Flask Blueprint；只处理 HTTP 参数、鉴权结果、状态码和响应 |
| `webui/blueprint.py` | Blueprint 注册兼容层；不得在这里放业务逻辑 |
| `webui/route_helpers.py` | 多个路由组共享的查询、分页、脱敏和能力判断辅助函数 |
| `service.py` | 业务编排、事务边界、资源收口 |
| `repository.py` / `store.py` | PostgreSQL 查询和写入 |
| `client.py` | 一个外部服务的协议封装 |
| `driver.py` | 一种注册、OAuth 或浏览器执行策略 |
| `contracts.py` | 输入、输出、状态和能力协议 |
| `errors.py` | 稳定领域异常和错误分类 |
| `runtime.py` | 线程、取消、心跳、恢复和生命周期 |
| `compat.py` | 有明确删除条件的兼容入口 |
| `core/registration/selenium_auth.py` | Selenium 登录挑战、OTP、资料和 ChatGPT session 公共能力 |
| `core/registration/browser_use_auth.py` | Browser Use/Skyvern 登录挑战和 OTP 公共能力 |

浏览器能力模块是注册、Codex 和查活之间的调用边界。当前实现仍由旧驱动模块延迟提供，
目的是先稳定公开函数名和测试契约；新增调用方不得再直接导入旧驱动的私有函数。

## 4. 配置规范

新增或修改 WebUI 可编辑配置时必须同步检查：

1. `config/<domain>.py` 中的默认值和类型；
2. `config.env_loader.apply_env_overrides` 映射；
3. `config/__init__.py` 历史兼容导出；
4. `webui/config_editor.py` 白名单；
5. `.env.example`；
6. README；
7. CLI、WebUI、批量任务和后台任务读取路径；
8. `tests/test_config_defaults.py`。

密钥只允许保存在 `.env` 或进程环境中。运行时需要热更新的配置必须通过子模块属性读取，
不能长期持有 `from config import VALUE` 的旧绑定。

## 5. 存储规范

- PostgreSQL 是唯一事实来源，不得增加文件模式回退。
- 管理列表通过 SQL 完成筛选、排序、聚合和分页。
- 单行修改使用 PATCH 语义，只写明确字段。
- 跨表状态修改必须在同一事务中提交。
- 资源领取和任务 claim 必须使用数据库条件更新保证跨进程互斥。
- 稀疏字段可以保留在 `data JSONB`；进入筛选、排序、唯一性或抢占条件后再提升为列。
- `copy_line` 等纯展示派生字段不得持久化。
- 启动恢复只能修正状态，不能改变业务表行数。
- 兼容导出不在业务写入事务中，失败不能改变业务写入结果。

存储代码开发必须使用独立 worktree 和独立数据库。测试类继承
`tests.support_pg.PostgresTestCase`，不得指向生产库或 `public` schema。

## 6. 任务和并发规范

- 逻辑任务、执行 run、事件和目标业务状态必须分开。
- 重试创建新 run，不覆盖历史事件和终态。
- 取消采用协作式 token 和安全检查点，不向 Python 线程注入异步异常。
- 线程池、浏览器、代理、短信和临时下载都必须有明确 owner 和 finally 收口。
- 外部阻塞调用可放入 daemon 辅助线程，但辅助线程不得在取消后继续推进业务状态。
- 每个新增长任务类型都必须提供进程重启恢复策略。

## 7. 错误与日志

- 配置错误、用户取消、外部服务错误、页面工作流错误、存储错误应使用不同类型或错误码。
- 原始技术错误可以保留在日志中，但任务事件只保存脱敏摘要。
- 捕获宽泛 `Exception` 时必须记录操作上下文；数据库写入和状态流转不得静默吞错。
- 浏览器探测类 best-effort 操作允许降级，但必须区分“未发现元素”和“自动化本身失败”。
- 日志中不得出现密码、access/refresh/id token、OTP、Cookie、完整邮件正文或带凭据代理 URL。

## 8. Web API 规范

- 路由层只做参数读取、校验、service 调用和 HTTP 响应转换。
- 列表接口统一使用 `items/total/page/page_size/facets/revision`。
- 错误响应至少包含 `ok=false` 和脱敏 `error`；功能不可用统一返回 503。
- 批量接口必须返回 accepted/skipped/failed 的可对账数量。
- 敏感字段不进入普通列表响应，通过专用 secret/download 接口按需读取。
- 目录整理期间 URL、HTTP 方法、endpoint、状态码和既有响应字段保持兼容。
- Blueprint 的 endpoint 默认会带模块前缀；本项目必须使用兼容注册器或显式契约测试，不能让旧 endpoint 意外变化。
- `webui/app.py` 只负责 Flask 实例、鉴权、上下文和 Blueprint 装配；启动恢复和后台 worker 由 `webui/runtime.py` 显式初始化。

## 9. 前端规范

- HTML 负责语义结构，CSS 和 JavaScript 放入 `webui/static/`。
- 网络请求统一经过一个 API 包装层。
- 用户可见文本必须转义；敏感值不写入 DOM data 属性或 localStorage。
- 同一列表只允许一个在途轮询请求，手动刷新应排队或取消旧请求。
- 页面模块负责自己的加载、渲染、事件和销毁逻辑。
- 第一轮拆分不引入构建系统；使用普通静态脚本维持现有部署方式。

静态资源按页面和业务边界组织：

```text
webui/static/
├── css/modern.css  legacy.css  login.css  ui-foundation.css  legacy-bridge.css
└── js/
    ├── modern/{common,dashboard,jobs,accounts,email,codex,config,bootstrap}.js
    ├── legacy/{common,dashboard,jobs,accounts,email,codex,config,bootstrap}.js
    └── login.js
```

现代页和兼容页均使用普通 `<script>` 按 `common -> dashboard -> jobs -> accounts -> email -> codex -> config -> bootstrap`
顺序加载。第一轮迁移保留顶层全局函数、全局状态和 HTML 内联事件接口；新代码不得依赖未声明的加载顺序，
也不得把业务代码重新塞回模板。后续迁移事件委托或 ES module 时，必须先增加浏览器验收并评估全局 API 兼容范围。

## 10. 测试规范

- 纯函数和错误分类使用单元测试。
- PostgreSQL 行为使用临时 schema 集成测试。
- 每种注册/Codex driver 必须通过相同的 contract tests。
- API 变更必须覆盖鉴权、参数、状态码和响应字段。
- Flask 路由契约由 `tests/test_route_contract.py` 固化；有意变更必须单独评审。
- 修复缺陷时先增加能复现缺陷的测试。
- 测试不得写入仓库根目录真实账号、日志、邮箱池或兼容导出。

## 11. 文件规模

这些是触发拆分评审的参考线，不是机械失败条件：

- 普通模块建议不超过 500～800 行；
- 路由模块建议不超过 600 行；
- 普通函数建议不超过 80～120 行；
- 超过 1,000 行的文件新增功能前应优先评估拆分；
- 跨三个以上模块复用的能力应形成明确公共模块，而不是继续复制或导入私有函数。

## 12. Git 和文档

- 提交信息优先使用 Conventional Commits：`feat:`、`fix:`、`refactor:`、`test:`、`docs:`。
- 一个提交只表达一个可回滚意图。
- 目录移动与行为修改尽量分开提交。
- 新增领域、数据表、后台任务或兼容层时同步更新架构文档。
- 兼容代码必须说明保留原因、替代入口和计划删除条件。
- `.env`、账号、邮箱池、Token、日志、`run/`、`.venv/` 和迁移快照永远不得提交。
