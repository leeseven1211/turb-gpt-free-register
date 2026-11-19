#!/usr/bin/env bash
set -euo pipefail
# Compatibility commands default to combined. Explicit roles are independently managed.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "" || "${1:-}" == "--help" || "${1:-}" == "-h" || "${1:-}" == "help" ]]; then
  cat <<'HELP'
用法：./webui.sh <start|stop|restart|status|check|logs> [combined|web|worker|all]
默认 combined 保持原入口；web 使用 Waitress，worker 不监听 HTTP。
split 角色须设置 TURB_RUNTIME_DIR=/绝对路径 TURB_INSTANCE_ID=稳定实例名。
HOST/PORT/OPEN_BROWSER/VERBOSE/STARTUP_CHECK_TIMEOUT 沿用；STOP_TIMEOUT 默认 90 秒。
AUTH_CODE 仅作为子进程环境传入。EXTRA_ARGS 不再空白切分，请使用显式 Python CLI。
已托管角色必须由 systemd/launchd 启停；脚本不自动安装服务或强杀进程。
HELP
  exit 0
fi
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi
exec "$PYTHON_BIN" "$ROOT_DIR/tools/manage_runtime.py" "$@"
