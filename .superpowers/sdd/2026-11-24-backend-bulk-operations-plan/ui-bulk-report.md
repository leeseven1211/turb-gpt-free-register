# 异步批量命令前端兼容回执

2026-11-24，负责 `impl_ui_bulk_receipts`。

## 实现

- 新增 `frontend/src/api/bulkMutations.ts`：一次 POST，收到 accepted/reused + command_id 后仅 GET 查询，默认 750ms 间隔、30 秒有界等待。终态支持 success、partial_success、failed、cancelled、interrupted、terminated；按 next_offset 获取最终全部分页后才解析回执。
- 支持 AbortSignal；查询失败、超时、取消等待统一保留 command ID，以 BulkMutationPendingError 明确提示“已受理，仍在执行或等待结果确认，勿重复提交”。不会自动重发 POST，也不会用尚在执行中的 items 假报完成。
- 每次独立调用生成随机 Idempotency-Key；调用者可显式传入 idempotencyKey 以复用同一用户意图。账号请求同步发送 X-Account-Request-Key 以兼容后端既有约定。
- 精确解析 command/task/run/target bigint 字段；账号选择与请求支持大整数文本，避免 Number 取整。账号 deps.request 仍保持依赖注入，须由后端查询返回字符串身份（已与集成 agent 协调）。
- 将最终 item.status=updated 投影为既有 updated/deleted，skipped/failed 保留身份与原因。账号、Codex、邮箱只清除成功且属于本次请求的选择。
- Codex 批量归档/删除改为适配器薄封装，提供 resetBulk API；保留原来的单项操作与 OAuth 异步任务契约。
- 邮箱 createEmailApi 全程使用注入 send；useEmailInventory 保留失败选择、在执行期间显示受理状态、查询不可用时以 warning 显示命令 ID。
- 账号异步邮箱失效标记只清成功项；同步旧响应保留既有行为。账号 note 暂无 Vue UI 入口，通用适配器可供后续入口使用。

## 验证

按 TDD 增加直接测试，观察缺失实现导致的失败，再实现并验证。最后运行：

```
cd frontend
npm test -- src/api/bulkMutations.test.ts src/api/codex.test.ts src/api/email.test.ts src/features/accounts/localMutations.test.ts src/features/email/useEmailInventory.test.ts src/features/codex/actions.test.ts
npm run typecheck
git diff --check
```

覆盖：202 不算完成、running 轮询、分页全部读取、partial_success/failed 逐项投影、大整数、独立意图幂等键、外部取消、查询失败、挂起请求超时、超时后迟到结果不再分页、无逐项回执不假报成功、选择保留、刷新失败不重发。

最终结果：6 个直接测试文件、112 tests 全通过；vue-tsc --noEmit 通过；git diff --check 通过。

依赖通过 `npm ci --ignore-scripts --no-audit --no-fund` 安装，未改 package-lock。未跑全前端测试、未部署或构建发布资源。

## 移交

- `frontend/src/features/extract/useExtractWorkbench.ts:97` 仍对所选任务逐项 POST `api.action(id,'sync_status')`，交由主线程/Task 6 收口。`:95` 支付链接为逐项 GET，只读。
- 账号执行类 `setupActions.ts`、`queuedActions.ts` 已采用数组 POST 到对应 bulk 路由，无逐项 POST 循环。
- 所有等待超过 30 秒的命令保留原选择，用户可在任务中心查看执行结果；此改动不增加新的后台常驻前端轮询流程。
- 后端 GET 默认页 500，next_offset=null 表示结束；前端支持显式后续分页。已提醒集成 agent 将 command/task/run 及账号 key/data.id 序列化为规范字符串。
- 主线程仍需进行统一前后端契约验证与浏览器验收。
