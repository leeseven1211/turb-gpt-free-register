# 邮箱子地址库存管理实现计划

**目标：** 将子地址从领取时生成改为人工预生成库存，并提供现代列表管理。

**架构：** 复用地址账本和固定 profile；生成、领取、管理分别有清晰事务边界。库存领取仍走 email_provider 的统一契约。前端复用现有表头筛选和分页组件。

**技术栈：** Python、PostgreSQL、Flask、原生 JavaScript、HTML/CSS、node:test、pytest。

**设计：** [库存管理设计](../specs/2026-10-27-email-subaddress-inventory-design.md)

## 全局约束

- 中文界面、文档、注释和新增错误文案。
- 不执行 rm -r 或递归删除；保留用户数据和现有工作区。
- 不连接生产数据库执行测试，不使用 public schema。
- 历史归属不回收；未知注册结果继续原身份重跑。
- 不新增领取时生成的 fallback，不隐式改变配置。

## 任务一：库存事实、生成与原子领取

**文件：** core/record_store.py、core/storage/email_address_allocations.py、core/email_derivation.py，及对应隔离存储测试。

**产出接口：**

```python
generate_inventory(source: str, count: int, request_id: str, parent_id: int | None = None) -> dict
update_inventory_status(ids: list[int], state: str) -> dict
list_allocations(source=None, parent_id=None, page=1, page_size=50,
                 q='', parent_q='', state='', related_q='', created_from='', created_to='') -> dict
capacity_summary(source: str) -> dict  # remaining 为实际可领取库存
generation_capacity_summary(source: str) -> dict  # 原理论生成容量
```

- [x] 先补隔离测试：生成 available 且无 owner；同 request_id 重试不重复；旧 NOT NULL 表迁移保留历史。
- [x] 迁移 nullable 归属字段，添加 generation_key 和必要索引；实现人工生成，沿用母资源额度和 profile 固定规则。
- [x] 实现并发库存领取与事务绑定；修改 acquire_address 只领取库存；恢复路径先于配置和健康检查。
- [x] 状态管理仅允许未领取库存 available/disabled 切换，返回逐条原因。
- [x] 扩展服务端过滤和公共行能力字段，保留母资源概况；容量计数与真实领取使用一致条件。
- [x] 测试覆盖并发、回滚、历史恢复、库存为空但理论额度充足、母资源失效、旧 profile 恢复、额度调小。

## 任务二：接口、注册预检和错误分类

**文件：** webui/routes/email_pool.py、webui/routes/jobs.py、core/task_errors.py、README.md、docs/architecture/storage-architecture.md，及对应 API/错误分类测试。

**消费：** 任务一的服务接口；前端按设计中的 HTTP 契约调用。

- [x] 新增生成和状态批量接口；验证来源、整数数量/ID、稳定请求 ID、日期与状态；返回字段继续白名单。
- [x] allocations 透传表头过滤，summary 新增库存聚合字段。
- [x] 注册预检跳过库存模式的 HME 同步；容量不足提示库存补充，继续保留 warning 和重跑入口。
- [x] 为库存不足、来源不支持、母资源或 profile 不可用、身份冲突添加稳定错误分类，保留详细原因。
- [x] 用真实蓝图与隔离库验证参数、请求幂等、批量跳过结果和预检无外部调用；更新功能文档。

## 任务三：现代库存列表与生成弹窗

**文件：** webui/templates/index.html、webui/static/js/modern/email.js、common.js、modern.css 及相关前端测试。

- [x] 删除旧说明/概况/来源select/刷新按钮，替换为统一工具栏和筛选表格。
- [x] 接入各表头筛选、清筛、统一 pager、列宽及选择状态；保留请求 generation 防旧响应覆盖。
- [x] 生成 dialog 使用稳定 request_id，提交中禁用，失败保留参数和 ID，部分生成明确提示；成功刷新库存。
- [x] 实现复制选中/当前页、批量停用/恢复、逐行操作与跳过原因展示；不对已归属地址提供回收操作。
- [x] 保留母邮箱“查看子地址”的精确跳转与分页重置，小屏保留筛选入口。
- [x] 运行定向 node 测试、语法检查，并使用真实浏览器验收桌面/小屏、生成、领取前后状态、筛选、复制、批量和导航恢复。

## 集成与交付

- [x] 独立复核三部分差异；修正有效问题后运行相关隔离回归。
- [ ] 在本地 main 集成已验证提交；不推送未授权远端。
- [ ] 重启已有 8000 端口服务，检查 PID、工作目录、健康、readiness 与页面新版本。
- [ ] 最终报告已修改、测试、提交、推送、重启和真实流程验收范围。

## 验证记录

- 核心、迁移、请求幂等、库存事务、收件路由、API、错误分类和路由契约合跑：213 passed、121 subtests passed。
- 相邻注册/换绑/配置回归：344 passed、1413 subtests passed；另有 1 项既有刷新 AT 配置帮助文案断言失败。该字段在本轮 diff 中未变，main 原文也不满足旧断言，保留原功能。补跑配置与库存可用性及路由契约：55 passed、10 subtests passed。
- 前端库存/列宽/配置导航：53 passed；最后调整移除顶部介绍后，库存/列宽/注册导航相关 41 passed。JavaScript 语法和变更 Python 文件的 Ruff 检查通过。
- 独立审查验证了请求事实写入故障回滚、零/部分结果重放、范围冲突、固定收件密钥失效及历史恢复。发现并修复坏 profile 扫描保留母资源锁导致的并发死锁；原场景和继续领取健康库存两个独立复测均通过。
- 真实 Chrome 在独立 turb_dev/test_ schema 验证生成、表头关键词/状态筛选、批量停用与恢复、混合选择跳过已绑定地址、跨页选择、390px 窄屏及统一领取后状态。复制动作成功提示和前端传参测试通过，浏览器工具虚拟剪贴板未返回系统剪贴板内容。未执行外部注册或真实 OTP 收件。
- 路由快照原先滞后：对照 main 实际 155 条，本轮仅增加生成与状态批量两条，无原有路由删除或变更；基线校正为 157 条。
