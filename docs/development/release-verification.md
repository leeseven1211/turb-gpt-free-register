# 发布与验证

> 本文是当前可复用的验证规则，不记录某次优化的性能数字或历史验收结论。相关历史证据
> 保存在[2026-09 优化记录](../history/2026-09-optimization/)。

## 1. 验证范围

代码改动先运行最小相关测试，再按风险扩大。涉及存储、运行时、迁移、发布工具或共享
配置时，至少补充隔离数据库验证；涉及 WebUI 时，还要验证现代界面及真实浏览器
行为。项目只维护现代 WebUI；旧 `?ui=legacy` 链接和 `ui_mode=legacy` Cookie 均返回现代
页面，涉及入口路由的修改应保留这两项兼容检查。文档改动至少检查标题、相对链接、重复
内容和现行代码引用。

测试必须使用非生产 PostgreSQL 与独立 schema。`tools/test_isolated.py` 会建立隔离环境；
常用档位为：

```bash
python tools/test_isolated.py --profile default
python tools/test_isolated.py --profile extended
python tools/test_isolated.py --profile all
```

测试进程不得连接生产库、不得使用 `public` schema，也不能依赖 `.env`、账号、Token 或
运行日志作为测试输入。若隔离数据库不可用，应报告验证未执行或失败，不能把 skip 说成
通过。

## 2. 提交与发布前检查

```text
最小相关测试
  -> 相邻回归/隔离测试
  -> git diff --check
  -> 检查暂存范围不含私有数据
  -> 确认提交与远端推送状态
```

提交、推送、部署和服务重启是独立事实：本地提交不代表已推送，推送不代表进程已加载新
代码，进程启动也不代表数据库和 worker 已就绪。未被请求的操作不得隐含执行。

## 3. 服务运行时验收

当任务明确要求启动、重启或部署时，依次核对：

1. 实际进程 PID、工作目录和监听端口；
2. PostgreSQL 可用性及启动日志；
3. `GET /healthz` 的 liveness；
4. `GET /readyz` 的数据库和 runtime 就绪；
5. `GET /login` 或相关页面/API 的真实响应；
6. 涉及 UI 的现代界面交互和浏览器控制台结果；入口路由变更另核对旧链接与 Cookie 均返回现代页面。

`/healthz` 通过不等于 `/readyz` 通过。若 supervisor 自动拉起旧进程，必须确认它加载的
工作目录和代码版本，不能仅依据启动脚本输出声明成功。

## 4. 数据与日志安全

验证输出只保留排障必要字段并脱敏。不得提交或展示 `.env`、账号、Token、Cookie、OTP、
完整代理、邮箱池、`logs/`、`run/`、`accounts/` 或 `codex_accounts/` 内容。兼容文件的
存在或生成成功不能替代 PostgreSQL 行级数据的正确性。

历史性能门禁、依赖锁验证和迁移演练记录见
[历史发布验证证据](../history/2026-09-optimization/release-verification-evidence.md)。
