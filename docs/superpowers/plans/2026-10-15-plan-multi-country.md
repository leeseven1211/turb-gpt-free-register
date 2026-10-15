# 独立查套餐多国家查询实施计划

**目标：** 账号页查套餐支持配置 `JP / VN / IN`，按国家查询、保存并展示优惠。

**架构：** 复用持久任务与按地区区分的代理 profile，增加逐国查询协调和账号 JSONB 国家快照。注册路径继续单次查询；前端消费明确白名单的国家结果。

**技术栈：** Python、PostgreSQL、Flask、原生 JavaScript/CSS。

**设计：** [独立查套餐的多国家优惠查询](../specs/2026-10-15-plan-multi-country-design.md)

## 全局约束

- 不执行递归删除，不修改或输出私有数据。
- 存储修改在隔离工作区，测试使用开发库的 `test_` schema。
- 注册查套餐保持原行为；不新增结账或付款操作。
- 新增文案、注释和文档使用中文。

## 审查重点

- 某国家长期没有可用 IP：该国有限等待后记录失败，其余国家继续。
- 失败国家已有免费优惠：保留历史并明确失败，不能冒充本次成功。
- 热加载或手动重跑：本次国家和线路策略保持冻结，允许再次查询。
- 服务中断：已完成国家结果不会丢失，未完成国家不能显示无优惠。
- 历史记录和注册自动查询：不从当前配置猜测历史国家，也不扩展注册查询次数。

### 任务 1：配置与分国家代理库存

**文件：** `config/schema.py`、`config/proxy.py`、`.env.example`、`core/proxy_pool.py`、`webui/static/js/modern/config.js`，以及专用测试。

**接口：** 输出 `PLAN_CHECK_COUNTRIES: list[str]`（默认 `['JP', 'VN', 'IN']`）、`PLAN_CHECK_COUNTRY_WAIT_TIMEOUT: int`（默认 60，5–300 秒）；`proxy_pool.snapshot()` 增加安全的 `country_pools` 统计。

- [x] 先测试国家规范化、非法/重复/空列表、配置热加载和分国 profile。
- [x] 实现配置、分国家预热、容量与地区统计；沿用既有出口校验。
- [x] 执行配置和代理池相邻回归。

### 任务 2：查询协调与逐国存储

**文件：** `core/plan_check_service.py`、新建 `core/plan_check_countries.py`、新建 `core/storage/plan_countries.py`、`core/storage/db_legacy.py`、`webui/route_helpers.py`，以及专用测试。

**接口：** 账号公开 `plan_check_countries: list[str]`、`plan_check_country_results: list[dict]`、`plan_check_partial: bool`。每国结果结构遵循设计文档；优惠列表增加 `country` 与历史状态标记。

- [x] 先测试国家不同优惠、部分/全部失败、逐国保存、取消和注册隔离。
- [x] 在新独立任务 data 冻结国家；旧任务与 `registration*` trigger 保持单次查询。
- [x] 逐国申请对应出口并验证，白名单持久化每个结果，汇总并写回兼容套餐字段。
- [x] 执行隔离存储、任务历史、重跑和注册相邻回归。

### 任务 3：国家优惠与库存页面

**文件：** `webui/static/js/modern/accounts.js`、`webui/static/css/modern.css`、`webui/static/js/proxy_traffic.js`，以及前端测试。

**接口：** 消费任务 2 的账号字段和任务 1 的 `country_pools`；没有国家结果时保持现有展示。

- [x] 先测试国家标签、逐国最高优惠、失败保留历史、提示转义和旧记录兼容。
- [x] 列表、详情、任务摘要和池页面显示真实国家结果。
- [x] 执行 Node 测试及桌面/移动浏览器交互验证。

### 任务 4：集成与交付

- [x] 同步 README 和存储文档，检查 Markdown 相对链接。
- [x] 运行定向及相邻 Python/Node 回归、静态检查和隔离浏览器验收。
- [x] 完成差异审查并确定选择性暂存范围。

交付约定：将验证通过的提交整合到 main；分别汇报文件、测试、提交、推送、重启和真实远端查询状态。

验证记录：最终 Python 相关回归覆盖 8 个文件，109 项及 11 个子测试通过；前端相关 Node 测试 60 项通过。使用隔离开发库、合成账号完成桌面、手机点击、键盘提示、配置页和代理池页验收；真实账号跨国查询尚未执行。
