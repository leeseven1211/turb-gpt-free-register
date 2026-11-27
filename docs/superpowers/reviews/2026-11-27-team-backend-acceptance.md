# Team 管理后端验收记录

日期：2026-11-27。工作区：`codex/team-management-backend`，基线 `05ee76a2`。

## 交付范围

已实现绑定探测、工作区配置与更换母号、成员与邀请分页、候选解析、本地预检、持久批量加入、继续与重跑。21 个 HTTP 操作共用 [Team OpenAPI](../../../contracts/teams.openapi.json)，前端使用[生成类型](../../../frontend/src/api/teams-schema.d.ts)独立对接。

账号仍保存在同一份账号记录中，使用 `team_scope` 形成视图。加入待处理不会提前进入 Team 账号视图；归档独立于成员关系。统一任务中心支持精确 `team_id`，父子任务、整批重跑及同一任务的多批次关联均保留历史回执。

新增存储维护单账号业务占用、席位身份并集、全局幂等回执、事务 outbox、执行围栏和工作区独立加密上下文。后台复用现有 Task/Run 网关与启动恢复入口，没有改动注册主流程。本文记录后端阶段；后续已集成 Antigravity 前端，契约修正与浏览器验证见[前后端集成验收](2026-11-27-team-ui-integration.md)。

## 本地验证

测试通过项目隔离入口执行，显式使用 `turb_dev` 与独立 `test_*` schema。测试不连接生产库，不放行生产数据库保护。远端协议使用合成响应验证；真实验收单独记录。

最终组合测试通过：**374 passed，222 subtests passed**，耗时 697.32 秒。范围包括整个 `tests/teams/`、账号 Team 视图、固定名单、Team 任务接缝、错误目录及运行时组合：

```sh
python tools/test_isolated.py --profile all -- \
  tests/teams/ \
  tests/accounts/test_account_team_scope.py \
  tests/bulk/test_team_selection.py \
  tests/operations/test_team_operation_seams.py \
  tests/operations/test_team_error_catalog.py \
  tests/runtime/test_runtime_composition.py -q
```

执行前仅从本机配置提取数据库连接，将目标数据库替换为 `turb_dev`；不加载整份生产配置，不设置生产放行。全部 PostgreSQL 用例由项目隔离工具及 `PostgresTestCase` 管理测试 schema。

新增 Team 模块、HTTP、测试与基准脚本的 ruff 检查通过；OpenAPI 类型和错误短语生成检查通过，Markdown 标题与相对链接检查通过，差异空白检查通过。

独立审查覆盖单 Team 约束、邮箱唯一关联、未知席位、迟到回执、取消与重跑、固定名单消费、预检数组编码及 SQL 分类等价性；所发现的具体问题已逐项修复。最终只读审查没有发现新的 P1/P2。常规批量任务、任务查询及错误目录的相邻回归已在开发期间分组验证；没有运行全项目测试套件。

## 本地预检性能

使用 10,000 个合成目标、一个已确认管理母号及完整空邀请快照，各场景预热 2 次、正式采样 20 次。测量包括输入校验、实际 `service.preview_join`、公开 DTO 投影及 Flask JSON 序列化，不包含 HTTP 传输。全部目标为新增候选，认证能力未知；此数据集不代表大量历史邀请或跨 Team 冲突的最坏情况。

| 目标规模与输入 | P50 | P95 | P95 < 50ms |
| --- | ---: | ---: | --- |
| 10，显式 ID | 11.856ms | 17.477ms | 是 |
| 100，显式 ID | 6.485ms | 9.634ms | 是 |
| 1,000，显式 ID | 9.701ms | 11.884ms | 是 |
| 10,000，显式 ID | 40.967ms | 56.510ms | 否 |
| 10,000，显式 ID 与完整邮箱快照 | 56.403ms | 77.699ms | 否 |

两个 10,000 场景未达到契约的性能目标，保留为未达项；不能以纯 SQL 耗时替代完整接口结果，也没有缩减名单使数据看起来达标。100,000 项固定名单的语义已测试，但未做完整接口性能验收。

已消除邮箱关联相关子查询、逐账号数组适配、邮箱快照名单包含检查的平方复杂度及重复数据库往返。预检现用单 SQL 读取 Team、互斥分类和容量，容量身份并集复用统一实现。此前完整邮箱快照 P95 147.633ms；最后优化后为表中的 77.699ms。

最终测量中源文件摘要不变，业务表行数不变，每次使用只读事务，远端边界调用为零。本机存在负载抖动，结果按实际样本保留。原始结果位于本地忽略目录 `logs/run/diagnostics/team-preview-20261127/`，包含优化前后的 JSON；基准入口为 [team_join_preview.py](../../../tools/benchmarks/team_join_preview.py)。

## 真实单账号验收

用户授权从已有账号中选择一个较早注册的 Roxy iCloud Free 账号。选中账号 `#76`，注册日期为 2026-08-13；管理母号为 `#2376`。邀请前只读确认目标只有个人工作区。

实际发送普通邀请 1 次。后续完整快照读到目标已是成员，Team 为 2 名成员、0 条邀请，目标个人工作区仍存在。实际接受 POST 为 0 次：准备执行接受时目标已经加入，适配层返回已加入复用；导致其加入的具体来源未确认。因此，真实接受 POST 尚未验收，不能把这一结果表述为自动接受接口已完成真实验证。

随后经正式网关走通 `team_join_request` → `team_join` → `team_accept`。成员任务只发送远端 GET，精确核验成员身份，保存 Team 加密认证上下文并解密读回；两个父任务均成功。没有重复发送邀请或接受请求，也没有覆盖个人会话缓存。

参考工作区事实与网关验收数据仅写入 `turb_dev` 的独立测试 schema。生产数据库没有写入此次 Team 记录。脱敏摘要保存在本地忽略目录：

- `logs/run/diagnostics/team-one-member-20261127/acceptance-summary.json`
- `logs/run/diagnostics/team-gateway-20261127/gateway-summary.json`

私有认证材料加密保存于忽略目录，不属于交付文件。

## 发布状态

当前后端和集成修正仍为独立工作区文件修改；未提交、未推送、未合并主分支，未重启或部署本地服务及 Oracle 服务。前端提交 `5f7b9a74` 已合入该工作区；使用真实应用和合成隔离数据库的浏览器验证另见集成验收，部署后的真实流程尚未验收。
