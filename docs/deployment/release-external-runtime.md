# 固定 release 与外置 Python 运行环境

[`tools/render_release_manager.py`](../../tools/render_release_manager.py) 提供两个 Python 函数：`render_systemd_unit()` 和 `render_launchd_plist()`。目前没有 CLI；渲染只生成配置文件，不安装、加载、启停或部署服务。仓库原有 checkout 模板保持原样。

固定 release 内不放 `.venv`、运行数据、日志或字节码缓存。建议将依赖环境放在 `environments/<依赖锁哈希>-<Python ABI>/`，与 `releases/<release-id>/` 分开保存。依赖环境需要事先按对应锁文件和目标平台准备，并独立确认解释器、依赖版本及运行权限；renderer 不创建 venv，也不检查解释器是否存在或可执行。

## 发布输入与身份

正式 release 必须来自已审核、已提交的精确源码 revision。`prepare_release()` 要求 tracked 文件没有未提交改动，只复制 Git tracked 的非私有文件；未跟踪的新源码不会自动纳入。因此应先确认交付文件已提交，不能把 dirty 工作树复制后填入一个旧 commit，冒充该 commit 的正式发布包。

已有 manifest 的包应通过 `check_release()` 的完整文件哈希和依赖锁校验。仅对没有 manifest 的源码目录执行 `tools/release.py check`，不能证明包内容或发布身份。runtime bootstrap 对固定包优先校验 manifest 后读取 `source_commit`；没有 manifest 时只接受根目录匹配的真实 Git checkout。不要用环境变量注入 SHA 绕过校验。

所有示例路径和 `RELEASE_ID`、`LOCK_HASH-py312` 都是待替换占位值，不代表已存在或已验收的环境。以下函数调用应由对应外置 Python 在已审核源码或 release 的导入路径下执行。

## 渲染 systemd 配置

```python
from pathlib import Path

from tools.release import check_release
from tools.render_release_manager import render_systemd_unit

release = Path("/srv/turb/example/releases/RELEASE_ID")
python = Path("/srv/turb/example/environments/LOCK_HASH-py312/bin/python")
output_dir = Path("/srv/turb/example/manager-config/RELEASE_ID")

report = check_release(release, expected_release_id="RELEASE_ID")
assert report["ok"] is True

for role in ("web", "worker"):
    rendered = render_systemd_unit(
        release / f"deploy/systemd/turb-{role}@.service",
        output_dir / f"turb-{role}-example.service",
        release_dir=release,
        interpreter=python,
        instance="example",
    )
    print(rendered)
```

函数将模板中的 `/srv/turb/%i/current` 替换为固定 release 路径，替换解释器，并把 `%i` 替换为 `instance`。生成配置含 `PYTHONDONTWRITEBYTECODE=1`；原模板的角色边界、重启策略、停止预算与 umask 保留。

systemd API 没有 `runtime_dir`、`task_log_dir` 或 `logs_dir` 参数。当前模板渲染后继续使用 `/etc/turb/example/bootstrap.env`、`/var/lib/turb/example/runtime` 和 `/var/log/turb/example/tasks` 等实例路径。需要其它布局时，应另行审核专用模板和生成结果；不要传入不存在的函数参数，也不要假定目录、权限或 bootstrap 配置已由 renderer 创建。

release、解释器和输出路径必须为绝对路径，解释器及生成配置必须位于包外。systemd 的 release 和解释器路径还不能包含空白、反斜线、引号、`%` 或 `$`。实例名允许字母、数字、点、下划线和短横线，长度最多 64 个字符，首字符须为字母或数字。

## 渲染 launchd 配置

```python
from pathlib import Path

from tools.release import check_release
from tools.render_release_manager import render_launchd_plist

base = Path("/Users/operator/turb/example")
release = base / "releases/RELEASE_ID"
python = base / "environments/LOCK_HASH-py312/bin/python"
output_dir = base / "manager-config/RELEASE_ID"

report = check_release(release, expected_release_id="RELEASE_ID")
assert report["ok"] is True

for role in ("web", "worker"):
    rendered = render_launchd_plist(
        release / f"deploy/launchd/local.turb.{role}.plist.example",
        output_dir / f"local.turb.example.{role}.plist",
        release_dir=release,
        interpreter=python,
        instance="example",
        runtime_dir=base / "runtime",
        task_log_dir=base / "task-logs",
        logs_dir=base / "manager-logs",
    )
    print(rendered)
```

函数设置固定 `WorkingDirectory`、脚本路径和外置解释器，替换 label、环境和 stdout/stderr 路径占位值，并加入 `PYTHONDONTWRITEBYTECODE=1`。输出、runtime、任务日志和 manager 日志目录均须使用包外绝对路径。renderer 会创建输出父目录并原子写入配置；它不会准备运行目录权限，也不会安装 plist 或触发 launchd。

## 保留 venv 解释器路径

传入 `/absolute/environments/<version>/bin/python`，不要先对该文件调用 `Path.resolve()`。venv 的 `bin/python` 经常是指向基础 Python 的符号链接；将 argv 中的解释器替换成解析后的基础 Python，可能失去 venv 的 `sys.prefix` 和依赖环境。

renderer 会解析解释器父目录，同时保留最后一级 `bin/python` 文件名作为 argv；它也检查符号链接最终目标是否落入 release，避免借链接把解释器放回包内。这允许包外 venv 的正常解释器链接，不表示固定 release 内可以加入 `.venv` 或任意符号链接。`check_release()` 仍拒绝包内符号链接。

两种渲染结果都禁写 Python bytecode。直接进行包内模块导入检查时也应使用外置 Python 的 `-B` 或设置同一环境变量，避免产生 `__pycache__` 后破坏文件清单。该设置只约束字节码缓存，不能代替对其它运行数据和日志目录的外置配置。

## 启动、切换与回退的证据

渲染完成后，应核对固定 release、解释器、实例、配置及运行目录映射，并分别记录包校验、解释器环境检查与 manager 配置检查结果。配置语法正确、文件生成成功或 `Type=exec` 生效，都不能代替实际启动与 readiness 验收。

实际安装和启动需要独立执行与证据：确认 manager 加载的是审核后的配置，核对进程 PID、启动时间、cwd、argv、release、instance、执行 owner、Web/Worker readiness，以及授权范围内的业务收尾。角色停止、排空和 owner 释放须真实确认；发生 stop incomplete 时停止推进。具体角色边界见[独立 Web 与 Worker 入口](split-runtime.md)。

回退应保留上一版 release、匹配的外置环境及对应配置。renderer 将脚本与 cwd 绑定到解析后的固定 release；单独切换 `current` 符号链接不会改写已经生成的配置，也不会重启进程。`tools/release.py switch/rollback` 只负责校验与本地链接/状态切换，服务配置切换、停止顺序、owner 交接和回退后的业务验证需要另行完成并记录。不要原地升级仍被旧版本使用的外置环境。

本文描述调用方法和验收要求，不构成已启动、回退验证通过或部署完成的声明。
