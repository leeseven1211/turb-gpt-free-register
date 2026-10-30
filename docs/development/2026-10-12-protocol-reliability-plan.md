# 协议注册可靠性实施记录

日期：2026-10-12。依据[主流程对比报告](../reference/2026-10-12-protocol-registration-comparison.md)，本轮完成 P1、P2 的代码与隔离验证，并对 wreq 做离线兼容性评估。基线为本地 main `0f1cb6a`，保留此提交包含的套餐重跑与代理复用修复。

## 设计边界

- 沿用 PostgreSQL、Attempt/Run、统一驱动和邮箱租约；不引入第二套数据库或注册引擎。
- 密码在发出请求前进入原 Attempt 的私有恢复上下文；准备、请求开始、远端确认分别记录。已有密码不等于已成功提交；未知结果不释放邮箱。
- 2FA 密钥在激活前保存为待确认，激活确认后才显示启用；后续 Codex 失败不影响凭据保存。
- AT/session 在预热与其他后处理前保存；恢复过程只补未完成步骤。
- 已有密码按明确响应分派邮箱 OTP、MFA、回调和资料页；缺少凭据与未知状态停止，不猜测或重复创建。
- 阶段截止时间传到实际请求和等待；取消不丢失已发送请求的未知结果语义。成功消费的回调不因 session 获取失败而重放。
- 常规协议统计仅保存聚合数值与任务归属，不保存 URL 查询、请求正文、Cookie 或凭据；计量异常不影响业务。
- 条件性高熵请求头从会话已解析画像派生，默认开关保持原样。
- wreq 仅在受控本地服务中检查接口语义与资源行为；不默认替换生产后端、不增加真实注册或试用测试。

## 并发分工与文件边界

1. 凭据与恢复：协议密码阶段、注册主函数、检查点与必要的存储/投影，覆盖 P1-1 至 P1-4。
2. 预算与取消：协议 OTP 等待和 callback/session helper、实际网络超时及邮箱等待，覆盖 P2-1、P2-4；与第一组按函数边界协作。
3. 会话与统计：`core/auth/protocol/session.py`、协议流量采集/归集与对应测试，覆盖 P2-2、P2-3。
4. 集成：主 agent 负责跨组接口、wreq 本地契约评估、文档、隔离测试、审查与提交。

所有 agent 使用 GPT-6.1-sol。存储修改在独立 worktree 中完成，测试使用非生产数据库和 `test_` schema。子 agent 不提交，主 agent 审查后按工作包提交。

## 验证要求

- 密码提交前中断、提交后无响应、明确拒绝、确认后写入失败；核实原密码和 Attempt 能继续恢复。
- 2FA enrollment/activation/Codex 三个边界故障注入；待确认不能投影为已启用。
- session 到预热的异常边界；核心凭据已持久化。
- 密码后 OTP/MFA/callback/资料页/未知响应矩阵；不额外发送 OTP。
- 假时钟和取消信号验证截止时间、退避与 provider 等待；callback 成功后 session 重试只消费一次 callback。
- 会话画像开关契约；并发任务聚合归属、失败计数、隐私和计量降级。
- 本地 HTTP 服务验证后端代理、Cookie、重定向、编码、超时、异常、资源关闭；结果不外推为风控或优惠改善。
- 最小测试通过后执行跨模块回归，记录未验收的真实流程和运行时边界。

## 交付状态

P1、P2 实现及 P3 本地后端兼容性评估已完成。本轮相关回归通过；全量仍有 3 项已复现的基线失败，具体结果如下。交付为本地代码，运行时和真实注册尚未验收。

## 实际变更

| 工作包 | 实际行为 |
|---|---|
| 原密码早存 | `registration_attempts.private_context` 保存原密码，提交前按 `prepared`、`started`、`confirmed` 分段记账；公开查询和事件不返回私有字段。候选密码只有收到远端提交或验证确认，才显示为账号的有效密码。 |
| 原意图恢复 | 无本地账号记录的未知结果可以在原 Attempt 续跑；根据服务端状态分派密码、OTP、MFA、回调和资料页，未知状态停止。CLI 建立稳定 Attempt 和逐次 Run，仅确认旧本机进程已退出时恢复该 CLI 执行。 |
| 2FA 与核心会话 | 密钥先保存为待确认，激活成功后才更新已启用字段；AT 与完整 session 在预热和后处理之前保存。严格预热失败返回核心成功、后处理未完成。 |
| 阶段预算与回调 | 验证码轮询、无效码重试、退避、手动输入和实际请求共享预算；成功回调不重放，仅重试 session。回调响应丢失或 5xx 保留未知结果，仅明确 429 拒绝允许有限重试。 |
| 会话画像 | 条件性高熵请求头从当前解析后的会话画像派生，保留原开关默认值。 |
| 请求统计 | 按会话聚合请求、错误、状态族、耗时和后端观测字节，使用真实 Task/Run、Attempt 和代理租约归属；CLI 使用原生注册 Run，不伪造 operation Run。现有页面增加协议来源和计量口径。 |

## wreq 本地评估

独立临时 Python 环境使用 `curl_cffi==0.16.0` 与 `wreq==0.13.0`，分别通过 13 项 loopback HTTP 合成检查，主 agent 又独立复跑一次，结果均通过。工具和固定依赖位于 [`tools/benchmarks/evaluate_http_backends.py`](../../tools/benchmarks/evaluate_http_backends.py)、[`tools/benchmarks/http_backend_eval_requirements.txt`](../../tools/benchmarks/http_backend_eval_requirements.txt)，机器可读结果见[评估 JSON](../reference/2026-10-12-http-backend-contract-result.json)。

覆盖 Cookie 合并、重定向开关、表单/JSON/原始正文、压缩与字符集、HTTP 错误、连接断开、请求超时、显式 HTTP 代理和关闭后拒绝新请求。代理检查确认请求命中合成代理，未访问合成源站。两个库的参数与异常类型不同，需要适配，不能直接替换导入。

本轮没有评估 TLS/HTTP2 相似度、HTTPS CONNECT、SOCKS/DNS、在途取消、真实注册、风控或优惠资格。合成本机耗时不能外推远端性能。因此保留生产默认 `curl_cffi`，未添加 `wreq` 自动启用或加载失败回退逻辑。

## 验证记录

- 使用独立工作区、独立非生产数据库 `turb_test_protocol_20261012` 和隔离 `test_` schema；未读取生产账号或执行真实注册。
- 分组验证覆盖凭据边界、注册服务、邮箱 provider、状态机、HTTP 会话、流量 API 和页面契约。跨存储、注册驱动和多个邮箱 provider 的改动涉及共享运行时，因此额外执行整个 `tests/` 的 `--profile all` 回归。
- 真实 Chromium 打开实际现代模板和静态资源，以合成 API 数据验证流量列表及详情。桌面和 390 × 844 窄屏均能查看；窄屏详情宽 343 px、页面没有水平溢出，控制台无错误。这属于页面验证，不是生产服务验收。

全量首轮为 2211 passed、1396 subtests passed、8 failed（346.81 秒）。其中 5 项涉及新测试上下文隔离及 callback 新预算参数断言，修复后重新验证；另外 3 项在未修改的 `0f1cb6a` Git 归档快照中单独复现了同样失败，未扩大本轮范围修改：

| 基线失败用例 | 已核对原因 |
|---|---|
| `test_dashboard_api.py::DashboardApiTests::test_modern_ui_contains_overview_and_no_external_sidebar_links` | CSS 已采用 `minmax(0,1fr)`，原测试仍要求旧的 `minmax(64px, 1fr)`。 |
| `test_db_only_compat_files.py::DatabaseOnlyCompatibilityTests::test_save_account_data_preserves_deprecated_output_path_position` | 原函数第 5 个参数已是 `chatgpt_session`，旧调用测试仍把 `Path` 放在该位置。 |
| `test_release_checks.py::test_runtime_has_no_retired_root_file_io` | 原 `roxy_profile_binding.py` 仍读取旧 JSON，发布检查禁止该引用。 |

基线复现命令为隔离入口加上上述三个完整节点 ID，`--profile all -- <三个节点> -q --tb=short`，结果 3 failed（3.11 秒）。

最终在相同独立测试库中执行 `python tools/test_isolated.py --profile all -- -q --tb=no`，没有排除用例，结果 **2223 passed、1398 subtests passed、3 failed**（318.70 秒）；失败项恰好为上表三个基线问题，本轮引入的失败已全部修复。没有把这次结果标记成全量绿灯。

- CLI、流量、身份分派和日志上下文联合回归：70 passed、2 subtests passed；另补显式空范围与外层关联恢复验证，44 passed、2 subtests passed。
- OTP 预算、CLI、Forward IMAP、CloudMail、会话和凭据的边界回归：108 passed、18 subtests passed；后续 CLI 核心结果摘要专项 17 passed、2 subtests passed。计数有重叠，不相加作为覆盖率。
- `node --test tests/test_proxy_traffic_frontend.cjs`：9 passed；两个变更脚本的 `node --check` 通过。
- 本地后端工具独立复跑：curl_cffi 与 wreq 各 13 项通过。
- 暂存范围内 Python 语法、`git diff --cached --check`、新增 Markdown 链接与标题检查通过；仅暂存本轮 49 个文件。

## 运行时边界

- `requests` 的 connect/read 参数是连接或读取空闲超时；持续传输的同步响应不承诺硬总截止时间。轮询与退避分段检查取消，在途 I/O 仍受底层库超时约束。
- 协议字节只取后端传输正文计数，不含请求/响应头、TLS 和隧道；解压后长度单列，不能代替传输字节。Node、预检以及绕过 `BrowserSession.get/post` 的请求不在本轮采集范围。统计写入有节流，异常不改变注册结果，但同步落库仍有开销。
- 没有改动优惠资格判断，也没有证据表明本轮可靠性改动会提高试用出现比例。
- 未推送远端、未重启服务、未验收真实注册或线上数据库迁移。下次加载注册存储时会执行幂等的私有恢复字段扩展。
