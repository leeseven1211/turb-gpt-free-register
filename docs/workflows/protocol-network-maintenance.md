# Sentinel 资源检查与匿名预检挑战实验

本功能的默认开关均为关闭，不替换当前 SDK，不增加注册后台检查任务。Roxy、账号密码、OTP/MFA、授权回调、Token 交换和支付不使用挑战重放。

## Sentinel 候选管理

在 **配置 → 系统与维护 → 通用配置 → Sentinel 检查** 点击“检查 Sentinel 更新”。卡片显示当前内置版本、发现版本、上次检查时间、内容比较及两套执行器的静态检查结果。检查中按钮禁用，完成后直接更新结果；失败保留上次候选，显示失败提示后可重试。打开配置页只读取已有结果，只有点击按钮才访问官方公共资源。

检查由独立维护线程监管下载子进程，不占注册或账号任务 worker。下载进程最多运行 35 秒，DNS 卡住等情况会被终止并显示失败，可再次点击重试。候选保存在当前实例的 `run/sentinel-candidates/`，不会切换现用版本，也不会清理或修改其他任务。WebUI 中不展示脚本源码及内部缓存路径。

`tools/diagnostics/check_sentinel_assets.py` 继续作为可选命令行维护工具。检查官方 loader 并缓存候选，不执行 loader、不覆盖 `sentinel/sdk.js` 或 Proto2 活跃缓存。使用 `--help` 查看缓存路径和刷新选项。输出区分内容一致、候选变更和静态兼容性；静态兼容不等于注册实测通过。

通用 runner 与 Proto2 依然使用原有资源。候选激活需要将版本、hash、SDK 路径以及 iframe/referer/fingerprint 一起绑定到认证会话；本次不切换。

## Cloudflare 实验

运行配置中的通用协议开关源码默认为 `false`：

- `OPENAI_CF_PREFLIGHT_ENABLED`：通用协议提交邮箱前的 `https://chatgpt.com/auth/login` 预检。

该开关覆盖本地优化 Protocol 及复用公共匿名预检的认证路径；开源 Protocol 使用自身预检，未接入。开源protocol-2 的自动接入和专用开关已撤回，保留原注册流程。

**2026-11-03 撤回依据：**保留真实上游 `AuthFlow.run_register`、替换最底层网络为离线响应后，完整成功分支共记录 16 个模拟请求，原自动接入开启时恢复调用仍为 0。默认预热和取 CSRF 均访问 `/api/auth/csrf`，登录页在取 CSRF 和 signin 中只是 Referer。少数后段兜底的非流式回跳又可能匹配旧钩子，超出预检定位。按用户要求移除该自动接入、专用配置及恢复入口；后续若需要支持，应先验证真实失败端点与阶段。独立探针的 wreq 适配器仍保留供显式诊断。

开启后，仅在明确的 `403 + cf-mitigated: challenge` 尝试一次；普通响应、普通 403、429、流式请求和其他端点不进入求解。依赖缺失、运行环境不支持或求解失败时保留原响应及原重试/失败分类。取消信号继续传播，恢复失败不会伪装成成功。每会话最多一次，最多占用该预检剩余预算，并限制请求和响应体积。

挑战网络请求仍走原 curl 或 wreq transport、代理和 Cookie store，所有跳转由 Python 策略控制；Cookie 出现和验证成功分别报告。成功只指批准的匿名页面恢复，不代表注册成功率已经提高。

DOM runtime 依赖单独安装在 `sentinel/cloudflare/`，不会成为现有 Sentinel 的启动依赖。具体依赖和平台支持见该目录文档。缺少操作系统隔离时不会执行远端脚本。

独立探针默认不联网、不读取账号：

```bash
python tools/diagnostics/cloudflare_session_probe.py
python tools/diagnostics/cloudflare_session_probe.py --help
```

显式 `--run --transport curl` 或 `--run --transport wreq` 才访问固定匿名登录页；`--proxy` 显式指定测试代理，留空直连，不领取业务代理池，也不改变已有任务或配置。不要将真实账号材料传给探针。

离线回归覆盖同会话 Cookie、请求白名单、预算、取消、依赖缺失及默认关闭时的现有调用路径。离线 fixture 和本地代理测试不证明当前线上挑战可被支持；真实运行保持关闭，未以真实账号验收或部署。
