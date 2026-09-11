# 代理来源与提供商路由设计

## 目标

将注册代理、静态代理池和代理平台统一为“代理与网络”配置域，并允许补密码、补 2FA、查套餐、查活、刷新 AT、Codex OAuth 分别选择线路来源。低风险只读动作默认直连，高风险认证动作默认沿用注册线路。

## 行为契约

账号动作代理来源使用统一值：

- `registration`：跟随注册代理来源。
- `direct`：直连。
- `pool`：使用静态代理池或动作固定代理。
- `provider:<id>`：使用已注册的代理提供商，例如 `provider:1024proxy`。

旧值 `1024`、`1024proxy`、`platform` 和 `none` 继续兼容，并分别归一化为 `provider:1024proxy` 或 `direct`。旧的 `ACCOUNT_ACTION_PROXY_MODE` 继续作为没有动作级配置时的回退。

动作级默认值：

| 动作 | 配置 | 默认 |
| --- | --- | --- |
| 补密码 | `ACCOUNT_PASSWORD_PROXY_MODE` | `registration` |
| 补 2FA | `ACCOUNT_2FA_PROXY_MODE` | `registration` |
| 查套餐 | `ACCOUNT_PLAN_CHECK_PROXY_MODE` | `direct` |
| 查活 | `ACCOUNT_LIVE_CHECK_PROXY_MODE` | `direct` |
| 刷新 AT | `ACCOUNT_REFRESH_AT_PROXY_MODE` | `registration` |
| Codex OAuth | `ACCOUNT_CODEX_PROXY_MODE` | `registration` |

## 提供商边界

`core/account_proxy.py` 负责动作路由和来源解析，`core/proxy_provider.py` 继续负责 1024Proxy 的具体租约实现。来源解析内置 `direct`、`static_pool`，代理提供商注册表当前内置 `1024proxy`；现有 1024 获取函数保持兼容，避免一次重写整个租约实现。新的平台通过 `provider:<id>` 进入统一接口，暂未实现的平台返回明确的配置错误，不回退到其他平台或直连。

## 执行与释放

- 查套餐和查活各自按自己的动作配置申请线路；默认直连时不创建 1024 租约。
- 账号补全任务包含多个步骤时，查套餐使用套餐线路；后续密码/2FA 浏览器或协议步骤使用密码线路或 2FA 线路，并在步骤边界释放前一条租约。
- 只保留一个需要浏览器的账号配置阶段线路；如果任务同时需要补密码和 2FA，密码线路优先，因为浏览器会话由密码步骤主导。
- 刷新 AT 和 Codex OAuth 在各自服务入口按动作配置获取线路。
- 失败、取消和正常完成都沿用现有 `release()` 语义。

## WebUI

现代配置页新增一级导航“代理与网络”，二级页签为“注册线路”“账号动作线路”“代理提供商”“静态代理池”。字段的后端 `group` 统一为“代理与网络”，二级归属由字段 key 在前端决定。旧版配置页也使用同一个一级分组，并按二级页签显示字段，保留已有邮箱、短信和 Codex 分组行为。

## 兼容与验证

- 旧 `.env` 不增加动作级字段时，密码、2FA、刷新 AT 和 Codex 保持原来的账号动作策略；查套餐和查活的新默认直连只在新配置缺失时生效。
- 配置热加载仍由现有 `config.reload_all()` 负责；所有新字段加入 `config/account.py`、`config/__init__.py`、WebUI 白名单、`.env.example` 和 README。
- 测试覆盖来源归一化、动作路由、直连不申请租约、旧配置回退、组合补全的分步线路，以及现代配置字段分组。
