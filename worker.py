"""Explicit execution process; no Flask application or HTTP listener."""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import signal
import threading
import time


# Publish only fixed ManagedRuntime stop reasons, never exception text or
# readiness details from other components.
_STOP_FAILURE_CODES = frozenset({
    "runtime_stop_deadline_exhausted",
    "runtime_settlement_shutdown_start_failed",
    "runtime_producers_still_running",
    "runtime_claimers_still_running",
    "runtime_settlement_drain_timeout",
    "runtime_drain_timeout",
    "runtime_executors_still_running",
    "runtime_executor_handoff_pending",
    "runtime_settle_timeout",
    "runtime_settle_failed",
    "runtime_components_still_running",
    "runtime_settlement_final_drain_timeout",
    "runtime_final_cleanup_pending",
    "runtime_settlement_still_running",
    "runtime_settlement_stop_failed",
    "runtime_permit_releases_still_running",
    "runtime_permit_releases_stop_failed",
    "runtime_flush_timeout",
    "runtime_flush_failed",
    "runtime_heartbeat_still_running",
    "runtime_connections_still_running",
    "runtime_owner_close_failed",
    "runtime_settlement_background_resume_failed",
})


def _stop_failure_code(runtime) -> str:
    if runtime is not None:
        try:
            status = runtime.manager.status()
            code = status.get("error_code")
            if (status.get("state") == "stop_incomplete"
                    and isinstance(code, str) and code in _STOP_FAILURE_CODES):
                return code
        except Exception:
            # Diagnostics must not replace the original exit reason.
            pass
    return "runtime_stop_failed"


def main() -> None:
    parser = argparse.ArgumentParser(description="Turb 独立后台执行进程")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--shutdown-timeout", type=float, default=60.0,
                        help="后台收尾的总预算（秒），默认 60")
    args = parser.parse_args()
    import math
    if not math.isfinite(args.shutdown_timeout) or args.shutdown_timeout <= 0:
        parser.error("shutdown-timeout 必须是大于 0 的有限秒数")
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    from config.env_loader import ensure_loaded
    ensure_loaded()
    os.environ["TURB_RUNTIME_MODE"] = "worker"
    from core.runtime.bootstrap import RuntimeBootstrap
    bootstrap = RuntimeBootstrap.from_environment(project_root=Path(__file__).resolve().parent)
    bootstrap.prepare_log_environment()
    from core.storage import postgres
    from core.runtime.assembly import install
    from core.runtime.process import start_runtime, stop_runtime
    logger = logging.getLogger(__name__)
    stopped = threading.Event()
    original_failure = False
    failure_code = 0
    install_attempted = False
    runtime = None
    shutdown_deadline = None
    started = False

    def begin_shutdown():
        nonlocal shutdown_deadline
        if shutdown_deadline is None:
            shutdown_deadline = time.monotonic() + args.shutdown_timeout

    try:
        def request_stop(*_args):
            if shutdown_deadline is not None:
                return
            begin_shutdown()
            if not started:
                raise SystemExit(0)
            stopped.set()
        for name in ('SIGTERM', 'SIGINT'):
            signal.signal(getattr(signal, name), request_stop)
        postgres.require_ready()
        install_attempted = True
        runtime = install(bootstrap)
        start_runtime()
        started = True
        if os.environ.get('TURB_RUNTIME_MANAGER'):
            from core.runtime.role_launcher import publish_managed_identity
            publish_managed_identity(bootstrap)
        while not stopped.wait(.5):
            from core.runtime.process import execution_owner_valid
            if not execution_owner_valid():
                begin_shutdown()
                logger.error("后台执行归属已失效，当前进程将收尾退出：code=runtime_execution_owner_lost")
                raise SystemExit(1)
    except BaseException as exc:
        original_failure = not (isinstance(exc, SystemExit) and exc.code in (None, 0))
        failure_code = (exc.code if isinstance(exc, SystemExit) and isinstance(exc.code, int) else 1) if original_failure else 0
        raise
    finally:
        begin_shutdown()
        try:
            clean = not install_attempted or stop_runtime(
                timeout=min(60.0, max(0.0, shutdown_deadline - time.monotonic()))) is True
        except BaseException:
            clean = False
            logger.exception("后台收尾失败")
        if os.environ.get('TURB_ROLE_EXIT_PATH'):
            from core.runtime.role_launcher import write_exit_receipt
            try:
                write_exit_receipt(role='worker', clean=clean and not original_failure, code=failure_code or (0 if clean else 3))
            except Exception:
                clean = False
                logger.exception('role_exit_receipt_failed')
        if not clean:
            logger.error("后台排空未完成：code=%s", _stop_failure_code(runtime))
            if not original_failure:
                raise SystemExit(3)


if __name__ == "__main__":
    main()
