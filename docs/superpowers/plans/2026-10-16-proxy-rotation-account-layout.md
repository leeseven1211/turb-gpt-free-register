# 代理轮换回收与账号两行布局实施计划

> 代理执行要求：使用 `superpowers:subagent-driven-development` 分工实施并审查；用户已明确要求直接开发，沿用项目规定的并发子代理方式，不再增加计划确认轮次。

**目标：** 提供多国家预热入口、最多两行的账号列表，以及支持少量复用和出口换代的代理池。

**架构：** 保留 PostgreSQL 库存及任务租约，按 endpoint 与出口代次分离所有权。独立文件分工并行开发，控制器完成代理后台调度、配置与最终集成；涉及相同文件的修改串行处理。

**技术栈：** Python、PostgreSQL/psycopg、Flask、原生 JavaScript/CSS、pytest 与 Node 测试。

**设计：** [设计稿](../specs/2026-10-16-proxy-rotation-account-layout-design.md)。

## 全局约束

- 中文交流、文案、日志与新增注释；不得执行 `rm -r`、`rm -rf`。
- 保留用户文件及私有运行数据；只提交明确审查过的目标文件。
- 查套餐每 IP 最多三次，包含首次，跨 endpoint、profile 和进程累计。
- 原有效期不因复检或换代延长；活跃子租约及历史 IP 关联不可改写。
- 只在独立工作区开发共享存储；测试使用 `turb_test` 及 `test_` schema，禁止生产库及 `public`。
- 隔离运行器使用原工作区 Python 依赖；不复制 `.env`、账号及运行日志到工作区。
- 测试统一通过本计划工作目录下的 `run-tests.py --profile all -- ...` 调用项目隔离入口。
- 产品实现完成后运行聚焦、相邻及隔离完整套件，再做真实桌面和手机页面验收。

## 审查重点

1. 第三次领取即耗尽；尚未交付的取消须返还额度，已交付失败不能返还。
2. 旧 IP 隔离不能随 endpoint 换代消失；相同 IP 跨 endpoint 不能重复取得额度。
3. 用户保存的极窄列宽不能裁掉操作及优惠历史/失败标记。
4. 进程重启不能重建国家等待预算或重复查询本 Run 已成功国家。
5. 复检全部卡慢时仍有补货额度，容量满时只回收无活跃子租约的等待资源。

## Task 1: 库存与租约换代

**文件：** `core/record_store.py`、`core/proxy_lease_store.py`、`core/proxy_pool_store.py`；相关 `tests/test_proxy_resource_pool.py`、`test_proxy_lease_store.py`、`test_plan_proxy_reuse.py`，可新增聚焦测试文件。不要修改 `core/proxy_pool.py`，由控制器接线。

**接口：** 保留 `claim/release/maintenance/counts/public_items` 调用契约，扩展 `take_check(profile_key, *, max_age, timeout, min_ttl=0)`；扩展 `finish_check(resource, *, success, exit_ip=None, region=None, min_ttl=0, check_interval=60, max_failures=3) -> bool`，返回是否接受本次检测，不表示一定发布 ready；新增 `mark_delivered(lease) -> bool`，供池确认交付。确认事务迟到时，只有池返回前的异常路径显式声明 `release(..., before_delivery=True)` 补偿，普通已交付释放不退款。所有新参数保持旧调用兼容。

- [x] 先增加并观察失败：`test_third_claim_marks_exhausted`、`test_unhanded_cancel_refunds_only_reserved_lease`、`test_rotation_preserves_old_ip_and_expiry`，分别断言三次、未交付返还、原期限与旧 IP 不变。
- [x] 新增 `endpoint_owner` 并幂等更新原 endpoint 唯一索引；旧 IP 索引保留。所有 endpoint 检查识别新所有权，升级旧数据保持默认真。
- [x] 增加 `rotation_wait`、持久探测调度、无活跃租约换代事务、代次耗尽清除、失败三次淘汰和中断恢复；旧任务迟到释放不改变新代。
- [x] 领取预留参与限额，`delivery_state` 区分交付和确定未交付，旧记录缺字段按已交付。容量包含等待轮换，紧张时回收无活跃子租约的等待资源。
- [x] 验证并发换代、不同国家、旧 IP 再出现、临近到期、迟到结果及迁移重复执行。运行隔离聚焦套件并自审；向控制器报告实际命令及结果。不要自行提交其他代理文件。

## Task 2: 账号两行布局

**文件：** `webui/static/js/modern/accounts.js`、`common.js`、`webui/static/css/modern.css`、`ui-foundation.css`，必要时仅修改 `webui/templates/index.html` 的账号区域；对应账号优惠/筛选/搜索 Node 测试。不要修改配置页和代理库存页面。

**接口：** 保留十五列顺序、列标识、筛选、事件属性与保存列宽；复用原优惠浮层及详情。

- [x] 先增加并观察失败：三国与十国优惠最多两条轨道，折叠结果显示另 N 国及不可裁切的失败/历史计数；浮层仍含所有国家。
- [x] 按设计表安排列内内容，桌面行高起点 72px、触屏 80px；额度从实际窗口选择最多两条，其他状态保留。
- [x] 默认列宽起点 `36/72/160/80/84/88/72/88/88/192/72/88/72/96/108`，解除账号表 1100px 强制压缩，滚动仅在表内；用户保存比例保留，必要时扩大整表。
- [x] 保护 Token、ID 筛选、操作及优惠固定标记。全部无优惠/待查询仅在无历史快照时合并；历史徽标不随支付方式截断。
- [x] 运行优惠、筛选、搜索相邻 Node 测试，记录需控制器验证的 DOM 与浏览器场景，不增加无关移动卡片或新弹窗。

## Task 3: 持久化国家等待与换线预算

**文件：** `core/plan_check_service.py`、`core/storage/plan_countries.py`、`core/chatgpt_plan.py` 的可选绝对期限参数；`tests/test_plan_country_check.py` 及相关套餐测试。不要修改池存储与全局 record_store。

**接口：** 沿用 `acquire_account_proxy(..., timeout=..., allow_reuse=..., reuse_limit=...)`；保持国家结果投影与执行 fence。新进度保存在 `operation_runs.data.plan_country_progress`，旧无 fence 的测试/兼容入口仍可工作但不能访问生产库。

- [x] 先增加并观察失败：首轮缺货国家最多五秒后继续其他国家；本 Run 已成功国家不重查；累计等待 60 秒不会因切片或恢复重置。
- [x] 按 Run 和 country 持久化等待已用、切片开始/截止、HTTP 尝试、待补试与成功、总期限；初始化幂等，预算与账号投影同事务受 fence 保护。
- [x] 公平补试缺货国家，共用原单国和 Run 期限；中断片段先结算。TLS/代理/超时在原冻结次数内换线，不为每条新线路重置次数。
- [x] HTTP 401、403、429明确收口，不无限换线；取消、失租与重启保留成功国家及历史快照；手动重跑继续原快照，不增人工核对门槛。
- [x] 运行隔离国家及相邻套餐测试，验证失败国补试、无忙循环、旧 Run 不能写入、新 Run 预算独立。

## Task 4: 配置、后台调度与库存展示集成

**控制器负责文件：** `config/schema.py`、`proxy.py`、`countries.py`、`.env.example`、`webui/static/js/modern/config.js`、`core/proxy_pool.py`、`webui/static/js/proxy_traffic.js`、README 和存储架构文档；对应配置、预热、公平调度及流量前端测试。

**接口：** 消费 Task 1 的检测与交付接口，Task 3 的查询接口保持不变。新增 `PROXY_POOL_COUNTRIES=[]`，大写去重并校验 ISO 代码；不能改 `PLAN_CHECK_COUNTRIES` 的业务语义。

- [x] 先增加并观察失败：额外国家与注册/套餐国家取并集，静态国家也预热；配置页位于独立代理池；相同 profile 不重复。
- [x] 配置的国家、动作实际来源及默认注册 profile 合并预热；快照展示各国 ready/leased/checking/rotation_wait/故障、补货原因及容量不足提示。
- [x] `_check` 将实际出口传给 `finish_check`，不再把 IP 变化直接当故障；交付前调用 `mark_delivered`，取消路径原子返还。
- [x] 总 worker 大于一时供给保留至少一半向上取整，复检最多一半向下取整；五个拆三/二，一个时轮换。保留公平排序、限速和有界网络预算。
- [x] 更新配置与存储文档，完成与三个子任务的聚焦和相邻集成测试。

集成审查补充：静态来源的 generic 与国家 profile 通过稳定的完整来源键集合共用已检测库存，继续校验实际国家、URL、provider 和原租约限制。领取、补货计数及满池回收共用范围；在途槽位只计当前 profile，满池时不能退役当前调用方本可借用的同源 `ready`。新增静态库存测试覆盖进程内 profile 清空、并发独占、错国/异源拒绝及满池 worker 抢先运行。

## Task 5: 全面验证、审查与 main 交付

- [x] 检查所有实际变更的静态检查、文档链接、无私密内容；审查数据库锁序、迁移与恢复，修复可复现缺陷。
- [x] 运行项目隔离完整套件，并运行全部相关 Node 测试；失败按原因定位，不掩盖或删除用例。
- [x] 用隔离测试实例与虚拟账号数据做 1100/1280/1440px 桌面和 390px 手机验收；验证两行、按钮、浮层、筛选、轮询、保存列宽与国家配置保存。
- [x] 派发整体分支审查并处理有效发现。只提交审查过的文件，Conventional Commits 中文提交。
- [x] 保留主工作区私有及未跟踪文件，将已验收提交合回 main；检查实际提交状态。不自动推送，不把本地提交声称部署。
- [x] 若实际服务发布仍需迁移及重启，先准备完成可审阅版本，再按真实授权执行；报告测试、合并、推送、重启与真实套餐验收各自状态。

## 验证与交付记录

- 最终综合相关回归：437 passed、1041 subtests passed；全部 Node 测试：111 passed。变更 Python 的 Ruff、三份 JavaScript 语法及 diff 检查通过。
- 首轮隔离完整套件：2929 passed、1989 subtests passed，9 failed。原 main `a0ec544` 精确复测确认其中 8 项为已有失败；剩余 1 项为严格耗时阈值，全套 3.899 秒、隔离单点 1.18 秒通过。没有修改无关功能或删除失败用例。完整套件后的增量由最终综合相关回归及独立复审覆盖。
- 独立集成审查确认并修复：领取和 HTTP 前的事务耗时、交付确认迟到、静态预热与普通动作竞争、满池补货回收可借库存。最终复审无未解决发现。
- 真实浏览器使用隔离测试库及六个虚构账号；桌面 1100/1280/1440px、手机 390px 验证两行、表内横滚、分页、优惠浮窗和键盘、更多菜单、TOTP 复制、详情、筛选及列宽刷新保存。国家配置保存归一化、拒绝非法值并保留输入，独立套餐国家保持不变。临时实例和页面测试 schema 已清理。
- 交付范围为本地 main 提交；不自动推送或重启。实际服务的生产迁移、供应商轮换频率与套餐成功率尚未验收。发布需要先停止旧版本池 worker，再以同一版本初始化索引并启动，避免新旧所有权规则混用。
