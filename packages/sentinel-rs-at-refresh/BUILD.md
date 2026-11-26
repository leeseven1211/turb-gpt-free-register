# sentinel-rs 构建说明

本目录是 `sentinel-rs` 源码，不含编译产物，也没有 `target/`。

> 二进制必须按目标系统和 CPU 架构分别构建，**不要把 Linux/macOS 的二进制复制到 Windows 使用**。
> 上游来源与授权说明见 `FORK.md`。

---

## Windows 构建（推荐）

### 1. 安装依赖

| 依赖 | 说明 |
| --- | --- |
| Rust | 用 [rustup](https://rustup.rs/) 安装 stable 工具链 |
| Visual Studio 2022 | 勾选「使用 C++ 的桌面开发」（MSVC + Windows SDK） |
| nasm | 加入 PATH |
| Strawberry Perl | 加入 PATH |
| LLVM | 安装后确认存在 `C:\Program Files\LLVM\bin\libclang.dll` |

### 2. 检查 build.ps1 里的路径

脚本顶部有三个固定路径：

```powershell
$VcVars    = 'C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat'
$LlvmDir   = 'C:\Program Files\LLVM\bin'
$LibClang  = Join-Path $LlvmDir 'libclang.dll'
```

- 如果装的是 Community / Enterprise，把 `$VcVars` 改成对应路径（例如 `...\Community\VC\Auxiliary\Build\vcvars64.bat`）。
- LLVM 不在默认目录时改 `$LlvmDir`。

### 3. 构建

```powershell
cd <本目录>
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

产物：

```
target\release\sentinel-rs.exe
```

> 不要直接在普通 PowerShell 里 `cargo build`：BoringSSL 需要 `vcvars64` 环境，否则会挂在 `nasm` / `bindgen` / `cl.exe`。
> 项目路径不要带中文；`build.ps1` 会自动做 ASCII 目录联接兜底，但直接用纯 ASCII 路径最稳。

---

## Linux / macOS 构建

Debian / Ubuntu：

```bash
sudo apt-get install -y cmake nasm clang libclang-dev pkg-config build-essential
curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
cd <本目录>
cargo build --release --bin sentinel-rs
```

产物：`target/release/sentinel-rs`

macOS 用 Homebrew 安装 `cmake nasm llvm`，并设置 `LIBCLANG_PATH` 指向 Homebrew 的 LLVM `lib` 目录。

---

## 让 Turb 使用这个二进制

Turb 的查找顺序：

1. 运行配置 `SENTINEL_RS_BIN`
2. `<仓库>/native/sentinel-rs/target/release/sentinel-rs`
3. `/srv/apps/sentinel-rs/target/release/sentinel-rs`
4. `/usr/local/bin/sentinel-rs`
5. `PATH` 里的 `sentinel-rs`

本地最简单的做法：在 Turb 配置页把 `SENTINEL_RS_BIN` 填成刚构建出来的可执行文件绝对路径；或者把它放进 PATH。

Linux 也可以直接安装：

```bash
sudo install -m 0755 target/release/sentinel-rs /usr/local/bin/sentinel-rs
```

---

## 验证构建

```bash
sentinel-rs --version
sentinel-rs refresh --config refresh.sample.json          # dry-run：只打印计划，不联网
```

`refresh` 子命令存在，说明这一版包含刷新 AT 的能力。

需要真实刷新时：

```bash
sentinel-rs refresh --config refresh.sample.json --live
```

`refresh.sample.json` 字段说明：

- `email`：账号邮箱（必填）
- `password` / `totp_secret`：登录凭据，可空
- `cookies`：上次登录保存的 Cookie，可空（为空则直接重登）
- `device_id`：上次登录的 `oai-did`，可空
- `user_id` / `account_id`：账号身份，用于核验返回的会话
- `proxy`：`host:port` 或 `http://user:pass@host:port`，可空
- `country`：两位国家码，影响指纹档位

---

## 常见问题

**`bindgen` / `libclang.dll` 找不到**
没有用 `build.ps1`，或 LLVM 路径不对。确认 `$LlvmDir` 指向真实安装目录。

**`nasm` 返回 1 / Unable to open input file**
项目路径含中文。把源码移到纯 ASCII 路径后重试。

**`vcvars64.bat` 找不到**
`build.ps1` 里写死了 Professional 版本路径，按实际 VS 版本修改。

**构建很慢**
BoringSSL 首次编译需要几分钟到十几分钟，属正常；后续增量构建会快很多。

**运行时提示找不到二进制**
Turb 里检查 `SENTINEL_RS_BIN` 是否是绝对路径、是否可执行；Linux 还要确认有执行权限。
