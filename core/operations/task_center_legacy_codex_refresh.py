"""历史 Codex Token 刷新任务的显式人工重试，集合受理到原 Worker 队列。"""
from __future__ import annotations

import json
import logging

from core import db
from core.codex import token_refresh_service as refresh
from core.operations import task_gateway
from core.storage import db_legacy, records
from core.storage.codex import bulk_submission as codex_storage
from core.storage.operations import schema
from core.storage.operations.bulk_submission import create_specs

_TRIGGER = "manual_task_center_retry"
_CHUNK_SIZE = 500
_ACTIVE = ("queued", "running", "cancelling", "settling", "stopping")
logger = logging.getLogger(__name__)


def _reply(payload: dict) -> tuple[dict, int]:
    return {"ok": bool(payload.get("accepted")) and not payload.get("busy"), **payload}, (
        409 if payload.get("busy") else 202 if payload.get("accepted") else 400)


def _filename(task: dict) -> str:
    summary = task.get("result_summary") if isinstance(task.get("result_summary"), dict) else {}
    data = task.get("data") if isinstance(task.get("data"), dict) else {}
    return str(summary.get("filename") or data.get("credential_filename") or "").strip()


def _busy(filename: str, email: str, active: dict) -> dict:
    return {"accepted": False, "busy": True,
        "error": "该凭证已有排队或运行中的 durable refresh 任务",
        "task_id": int(active.get("task_id") or 0) or None,
        "run_id": int(active.get("id") or 0) or None, "status": str(active.get("status") or ""),
        "filename": filename, "email": email}


def _mark_deactivated(conn, accounts: dict[int, dict]) -> None:
    if not accounts:
        return
    now = refresh._iso_utc(refresh._utc_now())
    rows = [{"email": str(row.get("email") or "").strip().lower(),
             "reason": str(row.get("account_status_reason") or "account_deactivated").strip()[:500]}
            for row in accounts.values() if str(row.get("email") or "").strip()]
    with conn.cursor() as cur:
        cur.execute(f"""UPDATE {records._qualified(records.CODEX_CREDENTIALS)} credential
            SET oauth_status='deactivated',oauth_account_status='deactivated',
                oauth_account_status_reason=s.reason,oauth_account_status_at=%s,
                oauth_reauth_required=true,data=credential.data ||
                    jsonb_build_object('oauth_refresh_error',s.reason),updated_at=%s
            FROM jsonb_to_recordset(%s::jsonb) s(email TEXT,reason TEXT)
            WHERE lower(btrim(credential.email))=s.email""", (now, now, json.dumps(rows)))


def _project_queued(conn, rows: list[dict]) -> None:
    values = [{"account_id": row["account_id"], "run_id": row["run_id"]}
              for row in rows if not row.get("reused")]
    if not values:
        return
    with conn.cursor() as cur:
        cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)} account
            SET codex_execution_status='queued',codex_active_run_id=s.run_id,
                codex_status=CASE lower(COALESCE(account.codex_credential_state,''))
                    WHEN 'valid' THEN 'success' WHEN 'pending_confirmation' THEN 'pending_confirmation'
                    WHEN 'deactivated' THEN 'deactivated'
                    ELSE CASE WHEN lower(COALESCE(account.codex_status,''))='success'
                        THEN account.codex_status ELSE 'retrying' END END,
                updated_at=%s
            FROM jsonb_to_recordset(%s::jsonb) s(account_id BIGINT,run_id BIGINT)
            WHERE account.id=s.account_id""", (records._now(), json.dumps(values)))


def _submit_chunk(conn, tasks: dict[int, dict], accounts: dict[int, dict], snapshot) -> tuple[dict, bool]:
    output, valid = {}, {}
    for task_id, task in tasks.items():
        account = accounts.get(int(task.get("account_id") or 0))
        if not account:
            output[task_id] = ({"ok": False, "error": "关联账号不存在"}, 404)
        elif db.account_is_deactivated(account):
            output[task_id] = ({"ok": False, "deactivated": True, "error": "账号已废号，不能重跑"}, 409)
        else:
            name = _filename(task)
            try:
                db_legacy._validate_codex_filename(name)
            except ValueError:
                output[task_id] = _reply({"accepted": False, "error": "Codex 凭证不存在", "filename": name})
            else:
                valid[task_id] = name
    if not valid:
        return output, False
    credentials = {row["filename"]: row for row in codex_storage.credentials(
        conn, filenames=list(dict.fromkeys(valid.values())))}
    # 原入口按凭证邮箱定位本地账号；凭证的 provider account_id 不是本地账号 ID。
    credential_emails = sorted({str(db_legacy._codex_public_row(row).get("email") or "").strip().lower()
                               for row in credentials.values()})
    selected = codex_storage.accounts(conn, emails=credential_emails)
    by_email = {str(row.get("email") or "").strip().lower(): row for row in selected}
    active = {}
    if selected:
        with conn.cursor() as cur:
            from core.storage.operations import common
            cur.execute(f"""SELECT id,task_id,account_id,status FROM {common._table('operation_runs')}
                WHERE account_id=ANY(%s) AND resource_family=%s AND status=ANY(%s) ORDER BY id DESC""",
                ([int(row["id"]) for row in selected], refresh.RESOURCE_FAMILY, list(_ACTIVE)))
            for row in cur.fetchall():
                active.setdefault(int(row["account_id"]), dict(row))
    specs, submitted, pending, deactivated = [], [], {}, {}
    for task_id, name in valid.items():
        row = credentials.get(name)
        if row is None:
            output[task_id] = _reply({"accepted": False, "error": "Codex 凭证不存在", "filename": name})
            continue
        public = db_legacy._codex_public_row(row)
        decorated = refresh.decorate_row(public)
        base = {"accepted": False, "filename": name}
        if str(decorated.get("oauth_account_status") or "").strip().lower() == "deactivated":
            output[task_id] = _reply({**base, "error_code": "account_deactivated", "next_action": "reauthorize",
                "error": "账号已停用，禁止刷新 Codex OAuth；需先恢复账号后重新授权"})
        elif not decorated.get("oauth_refreshable"):
            output[task_id] = _reply({**base, "error_code": refresh.REAUTH_REQUIRED,
                "error": "凭证缺少 refresh_token，只能重跑 OAuth 授权"})
        elif decorated.get("oauth_reauth_required"):
            output[task_id] = _reply({**base, "error_code": refresh.REAUTH_REQUIRED, "next_action": "reauthorize",
                "error": "当前凭证需要重新 OAuth 授权"})
        else:
            email = str(public.get("email") or decorated.get("email") or "").strip()
            account = by_email.get(email.lower())
            account_id = int((account or {}).get("id") or 0)
            base["email"] = email
            if not account_id:
                output[task_id] = _reply({**base, "error_code": "account_reference_missing",
                    "error": "Codex 凭证没有对应的 registered account，不能申请 durable lease"})
            elif db.account_is_deactivated(account):
                deactivated[account_id] = account
                output[task_id] = _reply({**base, "error_code": "account_deactivated", "next_action": "reauthorize",
                    "error": "账号已停用，禁止刷新 Codex OAuth；需先恢复账号后重新授权"})
            elif account_id in active:
                output[task_id] = _reply(_busy(name, email, active[account_id]))
            elif account_id in pending:
                # 同一波按原输入顺序只提交首次，其后回执指向本次新 Run。
                submitted.append((task_id, name, email, pending[account_id], False))
            else:
                key = refresh._idempotency_key(name, public, trigger=_TRIGGER, explicit=None,
                    reconcile=False, manual_retry_unknown=True)
                pending[account_id] = len(specs)
                submitted.append((task_id, name, email, len(specs), True))
                specs.append({"task_type": refresh.TASK_TYPE, "account_id": account_id, "email": email,
                    "trigger": _TRIGGER, "source_system": "native_operations", "source_id": key,
                    "idempotency_key": key, "resource_family": refresh.RESOURCE_FAMILY,
                    "data": {"credential_filename": name, "resource_family": refresh.RESOURCE_FAMILY,
                             "manual_retry_unknown": True},
                    "config_snapshot": snapshot, "config_allowlist": refresh._CONFIG_ALLOWLIST})
    if deactivated:
        # 旧人工入口的停用凭据同步是尽力写回；一次集合保存点保持相同失败边界。
        try:
            with conn.transaction():
                _mark_deactivated(conn, deactivated)
        except Exception:
            logger.exception("批量同步停用账号到 Codex OAuth 凭据失败")
    created = create_specs(specs, conn=conn)
    _project_queued(conn, created)
    for task_id, name, email, index, first in submitted:
        result = created[index]
        if first:
            payload = {**result, "filename": name, "email": email}
            captured = task_gateway.normalize_config_snapshot(snapshot, allowlist=refresh._CONFIG_ALLOWLIST)
            payload["config_snapshot_revision"] = captured.get("config_snapshot_revision")
        else:
            payload = _busy(name, email, {"task_id": result["task_id"], "id": result["run_id"],
                                         "status": result["status"]})
        output[task_id] = _reply(payload)
    return output, any(not row.get("reused") for row in created)


def submit_legacy(tasks: dict[int, dict], accounts: dict[int, dict]) -> dict[int, tuple[dict, int]]:
    """保持旧任务人工重试未知结果的许可；外部 grant 仍由已装配的 Worker 执行。"""
    if not tasks:
        return {}
    records.init()
    schema.init_operation_schema()
    output, created = {}, False
    try:
        snapshot = refresh._snapshot_for_submission()
        rows = list(tasks.items())
        with records.transaction() as conn:
            for offset in range(0, len(rows), _CHUNK_SIZE):
                chunk, fresh = _submit_chunk(conn, dict(rows[offset:offset + _CHUNK_SIZE]), accounts, snapshot)
                output.update(chunk)
                created = created or fresh
    except Exception as exc:
        # 整波本地事实回滚；保留原人工入口的安全错误正文及提交失败分类。
        return {task_id: _reply({"accepted": False, "error_code": "durable_submit_failed",
            "error": f"刷新任务创建失败: {refresh._safe_error(exc)}", "filename": _filename(task),
            "email": str((accounts.get(int(task.get("account_id") or 0)) or {}).get("email") or "")})
            for task_id, task in tasks.items()}
    if created:
        task_gateway.notify_dispatch()
    return output
