"""将本地有效 AT 同步到 C2A，支持手动导入和指定管理 ID 的修复。"""
from __future__ import annotations

import hashlib
import logging
import math
import time
import uuid
from typing import Any

from core import db
from core.accounts.plans.client import normalize_token, token_claims
from core.integrations.c2a import client
from core.operations import concurrency, task_gateway
from core.operations.runtime import OperationCancelled


logger = logging.getLogger(__name__)
TASK_TYPE = "c2a_session_reimport"
RESOURCE_FAMILY = "openai_interactive"
_MAX_REMOTE_ATTEMPTS = 3
_TRANSIENT_CODES = frozenset({
    "c2a_timeout",
    "c2a_connection_failed",
    "c2a_request_failed",
    "c2a_rate_limited",
    "c2a_server_error",
    "c2a_http_error",
})
_REJECTED_REMOTE_CODES = frozenset({
    "c2a_auth_rejected",
    "c2a_update_rejected",
    "c2a_remote_token_conflict",
    "c2a_create_rejected",
    "c2a_remote_account_missing",
})
_NOT_SUBMITTED_CODES = frozenset({
    "c2a_config_invalid",
    "c2a_backend_changed",
    "c2a_remote_account_id_invalid",
    "c2a_account_identity_invalid",
    "c2a_local_access_token_missing",
    "c2a_remote_policy_unverified",
    "c2a_remote_auto_removal_enabled",
})


class C2AReimportError(ValueError):
    """本地重导入前置条件错误；消息不包含凭据和远端正文。"""

    def __init__(self, code: str, message: str, *, stage: str = "preflight") -> None:
        self.code = str(code)
        self.stage = str(stage)
        super().__init__(message)


def register_actions() -> None:
    task_gateway.register_operation_actions(
        TASK_TYPE,
        retry_handler=task_gateway.default_operation_retry,
        cancel_handler=task_gateway.default_operation_cancel,
        terminate_handler=task_gateway.default_operation_terminate,
    )


def register_handler() -> None:
    """登记持久化处理器；多次调用保持幂等。"""
    concurrency.register_admission_alias(TASK_TYPE, "c2a_sync")
    task_gateway.register_operation_handler(TASK_TYPE, _handle, config_allowlist=())
    register_actions()


def _normalized_email(value: Any, *, code: str, message: str) -> str:
    email = str(value or "").strip().casefold()
    if not email or "@" not in email or any(char.isspace() for char in email):
        raise C2AReimportError(code, message)
    return email


def _account_reference(account: dict[str, Any]) -> tuple[int, str]:
    if db.account_is_deactivated(account):
        raise C2AReimportError("c2a_account_deactivated", "关联账号已确认停用，未向 C2A 更新 AT")
    try:
        account_id = int(account.get("id") or 0)
    except (TypeError, ValueError):
        account_id = 0
    if account_id <= 0:
        raise C2AReimportError("c2a_local_account_missing", "本地账号不存在，无法重新导入 C2A")
    email = _normalized_email(
        account.get("email"),
        code="c2a_local_account_identity_invalid",
        message="本地账号缺少有效邮箱，无法导入 C2A",
    )
    return account_id, email


def _queue(account_id: int, email: str, *, trigger: str, request_id: str, data: dict) -> dict[str, Any]:
    register_handler()
    result = task_gateway.submit_durable_operation(
        task_type=TASK_TYPE,
        account_id=account_id,
        email=email,
        trigger=trigger,
        source_id=request_id,
        idempotency_key=request_id,
        resource_family=RESOURCE_FAMILY,
        data=data,
    )
    return {**result, "status": str(result.get("status") or "queued")}


def queue_account(account: dict[str, Any]) -> dict[str, Any]:
    """仅入队账号引用，实际 AT 在 worker 获准时读取。"""
    account_id, email = _account_reference(account)
    return _queue(
        account_id, email,
        trigger="c2a_manual_reimport",
        request_id=f"c2a-reimport:{uuid.uuid4().hex}",
        data={"backend_identity": client.configured_backend_identity()},
    )


def queue_target(
    account: dict[str, Any],
    remote_id: str,
    *,
    expected_backend: str,
    idempotency_key: str,
    trigger: str = "c2a_monitor",
) -> dict[str, Any]:
    """入队原管理 ID 的 AT 修复，重放同一提交键会复用原任务。"""
    account_id, email = _account_reference(account)
    target_id = client.validate_remote_account_id(remote_id)
    backend = str(expected_backend or "").strip()
    if not backend:
        raise C2AReimportError("c2a_config_invalid", "定向修复缺少原 C2A 目标摘要")
    if client.configured_backend_identity() != backend:
        raise C2AReimportError("c2a_backend_changed", "C2A 目标已变化，未入队原目标修复")
    key = str(idempotency_key or "").strip()
    if not key:
        raise C2AReimportError("c2a_repair_request_invalid", "定向修复缺少稳定的提交标识")
    request_digest = hashlib.sha256(f"{backend}\n{target_id}\n{account_id}\n{key}".encode()).hexdigest()
    return _queue(
        account_id, email, trigger=trigger, request_id=f"c2a-repair:{request_digest}",
        data={"backend_identity": backend, "remote_account_id": target_id, "monitor_managed": True},
    )


def _read_current_account(context) -> tuple[str, dict[str, Any]]:
    """读取当前账号和 AT，并阻止队列等待期间发生的身份漂移。"""
    account = db.get_account(int(context.account_id or 0)) if context.account_id else None
    if account is None:
        raise C2AReimportError("c2a_local_account_missing", "本地账号已不存在，未向 C2A 更新 AT")
    if db.account_is_deactivated(account):
        raise C2AReimportError("c2a_account_deactivated", "关联账号已确认停用，未向 C2A 更新 AT")
    current_email = _normalized_email(
        account.get("email"),
        code="c2a_local_account_identity_invalid",
        message="本地账号缺少有效邮箱，未向 C2A 更新 AT",
    )
    expected_email = _normalized_email(
        context.email,
        code="c2a_local_account_identity_invalid",
        message="原任务缺少有效邮箱，未向 C2A 更新 AT",
    )
    if current_email != expected_email:
        raise C2AReimportError(
            "c2a_local_identity_changed",
            "本地账号邮箱已变化，未覆盖原 C2A 目标",
        )
    access_token = normalize_token(str(account.get("access_token") or ""))
    if not access_token:
        raise C2AReimportError("c2a_local_at_missing", "本地账号没有可重新导入的 AT")
    if len(access_token.split(".")) != 3 or any(not part for part in access_token.split(".")):
        raise C2AReimportError(
            "c2a_local_at_unverified", "本地 AT 的有效期或身份无法解析，请先刷新 AT"
        )
    try:
        claims = token_claims(access_token)
    except (AttributeError, TypeError, ValueError, OverflowError, OSError):
        raise C2AReimportError(
            "c2a_local_at_unverified", "本地 AT 的有效期或身份无法解析，请先刷新 AT"
        ) from None
    if claims.get("token_expired") is True:
        raise C2AReimportError("c2a_local_at_expired", "本地 AT 已过期，未向 C2A 覆盖旧 AT")
    token_email = str(claims.get("email") or "").strip().casefold()
    if token_email and token_email != current_email:
        raise C2AReimportError(
            "c2a_local_at_identity_mismatch",
            "本地 AT 身份与账号邮箱不一致，未向 C2A 更新 AT",
        )
    if isinstance(claims.get("exp"), bool) or claims.get("token_expired") is not False or not token_email:
        raise C2AReimportError(
            "c2a_local_at_unverified", "本地 AT 的有效期或身份无法解析，请先刷新 AT"
        )
    return access_token, claims


def _wait_before_retry(context, *, stage: str, attempt: int, code: str) -> None:
    context.report(
        stage=stage,
        message="C2A 请求暂未完成，正在进行受限重试",
        detail={"attempt": attempt, "next_attempt": attempt + 1, "error_code": code},
    )
    context.checkpoint()
    time.sleep(float(attempt))
    context.checkpoint()


def _find_unique_account(context, email: str, backend: str) -> tuple[dict[str, str] | None, int]:
    for attempt in range(1, _MAX_REMOTE_ATTEMPTS + 1):
        try:
            result = client.find_unique_account(
                email,
                expected_backend=backend,
                checkpoint=context.checkpoint,
            )
            return result, attempt
        except client.C2AError as exc:
            if exc.code == "c2a_account_missing":
                return None, attempt
            if exc.code not in _TRANSIENT_CODES or attempt == _MAX_REMOTE_ATTEMPTS:
                raise
            _wait_before_retry(context, stage="c2a_resolve", attempt=attempt, code=exc.code)
    raise AssertionError("C2A 账号定位重试循环未返回")


def _get_target_account(context, remote_id: str, access_token: str, backend: str) -> tuple[dict[str, Any], int]:
    for attempt in range(1, _MAX_REMOTE_ATTEMPTS + 1):
        try:
            result = client.get_account_sync_state(
                remote_id, context.email, access_token,
                expected_backend=backend, checkpoint=context.checkpoint,
            )
            return result, attempt
        except client.C2AError as exc:
            if exc.code not in _TRANSIENT_CODES or attempt == _MAX_REMOTE_ATTEMPTS:
                raise
            _wait_before_retry(context, stage="c2a_resolve", attempt=attempt, code=exc.code)
    raise AssertionError("C2A 原管理 ID 核验重试循环未返回")


def _remote_at_valid(remote_account: dict[str, Any]) -> bool:
    expires_at = remote_account.get("access_token_expires_at")
    return (
        remote_account.get("access_token_status") in {"valid", "expiring"}
        and type(expires_at) is int and expires_at > time.time()
        and remote_account.get("backend_status") != "异常"
        and remote_account.get("status_reason_code") not in {"auth_invalid", "credentials_unavailable"}
    )


def _remote_at_is_newer(remote_account: dict[str, Any], local_claims: dict[str, Any]) -> bool:
    remote_issued_at = remote_account.get("access_token_issued_at")
    local_issued_at = local_claims["payload"].get("iat")
    local_issued_at_is_number = type(local_issued_at) is int or (
        type(local_issued_at) is float and math.isfinite(local_issued_at)
    )
    if (
        type(remote_issued_at) is int and remote_issued_at > 0
        and local_issued_at_is_number and local_issued_at > 0
    ):
        return remote_issued_at > local_issued_at
    # C2A 的到期时间已经由 _remote_at_valid 确认。
    local_expires_at = local_claims.get("exp")
    return type(local_expires_at) in (int, float) and remote_account["access_token_expires_at"] > local_expires_at


def _confirm_target_state(
    context, remote_account: dict[str, Any], local_claims: dict[str, Any], resolve_attempts: int,
) -> task_gateway.OperationResult | None:
    token_matches = remote_account["token_matches"]
    if not _remote_at_valid(remote_account):
        if token_matches:
            raise C2AReimportError(
                "c2a_remote_at_invalid", "C2A 已保存相同 AT，但凭据仍失效，需要重新刷新 AT",
                stage="c2a_resolve",
            )
        return None
    if not token_matches and not _remote_at_is_newer(remote_account, local_claims):
        return None
    context.checkpoint()
    return task_gateway.OperationResult.success({
        "ok": True,
        "mode": "monitor_repair",
        "action": "already_synced" if token_matches else "remote_at_newer",
        "updated": False,
        "remote_already_synced": token_matches,
        "c2a_account_id": remote_account["id"],
        "backend_identity": remote_account["backend_identity"],
        "resolve_attempts": resolve_attempts,
        **({} if token_matches else {"reason_code": "c2a_remote_at_newer"}),
    }, message="C2A 原目标已保存相同的有效 AT" if token_matches else "C2A 原目标已保存更新的有效 AT")


def _verify_safe_mutation_policy(context, backend: str) -> tuple[client.SafeMutationPolicy, int]:
    """在任何远端写入意图前，确认 C2A 的自动删除策略已关闭。"""
    for attempt in range(1, _MAX_REMOTE_ATTEMPTS + 1):
        try:
            result = client.verify_safe_mutation_policy(
                expected_backend=backend,
                checkpoint=context.checkpoint,
            )
            return result, attempt
        except client.C2AError as exc:
            if exc.code not in _TRANSIENT_CODES or attempt == _MAX_REMOTE_ATTEMPTS:
                raise
            _wait_before_retry(context, stage="c2a_safety", attempt=attempt, code=exc.code)
    raise AssertionError("C2A 安全策略预检重试循环未返回")


def _update_access_token(
    context,
    remote_id: str,
    access_token: str,
    backend: str,
    safe_mutation_policy: client.SafeMutationPolicy,
) -> tuple[dict[str, Any], int]:
    # C2A 3.2.9 的通用更新接口没有幂等键或可查询的写入回执。POST 一旦因
    # 网络异常而失去响应，无法证明远端是否已写入；因此绝不能自动重发同一个
    # AT。用户仍可在任务中心确认后显式重跑，新的执行会重新完成全部前置校验。
    result = client.update_account_access_token(
        remote_id,
        access_token,
        expected_backend=backend,
        checkpoint=context.checkpoint,
        safe_mutation_policy=safe_mutation_policy,
    )
    return result, 1


def _record_known_non_write_receipt(context, code: str) -> None:
    """只有客户端已明确证明请求未提交或被远端拒绝时才收口。"""
    if code in _NOT_SUBMITTED_CODES:
        context.remote_request_receipt(
            outcome="not_submitted",
            receipt_state="not_submitted",
            detail={
                "error_code": code,
                "mutation_submitted": False,
                "action_dispatched": False,
            },
        )
    elif code in _REJECTED_REMOTE_CODES:
        context.remote_request_receipt(
            outcome="rejected",
            receipt_state="rejected",
            detail={"error_code": code},
        )


def _record_unknown_write_receipt(context, code: str) -> None:
    """保留可能已经到达 C2A 的单次写请求，交由用户核验后决定是否重跑。"""
    context.remote_request_receipt(
        outcome="unknown",
        receipt_state="unknown",
        detail={
            "error_code": code,
            "remote_result_confirmed": False,
            "manual_reconcile_required": True,
        },
    )


def _handle(context):
    """执行手动导入或对原管理 ID 的 AT 修复。"""
    data = context.run.get("data") or {}
    targeted = data.get("monitor_managed") is True or "remote_account_id" in data
    mode = "monitor_repair" if targeted else "manual_reimport"
    stage = "preflight"
    remote_started = False
    remote_completed = False
    remote_import_confirmed = False
    action = "update"
    with context.lease(resource_family=RESOURCE_FAMILY, scope_kind="final"):
        try:
            context.checkpoint()
            context.report(stage="preflight", state="running", message="正在校验本地账号与 C2A 配置")
            backend = str(data.get("backend_identity") or "")
            if not backend:
                raise C2AReimportError("c2a_config_invalid", "原任务缺少 C2A 目标摘要，未发起远端更新")
            if client.configured_backend_identity() != backend:
                raise C2AReimportError("c2a_backend_changed", "C2A 目标已变化，原任务未更新远端账号")
            access_token, _claims = _read_current_account(context)
            context.report(stage="preflight", state="success", message="C2A 预检通过")
            stage = "c2a_resolve"
            context.report(
                stage=stage,
                state="running",
                message="正在核对原 C2A 管理 ID 与账号 AT" if targeted else "正在按邮箱定位唯一 C2A 账号",
                detail={"mode": mode},
            )
            if targeted:
                target_id = client.validate_remote_account_id(data.get("remote_account_id"))
                remote_account, resolve_attempts = _get_target_account(context, target_id, access_token, backend)
                current_token, local_claims = _read_current_account(context)
                if current_token != access_token:
                    remote_account, extra_attempts = _get_target_account(context, target_id, current_token, backend)
                    resolve_attempts += extra_attempts
                access_token = current_token
                confirmed = _confirm_target_state(context, remote_account, local_claims, resolve_attempts)
                if confirmed is not None:
                    context.report(stage="c2a_resolve", state="success", message="C2A 原目标已保存有效 AT")
                    context.report(stage="c2a_safety", state="skipped", message="远端无需覆盖写入，跳过安全策略检查")
                    context.report(stage="c2a_update", state="skipped", message="远端无需覆盖写入，跳过 AT 更新")
                    return confirmed
            else:
                remote_account, resolve_attempts = _find_unique_account(context, context.email, backend)
                action = "update" if remote_account is not None else "create"
                # 重新读取当前 AT，避免查询期间身份变化或 AT 被替换。
                access_token, _claims = _read_current_account(context)
            context.report(stage="c2a_resolve", state="success", message="C2A 目标账号定位完成")
            # 尽量把兼容模式的 C2A 策略读取贴近写入边界。旧版 C2A 没有把
            # settings revision 与更新请求绑定的接口，仍需由部署侧保持策略稳定。
            stage = "c2a_safety"
            context.report(
                stage=stage,
                state="running",
                message="正在确认 C2A 自动清理策略已关闭",
                detail={"mode": mode, "resolve_attempts": resolve_attempts},
            )
            safe_mutation_policy, safety_attempts = _verify_safe_mutation_policy(context, backend)
            context.report(stage="c2a_safety", state="success", message="C2A 安全策略已确认")
            stage = "c2a_update"
            context.report(
                stage=stage,
                state="running",
                message="正在原位更新 C2A 账号 AT" if remote_account is not None else "正在新建 C2A 账号并导入 AT",
                detail={"mode": mode, "action": action, "resolve_attempts": resolve_attempts},
            )
            request_id = f"c2a-{action}:{context.run_id}"
            context.remote_request_started(
                "c2a_update_access_token" if remote_account is not None else "c2a_create_account",
                request_id=request_id,
                detail={
                    "backend_identity": backend, "action": action,
                    **({"remote_account_id": remote_account["id"]} if remote_account is not None else {}),
                },
            )
            remote_started = True
            if remote_account is not None:
                update_result, update_attempts = _update_access_token(
                    context, remote_account["id"], access_token, backend, safe_mutation_policy,
                )
                create_attempts = 0
            else:
                update_result = client.create_account_access_token(
                    context.email, access_token, expected_backend=backend,
                    checkpoint=context.checkpoint, safe_mutation_policy=safe_mutation_policy,
                )
                create_attempts = 1
                update_attempts = 0
                remote_import_confirmed = True
                if not update_result.get("created"):
                    # 导入可能仅命中历史 AT 指纹；保留这一步回执，再单独记录覆盖请求。
                    context.remote_request_receipt(
                        outcome="response_received", receipt_state="response_received", request_id=request_id,
                        detail={
                            "remote_account_id": update_result["id"],
                            "remote_result_confirmed": True, "phase_complete": True,
                        },
                    )
                    action = "update"
                    request_id = f"c2a-update:{context.run_id}"
                    context.remote_request_started(
                        "c2a_update_access_token", request_id=request_id,
                        detail={"backend_identity": backend, "remote_account_id": update_result["id"]},
                    )
                    update_result, update_attempts = _update_access_token(
                        context, update_result["id"], access_token, backend, safe_mutation_policy,
                    )
            remote_completed = True
            receipt = context.remote_request_receipt(
                outcome="confirmed",
                receipt_state="confirmed",
                request_id=request_id,
                detail={
                    "remote_account_id": update_result["id"],
                    "remote_result_confirmed": True,
                    # 本任务不修改账号数据；持久化并读回本次确认回执就是本地业务写回。
                    "local_business_writeback_confirmed": True,
                    "local_readback_confirmed": True,
                },
            )
            receipt_data = receipt.get("data") if isinstance(receipt, dict) else None
            receipt_data = receipt_data if isinstance(receipt_data, dict) else {}
            persisted = receipt_data.get("remote_receipt") if isinstance(receipt_data, dict) else None
            if not isinstance(persisted, dict) or str(persisted.get("receipt_state") or "") != "confirmed":
                raise C2AReimportError(
                    "c2a_local_receipt_writeback_failed",
                    "C2A 已确认导入，但本地回执读回未确认",
                    stage="local_writeback",
                )
            summary = {
                "ok": True,
                "mode": mode,
                "action": "create" if update_result.get("created") else "update",
                "created": bool(update_result.get("created")),
                "remote_import_confirmed": remote_import_confirmed,
                "updated": bool(update_result.get("updated")),
                "c2a_account_id": str(update_result["id"]),
                "backend_identity": backend,
                "safety_attempts": safety_attempts,
                "resolve_attempts": resolve_attempts,
                "update_attempts": update_attempts,
                "create_attempts": create_attempts,
            }
            message = "C2A 账号已新建并导入本地 AT" if summary["created"] else "C2A AT 已从本地重新导入"
            context.report(stage="c2a_update", state="success", message=message)
            return task_gateway.OperationResult.success(summary, message=message)
        except (OperationCancelled, task_gateway.OperationLeaseLost):
            raise
        except (C2AReimportError, client.C2AError) as exc:
            code = str(exc.code)
            error_stage = str(getattr(exc, "stage", stage) or stage)
            if error_stage == "update_account":
                action = "update"
            error_stage = {
                "find_account": "c2a_resolve", "get_account": "c2a_resolve",
                "get_account_access_token": "c2a_resolve",
                "update_account": "c2a_update", "create_account": "c2a_update",
            }.get(error_stage, error_stage)
            reported_stage = error_stage if error_stage in {"preflight", "c2a_resolve", "c2a_safety", "c2a_update"} else stage
            summary = {
                "ok": False,
                "mode": mode,
                "action": action,
                "remote_import_confirmed": remote_import_confirmed,
                "error_code": code,
                "stage": error_stage,
                "remote_update_started": remote_started,
                "remote_update_confirmed": remote_completed,
            }
            if remote_started:
                if not remote_completed and (code in _NOT_SUBMITTED_CODES or code in _REJECTED_REMOTE_CODES):
                    _record_known_non_write_receipt(context, code)
                    context.report(stage=reported_stage, state="failed", message=str(exc), detail={"error_code": code})
                    return task_gateway.OperationResult.failed(str(exc), summary)
                if not remote_completed:
                    _record_unknown_write_receipt(context, code)
                return task_gateway.OperationResult.request_unknown(str(exc), summary)
            context.report(stage=reported_stage, state="failed", message=str(exc), detail={"error_code": code})
            return task_gateway.OperationResult.failed(str(exc), summary)
        except Exception as exc:
            code = "c2a_manual_execution_failed"
            message = f"C2A 重新导入在 {stage} 阶段发生 {type(exc).__name__}，请查看服务日志"
            logger.exception("C2A 重新导入异常：阶段=%s 分类=%s", stage, code)
            summary = {
                "ok": False,
                "mode": mode,
                "action": action,
                "remote_import_confirmed": remote_import_confirmed,
                "error_code": code,
                "stage": stage,
                "remote_update_started": remote_started,
                "remote_update_confirmed": remote_completed,
            }
            if remote_started:
                return task_gateway.OperationResult.request_unknown(message, summary)
            context.report(stage=stage, state="failed", message=message, detail={"error_code": code})
            return task_gateway.OperationResult.failed(message, summary)
