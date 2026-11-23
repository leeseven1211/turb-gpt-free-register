# sentinel-rs（内置 fork）

本目录是 `sentinel-rs` 内核的内置源码，来自上游
`https://github.com/wangshen233/sentinel-rs`，基线提交
`f222371c7960be490baf4ab1a2873da900506f2a`。

- 使用授权：仓库作者已明确允许本项目使用（2026-11-23，由项目负责人直接确认）。
  上游自身未附 LICENSE 文件；保留本说明和提交来源用于追溯，不对外再分发。
- 构建方式见 `docs/architecture/sentinel-rs-build.md`；产物安装到 `/usr/local/bin/sentinel-rs`。
- 本 fork 只做增量补丁，不改动注册请求构造、指纹、sentinel token 与代理逻辑。

## 本地补丁清单

1. `src/protocol.rs`（新增）：可选的双向 JSON Lines 协议层。
   - `SENTINEL_PROTOCOL=1` 时启用；未设置时为完全空操作，CLI 行为不变。
   - 已实现：`ready/start` 握手、`landing` 事实、`checkpoint_prepare`/`checkpoint_ack` 密码落库闸门、`submission` 回执。
2. `src/lib.rs`：导出 `protocol` 模块。
3. `src/main.rs`：`register` 子命令在协议模式下先握手（报告能力并等待 `start`）。
4. `src/flow/mod.rs`：
   - authorize 落地判定后发 `landing`（`new|existing|unknown`）；
   - 发 `user/register` 前调用 `checkpoint_password`，Python 未确认落库时拒绝发送；
   - `user/register` 返回后发 `submission`。

## 验收

- `--dry-run` 请求计划与未打补丁的二进制逐行一致（除随机 uuid / 库路径）。
- 协议层契约测试见 `tests/protocol/`（Python 侧假内核）。
