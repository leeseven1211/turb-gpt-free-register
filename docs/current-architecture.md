# 当前项目架构基线

> 基线日期：2026-08-26
>
> 基线提交：`8985fff fix: stretch account table on wide screens`
>
> 本文描述当前已运行代码，不描述历史设计或未来目标。

## 1. 项目定位

本项目是 ChatGPT / OpenAI 账号注册、账号维护和 Codex OAuth 授权工具。运行形态为
一个 Python 单体应用，提供两个入口：

- `main.py`：CLI，支持单任务和批量注册；
- `web.py`：本地 Flask WebUI，负责启动恢复、后台调度和 HTTP 服务。

两种入口共享 `core/` 业务实现和 PostgreSQL 数据库。日常使用以 WebUI 为主。

## 2. 规模基线

| 项目 | 当前值 |
| --- | ---: |
| Git 跟踪的 Python 文件 | 163 |
| Python 总行数 | 60,993 |
| `tests/test_*.py` 模块 | 62 |
| 阶段 0 未修改代码完整测试 | 501 项，66.502 秒，全部通过 |
| 阶段 0 加入路由契约保护后完整测试 | 502 项，65.032 秒，全部通过 |
| 当前阶段 2 完整测试 | 513 项，57.537 秒，全部通过 |
| 当前阶段 3 完整测试 | 514 项，52.337 秒，全部通过 |
| Flask 路由规则 | 96 |

主要大文件：

| 文件 | 行数 | 当前职责 |
| --- | ---: | --- |
| `webui/templates/index.html` | 671 | 现代 UI HTML；CSS/JavaScript 外置到 `webui/static/` |
| `core/roxy_registration.py` | 4,019 | Roxy 注册及大量 Selenium 页面能力 |
| `core/registration/protocol.py` | 456 | 纯协议注册主体和 OAuth 回调收口 |
| `webui/app.py` | 70 | Flask 应用工厂和 Blueprint 装配 |
| `webui/routes/accounts.py` | 1,176 | 账号列表、账号操作、提链和 CPA/Sub2 上传路由 |
| `webui/routes/codex.py` | 611 | Codex 凭证、补跑、下载和停止路由 |
| `webui/routes/jobs.py` | 476 | 注册任务提交、重试、停止和日志路由 |
| `webui/runtime.py` | 266 | WebUI 请求上下文、启动恢复和后台 worker 生命周期 |
| `core/db.py` | 3,589 | 业务数据门面、状态命令和兼容导出接缝 |
| `webui/templates/index_legacy.html` | 322 | 兼容版 UI HTML；CSS/JavaScript 外置到 `webui/static/` |
| `webui/static/js/modern/*.js` | 6,059 | 现代页公共、总览、任务、账号、邮箱、Codex、配置和初始化脚本 |
| `webui/static/js/legacy/*.js` | 2,609 | 兼容页对应业务脚本 |
| `webui/static/css/{modern,legacy,login}.css` | 3,593 | 页面专属 CSS；共享样式仍在 `ui-foundation.css` |
| `core/roxy_codex_oauth.py` | 2,802 | Roxy Codex OAuth 页面流程 |
| `core/operation_task_store.py` | 2,094 | 统一任务中心投影、读写、运行时和迁移 |
| `core/browser_use_registration.py` | 2,089 | Browser Use/Skyvern 注册页面流程 |
| `core/codex_oauth.py` | 1,721 | Codex OAuth 调度与协议实现 |

## 3. 当前调用链

### 3.1 注册

```text
WebUI POST /api/jobs
  -> core.registration_service.submit_registration
  -> ThreadPoolExecutor
  -> core.registration_service._run_one_job
  -> core.registration.dispatcher.run_registration
  -> protocol / roxy / cloak / browser_use / skyvern
  -> 保存账号、收口邮箱和代理、执行 Codex/2FA/套餐后置步骤

CLI main.py
  -> main.run_registration（兼容门面）
  -> core.registration.dispatcher.run_registration
  -> 同一组注册驱动
```

`core` 不再反向导入 CLI 模块；`main.run_registration` 只为已有 CLI/外部调用保留兼容门面。

### 3.2 Codex operation

```text
Web/API/注册后置步骤
  -> core.codex_operation_service
  -> operation_tasks / operation_runs
  -> 账号资源租约和 operation_resources
  -> core.codex_oauth.run_codex_oauth
  -> protocol / roxy / browser_use / skyvern
  -> operation_events 和凭证状态收口
```

Codex 补跑已经使用原生统一任务运行模型；其他账号操作仍主要通过
`account_action_*` 旧写模型，再投影到统一任务中心。

### 3.3 WebUI

`web.py` 负责：

- 参数解析、日志和单实例文件锁；
- PostgreSQL 启动自检；
- 调用 `webui.runtime.start_runtime()`，统一执行注册任务、账号任务、原生 operation、Roxy 环境和业务状态的中断恢复；
- 由 runtime 统一启动 SMS 取消、AT/Codex Token 刷新和封号扫描等后台 worker；
- 运行 Flask 服务并在退出前 flush 兼容导出。

`webui.app.create_app()` 当前只负责：

- 创建 Flask app 和注册鉴权；
- 创建每个请求上下文持有的短期下载缓存和共享 service 依赖；
- 按 `dashboard -> config -> email_pool -> accounts -> jobs -> operations -> codex -> integrations` 注册 Blueprint。

应用工厂不再启动恢复流程或后台 worker；需要进程级资源时只能由显式的
`start_runtime()` 初始化，并且同一进程只执行一次。

## 4. 当前目录职责

| 目录/文件 | 当前职责 |
| --- | --- |
| `config/` | 默认配置、`.env` 覆盖、热重载和历史顶层导出 |
| `core/` | 注册、Codex、账号、邮箱、浏览器、代理、任务和存储 |
| `webui/` | Flask API、鉴权、配置编辑器、现代/兼容版页面 |
| `webui/app.py` | Flask app 工厂和 Blueprint 装配，不承载业务路由 |
| `webui/routes/` | 按领域组织的 Blueprint 路由组，保留原 URL/方法/endpoint |
| `webui/route_helpers.py` | 查询、分页、脱敏和功能可用性共享辅助函数 |
| `webui/runtime.py` | 请求上下文、下载缓存和进程级恢复/worker 生命周期 |
| `webui/static/` | 页面 CSS、普通 JavaScript 和 favicon；不引入构建步骤 |
| `sentinel/` | 纯协议注册使用的 Node.js Sentinel/PoW 运行环境 |
| `tests/` | stdlib `unittest` 单元和 PostgreSQL 集成测试 |
| `tools/` | 数据迁移、协议分析和真实链路调试工具 |
| `docs/` | 当前架构、专项设计、迁移方案和协议分析 |
| `core/registration/` | 注册公共签名、驱动分发和纯协议注册流程 |
| `main.py` | CLI 和 `run_registration` 兼容门面 |
| `web.py` | Web 进程生命周期入口 |

## 5. 数据与存储

PostgreSQL 是唯一事实来源，没有纯文件运行模式。`DATABASE_URL` 缺失或连接失败时，
CLI/WebUI 必须在启动阶段终止。

### 5.1 行级业务表

`core.record_store` 当前管理：

- `registered_accounts`
- `registration_jobs`
- `email_pool_outlook`
- `email_pool_generic_api`
- `email_pool_domain`
- `email_pool_icloud_hide`
- `codex_credentials`
- `proxy_leases`

表采用“查询/排序/抢占字段提升为普通列，其余字段放 `data JSONB`”的混合模型。

### 5.2 任务表

旧账号任务写模型：

- `account_action_batches`
- `account_action_tasks`
- `account_action_events`

统一任务中心：

- `operation_batches`
- `operation_batch_items`
- `operation_tasks`
- `operation_runs`
- `operation_events`
- `operation_resources`
- `account_operation_leases`
- `registration_attempts`

迁移期保留旧写入口，并通过 `operation_task_store` 幂等投影到统一任务中心。

### 5.3 兼容数据

根目录 JSON/TXT、`accounts_viewer.html` 和 `codex_accounts/*.json` 是兼容导出，不是
数据库故障时的回退数据源。兼容导出失败只能记录错误，不能回滚业务数据库写入。

仍应保留在文件系统的运行数据包括：

- `.env`
- `注册日志/`
- `logs/`
- `run/`
- 浏览器和 Sentinel 临时文件
- 对外部消费者提供的兼容导出

## 6. 当前边界问题

1. 现代前端仍是单个 9,642 行模板。
2. `core/` 仍有大量平铺模块，领域包边界还未稳定。
3. Cloak、查活和 Browser Use Codex 等模块直接导入其他驱动的私有函数。
4. `db.py` 和 `operation_task_store.py` 同时承担 schema、命令、查询、兼容和迁移职责。
5. `webui/routes/accounts.py` 和 `webui/routes/codex.py` 仍偏大，后续可在不改变 Blueprint 契约的前提下继续按子领域拆分。
6. `core/mail_password_change.py` 引用仓库内不存在的 `core.mailcom_client`，且没有发现
   其他源码调用方，属于待确认的孤儿兼容模块。
7. 历史专项架构文档中的切换结果和当前实现必须明确标注时间，避免把历史测试数量当成当前基线。
8. 已建立最小 `pyproject.toml` / Ruff 阻断基线，但仓库仍没有可复现依赖锁；更宽的历史 lint 问题暂按 advisory 管理。

## 7. 不可破坏的不变量

- PostgreSQL 始终是唯一事实来源。
- 存储改造必须在独立 worktree 和独立开发数据库完成。
- 生产数据库默认拒绝连接，测试不得使用 `public` schema。
- 启动恢复只允许改变状态，不允许改变业务行数。
- 账号、邮箱、注册任务和凭证 ID 在迁移中保持不变。
- 同一账号同一资源族只能存在一个活跃 operation run。
- 重跑新增 run，不能覆盖历史执行。
- 密码、Token、OTP、Cookie 和带凭据代理不得进入任务事件或普通日志。
- 兼容文件可以延迟或生成失败，但不能影响业务写入成功与否。

## 8. 架构资料优先级

理解当前代码时按以下顺序使用资料：

1. 本文和实际代码；
2. `docs/admin-data-architecture.md`；
3. `docs/unified-task-center-architecture.md`；
4. `docs/codex-operation-architecture.md`；
5. `docs/core-registration-flow.md`；
6. `docs/storage-architecture.md` 中仍与代码一致的设计原则；
7. README/`CLAUDE.md` 中的使用说明。

历史文档出现冲突时，以实际表定义、入口代码和本基线为准。
