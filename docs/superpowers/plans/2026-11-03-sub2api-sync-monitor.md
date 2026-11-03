# Sub2API 实施计划

> 使用当前隔离工作区，按用户已确认的三项范围并行实施。禁止改动注册驱动。

1. 客户端与上传参数：`core/integrations/sub2api/client.py` 新增后端摘要、分页异常列表和按原 ID 更新接口；以 mock HTTP 行为测试参数保留、身份核验、清错/启用和配置热切换。
2. 持久补传：`core/storage/sub2api.py` 保存领域状态；`core/integrations/sub2api/jobs.py` 注册 `sub2api_sync` durable handler；测试代际、互斥、退避、失败阶段与重启恢复。
3. 异常巡检：`core/integrations/sub2api/monitor.py` 编排补传、现有刷新任务和现有 OAuth 任务；测试按邮箱归并、固定目标、多阶段恢复、资料缺失、停用、忙碌和冷却。
4. 集成：OAuth 与刷新成功保留原结果，并把未完成同步交给补传；巡检 OAuth 任务携带固定远端目标；配置 schema、模块、示例、前端分组、状态接口及启动恢复同步更新。
5. 定向验证：通过 `tools/test_isolated.py --profile all` 运行新增测试以及现有上传、授权同步、刷新持久化、配置和调度相邻回归，再运行静态检查与隔离浏览器验收。
6. 独立审查并修复发现的问题。交付本地改动、测试结果与实际部署状态，不自动推送或修改 Oracle。

各并行单元先写业务失败用例并确认红灯，再实现；跨模块接口由主代理协调，最后统一执行回归。
