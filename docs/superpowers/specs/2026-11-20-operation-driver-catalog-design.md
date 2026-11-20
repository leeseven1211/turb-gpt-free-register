# 认证操作驱动入口整理

## 已确认范围

用户确认一起整理注册、刷新 AT、密码、2FA、Codex、普通查活和查套餐的驱动登记与选择。目标是让后续实现有明确接入位置，并使不同操作的别名、默认值和能力互不串用。本轮不接入 Rust。

## 结构

- `contracts/operation_drivers.py` 保存不可变、无运行副作用的操作驱动目录、中文选项、操作专属历史别名和协议版本能力。它只依赖标准库，不导入配置加载器或 `core`。`contracts/__init__.py` 无初始化逻辑；`config/operation_drivers.py` 显式重导出同一组对象，避免复制事实。
- 原本可独立使用的核心纯入口直接依赖契约目录，不能因导入 `config` 包提前运行配置加载器。
- `config/schema.py` 继续拥有配置字段、默认值和校验规则，从驱动目录取得已有选项；选项的顺序、标签和值完全保持。
- `config/registration_drivers.py` 保留原公开常量、归一化函数和历史别名语义，转用统一目录。
- `core/registration/registry.py` 只把注册 canonical ID 绑定到模块、函数和 CLI 入口，按调用懒加载，不缓存函数对象。新实现必须明确接入自己的可用性检查，登记目录本身不继承 Roxy 的配置要求或自动变为可用。
- 账号认证、普通查活、2FA、协议版本和 Codex 的原解析函数继续作为操作专属入口。纯选项、别名、注册到 Codex 的映射引用统一目录；配置读取、快照选择、异常、兜底和日志仍由原入口负责。
- 原有任务、存储、邮箱、代理、并发策略和后处理服务继续持有其职责。目录只引用并发类别，不保存另一套额度或调度规则。

## 目录接口

`DriverDefinition(value, label)` 描述一种公开选项；`RegistrationDriverDefinition` 额外声明说明、并发类别、固有密码要求、调试支持、注册后 Codex 对应值及 `browser_required`。

- `operation_driver_definitions(operation)` 返回操作的不可变选项元组。
- `operation_driver_options(operation)` 返回供 schema 使用的 `(value, label)` 元组。
- `operation_driver_values(operation, include_aliases=False)` 返回规范值，只有调用方明确要求才包含该操作的历史别名。
- `operation_driver_aliases(operation)` 返回只属于该操作的不可变别名表。
- `get_operation_driver(operation, value)` 只查规范值，不隐式归一化。
- `registration_codex_driver(value)` 只执行原有注册到 Codex 的纯映射，不扩大调用方接受的历史别名。
- 协议版本选项、操作版本能力矩阵、AT 显式版本别名和内部版本映射各自独立，不将协议版本混成注册驱动。

## 行为保持边界

1. 注册请求顺序、页面操作、重试、超时、状态机、检查点、原任务重跑和后处理执行函数不改。
2. 配置和历史任务允许的注册别名与新 API 的严格 canonical 校验继续分开；历史任务不迁移。
3. Roxy 未显式传 options 时不新增参数；protocol-2 继续注入其原有密码选项。CLI entrypoint、异常文案和 monkeypatch 路径保持。
4. Codex 各入口原有归一化范围并不完全相同。共享纯映射不修正这些差异，不让旧不支持值获得执行能力。
5. AT 未知选择继续告警并回落 v1；旧字面 `protocol_v2` 的兼容开关保留。邮箱失效时的升级和浏览器 fallback 保留原位置。
6. 查活的浏览器开关、只验证旧 AT 的契约和无 fallback 语义保持。
7. 2FA 的 `auto` 是上下文选择策略；强制换 2FA、强制改密码及各类 fallback 保持原业务语义。
8. 单独查套餐原先不校验驱动值，不增加校验；套餐补全原有 `protocol/api/http` 校验保持。
9. Codex Token 刷新和邮箱换绑没有可选驱动，本轮不新增选项或改变实现。
10. 不新增预检、重跑拦截、人工核对、环境全局补丁或跨驱动依赖。

## 验证和交付

先验证目录跨操作隔离、不可变性、懒加载和既有选择矩阵；复用配置、注册分发、AT 版本、2FA、账号配置、Codex、查活及运行能力的直接相关测试。通过统一隔离入口连接本机独立测试库，每组使用独立测试 schema。

独立审查重点是参数等价、旧值兼容、无新增业务执行分支及缺失可选依赖的隔离。README 与现行架构文档同步描述扩展位置。此次不部署、不重启、不推送，不运行真实认证；提交前先完成验证和审查。
