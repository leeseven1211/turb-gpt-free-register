# 幻光 XXSYUN 转单接入

## 目标与边界

在已有幻光自动支付上补齐截图中的 XXSYUN API Key、超时转单开关和剩余次数查询。幻光平台已经负责 90 秒未接单后的取消确认、退次与转单，本项目仅提交配置并同步返回状态，不增加本地计时器、取消任务或转单 worker。

## 配置与请求

新增 `EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY`（密码框、默认空）和 `EXTRACT_LINK_HUANGUANG_SCAN_FALLBACK_ENABLED`（默认关闭）。新建幻光自动支付任务时，开关开启且 Key 非空才提交 `scan_fallback_enabled` 与 `fallback_xxsyun_api_key`。缺少备用 Key 不阻断原有主通道自动支付；仅提链和手动支付不携带备用凭据。

Key 只存 `.env`，不进入任务快照、公开配置、日志或任务结果。常规进度 GET 沿用原任务密钥；平台返回 `credentials_required` 时，可使用配置 Key 调用 `/api/xxsyun-resume` 恢复已有订单查询，每次查询最多恢复一次，不重建支付订单。

## 次数与状态

本地 `POST /api/extract-link/huanguang/xxsyun-quota` 代理平台 `/api/xxsyun-quota`。省略 `api_key` 使用已保存 Key，明确空字符串表示清空后的输入，不回退旧 Key。查询不保存配置，只返回安全的次数字段；剩余次数为真实零时显示零，未知的总量或占用为 `null`，不重复扣减占用。失败不回显上游正文，响应禁止缓存。

同步平台的 XXSYUN 和转单状态及轮询标记。转单已生效时，旧主通道的取消退款不覆盖备用通道的当前状态。扫码完成仍需独立 Plus 核验，不能直接当作到账成功。

接口依据：[幻光公开页面](https://chongyun-link.xiaoliai.shop/)、该页面当前引用的公开 `app.js` 及 [API 手册](https://chongyun-link.xiaoliai.shop/static/api-docs.html)。旧手册中的网页计时转单说明与当前页面不一致，以当前提交参数和后台处理说明为准。
