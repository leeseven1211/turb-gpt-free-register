# -*- coding: utf-8 -*-
"""
WebUI 启动入口。

用法：
    python web.py                 # 默认 http://127.0.0.1:5000，仅本地访问，不自动打开浏览器
    python web.py --open-browser  # 启动后自动打开浏览器
    python web.py --port 8000     # 换端口
    python web.py --host 0.0.0.0  # 允许局域网访问（敏感工具，自行评估）

同实例的 combined / worker 与独立执行 CLI 共享唯一执行 owner；web 模式只受理和查询。
"""
import argparse
import logging
import os
import signal
import tempfile
import time
import webbrowser
from pathlib import Path
from threading import Timer


def _acquire_single_instance(port: int):
    """持有跨进程文件锁，防止同一端口启动多个 WebUI 实例。"""
    lock_path = Path(tempfile.gettempdir()) / f"turb-gpt-free-register-web-{int(port)}.lock"
    handle = lock_path.open("a+", encoding="utf-8")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write("0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, IOError) as exc:
        handle.close()
        raise RuntimeError(f"端口 {port} 的 WebUI 已在运行") from exc
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def _release_single_instance(handle) -> None:
    if handle is None:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except (OSError, IOError):
        pass
    handle.close()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="GPT 注册 WebUI 控制台")
    parser.add_argument("--host", default="127.0.0.1", help="绑定地址，默认仅本地 127.0.0.1")
    parser.add_argument("--port", type=int, default=5000, help="端口，默认 5000")
    parser.add_argument("--open-browser", action="store_true", help="启动后自动打开浏览器")
    parser.add_argument("--auth-code", default=None, help="WebUI 授权码；也可配置 .env: WEBUI_AUTH_CODE=...")
    parser.add_argument("--verbose", action="store_true", help="详细日志")
    parser.add_argument("--mode", choices=("combined", "web"), default=None,
                        help="默认 combined；web 只受理和查询，独立执行使用 worker.py")
    parser.add_argument('--server', choices=('flask', 'waitress'), default='flask',
                        help='默认开发 Flask；Waitress 仅用于显式 web 角色')
    parser.add_argument('--http-threads', type=int, default=16)
    parser.add_argument('--http-drain-timeout', type=float, default=20.0)
    parser.add_argument('--shutdown-timeout', type=float, default=80.0,
                        help='HTTP 与后台收尾共享的总预算（秒），默认 80')
    args = parser.parse_args()
    import math
    import ipaddress
    try:
        ipaddress.ip_address(args.host)
    except ValueError:
        if args.host != 'localhost':
            parser.error('host 必须是 IP 地址或 localhost')
    if not 1 <= args.port <= 65535:
        parser.error('port 必须是 1 到 65535')
    if not 1 <= args.http_threads <= 128:
        parser.error('http-threads 必须是 1 到 128')
    if not math.isfinite(args.http_drain_timeout) or not 0 < args.http_drain_timeout <= 20:
        parser.error('http-drain-timeout 必须大于 0 且不超过 20 秒')
    if not math.isfinite(args.shutdown_timeout) or args.shutdown_timeout <= 0:
        parser.error('shutdown-timeout 必须是大于 0 的有限秒数')
    if args.server == 'waitress' and args.mode == 'combined':
        parser.error('waitress 只允许显式 web 角色')

    _setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    from config.env_loader import ensure_loaded
    ensure_loaded()
    if args.mode is not None:
        os.environ["TURB_RUNTIME_MODE"] = args.mode
    from core.runtime.bootstrap import RuntimeBootstrap
    bootstrap = RuntimeBootstrap.from_environment(project_root=Path(__file__).resolve().parent)
    if args.server == 'waitress' and bootstrap.mode != 'web':
        parser.error('waitress 只允许 web 角色；请传 --mode web')
    if bootstrap.mode == "worker":
        raise SystemExit("worker 模式请使用 python worker.py")
    bootstrap.prepare_log_environment()
    from core.runtime.assembly import install
    from core.runtime.process import start_runtime, stop_runtime
    from webui.app import create_app
    from webui.auth import is_generated_code
    from config.deployment import browser_enabled

    # 启动项拼写错误须在连接数据库和启动后台任务之前明确失败。
    browser_enabled()

    if args.auth_code:
        os.environ["WEBUI_AUTH_CODE"] = args.auth_code

    try:
        instance_lock = _acquire_single_instance(args.port)
    except RuntimeError as exc:
        logger.error(str(exc))
        raise SystemExit(2) from exc

    runtime_install_attempted = False
    original_failure = False
    failure_code = 0
    http_server = None
    shutdown_deadline = None

    def begin_shutdown():
        nonlocal shutdown_deadline
        if shutdown_deadline is None:
            shutdown_deadline = time.monotonic() + args.shutdown_timeout

    try:
        # First signal interrupts startup/serve; re-entry never skips the drain.
        def _graceful_exit(signum, _frame):
            if shutdown_deadline is not None:
                logger.info('重复停止信号 %s；继续当前排空', signum)
                return
            begin_shutdown()
            logger.info('收到信号 %s，正在优雅退出', signum)
            raise SystemExit(0)
        for signal_name in ('SIGTERM', 'SIGINT'):
            selected_signal = getattr(signal, signal_name, None)
            if selected_signal is not None:
                signal.signal(selected_signal, _graceful_exit)

        if os.environ.get('TURB_RUNTIME_MANAGER'):
            from core.runtime.role_launcher import publish_managed_identity
            publish_managed_identity(bootstrap)

        # PostgreSQL 是唯一主存储；连接失败同样需要归还端口锁。
        from core.storage import postgres as postgres_store
        postgres_store.require_ready()

        # install 可能在登记部分生命周期资源之后失败，仍须尝试收尾。
        runtime_install_attempted = True
        install(bootstrap, logger=logger)

        if bootstrap.mode == "web":
            # 列表请求仅读取已部署的表，业务存储在监听前准备好。
            from core.operation_task_store import init as init_operation_storage
            from core.storage import registration
            from core.sales import store as sales_store

            registration.init()
            init_operation_storage()
            sales_store.init()

        app = create_app(auth_code=args.auth_code)
        start_runtime(logger)
        url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.port}"
        if args.server != "waitress":
            logger.info(f"WebUI 已启动：{url}")
        if is_generated_code():
            from webui.auth import expected_auth_code
            logger.warning("未配置 WEBUI_AUTH_CODE/AUTH_CODE，已生成本次临时授权码：%s", expected_auth_code())
        if args.host in ("0.0.0.0", "::"):
            logger.warning("已绑定到所有网卡，局域网内其他设备可访问。这是敏感工具，请确认网络环境可信。")

        # 默认不自动打开浏览器；需要时显式传 --open-browser
        if args.open_browser:
            Timer(1.0, lambda: webbrowser.open(url)).start()

        # debug=False：避免 reloader 双进程导致线程池/定时器重复
        try:
            if args.server == 'waitress':
                from core.runtime.http_server import HttpServer
                http_server = HttpServer(app, host=args.host, port=args.port,
                    threads=args.http_threads, spool_dir=bootstrap.runtime_dir / 'web-spool', logger=logger)
                http_server.start()
                logger.info("WebUI 已启动：%s", url)
                http_server.serve()
            else:
                app.run(host=args.host, port=args.port, debug=False, threaded=True)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
    except BaseException as exc:
        original_failure = not (isinstance(exc, SystemExit) and exc.code in (None, 0))
        failure_code = (exc.code if isinstance(exc, SystemExit) and isinstance(exc.code, int) else 1) if original_failure else 0
        raise
    finally:
        begin_shutdown()
        remaining = lambda: max(0.0, shutdown_deadline - time.monotonic())
        cleanup_failed = False
        http_clean = True
        if http_server is not None:
            try:
                http_clean = http_server.stop(timeout=min(args.http_drain_timeout, remaining())) is True
            except BaseException:
                http_clean = False
                logger.exception('http_stop_incomplete')
            if not http_clean:
                logger.error('http_stop_incomplete；保留 HTTP 正在使用的 runtime 与端口身份')
                cleanup_failed = True
        if runtime_install_attempted and http_clean:
            try:
                cleanup_failed = stop_runtime(timeout=min(60.0, remaining())) is not True
            except BaseException:
                cleanup_failed = True
                logger.exception("后台收尾失败")
        if http_clean:
            try:
                _release_single_instance(instance_lock)
            except BaseException:
                cleanup_failed = True
                logger.exception('释放 WebUI 端口锁失败')
        if os.environ.get('TURB_ROLE_EXIT_PATH'):
            from core.runtime.role_launcher import write_exit_receipt
            try:
                write_exit_receipt(role=bootstrap.mode, clean=not cleanup_failed and not original_failure,
                                   code=failure_code or (3 if cleanup_failed else 0))
            except Exception:
                cleanup_failed = True
                logger.exception('role_exit_receipt_failed')
        if cleanup_failed:
            logger.error("后台排空未完成，保留任务执行证据；进程将以非零状态退出")
            if not original_failure:
                raise SystemExit(3)


if __name__ == "__main__":
    main()
