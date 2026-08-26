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
| Git 跟踪的 Python 文件 | 158 |
| Python 总行数 | 60,790 |
| `tests/test_*.py` 模块 | 60 |
| 未修改代码完整测试 | 501 项，66.502 秒，全部通过 |
| 加入路由契约保护后完整测试 | 502 项，65.032 秒，全部通过 |
| Flask 路由规则 | 96 |

主要大文件：

| 文件 | 行数 | 当前职责 |
| --- | ---: | --- |
| `webui/templates/index.html` | 9,642 | 现代 UI 的 HTML、CSS、JavaScript |
| `core/roxy_registration.py` | 4,019 | Roxy 注册及大量 Selenium 页面能力 |
| `webui/app.py` | 3,612 | Flask 应用工厂和全部业务路由 |
| `core/db.py` | 3,589 | 业务数据门面、状态命令和兼容导出接缝 |
| `webui/templates/index_legacy.html` | 3,279 | 兼容版 UI |
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
  -> main.run_registration
  -> protocol / roxy / cloak / browser_use / skyvern
  -> 保存账号、收口邮箱和代理、执行 Codex/2FA/套餐后置步骤

CLI main.py
  -> main.run_registration
  -> 同一组注册驱动
```

当前最明显的分层倒置是 `core.registration_service` 反向导入 CLI 模块
`main.run_registration`。这是第一项需要解除的结构依赖。

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
- 注册任务、账号任务、原生 operation 和 Roxy 环境的中断恢复；
- 启动 Token 刷新、封号扫描等周期任务；
- 运行 Flask 服务并在退出前 flush 兼容导出。

`webui.app.create_app()` 当前同时负责：

- 创建 Flask app 和注册鉴权；
- 启动 SMS 取消 worker；
- 恢复套餐、提链、查活状态并执行历史字段回填；
- 注册全部页面和 API 路由；
- 部分下载缓存和业务辅助逻辑。

应用工厂并非纯工厂，测试创建 app 时也会触发部分启动恢复逻辑。

## 4. 当前目录职责

| 目录/文件 | 当前职责 |
| --- | --- |
| `config/` | 默认配置、`.env` 覆盖、热重载和历史顶层导出 |
| `core/` | 注册、Codex、账号、邮箱、浏览器、代理、任务和存储 |
| `webui/` | Flask API、鉴权、配置编辑器、现代/兼容版页面 |
| `sentinel/` | 纯协议注册使用的 Node.js Sentinel/PoW 运行环境 |
| `tests/` | stdlib `unittest` 单元和 PostgreSQL 集成测试 |
| `tools/` | 数据迁移、协议分析和真实链路调试工具 |
| `docs/` | 当前架构、专项设计、迁移方案和协议分析 |
| `main.py` | CLI，以及当前仍放在入口中的注册分发/协议主体 |
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

1. `core` 反向依赖 `main.py`。
2. `webui/app.py` 集中了 96 条 Flask 路由规则中的绝大部分。
3. 现代前端仍是单个 9,642 行模板。
4. `core/` 有 68 个平铺模块，没有稳定领域包边界。
5. Cloak、查活和 Browser Use Codex 等模块直接导入其他驱动的私有函数。
6. `db.py` 和 `operation_task_store.py` 同时承担 schema、命令、查询、兼容和迁移职责。
7. `create_app()` 带启动副作用，应用生命周期边界不清晰。
8. `core/mail_password_change.py` 引用仓库内不存在的 `core.mailcom_client`，且没有发现
   其他源码调用方，属于待确认的孤儿兼容模块。
9. 历史专项架构文档中的切换结果和当前实现必须明确标注时间，避免把历史测试数量当成当前基线。
10. 已建立最小 `pyproject.toml` / Ruff 阻断基线，但仓库仍没有可复现依赖锁；更宽的历史 lint 问题暂按 advisory 管理。

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
