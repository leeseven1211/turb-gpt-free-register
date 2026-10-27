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

- [ ] 先补隔离测试：生成 available 且无 owner；同 request_id 重试不重复；旧 NOT NULL 表迁移保留历史。
- [ ] 迁移 nullable 归属字段，添加 generation_key 和必要索引；实现人工生成，沿用母资源额度和 profile 固定规则。
- [ ] 实现并发库存领取与事务绑定；修改 acquire_address 只领取库存；恢复路径先于配置和健康检查。
- [ ] 状态管理仅允许未领取库存 available/disabled 切换，返回逐条原因。
- [ ] 扩展服务端过滤和公共行能力字段，保留母资源概况；容量计数与真实领取使用一致条件。
- [ ] 测试覆盖并发、回滚、历史恢复、库存为空但理论额度充足、母资源失效、旧 profile 恢复、额度调小。

## 任务二：接口、注册预检和错误分类

**文件：** webui/routes/email_pool.py、webui/routes/jobs.py、core/task_errors.py、README.md、docs/architecture/storage-architecture.md，及对应 API/错误分类测试。

**消费：** 任务一的服务接口；前端按设计中的 HTTP 契约调用。

- [ ] 新增生成和状态批量接口；验证来源、整数数量/ID、稳定请求 ID、日期与状态；返回字段继续白名单。
- [ ] allocations 透传表头过滤，summary 新增库存聚合字段。
- [ ] 注册预检跳过库存模式的 HME 同步；容量不足提示库存补充，继续保留 warning 和重跑入口。
- [ ] 为库存不足、来源不支持、母资源或 profile 不可用、身份冲突添加稳定错误分类，保留详细原因。
- [ ] 用真实蓝图与隔离库验证参数、请求幂等、批量跳过结果和预检无外部调用；更新功能文档。

## 任务三：现代库存列表与生成弹窗

**文件：** webui/templates/index.html、webui/static/js/modern/email.js、common.js、modern.css 及相关前端测试。

- [ ] 删除旧说明/概况/来源select/刷新按钮，替换为统一工具栏和筛选表格。
- [ ] 接入各表头筛选、清筛、统一 pager、列宽及选择状态；保留请求 generation 防旧响应覆盖。
- [ ] 生成 dialog 使用稳定 request_id，提交中禁用，失败保留参数和 ID，部分生成明确提示；成功刷新库存。
- [ ] 实现复制选中/当前页、批量停用/恢复、逐行操作与跳过原因展示；不对已归属地址提供回收操作。
- [ ] 保留母邮箱“查看子地址”的精确跳转与分页重置，小屏保留筛选入口。
- [ ] 运行定向 node 测试、语法检查，并使用真实浏览器验收桌面/小屏、生成、领取前后状态、筛选、复制、批量和导航恢复。

## 集成与交付

- [ ] 独立复核三部分差异；修正有效问题后运行相关隔离回归。
- [ ] 在本地 main 集成已验证提交；不推送未授权远端。
- [ ] 重启已有 8000 端口服务，检查 PID、工作目录、健康、readiness 与页面新版本。
- [ ] 最终报告已修改、测试、提交、推送、重启和真实流程验收范围。
