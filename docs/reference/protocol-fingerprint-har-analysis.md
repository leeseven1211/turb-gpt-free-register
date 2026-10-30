# 协议会话与 HAR 排查参考

本页保留可复用的会话一致性和协议定位方法。历史抓包、逐条请求 JSON、固定前端 build 和单次后端评估从当前文档移除，需追溯时使用 Git 历史；它们不能定义服务端当前行为。

## 代码入口

| 关注点 | 实现 |
| --- | --- |
| 浏览器环境画像、语言、时区和 TLS 档位选择 | [config/browser.py](../../config/browser.py) |
| HTTP 会话、请求头和阶段预算 | [auth/protocol/session.py](../../core/auth/protocol/session.py) |
| ChatGPT 匿名及登录态预热 | [auth/protocol/chatgpt_bootstrap.py](../../core/auth/protocol/chatgpt_bootstrap.py) |
| NextAuth、授权跳转与账号认证 | [auth/protocol/chatgpt_auth.py](../../core/auth/protocol/chatgpt_auth.py)、[openai_auth.py](../../core/auth/protocol/openai_auth.py) |
| Sentinel 和 Node 执行器 | [sentinel.py](../../core/auth/protocol/sentinel.py)、[sentinel_runner.py](../../core/auth/protocol/sentinel_runner.py) |
| 任务网络诊断和 HAR | [registration/debug.py](../../core/registration/debug.py) |
| 离线抓包摘要工具 | [analyze_har_protocol.py](../../tools/diagnostics/analyze_har_protocol.py) |

## 会话一致性

同一个 `BrowserSession` 的设备 ID、Cookie、UA、语言、时区、屏幕和 JS 环境应相互一致；不同会话可以采用各自画像。HTTP 头、Python Sentinel 参数和 Node runner 的环境必须沿同一会话传递。

UA 声明与实际 TLS 模拟能力是不同层次。`resolve_impersonate()` 按已安装的 `curl_cffi` 支持档位解析，不能仅修改 UA 就声称实际使用了对应 TLS 指纹。GeoIP、地区、语言和时区也应记录来源；兜底配置不能当作实际出口检测成功。

JS `Date.getTimezoneOffset()` 采用西区为正、东区为负的分钟数；不要直接混用内部地理时区偏移。NextAuth 请求头与 ChatGPT 业务 API 请求头分别由会话接口生成，不把所有头无条件复制到每个域名。

## 链路判断

排查时区分预检、可选 bootstrap、NextAuth providers/CSRF/signin、Auth 挑战、资料提交、回调与 session 获取。驱动可能遇到密码、MFA、邮箱 OTP 或已认证跳转，实际顺序以当前驱动和同一 Run 的事件为准，不能照历史 HAR 强制补发请求。

Sentinel challenge、请求 token 和 Cookie 均有各自作用域与生命周期。历史样本是否携带某个头，仅是该样本的证据；不能据此推广所有驱动或服务端版本。预热不是注册成功证据，遥测请求也不能用来推断账号优惠或风控因果。

远端写请求超时、回调结果未知与明确拒绝要分别记录。诊断不能触发自动重放；恢复边界见[注册流程](../workflows/registration.md)。

## 离线摘要

原始 HAR 放在私有目录，显式把摘要输出到已忽略的运行目录：

```bash
mkdir -p logs/run/diagnostics
python tools/diagnostics/analyze_har_protocol.py /path/to/capture.har \
  --output logs/run/diagnostics/protocol-har-summary.json
```

工具只解析本地文件。它仍兼容默认输出 `docs/reference/protocol-har-summary.json`，该生成物不再跟踪；源码注释里的旧摘要名指历史分析产物。摘要可能携带请求地址、头部和指纹信息，分享前检查并脱敏，不提交原始会话数据。

对照时固定代码版本、依赖、会话和出口条件，分别记录请求顺序、错误、耗时与样本范围。一次成功、单次时延或离线后端探针不能替代真实注册、长期稳定性或优惠资格验证。
