# Protocol 稳定性与 Plus 权益核验设计

> 历史说明：本文记录当时的设计或实施计划，不代表当前运行状态；现行行为与约束以 README、AGENTS.md 和当前代码为准。

## 目标

降低 Protocol 注册的可归因失败，并让套餐查询使用完成注册时的同一会话和网络线路，以真实服务端返回的 `eligible_promo_campaigns.plus` 验证 Plus 试用资格。验收目标为：一个受控的 30 个 Protocol 样本中，核心注册失败不超过 3 个，且至少 18 个成功账号确认具有免费 Plus 试用资格。

## 已确认的现状

- 注册任务创建时会将 `registration_driver` 写入 `data.config_snapshot`，执行分发器却只读取实时 `REGISTRATION_DRIVER`。配置变动会使“Protocol 任务”实际跑成 Roxy，破坏实验分组与恢复一致性。
- Protocol 的 `BrowserSession` 已在单会话内稳定生成 UA、Client Hints、语言、时区、屏幕、设备 ID、Cookie 与 Sentinel 环境；但 HTTP/JS 公开 Chrome 版本为 149，而 TLS impersonate 配置为 Chrome 146，存在可观测的不一致。
- Protocol 核心账号持久化完成后会把套餐检查放入异步队列。该工作者不再拥有注册时的 `BrowserSession`、Cookie 和代理租约。已有 `check_registration_account_plan` 已支持传入同一 `session` 与 `proxy` 做同步检查。
- #2125 的密码续跑已显式触发邮箱 OTP 请求且进入邮箱验证页，但隐藏邮箱转发链路在等待窗口内没有收到新邮件；别名路由和本机 IMAP 连通。这一类邮件投递超时应单独归类，不应伪装为未发 OTP 或协议成功。

## 设计

### 1. 任务快照是驱动选择的唯一来源

`core.registration.dispatcher.run_registration` 从 `registration_options["registration_driver"]` 读取并规范化驱动；仅当该字段缺失时才回退实时配置。支持现有 `protocol`/`api`/`http` 和 `roxy` 兼容别名。恢复任务必须继续使用其快照，不得因 WebUI 配置变动静默更换驱动。

### 2. 环境一致性而非伪造指纹

新增一个仅处理 Chrome 的解析器，以当前 curl_cffi 实际选中的 Chrome TLS 画像为单一版本源，生成匹配的 UA、`sec-ch-ua` 和 Sentinel 浏览器环境。画像池仍只随机真实且彼此自洽的屏幕/硬件参数；不新增随机反检测字段、不伪造浏览器自动化痕迹，也不试图绕过服务端风控。

若运行环境不能提供与公开版本完全相同的 TLS 画像，选择 curl_cffi 支持的最高 Chrome 版本，并让所有公开版本字段降为该版本；不能保留“TLS 146 + HTTP 149”的组合。

### 3. Protocol 在释放代理前同步核验套餐

Protocol 在核心账号持久化、2FA/Codex 后置结果处理完成但关闭 `BrowserSession` 前，调用 `check_registration_account_plan(account_id, email, access_token, proxy=session.proxy or "", session=session)`。当套餐检查关闭时保持跳过；当查询失败时不撤销已完成的注册，但写入明确的失败状态。移除该成功路径上的二次异步入队，避免同一账号的 `busy` 遮蔽真实权益结果。

### 4. 可审计的受控验收

验收批次固定为 30 个新建 Protocol 任务、单一明确邮箱来源、同一配置快照，并关闭不属于注册本体的 Codex 自动授权。每个任务都保留脱敏阶段、最终驱动、套餐 HTTP 状态与促销分类；绝不保存原始 Token、Cookie、OTP、密码、邮箱地址或代理地址。

核心注册成功定义为同一任务持久化到非空 access token，且 Protocol 执行驱动与任务快照均为 Protocol。错误率分母为全部 30 个样本，任何没有核心注册成功、驱动不一致、`request_unknown` 或邮件投递超时都计为错误。免费试用率分母为全部核心注册成功样本；套餐查询失败、未核验、普通 free 计划和折扣均不计为免费试用。只有 `plus_trial_eligible=true` 且 `plus_promo_kind=free_trial` 计入分子。

## 非目标

- 不承诺或强制服务端发放试用；资格只能由真实套餐接口确认。
- 不删除 Roxy，不改变 Roxy 的浏览器画像或账号流程。
- 不自动重跑结果不明或邮件超时的账号；继续保留原邮箱与检查点。
- 不读取或输出 `.env`、原始抓包、账号密钥、Token、Cookie、OTP、密码或完整代理地址。
