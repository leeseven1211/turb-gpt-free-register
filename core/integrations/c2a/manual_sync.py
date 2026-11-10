"""把本地最新 AT 原位更新到既有 C2A 账号的持久化任务。"""
from __future__ import annotations

import logging
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
    "c2a_remote_account_missing",
})
_NOT_SUBMITTED_CODES = frozenset({
    "c2a_config_invalid",
    "c2a_backend_changed",
    "c2a_remote_account_id_invalid",
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


def register_handler() -> None:
    """登记持久化处理器；多次调用保持幂等。"""
    concurrency.register_admission_alias(TASK_TYPE, "c2a_sync")
    task_gateway.register_operation_handler(TASK_TYPE, _handle, config_allowlist=())


def _normalized_email(value: Any, *, code: str, message: str) -> str:
    email = str(value or "").strip().casefold()
    if not email or "@" not in email or any(char.isspace() for char in email):
        raise C2AReimportError(code, message)
    return email


def queue_account(account: dict[str, Any]) -> dict[str, Any]:
    """仅入队账号引用，实际 AT 在 worker 获准时读取。"""
    register_handler()
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
        message="本地账号缺少有效邮箱，无法匹配 C2A 既有账号",
    )
    backend = client.configured_backend_identity()
    request_id = f"c2a-reimport:{uuid.uuid4().hex}"
    result = task_gateway.submit_durable_operation(
        task_type=TASK_TYPE,
        account_id=account_id,
        email=email,
        trigger="c2a_manual_reimport",
        source_id=request_id,
        idempotency_key=request_id,
        resource_family=RESOURCE_FAMILY,
        data={"backend_identity": backend},
    )
    return {**result, "status": str(result.get("status") or "queued")}


def _read_current_account(context) -> tuple[dict[str, Any], str]:
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
    return account, access_token


def _wait_before_retry(context, *, stage: str, attempt: int, code: str) -> None:
    context.report(
        stage=stage,
        message="C2A 请求暂未完成，正在进行受限重试",
        detail={"attempt": attempt, "next_attempt": attempt + 1, "error_code": code},
    )
    context.checkpoint()
    time.sleep(float(attempt))
    context.checkpoint()


def _find_unique_account(context, email: str, backend: str) -> tuple[dict[str, str], int]:
    for attempt in range(1, _MAX_REMOTE_ATTEMPTS + 1):
        try:
            result = client.find_unique_account(
                email,
                expected_backend=backend,
                checkpoint=context.checkpoint,
            )
            return result, attempt
        except client.C2AError as exc:
            if exc.code not in _TRANSIENT_CODES or attempt == _MAX_REMOTE_ATTEMPTS:
                raise
            _wait_before_retry(context, stage="c2a_resolve", attempt=attempt, code=exc.code)
    raise AssertionError("C2A 账号定位重试循环未返回")


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
    """执行同邮箱定位与 AT 原位覆盖，不直接调用其他 C2A 属性接口。

    C2A 通用更新接口本身可能按自身规则清除凭据错误，因此 AT 更新确认后，
    远端异常状态可能恢复正常。
    """
    data = context.run.get("data") or {}
    stage = "preflight"
    remote_started = False
    remote_completed = False
    with context.lease(resource_family=RESOURCE_FAMILY):
        try:
            context.checkpoint()
            backend = str(data.get("backend_identity") or "")
            if not backend:
                raise C2AReimportError("c2a_config_invalid", "原任务缺少 C2A 目标摘要，未发起远端更新")
            if client.configured_backend_identity() != backend:
                raise C2AReimportError("c2a_backend_changed", "C2A 目标已变化，原任务未更新远端账号")
            _account, access_token = _read_current_account(context)
            stage = "c2a_resolve"
            context.report(
                stage=stage,
                message="正在按邮箱定位唯一 C2A 账号",
                detail={"mode": "manual_reimport"},
            )
            remote_account, resolve_attempts = _find_unique_account(context, context.email, backend)

            # 查询与写入之间再次读取，避免用队列期间已替换的身份或旧 AT 覆盖远端。
            _account, access_token = _read_current_account(context)
            # 尽量把兼容模式的 C2A 策略读取贴近写入边界。旧版 C2A 没有把
            # settings revision 与更新请求绑定的接口，仍需由部署侧保持策略稳定。
            stage = "c2a_safety"
            context.report(
                stage=stage,
                message="正在确认 C2A 自动清理策略已关闭",
                detail={"mode": "manual_reimport", "resolve_attempts": resolve_attempts},
            )
            safe_mutation_policy, safety_attempts = _verify_safe_mutation_policy(context, backend)
            stage = "c2a_update"
            context.report(
                stage=stage,
                message="正在原位更新 C2A 账号 AT",
                detail={"mode": "manual_reimport", "resolve_attempts": resolve_attempts},
            )
            request_id = f"c2a-update:{context.run_id}"
            context.remote_request_started(
                "c2a_update_access_token",
                request_id=request_id,
                detail={"backend_identity": backend, "remote_account_id": remote_account["id"]},
            )
            remote_started = True
            update_result, update_attempts = _update_access_token(
                context,
                remote_account["id"],
                access_token,
                backend,
                safe_mutation_policy,
            )
            remote_completed = True
            receipt = context.remote_request_receipt(
                outcome="confirmed",
                receipt_state="confirmed",
                request_id=request_id,
                detail={
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
                    "C2A 已确认更新，但本地回执读回未确认",
                    stage="local_writeback",
                )
            summary = {
                "ok": True,
                "mode": "manual_reimport",
                "updated": bool(update_result.get("updated")),
                "c2a_account_id": str(remote_account["id"]),
                "backend_identity": backend,
                "safety_attempts": safety_attempts,
                "resolve_attempts": resolve_attempts,
                "update_attempts": update_attempts,
            }
            return task_gateway.OperationResult.success(summary, message="C2A AT 已从本地重新导入")
        except (OperationCancelled, task_gateway.OperationLeaseLost):
            raise
        except (C2AReimportError, client.C2AError) as exc:
            code = str(exc.code)
            error_stage = str(getattr(exc, "stage", stage) or stage)
            error_stage = {"find_account": "c2a_resolve", "update_account": "c2a_update"}.get(error_stage, error_stage)
            summary = {
                "ok": False,
                "mode": "manual_reimport",
                "error_code": code,
                "stage": error_stage,
                "remote_update_started": remote_started,
                "remote_update_confirmed": remote_completed,
            }
            if remote_started:
                if not remote_completed and (code in _NOT_SUBMITTED_CODES or code in _REJECTED_REMOTE_CODES):
                    _record_known_non_write_receipt(context, code)
                    return task_gateway.OperationResult.failed(str(exc), summary)
                if not remote_completed:
                    _record_unknown_write_receipt(context, code)
                return task_gateway.OperationResult.request_unknown(str(exc), summary)
            return task_gateway.OperationResult.failed(str(exc), summary)
        except Exception as exc:
            code = "c2a_manual_execution_failed"
            message = f"C2A 重新导入在 {stage} 阶段发生 {type(exc).__name__}，请查看服务日志"
            logger.exception("C2A 重新导入异常：阶段=%s 分类=%s", stage, code)
            summary = {
                "ok": False,
                "mode": "manual_reimport",
                "error_code": code,
                "stage": stage,
                "remote_update_started": remote_started,
                "remote_update_confirmed": remote_completed,
            }
            if remote_started:
                return task_gateway.OperationResult.request_unknown(message, summary)
            return task_gateway.OperationResult.failed(message, summary)
