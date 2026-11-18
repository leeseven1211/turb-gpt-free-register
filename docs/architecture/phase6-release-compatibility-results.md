# Phase 6 发布兼容性结果

2026-11-18。用户本批批准的三项发布兼容工作已完成实现、离线验证和隔离空业务 A→B→A 进程验收。实际运行通过的范围是：从固定 release 启动独立 Worker/Web，核对版本与进程身份，正常停止，再切换和回退。下述结果不代表生产部署完成。

## 三项实现

| 批准范围 | 实现与验证 |
| --- | --- |
| 保留前端 accounts 源码 | 发布过滤只为 `frontend/src/features/accounts` 增加 `.ts/.vue/.css` 例外，继续排除私有目录、环境文件和运行数据；两个实际候选包各保留 47 份该目录源码。 |
| 固定 release 的可信版本身份 | bootstrap 优先使用完整 manifest、文件清单、哈希和依赖锁检查返回的 commit；损坏或非普通 manifest 标记失败即停止，不回退 Git。无 manifest 的开发目录必须匹配真实 Git 根目录。 |
| 外置运行环境及 manager 配置 | 新增 systemd/launchd 配置渲染器，绑定固定 release 和包外解释器，保留 venv 的 `bin/python` 调用路径，禁止字节码写入，拒绝包内输出和不支持的路径；渲染器不安装或操作服务。 |

调用方法、路径约束和回退要求见[固定 release 与外置 Python 运行环境](../deployment/release-external-runtime.md)。

## 已核验证据

| 检查 | 结果 |
| --- | --- |
| 离线单元与回归测试 | **85 passed，3 subtests passed，4.58 秒**；覆盖 renderer、release、bootstrap、角色模板、launcher 和依赖锁检查。相关 ruff 与 diff-check 通过。 |
| 外置依赖环境 | CPython 3.12.13；53 项运行锁版本与运行记录、已安装 `dist-info/METADATA` 一致，`pip check` 记录无冲突。 |
| 实际候选包 | A：1592 文件；B：1593 文件；各有 47 份 accounts 源码。运行后完整文件集合、大小和 SHA256 均与各自 manifest 一致。 |
| 实际三阶段 | A→B→A；Worker generation 为 1→2→3，每阶段 Worker ready、Web HTTP 200 且 `body.ok=true`，PID、启动时间、cwd、release 与实际 plist 参数一致。 |
| 停止与回收 | 六份原始退出凭据均 `clean=true/exit_code=0`，六个自有子进程全部回收且返回 0；每阶段先停 Web，再停 Worker。 |
| 业务空态 | 初始十表均不存在；初始化后最终十表实际 `count(*)` 全为 0，缺表不会当作 0。 |
| 原生保护 | 非 localhost 外连探针返回 `EPERM`，真实 localhost 连接成功；A、B、外置 venv 三处写探针均被拒绝。真实 `ps` 字节副本以 `0755` 运行，身份查询成功。 |

十表为：`registered_accounts`、`operation_tasks`、`operation_runs`、`operation_events`、`operation_resources`、`account_operation_leases`、`operation_execution_permits`、`operation_settlement_cleanup`、`operation_settlement_receipts`、`operation_settlement_handoffs`。此计数不包含配置和 owner 等元数据表。

通过运行是 `root-release-processes-v2-da7ff73655`，上海时间 2026-11-18 01:37:44 至 01:38:11，耗时 27.680 秒。独立复核的 93 项文件及字段一致性检查全部通过；`result.json` SHA256 为 `03ebf9d5eea1921589966c7ab2c5308a7cdac5e2ee519618ed239819fd58fd44`。

## 保留的两次失败

| 运行 | 原始结果与后续修正 |
| --- | --- |
| `root-release-processes-v2-74f0de89e9` | 保持 FAIL：`worker_exited_before_ready`，Worker 身份采集失败，退出 1 并已回收。夹具改用与系统 `/bin/ps` 字节完全相同、去掉 setuid 的包外副本；产品身份检查及网络限制保留。 |
| `root-release-processes-v2-3b2a960b67` | 保持 FAIL：`NameError`，阶段结果为空，两个子进程退出 0 并已回收。修复验收脚本中局部变量 `http` 遮蔽模块的问题；正常退出不把该次失败改为通过。 |

修正后使用全新隔离 schema 和输出目录完成第三次运行，前两次原始结果未改标。

## 结论边界

本次 `manager_installed=false`、`business_submissions=0`。实际执行的是渲染后的 manager 参数和环境，由夹具持有的前台进程完成验收；没有安装 launchd，也不覆盖其 KeepAlive、Throttle 或原生 manager 重启行为。网络与禁写探针结论适用于受 sandbox 保护的产品子进程和原生探针。

准备阶段的临时 Git 仓库只产生 **synthetic 验收 commit**，不等于共享工作区已提交、推送或交付。A/B 唯一内容差异是验收身份标记，因此证明发布身份、切换和回退流程，不能扩为不同业务代码或数据库迁移回退兼容性。

本批未执行真实账号业务、远端 API 验收、本地生产切换或 Oracle 部署。正式交付仍须基于审核后的精确提交和目标主机独立证据。

## 原始记录与独立审查

- [离线最终审查：85 tests 与 3 subtests](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/release-v4/renderer-final-review-20261118.md)
- [实际通过运行原始结果](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/release-v4/root-release-processes-v2-da7ff73655/result.json)
- [最终进程结果独立复核](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/release-v4/release-process-final-results-review-20261118.md)
- [真实 ps 夹具复审](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/release-v4/release-process-review-v4-ps-fixture-20261118.md)
- [HTTP 变量作用域修复复审](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/release-v4/release-process-review-v5-http-scope-20261118.md)

## 2026-11-18 manifest 校验补充收口

整体源审查发现并按既有授权修复两项边界：显式`--release-dir`在manifest缺失、目录或悬空链接时必须完整检查并失败，不降级为源码锁检查；实际文件集合只排除根manifest，嵌套同名文件照常校验。ART同八例实际RED为7失败/1通过，提案GREEN为8通过；正式应用后六模块相关回归为**93 passed、3 subtests passed（5.14秒）**，原85测试记录保留其修订。root另记录本轮8个修改路径的ruff通过、定向`git diff --check`退出0；这不等于全仓库lint。

新源码清单`source-manifest-root-b5-release-checker-postfix-v1.json` SHA`bd6f53d6e43da5d56bdb0400524ba3165d8af2c6450457e251c7c52221a89682`仅变更原482项中的`tools/release.py`，旧8511清单保留。新prepare`root-bundle-preparation-v2-4c071aedad`实际成功：A1599文件、B1600文件，各保留47份accounts源码，仍是临时syntheticGit身份。

新进程轮`root-release-processes-v2-bb328c0233`已由root确认session33246 exit0，原result`ok=true`：三阶段A/B/A、六自有进程ready/cleanexit0/reaped，53锁与pipcheck、三处写拒绝、外网errno1/loopback0、十表真实count0和完整bundle树不变。新轮已获整链限定独审通过，报告为[发布清单补丁及新包结果独审](/Users/lihongwei/.codex/visualizations/2026/11/13/01a1d26e-ed39-7171-a004-18b3e981d0c6/phase6-settlement-b-20261117/review/release-manifest-minimal-fix-independent-review-20261118.md)。本批三项发布兼容工作及两项 manifest 校验收尾已完成所述隔离验证。继续保持`manager_installed=false`、`business_submissions=0`，不扩为不同业务代码或DB迁移兼容、真实manager安装、workspaceGit交付或生产部署。
