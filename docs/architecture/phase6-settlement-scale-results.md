# 第六阶段 B 结算队列成本结果

2026-11-18。300k、500k 两档真实 PostgreSQL 队列成本测量均已完成，root 确认进程正常退出、最终结果 `ok=true`，并经独立文件复核。结论限于本轮原生查询成本、跨批推进及数据保护断言；未设延迟 SLO，也不由此推导 mixed 容量、领域 cleanup adapter、业务或部署验收通过。

## 数据形状与方法

300k／500k 指账号数。两档原始历史均为 **200 个 batch、200000 个 Task、400000 个 Run、800000 个 Event**；分别从已验证的原始 fixture 新建专用 clone，没有复用已跑 mixed 的 clone。

每档另用隔离技术身份生成 300000／500000 条 B receipt、cleanup、handoff 历史，cleanup 为 95% done、5% superseded，再增加 65 个当前 case。精确 receipt／cleanup 总数分别为 300065／500065，handoff 为 300033／500033。这些是查询夹具数据，不是数十万次原生终态提交的正确性证明，也没有新增业务 Task／Run。

六组原生查询路径各保存 30 个 wall-clock 样本，每档 180 份；median、nearest-rank p95、min/max 均从原始样本独立重算一致。每档还保存 13 条实际 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`，包含实际行数、loops、timing 与 buffers。原生计时包含连接、多条 SQL、身份及 owner-liveness 路径，不能与单条 SQL 的 EXPLAIN 时间混用。

## 观察到的延迟

原生方法 wall-clock p95，单位毫秒；每格 n=30，四舍五入至三位小数。

| 原生路径 | 300k | 500k |
| --- | ---: | ---: |
| 回执读回 | 4.571 | 3.690 |
| cleanup 阻塞 permit：true | 6.733 | 6.404 |
| cleanup 阻塞 permit：false | 7.266 | 5.988 |
| 已有 handoff 读取 | 5.611 | 4.306 |
| 32 条外进程待办扫描 | 290.014 | 300.216 |
| 精确领取 | 72.088 | 93.858 |

**有限返回批次不代表恒定扫描成本。** foreign scan 虽 `LIMIT 32`，实际 parallel cleanup PK 扫描约过滤 30 万／50 万历史行；500k 的每 loop 显示值经过四舍五入，不能把乘积当作精确扫描总数。精确领取的候选查询分别过滤 15033／25033 行：现有 partial index 包含 superseded 历史，而候选只接受 pending／过期 claimed。最后 PK CAS 的 EXPLAIN 仅 0.149／0.154 ms，不能省略前置查询而只引用该值。

500k 候选查询和全局扫描出现较多 Shared Read Blocks，300k 相应计划主要为 buffer hit；两次顺序测量没有控制缓存，不构成因果或扩展曲线实验。结果没有人为延迟阈值，不能称 O(32)、恒定开销或普遍性能达标。扫描、索引优化尚未批准，本轮未实施优化。

## 历史保护与收尾

两档均完整重读原五表固定列及历史 ID 范围，最终 canonical SHA、精确行数、max_id 与 clone 收据和原 fixture manifest 三方一致；不是抽样。五个历史写保护 trigger、cluster／database／schema／clone marker 和捕获 domain 起止一致。

原 resource、account lease、execution permit、permit scope 四表前后完整内容 hash 与行数逐表相等，均为 0。两个技术 probe permit 仅按精确身份、已释放条件删除后再比较；这不表示技术 B 队列清空，每档仍保留 **34 条 query-only pending**，target 不能交给真实 runtime／mixed scanner，也不能再次作为 pristine 测量输入。

实际 carrier 在测量时存活并正常退出。32 个 foreign job 无 handoff，state／attempts／token／until 保持原值；第一批未领取而推进 cursor，下一批成功领取后方 eligible job。每档正式领取并由夹具精确完成 31 个 job，其中 30 个用于计时；callback、remote call、typed cleanup action 均为 0。

capture 与逐条 EXPLAIN（含唯一 exact claim UPDATE）绑定 `force_rollback=True`；最终状态净变化恰与 31 次正式完成一致。该回滚证据来自绑定事务实现及精确聚合一致性，没有另行导出 PostgreSQL transaction log。关系大小中的 `reltuples` 是估计；500k receipt 的估计 500068 不改变前后精确 `count(*)=500065`。

## 冻结与 mixed 证据边界

本轮两档起止均绑定[最新 v2 冻结清单](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/faults/source-manifest-final-root-b5-release-bootstrap-v2.json)，精确 SHA256 为 `8511387c4656d6139853f9c02362ca798ea74db9ca0bd5486e541094be92444c`，482 项；独审时当前源码逐项零漂移，fixture/helper 与 harness pin 一致。清单仍为 `acceptance_complete=false`，冻结本身不代表第六阶段完成。

此前 [500k combined mixed v15](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/mixed-500k-combined-v15-b5/result.json) 与 [split mixed v15](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/mixed-500k-split-v15-b5/result.json) 绑定原 B5 冻结 `cddbdf098e1c601316b2d4e3eb94dcaeb8fe86930ade62694ba030b0fea9ebd7`，是另一套真实入口及混载观察。其原契约仍是每读取接口 mixed＋终态后只读补样合计至少 30 份，两 phase 的样本和延迟分列，补样不计 mixed RPS；没有改成 mixed 本身至少 30。更早 v13 补样预算耗尽的失败继续保留，不能由后续结果改写。

旧 B5 上的 [queue 漂移预检失败](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/queue-cost-b5-drift-probe-20261118.json) 因 bootstrap／release 源码已变化而在连接数据库、创建输出前拒绝执行。它不是运行后的成本失败，也不撤销旧 mixed 的历史结果；本轮使用新冻结及新 clone 独立测量，保留该失败记录。

## 原始证据

- 300k：[clone 收据](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/clone-300k-root-queue-v2-20261118.json)、[最终结果及原始样本／执行计划](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/measure-300k-root-queue-v2-20261118/result.json)、[完整进度](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/measure-300k-root-queue-v2-20261118/progress.json)、[独立审查](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/measure-300k-independent-review-20261118.md)。
- 500k：[clone 收据](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/clone-500k-root-queue-v2-20261118.json)、[最终结果及原始样本／执行计划](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/measure-500k-root-queue-v2-20261118/result.json)、[完整进度](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/measure-500k-root-queue-v2-20261118/progress.json)、[独立审查及两档详细对比](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/scale_cost/measure-500k-independent-review-20261118.md)。

本页补记两档队列成本门槛的完成事实；[此前预部署记录](phase6-predeployment.md)中的历史状态、其他边界验证、最终联合回归及实际产品目标验收各自保留。Git 交付、生产切换和部署没有因本轮成本测量而自动完成。
