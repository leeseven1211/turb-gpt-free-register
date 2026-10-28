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

## 本次发布结果

准备工具和回归源码已提交本机 main：`a06dc6b`，未推送远端。
新增 8 项测试通过，包含 36 个多语言正例模板在主题和正文中的取码验证；
独立审查核对源码哈希、AST 范围及产品优惠码误取反例后通过。
精确保留生产基线原始字节，包括文件末尾空行，便于核对源码 SHA256。

北京时间 2026-10-28 14:55:10 发布单文件并重启 `mail-pipeline.service`，
PID 为 `3802698`，状态 active。现网 `parse.py` 哈希与准备结果一致；
`pipeline.py` 哈希仍为
`18b13a8bf50d134f973f8ccb021d43ff529c4bb1338806c3428674dcc39190bb`。
原文件备份为 `/srv/apps/mail-pipeline/parse.py.bak-20261028-multilingual-otp`。
Butler PID `3730505` 保持运行，`/api/health` 返回 HTTP 200、status=ok，
writer 启动后没有 Python 导入或语法异常。

只读取得 3 封真实越南语邮件的 HTTP 正文并做解析比对：旧解析器候选均为 0，
发布版本均得到 1 个与正文可见六位码一致的候选。没有输出验证码，
这项验证不等于读取了原始 MIME 或回填了历史缓存。

部署后对原失败账号执行一次 AT 重跑，Run `266500` 于北京时间 14:56:54
成功结束；该 Run 的 `email_otp`、`authenticate`、`token` 事件均为 success，
已实际验收新邮件入库、取码与 AT 刷新链路。没有重复提交整批任务。

随后为该账号提交单次套餐查询，Run `266501` 于北京时间 14:59:22 成功结束：
套餐为 `free`，3/3 个国家查询成功，无 Plus 试用或折扣资格。

额外检查的两个既有 Turb 客户端/桥接测试模块并非全绿：在 `turb_dev` 的
一次性隔离 schema 中，37 项中 22 项通过、15 项失败。12 项仍只 mock 旧远端
领号接口、没有播种现行契约所需的本地库存；3 项仍期待恢复时重新远端领号，
与当前缺少固定身份时返回 `lease_restore_required` 的契约不符。
这些模块和运行代码未在本次修改；新增解析测试独立通过，真实流程也已成功。
