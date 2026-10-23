# Protocol 稳定性与 Plus 权益核验 Implementation Plan

> 历史说明：本文记录当时的设计或实施计划，不代表当前运行状态；现行行为与约束以 README、AGENTS.md 和当前代码为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使 Protocol 注册准确执行任务快照、保持版本自洽，并在原会话和代理仍有效时核验真实 Plus 免费试用资格。

**Architecture:** Dispatcher 以持久化快照选驱动；浏览器环境以 curl_cffi 可用 Chrome TLS 版本派生公开 HTTP/JS 版本；Protocol 在会话关闭前同步调用已有套餐检查接口。真实验收将注册成败和服务端促销结果分开统计，拒绝把未核验结果计为试用。

**Tech Stack:** Python 3.12、curl_cffi、PostgreSQL、pytest、现有 BrowserSession 与套餐查询服务。

**Spec:** `docs/superpowers/specs/2026-09-22-protocol-reliability-promo-design.md`

## Global Constraints

- 不执行 `rm -r`/`rm -rf`，不重置或覆盖现有工作区改动。
- 不读取、输出或提交 `.env`、账号、Token、Cookie、OTP、密码、完整代理地址、原始 HAR、`logs/`、`run/` 或未跟踪私有文件。
- PostgreSQL 是唯一事实来源；测试必须用 `tools/test_isolated.py` 提供的非生产测试数据库和临时 `test_` schema。
- 不伪造或绕过风控；仅保持会话内 HTTP、TLS、Sentinel 和网络线路的真实一致性。
- 不提交、推送、部署或重启服务，除非用户另行明确要求。

## Review Focus

- 配置切换发生在任务创建和执行之间时，恢复任务仍必须选择保存的驱动。
- 旧任务没有 `registration_driver` 快照时，必须兼容回退实时配置。
- curl_cffi 不支持配置的 Chrome 版本时，UA、Client Hints 与 Sentinel 环境必须同时降到实际 TLS 版本。
- 套餐同步查询无论成功或失败都必须在注册会话关闭前结束，且不能再次异步入队。
- 邮件、`request_unknown`、套餐 HTTP 错误和后处理失败必须保留为独立可统计终态，不能计入核心成功或免费试用。

### Task 1: 锁定任务快照的驱动选择

**Files:**
- Modify: `tests/test_registration_dispatcher.py`
- Modify: `core/registration/dispatcher.py`

**Interfaces:**
- Consumes: `run_registration(..., registration_options: dict | None)`
- Produces: 以 `registration_options["registration_driver"]` 为优先级的稳定驱动分发。

- [ ] **Step 1: 写红灯测试**

```python
def test_snapshot_protocol_driver_overrides_later_live_roxy_config(self):
    with patch.object(dispatcher._roxy_cfg, "REGISTRATION_DRIVER", "roxy"), patch(
        "core.registration.protocol.run_protocol_registration", return_value={"success": True}
    ) as protocol_runner, patch("core.registration.roxy.run_roxy_registration") as roxy_runner:
        dispatcher.run_registration(**self.args, registration_options={"registration_driver": "protocol"})
    protocol_runner.assert_called_once()
    roxy_runner.assert_not_called()
```

- [ ] **Step 2: 验证红灯**

Run: `PYTHON_DOTENV_DISABLED=1 python tools/test_isolated.py --profile all -- tests/test_registration_dispatcher.py::RegistrationDispatcherTests::test_snapshot_protocol_driver_overrides_later_live_roxy_config -q`

Expected: 失败，因为当前分发器只读取实时 `REGISTRATION_DRIVER`。

- [ ] **Step 3: 写最小实现**

在 `run_registration` 起始处读取 `registration_options` 字典中的非空 `registration_driver`，使用其小写规范化值；字段缺失时才读取 `_roxy_cfg.REGISTRATION_DRIVER`。保留所有现有别名与参数转发。

- [ ] **Step 4: 验证绿灯与旧任务回退**

Run: `PYTHON_DOTENV_DISABLED=1 python tools/test_isolated.py --profile all -- tests/test_registration_dispatcher.py -q`

Expected: 快照覆盖实时配置，未携带快照的原有用例仍通过。

### Task 2: 使公开 Chrome 环境与 TLS 画像版本一致

**Files:**
- Modify: `tests/test_protocol_runtime_compat.py`
- Modify: `config/browser.py`
- Modify: `core/session.py`

**Interfaces:**
- Consumes: `resolve_impersonate(value)` 与 `build_browser_environment()`。
- Produces: `resolve_chrome_identity(value) -> dict[str, str]`，其中 TLS impersonate、major、full version、UA 和 `sec-ch-ua` 使用同一 Chrome major。

- [ ] **Step 1: 写红灯测试**

```python
def test_runtime_chrome_fallback_keeps_http_and_sentinel_versions_equal(self):
    identity = resolve_chrome_identity("chrome999")
    profile = build_browser_environment(chrome_identity=identity)
    assert identity["impersonate"] in {item.value for item in BrowserType}
    assert f'Chrome/{identity["full_version"]}' in profile["user_agent"]
    assert f'v="{identity["major"]}"' in profile["sec_ch_ua"]
    assert profile["chrome_major"] == identity["major"]
```

- [ ] **Step 2: 验证红灯**

Run: `PYTHON_DOTENV_DISABLED=1 python tools/test_isolated.py --profile all -- tests/test_protocol_runtime_compat.py -q`

Expected: 失败，因为当前回退只改变 TLS impersonate，HTTP/JS 仍声明 Chrome 149。

- [ ] **Step 3: 写最小实现**

解析可用 Chrome `BrowserType` 后由实际 major 构建 `full_version`、UA 和 Client Hints；`BrowserSession` 在生成环境与创建/轮换 curl_cffi session 时使用同一解析结果。非 Chrome 值保持原行为，且不得添加随机 UA 或不存在的 navigator 字段。

- [ ] **Step 4: 验证绿灯**

Run: `PYTHON_DOTENV_DISABLED=1 python tools/test_isolated.py --profile all -- tests/test_protocol_runtime_compat.py tests/test_openai_auth_registration_flow.py -q`

Expected: 支持值原样保留，回退值在 TLS、HTTP 与 Sentinel 环境中一致。

### Task 3: 在 Protocol 会话中同步核验套餐

**Files:**
- Modify: `tests/test_protocol_registration_password.py`
- Modify: `tests/test_registration_plan_check.py`
- Modify: `core/registration/protocol.py`

**Interfaces:**
- Consumes: `check_registration_account_plan(account_id, email, access_token, proxy, session)`。
- Produces: Protocol 成功路径的单次同步套餐结果；不会再为同一账号调用 `enqueue_account_plan_check`。

- [ ] **Step 1: 写红灯测试**

```python
def test_protocol_plan_check_reuses_registration_session_and_proxy(self):
    result = run_with_completed_protocol_flow(plan_check_enabled=True)
    sync_check.assert_called_once_with(
        account_id=result["account_id"], email="user@example.test",
        access_token="test-access-token", proxy="http://proxy.example:8080", session=session,
    )
    enqueue.assert_not_called()
```

- [ ] **Step 2: 验证红灯**

Run: `PYTHON_DOTENV_DISABLED=1 python tools/test_isolated.py --profile all -- tests/test_protocol_registration_password.py -q`

Expected: 失败，因为当前 Protocol 只异步入队，未传注册会话和代理。

- [ ] **Step 3: 写最小实现**

在 Protocol 核心账号持久化、且 `plan_check_enabled` 为真时调用同步检查，并将 `session.proxy or ""` 与当前 `session` 传入。以其结果生成既有 `plan_result`；套餐失败仅标为后置失败，不撤销 access token、邮箱租约或注册核心结果。删除该路径的异步入队调用。

- [ ] **Step 4: 验证绿灯**

Run: `PYTHON_DOTENV_DISABLED=1 python tools/test_isolated.py --profile all -- tests/test_protocol_registration_password.py tests/test_registration_plan_check.py tests/test_registration_twofa_auto.py -q`

Expected: 套餐查询只执行一次，且在会话关闭前使用同一代理、Cookie 和设备环境。

### Task 4: 隔离回归与静态验证

**Files:**
- Modify: 仅 Task 1 至 Task 3 的文件。

- [ ] **Step 1: 运行受影响模块的隔离回归**

Run: `PYTHON_DOTENV_DISABLED=1 python tools/test_isolated.py --profile all -- tests/test_registration_dispatcher.py tests/test_protocol_runtime_compat.py tests/test_protocol_registration_password.py tests/test_openai_auth_registration_flow.py tests/test_registration_plan_check.py tests/test_registration_twofa_auto.py tests/test_twofa_flow.py tests/test_roxy_twofa.py -q`

Expected: 所有指定用例通过；测试连接为非生产库且 schema 由入口创建。

- [ ] **Step 2: 运行静态验证**

Run: `PYTHON_DOTENV_DISABLED=1 python -m compileall -q config core tests && node --check sentinel/sentinel-runner.js && git diff --check`

Expected: 无 Python 语法错误、Node 语法错误或补丁空白错误。

### Task 5: 受控真实验收

**Files:**
- Modify: 无；只读取任务、运行与账号的脱敏状态。

- [ ] **Step 1: 创建固定配置的 30 个新 Protocol 任务**

在确认邮箱来源、代理供应、隐藏邮箱转发和 WebUI 当前代码版本后，创建 30 个 `registration_driver=protocol` 快照任务。关闭 Codex 自动授权，启用套餐检查；不重跑 `request_unknown` 或邮件超时账号，不改变现有账号资源。

- [ ] **Step 2: 完成后按严格分母统计**

从 PostgreSQL 的任务快照、注册运行、核心账号 token 状态与套餐检查结果联合统计。30 个任务全部进入分母；核心注册失败、错误驱动、未知结果、未收到邮箱 OTP 均计错误。免费试用仅统计 `plus_trial_eligible=true` 与 `plus_promo_kind=free_trial`，套餐未核验计非试用。

- [ ] **Step 3: 报告并决定后续**

仅当错误不超过 3/30 且免费试用不少于核心成功账号的 18/30 时，报告达到目标；否则按失败阶段与真实套餐结果继续定位，不把 Roxy 结果混入 Protocol 样本。
