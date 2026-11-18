# 代理原租约被动对账结果

2026-11-18。**用户批准的[简化被动对账方案](phase6-proxy-passive-reconciliation-plan.md)已完成实现，存储定向、三个真实进程窗口及受影响整组均已实际通过；源码与测试独审无阻断，最终证据独审已对本批实际执行范围给出 scoped ACCEPT。** 以下通过仅限本批列明范围，不宣布全项目、完整 residual2 或投产验收完成。

## 本批范围

领取时从原 live handle 冻结代理 child、pool resource/anchor、原始领取/到期时间及原 Task/Run/execution 身份；关联只保存技术标识，不含代理地址或凭据，同时进入 operation resource 与收尾义务。

仅明确使用进程内协议客户端的路径声明 `owner_process`。已证明原 owner 进程退出，且原 child 已归还（含现有冷却状态）或达到原到期时间时，存储被动确认对应 operation resource，继续使用原清理任务与 permit gate 收口。该过程不主动归还代理，不改 child、pool、anchor、TTL、冷却或共享策略，不重放业务。

同代已提交终态回执走原 `resource_release` 清理；原孤儿恢复 disposition 沿用原身份与资源确认协议。两种路径分别验收，不能以已提交终态回执的进程试验代替无回执孤儿恢复整链。

## 当前验收状态

| 验收层 | 当前记录 |
| --- | --- |
| 关联生成与调用侧声明 | 已实现，资源与义务使用同一原始快照；源码与测试独审无阻断，最终证据独审已限定 ACCEPT |
| PostgreSQL 定向存储 | `storage-final-green-v3`实际 exit0，15项测试＋38个子测试通过，36.05秒，源码零漂移；范围包括精确身份、自然到期、原归还、活跃 owner、旧数据、外部 actor、共享新代、事务失败及确认丢失 |
| 真实进程故障 | `process-green-v2`实际 exit0，3项通过，36.05秒，源码零漂移；三原进程各正式SIGKILL/-9/reap、三replacement与三successor均正常exit0/reap，共九进程；三组owned-cleanup均closed，原permit/resource/cleanup无残留 |
| 受影响整组 | `adjacent-green-v2`实际 exit0，436项测试＋80个子测试通过，211.83秒，源码零漂移；这是受影响范围，不能替代全项目回归 |
| 最终证据独审 | 本批实际执行范围 scoped ACCEPT；当前515项源输入逐项匹配，测试、进程身份及原始结果绑定无差异 |
| root 最终只读审计 | 已保存14个 PID/start 均退出、两个已知测试 schema 均不存在、其他活跃 PG 查询为0、515项输入零漂移；这是当时只读观察，不替代原生精确资源收尾 |

真实进程试验限定三个已提交终态回执的窗口：原 child 归还提交后资源尚未确认；原 child 未归还时死亡并等待初始短合成租约自然到期；资源确认已落库而清理任务尚未确认。第三种不称 SQL ACK 丢失；没有改写到期时间、模拟 owner 退出或伪造清理完成，也不重复等待或宣称测试了自然 900 秒无回执恢复。

同池后继另有真实存活进程、独立 Task/Run/permit 和共享 child。短到期场景中两个 child 继承同一 anchor 的到期时间，保护判据是存活 owner 的责任与共享池快照不被误改，不能称后继租约始终有效；其他共享与新 anchor 边界由对应 SQL 场景分别证明。

首轮`process-green-v1`保留 exit1、1失败/1通过：`child_released`在正式kill前被旧夹具“只允许acquired”的断言阻挡，实际终态已按原行为标为`reconciliation_required`。该失败例仅有清理fallback kill，不算正式验收kill。v2仅修夹具对未released状态的判断，并补齐失败时原ticket/回执排空与schema保护，不修改产品绕过断言；旧夹具基线及各轮失败记录全部保留，不因后续通过改标。

原始结果位于[本批工件](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/review/proxy-passive-reconciliation-20261118)：`storage-final-green-v3.json/.log`、`process-green-v2.json/.log`、`process-v2/`及`adjacent-green-v2.json/.log`分别保存，各组存在重叠，计数不相加。当前[源输入冻结](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/review/proxy-passive-reconciliation-20261118/source-manifest-proxy-passive-v1.json)含515项源输入，SHA `03995864364dd330cad47c4de0fbef4608e5b68af9e87271313bc395d33b0bfd`；相对父冻结仅6项既有产品差异并新增2个helper，其余包含测试与ART依赖，不能称515个产品文件。冻结不等于完整验收通过。

[最终证据独审](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/review/proxy-passive-reconciliation-20261118/final-evidence-independent-review.md) SHA为`e6f431242c4f8c02d3e3615bce4cc97ef6bf59294f7ef080507f593e3f9f312e`。[root只读审计](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/review/proxy-passive-reconciliation-20261118/final-owned-audit.json) SHA为`fb49d4a51da37e661a5947b0f9735bdde346f90f515a7fe794a0b11f7f6e9c9b`，没有访问生产或执行清理。process-v2三格保存的owned-cleanup均精确闭合；旧v1失败格没有正式gate kill及已保存的精确资源排空，后来schema不存在不能倒补其permit已释放的证据。

## 保守边界与未完成项

历史缺关联、身份或执行代不匹配、child 缺失、独立浏览器／Roxy／未知外部 actor，以及 defer 后执行代变化，继续待核验，不推断原 actor 已停或扩大自动释放。已确认远端不确定结果仍保留人工核验语义。

本批只实现获批的简化被动关联与对账，**不等于全 residual2、全 K05、完整故障矩阵或投产门槛已关闭**。保守保留场景若需新增行为，继续先讨论范围。

既有 Codex、联合回归与 defer 四格结果保留各自冻结及独审范围，不自动外推到本批改动。Oracle 非生产强隔离和 50 万 SQL 优化仍按用户决定延期；Git 正式交付、最终提交的正式包、生产切换和真实业务验收未执行。总进度见[当前收口结果](phase6-current-closeout-20261118.md)。
