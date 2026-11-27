# Team 前后端集成验收

日期：2026-11-27。工作区：`codex/team-management-backend`。

## 集成范围

Antigravity 前端提交 `5f7b9a74` 已快进合入当前工作区；后端和本轮集成修正仍为未提交文件。未合并本地 `main`、推送或部署。

页面保留 Antigravity 的设计，修正实际契约和异步交互：

- Team、探测、成员、邀请、候选、预检及回执直接复用 [OpenAPI](../../../contracts/teams.openapi.json) 生成类型，移除旧的手写 DTO。
- 列表不虚构席位容量；未知计数保持未知，容量由提交前预检核算。
- 加入请求移除未发布字段；固定名单提交带数字类型的修订和目标 Team，布尔筛选使用真实参数格式。
- 受理回执区分准备、逐项受理、跳过与失败，不将 HTTP 202 表述为已加入。
- 容量不足时按契约允许持久受理，并明确提示等待可用席位；零新增占席的续接不显示该提示。
- 切换 Team、退出选人、关闭或重新打开弹窗时，旧响应不会覆盖新会话；同一 Team 暂时隐藏后仍可恢复追踪。
- 静默轮询接替普通读取后，由当前请求清除加载状态；避免刷新按钮和分页永久禁用，旧请求不能提前清除新请求的状态。
- 母号或成员跳转账号详情使用精确 ID 查询，并等待实际挂载和读取；归档与 Team 关系独立展示。
- 绑定弹窗独立分页读取本地母号关联；尚未首次同步的母号也有归属标签，不伪造已确认成员关系。
- 账号保留「活跃账号」，提供「Team 账号」与「归档账号」视图；详情轻量选人和账号页固定名单共用加入预检。

## 自动验证

最终构建 `npm run build` 通过，包含 API 生成检查、错误短语生成检查和 TypeScript 校验。

前端定向测试 **17 个文件、174 项通过**：

```sh
npm test -- \
  src/api/teams.test.ts src/api/accounts.test.ts src/features/teams \
  src/features/accounts/AccountsPageShell.test.ts \
  src/features/accounts/AccountsList.test.ts \
  src/features/accounts/queryAdapter.test.ts \
  src/features/accounts/AccountsTable.test.ts \
  src/features/accounts/AccountsToolbar.test.ts \
  src/features/dashboard/DailyRegistrationStats.test.ts
```

导航桥接回归 **16 项通过**：

```sh
node --test tests/teams/test_navigation_frontend.cjs \
  tests/accounts/test_accounts_vue_bridge.cjs
```

后端本轮定向回归 **129 项、13 个子测试通过**，使用 `turb_dev` 的隔离 schema：

```sh
python tools/test_isolated.py --profile all -- \
  tests/teams/test_http_routes.py \
  tests/teams/test_http_validation.py \
  tests/accounts/test_account_team_scope.py -q
```

独立复核覆盖保存上限时切换 Team、取消候选解析、邀请迟到回执、加入摘要、绑定与编辑弹窗会话和按 Team 保存的回执筛选，未发现仍存的 P1/P2。对应窄回归 53 项通过，不与上方测试相加计算覆盖量。

后补的容量等待提示与母号关联索引已再次独立只读复核，未发现 P1/P2。

真实浏览器随后发现静默轮询接替普通读取会遗留加载状态。列表、详情、成员和邀请页的当前请求收尾已统一修复，保持序号保护；先失败后通过的定向回归覆盖成功、失败、迟到收尾及真实排队任务轮询路径，最终验证包含在上述 174 项中，独立复核未发现新增 P1/P2。

## 浏览器验收边界

使用真实 Flask 应用、生产构建资源和业务 HTTP/service，数据库为独立的 `turb_dev.test_team_ui_20261127_783f2a6d`，账号与工作区全部为合成数据。未使用整份假 DTO 服务替代真实接口。

运行模式为 `web`，不启动执行 worker；远端认证、请求和执行边界明确阻断。写入仅发生在此合成 schema；为展示异步阶段，只对指定合成 Probe 推进读模型、对指定 Team 固定名单执行一次本地准备。

预览中的受理回执、排队任务和合成探测结果不构成远端邀请、自动接受或生产部署验收。原后端的组合测试、预检性能和真实单账号限制见[后端验收记录](2026-11-27-team-backend-acceptance.md)。

## 浏览器结果

使用 Playwright 操作实际页面，已验证：

- 工作区列表、详情、成员与严格六列邀请列表，未知计数和归档标记正确。
- 母号跳账号详情：已确认加入且归档的账号进入 Team 视图，未确认加入的归档母号进入归档视图。
- 候选密码筛选 GET 200；邮箱与 ID 混合解析、重复目标去重、其他 Team 与缺认证材料跳过。
- 显式账号预检与加入 POST 202，生成请求 `#5`；显示准备状态和待处理数量，不显示为已加入。
- 账号页筛选 `ID:10`，创建固定名单 `#1`；本地一次性准备后以 `selection_revision: 1` 提交，POST 202 生成请求 `#6`，未重新筛选。
- 没有已购席位和本地上限时禁止确认；设置上限 PATCH 200 后重新预检，未知占用仍显示待同步。
- 已满 Team 显示等待可用席位提示，按契约继续允许受理，没有发送该 Team 的加入请求。
- 绑定探测 POST 202；指定合成 Probe 推进后，唯一可管理工作区默认预选。确认绑定 POST 201 创建 Team `#4`，首次同步 Task/Run `#14` 排队。
- 更换母号 PATCH 200，原工作区 ID 保持 `preview-binding-probe-4`，更新为指定归档母号 `#21`。
- 绑定弹窗搜索未同步母号 `#3`，显示独立的本地管理母号及 Team 名称。
- 「查看相关任务」真实请求携带精确 `team_id=4`，GET 200；返回菜单和账号深链可用。
- 邀请页「继续加入」POST 202，并读取实际持久请求回执。
- 有排队任务时进入详情再返回列表、手动刷新，刷新与每页条数控件均恢复可用，表格 `aria-busy=false`。
- Tab 焦点保留在弹窗内，Escape 可关闭；390×844 窄屏没有文档横向溢出。

最新产物验收期间，捕获的页面异常与 API 失败响应均为零。初始旧产物的 `capacity.blocking_reason_code` 错误曾实际复现，修复后不再出现，未将其历史日志计为新产物错误。

本地截图位于忽略目录 `output/playwright/team-*-20261127.png`；脱敏 HTTP 观察、名单准备与合成 Probe 结果位于 `logs/run/diagnostics/team-ui-integration-20261127/`，不包含真实认证材料。

验收后已关闭两个自建浏览器会话，干净停止预览进程并确认 18027 无监听。仅删除本次合成测试 schema，随后只读确认其不存在；既有两个真实单账号验收 schema 保留。脚本、截图与证据文件均保留。

## 保留的未达项

10,000 目标的完整预检 P95 仍为 56.510ms，带完整邮箱快照为 77.699ms，未达到 50ms 目标。真实自动接受 POST 尚未验收；此前仅发送一次真实邀请，没有为前端验收再邀请账号。
