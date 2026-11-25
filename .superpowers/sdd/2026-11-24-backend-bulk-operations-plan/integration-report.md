# Task 7 批量命令运行集成

实现提交 `1b1c26ea`。Web 只登记命令定义、接受并持久化命令。Worker 在启动现有 dispatcher 前单独登记执行处理器。两者共用领域注册的参数定义。批量命令状态进入现有 Worker readiness 及持久心跳，展示排队和活动数。

- `GET /api/bulk-mutations/<command_id>` 在同一个 PostgreSQL 快照中读取当前 Run、总计及分页结果。每页默认 500 条，最多 5,000 条。命令、任务、Run、目标及回执中已知的整数 ID 以十进制字符串返回。
- Codex 和邮箱批量路由用 HTTP 202 返回持久命令，同键异内容返回带错误码的 HTTP 409。
- 启动及周期恢复先按既有机制收口孤儿 Run。未取消且没有活动执行许可或有效租约的已注册命令，为同一 Task 新建一个 Run。Run 通过正常执行准入和结算，复用既有命令的已提交块。
- 提链模块和两个补充路由在独立实施提交中接入同一 registry 和冻结路由快照。

隔离 PostgreSQL 的 `tools/test_isolated.py --profile all` 定向组合为 52 passed、25 subtests passed。覆盖 5,001 条分页、大整数 ID、两个领域的 202/409、独立 Web/Worker 装配、公开路由快照以及命令恢复。恢复测试合成进程退出与超时心跳，使用真实 PostgreSQL 状态转换、执行许可和结算检查新 Run，两个非幂等计数器的提交各一次。该测试没有启动或终止外部 Worker 进程，也没有等待真实失联超时。

回执 OpenAPI 由独立的 `contracts/bulk-mutations.openapi.json` 提供。`npm run generate:api` 和 `npm run check:api` 均退出 0。

追加验证覆盖 Worker 第三轮错误分流和提链注册的工作树集成。九个目标测试文件共 75 passed、25 subtests passed，pytest 82.10 秒。生成类型提交 `6e5d67c2`。

## 全站覆盖的后续整合

原七项集成后继续补齐全部按钮背后的本地集合准入、读取及写入，范围和外部边界详见 `docs/reports/2026-11-24-backend-bulk-coverage.md`。完整改造前按钮索引随 `a0dec812` 归档到仓库，不依赖本机 visualization 目录。

最终测试证据独立记录在 `docs/reports/2026-11-24-backend-bulk-validation.md`：主 agent 跨域 PostgreSQL 组合为 231 passed / 76 subtests passed，前端完整门 92 files / 1,099 tests 和构建通过。组合存在重叠，不相加作为唯一测试总数。任务中心混合来源受理的后续回归以该验证记录的最终附录为准。

任务中心终止现使用 `task_terminate_bulk` 持久控制命令，受理 HTTP 202 后由 Worker 沿原 Run 安全结算。它明确保留每个真实执行的结算事务及恢复回执；普通 bulk mutation 的业务事实与块回执仍是同一事务。Web 安装元数据，Worker 安装 handler，集合原语保留调用方提交权。

当前所有验证均在隔离测试库及合成数据内完成，尚未推送、合并、部署或执行真实业务写入。
