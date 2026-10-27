# 子邮箱统一由 Email Butler 管理

用户授权：把子邮箱功能迁入 Email Butler，Turb 只导入、领取、使用邮箱；延续已授权的生产部署。

Butler 成为生成、累计额度、库存、原子分配和恢复的权威。新增 HME 子地址默认每母累计 3 个、随机后缀 6 位。母地址已登记服务不妨碍生成新子地址；来源停用、排除或固定路由缺失时禁止新生成。历史数量超过额度保留事实，剩余额度为零。现有 Butler Outlook 默认别名机制继续由 Butler 管理，Turb 不再生成 Outlook 子地址；既有 MailCom 行为必须保留。

HME 使用 PostgreSQL 独立权威账本：完整地址唯一、稳定母身份、累计额度、生成请求指纹与不可变结果、认证客户端范围的 acquisition 与 owner、结果 operation ID。生成和领取使用真实数据库事务/锁。零生成也保存幂等结果。同请求不同参数或 owner 拒绝。TTL、失败、未知结果、删除展示行不能让已发行地址重新成为新库存。旧 accounts/runtime 快照写回不能回滚权威状态。

沿用 POST /v1/mailboxes，响应包含 identity_type、完整地址、父身份及固定 mailbox。HME 继续 forwarded_exact_v1 严格原始收件证据。管理生成/策略只允许现有管理端或显式管理 capability；consumer 身份来自认证 Key，不能被请求 body 冒充。

Turb 在网络调用前持久保存领取意图；请求超时、断连、成功响应不可解析均保留 request_unknown，仅用原 acquisition 恢复。所有注册入口、CLI 和换绑贯通稳定 owner/acquisition。新远程子地址按完整地址启用已有 OTP fence，binding_id 可空，不伪造本地母地址或 allocation。历史 192 个 HME 子地址（144 used、48 reserved）、原 source/owner/profile、全部 OTP 未知结果与历史状态原样保留，仅导入 Butler 权威事实，不能重新发放。没有 Outlook 本地历史 allocation。

Turb 删除可编辑生成策略和生成/改库存入口，保留历史只读记录及邮箱导入使用能力。旧 API 明确告知去 Butler 管理。所有来源禁止新本地生成，旧已保存请求仍可恢复。Butler 在既有界面提供子地址库存、策略、生成入口，沿用视觉规范、清晰反馈及表单标签。

测试仅用 mail_prepare_20261027 与独立临时 schema；不得在生产 public 测试。验证多进程并发额度/领取、重启/未知恢复、旧快照写回、严格母子收码隔离、Outlook/MailCom 回归。Oracle 发布以最新现网文件最小合成，保留备份和哈希；Turb 只在任务空闲窗口重启。不 push，不删除用户资料，禁止 rm -r。
