# 三类内核结构迁移计划

**状态：** 代码迁移、逐组和全分支独立审查已通过，去重集成及最后回调回归通过；待部署验收。
上一轮七操作目录整理一并保留。实际部署事实以最后交付记录为准。

**目标：** 以浏览器、协议、Rust 三类内核组织独立实现，领域服务持有业务编排。

**设计：** [三类内核结构](../specs/2026-11-20-kernel-layout-design.md)。

**执行原则：** 先等价映射，再迁移入口，最后逐操作拆分和移动纯执行代码。
每步保留原业务行为；前一步完成不表示后续 Rust 接入或配置界面调整已完成。

## 阶段一：内核与实现身份

候选文件：

- 新建 `contracts/kernel_catalog.py`，只依赖标准库，描述三类内核及现有实现。
- 扩展 `contracts/operation_drivers.py`，将已解析的现有驱动关联到内核、实现和操作变体。
- `config/operation_drivers.py` 继续重导出需要的静态对象。
- 增加 `tests/contracts/test_kernel_catalog.py`，验证操作能力矩阵与跨实现隔离。
- 扩展 `tests/auth/test_driver_import_isolation.py`，覆盖新目录的真实独立导入。

执行步骤：

- [x] 定义 `KernelDefinition`、`KernelImplementation` 和 `OperationBinding` 的不可变身份。
- [x] 单独表达 `fixed/auto/same_as_registration` 策略，保持原解析时机。
- [x] 对注册、AT 版本、密码、2FA、Codex、查活和套餐建立等价映射。
- [x] 将 Rust 只登记为内核类型；没有 runner 时不登记可用操作。
- [x] 用现有选择矩阵对照规范值、别名、未知值、默认和快照。

此阶段不迁移数据库、不改配置选项、不触发真实账号操作。

## 阶段二：操作执行入口

候选文件：

- 新建 `core/kernels/registry.py`，懒加载明确操作的执行适配器。
- `core/registration/registry.py` 保留已有公开入口，兼容委托新的绑定。
- `core/accounts/liveness/router.py` 保留查活 API 和 gate。
- `core/accounts/liveness/service.py` 保留 AT 选择、快照与原 fallback。
- `core/auth/twofa.py` 保留模式和认证上下文规划。
- `core/codex/operation_service.py`、`core/codex/oauth.py` 保留快照来源与参数。

执行步骤：

- [x] 为每个操作保留自己的输入和结果类型，registry 只选择已经解析的绑定。
- [x] 先绑定原执行函数，确认参数和实际调用次数等价；过渡适配不记作执行实现隔离完成。
- [x] 保留 `auto` 与跟随注册的原语义，不把静态能力变成新增预检。
- [x] 冷导入不加载可选内核，加载失败不更换其它操作的实现。
- [x] 同一 Run 恢复沿用原快照；手动重跑新建 Run 和批量任务重跑各自保留原有配置捕获、
  冻结及覆盖规则，不改写历史 Run。

## 阶段三：账号操作的纯执行实现

按操作分别完成，不一次移动整份 service。

| 现有实现 | 目标职责位置 | 留在原领域的职责 |
| --- | --- | --- |
| `core/accounts/liveness/roxy/probe.py` | `core/kernels/browser/roxy/live_check.py` | 入队、账号租约、结果保存 |
| `core/accounts/liveness/roxy/flow.py` | `core/kernels/browser/roxy/refresh_at.py` | 刷新任务、配置、凭据写回 |
| `core/accounts/liveness/protocol/{legacy,v2,v3}.py` | `core/kernels/protocol/local/refresh_at/` | 刷新选择、fallback、任务收口 |
| 本地协议旧 AT probe | `core/kernels/protocol/local/live_check.py` | 查活调度及状态更新 |
| `core/accounts/password_setup/{auth,protocol,session}.py` 的纯执行部分 | `core/kernels/protocol/local/password_setup/` | 检查点保存、资源、确认写回 |
| 账号补全中的 Roxy 页面密码部分 | `core/kernels/browser/roxy/password_setup.py` | 补全计划、强制改密选择 |
| `core/accounts/export.py` 与浏览器 2FA 的纯执行部分 | 对应内核的 `twofa.py` | 旧/候选密钥保存、业务状态 |
| `core/codex/roxy/oauth.py` 的浏览器执行部分 | `core/kernels/browser/roxy/codex_oauth.py` | 授权地址来源、callback结算、上传 |
| `core/codex/oauth.py` 的协议执行部分 | `core/kernels/protocol/local/codex_oauth.py` | OAuth任务与凭据保存 |
| 套餐 client 中的请求执行部分 | `core/kernels/protocol/local/plan_check.py` | 国家调度、结果合并、自动刷新规划 |

执行步骤：

- [x] 每次选一个操作，列清取消、进度、OTP、认证上下文和凭据事实的回调。
- [x] 识别旧模块的持久化与领域服务依赖，先把这些职责保留在业务侧。
- [x] 内核只迁入已切清边界的执行代码，旧入口保留兼容委托。
- [x] 对照旧新函数参数、阶段顺序、异常分类和实际网络动作。
- [x] 不复制另一套资源或任务状态机；按实际影响运行相关验证并独审。

`BrowserSession` 是 HTTP 会话；其未来归属按真实职责判断，类名调整不与流程迁移捆绑。
共用浏览器资源及认证上下文也不因目录迁移就整块搬动。

## 阶段四：两条注册实现

现有来源：

- `core/registration/roxy/`。
- `core/registration/protocol_oss_2/{runtime,lifecycle}.py` 及 `upstream/`。

目标：

- `core/kernels/browser/roxy/registration/`。
- `core/kernels/protocol/protocol_oss_2/registration/` 及其 `upstream/`。
- `core/registration/` 继续拥有原批次、Attempt/Run、资源、凭据保存和后处理。

执行步骤：

- [x] 分别盘点两条实现中直接保存账号、检查点、邮箱及任务状态的调用。
- [x] 用显式执行上下文保持原调用和确认顺序，业务拥有者不变。
- [x] 每条实现独立迁移，不让一条链路导入另一条的私有辅助函数。
- [x] 保留原模块和替换入口，旧 API、CLI 与任务快照继续使用。
- [x] 比对新注册、原身份恢复、无回执、停止、部分成功和后处理失败的行为。

此阶段已按两条链路分别细化拆分，Roxy 主认证和协议请求观察执行通过显式回调迁入内核。
本规划不授权顺便优化请求、重试、超时或注册步骤。

## 阶段五：Rust 接入准备

未来候选目录：

- `core/kernels/rust/sentinel_rs/`：Python 侧适配、子进程、版本化通信。
- `native/sentinel-rs/`：独立原生源码及其构建。

执行步骤：

- [ ] 明确上游来源与许可，并锁定来源提交。
- [ ] 定义操作输入、OTP、密码提交前保存确认、进度、取消和结果的通信契约。
- [ ] 明确完整会话、身份、密码状态、无回执和原身份重跑的恢复契约。
- [ ] 分别验证 macOS 与 Oracle Linux 的构建和运行依赖。
- [ ] 具备真实注册能力后才增加对应操作绑定、可用性检查和配置项。

没有 Rust 实现前，不创建空 runner，也不将 Rust 注册配置为可执行选项。

## 配置界面与交付

本轮实现代码结构，配置键和界面选项保持。后续界面可按“操作 → 内核 → 实现/版本”组织，
原有配置键先保持兼容；界面设计和配置持久化迁移另行明确范围。

实施时记录阶段完成、实际测试、独立审查、提交、合并、推送、本地部署和 Oracle 部署，
不得将规划文档或单元测试通过表示为对应阶段已经上线。


## 实际执行边界与后续项

- 纯目录 `contracts/kernel_catalog.py` 登记三类内核、三个现有实现与十五项操作绑定；
  不解析历史输入或动态策略。注册、AT 与 Codex 的领域入口按已解析身份使用 registry，
  registry 返回原公开门面，保留各操作自己的签名、领域上下文和 patch 点。
- 浏览器注册的主页面/密码/OTP/资料/Session 认证位于
  `core/kernels/browser/roxy/registration/runner.py`；异常状态逐原赋值点回传。
  账号核心保存紧接认证返回。注册任务、检查点、保留浏览器、租约和后处理仍在领域。
- 协议注册的 `LocalAuthFlow`、邮箱回调适配和执行循环位于协议 kernel runner，
  请求观察/会话构造位于 `registration/transport.py`，独立上游源码位于平级 `upstream/`。
  原领域 runtime 提供持久化、流量、取消、路由与检查点回调；旧上游路径保持模块同一身份。
- AT 的 v1/v2/v3、Roxy OTP/恢复与旧 AT probe，密码、2FA、套餐和 Codex 的核心
  HTTP/DOM 执行已经下沉。协议普通查活仍复用套餐的同一 `accounts/check` 请求，
  实际请求归 `protocol/local/plan_check.py`，不复制另一份网络流程。
- 本轮没有把所有旧文件纯化。共享 `core/auth/browser` 的通用页面与资料能力、Recent Login，
  Codex 完整邮箱/密码恢复/手机号资源混合编排与部分 reset/phone DOM helper 仍保留；
  这些残留不应表述为全部迁移完成，后续可在独立范围继续按操作拆分。
- Rust 本轮只完成内核身份和[后续桥接契约](../../architecture/rust-kernel-bridge.md)。
  来源许可、两端原生产物、真实注册、配置开放均未完成，不登记占位 runner。
- 验证以独立测试库、受控 HTTP/DOM/Node 及直接相关回归为主；不把这些通过描述成
  OpenAI、Roxy、邮箱、CPA 或 Sub2API 真实远端账号写入验收。


## 本次验证记录

2026-11-20，统一隔离入口在本机独立 `turb_test` 与测试 schema 上运行 109 个
去重的受影响文件：`2160 passed, 2547 subtests passed`。该范围包含配置/驱动目录、
注册、AT、密码、2FA、Codex、套餐、查活、共享浏览器能力和功能地图。后续审查发现的
少量回调拥有者与延迟配置读取问题按受影响分组追加回归，不把重复执行次数累加为覆盖量。
逐组独立审查记录保存在本次工作树的忽略审查目录；这些离线和本机 DOM 结果不表示
真实远端账号操作验收。正式交付提交、推送、本地和 Oracle 部署分别记账。


最后审查修复后，另行运行 60 项定向测试和 2 个子测试通过，覆盖新增内核行为、
领域路由、冷导入与功能地图；注册受影响 8 文件回归为 315 项与 92 子测试通过。
全分支独立审查的两项配置读取/恢复拥有者问题均已关闭。暂存变更 Ruff 和空白检查通过。
