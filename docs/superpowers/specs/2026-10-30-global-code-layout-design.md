# 全项目代码目录设计：按业务与具体实现归位

> 状态：用户已批准实施；设计基线与实际迁移状态分别记录。
> 代码基线：`7f55e6c`，2026-10-30。
> 用户要求：注册只是例子；全项目按业务和具体实现组织，共用逻辑放所属模块根目录，目录调整不能改变实际逻辑。

## 1. 结论与范围

采用“业务模块 → 具体实现”的结构。先回答代码属于注册、账号、邮箱、提链还是代理，再在业务目录中找具体驱动或提供方。一个业务中共用的调度、状态、契约和辅助能力放该业务目录根部；跨业务共用的认证、浏览器、网络和任务能力有明确的独立目录。

这轮设计覆盖后端、路由、前端、测试、配置、工具、资源和兼容入口。后续实施以整文件、整包归位为主，不更改请求、分支、重试、超时、状态流转、数据库结构和页面行为。函数内部重新设计、去重、性能优化不混在目录迁移中。

不改用新的框架、微服务、`src/` 包装或前端构建系统。`core/`、`webui/`、`config/` 的分层继续有效。

继续审查时已同步 main 的最新已提交代码；新增运行配置数据库仓库、配置门面、迁移工具和相关测试已纳入清单。main 上正在修改的账号补全/查活文件及两份未跟踪测试仍属于其他工作，本设计不覆盖或搬迁它们，实施前必须重新合并基线并补登记。

### 已核对的现状

| 范围 | 当前情况 | 阅读问题 |
| --- | --- | --- |
| `core/` 根目录 | 124 个 Python 文件 | 业务服务、驱动、外部客户端、存储和兼容入口混放 |
| 注册 | 5 个公开驱动；其中 3 个已有目录 | 本地 Roxy/Protocol 与公共认证文件混放，历史实现也难区分 |
| 邮箱 | 12 个公开来源 | 客户端散落在 core 根，需靠前缀和名称推断来源 |
| 提链 | 3 个平台，查询已单独归位 | 服务、查询、平台仍分散在多个位置 |
| 存储 | `storage/` 根目录 26 个文件，另有顶层基础存储 | 已有领域门面不等于实现已拆分 |
| 测试 | 根目录 398 个文件 | 业务、前端、存储和共享测试帮助文件混放 |
| 前端 | 普通 script，固定加载顺序 | 第一轮拆了文件，仍需按页面收拢目录 |
| 配置 | 23 个文件，包含运行配置数据库门面、schema 和热加载 | 模块名参与热加载，不能只看目录就机械移动 |

### 方案取舍

| 组织方式 | 判断 |
| --- | --- |
| 只继续按 `*_service.py`、`*_client.py` 命名 | 无法解决单目录文件过多的问题 |
| 全局拆为 `services/clients/repositories/utils/` | 同一业务散落在多层，读一条链路需要反复跳目录 |
| 业务目录为主，域内按实现分组，跨域公共能力独立 | **采用**；既能按功能找，也能按具体驱动找 |

## 2. 全局目标结构

以下是目标结构。没有现成独立实现的提供方单独标注在第 5 节，不用空目录冒充拆分完成。

```text
项目根目录/
├── main.py / web.py / webui.sh       # 保持启动命令与部署入口
├── config/                          # 保持现有领域配置与热加载结构
├── core/
│   ├── registration/                # 注册业务编排、恢复及五种实现
│   │   ├── service.py / dispatcher.py / standalone.py
│   │   ├── checkpoints.py / postprocess.py / debug.py
│   │   ├── retained_browser.py / retained_resume.py
│   │   ├── protocol/                # 本地 Protocol
│   │   ├── protocol_oss/            # 开源 Protocol，含 upstream/
│   │   ├── protocol_oss_2/          # 开源 Protocol-2，含 upstream/
│   │   ├── roxy/                    # 本地 Roxy
│   │   ├── roxy_oss/                # 开源 Roxy，含 upstream/
│   │   └── legacy/                  # 保留历史直调实现，不再列为公开驱动
│   │       └── browser_use/  skyvern/  cloakbrowser/
│   ├── accounts/                    # 已注册账号的业务操作
│   │   ├── credentials.py / search.py / completion.py / export.py
│   │   ├── token_refresh.py / auth_context_cleanup.py
│   │   ├── liveness/                # 查活服务、路由；protocol/、roxy/（含专用 probe）
│   │   ├── plans/                   # 套餐、促销、地区和结账信息探测
│   │   ├── inspection/              # 巡检
│   │   ├── email_change/            # 账号换绑邮箱
│   │   └── deactivation/            # 封号邮件检查
│   ├── codex/                       # OAuth、凭证刷新、任务重试
│   │   ├── oauth.py / operation_service.py
│   │   ├── retry_service.py / token_refresh_service.py
│   │   ├── roxy/
│   │   └── legacy/browser_use/  skyvern/
│   ├── email/                       # 邮箱公共调度、库存、收件与 OTP
│   │   ├── provider.py / inventory.py / supply.py / derivation.py
│   │   ├── recipients.py / resource_lifetime.py / forward_imap.py
│   │   ├── mailbox_wait.py / manual_otp.py / otp.py
│   │   ├── outlook/  generic_api/  cloudflare_domain/  cloudflare/
│   │   ├── email_butler/  icloud_hide/  gptmail/  mailnest/
│   │   └── remail/  mailcode/  xigua/  cloudmail/
│   ├── extract_link/                # 提链查询、执行、对账与平台
│   │   ├── service.py / workbench_queries.py / reconcile_policy.py
│   │   ├── providers.py / contracts.py / payment_confirmation.py
│   │   └── legacy/  lumen_flow/  huanguang/
│   ├── proxy/                       # 公共租约、库存、供给、线路选择
│   │   └── provider.py / pool.py / supply.py / sources.py / chain.py / account_routes.py
│   ├── sms/                         # 公共接码生命周期，提供方抽取见第 5 节
│   │   └── provider.py
│   ├── operations/                  # 跨业务 Task/Run、取消、事件、日志
│   │   └── task_gateway.py / executor.py / runtime.py / errors.py / reporter.py / ...
│   ├── storage/                     # 数据访问，按业务归组
│   │   ├── postgres.py / records.py / runtime_config.py / compat_export.py / admin_repository.py
│   │   ├── db_legacy.py             # 现存集中实现，保持原位置与内部逻辑
│   │   └── accounts/  registration/  email/  codex/  operations/  extract_link/  proxy/
│   ├── auth/                        # 注册、账号操作、Codex 共用认证
│   │   ├── challenge.py / fingerprint.py / email_guard.py / twofa.py
│   │   ├── state_machine.py / humanize.py # 协议与浏览器共用的阶段预算/节奏
│   │   ├── browser/                 # 执行上下文、密码、OTP、MFA、Session、提交回执
│   │   └── protocol/                # OpenAI/ChatGPT 协议、HTTP Session、Sentinel
│   ├── browser/                     # 浏览器产品与资源能力
│   │   ├── asset_policy.py / data_saver.py / traffic.py / asset_cache.py / ...
│   │   ├── roxy/                    # 客户端、profile 绑定
│   │   └── legacy/browser_use/  skyvern/  cloakbrowser/
│   ├── network/                     # HTTP 诊断、协议流量统计
│   ├── runtime/                     # 周期调度状态与功能可用性汇总
│   └── integrations/                # sub2api 与外部流程触发
├── webui/
│   ├── app.py / auth.py / runtime.py / config_editor.py / ...
│   ├── routes/                      # 现有按业务分文件的路由，保持 URL 与 endpoint
│   ├── templates/                   # index.html、login.html 保持原位
│   └── static/
│       ├── js/shared/               # 跨页面共用脚本
│       ├── js/pages/                # accounts/、registration/、operations/、email/ 等
│       ├── js/bootstrap.js
│       ├── css/shared/  css/pages/   # 现有整份样式按用途归位
│       └── css/shell.css            # 当前 modern.css 整体移动，不拆选择器
├── tests/                           # 按被保护的业务组织，保留测试文件名
│   ├── registration/  accounts/  auth/  codex/  email/  extract_link/  proxy/  ...
│   ├── conftest.py / support_pg.py   # 共用隔离入口保留在根部
│   └── fixtures/
├── tools/
│   ├── test_isolated.py / test_profiles.py / release.py / check_*.py
│   └── diagnostics/  benchmarks/  maintenance/  migrations/
├── sentinel/                        # 保持 Node 子进程与依赖位置
└── docs/                            # 既有架构、流程、开发和历史分类继续使用
```

迁移期间 `core/` 根目录还保留现有五个兼容入口：`db.py`、`account_task_store.py`、`operation_task_store.py`、`roxy_registration.py`、`browser_use_registration.py`，加上 `__init__.py` 共 6 个文件。它们不是阅读入口。这个数字是目标布局，不是立即搬迁后可无条件保证的结果；新发现的外部调用或模块身份依赖必须先验证，不能为了达到数量删入口。

## 3. 公共逻辑放在哪里

“根目录”指**最近的业务模块根目录**。邮箱各来源共用的 OTP、供给和库存属于 `email/`；各提链平台共用的状态与支付确认属于 `extract_link/`；注册各方式共用的调度、恢复、后处理属于 `registration/`。

跨业务复用能力按真实职责单列，例如注册、账号登录和 Codex 都调用的密码/验证码能力属于 `auth/`；Roxy profile 的创建与回收属于 `browser/roxy/`，不属于 Roxy 注册专用目录。不要再建立能塞所有文件的 `common/`、`utils/`、`misc/`。

| 容易分错的文件 | 归属 | 原因 |
| --- | --- | --- |
| `email_change_service.py` | `accounts/email_change/` | 操作的是已有账号的邮箱绑定 |
| `deactivation_mail_service.py` | `accounts/deactivation/` | 邮箱是取证渠道，业务是账号封号检查 |
| `account_proxy.py` | `proxy/account_routes.py` | 注册、账号、套餐和提链共用线路选择 |
| `account_operation_executor.py` | `operations/executor.py` | 多业务共用执行池 |
| `forward_imap_client.py` | `email/forward_imap.py` | 多来源共用，不能放入 iCloud 专用实现 |
| `email_usage_reports.py` | `email/email_butler/usage_reports.py` | 实际处理 HME/Butler 结果投递 |
| `admin_repository.py` | `storage/admin_repository.py` | 跨账号、任务、邮箱与 Codex 聚合读取 |
| `humanize.py`、`registration/state_machine.py` | `auth/humanize.py`、`auth/state_machine.py` | Protocol、Codex 与浏览器认证共用的节奏、阶段预算和取消语义 |
| `live_check_browser.py` | `accounts/liveness/roxy/probe.py` | 当前实际只支持 Roxy，并非通用浏览器 probe |
| `session.py` | `auth/protocol/session.py` | `BrowserSession` 是共用认证 HTTP 会话，不是 Roxy 窗口 |
| `flow_trigger.py` | `integrations/flow_trigger.py` | 调用外部流程，不是本地任务调度器 |

每个文件只有一个真实实现位置。通过导入共享能力，不复制到各个提供方目录。

### 物理归位不等于逻辑解耦

当前 `roxy_oss` 复用 Roxy 生命周期，`protocol_oss_2` 复用 `protocol_oss` 适配层，`protocol_oss` 还会调用本地 Protocol 的恢复辅助。此轮保留这些依赖，不复制成五套互不相干的流程。

`auth/browser/` 部分现有能力仍依赖注册存储和进度上报，`roxy_codex_oauth.py` 被注册及账号操作复用。迁移不强行倒置依赖、不新增接口注入；文档如实标明这些联系。依赖方向约束用于避免继续增加耦合，不能在本轮悄悄重写既有调用链。

## 4. 跨层查找方式

沿用现有职责分层：CLI/WebUI 调用 core 业务服务，业务服务读取 config 并使用领域仓储。新加入的 `config/runtime.py` 延迟调用运行配置仓库，是现存初始化接缝；搬迁 `core/runtime_config_store.py` 时保持延迟时机、加密格式、事务、热加载回滚及启动参数边界，不能在 import 阶段提前连库。在 core 内按业务找实现，存储统一放 `storage/<业务>/`；路由只保留现有参数与响应职责。本轮不把存储 SQL 混入业务服务，也不重写现有混合模块。

| 要修改的功能 | 后端入口 | 前端页面 | 测试分组 |
| --- | --- | --- | --- |
| 注册 | `core/registration/` | `webui/static/js/pages/registration/` | `tests/registration/` |
| 查活、巡检、换绑邮箱 | `core/accounts/` | `webui/static/js/pages/accounts/` | `tests/accounts/` |
| 邮箱来源 | `core/email/<来源>/` | `webui/static/js/pages/email/` | `tests/email/` |
| 提链平台 | `core/extract_link/<平台>/` | `webui/static/js/pages/extract_link/` | `tests/extract_link/` |
| 任务中心 | `core/operations/` | `webui/static/js/pages/operations/` | `tests/operations/` |
| Codex | `core/codex/` | `webui/static/js/pages/codex/` | `tests/codex/` |

现有路由已按业务分成 12 个文件，先保留这些路径；不为每个单文件机械再套一层空目录。业务路由以后确有多个文件时，再放对应子目录。前端保留普通 script、全局函数、共享状态及加载/事件绑定顺序，仅改静态路径与缓存版本。

测试按业务组织：账号、邮箱、Codex 等业务专属存储/API/前端测试与该业务放一起；`tests/storage/` 只保留 PostgreSQL 基础设施和跨业务存储契约。配置加载/配置存储归 `tests/config/`，维护命令与迁移工具测试归 `tests/tools/`。先保留现有文件名，不同时转换测试框架。`conftest.py`、`support_pg.py`、前端脚本读取帮助文件留测试根目录；移动测试后逐项校准 `__file__`、fixture 路径、测试间导入、profile 路径匹配和 CI 命令。测试收集集合应按旧新路径映射一一对应，不通过删除测试获得通过。

## 5. 分清整文件移动与必要的内部抽取

大多数文件可以直接归位。以下文件当前混合多种实现，不能只凭目标目录图宣称已拆开：

| 文件 | 整文件归位 | 提供方/职责进一步抽取 |
| --- | --- | --- |
| `sms_provider.py` | `sms/provider.py` | 后续单独一批将 Grizzly、H、L 请求函数归入 `sms/grizzly/`、`sms/h/`、`sms/l/`；公共资源登记、取消队列、线程与批次状态保持唯一实例 |
| `proxy_sources.py` | `proxy/sources.py` | 两种供给地址构造函数可另批归入 `proxy/proxy1024/`、`proxy/proxy711/`；保留注册表键 `1024proxy`、`711proxy`，目录名只是 Python 标识符 |
| `proxy_provider.py` | `proxy/provider.py` | 共用租约与历史提供方分支相互交织，先不拆请求和控制流 |
| `codex_oauth.py` | `codex/oauth.py` | 当前含分发、协议流程和 CPA/Sub2 回调，保持整块，进一步分驱动需要独立的函数归属与状态审计 |
| `roxy_codex_oauth.py` | `codex/roxy/oauth.py` | 同时含 OAuth、登录挑战和账号操作；保持现有调用，不能顺手提取再改签名 |
| `account_export.py` | `accounts/export.py` | 同时含 Session、2FA 和账号保存；保留整块并注明实际职责，不把它写成已经独立的导出层 |

提供方抽取仍必须保持实际行为，只允许移动完整定义并调整明确的导入绑定，不能简化条件、重排调用或重新实现同等功能。全局文件清单对应“整文件归位”阶段；第一个表格中的后续抽取是明确的下一批设计范围，尚不代表那些目录已有独立实现，也不会现在创建空包。

对于 `registration/roxy.py` 和 `registration/protocol.py`，优先整体转为同名目录包的 `__init__.py`。这样五种方式都有独立目录，同时保留原模块全名、日志名、异常所属模块及已有 patch 点。这个阶段允许大 `__init__.py`；再拆成 `flow.py` 等文件必须另批验证函数全局绑定。不能用简单再导出把风险藏起来。

## 6. 保持实际逻辑不变的边界

### 允许变化

- 文件与目录的物理位置，清单中列出的文件名。
- 精确列出的 import 目标、相对导入层级和动态导入路径映射。
- 保持解析结果完全相同的资源定位表达式。
- 模板静态 URL、测试源码路径、文档导航和缓存版本。
- 必要且经过身份验证的兼容入口。

### 保持不变

- 函数签名、默认参数、装饰器、执行顺序、分支和异常处理。
- HTTP 参数、调用次数、超时、重试、注册与账号状态流转。
- 取消、恢复、支付、重跑、邮箱释放和任务并发规则。
- 数据库、schema、表结构和现有持久数据绝对路径。
- 配置键、默认值、热加载结果、外部 URL 和路由 endpoint。
- 全局锁、缓存、线程池、ContextVar 及模块实例的唯一性。
- 前端事件顺序、全局处理函数和轮询行为。

### 已找到的具体风险

| 风险 | 现有证据 | 必须怎样验证 |
| --- | --- | --- |
| 模块名字参与异常判断 | `core/proxy_provider.py:598` 判断 `CodexRetryStopped.__module__` | 单独保证取消分类及异常身份；未验证前不移动定义位置，不能只改 import 就判成功 |
| 全局变量/补丁依赖模块对象 | 旧 db/task/roxy 入口使用 `sys.modules`；Roxy 使用 `globals()` 查覆盖 | 新旧入口指向同一个模块及锁/缓存对象；兼容模块不能复制实现或仅 `import *` |
| 动态邮箱来源 | `core/email_provider.py` 拼接 `core.{source}_client` 并保存模块字符串 | 逐来源解析到对应同一实现；不靠仅搜索普通 import |
| 配置数据库初始化 | `config/runtime.py:_repository()`、`core/runtime_config_store.py` | 只改仓库引用，保留延迟导入、加密及事务语义，不迁移数据库内容 |
| 配置文件名决定模块名 | `config/schema.py:71`、`config/__init__.py:_RELOADABLE_SUBMODULES` | 此次保留 config 位置；不把配置文件随意下沉到业务包 |
| 运行数据位置依赖层级 | `sms_provider.py`、`registration_debug.py`、`task_run_log.py`、`codex_oauth.py` 等 | 比较迁移前后绝对路径；不改写数据、不自动修复历史路径 |
| 历史存储根有特殊结果 | `core/storage/db_legacy.py:25` 当前从文件层级得到 `core/` | 保留当前实际路径结果，不借搬目录更正 |
| Flask 资源与 endpoint | `webui/app.py`、`webui/blueprint.py` | 保留 app/templates/static 根，比较完整路由清单和资源响应 |
| 供应商源码与 JS 资源 | 三个 `upstream/`、根 `sentinel/` | 默认逐字保持；仅三份已启用本地接缝允许精确导入白名单变更，规则见下节，不覆盖为上游原版 |
| 启动方式依赖 cwd | `webui.sh`、`tools/test_isolated.py` 和维护脚本 | 保留三个主入口与测试入口；迁移工具验证原命令、目标命令和任意 cwd |

旧模块名字符串如果只影响迁移绑定，变更也必须进入差异白名单；如果影响异常类别、日志类别、资源路径或外部引用，就作为可观察契约单独测试。AST 校验不能粗暴忽略所有 import，否则会漏掉导入时机和副作用变化。

现有五个兼容入口继续满足[兼容入口清单](../../architecture/compatibility-inventory.md)。对新增兼容入口，必须记录调用方、真实实现、保留原因和退出条件；没有外部调用证据的内部导入随业务批次迁移，不给全部旧文件永久保留包装。也不引入全局 import hook 来隐藏旧目录。

### 上游快照与本地接缝的精确例外

大部分 `upstream/` 文件保持逐字一致。当前实际执行的三份本地接缝依赖将被搬走的模块，允许以下**仅 import 目标路径**变化；导入符号、`as` 别名、所在函数/模块位置、顺序和时机保持不变：

| 接缝文件 | 允许替换的旧模块 → 新模块 |
| --- | --- |
| `protocol_oss/upstream/core/chatgpt_auth.py` | `core.session` → `core.auth.protocol.session` |
| `protocol_oss/upstream/core/openai_auth.py` | `core.session` → `core.auth.protocol.session`；`core.sentinel` → `core.auth.protocol.sentinel`；`core.sentinel_runner` → `core.auth.protocol.sentinel_runner`；`core.registration_service` → `core.registration.service` |
| `roxy_oss/upstream/browser_helpers.py` | `core.registration.auth_context` → `core.auth.browser.auth_context`；`core.registration.selenium_dom` → `core.auth.browser.selenium_dom`；`core.registration.selenium_resource` → `core.auth.browser.selenium_resource` |

这三份文件的 AST 只归一化上述精确路径，其他内容必须一致；相应 `UPSTREAM.md` 增补本地路径迁移记录。许可证、JS、其他源码和原始来源校验记录不变，不重写 `SOURCE_SHA256.json`。`protocol_oss/upstream/main.py` 与 `roxy_oss/upstream/roxy_registration.py` 是来源说明明确禁止运行的对照快照，逐字保留，不顺手修复旧依赖或扩大其执行范围。

`storage/accounts.py`、`storage/codex.py`、`storage/registration.py` 也计划转为同名包的 `__init__.py`，和两个注册驱动一样属于保留模块全名的转换。它们仍是原有实现/门面，不宣称存储职责已经拆净。

### 扫描范围和工具命令兼容

`tests/test_release_checks.py` 当前使用 `tools.glob("*.py")` 扫描工具源码。工具下沉后，即使 pytest 用例数相同，该检查也可能漏掉文件。因此验收同时保存并比较：测试节点集合、default/extended 分类集合、源码检查输入集合、静态资源扫描集合；路径按映射归一化后应一致。所有 `glob/rglob`、白名单、源码拼接器和 CI 路径逐项审计，不能只确认“测试能运行”。

工具目录表示真实实现位置。已公开的 `python tools/<名称>.py` 命令保留原位置的薄转发入口，明确使用 `main` 或等价现有入口，保持 argv、cwd、退出码、执行次数，不以复制实现兼容。只被内部导入的模块更新所有调用方后可直接迁移。旧命令入口计入兼容清单，目标不以减少这些少量入口为指标。

## 7. 实施批次与每批验收

当前只交付设计。实际迁移按下表执行，每批保持可独立验证和回滚，不一次移动数百文件。

| 批次 | 工作范围 | 重点验收 |
| --- | --- | --- |
| P0 基线与依赖登记 | 固定提交、旧新路径、动态 import、资源路径、模块身份、测试收集与既有失败 | 清单完整，现有用户修改单独保留，基线可重现 |
| P1 页面归目录 | 整份 JS/CSS 按页面搬迁、模板路径和引用更新 | 实际 script 顺序、事件初始化、所有静态资源、浏览器只读交互与控制台 |
| P2 注册方式和提链平台 | 五种注册目录统一、注册业务文件归位、提链平台各目录 | 驱动签名、分发/恢复/错误语义；upstream 除精确导入白名单外内容相同；提链查询与执行契约 |
| P3 邮箱、代理、短信 | 现有独立客户端归位；混合单体先整体迁移 | 12 来源动态导入、租约与取消、路径、唯一状态；提供方内部抽取再单独分提交 |
| P4 账号、Codex、集成 | 各账号操作、OAuth、凭证刷新、外部集成归位 | 认证/取消/状态/重试边界；CodexRetryStopped 模块名依赖处理 |
| P5 跨业务认证与浏览器 | 公共 auth、browser、network 能力归位 | 所有消费者、globals/patch、日志名、共享状态与资源路径 |
| P6 存储、任务与运行时 | storage 分组、operations/runtime 文件归位 | 表数据对账、锁/线程池单例、恢复顺序、旧新入口身份；不拆历史集中存储 |
| P7 工具、文档与最终收口 | 维护工具分类、阅读导航、兼容清单、全项目契约 | 旧命令兼容、测试集合与 profile 一致、隔离全量回归及已知失败对照 |

测试文件随所属批次一起移动，不留到最后集中改断言。业务之间仍存在现有依赖时，用明确的临时入口过渡；迁移清单不是可直接按文件顺序执行的脚本。每批开始前解析本批导入闭包，确认所有调用方同时更新或有验证过的兼容入口。

每批的验收顺序：

1. 对照迁移前后 AST，列出全部允许差异，核对函数、类、初始化和调用顺序。供应商文件默认逐文件哈希比较，三份本地接缝只放行登记过的 import 路径差异。
2. 验证导入解析、模块/异常身份、共享对象、实际资源路径及相互导入顺序。
3. 按[功能地图](../../architecture/functional-map.json)选择本业务及相邻消费者测试，沿用隔离测试入口、非生产库及 `test_` schema。另比较源码/资源扫描集合，避免目录下沉后扫描范围缩小。
4. 涉及页面则真实浏览器验收；涉及路由则比较路径、方法、endpoint 和响应契约。测试期不触发真实注册、提链或支付。
5. 本批独立审查、提交；部署另行按既有服务方式检查代码、PID/cwd、端口、日志与 healthz/readyz。

全项目迁移结束有充分理由执行隔离全量回归。第一轮已发现的 dashboard/路由契约既有失败只作为历史线索，实施时重新建立基线；不能借既有失败跳过新增失败。没有调用真实外部平台时，交付明确只完成离线/隔离验证。

## 8. 迁移清单和设计交付

逐文件目标见 [全项目目录映射 JSON](2026-10-30-global-code-layout-map.json)。基线仓库共有 842 个已跟踪文件；清单覆盖 `core/config/webui/tests/tools/sentinel` 及三个主入口，共 708 项，其中 115 项保留、588 项整文件移动、5 项同名模块转目录包。其他根配置、CI 和文档保持原位置；迁移时其引用随批次更新。

清单的 `action` 仅描述物理位置；保留位置的文件仍可能需要 `content_changes` 指定的导入/文档更新。清单描述目标归属及批次，**不授权直接批量移动，也不声明行为已经验证**。混合单体的内部提供方抽取不属于这份一对一文件映射。新目录所需的空 `__init__.py` 在实施时按包需求添加，禁止导入全部子模块而提前启动 worker 或循环导入。

设计完成标准：所有现有文件有明确归属或保留理由；目标路径无碰撞；目录能按业务/提供方导航；公共能力没有复制；高风险兼容点有具体证据与验收方法；当前架构文档不被提案冒充替换。本轮不迁移源文件、不提交代码、不合并、不推送、不重启服务。


## 9. 本次设计验证结果

- 708 项映射已对照 `7f55e6c` 的已跟踪文件清单校验：来源完整、目标唯一、无文件与目录目标冲突。
- 设计中的 Markdown 标题、代码块、相对链接和基线统计检查通过。
- 独立架构审查及归属审查均通过；发现的上游接缝约束冲突、扫描范围遗漏和公共能力归属问题已修正。
- 本次只新增设计文档与 JSON 清单，业务源代码没有修改；未运行业务测试、未提交或部署目录迁移。
