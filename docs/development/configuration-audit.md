# 配置核查记录

本轮于 2026-10-16 按 schema、模块常量、运行时调用、配置 API、前端、示例和文档核查全部
235 个唯一可编辑字段。调整后保留 233 个字段，将原 15 个配置分组映射为 9 个主菜单；
schema 的领域分组继续用于字段归属。现有 `.env` 和任务配置快照不在清理范围内。

## 删除与去重

| 项目 | 处理与依据 |
|---|---|
| `CLOUDFLARE_PATH_DOMAINS` | 删除字段、模块导出和示例。Cloudflare 客户端没有域名列表请求；域名通过 `CLOUDFLARE_DEFAULT_DOMAINS` 指定，留空时由 Worker 决定。 |
| `CLOUDFLARE_PATH_TOKEN` | 删除字段、模块导出和示例。创建邮箱直接取得响应中的 `jwt` / `token`，没有单独获取 Token 的调用；该字段仅为预留。 |
| Codex Token 自动刷新 | 移除两个字段在「Codex」与「定时任务」间的重复展示；六个 `CODEX_TOKEN_*` 配置统一归入「系统设置 → 定时任务」，每项只展示一次。 |
| `PLAN_CHECK_WORKERS` / `PLAN_CHECK_QUEUE_LIMIT` | 从新配置示例移除，保留模块常量和历史环境变量兼容。它们已退出任务调度，持久账号任务使用 `ACCOUNT_BATCH_WORKERS`。 |
| Roxy API 默认端口 | schema 帮助、模块说明及示例统一为本项目的 `50100`，与实际默认值一致；连接时仍须以 Roxy 应用配置为准。 |

Cloudflare 的调用证据位于 [cloudflare/client.py](../../core/email/cloudflare/client.py) 的
`_default_domains()`、`_next_domain()` 和 `create_address()`。本次只删除没有执行路径的
预留字段，不删除 Cloudflare 邮箱来源或创建、收信与封号扫描能力。

## 菜单归属

| 主菜单 | 包含内容 | 字段数 |
|---|---|---:|
| 注册设置 | 注册主链路、注册调试 | 20 |
| 账号补全 | 补全能力、执行驱动、认证策略 | 22 |
| 浏览器设置 | RoxyBrowser、浏览器画像、人工节奏 | 37 |
| 邮箱 / OTP | 通用邮箱规则与各邮箱服务 | 55 |
| 接码平台 | 通用接码、GrizzlySMS、H 接码、L 接码 | 17 |
| 代理与网络 | 注册线路、账号动作线路、供应商、静态池与库存策略 | 47 |
| Codex | OAuth 基础配置、CPA、sub2api | 9 |
| 提链 | 提链服务与请求参数 | 6 |
| 系统设置 | 通用并发、网站配置、定时任务、任务中心 | 20 |

原配置分组入口和浏览器保存的停留位置映射到对应新菜单，保留配置键搜索、未保存状态、
保存与热加载行为。菜单只影响编辑入口；CLI、WebUI 和后台任务继续消费相同配置契约。
`REGISTER_NAME` 归入注册主链路；手动注册邮箱 `REGISTER_EMAIL` 继续保留在通用邮箱设置。

## 保留的兼容配置

含「旧版」或「兼容」不代表没有用途，仍有运行时调用的配置继续保留：

- `PLAN_CHECK_PROXY_MODE` / `PLAN_CHECK_PROXY` 仍供直接套餐查询入口使用。
- `ACCOUNT_ACTION_PROXY_MODE` / `ACCOUNT_ACTION_PROXY` 仍参与历史配置回退与静态线路选择。
- `PROXY_1024_ROTATE_SESSION_TIME` / `PROXY_1024_MAX_ATTEMPTS` 等参数仍被供应商诊断入口消费，
  正常库存补货采用独立策略。它们不能作为每次取得新 IP 的保证。
- `ACCOUNT_TOKEN_REFRESH_DRIVER`、`ACCOUNT_AUTH_V2_ENABLED` 和旧 sub2api 键保持历史读取兼容，
  不重新加入配置页。
- `PLAN_CHECK_MIN_INTERVAL` / `PLAN_CHECK_JITTER` 仍控制套餐查询节奏，不能随旧队列参数一起删除。

代码依据分别见 [accounts/plans/client.py](../../core/accounts/plans/client.py)、
[proxy/account_routes.py](../../core/proxy/account_routes.py)、[proxy/provider.py](../../core/proxy/provider.py)、
[accounts/plans/service.py](../../core/accounts/plans/service.py) 和
[config/schema.py](../../config/schema.py) 的 `LEGACY_ENV_OVERRIDE_TYPES`。

## 验证范围

配置契约检查覆盖字段唯一性、模块默认值、`.env.example` 覆盖、保存校验、热加载和已退役参数
的兼容边界；界面检查覆盖菜单归属、旧入口映射、搜索与未保存值。测试须通过统一隔离入口，
使用独立测试库，不读取生产账号与密钥。

```bash
python tools/test_isolated.py --profile all -- tests/config/test_config_schema.py tests/config/test_config_defaults.py tests/config/test_config_runtime_contract.py tests/config/test_config_ui.py -q
python tools/test_isolated.py --profile all -- tests/email/test_cf_temp_mail_client.py tests/webui/test_dashboard_api.py -q
```

静态契约测试不能替代浏览器验收。菜单切换、字段搜索、未保存值在切换后的保留，以及桌面和
窄屏滚动需在真实页面验证；实际测试与服务状态在任务交付时分别报告。通用规则见
[发布与验证](release-verification.md)。

本轮验收使用独立 `turb_test` 数据库与隔离 schema：250 项测试、954 个子测试通过，
另有 1 项总览静态契约测试失败。已比对修改前的 HEAD，失败来自既有的批次进度 CSS 和
`stages.length` 旧断言，与配置修改无关；本次不改动总览流程。配置导航的 7 项 Node 行为测试通过。
桌面与 375px 窄屏使用默认配置的独立页面验收：233 项逐一搜索均能找到对应控件，跨菜单修改、
统一保存和刷新回显通过，保存栏遮挡末尾菜单的问题已修复。未更改实际 `.env`，未重启生产服务。
