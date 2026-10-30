"""确认 OAuth 成功后的 Sub2API 上传与启用，不改变授权结果。"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from core.integrations.sub2api import client as sub2api_client
from core.integrations.sub2api.client import Sub2ApiSyncError
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost
from core.storage import codex as codex_store

logger = logging.getLogger(__name__)


def sync_confirmed_credential(
    result: Mapping[str, Any],
    *,
    email: str,
    checkpoint: Callable[[], None],
    assert_lease: Callable[[], None],
) -> dict[str, Any]:
    """只读取本次 OAuth 返回的真实凭证，单独保存同步阶段与错误原因。"""
    filename = Path(str(result.get("file_path") or "")).name
    stage = "read_credential"
    uploaded = False
    enabled = False
    account_id = None
    try:
        checkpoint()
        if not filename:
            raise Sub2ApiSyncError(stage, "sub2api_credential_missing", "本次授权没有返回可上传的凭证名称")
        text, filename = codex_store.read_codex_credential(filename)
        credential = json.loads(text)
        if not isinstance(credential, dict) or str(credential.get("email") or "").strip().casefold() != email.strip().casefold():
            raise Sub2ApiSyncError(stage, "sub2api_credential_identity_mismatch", "本次凭证邮箱与授权账号不一致")
        stage = "upload"
        synced = sub2api_client.upload_and_enable_configured_codex_oauth_credential(credential, checkpoint=checkpoint)
        uploaded = bool(synced.get("uploaded"))
        enabled = bool(synced.get("enabled"))
        account_id = synced.get("sub2api_account_id")
        stage = "persist_metadata"
        assert_lease()
        codex_store.mark_codex_sub2_uploaded(filename)
        return {
            "status": "success", "uploaded": uploaded, "enabled": enabled,
            "sub2api_account_id": account_id,
        }
    except (OperationCancelled, OperationLeaseLost) as exc:
        uploaded = bool(getattr(exc, "sub2api_uploaded", uploaded))
        account_id = getattr(exc, "sub2api_account_id", account_id)
        lease_lost = isinstance(exc, OperationLeaseLost)
        summary = {
            "status": "failed" if lease_lost else "cancelled",
            "stage": getattr(exc, "sub2api_stage", stage),
            "error_code": "sub2api_sync_lease_lost" if lease_lost else "sub2api_sync_cancelled",
            "error": "账号租约丢失，已停止 sub2api 自动同步" if lease_lost else "已停止 sub2api 自动同步，Codex 授权凭证已保留",
            "uploaded": uploaded, "enabled": enabled,
            "sub2api_account_id": account_id,
        }
        if lease_lost:
            return summary
    except Sub2ApiSyncError as exc:
        uploaded = bool(exc.uploaded)
        account_id = exc.sub2api_account_id
        summary = {
            "status": "failed", "stage": exc.stage, "error_code": exc.code,
            "error": str(exc), "uploaded": uploaded, "enabled": enabled,
            "sub2api_account_id": account_id,
        }
    except Exception as exc:
        code = {
            "read_credential": "sub2api_credential_read_failed",
            "persist_metadata": "sub2api_sync_metadata_write_failed",
        }.get(stage, "sub2api_sync_execution_error")
        summary = {
            "status": "failed", "stage": stage, "error_code": code,
            "error": f"sub2api 自动同步在 {stage} 阶段发生 {type(exc).__name__}",
            "uploaded": uploaded, "enabled": enabled, "sub2api_account_id": account_id,
        }
    try:
        assert_lease()
        if uploaded and stage != "persist_metadata":
            codex_store.mark_codex_sub2_uploaded(filename)
        if filename:
            codex_store.mark_codex_sub2_sync_error(filename, f"{summary['error_code']}: {summary['error']}")
    except Exception:
        summary["metadata_error_code"] = "sub2api_sync_metadata_write_failed"
        logger.warning("sub2api 同步结果写回失败：阶段=%s 原因=%s", summary["stage"], summary["error_code"])
    return summary
