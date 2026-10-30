# 部署与运维

本文保留可重复执行的升级、配置迁移和回滚步骤。安装与启动见[README](../../README.md)，验证范围见[发布与验证](../development/release-verification.md)，邮箱库存与收件规则见[邮箱资源](../workflows/email-resources.md)。历史发布记录、版本和验收数字通过 Git 历史回查，不作为当前服务状态。

## 升级与服务切换

1. 核对目标提交、实际工作目录、已有用户修改和进程管理方式；保存 PostgreSQL、启动配置、配置加密主密钥及相关迁移回执的备份。
2. 只读检查排队、执行中的任务和有效资源租约，在空闲窗口重复确认。`request_unknown` 和未确认远端 checkpoint 应单独保留身份与证据，不能当作失败清理或为了部署重跑。
3. 暂停原进程管理器的自动拉起，停止旧服务，确认监听端口关闭后再切换文件或执行迁移。保留用户未提交修改，不让两个实例同时加载不同版本。
4. 恢复原托管配置，核对新进程 PID、工作目录、监听端口和本次启动后的新增日志，再检查健康、就绪和登录。若切换失败，应先恢复完整的代码与配置，再恢复服务。

### 启动方式

已有 `launchd` / `systemd` 托管时，以该服务实际的工作目录、启动参数和环境为准。先查看对应服务的配置与状态；维护期间暂停自动拉起，完成后恢复同一个服务。仅停止子进程可能被托管器立即拉起，不能保证已停机。不要在托管服务旁另行执行手动 `start` 或 `restart`。

手动管理的实例使用项目入口，端口按实际部署指定：

```bash
PORT=8000 ./webui.sh status
PORT=8000 ./webui.sh check
PORT=8000 ./webui.sh start
PORT=8000 ./webui.sh stop
```

`webui.sh` 不加载 `.env`；`HOST`、`PORT`、`TASK_RUN_LOG_ROOT` 等启动覆盖由服务环境或命令行提供。运行配置和 API Key 在 WebUI 配置页管理。

### 启动后的核验

- 实际 PID、cwd 和监听端口对应目标部署；保存提交与是否推送的事实。
- 检查本次启动后的日志段，避免把旧错误当作本次启动失败；输出仅保留排障必要字段。
- `GET /healthz` 检查进程存活，`GET /readyz` 检查数据库和必需 worker；前者成功不能代替后者。
- `GET /login` 及授权后的相关页面正常。WebUI 资源变更后强制刷新，核对资源版本、请求和浏览器控制台。
- 业务状态需另按 PostgreSQL 中的任务、run、事件和远端回执核对；健康检查通过不代表真实注册、收码或提链已经成功。

## 配置备份与迁移

运行配置保存在 PostgreSQL 的加密配置表中，`.env` 保留数据库连接、WebUI 授权、稳定部署身份和加密主密钥。备份必须成套保留数据库、`.env`、`TURB_CONFIG_ENCRYPTION_KEY` 以及迁移前的原 `.env` 备份。保留原 `TURB_MAIL_CONSUMER_ID`，不能通过重建消费者改变既有邮箱归属。

旧部署需要显式迁入配置数据库时，先只读预览：

```bash
python tools/migrations/migrate_runtime_config.py --source-root . --dry-run
```

在业务空闲、托管已暂停、服务已停止且数据库完成备份后执行：

```bash
python tools/migrations/migrate_runtime_config.py --source-root . --apply
```

`--source-root` 指向实际部署目录，不应误指另一个工作树。也可用 `--backup-dir` 指定私有备份位置；默认在源目录的 `logs/run/runtime-config-backups/`。

- dry-run 不连接数据库、不建表、不生成主密钥，也不改源文件。
- apply 先以受限权限备份原 `.env`，保存或复用主密钥，再加密写入并核对全部显式值；成功后才精简 `.env`。
- 已有不同的数据库值不会被旧文件覆盖；冲突和失败保留原始资料，重复执行可完成中断后的文件精简。
- 主密钥缺失、错误或数据库不可用时明确失败，不回退到旧运行配置。不要重新生成主密钥来处理解密错误。

回退旧版代码前先停止服务，按同一备份恢复数据库与配置。密文数据库和主密钥不匹配时无法恢复配置；只回退代码可能让旧文件中的参数重新生效。存储模型与原子性见[运行配置与启动配置](../architecture/storage-architecture.md#运行配置与启动配置)。

## 历史 HME 固定路由迁移

已有 IMAP profile 需要切换为 Butler 时，使用显式迁移工具，不直接改表。迁移前备份数据库、固定 profile、对应凭据版本及配置，并确认目标 Butler 能力与最终收件箱；严格收件约束见[邮箱资源](../workflows/email-resources.md)。

```bash
# 默认只读预览
python tools/migrations/migrate_hme_inbox_to_butler.py

# 写入并保存回执：路径必须尚未存在，实际执行使用本次独立文件名
mkdir -p logs/run
python tools/migrations/migrate_hme_inbox_to_butler.py --apply --receipt logs/run/hme-butler-cutover.json

# 只读预览回滚
python tools/migrations/migrate_hme_inbox_to_butler.py --rollback logs/run/hme-butler-cutover.json

# 按同一回执执行回滚
python tools/migrations/migrate_hme_inbox_to_butler.py --apply --rollback logs/run/hme-butler-cutover.json
```

无固定 profile、仍依赖全局配置的旧母资源，可先显式加 `--include-unpinned-parents` 预览；执行时同样需要 `--apply --receipt`。工具保留已有其他连接器，不批量改写完整业务地址、历史归属或使用状态。

回执记录原路由映射，必须私有保存。回滚只恢复回执覆盖的路由引用，不回收 Butler 的永久交接归属。原 profile 和版本化 `credential_ref` 仍可能被历史任务、取码和待发送结果回执引用，不能随文档或旧代码一起清理。

## Oracle 邮箱服务的维护边界

Turb 是 Butler 的消费端；Oracle 上 Butler、mail-pipeline、iCloud sidecar 和补库任务的部署，应在对应仓库按现网版本核对。不要照搬本仓库旧准备文档的迁移序号、源码版本、服务状态或库存数量。

升级远端服务时，先备份其数据库、源码和配置，核对增量迁移依赖与现网差异，保留已有 MailCom、通知和 outbox 职责；不能以只写验证码缓存的新 worker 覆盖原入库链路。两个入库者不应未经核对争用同一游标或重复发送通知。

端到端验收应区分本地配置、HTTP 能力、原始邮件证据、固定收件匹配、到达时间及真实新邮件投递。旧缓存只读查询或合成 MIME 测试不能替代真实投递时延和母子地址隔离验收。凭据、邮件正文、OTP 和私有回执不进入文档或提交。
