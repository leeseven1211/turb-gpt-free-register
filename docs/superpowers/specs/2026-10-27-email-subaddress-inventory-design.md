# 邮箱子地址库存管理设计

## 目标

邮箱子地址成为可预生成、筛选、批量管理的库存。用户已明确选择：注册只领取已生成库存，库存不足提示补充，不在领取时生成新地址。

## 页面

- 沿用账号列表的工具栏、表头筛选、当前页勾选、列宽和统一分页。
- 删除上方说明、概况介绍、独立来源筛选和“刷新子地址”按钮。
- 工具栏提供“生成子邮箱”、复制选中或当前页、停用选中、恢复可领取。
- 列为勾选、子邮箱、母邮箱、来源、状态、关联账号/任务、生成时间、操作。
- 子邮箱、母邮箱、来源、状态、关联账号/任务和生成时间均可从表头筛选；支持清筛。
- 生成使用原生 dialog，选择来源和数量（1–1000），默认使用当前来源或 iCloud；可继承从母邮箱跳入的精确 parent_id。
- 来源、状态和生成时间筛选在小屏仍能操作，表格可横向滚动，不隐藏表头。

## 库存事实

复用 PostgreSQL email_address_allocations。新增 available、disabled；历史 reserved、used、replaced、retired 原样保留。available/disabled 从未分配，三项 acquisition_id、owner_kind、owner_id 为 NULL；新字段 generation_key 唯一标识某次人工生成请求中的序号，领取后仍保留以支持请求幂等。

已有表在初始化时显式幂等 DROP NOT NULL，保留全部行、地址和原 acquisition。新增 (source,state,id) 索引与 generation_key 非空唯一索引。

`email_address_generation_requests` 记录稳定请求身份、来源、数量、母资源范围和结果，与库存同事务提交。零结果和部分结果也冻结，重复请求直接恢复结果，变更参数拒绝；修复配置或补充额度后通过新的生成操作继续补库。

人工生成保留母资源健康检查、累计额度、地址碰撞检查和固定收件 profile。所有状态都消耗历史生成额度。新生成不需要启用注册领取开关；收件配置仍必须具备完整子地址识别能力。

新领取在一个事务内抢占 eligible available 行，available → reserved，写入稳定业务身份并绑定 job/Attempt/root。并发领取不同地址；同 acquisition 恢复同一地址；绑定失败回滚库存和业务绑定。领取不再调用上游同步、profile 创建或后缀生成，不受新生成额度调小影响。母邮箱失效、停用、归档或 profile 不可用的库存不参与新领取。

只能将从未领取的 available 改为 disabled，或将从未领取的 disabled 恢复 available。已分配、已绑定和历史终态均不可重新投入库存；批量请求逐条返回跳过原因，不阻断任务重跑。

## 接口契约

- GET /api/email-derivation/allocations：保留 source、parent_id、page、page_size；新增 q、parent_q、state、related_q、created_from、created_to。返回 items/total/page/page_size，行增加 can_disable/can_restore。
- POST /api/email-derivation/generate：JSON {source,count,request_id,parent_id?}；request_id 为前端为一次生成操作创建的稳定 ID，失败重试不更换。返回 requested/created/reused/shortfall/reason_code/reason；额度不足可部分生成并明确缺口，不静默更换母资源范围或请求身份。
- POST /api/email-derivation/status-bulk：JSON {ids,state}，state 仅 available/disabled；返回 updated/skipped/results，每条结果含 id/ok/reason_code/reason。
- summary 保留母资源额度展示，增加 available/disabled 聚合。
- 已知错误有稳定 reason_code，HTTP 校验错误不泄露凭据。任务库存不足归类为 email_derivation_inventory_empty。

## 集成与验证

注册继续通过现有 EMAIL_DERIVATION_ENABLED/SOURCES 判断来源是否领取子地址；开关不影响管理页人工生成。capacity_summary 改为可领取库存数；旧理论生成容量单独供管理使用。WebUI 注册预检在库存模式不再同步 HME，库存不足继续返回 warning，提示补充后重跑。CLI、WebUI 与换绑共用 provider 领取契约。

存储变更在隔离 worktree 开发，测试仅连接 turb_dev 和 test_ schema。验证旧表迁移、幂等生成、额度并发、领取并发、事务回滚、原任务恢复、已用不回收、过滤分页、批量跳过原因、生成弹窗和真实浏览器。验收使用测试库存，避免真实账号注册。最终集成本地 main 并重启 8000 端口，独立报告提交、推送与验收状态。
