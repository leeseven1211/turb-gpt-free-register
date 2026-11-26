# 优惠独立存储与列表提速实施计划

> 执行方式：使用 superpowers:subagent-driven-development；按职责分离文件，并发处理存储、查询、界面和基准，集成后统一评审。

**目标：** 将优惠筛选迁移到独立轻量表，动态列全实际套餐优惠并改善列表刷新。

**架构：** 保留账号 JSON 作为证据，轻量关系投影承担筛选和计数。顶层优惠发生持久化变化时原子更新投影，旧筛选值保留，账号与批量页面共享动态分面和标签。

**技术栈：** Python、PostgreSQL、Vue 3、TypeScript、Vitest。

**设计：** [已确认设计](../specs/2026-11-26-account-promotions-design.md)。

## 全局约束

- 不执行 rm -r / rm -rf；保留主工作区现有修改。
- 不改变注册请求、步骤、调用顺序、重试或状态机，不改变列表套餐显示。
- 所有新增文案、日志、注释和说明使用中文；私有数据不得提交或打印。
- 数据库测试仅使用 turb_test 和 test_ schema，统一入口为 tools/test_isolated.py。
- 投影表和动态组合键的格式以设计文档为准，读写逻辑必须一致。
- 原成功快照、未知结果和未查询不能混为无优惠；保留旧筛选语义。
- 先验证并评审，再提交并部署本地；不推送、不部署 Oracle。

### Task 1: 存储投影与显式迁移

**文件：** 新建 `core/storage/accounts/promotion_offers.py`；修改 `core/storage/records.py`；新建 `tests/accounts/test_promotion_offer_projection.py`。

**接口：** 导出 `TABLE_NAME = "account_promotion_offers"`、`ensure_schema(conn)`、`offer_key(plan, kind, percentage, periods, period)` 和 `offer_label(row)`；表列与设计一致。建表、触发器和幂等回填由显式版本迁移统一调用。

- [ ] 先添加失败测试，证明插入实际活动会生成记录，重复国家同权益不会重复；尚无投影时应失败。
- [ ] 运行 `source /tmp/turb-promotion-test-env-20261126.sh; .venv/bin/python tools/test_isolated.py --profile all -- tests/accounts/test_promotion_offer_projection.py -q`，记录红灯。
- [ ] 实现规范化键、中文标签、轻量表、索引、外键和自动事务维护，确保 UPDATE 无关字段不重建投影。
- [ ] 覆盖旧版本升级、空数组、旧 Plus 回填、失败保留、缺失字段保留、none/unknown、归档、级联删除、事务回滚和直接记录写入。
- [ ] 运行新测试及 `tests/accounts/test_account_promotion_storage.py`、`tests/accounts/test_plan_country_check.py`；输出修改清单和实际结果，不提交。

### Task 2: 索引查询、动态分面与旧值兼容

**文件：** 修改 `core/storage/admin_repository.py`、`core/accounts/query.py`；新建 `tests/accounts/test_promotion_offer_query.py`，必要时更新直接相关存储查询测试。

**接口：** 消费 Task 1 的表和标签函数；新值格式为 `offer_v1_[0-9a-f]{32}`。`facets.promotion` 返回 `{value, count, label?, group?}`，保留旧类别供状态和已选兼容条件使用。

- [ ] 先添加旧值和新组合键的列表、总数、跨国去重、分面和批量查询一致性失败测试。
- [ ] 用统一隔离入口运行红灯。
- [ ] 将 JSON 细分类谓词替换为投影索引查询；同列 OR、不同列 AND、自排除分面语义保持不变。
- [ ] 动态分面返回中文标签和套餐 group，已选零命中保留 metadata；不重复计算相同优惠条件。
- [ ] 运行新测试、`tests/bulk/test_account_query.py` 和 `tests/storage/test_admin_repository.py` 中相关账号查询用例；输出修改清单和结果，不提交。

### Task 3: 账号与批量筛选分组

**文件：** `frontend/src/features/accounts/filterDefinitions.ts`、`AccountFilters.vue`、`AccountsList.vue`，`frontend/src/features/bulk/useBulkCreate.ts`、`BulkCreate.vue`，对应样式及测试；`contracts/accounts.openapi.json`、生成的 `frontend/src/api/accounts-schema.d.ts`；必要时调整 `webui/static/js/shared/common.js` 的旧值中文标签。

**接口：** 动态分面提供 `value`、`count`、可选 `label` 与 `group`；新 value 为摘要键，界面标签必须使用 metadata。Team、Plus、Go、状态、已选兼容条件依次排列，复用同一选项整理逻辑。

- [ ] 先写前端行为测试，证明九种实际优惠分组显示、数量和已选摘要可读；无数据不得写死虚假套餐。
- [ ] 运行定向 Vitest 红灯。
- [ ] 实现两处共享的选项、分组和标签解析，保留已选零命中及旧筛选，隐藏未选的重复旧总类。
- [ ] 同步 AccountFacet 合同，运行 `npm --prefix frontend run generate:api`。
- [ ] 运行定向前端测试和类型检查；不构建产物、不提交，交主代理统一构建。

### Task 4: 隔离性能基准

**文件：** 新建 `tools/benchmarks/benchmark_account_promotions.py`。

**接口：** 使用 Task 1 投影和 Task 2 查询；脚本先经过 `build_isolated_environment`，仅允许 turb_test/test_ schema，无远端请求。输出完整样本、参数、结果等价、分段耗时和 EXPLAIN；清理仅用测试工具 drop_schema。

- [ ] 构建包含九种优惠、无优惠、旧 Plus、多国重复和较大 JSON 的合成数据。
- [ ] 同数据交替运行旧 JSON 细分类与新投影，覆盖无筛选、Team、九种具体优惠、多选、计数与 facets；常规对照每场景 30 样本。
- [ ] 支持 30 万账号容量，保留旧路径诊断样本数量和限制，不以不足 30 的旧样本报告 P95。
- [ ] 新旧兼容场景完整账号集合和总数相等；新动态选项与合成预期集合相等。
- [ ] 输出基准方法和使用命令，不与其他测试或构建同时运行正式采样。

### Task 5: 集成评审、提交、本地部署与验收

**文件：** README、存储架构说明、构建产物及验收记录。

- [ ] 集成上述四项，完成相关数据库测试、前端测试、合同检查、类型检查和构建。
- [ ] 独立评审完整 diff，处理发现后再提交；不包含主工作区的现有改动和私有数据。
- [ ] 运行隔离性能基准，记录 8,000 与 300,000 账号场景、查询计划和真实样本。
- [ ] 检查本地服务、活动任务、资源租约和托管方式，备份后按不可变 release 切换已提交版本。
- [ ] 核对 PID、目录、版本、监听、日志、healthz、readyz、login；真实浏览器验收账号与批量优惠筛选及刷新。
- [ ] 汇报修改、测试、评审、提交、推送、重启与浏览器验收各自实际状态；工作区保留到最终集成完成再使用原生归档。
