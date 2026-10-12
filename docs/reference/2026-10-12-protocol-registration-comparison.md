# 协议注册主流程对比与优化评估

日期：2026-10-12。本文是代码审查报告，不是已实施的改造方案或真实注册验收报告。

## 1. 结论与比较基线

**公开项目确实替换了协议引擎，但截图对咱们实现的描述有多处已经过期。当前最值得优先优化的是凭据保存与恢复分支，而不是立即整体更换引擎。**

本文统一使用以下名称，避免把不同版本混在一起：

| 名称 | 对象 | 固定版本 |
| --- | --- | --- |
| A：公开项目 | `wangshen233/turb-gpt-free-register-oss-20260928` | `7df094e05e48a74eeacc4ff6e3c27165def21cae`，2026-09-28；本轮 `git ls-remote` 确认仍为公开 main |
| B：咱们当前项目 | 本地 `turb-gpt-free-register` 的 main | `2b24fe82d48b2a8d9162dd4862fd6f8c7f1b6d6d`，2026-10-11 |
| 截图中的 B | 别人报告中的 `turb-gpt-free-register` | 没有可核验的提交号，不能假定等于咱们当前 main |

比较范围是协议注册的真实入口、请求顺序、密码与 OTP、身份分支、回调与会话、2FA、后处理、持久化、停止与诊断。套餐与优惠只说明它在流程中的位置，不以优惠比例评价注册实现。

审查依据包括固定版本源码、调用关系、本地依赖元数据和少量离线合成验证。截图中的说明及上游代码注释作为待核验材料，不作为实测结论。没有运行 A 的注册程序，没有访问真实账号、发送验证码、创建结账会话、修改生产数据库或重启服务。

主要判断：

1. **咱们已具备**统一驱动入口、成功提交密码后的检查点、原邮箱/原密码续跑、OTP 后的 MFA、核心账号与后处理分离、完整 ChatGPT session 保存、阶段事件和协议请求诊断。
2. **咱们仍有明确缺口**：新密码提交结果未知时缺少提交前持久化；注册 2FA 未接入已有的密钥早存回调；取得 AT 后到数据库保存前存在预热窗口；密码验证直接返回 MFA/回调的续跑分支不完整。
3. **A 可借鉴**的是更早保存 2FA 结果、按服务端下一步分派、协议请求流量归集和网络后端隔离思路。部分能力咱们已有，不需要重复移植。
4. **A 不适合整包接入**：引入两套 SQLite、父子进程结果同步、旧结果误认本轮成功、未知失败释放邮箱、预算冲突，以及部分外层配置未传入的问题。
5. **不能从截图推导**“升级声明的 Chrome 版本、修改 TLS/HTTP2、修复时区就能获得优惠”。其中的兼容性问题可以独立检验，优惠因果没有对照证据。

## 2. 两边真正执行的主流程

### 2.1 A：独立协议组件，通过子进程桥接

```text
WebUI / CLI
  → main.run_registration(protocol 分支)
  → _run_registration_via_protocol
      领取邮箱，读取 email----relay_url，解析代理
  → core.register_protocol_engine.register
  → subprocess.run(_turb_bridge.py，默认总超时 900 秒)
      → 调整 vendor 配置，尝试安装 wreq 适配层
      → registrar.start_registration
      → AuthFlow.run_register
          网络预检 → warmup → CSRF → signin → authorize
          → 根据落地状态判定新注册 / 已有账号
          → 注册密码或验证已有密码 / OTP / MFA
          → 必要时提交资料
          → 消费 NextAuth callback → 获取 session
          → on_session_ready 中绑定 2FA 并早存
          → 按组件选项取得其他 OAuth 产物
      → registrar 保存组件内部结果
      → 从组件数据库读取结果，JSON 返回父进程
  → 父项目保存账号、标记邮箱 used
  → 保存入口按配置触发后台套餐处理
```

A 的旧 `core/openai_auth.py` 仍存在，但主入口已经直接走 vendor；不能用旧文件的函数数量判断实际注册行为。`register_protocol_engine.py` 声称存在 `REGISTRATION_ENGINE=legacy`，当前主入口没有调用 `use_protocol()` 判断，不能依靠该开关恢复旧主链路。[A 入口][a-main]，[A 引擎][a-engine]，[A 桥接][a-bridge]，[A 认证流程][a-auth]

### 2.2 B：统一任务模型中的协议驱动

```text
WebUI registration_service / CLI 兼容入口
  → core.registration.dispatcher
  → core.registration.protocol.run_protocol_registration
      BrowserSession → 网络预检 → 可选匿名预热
      → providers → 匿名 session → CSRF → signin → authorize
      → 新账号可选密码注册，成功后保存待验证检查点
        或恢复原密码，沿原认证状态继续
      → OTP 时间过滤、收码、验证与受控重试
      → OTP 后按状态：新资料 / 已有回调 / 已有账号 MFA
      → callback → session → accessToken
      → 可选登录态预热
      → persist_registration_core（PostgreSQL）
      → 同会话套餐检查 → 可选 2FA → 可选 Codex OAuth
      → 后处理结果与 2FA 密钥保存 → 可选 Flow
      → 汇总 registration_success / postprocess_success / next_actions
  → 任务服务收口 Attempt、Run、阶段事件和资源
```

这里有两个容易被“已有检查点”掩盖的细节：密码检查点在成功响应之后；2FA 密钥写入在 Codex 之后。它们与“请求前已保存密码”“拿到密钥立刻保存”不是同一件事。详见第 5 节。[B 分发器][b-dispatch]，[B 协议主体][b-protocol]，[B 检查点][b-checkpoint]

## 3. 主流程逐项比较

| 环节 | A：公开项目 | B：当前本地 | 评估 |
| --- | --- | --- | --- |
| 入口与隔离 | vendor 独立配置和子进程，避免同名 `config` 冲突 | `main.py` 已是兼容门面，业务位于 `core/registration` | 都已模块化；子进程隔离有同步、取消和部署成本，并非必然更优 |
| 任务配置 | 桥接重新构造选项；当前主调用未传 `want_2fa`，引擎默认 True；姓名/生日也没有传入该引擎接口 | WebUI 为任务保存注册驱动、密码、2FA、Codex、查套餐配置快照 | 咱们配置契约更清晰；移植 A 不能只接一个 `register()` |
| 邮箱适配 | 外层实际要求 `email----relay_url`，桥接固定 `icloud_relay` | 通过统一邮箱接口和明确 `email_source` 取码 | A vendor 有其他 provider，不等于这条桥已支持它们 |
| HTTP 后端 | 默认尝试 wreq；加载失败保留 curl_cffi | curl_cffi，按实际支持的档位规范化会话画像 | 是实质差异，但优劣须按真实依赖与请求行为验证 |
| 预检与预热 | vendor warmup、落地状态检查，部分探测按桥接配置禁用 | 预检明确跳过无参数 Auth 探针，可选匿名/登录态 bootstrap | 两边都有优化；不能按源码注释宣称的历史失败比例比较 |
| signin 参数 | `login_hint`、`screen_hint=login_or_signup`、相对 `/` 回调 | 当前同样具备这几个关键参数 | 截图所暗示的相关“新能力”并非咱们缺失 |
| 新账号密码 | 成功响应后通过回调写 vendor 数据库 | 成功响应后、发 OTP 前写 PostgreSQL 检查点 | 两边都没有完整覆盖“已发出、响应未知”的密码早存边界 |
| OTP | 发码时间过滤、重发、不同分支等待；桥接默认等待 900 秒 | 发码前时间边界、无效码最多 3 次；特定 IMAP 无邮件情形在同预算重发一次 | 不应照搬 900 秒；须先区分投递慢、取件慢、发码未确认和 OTP 无效 |
| 已有账号恢复 | 密码验证后可直接处理 MFA、邮箱 OTP、回调；会回读组件已有凭据 | 同 Attempt/原邮箱/原密码续跑已接入；OTP 后 MFA 已接入 | A 分派更广；B 的“密码后直接 MFA/回调”仍有缺口，不能说完全没有恢复 |
| 创建资料 | 根据新/旧账号状态处理；部分拒绝会尝试再次授权 | 明确区分 `new_candidate`、`existing`、未知；未知不盲目创建 | 宽泛兜底不一定更安全，恢复应受远端身份与本地检查点约束 |
| callback 与 session | 注册入口先消费 callback，再取 session | 同样先 callback 后 session；有终态停止与有限退避 | A 的顺序修复并不是 B 当前的缺项；A 的另一登录函数不能代替注册入口证明 |
| 核心账号保存 | 组件早存部分字段，父项目等子进程返回才同步 | AT 与完整 ChatGPT session 在独立后处理前保存 | B 已不再全流程结束才落库，但 AT 与保存之间仍有预热窗口 |
| 2FA 保存 | 组件绑定成功后回调保存，早于后续 Codex 获取；保存回调失败主要记警告 | 注册入口绑定后先执行 Codex，随后保存 secret | A 的保存时点值得借鉴；B 已有更早回调接口但入口未接入 |
| 成功口径 | 父流程主要看返回 AT；Flow/Codex 字段为 skipped；组件可能返回历史凭据 | 显式区分注册完成、后处理完成、部分完成与下一步动作 | 不能直接比较两边页面“成功率” |
| 会话资料 | 汇总 access/session/refresh/id token、Cookie 等字段，不保证每轮齐全 | 保存完整 `chatgpt_session`；Codex 凭据归独立流程和存储 | “咱们只存 AT”过期；原始 Cookie/RT 扩大收集需有明确恢复用途 |
| 邮箱安全 | 父层异常或 `ok=False` 会释放为 available | 未知结果保留原邮箱，任务检查点保护继续执行边界 | A 的父层处理可能抵消 vendor 的中间态保护 |
| 停止与预算 | 默认整进程 900 秒，OTP 本身也可占 900 秒；父日志延后转发 | 任务服务、停止检查、阶段预算已有；仍有软预算和不可中断等待 | 两边都不能笼统称为“总超时与即时停止完整” |
| 诊断与流量 | 有阶段诊断和 HTTP 字节统计；父任务实时观察较弱 | 已有阶段事件、耗时、原因码和按任务隔离的协议请求诊断；完整抓包保留原始材料 | 真正差距偏向常规协议流量归集，不是“没有诊断”；原始抓包不能直接用于公开报告 |
| 存储与测试 | 父项目与 vendor 各有 SQLite；公开快照无 `tests/` 套件 | PostgreSQL 唯一事实来源；174 个受 Git 跟踪的 `tests/test*.py` | 截图的“54 个测试”不能描述当前本地；数量不等于覆盖或执行结果 |

证据主要来自 [A 入口][a-main] 行 136–297、380–392，[A 引擎][a-engine] 行 48–106、137–155，[A 桥接][a-bridge] 行 778–859，[A 认证流程][a-auth] 行 3810–4190，[B 协议主体][b-protocol] 行 542–1200，[B 任务服务][b-service] 行 55–76、1490–1586。

## 4. 对五张截图的核验

### 4.1 截图 1、2：架构、凭据与恢复能力

| 截图观点 | 对当前代码的判断 | 说明 |
| --- | --- | --- |
| A 换独立协议引擎 | 成立 | 主入口确实通过子进程桥接 vendor |
| A 增加 wreq，失败回退 | 成立但有部署前提 | 适配层已接入；依赖声明和回退画像还有问题，见下节 |
| B 密码只在最后保存 | 已过期，但未完全解决 | 成功响应后即保存检查点；响应未知时仍未保存原密码 |
| A 2FA 密钥保存更早 | 对当前注册入口仍成立 | B 底层有 `on_secret`，但注册入口没有传入 |
| B 无已有账号恢复 | 已过期 | 原密码续跑和 OTP 后 MFA 已有；直接密码后 MFA/回调尚不完整 |
| B 无部分结果保存 | 已过期 | 核心持久化、`partial_success`、后处理状态和下一步动作已有 |
| B 只保存 AT 等少量字段 | 不完整 | 当前另存完整 ChatGPT session，Codex 凭据单独管理 |
| A 诊断全面优于 B | 不能成立 | A 多了协议流量统计；B 已有任务、阶段和请求证据体系 |
| 应优先保留中间成果 | 方向正确 | 应精准补剩余保存窗口，而非再次重写已有检查点体系 |

### 4.2 截图 3：Chrome 152 降到 146 与优惠的关系

截图正确保留了“作者观察，不足以证明因果”的限定。A 注释确有这种历史描述，但没有相同账号条件、时间、线路、依赖及完整响应的可复核对照材料。

本轮本地依赖元数据为 `curl_cffi 0.16.0`；该已安装包的 `BrowserType` 枚举最高 Chrome 档位为 `chrome146`，此处未做实际 TLS 握手验证。B 并不是简单把配置中的 149 原样发出：`BrowserSession` 会按库支持能力解析实际档位，并同步常规 UA/Client Hints 与传入 JS 的画像。**所以“代码常量出现 149”不能直接等同于“运行时 UA149、TLS146”。**

A 桥接先把 Chrome 画像改成 152，再尝试 wreq；其根目录及 vendor 的 requirements 未声明 wreq。若按公开依赖安装后实际回退 curl_cffi，需重新验证该档位支持情况。这是部署可重复性和回退兼容问题，不能把本机未安装 wreq 当成作者线上也未安装的证据。

值得处理的是“后端、实际支持档位、UA/Client Hints/JS 是否一致”的可验证契约，不是单独把版本字符串改大。[A 桥接][a-bridge]，[A HTTP 适配][a-wreq]，[B 会话][b-session]，[B 浏览器配置][b-browser]

### 4.3 截图 4：Date、Intl 与 VM 时区

A 当前文件确实处理了 Date 时区并将 Date 注入 VM；截图指出的历史错误具有具体技术含义。但 B 当前也已有对应保护：Python 向 Node 传递时区，Node 设置 `process.env.TZ`，VM 使用相应 Date/Intl 环境。

离线提取日期构造逻辑、使用合成时区值验证，A/B 均可给出 GMT+0700。该验证没有运行远端 SDK、网络或挑战计算。它支持“当前实现已有时区一致性处理”，不证明全部 SDK 行为或真实服务端资格判断。

因此，这不是可以直接复制给咱们的新增优化，也不能用某段历史 GMT+0800 文本推断当前实际线路或优惠原因。[A JS 环境][a-js]，[B Python runner][b-runner-py]，[B Node runner][b-runner-js]

### 4.4 截图 5：修改 TLS/HTTP2 的小样本数据

截图已正确指出：这些数字最多说明作者当时某组请求的通过情况，未提供对应优惠结果的对照。原始、只改 TLS、同时改 TLS/HTTP2、只改 HTTP2 几组观察，不能证明随机化更优，也不能跨日期、线路和 SDK 版本外推。

另一个版本差异是：A 当前默认尝试的 wreq 工厂明确忽略 `tls_fp` 和 `akamai_fp` 参数，因此截图中的历史定制实验也不能直接代表当前默认后端行为。[A HTTP 适配][a-wreq] 行 759–766。

本报告不把这些注释当成选择网络后端的依据。若未来评估传输层，应先在受控环境验证代理、Cookie、重定向、超时、错误类型、取消与资源关闭的语义一致性，再用明确授权的实际业务样本评估兼容性和可靠性。

## 5. 咱们当前值得优化的具体问题

优先级定义：P1 为凭据丢失或续跑正确性风险；P2 为预算、兼容性和可观测性改善；P3 为需要额外证据才值得做的架构工作。这里列的是建议，尚未实施。

### P1-1：新密码提交结果未知时，原密码没有持久化

**触发条件：** 新账号密码模式，`user/register` 请求已发出，但连接中断、超时或服务端 5xx，使结果未知。

当前顺序为生成密码 → 发请求 → 收到成功响应 → `on_password_submitted` 保存检查点。请求抛异常时会进入 `request_unknown`，但保存回调尚未执行，外层也未取得函数返回的密码。虽然保留了邮箱，仍缺少可靠复用同一密码的依据。A 的密码早存同样在成功响应之后，并没有完全解决这个窗口。

**本轮离线复现：** 从源码 AST 提取密码阶段函数，全部网络动作替换为桩，在提交点注入 `TimeoutError`。结果为 `user/register 请求结果未知`，保存回调调用次数为 0；未导入业务配置或连接数据库。

**建议：** 在提交前把生成密码写入原 Attempt 的私有恢复上下文，区分“准备提交、请求已发出、远端确认”；本地保存失败时不要提交。未知结果续跑复用原邮箱、原密码和原 Attempt，不重新生成密码，也不把“本地已有密码”当成“远端已接受”。

**验收：** 提交前中断、提交后无响应、远端明确拒绝、远端成功后本地写失败四类故障注入；确认不会丢原密码、重复建号或释放邮箱。

证据：[B 协议主体][b-protocol] 行 180–238、677–711；[A 认证流程][a-auth] 行 2696–2788。

### P1-2：注册 2FA 没接上现有密钥早存回调

**触发条件：** enrollment 已返回密钥，激活响应丢失；或 2FA 已成功，随后 Codex 长时间等待、进程退出或结果写入失败。

`setup_2fa_protocol(..., on_secret=...)` 已支持拿到密钥后、激活前执行回调。注册入口调用时没有传 `on_secret`，成功返回的 `totp_secret` 又要等 Codex 完成后才写入数据库。风险是远端已经启用 2FA，本地只有进程内变量，进程中断后失去密钥。

**本轮核验：** AST 检查确认注册入口这一调用没有任何关键字参数，因此未接 `on_secret`。A 有绑定成功后的保存回调，保存时点更早，但它也不是 enrollment 前后的完整事务保证。

**建议：** 使用已有回调将密钥写入受限字段，并单独记录 enrollment/activation 状态；激活确认后立即更新状态。保存密钥不等于宣称 2FA 已启用。后续 Codex 成败不能决定密钥是否落库。

**验收：** enrollment 成功后、activation 无响应后、Codex 开始后分别模拟中断；重启后可读原密钥，且待确认状态不会被错误显示为已启用。

证据：[B 2FA 函数][b-export] 行 653–669；[B 协议主体][b-protocol] 行 971、996–1001、1048–1052；[A registrar][a-registrar] 行 350–383。

### P1-3：取得 AT 后，仍经过预热才保存核心账号

代码虽已把核心保存移到独立后处理之前，但多个 Token 成功分支之后仍运行 `authenticated_bootstrap` 和等待，再统一调用 `persist_registration_core`。

普通非严格预热失败通常会降级，不能说任意预热错误必然丢账号；但进程中断、严格模式抛异常，或预热耗时扩大，都让已经取得的 AT/session 暂时只存在内存。

**建议：** 把成功取得并校验 AT/session 的持久化作为紧邻的边界，后续预热、套餐和其他设置使用已保存账号。保留现有会话与 Cookie，不需要重建认证流程。

**验收：** 在取 session 后、预热中和进入后处理前注入异常或进程中断；账号核心凭据应已保存，恢复仅补未完成步骤。

证据：[B 协议主体][b-protocol] 行 802–819、840–855、889–925。

### P1-4：已有密码直接进入 MFA/回调时被当成未知页面

B 已支持原密码续跑，也支持 OTP 验证后的 TOTP。但 `_run_protocol_existing_password_stage` 仅接受邮箱验证相关响应；如果密码验证直接返回 MFA 或 OAuth callback，会在进入后续处理前抛“页面未知”。不能用“已经调用 v2 的密码函数”推断 v2 的全部分支都已接入注册。

**建议：** 根据服务端返回的明确状态分派邮箱 OTP、TOTP、回调及资料页；复用现有认证结果契约。仅使用已保存的凭据，缺少必要密码/密钥时返回可理解的待处理状态，不猜密码、不盲目发码。

**验收：** 分别覆盖密码→OTP、密码→TOTP、密码→callback、OTP→TOTP、凭据缺失和未知响应；尤其断言直接 TOTP/回调分支不额外发送邮箱 OTP。

证据：[B 协议主体][b-protocol] 行 263–297、648–673、794–807；[A 认证流程][a-auth] 行 3957–4009；[B 协议测试][b-protocol-tests] 行 775–871 的现有样本主要是密码→OTP→MFA。

### P2-1：把阶段预算传到实际等待，并改善停止响应

B 的 callback/session 有 90 秒 `StageBudget`，但主要在每轮开始检查，没有把剩余预算完整传入每个网络请求；一个调用仍可能超过阶段剩余时间。此处默认创建的 budget 也没有绑定任务取消对象。OTP 无效码后的再次等待可能重新取得 provider 等待额度，不能把“一处重发共享预算”推广为“全注册共享预算”。

**建议：** 先明确每个阶段的总截止时间、单请求上限和取消检查，再让调用方传入剩余时间；保留已提交请求的未知结果边界。不要简单把总等待增加到 A 的 900 秒。

**验收：** 使用假时钟、慢响应与取消信号，检查超时上限、停止延迟、任务终态和邮箱保留是否一致。

证据：[B 协议主体][b-protocol] 行 361–397、476–537、718–765；[B 阶段预算][b-budget] 行 178–227。A 的父进程/OTP 同为 900 秒见 [A 引擎][a-engine] 行 48、85–98 与 [A 桥接][a-bridge] 行 854。

### P2-2：补高熵 Client Hints 的条件路径一致性

B 常规画像已经按实际支持档位规范化；但启用高熵 Client Hints 时仍有读取全局版本字段的路径，可能与会话实际档位不同。该开关源码默认关闭，属于条件路径缺口，不能写成当前默认请求必然不一致。

**建议：** 所有版本相关字段从同一个会话画像派生，并增加开关开启/关闭的离线契约检查。先证明内部一致，再评估是否需要增加新传输层。

证据：[B 会话][b-session] 行 339–346 与 [B 浏览器配置][b-browser] 行 112–121。本轮仅确认本地依赖与源码默认，不声称已检查运行进程的私有配置。

### P2-3：补协议请求的常规统计，复用已有诊断体系

B 已能按任务记录阶段、耗时、原因码和 HTTP 请求。缺口是常规协议请求流量没有像浏览器流量一样进入汇总；A 在这一层更丰富。

需要纠正文档口径：当前完整抓包路径使用 `_raw_url/_raw_headers/_raw_body`，测试也明确要求保留原始字段，不能沿用旧流程文档“全部脱敏”的描述。`failure_only` 分支会排除成功请求并移除请求/响应正文，但这不等于全部元数据已脱敏。完整抓包属于私有敏感材料；本轮未读取实际抓包。新增常规统计应只保留聚合字段，不能把完整抓包直接当作可展示摘要。

**建议：** 在现有 session/任务上下文上汇总请求次数、耗时、状态族及可观测字节，关联 Attempt/Run。明确响应解压前后、重定向和重试口径；HTTP 可观测字节不等于 TLS/代理商账单流量。不要另建一套不关联任务的日志或数据库。

**验收：** 合成 GET/POST、重定向、重试和失败响应，检查归属与计数；凭据不进入统计、并发任务不串账、计量失败不影响注册。

证据：[B 会话][b-session] 行 664–733；[B 请求诊断][b-debug] 行 107–141、715–723、1641–1691；[B 请求诊断测试](../../tests/test_registration_debug.py) 行 274–296；[B 流量契约测试][b-traffic-tests]。

### P2-4：区分回调已经消费与 session 尚未取得

B 的 callback/session 组合重试每轮都会再次调用 `follow_oauth_callback`。如果 callback 已成功，而紧接着获取 session 临时失败，下一轮仍可能重放带一次性授权码的回调。该调用顺序已由源码确认；本轮没有在真实服务上验证重放的具体后果，不能断言已经造成某次注册失败。

**建议：** 保存同一会话中 callback 已完成的状态；后续先重试读取 session，只有明确未完成回调时才继续回调步骤。与现有终态停止、阶段预算一起验证，避免凭一次网络异常重启整个认证过程。

**验收：** callback 成功、首次 session 请求失败、第二次 session 成功的合成场景中，callback 只执行一次；callback 明确拒绝时停止，不靠重复请求掩盖错误。

证据：[B 协议主体][b-protocol] 行 489–529。

### P3：把 wreq 作为可评估后端，不作为当前默认改造

若后续有真实传输层兼容故障，值得隔离评估 wreq。评估至少覆盖相同代理语义、Cookie 合并、重定向参数、响应编码、超时、异常类型、关闭资源与取消；依赖须声明、版本须可复现、后端加载失败须明确可观测。

A 当前回退路径、依赖声明和固定画像并不足以证明可以直接替换 B 的 `BrowserSession`。更换后端也不能替代前面的持久化与恢复修复。暂不建议为此引入 vendor 全量代码、SQLite 或整套子进程任务模型。

## 6. A 的能力需要连同边界一起看

1. **成功可能来自历史结果。** 本轮队列结束或等待退出后，桥接只要按邮箱查到 `registered` 行，就停止重试并读取结果；最终主要以 AT 非空判断成功，未充分绑定本轮 Run。旧凭据可能掩盖本次失败，报告比较必须区分本轮完成与读取历史资产。[A 桥接][a-bridge] 行 874–899、948–998。
2. **异常时释放邮箱存在安全缺口。** 父入口对异常或 `ok=False` 标 available，无法证明远端账号未创建。不能照搬到本地租约模型。[A 入口][a-main] 行 219–237。
3. **两个持久化边界容易分叉。** vendor 中间凭据先写自己的 SQLite，父项目结果要等 JSON 返回再同步；子进程有数据不等于父 WebUI 已可恢复。[A 父数据库][a-db]，[A vendor 数据库][a-vendor-db]。
4. **总超时与内部等待冲突。** 单 OTP 默认 900 秒，父进程全部工作也默认 900 秒；预检、启动间隔、2FA 等还要额外占时。内部等待未结束就可能被外层截断。[A 引擎][a-engine]，[A 桥接][a-bridge]。
5. **日志实时性与停止并不天然更好。** `subprocess.run(capture_output=True)` 在结束后转发 stderr，未提供按任务传播取消的控制通道；不能只看到内部有阶段日志就认为主 WebUI 实时可见。[A 引擎][a-engine] 行 85–106。
6. **新 backend 还需要部署契约。** requirements 缺 wreq、回退保留已改画像，都会影响公开项目在新环境复现。[A HTTP 适配][a-wreq]，[A 桥接][a-bridge]。
7. **调试信息需要重新审核。** A 有输出完整代理、Token 前缀及异常时凭据材料的路径；不适合直接复制到当前任务日志体系。[A 入口][a-main] 行 217、275–276；[A registrar][a-registrar] 异常与凭据回调相关代码。
8. **HTTP 后端会重试有副作用的请求。** A 的 wreq `_call` 对 GET、POST、PUT 等共用超时、连接重置和 EOF 重试判断，没有依据方法或“请求是否已发出”分类。返回错误不等于远端没有执行；账号创建、发码或激活可能被重复提交。B `BrowserSession.get/post` 没有这一层通用自动重试，但仍须单独审查各业务重试。[A HTTP 适配][a-wreq] 行 92–108、696–748；[B 会话][b-session] 行 664–733。

这些问题不否定 A 某些模块的价值；它们说明“组件更丰富”与“整体集成更可靠”需要分开判断。

## 7. 建议实施顺序与验收范围

| 顺序 | 工作包 | 预期收益 | 先做的验证 |
| --- | --- | --- | --- |
| 第一批 | 原密码请求前保存、2FA 密钥早存、AT 立即保存 | 降低远端已成功而本地丢凭据的风险 | 离线故障注入；独立 PostgreSQL 测试库/schema；确认原 Attempt 与原邮箱可恢复 |
| 第二批 | 补齐密码后直接 MFA/回调分支 | 改善已有账号和中断续跑的确定性 | 合成响应矩阵、无多余 OTP/注册提交、已有凭据不降级 |
| 第三批 | 预算与取消贯通、回调/session 重试、高熵头契约、协议请求统计 | 改善可定位性、停止体验和条件路径兼容性 | 假时钟、受控 HTTP 服务、聚合隐私与并发归属测试 |
| 条件性评估 | 可替换 HTTP 后端 | 处理有证据的传输层兼容需求 | 不接真实注册的后端契约测试；明确授权后再做有限真实流程验收 |

每批应按问题拆开验证，保留原有 PG、Attempt/Run、统一邮箱接口和成功口径。真实流程验收与离线测试分开记录；不要用新增注册数量、优惠数量或作者注释代替凭据保存、续跑安全和状态正确性的验收。

## 8. 本轮验证与限制

已完成：

- 固定 A/B 提交并核实公开 main，检查本地工作区；保留所有已有未跟踪文件。
- 追踪两边真实入口，区分已接入、默认关闭、仅工具/旧代码和作者注释。
- 对截图 1–5 逐项核验，尤其检查当前 B 已有的优化。
- 离线复现密码提交超时不触发保存回调；AST 确认注册 2FA 未接 `on_secret`。
- 读取本地依赖元数据；离线检查 Date/VM 时区逻辑。
- 静态检查测试文件与关键断言；未把文件数量当作测试通过证据。

未完成且不作声称：

- 没有跑整个 pytest 套件或真实注册；没有测量两边相同条件下的成功率、耗时和实际代理账单。
- 没有检查作者线上依赖、私有配置或注释引用的未公开实验材料。
- 没有检查本地运行进程已加载的版本与配置，因此本报告评价的是固定源码及所检查的本地依赖。
- 没有修复上述问题；报告列出的触发条件不表示已经在某个真实账号上发生。

## 9. 源码索引

所有 A 链接固定到本轮审查提交；B 链接指向当前仓库文件，行号以本文基线为准。后续修改后须重新定位。

- [A 主入口][a-main]；[A 子进程引擎][a-engine]；[A 桥接][a-bridge]。
- [A 认证状态流程][a-auth]；[A registrar][a-registrar]；[A wreq 适配][a-wreq]；[A JS 环境][a-js]。
- [A 父数据库][a-db]；[A vendor 数据库][a-vendor-db]。
- [B 协议主体][b-protocol]；[B 分发器][b-dispatch]；[B 任务服务][b-service]；[B 检查点][b-checkpoint]。
- [B session][b-session]；[B 浏览器画像][b-browser]；[B Python runner][b-runner-py]；[B Node runner][b-runner-js]。
- [B 2FA/session 工具][b-export]；[B 阶段预算][b-budget]；[B 请求诊断][b-debug]。
- [B 协议注册测试][b-protocol-tests]；[B 协议流量契约][b-traffic-tests]。

[a-main]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/main.py
[a-engine]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/core/register_protocol_engine.py
[a-bridge]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/vendor/gpt-register-tool/协议/_turb_bridge.py
[a-auth]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/vendor/gpt-register-tool/协议/auth_flow.py
[a-registrar]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/vendor/gpt-register-tool/协议/webui/registrar.py
[a-wreq]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/vendor/gpt-register-tool/协议/http_client_wreq.py
[a-js]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/vendor/gpt-register-tool/协议/openai_sentinel_quickjs.js
[a-db]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/core/db.py
[a-vendor-db]: https://github.com/wangshen233/turb-gpt-free-register-oss-20260928/blob/7df094e05e48a74eeacc4ff6e3c27165def21cae/vendor/gpt-register-tool/协议/webui/db.py
[b-protocol]: ../../core/registration/protocol.py
[b-dispatch]: ../../core/registration/dispatcher.py
[b-service]: ../../core/registration_service.py
[b-checkpoint]: ../../core/registration/checkpoints.py
[b-session]: ../../core/session.py
[b-browser]: ../../config/browser.py
[b-runner-py]: ../../core/sentinel_runner.py
[b-runner-js]: ../../sentinel/sentinel-runner.js
[b-export]: ../../core/account_export.py
[b-budget]: ../../core/registration/state_machine.py
[b-debug]: ../../core/registration_debug.py
[b-protocol-tests]: ../../tests/test_protocol_registration_password.py
[b-traffic-tests]: ../../tests/test_proxy_traffic_backend.py
