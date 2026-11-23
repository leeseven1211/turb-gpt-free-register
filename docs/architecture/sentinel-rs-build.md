# sentinel-rs 原生构建与验证

`rust / sentinel_rs / registration` 使用独立原生进程。仓库不复制上游源码；
构建前请自行确认 `wangshen233/sentinel-rs` 的许可与使用范围，再按下述步骤在本机获取源码。

## 已验收基线

- 上游提交：`f222371c7960be490baf4ab1a2873da900506f2a`
- 平台：Ubuntu 24.04 / aarch64（Oracle VPS）
- 工具链：Rust stable 1.100.0，`wreq = 0.16.1` + `wreq-util = 0.2.0`
- BoringSSL 构建依赖：`cmake`、`nasm`、`perl`、`clang/libclang-dev`、`pkg-config`、`build-essential`

## 构建

```bash
sudo apt-get install -y cmake nasm clang libclang-dev pkg-config build-essential
curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
git clone https://github.com/wangshen233/sentinel-rs /home/ubuntu/src/sentinel-rs
cd /home/ubuntu/src/sentinel-rs
cargo build --release --bin sentinel-rs
sudo install -m 0755 target/release/sentinel-rs /usr/local/bin/sentinel-rs
```

Windows 请使用仓库自带 `build.ps1`（BoringSSL 需要 MSVC、nasm、Strawberry Perl 和 libclang）。
macOS / Linux 不要复用 Windows 产物，必须按目标系统和 CPU 架构分别构建。

## 二进制查找顺序

1. 运行配置 `SENTINEL_RS_BIN`（数据库运行配置，可在配置页修改）；
2. `<repo>/native/sentinel-rs/target/release/sentinel-rs`（本地构建，`.gitignore` 已排除）；
3. `/srv/apps/sentinel-rs/target/release/sentinel-rs`；
4. `/usr/local/bin/sentinel-rs`；
5. `PATH` 中的 `sentinel-rs`。

## 离线验证

```bash
sentinel-rs --version
cd /home/ubuntu/src/sentinel-rs && sentinel-rs mint --file sample_challenge.json
cd /home/ubuntu/src/sentinel-rs && sentinel-rs register -n 1   # 默认 dry-run，不联网
```

Turb 侧不执行 dry-run：桥接入口只接受真实注册，并要求显式分配邮箱与代理。
`SENTINEL_RS_BIN` 指向的进程必须可执行，`register --live` 才会触发远端动作。

## 本机补丁：取码地址直连

静态邮箱池的 `code_url` 常在专属邮箱服务/内网地址上；上游 `f222371` 会把它交给
同一个注册代理客户端请求。实测 JP 注册代理访问取码地址返回 **HTTP 502**，而本机直连
返回 200 与验证码，导致 Rust 注册在“等待邮箱验证码”处超时。

构建前应用 `docs/architecture/patches/sentinel-rs-otp-direct.patch`：

```bash
git clone https://github.com/wangshen233/sentinel-rs /home/ubuntu/src/sentinel-rs
cd /home/ubuntu/src/sentinel-rs
git checkout f222371c7960be490baf4ab1a2873da900506f2a
git apply /srv/apps/turb-gpt-free-register/docs/architecture/patches/sentinel-rs-otp-direct.patch
cargo build --release --bin sentinel-rs
sudo install -m 0755 target/release/sentinel-rs /usr/local/bin/sentinel-rs
```

补丁只把 `email.inbox`/`code_url` 的轮询客户端改为直连；OpenAI 注册请求仍走注册代理。
2026-11-23 用该补丁构建的 aarch64 二进制已验证：新邮箱收到验证码后 Rust 正常完成注册，
账号已写入 PostgreSQL。任务可能以 `registration_password_unconfirmed` 结束（Rust 内核
不校验密码），这是后处理状态，不是注册失败。
