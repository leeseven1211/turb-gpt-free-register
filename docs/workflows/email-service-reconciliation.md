# 永久服务标签与历史读取绑定对账

凡成功导入 Turb 的完整地址，永久具有 `openai` 标签；退号、删除及换绑不撤销事实。标签不代表注册成功，不增加成功次数。具体规则见[设计说明](../superpowers/specs/2026-11-07-email-service-facts-design.md)。

## 对账边界

`tools/maintenance/reconcile_butler_service_facts.py` 以数据库只读事务读取现存账号、邮箱池（含删除留痕）、历史领取、分配、成功导入项，以及明确完成注册的 attempt。完整 plus 地址独立处理。仅补事实，不重新领取、续租、退号或修改成功次数；Butler 无收件素材的地址也可以保存独立事实。

`tools/maintenance/reconcile_butler_read_bindings.py` 只从原固定 `forward_butler` profile、具体地址引用及对应凭据生成读取绑定；排除本地删除留痕，缺失或冲突的路由必须先解决。绑定不提供领取、续租或报告权限。迁移前应核对原完整地址在 Butler 中存在、最终收件箱一致且没有显式退号；不得根据全局默认收件箱猜测历史路由。

两个工具默认只读预览。回执只包含数量、哈希及必要引用，不保存 API Key 或邮件正文。回执位于私有运行目录，不得提交。

## 预览与执行

先停止任务提交，在两端 Turb 的空闲维护窗口固定源数据，备份后执行。`--source-timezone` 必须依据该实例记录无时区时间时的原运行时区，不按部署机器所在地猜测；带时区的原时间保持原意义。

```bash
python tools/maintenance/reconcile_butler_service_facts.py \
  --source-root /path/to/turb --source-instance turb-local \
  --source-timezone Asia/Shanghai --receipt /private/facts-preview.json

python tools/maintenance/reconcile_butler_read_bindings.py \
  --source-root /path/to/turb --source-instance turb-local \
  --receipt /private/reads-preview.json
```

事实接口要求当前 Key 的 `service=openai`，并具有 `service_facts.permanent.v1` 和 `service_facts.reconcile.v1` 能力。读取绑定接口另外要求 `service_read_bindings.reconcile.v1`。日常导入仅需永久事实写入能力；对账结束后应撤销临时对账能力，保留原有其他权限。

执行时沿用全部源参数，另传 `--apply --expected-facts N --expected-manifest SHA256` 或 `--apply --expected-bindings N --expected-manifest SHA256`，数量和哈希必须来自本次预览。读取绑定在每批发送前再次读取源数据；变化即停止。应使用新的执行回执路径保留预览证据，部分失败可重跑原证据，不伪造新业务操作。

维护窗口可用 `--transport-base http://127.0.0.1:8789/v1` 访问尚未公开的新 Butler 服务；仅接受本机回环地址，仍使用原固定 Key 验证客户端。公开服务停机期间不能同时运行旧、新写进程。

## 验证与回滚

补标前后比对当前 owner、lease、fence、邮箱状态及使用计数，确认不变；逐项确认永久回执及注册证据回执。Butler 的旧归属迁移脚本只凭已登记的原始事实补服务维度，未决项必须归零后才启动公开服务。

启用多服务归属后，旧版单归属代码不能直接回滚。回滚须停止写入，使用兼容版本或恢复成套已核验备份。历史证据范围仅限现存持久记录，没有记录的早期物理删除不能凭推测恢复。
