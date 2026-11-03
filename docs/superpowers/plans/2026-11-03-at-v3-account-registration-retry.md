# AT v3 与账号列表注册重跑实施计划

用户已确认新增独立 AT v3，并确认账号列表按原方案接入注册重跑。本计划细化已授权工作；不涉及修改注册驱动主流程。

## 目标与边界

- 新增可选 `OPENAI_PROTOCOL_VERSION=v3`，默认仍为 v1，v1/v2/Roxy 继续使用原实现。
- v3 只服务 ChatGPT AT 刷新：密码、邮箱 OTP、MFA 连续挑战、嵌套 MFA factor、工作区选择、已认证 Cookie 会话复用、最终 Session/AT 和目标身份校验。
- 成功会话加密保存在 PostgreSQL 私有表，账号 ID 与规范化邮箱绑定；不进入普通 API、导出和任务载荷。会话失效可重新认证；网络失败不能冒充会话失效，未知认证提交不自动重复。
- 不移植附件随机补资料/创建账号、无限交互重试、把所有 RT 错误视为失效等行为；不改注册、Codex 授权或普通查活步骤。
- 账号页提供单个/批量原注册重跑，复用现有 `get_retry_info_bulk` 和 `retry_job`。现有补全账号保持独立。
- 不操作真实账号、不重启服务、不推送、不提交已有混合工作区。禁止递归删除。
- 测试使用 `/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/.venv/bin/python /tmp/turb_sub2api_test.py`；仅连接 turb_test 隔离 schema。

## Task 1：独立 v3 认证适配器

文件所有权：新增 `core/accounts/liveness/protocol/v3.py`、`core/storage/accounts/protocol_sessions.py` 与对应新测试；不要编辑 v2.py、注册文件或 service.py。

接口：

```python
def refresh_access_token(email: str, *, proxy=None, proxy_supplier=None,
                         identity=None, context_recorder=None,
                         on_remote_request_started=None, on_authenticated=None,
                         account_id: int | None = None) -> dict:
    ...
```

返回遵守现有 v2 结果协议，`live_check_driver=protocol_v3`，错误均分类。复用无状态基础函数，不通过全局 monkeypatch 改 v2。回调必须在 Session 活着时执行。

- [x] 先写失败测试：嵌套 MFA、密码→邮箱→MFA、直接 MFA、工作区选择、资料页拒绝、目标身份不匹配。
- [x] 实现有界认证分支，仅信任 OpenAI/ChatGPT 的 HTTPS URL；工作区优先匹配目标账户，无法消歧时给出分类错误。
- [x] 保存经目标身份确认的认证 Cookie 与设备画像；复用时首先读取 Session，明确失效才走新登录。旧/不匹配/损坏缓存不污染新会话。
- [x] 私有会话采用 `runtime_config.encrypt_private_text/decrypt_private_text`，隔离账号/邮箱，有限有效期；缓存存储失败不能抹掉已获得的有效 AT。
- [x] 验证存储往返、过期、身份隔离、网络故障不触发登录、缓存成功免密码/OTP、无缓存完整认证以及 v2 回归。

## Task 2：账号到注册任务的后端适配

文件所有权：新增 `core/accounts/registration_retry.py`，修改 `webui/routes/accounts.py`、必要时 `webui/route_helpers.py`，新增后端测试。不得改 `core/registration/`。

账号列表输出追加：

```json
{"registration_retry":{"available":true,"source_job_id":123,"action":"registration_resume","label":"继续注册","reason":"","active":false}}
```

仅字段白名单，不含凭据。账号列表没有可关联原任务时 `available=false`，返回原因。

接口：`POST /api/accounts/<id>/registration-retry`，`POST /api/accounts/registration-retry-bulk`，批量体 `{"account_ids":[1,2]}`。返回 `ok, started_count, started, reused_count, reused, skipped_count, skipped`，每项至少 `account_id`；成功项含 `job_id`、原接口返回的 `task_id/run_id`（若有）、`retry_action`、`message`。单个也返回同结构。

- [x] 失败测试：账号绑定原 Attempt/任务、原 job account_id 空、无来源、多历史失败后成功、活跃任务、批量去重。
- [x] 按 account→Attempt→root→最新链路解析，禁止随意挑旧失败；复用批量 retry 投影，执行前重验来源。
- [x] 调用原 retry_job，不修改注册步骤或另建注册执行器；已有活动归入 reused/进行中，不重复派发。
- [x] 列表投影批量读取，失败不拖垮账号列表；API 参数验证与现有路由一致。
- [x] 测试只 mock 执行边界，不发真实注册请求；验证现有 complete 操作仍独立。

## Task 3：账号列表 UI 与 v3 文案

文件所有权：`webui/static/js/pages/accounts/page.js`、`webui/templates/index.html`、新增前端测试。不改后端与配置 schema。

- [x] 行更多菜单加入原注册重跑，采用后端 label/reason；批量工具栏加入“重跑注册”。
- [x] 调用 Task 2 接口；显示创建、进行中和跳过原因。单任务定位任务详情，缺少统一任务 ID 时定位注册 job；批量展示汇总和任务入口。
- [x] 防重复点击；后端最新资格为准；已完成/无来源不得误显示可继续。
- [x] 刷新配置说明识别 v3，提示先复用有效登录会话、失效后认证；v1/v2/Roxy 文案兼容。
- [x] Node 行为测试验证按钮、批量请求、忙碌、跳过、任务定位和旧刷新配置。

## Task 4：v3 调度、配置、文档与集成

主代理负责 `core/auth/protocol/version.py`、`core/accounts/liveness/service.py`、`config/openai_protocol.py`、`config/schema.py`、`.env.example`、README、工作流文档和集成测试。

- [x] 先加入 v3 版本解析/配置/调度失败测试，覆盖入队冻结、显式驱动、自动刷新、重跑配置、邮箱失效不覆盖 v3。
- [x] 增加 v3 路由，account_id 只传给 v3；错误、持久任务回执与代理选择沿用现有结构。
- [x] 版本选项只影响 refresh_at，其他单版本步骤仍固定原实现；默认值不变。
- [x] 文档说明入口、边界、缓存失效后的回退和账号列表重跑使用方式。
- [x] 合并相关单元/存储/路由/前端回归；用本地隔离浏览器页面验证新入口与 v3 文案。
- [x] 独立审阅本次差异，修复发现的问题后复验。交付区分已改文件、测试、真实验收和服务加载状态。


## 完成验收（2026-11-03）

- v3 独立适配器、账号绑定加密缓存、配置/任务快照选择、错误分类和认证步骤投影完成；默认仍为 v1。缓存每次成功验证后保存 24 小时，不复用旧代理。
- 账号列表单个/批量重跑完成，直接复用原注册服务；已存在的任务归入进行中，支持原注册 job 与 Codex/套餐 operation_task_id 的准确定位。
- 两次独立审阅共发现 7 项问题，均修复并复审通过：过期 AT、实际认证 Cookie、取消/租约控制异常、前序认证成功证据、进行中后处理任务识别、busy 归类及 operation_task_id 定位。
- 浏览器使用纯模拟 API 页面验收单账号任务跳转、批量创建/进行中/跳过原因和 v3 提示。补修了小视口长菜单的高度与内部滚动，鼠标可正常打开原刷新 AT 操作；模拟服务器和临时标签已关闭。
- 最终相关 Python 回归 423 项通过（119 项账号/注册兼容用例，303 项 v3/旧驱动/错误/路由用例，另增 1 项配置验证；重复复跑不计），Node 165 项通过。数据库测试仅使用 turb_test 隔离 schema。
- 路由契约新增两条明确白名单，原路由基线摘要通过；git diff --check、前端语法检查通过。core/registration、v2.py、legacy.py 无差异。
- 未发真实账号请求，未修改生产数据库，未重启、提交、推送或部署；真实服务成功率尚未验收。
