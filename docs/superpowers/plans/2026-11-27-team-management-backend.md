# Team 管理后端实施计划

> **供执行代理：** 使用 `superpowers:subagent-driven-development` 逐项实施并审查；本计划的开发已获用户授权，不再询问执行方式。

**目标：** 按 v1 契约交付可独立对接前端的 Team 存储、HTTP、持久任务和账号查询扩展。

**架构：** Team 事实保存在 PostgreSQL，通过现有 Task/Run 网关执行认证和远端操作。事务 outbox 保证绑定、固定加入目标和后续任务能够在重启后继续。前端由 Antigravity 在其他工作区开发。

**技术栈：** Python、Flask、psycopg、PostgreSQL、现有任务网关、pytest。

**依据：** [业务设计](../specs/2026-11-27-team-management-design.md)、[HTTP 契约](../specs/2026-11-27-team-management-api-contract.md)。

## 全局约束

- 工作区为 `codex/team-management-backend`，不覆盖主目录的其他修改。
- 禁止递归删除文件、连接生产库执行开发测试、改动注册主流程。
- 测试使用 `turb_dev`，存储用例继承 `PostgresTestCase`，每类独立临时 schema。
- 本地 ID 对外使用字符串；缺失事实返回 null；已购席位 0 不回退。
- 归档独立于 Team 关系；单账号只主动归属一个本地 Team，历史事实完整保留。
- 不自动补 Codex，不覆盖个人会话，不购买席位。
- 不推送、不部署，不把模拟通过表述成真实邀请验收。

## 任务 1：领域规则与服务协调

文件：`core/teams/domain.py`、`errors.py`、`service.py`；`tests/teams/test_domain.py`、`test_service.py`。

接口：HTTP 调用模块级服务函数；服务通过 `repository.transaction()`、全局请求回执和 outbox 事务协调写入。

- [x] 先增加七个互斥分类、零席位、缺少上限、未知完整性和净新增人数用例并确认失败。
- [x] 实现纯本地分类、容量计算和窄 DTO，不读取远端或凭据。
- [x] 先增加持久幂等、同键跨路径冲突和配置版本用例并确认失败。
- [x] 实现 service 写事务；先查询原回执，再检查 Probe、配置及名单版本。
- [x] 验证 preview 无写入，HTTP 受理只持久化名单、父任务及 outbox。

## 任务 2：PostgreSQL 事实与并发约束

文件：`core/storage/teams/`；`tests/teams/test_storage*.py`。

接口：模块级仓储函数接受可选 `conn`，Team、Probe、邀请、请求返回 raw dict；`get_account_states` 集合查询窄字段。

- [x] 先写绑定与首同步 outbox 原子性、重复 workspace、跨 Team 并发占用测试。
- [x] 实现窄表、唯一约束、部分索引和事务封装。
- [x] 先写完整/不完整快照、席位并集、同意图重跑及旧管理身份回执测试。
- [x] 实现同步事实、容量预留、执行围栏、工作区会话和恢复 outbox。
- [x] 运行存储定向测试，检查 schema 与查询索引。

## 任务 3：HTTP 与机器契约

文件：`webui/routes/teams.py`、`webui/app.py`、`core/teams/validation.py`、`contracts/teams.openapi.json`；`tests/teams/test_http*.py`。

接口：调用服务层，无远端调用；新端点统一 `{ok,request_id,data/error}`。

- [x] 先写路由、未知字段、ID、枚举、分页及双源幂等键测试。
- [x] 实现所有已冻结端点的验证、响应与认证兼容。
- [x] 补齐请求、响应、状态枚举和错误 Schema。
- [x] 对照 Markdown 契约核对端点与 DTO。

## 任务 4：账号视图与固定名单

文件：账号查询/仓储、bulk catalog/adapters、`core/teams/selection.py`；对应定向测试。

接口：`read_team_selection(selection_id,selection_revision,team_id,for_consumption=False,conn=None)` 返回固定 ID 和邮箱快照。

- [x] 先写 team_scope 去重、归档兼容、joined 与 pending 区分测试。
- [x] 贯通账号读取、状态、facets 与 query selection，补窄 `team_memberships`。
- [x] 注册 `team_join` v1 及 `parameters.team_id`，固定目标后不重新执行筛选。
- [x] 验证跨操作、跨 Team、过期和修订不匹配；原子消费名单。

## 任务 5：统一任务过滤、重跑和错误

文件：operations query/store/schema、HTTP、既有 OpenAPI、错误目录；对应定向测试。

- [x] 先写精确 team_id 列表、total、facets 和同名目标不误匹配测试。
- [x] 新增可索引 Team 关联，贯通查询，保持既有响应与分页上限。
- [x] 向原生 retry handler 传递幂等键，兼容旧 handler。
- [x] 登记全部 Team 原因码与中文短语，生成错误目录。

## 任务 6：远端适配、持久执行与恢复

文件：`core/teams/remote.py`、`execution.py`、runtime 注册；`tests/teams/test_remote*.py`、`test_execution*.py`。

接口：远端适配提供 discover、snapshot、invite、accept、verify_member；outbox 与子任务通过现有网关执行。

- [x] 从现有源码与已授权浏览器只读取证，记录真实接口能力。
- [x] 先写分页、身份/工作区校验、未知计数与错误分类测试。
- [x] 实现有证据的远端适配；未核实的能力明确返回分类错误，不假成功。
- [x] 先写父任务窗口受理、母号/成员独立认证、断点恢复与取消测试。
- [x] 实现 Probe、同步和加入阶段；复用认证锁、并发策略与启动恢复。
- [x] 验证未知回执保留占用、同 Team 重跑复用，远端 joined 与本地保存分别记录。

## 任务 7：集成与交付

- [x] 汇总所有定向测试并检查相邻接口回归，不默认跑全套。
- [x] 独立审查单 Team 并发、事务幂等、恢复与费用边界，修复具体问题。
- [x] 检查 Markdown 相对链接、JSON/OpenAPI、空白及私有数据。
- [x] 更新 README 和开发记录，明确真实流程尚未验收的能力。
- [x] 汇报本地文件、测试、提交、推送、部署及真实验证各自状态。

## 交付结果

最终组合验证为 374 passed、222 subtests passed；详见[后端验收记录](../reviews/2026-11-27-team-backend-acceptance.md)。1 万目标的两个预检场景仍未达到 P95 小于 50ms，真实接受 POST 尚未验收；保留这两项边界，不把功能实现等同于性能与真实链路全部达标。当前未提交、推送、合并或部署。
