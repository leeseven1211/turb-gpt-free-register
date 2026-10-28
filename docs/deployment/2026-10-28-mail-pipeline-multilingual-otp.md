# 2026-10-28 mail-pipeline 多语言验证码

## 故障与修改范围

Gmail 已收到越南语登录验证码，但 Oracle 独立 `mail-pipeline` 的
`parse.py` 仅有中英文语义标记，入库 `otp` 为空。Butler 邮件列表直接读
IMAP，所以能显示邮件；`/v1/inbound/code` 只查询有验证码的入站记录，最终超时。

修复针对 Oracle `/srv/apps/mail-pipeline/parse.py`，不是 Turb 收件客户端或
Butler 独立 Gmail worker。该服务目录没有 Git；本仓库保存可复现的
[离线准备工具](../../tools/prepare_mail_pipeline_otp_patch.py)、
[无配置和私密数据的源码基线](../../tests/fixtures/mail_pipeline_parse_baseline.py.txt)
以及[回归测试](../../tests/test_mail_pipeline_otp_patch.py)。

基线 SHA256 为
`2c4531ee7fb51920744ede6aec4eb2cb1b135cb1c21db550e646974a6b3186b6`，
准备结果 SHA256 为
`0244461e4e5aea5253056b05ef31574898c9e4e4a73cba384c47ad323756de04`。
准备器拒绝未知或部分修改的源码；同版本再次准备保持幂等。

## 语言及边界

明确的验证码、验证、认证、安全或登录提示覆盖中文（简繁）、英语、越南语、
日语、韩语、法语、德语、西班牙语、葡萄牙语、意大利语、荷兰语、波兰语、
土耳其语、俄语、乌克兰语、捷克语、罗马尼亚语、匈牙利语、希腊语、瑞典语、
挪威语、丹麦语、芬兰语、印尼语、马来语、泰语、印地语、阿拉伯语、希伯来语、
菲律宾语。这里表示测试过的明确提示词，不代表这些语言的所有邮件模板。

同时做 NFC Unicode 规范化，兼容拆分重音和韩文字母；修正候选码的数字前瞻，
确保数字属于候选码自身，避免德语 `lautet`、印尼语 `Anda` 等普通单词借用
后续数字成为无效候选，吞掉真正的验证码。

没有任意数字兜底；单独产品名加普通 `code` 不能证明验证码语义。保留 URL、
新闻订阅防护、代码长度和距离上限，来源、收件证据、UID、事务与通知逻辑保持
原样。普通订单、金额、邮编、优惠码、新闻引用及超长数字均有拒绝测试。
不新增验证码在提示词前的倒装识别，也不将其他数字字形转换成 ASCII 代码。

## 离线验证与部署

```bash
.venv/bin/python -m unittest tests.test_mail_pipeline_otp_patch -v
.venv/bin/python tools/prepare_mail_pipeline_otp_patch.py \
  --source /审计目录/parse.py \
  --output /审计目录/parse.prepared.py
```

输出路径必须不存在；不覆盖源文件，也不连接邮件、数据库或远端。测试使用
生产纯函数基线和合成邮件，包含 MIME 编码、拆分 Unicode、误取、幂等及漂移保护。
修改前测试先复现失败，修改后验证通过。

发布前核对当前源码 SHA256，保留原文件备份与权限，原子替换单个 `parse.py`，
仅重启 `mail-pipeline.service`。检查实际进程、源码哈希、启动日志及 Butler
健康接口。`pipeline.py` 与 Butler API 不需要替换或重启。

已入库 UID 的 `ON CONFLICT DO NOTHING` 保留，重启不会重新解析历史空 OTP。
新邮件走新规则；历史真实邮件可只读验证解析结果，但不能把这项验证说成历史
缓存已补码或完整登录已成功。不直接修改生产数据库，不重开已结束的 607 批任务。
