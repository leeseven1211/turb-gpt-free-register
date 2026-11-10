"""手动上传沿用原上传步骤，通过持久任务统一取得全局与同步类型许可。"""
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
import json
import logging
from typing import Any
import uuid

from core import db
from core.codex import token_refresh_service
from core.integrations.sub2api import client
from core.operations import concurrency, task_gateway
from core.operations.runtime import OperationCancelled
from core.storage import records
from core.storage import codex as credential_store
from core.storage.operations import store as operation
from core.storage.sub2api import credential_generation

logger = logging.getLogger(__name__)
TASK_TYPE = "sub2api_manual_upload"
RESOURCE_FAMILY = "openai_interactive"


class ManualUploadError(ValueError):
    """只携带明确分类的本地说明，不保存凭据或远端响应正文。"""

    def __init__(self, code: str, message: str, *, stage: str = "read_credential") -> None:
        self.code, self.stage = code, stage
        super().__init__(message)


def register_handler() -> None:
    concurrency.register_admission_alias(TASK_TYPE, "sub2api_sync")
    task_gateway.register_operation_handler(TASK_TYPE, _handle, config_allowlist=())


def _read(filename: str) -> tuple[dict, str, dict | None, dict | None]:
    try:
        row = credential_store.get_codex_account(filename)
    except ValueError as exc:
        raise ManualUploadError("sub2api_credential_invalid", "Codex 凭证文件名无效") from exc
    account = db.get_account_by_email(str((row or {}).get("email") or "")) if row else None
    if row and (str(row.get("oauth_account_status") or "").lower() == "deactivated" or db.account_is_deactivated(account)):
        raise ManualUploadError("sub2api_account_deactivated", "关联账号已停用，禁止上传 OAuth 凭证")
    if row and token_refresh_service.refresh_error_requires_reauth(row.get("oauth_refresh_error")):
        raise ManualUploadError("sub2api_credential_reauthorization_required", "当前 Codex 凭证需重新授权后才能上传")
    try:
        text, actual_filename = db.read_codex_credential(filename)
        auth = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ManualUploadError("sub2api_credential_invalid", "Codex 凭证不存在或 JSON 格式无效") from exc
    if not isinstance(auth, dict):
        raise ManualUploadError("sub2api_credential_invalid", "Codex 凭证必须是 JSON 对象")
    email = str(auth.get("email") or "").strip()
    linked = db.get_account_by_email(email) if email else account
    if db.account_is_deactivated(linked):
        raise ManualUploadError("sub2api_account_deactivated", "关联账号已停用，禁止上传 OAuth 凭证")
    return auth, actual_filename, linked, row


def queue_filename(filename: str) -> dict[str, Any]:
    """只保存原存储引用与目标摘要，上传在 worker 获准后执行。"""
    register_handler()
    auth, name, account, _row = _read(str(filename or "").strip())
    backend = client.configured_backend_identity()
    reference = records.get_row_by(records.CODEX_CREDENTIALS, "filename", name)
    if not reference:
        raise ManualUploadError("sub2api_credential_missing", "原 Codex 凭证已不存在，手动上传未入队")
    if not isinstance(reference.get("content"), dict) or credential_generation(reference["content"]) != credential_generation(auth):
        raise ManualUploadError("sub2api_credential_generation_changed", "本地凭证在提交时已更新，请重新上传")
    request_id = f"manual-upload:{uuid.uuid4().hex}"
    result = task_gateway.submit_durable_operation(
        task_type=TASK_TYPE,
        account_id=int(account["id"]) if account else None,
        email=str(auth.get("email") or ""),
        trigger="manual_upload",
        source_id=request_id,
        idempotency_key=request_id,
        resource_family=RESOURCE_FAMILY,
        data={"filename": name, "credential_id": int(reference["id"]),
              "credential_generation": credential_generation(auth), "backend_identity": backend},
    )
    return {**result, "filename": name, "status": str(result.get("status") or "queued")}


def queue_account(account: dict) -> dict[str, Any]:
    if db.account_is_deactivated(account):
        raise ManualUploadError("sub2api_account_deactivated", "关联账号已停用，禁止上传 OAuth 凭证")
    if str(account.get("codex_status") or "") != "success":
        raise ManualUploadError("sub2api_oauth_incomplete", "该账号尚未完成 Codex OAuth")
    email = str(account.get("email") or "").strip().casefold()
    row = credential_store.get_codex_account_by_email(email)
    if row is None:
        raise ManualUploadError("sub2api_credential_missing", "Codex 状态已通过，但本地未找到对应 OAuth JSON")
    return queue_filename(str(row.get("filename") or ""))


def _bound_reference(data: dict, *, expected_email: str, conn=None, for_update: bool = False) -> dict:
    credential_id = int(data.get("credential_id") or 0)
    reference = records.get_row(records.CODEX_CREDENTIALS, credential_id, conn=conn, for_update=for_update) if credential_id else None
    if reference is None:
        raise ManualUploadError("sub2api_credential_missing", "原 Codex 凭证已不存在，同名新凭证不会替代原上传目标")
    content = reference.get("content")
    if not isinstance(content, dict):
        raise ManualUploadError("sub2api_credential_invalid", "原 Codex 凭证内容无效")
    if credential_generation(content) != data.get("credential_generation"):
        raise ManualUploadError("sub2api_credential_generation_changed", "本地凭证代际已更新，原上传回执保留；请按新凭证重新上传")
    if str(content.get("email") or "").strip().casefold() != str(expected_email or "").strip().casefold():
        raise ManualUploadError("sub2api_credential_identity_mismatch", "原 Codex 凭证身份与上传目标不一致")
    if str(reference.get("oauth_account_status") or "").lower() == "deactivated":
        raise ManualUploadError("sub2api_account_deactivated", "关联凭证已确认停用，手动上传未执行")
    if token_refresh_service.refresh_error_requires_reauth(reference.get("oauth_refresh_error")):
        raise ManualUploadError("sub2api_credential_reauthorization_required", "当前 Codex 凭证需重新授权后才能上传")
    return reference


def _commit_upload(context, data: dict) -> str:
    """在短事务中锁定原 ID/代际，合并两个计数并读回，避免标记同名新凭证。"""
    fence = context.execution_fence if context.account_id else None
    with records.transaction() as conn, conn.cursor() as cur:
        if fence:
            operation.fence_execution(cur, **fence)
        else:
            operation._remote_checkpoint_fence(cur, context.run_id, execution_id=context.execution_id,
                                               lease_token=None, require_lease=False)
        reference = _bound_reference(data, expected_email=context.email, conn=conn, for_update=True)
        now = datetime.now().isoformat(timespec="seconds")
        changes = {"exported_count": int(reference.get("exported_count") or 0) + 1,
                   "sub2_uploaded_count": int(reference.get("sub2_uploaded_count") or 0) + 1,
                   "exported_at": now, "sub2_uploaded_at": now, "sub2_sync_error": None, "updated_at": now}
        if not records.patch_row(records.CODEX_CREDENTIALS, int(reference["id"]), changes, conn=conn):
            raise ManualUploadError("sub2api_manual_local_writeback_failed", "原凭证上传状态未写回", stage="local_writeback")
        confirmed = _bound_reference(data, expected_email=context.email, conn=conn)
        if any(confirmed.get(key) != value for key, value in changes.items()):
            raise ManualUploadError("sub2api_manual_local_writeback_failed", "原凭证上传状态读回未确认", stage="local_writeback")
        return str(confirmed["filename"])


def _handle(context):
    data = context.run.get("data") or {}
    scope = context.lease(resource_family=RESOURCE_FAMILY) if context.account_id else nullcontext()
    with scope:
        stage = "read_credential"
        remote_started = False
        remote_completed = False
        try:
            context.checkpoint()
            reference = _bound_reference(data, expected_email=context.email)
            auth, filename = reference["content"], str(reference["filename"])
            if client.configured_backend_identity() != data.get("backend_identity"):
                raise ManualUploadError("sub2api_backend_changed", "Sub2API 后端已变化，原上传目标保留；请恢复原后端或重新提交", stage="configuration")
            stage = "upload"
            context.report(stage=stage, message="开始手动上传 Codex OAuth 凭证", detail={"mode": "manual_upload"})
            context.remote_request_started("sub2api_manual_upload", detail={"backend_identity": data.get("backend_identity")})
            remote_started = True
            result = client.upload_configured_codex_oauth_credential(
                auth, checkpoint=context.checkpoint, expected_backend=str(data.get("backend_identity") or ""),
            )
            remote_completed = True
            context.remote_request_receipt(outcome="received", receipt_state="local_commit_required",
                                           detail={"remote_result_confirmed": True})
            stage = "local_writeback"
            context.checkpoint()
            filename = _commit_upload(context, data)
            context.remote_request_receipt(outcome="confirmed", receipt_state="confirmed", detail={
                "remote_result_confirmed": True, "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True,
            })
            summary = {"ok": True, "uploaded": True, "filename": filename, "mode": "manual_upload",
                       "status_code": result.get("status_code"), "sub2api_account_id": result.get("sub2api_account_id")}
            return task_gateway.OperationResult.success(summary, message="手动上传 Sub2API 已完成")
        except (OperationCancelled, task_gateway.OperationLeaseLost):
            raise
        except (ManualUploadError, client.Sub2ApiSyncError) as exc:
            code = exc.code
            summary = {"ok": False, "mode": "manual_upload", "error_code": code, "stage": stage if remote_completed else exc.stage,
                       "uploaded": remote_completed or bool(getattr(exc, "uploaded", False))}
            if remote_started:
                if not remote_completed and code in {"sub2api_auth_rejected", "sub2api_upload_rejected"}:
                    context.remote_request_receipt(outcome="rejected", receipt_state="rejected", detail={"error_code": code})
                else:
                    return task_gateway.OperationResult.request_unknown(str(exc), summary)
            return task_gateway.OperationResult.failed(str(exc), summary)
        except Exception as exc:
            code = "sub2api_manual_local_writeback_failed" if remote_completed else "sub2api_manual_execution_failed"
            message = f"手动上传在{stage}阶段发生 {type(exc).__name__}，请查看任务日志"
            logger.exception("手动上传异常：阶段=%s 分类=%s", stage, code)
            summary = {"ok": False, "mode": "manual_upload", "error_code": code, "stage": stage,
                       "uploaded": remote_completed}
            if remote_started:
                return task_gateway.OperationResult.request_unknown(message, summary)
            return task_gateway.OperationResult.failed(message, summary)
