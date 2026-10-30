# 运行配置迁入 PostgreSQL

用户已确认将运行配置迁库，`.env` 保留启动配置及稳定部署身份；按本设计直接实施，不重复索取批准。

## 目标与边界

保留 DATABASE_URL、TURB_ALLOW_PRODUCTION_DB、WEBUI_AUTH_CODE、WEBUI_SESSION_SECRET、TURB_MAIL_CONSUMER_ID；TURB_DB_SCHEMA、TURB_DB_POOL_MAX、本机日志和 Node 路径及已有特殊任务 schema 覆盖按需保留。增加 TURB_CONFIG_ENCRYPTION_KEY，保存 Fernet 主密钥，不进数据库。HOST/PORT 等 shell 启动参数仍由服务环境或 CLI 管理。所有原运行参数和历史 EMAIL_DERIVATION_*_SECRET_* 引用原值迁库，不改变注册执行行为。

## 数据模型与接口

core/runtime_config_store.py：独立 runtime_config_values、runtime_config_meta、runtime_config_history 表。所有原始字符串都加密保存，避免未知历史密钥漏标；历史保存密文，不记录明文。meta 记录 active 与单调 revision。只保存显式值，默认值继续由 schema 拥有。

仓库接口：read_values(*, conn=None) -> dict[str,str] | None（未激活返回 None；激活后缺密钥/解密失败/数据库失败抛脱敏异常）；transaction() 为跨进程 advisory 锁保护的连接事务；ensure_tables(conn)；write_values(updates, *, conn=None, activate=False, source='webui') -> list[str]；current_revision(*,conn=None) -> int。transaction 内嵌套 read/write 必须共用同一连接，可使用 ContextVar。write_values 不覆盖无关键，记录变更历史；相同值不重复版本。

config/runtime.py：保留键集合 BOOTSTRAP_KEYS；is_bootstrap_key(key)；database_enabled()；load_values(*, force=False)；read_persisted_values()；write_persisted_values(updates)；管理缓存及数据库值注入进程环境。该 facade 延迟导入仓库，bootstrap 已加载后再连接，禁止 import 循环。PYTHON_DOTENV_DISABLED 的隔离测试默认不自动连库；测试显式调用仓库，或用受控临时.env子进程测试真正启动。

config/env_loader.py 保留读写 .env 的物理 API，但 load_env 激活后只从文件加载 bootstrap，运行值从数据库加载到内存并投影环境，兼容原 getenv 调用。配置页、动态收码密钥的持久化写入必须经过 facade 分流，不再把运行参数写回 .env。数据库 active 存在却丢密钥不得回退。

## 原子性

WebUI 批量修改先基于同一候选严格校验；数据库写与 reload 共用事务。失败恢复数据库、环境、模块常量和已发布快照；bootstrap 文件保持原值或精确恢复。旧任务持有原不可变快照。GET 不暴露任何敏感值。配置 metadata 反映 database/env 存储与来源。

## 迁移

tools/migrate_runtime_config.py 提供 --source-root、--dry-run、--apply。dry-run 不建表、不生成密钥、不改文件。apply 持文件锁与数据库锁，先以0600备份.env，并持久化加密主密钥，再写库、全量核对读取结果，激活后才原子精简.env。保留原身份与既有 bootstrap。已存在不同数据库值禁止用旧文件覆盖，重复迁移幂等。未知.env键保守分类，不能无声丢弃。仅输出数量、键名与错误类别，不输出值或连接信息。崩溃后可重放完成文件精简，密钥与备份可恢复。迁移只在服务停止、确认无进行中的工作时应用，生产操作前完整备份数据库。

## 验证

非生产库独立 schema，覆盖密文无明文、错误主密钥、缺密钥、事务回滚、并发不丢更改、幂等迁移、历史凭据引用、加载优先级、空值与列表、配置页保存和失败回滚、任务快照稳定。真正受控启动与浏览器配置页验收，不触发注册或第三方业务请求。迁移前后比较全部显式值及有效配置，最终核查服务 health/readiness/login。
