# Oracle B5 sandbox 网络护栏分析

日期：2026-11-18（Asia/Shanghai）
范围：仅分析一次失败的 B5 非生产 sandbox 运行与目标主机只读能力；没有重跑、没有修改产品、没有修改生产服务/数据库/配置。

## 结论

本次失败不是产品启动失败，也不是生产影响。真实 Oracle 运行在启动 Web/Worker 之前，网络 probe 因 `sandbox_network_deny_not_enforced` 中止；应用没有启动。此前所有前置检查通过，生产 combined 的 PID、start ticks、工作目录和 active/running 状态前后未变。

目标主机的 systemd 构建直接解释了这个结果：

```text
systemd 255 (255.4-1ubuntu8.16)
... -BPF_FRAMEWORK ... default-hierarchy=unified
```

只读能力同时显示 `cgroup2fs`、unified cgroup controllers 和 `/sys/fs/bpf` 存在，但 systemd 本身没有编译 BPF framework。目标机本地 `man systemd.resource-control` 对 `IPAddressAllow=`/`IPAddressDeny=` 的说明写明：这些设置依赖底层内核或容器管理器提供 eBPF cgroup 支持；不支持时设置不生效，不能单独作为 IP 安全边界。当前证据因此支持“目标 systemd 构建不具备该护栏的可验收条件”，不支持声称该服务的 IP deny 已工作。

失败运行 `root-run-5079fda704234d29` 的 probe 只保留了断言失败，没有记录 `connect_ex` 返回值；所以不能把当次具体结果进一步写成 `0`、`ETIMEDOUT`、`ENETUNREACH` 或其他 errno。后续若获批准修夹具，应先让 probe 原样记录返回码和异常类别，再决定产品是否启动。

## 实际证据

- 运行结果：`root-run-5079fda704234d29/driver-result.json`，`accepted=false`。
- 失败点：`root-run-5079fda704234d29/evidence/probe.stderr.log`，`AssertionError: sandbox_network_deny_not_enforced`。
- 生产身份前后：`driver-result.json` 中 PID `346314`、start ticks `1877794365`、cwd `/srv/apps/turb-gpt-free-register`，保持一致。
- 运行前资源、B5 源包哈希、53 项依赖、PG 镜像和限额、源 HEAD 元数据均通过；没有启动实际 Web/Worker。
- 清理实际删除了独立 PG、临时 unit 和其 cgroup；`docker container ls --all --filter id=<exact-id>` 为空。`cleanup_complete=false` 另有一个仅影响证据判定的大小写匹配问题：Docker 返回 `error: no such object: <id>`，driver 只匹配大写 `No such object`。

## 三个方案

### A：保留当前 EPERM/EACCES 硬条件

继续要求 TEST-NET 连接必须返回 `EPERM` 或 `EACCES`，否则在启动应用前失败。

优点是边界最强、判定清楚。缺点是当前 Oracle 目标的 `-BPF_FRAMEWORK` 永远无法满足，B5 sandbox 无法在该主机上完成；即使应用自身配置无问题，也会被平台能力阻断。A 适合把“只有系统确认支持 cgroup BPF 才可运行”的平台门槛写进部署要求。

### B：改为“目标地址不可达 + 自身 PG 回环可达”，并记录 errno 分类（推荐用于当前目标）

把 probe 改成记录 `connect_ex` 数值、`errno.errorcode`、超时和异常类型；将外部 TEST-NET 的结果分类为：

- `EPERM`/`EACCES`：IP deny 规则生效；
- `ENETUNREACH`/`EHOSTUNREACH`/明确超时：目标网络不可达，但不能证明是 systemd IP deny；
- `0`/`ECONNREFUSED`/其他可达性结果：外部目标未被可靠隔离，继续拒绝启动。

在当前主机上，这只能证明“外部测试目的地未形成可用业务连接，并且自身 PG 回环可达”；不能把 `ENETUNREACH` 或超时宣称为 systemd deny。运行报告必须明确 `IPAddressDeny` 是 unsupported/未验证状态。B 可用于非生产平台兼容性验收，但若投产安全要求是强制禁止外连，仍需额外平台隔离门槛。

### C：把网络边界迁移到独立 network namespace / 主机防火墙

使用目标平台已启用且可验证的 network namespace、iptables/nftables 或等效主机级策略，在 namespace 级禁止外部访问，仅允许 loopback 和 PG 连接，再启动产品。

优点是可以提供独立于 systemd BPF framework 的硬边界。缺点是会显著扩大部署权限、配置、回滚、审计和宿主机网络变更范围；当前阶段没有这项授权，也不应为了修复一次 sandbox 护栏失败直接改 Oracle 主机网络。

## 建议顺序

1. 先按 B 修正 probe 的诊断字段和 driver 的大小写匹配，保留本次失败证据，不重跑覆盖。
2. 重新讨论是否接受“只能证明目标不可达、不能证明 systemd deny”的非生产验收口径。若不接受，选择 A，明确要求带 `+BPF_FRAMEWORK` 的 systemd/兼容平台。
3. 只有明确需要强网络隔离并完成平台方案评审后，才另立 C 的改造清单；C 不属于本次 sandbox 的自动修复。

本文件不构成投产或生产部署通过。当前 B5 非生产 sandbox 结论仍是 `accepted=false`。
