# 配置 schema 与生效边界

## 单一事实来源

`config/schema.py` 拥有 WebUI 可编辑字段的完整定义：字段 key、模块文件、类型、
默认值、范围、选项、别名、secret 标记、是否需要重启以及热编辑策略。
`config.CONFIG_SCHEMA`（别名 `config.schema.CONFIG_SCHEMA`）是运行时 registry。

配置模块只通过 `schema_default(KEY)` 声明兼容常量，并通过
`config.env_loader.apply_env_overrides(globals())` 读取环境覆盖。WebUI 的
`EDITABLE_FIELDS` 和前端 `<select>`/数值范围元数据均由 schema 投影生成；旧的
AST helper 仅为直接调用它的兼容测试保留，配置读 API 不解析 `config/*.py` 源码。

`.env.example` 中保留数据库等不可编辑的运行配置；可编辑字段由
`config.schema.render_env_example_section()` 生成。字段定义新增时，应同步确认
示例文件覆盖该 key，但不要把真实 token、邮箱池、代理凭证或 `.env` 内容写入 git。

## 读取与保存

`GET /api/config` 的 `value`、`source`（`default` 或 `env`）和
`config_revision` 始终指向已发布的 effective snapshot。当前 `.env`/环境解析结果
单独放在 `configured_value`、`configured_source`、`configured_source_key` 和
`pending_reload`；因此外部环境
在未 reload 时不会被误报成已生效。另有 `published_effective_value`、
`published_effective_source`、`published_revision` 这组显式字段供新调用方使用。
secret 字段的两组 value 永远为空，只返回是否配置和来源状态。

`POST /api/config` 先对整批候选值做 schema 校验（未知字段、类型、范围、选项和
跨字段约束）；全部通过后才更新 `.env`。写盘或 reload 任一步失败会恢复原 `.env`
和本次触碰的环境键，失败响应不会报告已应用。`config.reload_all()` 还会恢复已
reload 模块的 namespace；环境恢复按“当前值仍等于本次操作期望值”执行，不清空整个
`os.environ`，以免覆盖并发线程的无关变量。

`WEBUI_AUTH_CODE`、`WEBUI_SESSION_SECRET`、`PLAN_CHECK_WORKERS` 和
`PLAN_CHECK_QUEUE_LIMIT` 标记为 restart 策略；其余字段按 schema 的 `hot_edit` 元数据
报告为 safe。账号动作代理字段仍分别保存和路由，不能用一个全局代理覆盖注册、密码、
2FA、查活、刷新 AT、套餐或 Codex OAuth 的差异。

## 任务快照 API

任务在开始时应调用：

```python
from config import non_sensitive_snapshot

snapshot = non_sensitive_snapshot()
```

返回类型为 `config.schema.ConfigSnapshot`，稳定结构如下：

```text
ConfigSnapshot(
    revision: int,
    values: Mapping[str, scalar | tuple],
    sources: Mapping[str, "default" | "env"],
)
```

`values` 不含任何 secret key（包括可能带认证信息的 `PROXY_POOL`）；`sources` 只包含
`default`/`env` 这种非敏感来源元数据。外层是只读 mapping，列表值已冻结为 tuple，
不能通过快照对象修改配置。可用 `snapshot[key]`、`snapshot.get(key)`、
`snapshot.as_dict()` 和 `snapshot.sources` 读取。`revision` 与 `values` 属于同一个
不可变对象版本。reload 前会先离线解析、严格校验并构建候选快照，只有全部兼容模块
成功后才一次性替换已发布引用，因此新任务不会在发布点拿到“新 revision + 旧 values”。

这项保证只覆盖 snapshot API。历史代码若直接读取 `mod.CONSTANT`，仍可能在逐模块
reload 的窗口观察到不同模块的不同版本；迁移边界是把一次业务操作中需要一致的字段
改为开始时抓取一个 snapshot，并从该 snapshot 读取。`from config import CONSTANT`
和 `from config.module import CONSTANT` 的旧绑定也不会自动变成 snapshot 读取。

当 `PYTHON_DOTENV_DISABLED=1` 时，`config.env_loader.load_env()` 在导入
python-dotenv 或执行内置 parser 前直接返回，不读取 `.env`；隔离测试 runner 可据此
避免把生产 dotenv 带入测试进程。
