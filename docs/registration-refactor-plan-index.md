# 注册流程重构文档包

这是后续并行开发的入口。当前只完成设计和实施计划，未修改业务代码、数据库和运行时数据。

## 阅读顺序

1. [registration-refactor-master-design.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/registration-refactor-master-design.md)  
   统一架构、Roxy 主流程 + Protocol 辅助、状态模型、诊断和性能目标。
2. [registration-implementation-plan.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/registration-implementation-plan.md)  
   阶段拆解、依赖、交付顺序和每阶段完成标准。
3. [registration-parallel-workstreams.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/registration-parallel-workstreams.md)  
   五个开发窗口的认领边界、文件范围、禁止修改项和验收条件。
4. [registration-test-migration-rollout.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/registration-test-migration-rollout.md)  
   测试、数据库迁移、灰度投产、回滚和最终验证。

## 权威口径

本文档包对后续注册重构的新增口径优先级最高：

```text
Roxy = 注册主流程
Protocol = Roxy 流程中的阶段级辅助和加速通道
```

不要把 Roxy 和 Protocol 实现成两套互相独立的注册任务。Protocol 失败时优先在同一个 Roxy 会话中恢复或使用 Roxy 页面 fallback；一旦越过不可逆检查点，不允许自动启动另一套新注册流程。

## 现有文档的使用方式

- [core-registration-flow.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/core-registration-flow.md)：当前实现基线，开发前用于确认现状。
- [registration-state-refactor-design.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/registration-state-refactor-design.md)：已有状态/恢复设计，本文档包将其细化为可实施任务。
- [unified-task-center-architecture.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/unified-task-center-architecture.md)：统一任务中心基础设计，本文档包补充死锁修复和异步投影要求。
- [refactor-roadmap.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/refactor-roadmap.md)：既有项目结构整理路线图；其中历史驱动清单以本文档包的正式支持范围为准。

## 开发窗口启动前必须确认

- 使用独立分支或 worktree。
- 存储改动使用独立开发数据库。
- 不修改 `.env`、账号、Token、邮箱池、日志、`run/`、`.venv/`。
- 不执行 `rm -r` / `rm -rf`。
- 先认领 [registration-parallel-workstreams.md](/Users/lihongwei/code/personal/gpt/turb-gpt-free-register/docs/registration-parallel-workstreams.md) 中的一个工作流。
- 先提交契约测试，再接入实现。
