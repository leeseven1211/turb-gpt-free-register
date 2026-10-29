# 2026-10-29 mail-pipeline 印地语验证码模板补充

## 根因与范围

Roxy 原任务 `8456`、`8458`、`8459` 各有三封邮件及时进入 Butler 缓存。
本地与 Butler 的完整邮箱身份、固定最终收件箱一致，九封邮件的收件地址均匹配，
但缓存 `otp` 全为空。邮件来自 OpenAI 域，使用印地语 ChatGPT 验证码模板，
正文各含一个 ASCII 六位数字；旧解析器没有识别模板中的借词
`वेरिफिकेशन कोड` 或 `वेरिफ़िकेशन कोड`。

Butler 取码查询要求 `otp <> ''`，因此这些邮件未进入候选集合，多轮等待超时。
两条任务最后一轮另有 HTTP ReadTimeout，不是前两轮正常返回超时的根因。

本次仅在独立 `/srv/apps/mail-pipeline/parse.py` 的明确验证码关键词中增加
`वेरिफ़?िकेशन`，沿用原有 `कोड`、候选码和来源校验要求。Turb 注册驱动、
Butler 查询过滤、收件证据及时间窗口均未修改。维护入口继续使用已有
[离线准备工具](../../tools/prepare_mail_pipeline_otp_patch.py)和
[纯函数回归测试](../../tests/test_mail_pipeline_otp_patch.py)。

## 验证与源码保护

新增合成模板、含 nukta 的 NFD/MIME 正例和普通订单反例，先复现失败，
修复后九项相关 unittest 全部通过。生成待部署实际源码后再次运行同一测试集，
Ruff 和 `git diff --check` 通过。独立审查另外核对六组 Unicode 词形、
三组误匹配反例及八组未知漂移拒绝。

准备工具仅额外接受已核对的两个上一版本 SHA256：原准备结果
`0244461e4e5aea5253056b05ef31574898c9e4e4a73cba384c47ad323756de04`，
以及现网少一个末尾空行的
`cd06e1ca09b267b6ad31242897c2b826815ff0208e01a2bceff848a077206c5e`。
升级时恢复该空行；未知内容或部分修改继续拒绝，升级结果保持幂等。
AST 比较只有 `MARKER` 赋值变化。

通过既有只读邮件摘要接口，在内存中用待部署源码重解析九封邮件，
九封全部得到恰好一个六位候选；未输出验证码或邮件正文，未回填历史缓存。

## 发布证据

代码提交为本机 main 的 `8e9f217`，未推送。
北京时间 2026-10-29 20:22:22，仅重启 `mail-pipeline.service`，
新 PID `1945138`，状态 `active/running`，`NRestarts=0`。

单文件原始备份为
`/srv/apps/mail-pipeline/parse.py.bak-20261029T122213Z-hindi-otp`，
备份 SHA256 与旧部署值一致。新 `parse.py` SHA256 为
`f3b0cf6dcf7f29f602c4ec13b3a7a23055f52e6e215db8eb17c15714dab38cc2`，
权限保留 `0664`。`pipeline.py` 未变，SHA256 为
`c35cf26a3a789b81d77e1a3ae24e7e32aa8a69a8f6ff0f49c3b0f5830ae54b86`。

Butler PID `1243322` 未变，`/api/health` 返回 HTTP 200、`status=ok`。
mail-pipeline 启动日志没有 Python traceback、语法或导入异常，
部署后独立进程加载实际解析文件，两组印地语合成模板均通过。

本次没有修改生产数据库或旧邮件缓存，也没有重跑注册任务。
历史空 OTP 不会因服务重启自动补齐；新邮件采用新解析规则。
上述只读解析验收不等于注册流程端到端成功。

发布后只读观察调用方已有任务 `8648`：补丁前北京时间 20:21:59 入站的
`pg:18795` 仍为 `has_otp=false`；补丁后重发邮件于 20:23:29 入站，
`pg:18796` 已为 `has_otp=true`，验证新邮件完成入库解析。
观察时任务仍在 `running/email_otp`，不据此宣称注册成功。
