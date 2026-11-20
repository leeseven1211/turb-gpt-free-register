# 认证操作驱动入口整理实施计划

> 执行方式：使用 superpowers:subagent-driven-development 按职责实施并独立审查。用户已确认本轮操作范围和保持行为的边界，无需重复询问。

**目标：** 统一七类操作的静态驱动目录与选择入口，使新增实现不需要重复维护选项。

**架构：** 无初始化副作用的 `contracts` 持有静态事实，`config` 提供兼容出口，`core` 按操作保留解析和执行拥有者；注册增加只绑定执行入口的懒加载 registry。共享数据不共享远端认证状态机。

**技术栈：** 项目 Python 3.10+，protocol-2 继续要求 Python 3.11+；dataclasses、不可变 Mapping、现有 Flask/pytest/PostgreSQL 测试工具。

**设计：** [认证操作驱动入口整理](../specs/2026-11-20-operation-driver-catalog-design.md)

## 全局约束

- 中文文档、注释、日志；禁止 `rm -r`、`rm -rf`。
- 保持配置字段、默认值、选项顺序和标签、已有快照、异常语义与公开兼容入口。
- 不改注册或其他认证的请求、重试、状态、恢复、fallback、资源收口及重跑行为。
- 不新增 Rust、不扩展历史值的实际执行范围、不增加预检或重跑阻断。
- 不读写生产数据库；测试使用统一隔离入口和独立测试 schema。
- 不提交私有数据；完成验证及独审前不提交，不推送、不部署。

## 任务 1：静态目录与配置投影（主代理）

文件：新建 `contracts/__init__.py`、`contracts/operation_drivers.py`、`config/operation_drivers.py`、
`tests/config/test_operation_drivers.py`、`tests/auth/test_driver_import_isolation.py`；修改 `config/schema.py`。

产出设计中的七个目录函数、两个不可变描述类型、协议版本和 AT 兼容映射。目录操作键为 `registration/refresh_at/password_setup/twofa/codex_oauth/live_check/plan_check`。

- [x] 先测试各操作规范选项和专属别名、规范查找不接受历史别名、目录不可变、目录导入不加载可选实现。
- [x] 通过统一隔离入口运行新测试，确认缺少目录而失败。
- [x] 实现目录，从当前 schema 逐字保留选项；schema 只替换选项来源。
- [x] 真实模块名的独立进程覆盖 2FA、查活、Codex 快照及并发分类，确认不提前初始化配置。
- [x] 运行新测试和配置 schema/默认值相关测试。

## 任务 2：注册入口整理

文件：`config/registration_drivers.py`、新建 `core/registration/registry.py`、`core/registration/dispatcher.py`、`core/registration/service.py`、`core/registration/admission.py`、`core/operations/concurrency.py`、`webui/routes/jobs.py` 及直接相关注册测试。

接口：消费目录的注册描述与纯映射；产出懒加载 `resolve_registration_runner(driver)`，返回原 runner 和 entrypoint。

- [x] 沿用现有分发测试，补充懒加载、原参数差异、runner 不缓存及目录与并发类别一致性验证。
- [x] 现有两个 runner、standalone、runtime/lifecycle、检查点、换线与重跑函数保持原实现。
- [x] choices、严格校验、快照密码要求、调试支持、并发类别引用描述。
- [x] 注册后的 Codex 纯映射改用目录函数，保持先执行历史归一化的原顺序。
- [x] 运行直接相关的分发/API/快照/并发测试；交付修改列表和验证命令。

## 任务 3：账号认证选择整理

文件：`config/account.py`、`config/twofa.py`、`core/auth/twofa.py`、`core/auth/protocol/version.py`、`core/accounts/liveness/service.py` 及相关认证/账号测试。

接口：消费操作别名、协议版本能力和 AT 显式版本/内部值映射；旧解析函数的签名不变。

- [x] 保留现有矩阵测试，补操作选择互不影响及无效值兼容的缺口。
- [x] 2FA 只替换选项/别名来源；上下文选择逻辑不改。
- [x] 协议版本只替换静态表来源；环境优先级及单版本操作忽略全局配置的规则不改。
- [x] AT 显式版本选择使用目录映射，旧 gate、告警、快照及 fallback 不改。
- [x] 运行版本、AT 刷新、Roxy 刷新、2FA 的直接相关测试。

## 任务 4：Codex、普通查活与账号补全选择整理

文件：`core/codex/oauth.py`、`core/codex/operation_service.py`、`core/codex/retry_service.py`、`core/accounts/liveness/router.py` 及对应测试。

接口：消费 `registration_codex_driver`、操作规范值和专属别名；保留原执行入口、传参和快照字段。

- [x] Codex 重复注册映射改为纯函数；各入口原始归一化边界不改。
- [x] 普通查活规范集合和别名来自目录，开关、异常、probe 传参及无 fallback 契约不改。
- [x] 账号补全的密码与套餐校验集合来自操作目录；强制动作及执行器判断不改。
- [x] 单独套餐 service 和 Codex refresh grant 不改；只登记已存在的可配置能力。
- [x] 运行 Codex 语义、查活路由、账号补全及密码相关测试。

## 任务 5：集成、文档和独立审查（主代理）

文件：`core/runtime/capabilities.py`、`README.md`、`docs/architecture/current-architecture.md`、本轮设计与计划。

- [x] 运行能力检查复用纯映射和静态描述，保留原历史白名单与返回原始 driver 的行为。
- [x] 文档说明目录与实际执行器各自归属、增加实现的方法和本轮不变的边界。
- [x] 整合各任务后运行受影响测试组、配置与层次检查、`git diff --check`。
- [x] 独立审查参数、默认、别名、快照、缺依赖、分层与业务分支；发现问题按影响修复并定向复验。
- [x] 汇报独立工作区、测试数量及未提交/未推送/未部署事实。
