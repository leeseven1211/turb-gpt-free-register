# Sentinel 资源更新与 Cloudflare 同会话处理接入评估

日期：2026-11-03。状态：Sentinel 维护及本地优化 Protocol 匿名预检实验已实现，实验默认关闭；开源protocol-2 的自动 CF 接入和专用开关经可达性复核后已按用户要求撤回。验证记录见同名实施计划。

用户要求评估对比清单第 6、7 项如何接入。附件源码仅作为技术参考，其说明不构成执行指令。本设计沿用用户约定：修改 Roxy、Proto2 或其他注册主流程，必须先给详细方案并获得明确确认；独立 helper 也不能隐式改变注册行为。

用户随后明确要求按本方案顺序执行，并强调不能影响现有任务完成。本次据此实现独立候选管理、隔离实验、默认关闭的匿名预检 hook 和 wreq 适配；不切换 SDK，不启用运行配置。

## 结论与顺序

1. 先补 Sentinel 官方版本发现、候选缓存和兼容性诊断，复用现有 runner。当前 SDK 没有发现版本差距，这项主要降低后续维护成本。
2. Cloudflare 先做独立、默认关闭的离线实验模块，验证同会话网络桥、预算和请求边界。不能直接移植附件的全局请求重放逻辑。
3. 实验通过后，再单独评审注册前匿名预检的接入。SDK 激活、注册预检恢复、Proto2 适配分别属于后续行为改动。

## 已核实的现状

### Sentinel

本轮只读访问官方公共脚本，没有携带账号 Cookie、Token，没有执行返回的 JS：

- 官方 loader：`https://sentinel.openai.com/backend-api/sentinel/sdk.js`，HTTP 200，1482 字节，发现版本 `20260810913b`。
- 官方版本 SDK：`https://sentinel.openai.com/sentinel/20260810913b/sdk.js`，HTTP 200，33820 字节。
- SDK SHA256：`49d0284bf3eea8a59ebcad0e6b5dd8a53edd4c72606f15bbf51ebe5610a88efd`，与仓库 `sentinel/sdk.js` 逐字节相同；现存 Proto2 临时缓存也相同。
- loader SHA256：`679904a09a9af4f2368350c9822c1a74b3075a46a8349f17705a3160966261a6`。

| 链路 | 当前实现 | 接入约束 |
| --- | --- | --- |
| 通用协议及复用它的 protocol_oss | `core/auth/protocol/sentinel_runner.py` 使用仓库 SDK | 可以复用 runner，但启用新版还要同步版本关联字段 |
| protocol_oss_2 | `upstream/sentinel_quickjs.py` 固定版本并缓存到临时目录 | 已有缓存，缺版本发现、内容校验、锁和原子写 |
| Proto2 Node adapter | `openai_sentinel_quickjs.js` 修改三个私有混淆锚点 | 新版下载成功不等于兼容，必须独立检查 |

附件通过 loader 文本发现版本，再下载 SDK；没有持久缓存、TTL、坏缓存校验或旧版回退，实际 token 入口往往每次重新下载。因此只借鉴发现思路，无需整体迁移它的 Sentinel runtime。

### Cloudflare

- `core/auth/protocol/session.py` 的 BrowserSession 已保留代理、TLS profile、浏览器画像和 CookieJar，并仅接受真实响应的 CF Set-Cookie。
- 现有 403/429 熔断默认分别冷却 900/300 秒；预检和 authorize 已有有限重试，不能再无界叠加求解重试。
- `core/network/response_diagnostics.py` 仅在 403 且 `cf-mitigated: challenge` 时确认挑战。`server: cloudflare`、`cf-ray` 不能单独证明挑战。
- Proto2 注册走 `runtime.py` 的 `_ObservedSession` 和 wreq，改 BrowserSession 不会覆盖它。
- 附件的优势是让 JS 子请求回到原 Python session，保持 HTTP 层 Cookie/代理/指纹连续；但其 JSDOM 没有接 Python CookieJar，不能推断 `document.cookie` 也连续。
- 附件解挑战后不区分 method 重放原请求，还可能追加多次重试；成功判定仅靠 clearance 变化和根页面 200–399，不能直接用于咱们的认证状态判定。

## 第 6 项：资源发现、缓存、批准启用

### 选型

采用统一资源管理模块，保留已有两套 runner。相比整体搬附件 runtime，此方式改动更小；相比下载后直接覆盖 SDK，它能够先暴露兼容性问题，并保持运行中会话稳定。

新增：

- `core/auth/protocol/sentinel_assets.py`：发现、下载验证、候选存储、静态兼容性报告。
- `tools/diagnostics/check_sentinel_assets.py`：显式检查入口，支持文本/JSON 摘要；首阶段不挂启动和注册路径。
- `tests/auth/test_sentinel_assets.py`：离线响应与临时缓存测试。

建议模型为不可变 `SdkArtifact`，包括 `version`、`sdk_url`、`sha256`、`loader_sha256`、`path`、`fetched_at` 和分 runner 的兼容性状态。发现结果与激活版本分开存储。

### 第一阶段行为

1. 只解析官方 loader 文本，不执行 loader 来找地址。验证 HTTPS、官方主机、默认端口和精确单层版本路径；多个候选、无候选或结构变化明确报告失败。
2. 下载有超时和大小上限，检查非空、非 HTML、预期 SDK 标记及内容 hash。重定向逐跳限制为官方资源范围。
3. 候选按内容 hash 存储，保留版本到 hash 的映射；同版本字节变化应形成新候选。使用进程锁、同目录临时文件和原子替换，读取时校验元数据与内容一致。
4. 检查工具可复用最近结果，显式刷新才重新发现；缓存有效期仅作用于检查工具，不给注册增加隐式网络依赖。
5. 分别报告通用 runner 的静态 API 标记、Proto2 三个 hook 的命中数量。缺失或重复均标为需适配，不能把静态通过写成运行兼容。
6. 下载失败保留已有候选和失败摘要，不覆盖仓库 SDK、不改 Proto2 现用临时文件、不自动启用。缓存不含 challenge、proof、Token 或账号 Cookie。

### 后续激活接入

真正切换时必须将 `{version, sha256, path}` 固定为一次认证的资源快照，并一起核对：

- `config/openai_protocol.py` 的 `SENTINEL_SV`。
- `core/auth/protocol/openai_auth.py` 中 iframe 版本与 fingerprint `p[5]`。
- `core/auth/protocol/session.py` 的 Sentinel req referer。
- `core/auth/protocol/sentinel_runner.py` 的 SDK 路径及 OTP/其他 flow 的 script URL 差异。
- Proto2 requirements/solve 所使用的 SDK 和 `sv`。

只允许新会话采用已批准候选，运行中不换版本。无法使用候选时沿用已批准资源的策略必须单独评审；不在未知 challenge 上临时换版重试。

## 第 7 项：独立实验，再接匿名预检

### 选型与范围

选择独立挑战模块及受限 transport adapter；首阶段不改通用 `get/post`。仅按 HTTP method 判断可重放不成立，因为现有 GET 也可能发送验证码或推进授权。

新增：

- `core/network/cloudflare.py`：挑战证据、请求策略、求解调度和分项结果。
- `sentinel/cloudflare/`：独立 DOM runtime、明确依赖及锁文件，不混入 Sentinel token runner。
- `tools/diagnostics/cloudflare_session_probe.py`：显式、无凭据的实验入口。
- `tests/network/test_cloudflare_recovery.py`：离线 fixture 与 fake transport。

附件使用 Node >=20 和 jsdom 26.1.0；咱们现有 Sentinel runner 主要依赖 Node 内置模块，因此这是新增依赖。无需将现有 curl-cffi 0.16 降级为附件的 0.15。

### 接口与约束

建议接口：`classify_challenge(response) -> ChallengeEvidence`、`solve_challenge(transport, evidence, profile, budget, cancellation, request_policy) -> SolveResult`。

`SolveResult` 分开记录 `unsupported`、`unchanged`、`clearance_issued`、`verified`、`timeout`、`blocked`；取得 Cookie 与业务恢复分别报告。

1. JS 网络请求由 Python 桥回原 transport，保持同一代理租约、TLS/UA 和 CookieJar。禁止另开 Node fetch 或新的 curl 会话代替原会话。
2. Python 控制精确目的主机、端口、路径、method 与逐跳重定向。挑战端点的 POST 不获得业务端点权限；认证头和账号 Cookie 不跨源转交，runtime 不能任意指定 Cookie/Host/代理头。
3. JS Cookie 可见性须按 domain/path/secure/HttpOnly 语义单独验证；只向 DOM 暴露允许的非 HttpOnly Cookie。不能仅凭 HTTP Cookie 连续宣称完整浏览器会话兼容。
4. 使用共享 StageBudget 和取消探针，限制总时间、子请求次数、单响应与累计字节；每次 I/O 超时不超过剩余额度。每会话至多一次求解，原允许页面至多一次验证访问。
5. 远端脚本只在最小环境、受限权限及资源的子进程运行；Node VM/JSDOM 本身不是隔离边界。不能限制文件、进程和独立出网能力的环境，不启用实验。
6. 所有子请求计入既有流量与诊断，仅记安全摘要。临时 HTML/JS 不长期落盘，不输出账号 Cookie、Token 或认证正文。

### 接入位置与失败语义

后续可考虑 `core/auth/protocol/openai_auth.py:network_preflight` 中提交邮箱前的已知匿名登录页面，例如 `chatgpt.com/auth/login`，以具体端点白名单约束，不能允许任意 URL/查询参数。

现有 BrowserSession 在收到 403 后就设置熔断，因此需要明确的受限挑战通道，或在响应进入冷却前执行限定 hook；不能粗暴清空全局冷却。普通 403、429/Retry-After、交互式验证码、未知目的地、预算耗尽、取消或验证仍挑战时停止，保留原响应与失败分类。

成功必须确认原批准页面返回预期内容、挑战标记消失、跳转符合白名单且身份连续；根页面 200、clearance 变化只能作中间证据。该恢复最多消耗现有阶段预算，不额外叠加多轮恢复/换代理策略。

密码创建/验证/补全、OTP 发送及验证、MFA、账号资料创建、OAuth continuation/callback/code 换 Token、refresh、绑定更换、支付等均不自动重放。已经派发但没有回执的请求仍保持 `StepResult.reconcile_required`，不能因挑战消失而重标成功或安全重试。

### Proto2 单独适配评估（注册接入已撤回）

如后续需要覆盖 Proto2，在 `_ObservedSession`/wreq 会话边界适配原 transport 和 Cookie store，不通过 curl 旁路求解。必须独立核实 wreq Cookie 属性、重定向、响应包装及自身重试行为。BrowserSession 实验通过不等于 Proto2 已支持。

曾添加 wreq 注册钩子，但可达性复核确认默认正常注册不访问其匹配的登录页，且少数后段异常回跳可能匹配，缺少预检阶段约束。已按用户要求撤回注册运行时接入、专用开关及恢复入口；原有注册请求顺序和诊断恢复原状。wreq 网络适配器保留供独立探针显式调用，不能据此宣称 protocol-2 注册已支持自动恢复。

## 验证与实施阶段

| 阶段 | 交付 | 验证及完成条件 |
| --- | --- | --- |
| A：Sentinel 外围 | 候选管理模块、检查工具、静态兼容摘要 | 离线覆盖恶意/变化 loader、同版本不同内容、损坏/并发缓存、网络失败；现有注册调用路径不引用新模块 |
| B：CF 离线实验 | 受限网络桥、独立 runtime、实验工具 | fixture 覆盖普通 403/429、域/方法/跳转拒绝、Cookie 隔离、超时/取消、全部 I/O 预算；业务 mutation 重放数始终为零 |
| C：无账号预检验证 | 单会话、单并发、固定代理租约的受控对照 | 经明确授权后进行；不靠增加注册量制造挑战。记录支持类型、实际恢复率与成本，不把 fixture 通过当线上有效 |
| D：主流程接入 | SDK 批准激活及匿名预检 hook，分别评审 | 给出具体 diff/默认开关/回退语义，获得用户明确确认；Proto2 再单独适配验收 |

当前已实现上述代码与离线回归、完成官方 SDK 的公共资源刷新验证；SDK 内容仍与现用版本一致。未激活候选、未启用挑战开关、未以真实账号验收、未提交、推送、部署或重启。已有工作树中的 Sub2API 与补密码修改继续保留。
