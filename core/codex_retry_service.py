# -*- coding: utf-8 -*-
"""Codex 授权补跑服务，供账号页和注册任务队列共同使用。"""
import ctypes
import json
import logging
import threading
import time
from pathlib import Path

from core import account_task_store, db

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).resolve().parent.parent / "注册日志"
_RETRYING: set[str] = set()
_RETRYING_LOCK = threading.Lock()
_STOP_REQUESTED: set[str] = set()
_RUNNING_THREADS: dict[str, int] = {}
_RESERVED_AT: dict[str, float] = {}


class CodexRetryStopped(BaseException):
    """用户手动停止 Codex 补跑。"""


def _totp_setup_pending(account: dict) -> bool:
    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    return bool(raw_extra.get("totp_setup_pending")) if isinstance(raw_extra, dict) else False


def _thread_alive(thread_id: int | None) -> bool:
    if not thread_id:
        return False
    try:
        tid = int(thread_id)
    except Exception:
        return False
    return any(getattr(t, "ident", None) == tid and t.is_alive() for t in threading.enumerate())


def _clear_state_locked(key: str) -> None:
    _RETRYING.discard(key)
    _RUNNING_THREADS.pop(key, None)
    _RESERVED_AT.pop(key, None)


def log_path(email: str) -> Path:
    safe = email.replace("/", "_").replace("\\", "_").replace(":", "_")
    return _LOG_DIR / f"codex-retry-{safe}.log"


def reserve(email: str) -> bool:
    """进程内防止同一账号被重复补跑。"""
    key = (email or "").strip().lower()
    if not key:
        return False
    with _RETRYING_LOCK:
        if key in _RETRYING:
            thread_id = _RUNNING_THREADS.get(key)
            alive = _thread_alive(thread_id)
            age = time.time() - float(_RESERVED_AT.get(key) or 0)
            stop_req = key in _STOP_REQUESTED
            try:
                acc = db.get_account_by_email(email)
                status = str((acc or {}).get("codex_status") or "").lower()
            except Exception:
                status = ""
            # 修复“实际已停止/线程已结束，但进程内占位未释放”导致无法再次补跑。
            # 用户点停止后，部分浏览器/短信等待步骤可能不会立刻退出，UI 已是 stopped 但进程占位仍在。
            # 这种场景允许清理占位后重新补跑；旧线程仍保留 stop_requested，会在检查点退出。
            terminal_status = status in {"stopped", "failed", "success", "deactivated", "skipped", "cancelled"}
            if ((not alive) and (status != "retrying" or age > 15 * 60)) or (terminal_status and (stop_req or age > 30)):
                logger.warning(
                    "[Codex 补跑] 清理脏占位：email=%s status=%s thread_id=%s alive=%s stop_requested=%s age=%.1fs",
                    email, status or "-", thread_id or "-", alive, stop_req, age,
                )
                _clear_state_locked(key)
            else:
                return False
        _STOP_REQUESTED.discard(key)
        _RUNNING_THREADS.pop(key, None)
        _RETRYING.add(key)
        _RESERVED_AT[key] = time.time()
        return True


def release(email: str) -> None:
    key = (email or "").strip().lower()
    with _RETRYING_LOCK:
        _clear_state_locked(key)


def is_retrying(email: str) -> bool:
    with _RETRYING_LOCK:
        return (email or "").strip().lower() in _RETRYING


def is_stop_requested(email: str) -> bool:
    with _RETRYING_LOCK:
        return (email or "").strip().lower() in _STOP_REQUESTED


def check_stop_requested(email: str) -> None:
    if is_stop_requested(email):
        raise CodexRetryStopped("用户手动停止 Codex 补跑")


def _build_roxy_twofa_setup(email: str, task_id: int):
    """为缺少 TOTP 的 Codex 补跑构造一次性 2FA 前置步骤。"""
    state = {"secret": ""}

    def _setup(driver) -> bool:
        current = db.get_account_by_email(email) or {}
        existing_secret = str(current.get("totp_secret") or state["secret"] or "").strip()
        setup_pending = _totp_setup_pending(current)
        if existing_secret and not setup_pending:
            state["secret"] = existing_secret
            logger.info("[Codex 补跑][2FA] 本地已存在 Authenticator key，跳过重复设置：%s", email)
            return False

        check_stop_requested(email)
        account_task_store.append_event(
            task_id,
            stage="twofa",
            message="账号未设置 2FA，先启用 Authenticator 再执行 Codex OAuth",
        )
        logger.info("[Codex 补跑][2FA] 账号缺少 Authenticator key，开始前置设置：%s", email)

        def _checkpoint(secret: str) -> None:
            normalized = str(secret or "").strip()
            if not normalized or not db.update_account_totp_secret(email, normalized, setup_pending=True):
                raise RuntimeError("Authenticator key 写入账号检查点失败")
            state["secret"] = normalized
            logger.info("[Codex 补跑][2FA] Authenticator key 已在激活前写入账号检查点")

        try:
            from core.roxy_registration import setup_roxy_2fa

            secret = setup_roxy_2fa(
                driver,
                email,
                on_secret=_checkpoint,
                existing_secret=existing_secret or None,
            )
            if not state["secret"]:
                _checkpoint(secret)
            if not db.update_account_totp_secret(email, state["secret"], setup_pending=False):
                raise RuntimeError("Authenticator 完成状态写入账号失败")
            if not db.update_account_twofa_status(email, "success", "Authenticator 2FA 已启用"):
                raise RuntimeError("Authenticator 结果状态写入账号失败")
            check_stop_requested(email)
            account_task_store.append_event(
                task_id,
                stage="twofa_result",
                message="Authenticator 2FA 已启用，继续 Codex OAuth",
                detail={"enabled": True},
            )
            logger.info("[Codex 补跑][2FA] Authenticator 2FA 已启用：%s", email)
            return True
        except CodexRetryStopped:
            raise
        except Exception as exc:
            db.update_account_twofa_status(
                email,
                "failed",
                f"{type(exc).__name__}: {str(exc)[:220]}",
            )
            account_task_store.append_event(
                task_id,
                stage="twofa_result",
                message="Authenticator 2FA 设置失败，已停止进入 Codex OAuth",
                level="ERROR",
                detail={"enabled": False, "error": f"{type(exc).__name__}: {str(exc)[:220]}"},
            )
            raise RuntimeError(
                f"2FA 设置失败，已停止进入 Codex OAuth：{type(exc).__name__}: {str(exc)[:180]}"
            ) from exc

    return _setup


def _async_raise(thread_id: int, exc_type: type[BaseException]) -> bool:
    """向指定 Python 线程注入异常，用于尽快中断阻塞中的补跑流程。"""
    if not thread_id:
        return False
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread_id),
        ctypes.py_object(exc_type),
    )
    if res == 0:
        return False
    if res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), None)
        return False
    return True


def request_stop(email: str) -> dict:
    """请求停止单个 Codex 补跑。运行中会注入停止异常；排队中会在启动前退出。"""
    key = (email or "").strip().lower()
    if not key:
        return {"ok": False, "error": "email 为空", "status": 400}
    with _RETRYING_LOCK:
        retrying = key in _RETRYING
        thread_id = _RUNNING_THREADS.get(key)
        _STOP_REQUESTED.add(key)
    if not retrying:
        db.update_account_codex_status(email, "stopped", "用户手动停止（未发现运行中的补跑）")
        return {"ok": True, "message": "未发现运行中的补跑，已标记为已停止", "state": "stopped", "running": False}

    injected = bool(thread_id and _async_raise(int(thread_id), CodexRetryStopped))
    db.update_account_codex_status(email, "stopped", "用户手动停止 Codex 补跑")
    # 如果没有可注入的存活线程，立即释放进程内占位，避免 UI 显示已停止但再次补跑仍 409。
    with _RETRYING_LOCK:
        if not _thread_alive(thread_id):
            _clear_state_locked(key)
    if injected:
        # 异常注入通常会很快让线程进入 finally/release；若浏览器/CDP/短信等待阻塞导致线程
        # 短时间内仍未退出，延迟清理占位，避免 UI 已显示“已停止”但再次补跑仍 409。
        def _delayed_release() -> None:
            time.sleep(5)
            with _RETRYING_LOCK:
                if key in _RETRYING and key in _STOP_REQUESTED:
                    try:
                        acc = db.get_account_by_email(email)
                        status = str((acc or {}).get("codex_status") or "").lower()
                    except Exception:
                        status = ""
                    if status == "stopped":
                        logger.warning("[Codex 补跑] 停止后延迟释放占位：email=%s thread_id=%s", email, thread_id or "-")
                        _clear_state_locked(key)

        threading.Thread(target=_delayed_release, name=f"codex-stop-release-{key}", daemon=True).start()
    try:
        p = log_path(email)
        p.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime as _dt
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{_dt.now().strftime('%H:%M:%S')} [WARNING] [Codex 补跑] 用户手动停止，已发送停止信号 injected={injected}\n")
    except Exception:
        logger.exception("写入 Codex 停止日志失败")
    return {"ok": True, "message": "已发送停止信号", "state": "stopped", "running": True, "injected": injected}


def run_twofa_worker(
    email: str,
    *,
    clear_log: bool = True,
    target_log_path: str | Path | None = None,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> dict:
    """只重新登录并检查/补齐 Authenticator 2FA，不重复执行 Codex OAuth。"""
    fh: logging.FileHandler | None = None
    root_logger = logging.getLogger()
    result: dict = {"status": "failed", "ok": False, "message": "2FA 重试未返回结果"}
    account_route = None
    route_summary: dict = {}
    key = (email or "").strip().lower()
    try:
        account = db.get_account_by_email(email) or {}
        if task_id is None:
            task_id = account_task_store.create_task(
                task_type="twofa_retry",
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(task_trigger or "manual"),
            )
        with _RETRYING_LOCK:
            _RUNNING_THREADS[key] = threading.get_ident()
            _RESERVED_AT[key] = time.time()
        check_stop_requested(email)
        account_task_store.start_task(task_id, message="开始重新检查并补齐 Authenticator 2FA")

        path = Path(target_log_path) if target_log_path else log_path(email)
        path.parent.mkdir(parents=True, exist_ok=True)
        if clear_log:
            path.write_text("", encoding="utf-8")
        thread_name = threading.current_thread().name
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        fh.addFilter(lambda record: record.threadName == thread_name)
        root_logger.addHandler(fh)

        import config as config_pkg

        config_pkg.reload_all()
        from config import codex as codex_cfg
        from config import roxybrowser as roxy_cfg

        oauth_driver = str(getattr(codex_cfg, "CODEX_OAUTH_DRIVER", "protocol") or "protocol").strip().lower()
        if oauth_driver == "same_as_registration":
            oauth_driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
        if oauth_driver not in {"roxy", "roxybrowser", "fingerprint", "browser"}:
            raise RuntimeError(f"2FA 自动重试当前仅支持 Roxy 驱动，当前驱动={oauth_driver or 'protocol'}")

        from core.account_proxy import acquire_account_proxy

        account_route = acquire_account_proxy(
            account_id=int(account.get("id") or 0) or None,
            email=email,
            purpose="twofa-retry",
        )
        route_summary = account_route.public_dict()
        account_task_store.append_event(
            task_id,
            stage="network",
            message="已分配 2FA 重试线路",
            detail={
                "network_route": route_summary.get("network_route"),
                "proxy_mode": account_route.mode,
                "proxy_provider": account_route.provider,
                "proxy_region": account_route.region,
            },
        )
        account_task_store.append_event(
            task_id,
            stage="twofa",
            message="重新登录 ChatGPT，先检查远端开关，未开启时重新 enrollment",
        )
        from core.roxy_codex_oauth import run_roxy_chatgpt_account_action

        run_roxy_chatgpt_account_action(
            email,
            proxy=account_route.proxy_url,
            action=_build_roxy_twofa_setup(email, task_id),
        )
        check_stop_requested(email)
        result = {
            "status": "success",
            "ok": True,
            "message": "Authenticator 2FA 远端状态已确认启用",
            "proxy_provider": account_route.provider,
            "proxy_region": account_route.region,
            "proxy_mode": account_route.mode,
        }
        return result
    except CodexRetryStopped as exc:
        result = {"status": "stopped", "ok": False, "message": str(exc) or "用户手动停止 2FA 重试"}
        return result
    except Exception as exc:
        result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}
        logger.exception("[2FA 重试] %s 异常", email)
        return result
    finally:
        if fh is not None:
            try:
                root_logger.removeHandler(fh)
                fh.close()
            except Exception:
                pass
        if account_route is not None:
            account_route.release(reason=f"twofa-retry-{email}")
        release(email)
        with _RETRYING_LOCK:
            if key:
                _STOP_REQUESTED.discard(key)
        task_status = "success" if result.get("ok") else "cancelled" if result.get("status") == "stopped" else "failed"
        try:
            account_task_store.finish_task(
                task_id,
                status=task_status,
                message=(
                    "Authenticator 2FA 已确认启用"
                    if task_status == "success"
                    else "2FA 重试已停止" if task_status == "cancelled" else "2FA 重试失败"
                ),
                error=None if task_status == "success" else str(result.get("message") or "2FA 重试失败"),
                result_summary={"ok": bool(result.get("ok")), "status": result.get("status"), "message": result.get("message")},
                route={
                    "network_route": route_summary.get("network_route"),
                    "proxy_mode": result.get("proxy_mode") or getattr(account_route, "mode", None),
                    "proxy_provider": result.get("proxy_provider") or getattr(account_route, "provider", None),
                    "proxy_region": result.get("proxy_region") or getattr(account_route, "region", None),
                    "proxy_used": route_summary.get("proxy_used"),
                },
                validation_method="chatgpt_security_settings",
            )
        except Exception:
            logger.exception("[2FA 重试] 写入任务实例失败：task_id=%s email=%s", task_id or "-", email)


def run_worker(
    email: str,
    *,
    batch_label: str | None = None,
    clear_log: bool = True,
    target_log_path: str | Path | None = None,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> dict:
    """执行一次 Codex 补跑，并把脱敏后的关键阶段写入统一任务实例。"""
    fh: logging.FileHandler | None = None
    root_logger = logging.getLogger()
    result: dict = {"status": "failed", "ok": False, "message": "Codex 补跑未返回结果"}
    account_route = None
    route_summary: dict = {}
    oauth_driver = ""
    key = (email or "").strip().lower()
    sms_batch_bound = False
    if batch_label:
        from core import sms_provider

        # WebUI 会在同一批次标签后追加“#序号/总数”；去掉序号后共享一次选国结果。
        sms_provider.set_sms_batch_context(f"codex-retry:{batch_label.split(' #', 1)[0]}")
        sms_batch_bound = True
    try:
        if task_id is None:
            account = db.get_account_by_email(email) or {}
            task_id = account_task_store.create_task(
                task_type="codex_retry",
                account_id=int(account.get("id") or 0) or None,
                email=email,
                trigger=str(task_trigger or "manual"),
            )
        with _RETRYING_LOCK:
            _RUNNING_THREADS[key] = threading.get_ident()
            _RESERVED_AT[key] = time.time()
        check_stop_requested(email)

        account_task_store.start_task(task_id, message="开始补跑 Codex OAuth 授权")

        from core.codex_oauth import run_codex_oauth

        path = Path(target_log_path) if target_log_path else log_path(email)
        path.parent.mkdir(parents=True, exist_ok=True)
        if clear_log:
            path.write_text("", encoding="utf-8")

        thread_name = threading.current_thread().name
        fh = logging.FileHandler(str(path), encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        fh.addFilter(lambda record: record.threadName == thread_name)
        root_logger.addHandler(fh)

        try:
            import config as config_pkg
            config_pkg.reload_all()
            from config import codex as codex_cfg
            from config import roxybrowser as roxy_cfg
            logger.info(
                "[Codex 补跑] 已热加载配置：CODEX_OAUTH_DRIVER=%s ROXY_OPEN_HEADLESS=%s ROXY_KEEP_BROWSER_OPEN=%s",
                getattr(codex_cfg, "CODEX_OAUTH_DRIVER", ""),
                getattr(roxy_cfg, "ROXY_OPEN_HEADLESS", ""),
                getattr(roxy_cfg, "ROXY_KEEP_BROWSER_OPEN", ""),
            )
        except Exception as exc:
            logger.warning("[Codex 补跑] 配置热加载失败，将继续使用当前内存配置：%s: %s", type(exc).__name__, exc)

        if batch_label:
            logger.info("[Codex 补跑] 批量任务：%s", batch_label)
        logger.info("[Codex 补跑] 开始：%s", email)
        logger.info(
            "[Codex 补跑] 阶段说明：获取授权地址 → 登录邮箱 → 邮箱 OTP → "
            "缺失时先设置 2FA → 手机验证 → 捕获 callback → 提交/保存凭证"
        )
        check_stop_requested(email)
        from config import codex as codex_cfg
        from config import roxybrowser as roxy_cfg
        oauth_driver = str(getattr(codex_cfg, "CODEX_OAUTH_DRIVER", "protocol") or "protocol").strip().lower()
        if oauth_driver == "same_as_registration":
            oauth_driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
        account_task_store.append_event(
            task_id,
            stage="driver",
            message=f"使用 {oauth_driver or 'protocol'} 驱动执行 Codex OAuth",
            detail={"oauth_driver": oauth_driver or "protocol"},
        )
        # Browser Use / Skyvern 的浏览器运行在云端，只能使用云服务自身的代理设置；
        # protocol / Roxy / Cloak 才能注入本地申请的 1024Proxy 或静态代理池。
        if oauth_driver not in {"browser_use", "browseruse", "browser-use", "bu", "skyvern", "sv"}:
            from core.account_proxy import acquire_account_proxy
            account = db.get_account_by_email(email) or {}
            account_route = acquire_account_proxy(
                account_id=int(account.get("id") or 0) or None,
                email=email,
                purpose="codex-oauth",
            )
            route_summary = account_route.public_dict()
            logger.info(
                "[Codex 补跑] 账号网络：provider=%s region=%s route=%s proxy=%s",
                account_route.provider,
                account_route.region or "-",
                account_route.public_dict().get("network_route"),
                account_route.public_dict().get("proxy_used") or "-",
            )
            account_task_store.append_event(
                task_id,
                stage="network",
                message="已分配账号补跑线路",
                detail={
                    "network_route": route_summary.get("network_route"),
                    "proxy_mode": account_route.mode,
                    "proxy_provider": account_route.provider,
                    "proxy_region": account_route.region,
                    "proxy_used": route_summary.get("proxy_used"),
                },
            )
        else:
            route_summary = {"network_route": "cloud_driver"}
            account_task_store.append_event(
                task_id,
                stage="network",
                message="云端浏览器驱动使用平台线路",
                detail={"network_route": "cloud_driver"},
            )
        account = db.get_account_by_email(email) or {}
        needs_twofa = (
            not bool(str(account.get("totp_secret") or "").strip())
            or _totp_setup_pending(account)
        )
        account_task_store.append_event(
            task_id,
            stage="oauth",
            message=(
                "账号缺少 2FA，将先设置 Authenticator 再完成 OAuth"
                if needs_twofa and oauth_driver in {"roxy", "roxybrowser", "fingerprint", "browser"}
                else "开始获取授权地址并完成邮箱、短信与 callback 流程"
            ),
        )
        if needs_twofa and oauth_driver in {"roxy", "roxybrowser", "fingerprint", "browser"}:
            from core.roxy_codex_oauth import run_roxy_codex_oauth

            result = run_roxy_codex_oauth(
                email,
                proxy=(account_route.proxy_url if account_route is not None else None),
                force=True,
                before_oauth_setup=_build_roxy_twofa_setup(email, task_id),
            )
        else:
            result = run_codex_oauth(
                email,
                proxy=(account_route.proxy_url if account_route is not None else None),
                force=True,
            )
        if account_route is not None:
            # 标准任务页需要展示补跑实际使用的平台/地区；只写公开元数据，绝不落代理凭据。
            result["proxy_provider"] = account_route.provider
            result["proxy_region"] = account_route.region
            result["proxy_mode"] = account_route.mode
        check_stop_requested(email)
        logger.info(
            "[Codex 补跑] 结果：status=%s ok=%s file=%s callback=%s",
            result.get("status"), result.get("ok"), result.get("file_path"), result.get("callback_url"),
        )
        account_task_store.append_event(
            task_id,
            stage="oauth_result",
            message="Codex OAuth 已返回成功结果" if result.get("ok") else "Codex OAuth 返回失败结果",
            level="INFO" if result.get("ok") else "ERROR",
            detail={
                "ok": bool(result.get("ok")),
                "status": result.get("status"),
                "message": result.get("message"),
                "credential_saved": bool(result.get("file_path")),
            },
        )
        result_status = result.get("status", "failed")
        if result.get("ok"):
            db.update_account_codex_status(email, "success", None)
            logger.info("[Codex 补跑] %s 成功", email)
        elif result_status == "deactivated":
            db.update_account_codex_status(email, "deactivated", result.get("message"))
            logger.warning("[Codex 补跑] %s 账号已废: %s", email, result.get("message"))
        else:
            db.update_account_codex_status(email, result_status, result.get("message"))
            logger.warning("[Codex 补跑] %s 失败: %s", email, result.get("message"))
        return result
    except CodexRetryStopped as exc:
        result = {"status": "stopped", "ok": False, "message": str(exc) or "用户手动停止 Codex 补跑"}
        db.update_account_codex_status(email, "stopped", result["message"])
        logger.warning("[Codex 补跑] %s 已停止: %s", email, result["message"])
        return result
    except Exception as exc:
        if is_stop_requested(email):
            result = {"status": "stopped", "ok": False, "message": "用户手动停止 Codex 补跑"}
            db.update_account_codex_status(email, "stopped", result["message"])
            logger.warning("[Codex 补跑] %s 已停止", email)
            return result
        result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {exc}"}
        db.update_account_codex_status(email, "failed", result["message"])
        logger.exception("[Codex 补跑] %s 异常", email)
        logger.error("[Codex 补跑] 已结束：异常失败")
        return result
    finally:
        try:
            logger.info("[Codex 补跑] 结束：%s", email)
            if fh is not None:
                root_logger.removeHandler(fh)
                fh.close()
        finally:
            if account_route is not None:
                account_route.release(reason=f"codex-oauth-{email}")
            release(email)
            with _RETRYING_LOCK:
                if key:
                    _STOP_REQUESTED.discard(key)
            result_status = str(result.get("status") or "failed").lower()
            task_status = (
                "success" if result.get("ok")
                else "deactivated" if result_status == "deactivated"
                else "cancelled" if result_status in {"stopped", "cancelled"}
                else "failed"
            )
            route = {
                "network_route": route_summary.get("network_route"),
                "proxy_mode": result.get("proxy_mode") or getattr(account_route, "mode", None),
                "proxy_provider": result.get("proxy_provider") or getattr(account_route, "provider", None),
                "proxy_region": result.get("proxy_region") or getattr(account_route, "region", None),
                "proxy_used": route_summary.get("proxy_used"),
            }
            try:
                account_task_store.finish_task(
                    task_id,
                    status=task_status,
                    message=(
                        "Codex 补跑成功" if task_status == "success"
                        else "Codex 补跑已停止" if task_status == "cancelled"
                        else "账号已停用" if task_status == "deactivated"
                        else "Codex 补跑失败"
                    ),
                    error=None if task_status == "success" else str(result.get("message") or "Codex 补跑失败"),
                    result_summary={
                        "ok": bool(result.get("ok")),
                        "status": result_status,
                        "message": result.get("message"),
                        "credential_saved": bool(result.get("file_path")),
                        "oauth_driver": oauth_driver or None,
                    },
                    route=route,
                    validation_method=f"codex_oauth:{oauth_driver or 'unknown'}",
                )
            except Exception:
                logger.exception("[Codex 补跑] 写入任务实例失败：task_id=%s email=%s", task_id or "-", email)
            if sms_batch_bound:
                from core import sms_provider

                sms_provider.clear_sms_batch_context()
