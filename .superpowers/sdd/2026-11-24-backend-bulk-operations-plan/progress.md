# SDD ledger — plan: docs/superpowers/plans/2026-11-24-backend-bulk-operations-plan.md

## Preflight conflict scan

| Task | Shared file/interface | Finding | Ruling |
|---|---|---|---|
| 1 ↔ 2 | `core/operations/bulk_mutations.py` outputs consumed by `core/operations/bulk_mutation_worker.py` | Task 2 depends on Task 1 types and executor | Task 1 completes before Task 2 starts |
| 2 ↔ 7 | `core/runtime/assembly.py` | Worker registration and readiness recovery both touch assembly | Task 2 first; Task 7 follows all domain tasks |
| 3 ↔ 4 | API routes are separate; shared contract only | No source-file conflict | Parallel after Task 2 |
| 3 ↔ 5 | API routes/storage modules are separate | No source-file conflict | Parallel after Task 2 |
| 4 ↔ 6 | Codex routes and operations/jobs routes are separate | No source-file conflict | Parallel after Task 2 |
| 5 ↔ 6 | Email route/storage and operations/jobs route/storage are separate | No source-file conflict | Parallel after Task 2 |
| 6 ↔ 7 | Operation runtime/readiness and route contracts | Task 7 validates and documents Task 6 | Task 6 completes before Task 7 |
| 1 | `tests/operations/test_bulk_mutations.py` against new contract | Self-consistent | Implement TDD |
| 2 | Worker tests require runtime registration from Task 1 | Self-consistent after dependency | Implement TDD |
| 3 | Account tests exercise new storage and route compatibility | Self-consistent | Implement TDD |
| 4 | Codex tests exercise filename collection writes | Self-consistent | Implement TDD |
| 5 | Email tests exercise safety rules and chunk boundaries | Self-consistent | Implement TDD |
| 6 | Operations/registration tests preserve protected execution paths | Self-consistent | Implement TDD |
| 7 | Recovery/contract tests consume all prior task outputs | Self-consistent | Run last |

Ruling: domain tasks 3–6 may run in parallel only after Tasks 1–2 establish the shared command/worker interfaces; they must not edit each other's files. This keeps the user's requested parallel development while avoiding shared-file races.

## Task status

- Task 1: complete
- Task 2: complete; b6c8d84d → b2e3d286 → 98ffd02f，30 tests；独立复审 Spec/Quality Approved。技术异常重试、确定性错误终态、完整/脱敏回执、跨 Run 原子恢复均已验证。
- Task 3: complete; 724c2ef2 + 625c9819，42 tests / 33 subtests；独立复审 Approved，保留完整输入/duplicate/invalid/409。
- Task 4: complete; 78f02cab，24 tests；集合存储复审通过，HTTP 冲突映射已由 Task 7 集成并在跨域组合复验。
- Task 5: complete; 8e5ac289 + 915e746b，59 tests / 51 subtests；墓碑重放租约说明已修，导入/读取扩展另列。
- Task 6: complete; 7ee24978 + a3dd26e0 + f396902a，79 tests / 88 subtests；多 Run 覆盖审查意见因唯一索引证明撤回，未制造无效 schema 修复。
- Task 7: complete; 1b1c26ea + 6e5d67c2，75 tests / 25 subtests；Web metadata 与 Worker callback 分离、分页/bigint/409、真实 settlement 与重启恢复（模拟退出）已验证。
- UI receipt integration: complete; cfee3e59 + 33355d6f + 7ea9bcf1，119 tests + typecheck；终态、分页、查询失败命令引用与cause保留。隔离 Chromium 真实点击确认1 POST+3 GET、成功清选/跳过保留、bigint命令ID完整。
- Configuration collection save: implemented; 739d9b27，35 tests / 9 subtests；501 个字段的历史/当前值写入由 1002 SQL 降为 2 SQL，整份事务不变。

## 全按钮遗漏覆盖补充（2026-11-24）

原 7 项计划不足以覆盖设计中的“批量任务创建”和所有轻量集合读取。用户明确要求“所有”，因此继续完成以下已授权的本地数据库与受理路径；第三方执行仍复用原 handler。

| 补充范围 | Owner | 共享边界与验证 |
|---|---|---|
| 账号 setup/action/complete/live/AT/plan/C2A、Sub2 路由及 secret/session/CPA 集合读写 | impl_accounts_bulk | 先完成新 `core/storage/operations/bulk_submission.py:create_specs(..., conn=...)`；不修改注册驱动 |
| Codex OAuth refresh、重授权、Sub2 上传/选中停止的集合受理 | impl_codex_bulk | 复用共享 create_specs；自有凭证/账号集合预取；远端 handler 不变 |
| 提链支付入口读取、同步原单、新批次创建、批次取消 | survey_extract_bulk 与子 agents | 普通创建复用 create_specs；同步 Run 和 ProviderJob 私有快照同事务；不触发付款 |
| 邮箱 secret、粘贴导入、Butler 导入意图/完成事实、单条兼容服务复用 | impl_email_bulk | 本地集合 SQL；远端领取/校验和及时保存租约证据保持原语义 |
| 注册提交/重跑与任务控制剩余本地受理事实 | impl_operation_facts | 先报告最小方案；精确选中 Run；不改驱动步骤/请求/超时/租约 |

并行约束：所有 agent 仅 stage 自有文件并追加 commit，不 amend。`runtime.py` 不由多个域同时编辑；普通 Task/Run/Event 创建在共享新模块实现。账号/Codex/提链的资格规则和私有快照仍由各域服务负责，共享存储函数只保存集合事实。

## 验证环境

所有新增 PostgreSQL 测试使用隔离测试库和临时 schema，通过主 checkout 的 Python 3.12 `.venv` 执行 `tools/test_isolated.py --profile all`。禁止把全部 skipped 当通过；不调用真实注册或第三方写入。当前无 push、merge、部署或线上数据库迁移。

Task 1: minor (deferred): BulkMutationResult 深层不可变、Mapping 类型和位置参数兼容性可在全链路使用后再收紧；当前无调用者依赖。
Task 1: minor (deferred): 当前报告没有保存 TDD Step 2 失败输出；实现测试已通过，流程证据不完整。
Task 1: minor (deferred): max_targets 当前按去重后有效目标计数；后续接口层需明确原始输入上限语义。
Task 1: complete (commits 142ade5..21e8e5c, review clean with 3 parked minors)
Task 2 base: 21e8e5cd24e629e97fe31eea40467f7f579a727c
Task 3-6 base: b842436df0cf8e2aef1ad22e0d3e47378de03f3c

## 全站覆盖收尾

完整按钮源索引归档提交 `a0dec812`，目录为 `docs/reports/backend-bulk-button-inventory/`；实施矩阵与最终验证记录分别为 `docs/reports/2026-11-24-backend-bulk-coverage.md`、`docs/reports/2026-11-24-backend-bulk-validation.md`。历史报告保留原时点，不改写成当前源码状态。

追加范围已覆盖普通任务受理之外的父链、注册后处理与历史投影、任务中心特殊 handler、提链 managed 原单、取消和持久终止、邮箱删除的安全快照及 return intent、C2A/Sub2 monitor。运行中强制终止仍由原安全结算逐 Run 处理，普通本地变更保持块内业务事实与回执同事务。

主 agent 跨域 23 文件组合通过 231 tests / 76 subtests；前端完整门通过 92 files / 1,099 tests，生成契约、类型、标签及构建均通过。Sentinel 最终组通过 53 tests / 3 subtests，提交 `25e5e3ba` 并独立复核。

当前最后整合项为混合来源重试的统一选择顺序：原生任务、历史账号任务、历史 Codex OAuth refresh、注册后处理按真实账号及资源族统一资格和集合受理。该项的最终提交与测试追加至公开验证记录；在其通过前，不宣称全站实施完成。原 Task 1 缺失的历史失败输出仍按上述说明保留，不用后续 GREEN 测试补造。
