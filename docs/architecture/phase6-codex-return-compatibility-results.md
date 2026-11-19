# 第六阶段 Codex 同步返回兼容性结果

日期：2026-11-18。结论：本批 Codex 同步返回修复、五阶段完整联合回归及额外消费者定向回归，已分别取得实际通过结果与限定独审。它们不等于正式发布或部署完成。

## 修复与测试范围

`core/codex/operation_service.py` 仅调整同步 wrapper 的返回字典：实际 `OperationResult.status=request_unknown` 时，公开返回保持旧契约 `status=attention_required`、`ok=false`；其他状态继续取实际回执结果。wrapper 仅直接覆盖对外 status、ok、message、error；context 内的实际 summary 保持权威，不新增公开返回字典的 summary 覆盖。

内部 `OperationResult.request_unknown`、数据库执行与持久状态、`summary.outcome=request_unknown`、`reconcile_required`、人工核验及禁止自动重做的远端语义均不变。

回执权威性测试增强为“回调请求 success，但提交返回 attention_required 的实际回执”：对外 status、ok、message、error 取实际结果，内部 unknown 和实际 summary 则分别在 `context.last_result.status`、`context.last_result.summary` 中验证，防止测试只验证回调原值。

联合回归结束后另应用两项仅测试夹具的修正：OAuth/Sub2API 接入真实结算生命周期；取消阶段测试使用正确的进度事件和结算接缝。两文件不在本轮联合回归的 110 个目标模块或其静态导入中，其结果由后续 fresh22 单独验收，不追溯计入已完成的联合回归。

此前第 15 项 Pending/fence-rejection 场景（`test_sync_finish_fence_rejection_does_not_rewrite_oauth_as_unknown`）在原生 PG 测试中注入 `InsufficientPrivilege`（SQLSTATE 42501），实际验证其导致 `OperationSettlementPending`：故障期间保留原 success intent，Run 仍 running、无提前回执、permit 未释放；移除故障后，对**同一 intent**显式补偿，核对 transition ID、digest、实际 success 和账号凭证读回。OAuth 和上传计数始终各为 1，不重放业务。此例未改变数据库 GRANT/REVOKE 权限。

| 输入 | SHA-256 |
| --- | --- |
| 产品 `core/codex/operation_service.py` | `5de4e50b7507ff712dbd9a116bbc8a7b21faaf2bc030b44d6569cac811f60994` |
| 回执权威测试 `tests/codex/test_settlement_codex.py` | `d720b18391c8c7ef0f89dcb4aa64e6434c7de0abea78ab19165faf63f841ced0` |
| OAuth/Sub2API 夹具 `tests/codex/test_codex_oauth_sub2api.py` | `bc61da607fac09cfb920fc09b968f733c63c4c3891061b216f2be51bf2d0adee` |
| 取消阶段夹具 `tests/operations/test_stage_closure_reporting.py` | `666f4dbae515a8b46947672d8ad842c7c727ce553ca0cae23fc547b16f83af94` |

源输入冻结 `release-v4/source-manifest-root-b5-codex-return-v1.json` SHA 为 `e2c2aad69f62f30f45ad24e7f7e7d6501328dacb03ae806eb5cf1d5372d1f92d`。共482项源输入（466仓库源＋16ART依赖），相对前一发布校验冻结仅上述 Codex 产品文件有一项变化。

## 五阶段完整联合回归

`runtime/final-joint-pg-prepare/root-joint-98c047901729` 为一次实际完整顺序执行，外层及五阶段均 exit 0；父适配器 `budget-v4-parent-23ad97f6be79` 同为 exit 0。

| 阶段 | 独立采集节点 | 原生 PG 节点 | 通过的子测试 |
| --- | ---: | ---: | ---: |
| runtime_tools | 454 | 49 | 179 |
| pg_tool_compatibility | 31 | 30 | 6 |
| settlement_core | 336 | 128 | 104 |
| account_integration | 298 | 120 | 117 |
| codex_extract_legacy | 346 | 68 | 156 |
| 合计 | **1465** | **395** | **562** |

1465 个节点的 setup/call/teardown 全部通过，另有 562 条通过的子测试报告；2027 条 call 报告不算 2027 个独立测试。各阶段 collection/strict 校验无错误、缺项或跳过，未超时。482 项源输入及 694 项递归测试/辅助输入在本轮前后相同；两项额外夹具在本轮结束后才应用，不算运行期漂移。

原始五阶段名单与预算保留，Codex 预算为已批准的 2400 秒，实际运行约 1019.412 秒。新自然 900 秒 cohort 的三个原进程实际 SIGKILL/-9/reap，末次原心跳年龄为 915.427734、907.925555、900.511733 秒。闭合记录 `closed=true/errors=[]`，三个原测试均实际断言原 Run；无业务重放、原资源收口。该 cohort 属本轮新请求，不借用旧轮崩溃通过结果。

独审结论为 **GO：一轮完整五阶段本地合成 PG 联合回归**：

- [完整终态独审](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/review/codex-return-status-proposal-20261118/wholejoint-98c-independent-final-review.md)，SHA `a0b1eb928c078d8987eababcdf4c6f35785473f537228e5cd2b1753f9d2e3241`。
- 原始 `result.json` SHA `a5f559cfe7cb366a71636f149a0d91e9120b5eee6204bdb0107ffc15e018a324`。

## 额外消费者 fresh22

两项夹具按已审字节应用后，`review/codex-return-status-proposal-20261118/root-focused-final-c46e77d61d` 实际 exit 0。独立采集 **22 项测试＋5 个子测试，含 17 项原生 PG 测试**；22 setup、27 call、22 teardown 全通过，无缺失阶段、未知节点、收集拒绝或跳过。

范围为原两个状态失败节点、增强的回执权威节点、15 个 OAuth/Sub2API 节点及 4 个取消阶段节点。482 项源输入和 693 项纯 `tests/` 输入前后不变；联合回归的 694 还含 `tools/test_isolated.py`，两种计数不能互换。

独审结论为 **ACCEPT：精确应用字节与 fresh22**：

- [夹具及 fresh22 独审](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/review/extra-fixtures-applied-byte-review-20261118.md)，SHA `c18eb872bf59e11ec59fd940f03c1aaca3d56c3ed677529b7cc0a7236ce81235`。
- 原始 `result.json` SHA `68e3cafcb5e4aa405408d915f1f772730a1942afb19175425befb2aeb59dbf53`。

## 保留边界

原两状态 RED、权威测试 RED、旧 focused22 整体 exit 1 及其 19 个 extras 失败报告、旧账号和 Codex6387 失败均保留；新结果不改写旧记录。

此前发布包 A→B→A 验收绑定 `bd6f53...` 产品冻结，**不含本次 Codex 修复**；不能将旧包通过作为新修复已打包或部署的证明。Git 正式交付、从最终提交生成正式 release、生产切换及真实业务验收尚未完成。

Oracle 非生产强隔离按用户决定保留待办，本批不实施；50 万 SQL 优化延期以后再议，不开展实验、改写、索引或 50/45 秒 timeout 调整。residual2 仍未关闭，新 local-proxy shared-child 自动释放方案尚未获实施批准。延期和未批准项均不记完成。
