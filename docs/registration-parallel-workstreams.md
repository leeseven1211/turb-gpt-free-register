# 五窗口并行开发认领说明

本文用于后续五个开发窗口认领任务。认领时请复制对应工作流标题，并补充负责人、分支、预计提交和依赖。

## 总规则

1. 当前目标是 Roxy 主流程 + Protocol 辅助，不把两者拆成两个并列注册系统。
2. 不新增 fast 模式；优化正常流程中的等待和状态判断。
3. 不开发本地指纹浏览器、Browser Use、Skyvern 或 CloakBrowser。
4. 不修改 `.env`、账号、Token、邮箱池、日志、`run/`、`.venv/`。
5. 不连接生产数据库；存储变更只在独立开发库完成。
6. 不执行 `rm -r` / `rm -rf`；删除文件必须逐个确认。
7. 每个窗口只提交自己认领的领域，跨领域接口先提交契约，再由依赖窗口接入。

## 窗口 A：Roxy + Protocol 流程状态机

目标：让 Roxy 继续承担完整浏览器流程，Protocol 按阶段辅助，不重复等待。

范围：

- `core/registration/roxy.py`
- `core/registration/protocol.py`
- 新建页面状态/阶段编排模块
- Roxy 与 Protocol 的阶段契约

重点：邮箱提交、密码页、OTP 终态、Session 提前结束、Protocol fallback、统一总超时。

禁止：修改数据库 schema、任务中心投影、WebUI 大范围重构。

依赖：使用 D 窗口确认的阶段名和事件字段；状态契约先写测试。

验收：710、713、709 场景回放通过；Roxy 主流程未被 Protocol 失败打断。

## 窗口 B：Attempt / Run / Checkpoint 存储

目标：把一次注册意图和一次执行分开，建立可恢复事实。

范围：

- `core/record_store.py`
- `core/storage/`
- 数据库迁移脚本和 verify 工具

重点：`registration_attempts`、`registration_runs`、`registration_events`、检查点单向推进、Token 后核心落库。

禁止：修改 Roxy 页面选择器、删除旧表、连接生产库。

依赖：向 A/C/D 提供稳定的存储接口和状态枚举。

验收：中断恢复、重复迁移、Attempt 重试互斥、数据行数和孤儿检查通过。

## 窗口 C：后处理、恢复、重试和资源租约

目标：将 2FA、Codex、套餐从注册核心中解耦，并建立安全恢复动作。

范围：

- `core/registration_service.py`
- 2FA、Codex、plan check 服务
- email/proxy lease 相关编排
- `next_actions` 和 retry job

重点：2FA 失败不回滚核心注册；已越过不可逆边界不重新注册；资源租约绑定 Attempt。

禁止：修改诊断采集格式、修改 operation projection 实现。

依赖：B 的 Attempt/Checkpoint；A 的阶段结果。

验收：704 场景变成“核心成功、2FA 失败、可补跑”；重启不会重复注册。

## 窗口 D：诊断、事件、耗时和错误分类

目标：让所有失败和部分成功都有可追溯、可解释的现场。

范围：

- `core/registration_debug.py`
- `core/task_stages.py`
- `core/task_errors.py`
- 诊断 API 和测试 fixture

重点：取消脱敏；保存原始页面/网络/截图；记录邮箱证据、最后确认状态、等待原因；后处理失败也触发诊断。

禁止：修改注册主流程行为、修改数据库投影锁逻辑。

依赖：A 的阶段状态；B 的 `run_id/attempt_id`。

验收：诊断不串邮箱；网络错误和“没有观察到网络错误”能区分；采集不阻塞主流程。

## 窗口 E：统一任务中心异步投影

目标：解决批次死锁和成功任务长期显示 running。

范围：

- `core/storage/operation.py`
- `core/operation_task_store.py`
- 投影 worker/队列
- `webui/routes/jobs.py` 和任务展示

重点：事件异步投影、按 batch 更新、固定锁顺序、失败重试、事实/投影延迟展示。

禁止：把 operation 状态作为注册事实来源；修改注册核心状态判断。

依赖：B 的事件 schema；D 的事件字段。

验收：并发无死锁；投影故障不影响注册；批次计数最终一致。

## 窗口间交付顺序

```text
D 先定义事件/阶段字段
       |
       +--> A 使用状态和等待事件
       +--> B 使用 Attempt/Run 事件关联
       |
       B 完成基础存储
       |
       +--> C 接入恢复和后处理
       +--> E 接入异步投影
```

A、B、D 可以先并行开发；C、E 必须在接口契约冻结后接入。所有窗口先提交测试和契约，再提交实现，避免五个窗口同时修改同一个大函数。

## 认领模板

```text
认领工作流：A / B / C / D / E
负责人：
分支：
预计拆分提交：
依赖的契约：
本窗口不修改：
测试计划：
回滚方式：
```
