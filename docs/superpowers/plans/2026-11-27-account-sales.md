# 账号贩卖区第一版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. 按任务独立实现、定向验证并审查。

**Goal:** 交付可管理多店铺、多账号来源并持久同步上架与订单的账号贩卖区第一版。

**Architecture:** 平台适配器、账号来源适配器、PostgreSQL 销售仓储、统一任务 handler 和 Vue 页面分工。所有账号归属均包含来源部署；真实外部库存确认后才记上架与归档待办。异步工作复用统一任务中心。

**Tech Stack:** Python、Flask、psycopg、PostgreSQL、Vue 3、TypeScript、Vitest。

**Spec:** `docs/superpowers/specs/2026-11-27-account-sales-design.md`

## Global Constraints

- 沟通、界面、注释和新增文档统一中文。
- 不允许 `rm -r`、递归删除、生产数据库测试或修改注册主流程。
- `.env`、账号、Token、密码、2FA、Cookie 和日志不提交、不输出。
- 使用独立工作区和测试数据库/schema；存储测试继承 `PostgresTestCase`。
- 每个条目使用 `(source_id, account_id)`，不同来源相同数字 ID 不混用。
- 店铺、商品、库存和订单的外部引用带店铺作用域。
- 密钥只存 `.env`；销售表只保存环境变量名称。
- 上架材料加密冻结，重跑同一目标先回读，逐项继续；结果未知不是禁止重跑。
- 长任务接入统一任务预算并支持启动恢复。
- 已上架和已售出产生来源归档待办；归档失败保留真实销售事实。
- 不推送、不部署 Oracle、不接管真实店铺历史库存。

### Task 1: 销售 PostgreSQL 仓储

**Files:** `core/sales/store.py`、`core/sales/__init__.py`、`tests/sales/test_sales_store.py`。

**Interfaces:** 实现独立契约文件 `docs/superpowers/specs/2026-11-27-account-sales-contract.md` 的仓储 API，供 service 消费。

- [ ] 先验证两个来源相同账号 ID 可并存、同来源重复加入幂等、交付指纹跨店冲突。

```python
def test_source_account_identity(self):
    first = store.add_item(source_id="local", account_id=7, email="local@example.test")
    other = store.add_item(source_id="oracle", account_id=7, email="remote@example.test")
    self.assertNotEqual(first["id"], other["id"])
    self.assertEqual(first["id"], store.add_item(source_id="local", account_id=7, email="local@example.test")["id"])
```

- [ ] 用 `tools/test_isolated.py --profile all -- tests/sales/test_sales_store.py -q` 观察新增行为缺失，再实现仓储。
- [ ] 实现来源、店铺、商品、库存条目、事件和归档待办的原子操作，来源/店铺公共投影不泄漏私有材料。
- [ ] 通过定向存储测试，交付测试结果与待审差异，不在并行工作期间自行提交其他任务文件。

### Task 2: 店铺与来源适配器

**Files:** `core/sales/adapters.py`、`core/sales/sources.py`、`core/sales/errors.py`、`tests/sales/test_sales_adapters.py`。

**Interfaces:** 实现契约文件中的 `LiandongAdapter`、`AccountSource` 和 `SalesError`。

- [ ] 先写 HTTP 200/业务 401、重复导入 code 0 后回读、分页、多来源资料读取和归档确认测试。

```python
def test_business_unauthorized_is_not_success(self):
    transport = FixtureTransport([{"code": 401, "msg": "请先登录！"}])
    with self.assertRaises(SalesError) as raised:
        LiandongAdapter(shop, transport=transport).check()
    self.assertEqual("shop_auth_invalid", raised.exception.code)
```

- [ ] 用隔离入口运行 `tests/sales/test_sales_adapters.py`，确认缺失实现后增加标准化适配器。
- [ ] 凭据仅通过 `token_env/auth_env` 读取；所有失败转换固定分类，不输出远端卡密和错误正文。
- [ ] 分页读取直到完整，不静默截断；归档针对所属来源并回读，不上传 AT。
- [ ] 定向测试通过，向服务任务交付接口实现和模拟传输。

### Task 3: 领域服务、持久 handler 与 HTTP

**Files:** `core/sales/service.py`、`core/sales/runtime.py`、`webui/routes/sales.py`、`tests/sales/test_sales_service.py`、`tests/sales/test_sales_api.py`。

**Interfaces:** 消费前两任务，提供设计表中的 `/api/sales/*` 与 `register_handler/start_periodic_sync/stop_periodic_sync`。

- [ ] 先写重复上架回读、历史完整资料匹配、部分失败继续、已售订单与多来源同号不串写测试。

```python
def test_listing_archives_own_source_after_readback(self):
    result = service.execute_listing(shop_id=1, product_id=1, item_ids=[self.remote_item["id"]])
    self.assertEqual(1, result["listed_count"])
    self.assertTrue(store.get_item(self.remote_item["id"])["archived"])
```

- [ ] 使用统一任务 `sales_sync` 和独立并发策略，不在 Flask 请求中直接执行整批上架。
- [ ] 保存上架意图与加密材料，逐项处理、失败回执和归档待办；周期同步只入队，启动注册 handler 保证原任务可恢复。
- [ ] API 校验店铺和条目归属，支持只读投影及销售状态事件；测试鉴权和无敏感材料回传。
- [ ] 定向服务/API 测试通过，交付集成。

### Task 4: Vue 贩卖区和账号入口

**Files:** `frontend/src/sales.ts`、`frontend/src/api/sales.ts`、`frontend/src/features/sales/*`、`frontend/src/features/accounts/AccountsToolbar.vue`、`frontend/src/features/accounts/accountToolbar.ts`、`webui/static/js/pages/sales.js`。

**Interfaces:** 使用设计中的 HTTP 路径与字段；账号入口发送现有选择的账号 ID，销售表格使用 sale item ID。

- [ ] 先写筛选、跨页选择、加入待售、配置店铺/来源和提交上架的组件行为测试。

```typescript
it('切换销售状态时清空旧视图选择', async () => {
  const wrapper = mountSalesFixture();
  await wrapper.get('[data-item-check=\"1\"]').setValue(true);
  await wrapper.get('[data-status=\"sold\"]').trigger('click');
  expect(wrapper.findAll('tbody input:checked')).toHaveLength(0);
});
```

- [ ] 复用已有视觉 token 和列表基础组件，销售页同时显示店铺、账号来源、销售状态与同步问题。
- [ ] 配置只填写环境变量引用，显示是否已配置，不展示凭据。
- [ ] 定向 Vitest 和 TypeScript 检查通过后交付；构建由协调者统一进行。

### Task 5: 集成、配置、审查与浏览器验收

**Files:** `webui/app.py`、`webui/templates/index.html`、`webui/static/js/shared/common.js`、`frontend/vite.config.ts`、`core/runtime/manifest.py`、`core/runtime/assembly.py`、`core/operations/concurrency.py`、`config/schema.py`、`config/sales.py`、`.env.example`、`README.md`。

- [ ] 注册路由、导航、Vue 入口、受管和兼容 runtime；配置 `SALES_EXECUTOR_ID`、`SALES_SYNC_WORKERS`。
- [ ] 针对新增文件运行测试、类型检查、构建和代码审查，修复交叉接口问题。
- [ ] 在独立测试库/schema 启动预览和模拟小铺，通过真实浏览器验收销售筛选、配置、历史匹配、上架和任务结果。
- [ ] 核对 Markdown 链接、工作区差异和不包含私有数据，再提交功能分支。
- [ ] 交付明确区分代码、测试、提交、推送、部署与真实店铺运行状态；未执行的步骤不声称完成。
