# 发布与验证

> 本文维护现行验证规则；单次测试结果、性能数字和部署回执通过 Git 历史追溯。

## 1. 验证范围

代码改动先运行受影响功能的定向测试，再补相邻回归。小改动不默认执行全量；共享存储、
运行时、迁移、跨模块契约或发布验收需要扩大验证时，应说明具体风险和新增覆盖范围。
涉及 PostgreSQL 行为时补充对应的隔离数据库验证。涉及 WebUI 时，还要验证现代界面及
真实浏览器行为；旧 `?ui=legacy` 链接和 `ui_mode=legacy` Cookie 均返回现代页面，入口
路由修改应保留这两项兼容检查。文档改动检查标题、相对链接、重复内容和现行代码引用。

统一测试入口是 `python tools/test_isolated.py`，由它启动 pytest 并收集已有的
`unittest.TestCase`。运行前在进程环境提供独立测试库的 `DATABASE_URL`；入口会禁用项目
dotenv、清除业务环境配置并探测测试库。`TURB_DB_SCHEMA` 必须以 `test_` 开头，未指定时
由入口生成。profile 只决定 marker 筛选，不代替测试路径：

| profile | 实际选择 | 适用范围 |
|---|---|---|
| `default` | `not extended`，只选非扩展测试 | 日常基础回归，包含保留在默认集中的关键数据库契约 |
| `extended` | `extended`，只选扩展测试 | 按风险补充低频回归；不包含 default |
| `all` | 不添加 marker 筛选 | 对指定路径同时运行普通与扩展测试 |

三个 profile 都保留调用者指定的文件、目录、用例节点以及 `-k` 等 pytest 筛选条件。
例如 `all -- tests/config/test_config_ui.py` 只验证该文件；不指定路径时，pytest 按项目配置从
`tests/` 收集，只有此时 `all` 才覆盖整个测试目录。profile 不与 pytest `-m`/`--markexpr`
混用。

```bash
# 功能定向及相邻回归；文件应按本次影响范围选择
python tools/test_isolated.py --profile all -- tests/config/test_config_ui.py tests/webui/test_dashboard_api.py -q

# 需要更广基础回归时
python tools/test_isolated.py --profile default -- -q

# 路由契约变更时补充对应扩展测试
python tools/test_isolated.py --profile extended -- tests/webui/test_route_contract.py -q

# 已说明需要完整发布验收时，才运行整个测试目录
python tools/test_isolated.py --profile all -- -q
```

测试进程不得连接生产库、不得使用 `public` schema，也不能依赖 `.env`、账号、Token 或
运行日志作为测试输入。若隔离数据库不可用，应报告验证未执行或失败，不能把 skip 说成
通过。已有测试数量多不是删除依据；先确认其保护的行为、是否重复和耗时来源，再决定
合并重复检查、缩小 fixture 或调整测试分组，保留关键业务与数据安全约束。

## 2. 提交与发布前检查

```text
最小相关测试
  -> 相邻回归/相关隔离测试
  -> 有风险依据时补充扩展或全量验证
  -> git diff --check
  -> 检查暂存范围不含私有数据
  -> 确认提交与远端推送状态
```

提交、推送、部署和服务重启是独立事实：本地提交不代表已推送，推送不代表进程已加载新
代码，进程启动也不代表数据库和 worker 已就绪。未被请求的操作不得隐含执行。

验证结果记录实际命令、profile、所选路径、通过/失败/跳过数量及耗时；扩大范围时附上
原因。指定路径的 `--profile all` 不能写成“项目全量通过”。相关检查通过后，仅在新增
修改、失败或仍有未覆盖风险时重复或扩大测试。

## 3. 服务运行时验收

当任务明确要求启动、重启或部署时，依次核对：

1. 实际进程 PID、工作目录和监听端口；
2. PostgreSQL 可用性及启动日志；
3. `GET /healthz` 的 liveness；
4. `GET /readyz` 的数据库和 runtime 就绪；
5. `GET /login` 或相关页面/API 的真实响应；
6. 涉及 UI 的现代界面交互和浏览器控制台结果；入口路由变更另核对旧链接与 Cookie 均返回现代页面。

`/healthz` 通过不等于 `/readyz` 通过。若 supervisor 自动拉起旧进程，必须确认它加载的
工作目录和代码版本，不能仅依据启动脚本输出声明成功。

## 4. 数据与日志安全

验证输出只保留排障必要字段并脱敏。不得提交或展示 `.env`、账号、Token、Cookie、OTP、
完整代理、邮箱池、`logs/`、`accounts/` 或 `codex_accounts/` 内容。兼容文件的
存在或生成成功不能替代 PostgreSQL 行级数据的正确性。

可重复的服务切换、配置迁移及回滚步骤见[部署与维护](../deployment/operations.md)。
