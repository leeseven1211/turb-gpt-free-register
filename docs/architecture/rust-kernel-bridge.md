# Rust 内核接入契约

本次接入把 `rust` 与 `browser`、`protocol` 并列登记，并新增实现 `sentinel_rs` 的
`registration` 绑定。当前是**一次性子进程**接入：Python 交付已分配的邮箱与代理，原生进程
独立完成注册并写回自己的临时 SQLite，Python 只读取经过身份核验的账号事实。

> 已知限制：只支持 `generic_api` 邮箱来源（该来源本身提供 `email----code_url`）；不支持
> 原身份续跑、交互式 OTP 和提交前密码检查点；原生进程在成功后才返回密码。上述能力要等
> 双向 JSON Lines 协议落地后才能开放。

## 来源与实现位置

候选项目为 `wangshen233/sentinel-rs`，调查基线为提交
`f222371c7960be490baf4ab1a2873da900506f2a`。该次取得的源码没有 `LICENSE`，
README 声明研究用途并对使用范围作出限制；不能据此假定已经取得集成和再分发许可。
正式接入前需要确定许可和来源记录，锁定实际采用的提交，保留修改清单。
本次没有把该源码复制到项目内。

Python 侧位于 `core/kernels/rust/sentinel_rs/`（`bridge.py` 负责进程边界）。原生工程建议
构建到 `native/sentinel-rs/`，也可用 `SENTINEL_RS_BIN` 指向任意可执行文件。实现名
`sentinel_rs` 已进入 `IMPLEMENTATIONS`，当前开放 `registration`（注册）与
`refresh_at`（刷新 AT，驱动值 `rust`）两个操作。刷新设计见
[at-refresh-rust-driver.md](at-refresh-rust-driver.md)。

当前上游 `srs_register` C ABI 是单次调用，结果含邮箱、密码、AT、TOTP 和上游
SQLite 账号编号。它不足以表达本项目的密码提交前持久确认、交互式 OTP、取消、
完整会话交接和原身份恢复。后续采用独立子进程与双向消息，避免把原生崩溃扩散到
Python Worker；不能直接把该 ABI 的 `ok=true` 当作本地注册成功。

## 进程与消息边界

采用版本化 JSON Lines 双向通信；stdout 只输出协议事件，stderr 只允许脱敏诊断。
每条消息都携带 `protocol_version`、`execution_id`、`request_id`、单调 `sequence`
和 `type`。响应必须关联当前请求及当前执行身份；旧进程的迟到事件不能修改新 Run。
具体大小上限、超时、字段校验和版本协商在真实适配实现时固定并测试。

| 方向 / 消息 | 内容与责任 |
| --- | --- |
| Python → `start` | 固定操作、内核、实现、原邮箱、代理、指纹、候选密码、原密钥及恢复事实；不让 Rust 再领取邮箱或选择任务 |
| Rust → `ready` | 报告通信版本、构建身份和实际支持操作；尚未执行远端动作 |
| Rust → `progress` | 有界阶段和事实，不含响应正文、密码、OTP 或 Cookie |
| Rust → `otp_request` | 当前挑战、发送回执与 `after_ts`；Python 使用现有邮箱服务取码 |
| Python → `otp_response` | 仅交给对应挑战，沿用原邮箱租约与取消上下文 |
| Rust → `checkpoint_prepare` | 提交密码或其它不可重复动作前报告候选资料及本次动作身份 |
| Python → `checkpoint_ack` | 原业务检查点事务成功后确认；Rust 收到匹配确认前不能发送远端动作 |
| Rust → `submission` | 动作已发送、是否收到回执、白名单错误分类及阶段证据；不猜测远端结果 |
| Python → `cancel` | 请求停止新动作，并等待 Rust 报告已发送动作的事实 |
| Rust → `result` | 结构化终态与凭据事实；Python 验证身份后交回原业务保存和后处理 |

Python 继续持有任务、Attempt/Run、邮箱/代理租约、账号和凭据保存、资源归还以及
后置 2FA、套餐和 Codex 任务。Rust 只执行已分配操作，不初始化另一份 SQLite、
任务队列、代理池或邮箱分配器。通信中的私有资料不得写入普通日志或任务公开结果。

## 结果与恢复

注册结果分别表达账号创建事实、密码状态、AT/完整 Session、身份依据和未决提交。
成功所需字段由注册领域契约决定；没有 AT、身份不匹配、只有资料提交成功等情况
不能由桥接层统一改成成功。完整 Session 必须保留 Cookie 域、期限、设备/指纹、
账号与用户标识等后续验证需要的资料，并通过现有私有存储路径保存。

恢复输入来自原 Run 的检查点，继续使用原邮箱和原候选密码。Rust 不因重启生成
新密码，不把已有账号当成新注册，也不把未收到回执当作远端拒绝。缺少可核验恢复
资料时返回明确事实，保留现有原任务重跑入口；跨内核恢复需要另行定义转换，不能
把 Rust 私有资料交给浏览器或协议实现解释。

取消、连接断开或子进程崩溃后，已确认保存的事实不丢弃。Python 沿用原任务终态
和未决提交处理规则，收口子进程后才归还资源；不因进程退出自动重做远端提交。

## 平台和能力开放

macOS 与 Oracle Linux 分别构建匹配系统和 CPU 架构的产物；不复制 Windows
二进制到两端使用。需锁定工具链和依赖，验证 BoringSSL/wreq 构建、动态链接、
通信协商、离线契约、取消/崩溃以及原身份恢复。当前两种平台均未构建或验收该项目。

只有来源许可、通信和恢复契约、两端产物及实际注册验收完成后，才增加
`rust / sentinel_rs / registration` 绑定、独立并发策略和可用性检查，并开放配置。
`same_as_registration` 到 Codex 的映射也必须明确声明。Rust 所用语言本身不能
证明注册更快；性能应在相同代理、邮箱和远端条件下分别比较总耗时、成功率与资源消耗。


## 当前实现的进程边界

Python 侧 `core/kernels/rust/sentinel_rs/bridge.py`：

1. 读取本地已分配的邮箱和代理，确认邮箱来源为 `generic_api` 并取得 `code_url`；
2. 在临时目录写一行静态邮箱池 `email----code_url`，以 `register --live --count 1` 启动原生进程；
3. 只把 stdout 映射为阶段进度，stderr 合并后仅保留脱敏尾部诊断；
4. 进程退出后读取临时 SQLite，要求状态 `registered`、邮箱一致且 Access Token 非空；
5. 把 Cookie 装入本地会话、核验会话身份，再交回注册生命周期保存和后处理。

原生进程不接触 Turb 数据库、任务队列、代理池或邮箱分配器；临时目录在退出后删除。
构建与验收步骤见 [sentinel-rs 原生构建](sentinel-rs-build.md)。
