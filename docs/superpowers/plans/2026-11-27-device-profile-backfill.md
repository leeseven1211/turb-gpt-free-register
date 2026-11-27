# 历史设备画像补缺实施计划

> 本计划通过分工实施、隔离测试与独立审查完成；生产应用由主代理在两端备份后统一执行。

**目标：** 只从已有私有协议会话提取完整设备字段，补齐没有设备行的账号。

**架构：** 默认只读扫描，生成固定私有 manifest；显式 apply 校验实例、源版本、账号邮箱及目标缺失，单事务仅插入。沿用设备表现有加密包络，不修改普通存储模块，不重放 Cookie。

**技术栈：** Python、psycopg、Fernet、隔离 PostgreSQL schema。

**依据：** 主代理当前授权设计及 [设备画像方案](../../architecture/device-profile-reuse.md) 的历史来源与采集边界。

## 约束

- 仅补 `account_device_profiles` 缺失行，任何已有行均保留。
- 只消费 `account_protocol_sessions`，包括过期行的设备资料；不恢复会话、Cookie、TTL。
- 完整性沿用现有六个基础画像字段；不生成或修正设备值。
- 账号与密文内部邮箱、ID、版本都须匹配；不消费 legacy extra。
- 私有 manifest/receipt 权限为 `0600`，不输出邮箱、设备、Cookie 或原始画像。
- 缺表明确失败，不在工具中初始化业务 schema。
- 测试继承 `PostgresTestCase`，使用 `turb_dev` 独立 `test_` schema。

## 任务

### 1. 隔离回归

- [x] 新建 `tests/storage/test_device_profile_backfill.py`。
- [x] 证明默认 dry-run 不写数据；过期完整来源可补缺且不复制 Cookie。
- [x] 证明邮箱/源变更会跳过，已有行和迟到新增行不覆盖。
- [x] 证明 manifest 跨实例、篡改及不完整来源被拒绝或分类。
- [x] 观察缺少实现时测试失败。

### 2. 最小运维工具

- [x] 新建 `tools/migrations/backfill_account_device_profiles.py`。
- [x] 实现只读扫描、固定清单、事务内重新校验、加密插入及私有回执。
- [x] 证明相同 manifest 再次 apply 无新增；新 dry-run 候选为零。
- [x] 运行直接相关隔离回归、语法和空白检查。
- [x] 独立审查后冻结，交主代理统一提交、备份及两端生产应用。

2026-11-28：`turb_dev` 独立 `test_` schema 的新增迁移测试与设备存储测试共 19/19 通过。生产护栏同时校验声明库名、连接后的实际库名和实例显式授权；测试进程不允许生产库。尚未提交、推送、部署或应用生产清单。

## 运维使用

默认执行只读 dry-run：

```bash
python tools/migrations/backfill_account_device_profiles.py \
  --source-root /实例目录 --source-instance local \
  --manifest /私有运行目录/device-profile-manifest.json \
  --receipt /私有运行目录/device-profile-dry-run.json
```

备份、审核固定清单后，显式应用同一份 manifest：

```bash
python tools/migrations/backfill_account_device_profiles.py \
  --source-root /实例目录 --source-instance local --apply \
  --manifest /私有运行目录/device-profile-manifest.json \
  --receipt /私有运行目录/device-profile-apply.json
```

本地与 Oracle 分别生成清单和应用，不迁移实例密钥或跨端业务数据。清单固定后出现的新候选不自动纳入；来源已变化的账号分类跳过，再生成清单处理。提交状态以数据库事务和回执核对；中断后可以重用同一清单，已有行会跳过。
