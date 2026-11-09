# Turb 合并审计清单

审计日期：2026-11-09（Asia/Shanghai）。本清单仅记录 Git 只读审计；不代表服务已部署。

当前 main：`a24052a177461e411bce0c9c4f429900a1c7286a`。

## 本次已合入

- `3583e0c`：分离邮箱本地删除与原租约退还判定。
- `bc7047b`：查询套餐单次自动刷新 AT 与统一失败诊断。
- `36dc2a2`：整合上述改动。
- `a24052a`：保留旧单国套餐任务的具体失败原因。

## 非祖先本地分支的补丁等价证据

以 `git patch-id --stable` 比较，以下提交补丁已在 main 中，无需再次应用：

| 分支 | 分支提交 | main 对应提交 | stable patch-id |
|---|---|---|---|
| codex/cancel-account-sync | d291c2c | 0f012f6 | `5ddd2fef54092a8bdf01b8ba06f56632bcef289c` |
| codex/candidate-password-recovery | f37383b | ec2ecf1 | `f225e6912397431afbf54583ba6beedae996f50e` |
| codex/fix-email-otp-classification | 3fe86ef | ef31492 | `7c96fa8375be4e91f0c3e600cd01165fb84e37cf` |
| codex/fix-email-otp-classification | 5974325 | a4f20f3 | `2991d728c1b48186c506f38f7761d0ca21aeb7a9` |
| codex/payment-local-reconcile | fe369e9 | 2d47594 | `9941c2529c39118017a2102cc11ff62ec28cfc5f` |
| codex/payment-local-reconcile | 45f5070 | 361fd10 | `a0da42c2099a78ec4957e313c6526a3a894a128f` |

另外 3 个非祖先分支已通过合并后的功能快照核对：

- `codex/roxy-at-traffic`：3 个分支提交的累积 patch-id 与 main `9d951e9` 相同，均为 `7dab80c51019b8c875b660a18e261146d5a69338`。该 main 提交整合点的代码和测试一致；README 另含主线说明更新。
- `codex/xxsyun-yitiaochong`：11 个提交的累积 patch-id 与 main `4d35782` 相同，均为 `a4aaca4f6b9c71283ffd6c879b6f04ab5f169e81`；所涉全部文件在整合提交处完全一致。
- `codex/codex-database-only`：分支 `0e93fe4` 与 main `53c3a47` 的全部业务代码、配置、工具和测试一致。仅 main README 多一条任务取消说明、模板多 accounts 资源版本，均与 Codex 数据库功能无遗漏关系。

当前全部非祖先本地分支：`codex/cancel-account-sync`, `codex/candidate-password-recovery`, `codex/codex-database-only`, `codex/fix-email-otp-classification`, `codex/payment-local-reconcile`, `codex/roxy-at-traffic`, `codex/xxsyun-yitiaochong`。

其余 25 个本地分支均通过 `git merge-base --is-ancestor <分支> main`：

`codex/account-filter-counts`, `codex/butler-import-stop`, `codex/docs-cleanup`, `codex/email-butler-v2`, `codex/email-deletion-evidence`, `codex/email-subaddress-inventory`, `codex/generic-api-subaddress-receipt`, `codex/global-code-layout`, `codex/independent-xxsyun-payment`, `codex/oracle-mail-preparation`, `codex/password-proxy-rotation`, `codex/password-reset-recovery`, `codex/performance-p0-p1`, `codex/plan-check-at-recovery`, `codex/proto2-password-flow`, `codex/push-butler-return-identity`, `codex/readability-round1`, `codex/registration-admission-performance`, `codex/registration-password-contract`, `codex/required-password-recovery`, `codex/runtime-config-db`, `codex/tosub2-account-enhancements`, `codex/turb-service-tags`, `codex/unified-task-concurrency`, `main`。

## 工作树残留

已枚举全部 25 个 Git 工作树，包括 5 个 detached HEAD；未发现 detached 独有未合入提交。以下 4 个旧工作树仍有 tracked 未提交改动，但与 main 已合入补丁对应，原样保留：

| 工作树名 | main 提交 | 精确比较结果 |
|---|---|---|
| email-manual-reset | 57e7f21 | 完整补丁相同，`d68f5504751ca0ec7ddd67f336284c7fd9aaff45` |
| extract-concurrency-50 | 90c6176 | 对应 5 个脏文件补丁相同，`507cf774545e9e5b05b9de881e42e4b629d4488b` |
| password-page-status | 25a6d9c | 对应 2 个脏文件补丁相同，`8344e546c9967ccc33c4364da85c0150111b48fb` |
| password-reset-recovery | d8e3f5f | 完整补丁相同，`50ffee132f3de99e99c97388aa874dd4cdd2ffac` |

本次套餐工作树的改动已通过上述本次提交进入 main；本清单不清理其他会话留下的文件或工作树。

## 历史远端边界

`git ls-remote --heads self` 已核对实际远端与本地 tracking 一致（审计开始时 main 为 9dd4867，后续推送状态由部署步骤核验）。`self/codex/roxy-at-traffic` 与本地同名分支相同，已按累积补丁核对。

`self/deploy/leeseven@ab6bb25` 是 2026-08-14 的历史部署分支，含 12 个非等价提交；不是当前功能分支。其旧 Butler、Cloak、FlareSolverr 和旧路径注册实现已被主线替代，整支合并会恢复退役代码。尤其 `dd66db1` 修改旧 Roxy Cloudflare 挑战等待，`77453d3` 修改旧注册流程及新增旧辅助模块；本次保留历史分支，不复活退役流程。

`origin/*` 属于上游历史分支，不属于用户当前 self/main 功能整合范围，未导入其历史实现。

## 审计与验证结论

当前功能范围内无遗漏的独有代码补丁：真正新增的邮箱删除证据和套餐恢复改动均已合入；其他本地分支为祖先或功能补丁等价。

邮箱删除证据分支此前定向隔离验证：40 passed、45 subtests passed；前端 6 passed；相关 Python 静态检查通过。该记录不代替最终联合回归和本地/Oracle 部署验收。
