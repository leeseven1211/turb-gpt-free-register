"""持久补传 Codex 凭证；只请求 Sub2API，不执行 OpenAI 登录或刷新。"""

from __future__ import annotations

import logging
import threading

from core.integrations.sub2api import client
from core.operations import task_gateway
from core.operations.runtime import OperationCancelled
from core.runtime import scheduler_state
from core.runtime.periodic import PeriodicThread
from core.storage import codex, records, sub2api as store

logger = logging.getLogger(__name__)
TASK_TYPE = "sub2api_sync"
RESOURCE_FAMILY = "openai_interactive"
credential_generation = store.credential_generation
_START_LOCK = threading.Lock()
_SCHEDULER = PeriodicThread("sub2api-sync-producer")


class _Superseded(RuntimeError):
    """凭证已更新，旧执行只退出，由新代际继续补传。"""


class _Blocked(client.Sub2ApiSyncError):
    def __init__(self, status, code, message):
        super().__init__("read_credential", code, message)
        self.blocked_status = status


def _credential_reference(filename, credential_id=None, *, conn=None):
    if credential_id:
        return records.get_row(records.CODEX_CREDENTIALS, int(credential_id), conn=conn)
    return records.get_row_by(records.CODEX_CREDENTIALS, "filename", filename, conn=conn)


def _checked_reference(row, *, conn=None):
    credential = _credential_reference(row["filename"], row.get("credential_id"), conn=conn)
    if not credential or not isinstance(credential.get("content"), dict):
        raise _Blocked(
            "blocked_missing_credential",
            "sub2api_credential_missing",
            "本地 Codex 凭证已不存在，等待手动恢复后再次排队",
        )
    if credential.get("archived"):
        raise _Blocked("blocked_archived", "sub2api_target_archived", "Codex 凭证已归档，已停止补传")
    if str(credential["content"].get("email") or "").casefold() != str(row["email"]).casefold():
        raise _Blocked(
            "blocked_credential_identity", "sub2api_credential_identity_mismatch", "本地凭证身份发生变化，等待手动核对"
        )
    return credential


def _read(filename):
    record = _credential_reference(filename)
    if record is None:
        # OAuth 可能在保存新套餐时改名，旧任务通过稳定凭证行 ID 找到当前名称。
        for row in reversed(store.list_jobs(filename=filename)):
            record = _credential_reference(filename, row.get("credential_id"))
            if record:
                break
    if not record or not isinstance(record.get("content"), dict):
        raise _Blocked(
            "blocked_missing_credential",
            "sub2api_credential_missing",
            "本地 Codex 凭证已不存在，等待手动恢复后再次排队",
        )
    return record["content"], record["filename"]


def _ids(remote_ids):
    if remote_ids is None:
        return None
    if not isinstance(remote_ids, (list, tuple)) or any(type(value) is not int or value <= 0 for value in remote_ids):
        raise ValueError("Sub2API 账号 ID 必须为正整数列表")
    return list(dict.fromkeys(remote_ids))


def _response(items):
    active = [row for row in items if row["status"] in store.ACTIVE]
    first = active[0] if active else (items[0] if items else {})
    return {
        "accepted": True,
        "pending": any(row["status"] not in ("success", "superseded") for row in items),
        "items": items,
        "run_id": first.get("run_id"),
        "task_id": first.get("task_id"),
    }


def _queue(filename, *, remote_account_ids=None, trigger="manual", delay_seconds=0, backend=None, failure=None):
    auth, name = _read(filename)
    email = str(auth.get("email") or "").strip()
    account = codex.get_account_by_email(email) if email else None
    backend = client.configured_backend_identity() if backend is None else backend
    if not backend:
        raise client.Sub2ApiSyncError("configuration", "sub2api_config_invalid", "Sub2API 后端尚未配置")
    return store.queue(
        name,
        backend=backend,
        generation=credential_generation(auth),
        credential_id=int(_credential_reference(name)["id"]),
        account_id=int(account["id"]) if account else None,
        email=email,
        remote_account_ids=_ids(remote_account_ids),
        trigger=str(trigger or "manual")[:80],
        delay_seconds=max(0, float(delay_seconds)),
        failure=failure,
    )


def queue_sync(filename: str, *, remote_account_ids=None, trigger="manual", delay_seconds=0, expected_backend=None):
    """显式请求先持久化；父授权占租约时保留 pending，稍后再次扫描。"""
    items = _queue(
        filename,
        remote_account_ids=remote_account_ids,
        trigger=trigger,
        delay_seconds=delay_seconds,
        backend=expected_backend,
    )
    enqueue_due()
    selected = {row["id"] for row in items}
    current_name = items[0]["filename"] if items else filename
    return _response([row for row in store.list_jobs(filename=current_name) if row["id"] in selected])


def record_sync_failure(filename: str, summary: dict):
    """保存原请求的后端与已确认远端 ID，不因配置切换迁移旧目标。"""
    remote_id = summary.get("sub2api_account_id")
    backend = summary.get("backend_identity") or summary.get("backend") or client.configured_backend_identity()
    failure = {
        "stage": str(summary.get("stage") or "upload")[:80],
        "error_code": str(summary.get("error_code") or "sub2api_sync_failed")[:120],
        # 不接收远端正文；调用方只传分类后的本地文案。
        "error": str(summary.get("error") or "Sub2API 同步失败")[:500],
    }
    items = _queue(
        filename,
        remote_account_ids=[int(remote_id)] if remote_id else None,
        trigger="oauth_failure",
        delay_seconds=15,
        backend=backend,
        failure=failure,
    )
    return _response(items)


def sync_credential_id(filename: str, auth: dict) -> int | None:
    """在远端请求前固定本次凭据行，防止同名凭据被替换后误记成功。"""
    reference = _credential_reference(filename)
    if (
        not reference or not isinstance(reference.get("content"), dict)
        or credential_generation(reference["content"]) != credential_generation(auth)
    ):
        return None
    return int(reference["id"])


def record_sync_success(credential_id: int | None, auth: dict, result: dict) -> bool:
    """将同次真实上传回执与稳定凭据行对账，不重新上传或改写其他远端目标。"""
    if (
        not credential_id or not result.get("uploaded") or not result.get("enabled")
        or not result.get("backend_identity")
        or type(result.get("sub2api_account_id")) is not int
        or result["sub2api_account_id"] <= 0
    ):
        return False
    return store.confirm_sync(
        credential_id=credential_id,
        backend=result["backend_identity"],
        generation=credential_generation(auth),
        remote_account_id=result["sub2api_account_id"],
        count_upload=True,
    )


def _reconcile_missing_target(context, row: dict, auth: dict) -> client.ReplacementCandidate | None:
    """核验唯一替代目标；Token 被隐藏时原子排队同步，不能直接记为成功。"""
    def checkpoint():
        context.checkpoint()
        if context.is_cancel_requested(force=True):
            raise OperationCancelled("用户已取消 Sub2API 补传")
        current = _checked_reference(row)
        if credential_generation(current["content"]) != row["generation"]:
            raise client.Sub2ApiSyncError(
                "resolve_account", "sub2api_credential_generation_changed",
                "候选核验期间凭据已更新，沿新代际继续处理",
            )

    replacement = client.find_confirmed_replacement(
        auth, int(row["remote_account_id"]),
        checkpoint=checkpoint, expected_backend=row["backend"],
    )
    if replacement is None:
        return None
    checkpoint()
    saved = store.confirm_sync(
        credential_id=int(row["credential_id"]),
        backend=row["backend"], generation=row["generation"],
        remote_account_id=replacement.account_id,
        replaced_job_id=int(row["id"]), replaced_run_id=int(context.run_id),
        fence=context.execution_fence,
        credentials_confirmed=replacement.credentials_confirmed,
    )
    if not saved:
        logger.info("Sub2API 替代目标身份已核验，本地代际、取消或并发状态尚不允许提交")
    return replacement if saved else None


def _submit(row, conn):
    try:
        credential = _checked_reference(row, conn=conn)
    except _Blocked as exc:
        return {"accepted": False, "blocked_status": exc.blocked_status, "error_code": exc.code, "error": str(exc)}
    row["previous_generation"] = row["generation"]
    row.update(
        filename=credential["filename"],
        credential_id=int(credential["id"]),
        generation=credential_generation(credential["content"]),
    )
    key = f"sub2api:{row['id']}:{row['generation']}:{row['dispatch_no'] + 1}"
    return task_gateway.submit_durable_operation(
        task_type=TASK_TYPE,
        account_id=row["account_id"],
        email=row["email"],
        trigger=row["trigger"],
        source_id=key,
        idempotency_key=key,
        resource_family=RESOURCE_FAMILY,
        data={"sync_job_id": row["id"], "generation": row["generation"]},
        dispatch=False,
        conn=conn,
    )


def register_actions() -> None:
    task_gateway.register_operation_actions(
        TASK_TYPE,
        retry_handler=task_gateway.default_operation_retry,
        cancel_handler=task_gateway.default_operation_cancel,
        terminate_handler=task_gateway.default_operation_terminate,
    )


def register_handler() -> None:
    task_gateway.register_operation_handler(TASK_TYPE, _handle, config_allowlist=())
    register_actions()


def enqueue_due():
    """只投递已存在的补传记录，绝不产生 OAuth 或 Token 刷新任务。"""
    register_handler()
    backend = client.configured_backend_identity()
    result = store.enqueue_due(backend, _submit, include_retries=_enabled())
    # 已存在的 queued Run 也要唤醒；重启后由共享 dispatcher 收口失去 worker 的 Run。
    task_gateway.notify_dispatch()
    return result


def _handle(context):
    data = context.run.get("data") or {}
    report = getattr(context, "report", None)
    with context.lease(resource_family=RESOURCE_FAMILY, scope_kind="final"):
        if callable(report):
            report(stage="preflight", state="running", message="正在核验 Sub2API 同步任务与本地凭证")
        row = store.begin(int(data["sync_job_id"]), generation=str(data["generation"]), run_id=context.run_id)
        if row is None:
            if callable(report):
                report(stage="preflight", state="success", message="旧代际补传已由新凭证接续")
                report(stage="sub2api_sync", state="skipped", message="旧代际补传无需执行")
            return task_gateway.OperationResult.success({"superseded": True}, message="旧代际补传已由新凭证接续")
        generation = row["generation"]

        def checkpoint():
            context.checkpoint()
            if context.is_cancel_requested(force=True):
                raise OperationCancelled("用户已取消 Sub2API 补传")
            if client.configured_backend_identity() != row["backend"]:
                raise client.Sub2ApiSyncError(
                    "configuration", "sub2api_backend_changed", "Sub2API 后端已变化，旧目标保留等待原后端"
                )
            credential = _checked_reference(row)
            if credential["filename"] != row["filename"]:
                store.rename_reference(
                    row["id"], filename=credential["filename"], generation=generation, run_id=context.run_id
                )
                row["filename"] = credential["filename"]
            latest = credential["content"]
            if credential_generation(latest) != generation:
                _queue(
                    row["filename"],
                    remote_account_ids=[row["remote_account_id"]] if row["remote_account_id"] else None,
                    trigger="generation_changed",
                    backend=row["backend"],
                )
                raise _Superseded()

        sync_started = False
        try:
            checkpoint()
            auth = _checked_reference(row)["content"]
            if callable(report):
                report(stage="preflight", state="success", message="Sub2API 凭证与后端校验通过")
                report(stage="sub2api_sync", state="running", message="正在上传并启用 Sub2API 凭证")
            sync_started = True
            if row["remote_account_id"]:
                result = client.update_and_enable_configured_account(
                    auth, int(row["remote_account_id"]), checkpoint=checkpoint, expected_backend=row["backend"]
                )
            else:
                # 旧上传入口每个请求前执行 checkpoint，配置切换也不得继续发送。
                result = client.upload_and_enable_configured_codex_oauth_credential(
                    auth, checkpoint=checkpoint, expected_backend=row["backend"]
                )
            checkpoint()
            if not result.get("uploaded") or not result.get("enabled"):
                raise client.Sub2ApiSyncError(
                    "confirm",
                    "sub2api_sync_unconfirmed",
                    "Sub2API 尚未确认凭证更新和调度启用",
                    uploaded=bool(result.get("uploaded")),
                    sub2api_account_id=result.get("sub2api_account_id"),
                )
            saved = store.finish(
                row["id"],
                generation=generation,
                run_id=context.run_id,
                status="success",
                stage="complete",
                remote_account_id=result.get("sub2api_account_id"),
                fence=context.execution_fence,
                write_metadata=lambda: codex.mark_codex_sub2_uploaded(
                    row["filename"], sub2api_account_id=result.get("sub2api_account_id"),
                    backend_identity=row["backend"],
                ),
            )
            if callable(report):
                report(stage="sub2api_sync", state="success", message="Sub2API 凭证同步与调度启用已确认")
            return task_gateway.OperationResult.success(
                {"synced": saved, "sub2api_account_id": result.get("sub2api_account_id")},
                message="Sub2API 凭证同步与调度启用已确认",
            )
        except _Superseded:
            if callable(report):
                report(stage="sub2api_sync" if sync_started else "preflight", state="success", message="凭证代际已更新，等待新代际补传")
                if not sync_started:
                    report(stage="sub2api_sync", state="skipped", message="等待新代际补传")
            return task_gateway.OperationResult.success({"superseded": True}, message="凭证代际已更新，等待新代际补传")
        except OperationCancelled:
            store.cancel(row["id"], generation=generation, run_id=context.run_id, execution_id=context.execution_id)
            raise
        except task_gateway.OperationLeaseLost:
            raise
        except _Blocked as exc:
            if callable(report):
                report(stage="sub2api_sync" if sync_started else "preflight", state="failed", message=str(exc), detail={"error_code": exc.code})
            return _blocked_result(context, row, exc)
        except Exception as exc:
            known = isinstance(exc, client.Sub2ApiSyncError)
            code = exc.code if known else "sub2api_sync_execution_error"
            stage = exc.stage if known else "sync"
            error = str(exc) if known else f"Sub2API 补传在 {stage} 阶段发生 {type(exc).__name__}"
            if code == "sub2api_account_missing" and row.get("remote_account_id"):
                try:
                    replacement = _reconcile_missing_target(context, row, auth)
                    if replacement:
                        if callable(report):
                            report(stage="sub2api_sync", state="success", message="已与同身份的健康 Sub2API 账号对账")
                        return task_gateway.OperationResult.success(
                            {"superseded": True, "previous_sub2api_account_id": row["remote_account_id"],
                             "reconciled": True, "replacement_sub2api_account_id": replacement.account_id,
                             "replacement_credentials_redacted": not replacement.credentials_confirmed},
                            message=(
                                "旧 Sub2API 目标已失效，已与同身份的健康账号对账"
                                if replacement.credentials_confirmed
                                else "旧 Sub2API 目标已替代，新目标同步状态由持久队列继续核对"
                            ),
                        )
                except OperationCancelled:
                    store.cancel(row["id"], generation=generation, run_id=context.run_id,
                                 execution_id=context.execution_id)
                    raise
                except (task_gateway.OperationLeaseLost, _Superseded):
                    raise
                except _Blocked as blocked:
                    if callable(report):
                        report(stage="sub2api_sync" if sync_started else "preflight", state="failed", message=str(blocked), detail={"error_code": blocked.code})
                    return _blocked_result(context, row, blocked)
                except client.Sub2ApiSyncError as reconcile_error:
                    # 候选核验失败不改变原目标事实，保留本次 404 分类及原重试入口。
                    logger.info("Sub2API 旧目标替代核验未完成：阶段=%s 原因=%s",
                                reconcile_error.stage, reconcile_error.code)
            backend_changed = code == "sub2api_backend_changed"
            delay = min(300, 15 * 2 ** min(max(0, row["attempt_count"] - 1), 5))
            context.checkpoint()
            # 远端异常也可能晚于凭证更新，旧失败不能写入新代际元数据。
            try:
                credential = _checked_reference(row)
                if credential["filename"] != row["filename"]:
                    store.rename_reference(
                        row["id"], filename=credential["filename"], generation=generation, run_id=context.run_id
                    )
                    row["filename"] = credential["filename"]
                latest = credential["content"]
            except _Blocked as blocked:
                if callable(report):
                    report(stage="sub2api_sync" if sync_started else "preflight", state="failed", message=str(blocked), detail={"error_code": blocked.code})
                return _blocked_result(context, row, blocked)
            if credential_generation(latest) != generation:
                _queue(
                    row["filename"],
                    remote_account_ids=[row["remote_account_id"]] if row["remote_account_id"] else None,
                    trigger="generation_changed",
                    backend=row["backend"],
                )
                if callable(report):
                    report(stage="sub2api_sync" if sync_started else "preflight", state="success", message="旧补传失败已由新凭证代际接续")
                return task_gateway.OperationResult.success(
                    {"superseded": True}, message="旧补传失败已由新凭证代际接续"
                )
            saved = store.finish(
                row["id"],
                generation=generation,
                run_id=context.run_id,
                status="blocked_backend" if backend_changed else "pending",
                stage=stage,
                error_code=code,
                error=error,
                remote_account_id=getattr(exc, "sub2api_account_id", None),
                delay_seconds=delay,
                fence=context.execution_fence,
                write_metadata=lambda: codex.mark_codex_sub2_sync_error(row["filename"], f"{code}: {error}"),
            )
            if callable(report):
                report(stage="sub2api_sync" if sync_started else "preflight", state="failed", message=error, detail={"error_code": code})
            return task_gateway.OperationResult.failed(
                error, {"retry_pending": saved, "stage": stage, "error_code": code}
            )


def _blocked_result(context, row, exc):
    store.finish(
        row["id"],
        generation=row["generation"],
        run_id=context.run_id,
        status=exc.blocked_status,
        stage=exc.stage,
        error_code=exc.code,
        error=str(exc),
        fence=context.execution_fence,
    )
    return task_gateway.OperationResult.failed(str(exc), {"blocked": True, "stage": exc.stage, "error_code": exc.code})


def _enabled():
    from config import sub2api as cfg

    return bool(getattr(cfg, "SUB2API_SYNC_RETRY_ENABLED", False) or getattr(cfg, "SUB2API_MONITOR_ENABLED", False))


def _scheduler_loop():
    scheduler_state.run_periodic(
        task="sub2api_sync_retry",
        label="Sub2API 持久补传",
        work=enqueue_due,
        enabled=_scheduler_ready,
        interval_seconds=lambda: 15,
        initial_delay_seconds=0,
        stop=_SCHEDULER.stop_event,
        lifecycle=_SCHEDULER,
    )


def _scheduler_ready():
    if _enabled():
        return True
    try:
        backend = client.configured_backend_identity()
    except client.Sub2ApiSyncError:
        return False
    return store.has_dispatch_requests(backend)


def _register_scheduler_handler() -> None:
    register_handler()


def start_periodic_sync() -> bool:
    """Start one observable producer; work remains behind runtime admission."""
    try:
        started = _SCHEDULER.start(_scheduler_loop, before_start=_register_scheduler_handler)
    except Exception:
        logger.exception("Periodic scheduler start failed; it may be retried")
        return False

    # Managed loop starts at delay=0 and obeys admission. Preserve the old
    # synchronous best-effort request only for an unmanaged standalone caller.
    from core.runtime.process import get_runtime_context
    if started and get_runtime_context() is None and _enabled():
        try:
            enqueue_due()
        except client.Sub2ApiSyncError as exc:
            logger.warning("Sub2API startup enqueue deferred: stage=%s code=%s", exc.stage, exc.code)
        except Exception as exc:
            logger.warning("Sub2API startup enqueue deferred: %s", type(exc).__name__)

    return started


def stop_periodic_sync(timeout: float = 2.0) -> bool:
    return _SCHEDULER.stop(timeout)


def scheduler_status() -> dict:
    return _SCHEDULER.status(enabled=_enabled())


def status():
    counts = store.job_counts()
    return {**scheduler_status(), "counts": counts, "total": sum(counts.values())}
