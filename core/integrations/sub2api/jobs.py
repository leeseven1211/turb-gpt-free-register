"""持久补传 Codex 凭证；只请求 Sub2API，不执行 OpenAI 登录或刷新。"""

from __future__ import annotations

import logging
import threading

from core.integrations.sub2api import client
from core.operations import task_gateway
from core.operations.runtime import OperationCancelled
from core.runtime import scheduler_state
from core.storage import codex, records, sub2api as store

logger = logging.getLogger(__name__)
TASK_TYPE = "sub2api_sync"
RESOURCE_FAMILY = "openai_interactive"
credential_generation = store.credential_generation
_START_LOCK = threading.Lock()
_STARTED = False


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
    account = records.get_row(records.ACCOUNTS, int(row["account_id"]), conn=conn) if row.get("account_id") else None
    if credential.get("archived") or (account and account.get("archived")):
        raise _Blocked("blocked_archived", "sub2api_target_archived", "账号或 Codex 凭证已归档，已停止补传")
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
        "pending": any(row["status"] not in ("success",) for row in items),
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


def enqueue_due():
    """只投递已存在的补传记录，绝不产生 OAuth 或 Token 刷新任务。"""
    task_gateway.register_operation_handler(TASK_TYPE, _handle, config_allowlist=())
    backend = client.configured_backend_identity()
    result = store.enqueue_due(backend, _submit, include_retries=_enabled())
    # 已存在的 queued Run 也要唤醒；重启后由共享 dispatcher 收口失去 worker 的 Run。
    task_gateway.notify_dispatch()
    return result


def _handle(context):
    data = context.run.get("data") or {}
    with context.lease(resource_family=RESOURCE_FAMILY):
        row = store.begin(int(data["sync_job_id"]), generation=str(data["generation"]), run_id=context.run_id)
        if row is None:
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

        try:
            checkpoint()
            auth = _checked_reference(row)["content"]
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
                write_metadata=lambda: codex.mark_codex_sub2_uploaded(row["filename"]),
            )
            return task_gateway.OperationResult.success(
                {"synced": saved, "sub2api_account_id": result.get("sub2api_account_id")},
                message="Sub2API 凭证同步与调度启用已确认",
            )
        except _Superseded:
            return task_gateway.OperationResult.success({"superseded": True}, message="凭证代际已更新，等待新代际补传")
        except OperationCancelled:
            store.cancel(row["id"], generation=generation, run_id=context.run_id, execution_id=context.execution_id)
            raise
        except task_gateway.OperationLeaseLost:
            raise
        except _Blocked as exc:
            return _blocked_result(context, row, exc)
        except Exception as exc:
            known = isinstance(exc, client.Sub2ApiSyncError)
            code = exc.code if known else "sub2api_sync_execution_error"
            stage = exc.stage if known else "sync"
            error = str(exc) if known else f"Sub2API 补传在 {stage} 阶段发生 {type(exc).__name__}"
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
                return _blocked_result(context, row, blocked)
            if credential_generation(latest) != generation:
                _queue(
                    row["filename"],
                    remote_account_ids=[row["remote_account_id"]] if row["remote_account_id"] else None,
                    trigger="generation_changed",
                    backend=row["backend"],
                )
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
    )


def _scheduler_ready():
    if _enabled():
        return True
    try:
        backend = client.configured_backend_identity()
    except client.Sub2ApiSyncError:
        return False
    return store.has_dispatch_requests(backend)


def start_periodic_sync():
    """关闭时保留休眠线程以支持热启用；恢复仍由 PostgreSQL 与 durable 网关裁决。"""
    global _STARTED
    with _START_LOCK:
        if _STARTED:
            return False
        task_gateway.register_operation_handler(TASK_TYPE, _handle, config_allowlist=())
        threading.Thread(target=_scheduler_loop, name="sub2api-sync-producer", daemon=True).start()
        _STARTED = True
        if _enabled():
            try:
                enqueue_due()
            except client.Sub2ApiSyncError as exc:
                logger.warning("Sub2API 初始补传暂缓：阶段=%s 原因=%s；配置修正后自动恢复", exc.stage, exc.code)
            except Exception as exc:
                logger.warning(
                    "Sub2API 初始补传暂缓：原因=sub2api_sync_startup_failed 类型=%s；后台稍后继续", type(exc).__name__
                )
        return True


def status():
    counts = store.job_counts()
    return {"enabled": _enabled(), "started": _STARTED, "counts": counts, "total": sum(counts.values())}
