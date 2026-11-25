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


class ResolvedAccountsChanged(RuntimeError):
    """实际凭据账号不在调用方已锁集合；调用方必须退出整波事务后重新解析。"""

    def __init__(self, unlocked_account_ids):
        self.unlocked_account_ids = {int(value) for value in unlocked_account_ids}
        super().__init__("legacy_codex_refresh_accounts_changed")


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


def resolve_account_ids(conn, tasks: dict[int, dict]) -> set[int]:
    """只解析候选实际账号，不锁行；统一入口随后按全序锁完整账号集合。"""
    filenames = []
    for task in tasks.values():
        name = _filename(task)
        try:
            db_legacy._validate_codex_filename(name)
        except ValueError:
            continue
        filenames.append(name)
    names = list(dict.fromkeys(filenames))
    resolved = set()
    for offset in range(0, len(names), _CHUNK_SIZE):
        credentials = codex_storage.credentials(conn, filenames=names[offset:offset + _CHUNK_SIZE])
        emails = sorted({email for row in credentials
                         if (email := str(db_legacy._codex_public_row(row).get("email") or "").strip().lower())})
        resolved.update(int(row["id"]) for row in codex_storage.accounts(conn, emails=emails, for_update=False))
    return resolved


def _prepare_chunk(conn, tasks: dict[int, dict], accounts: dict[int, dict], snapshot,
                   locked_account_ids: set[int] | None) -> dict:
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
        return {"specs": {}, "replies": output, "resolved": {}, "deactivated": {}}
    credentials = {row["filename"]: row for row in codex_storage.credentials(
        conn, filenames=list(dict.fromkeys(valid.values())))}
    # 原入口按凭证邮箱定位本地账号；凭证的 provider account_id 不是本地账号 ID。
    credential_emails = sorted({email for row in credentials.values()
        if (email := str(db_legacy._codex_public_row(row).get("email") or "").strip().lower())})
    selected = codex_storage.accounts(conn, emails=credential_emails, for_update=locked_account_ids is None)
    if locked_account_ids is not None:
        unlocked = {int(row["id"]) for row in selected} - locked_account_ids
        if unlocked:
            raise ResolvedAccountsChanged(unlocked)
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
    specs, resolved, deactivated = {}, {}, {}
    captured = task_gateway.normalize_config_snapshot(snapshot, allowlist=refresh._CONFIG_ALLOWLIST)
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
            account = by_email.get(email.lower()) if email else None
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
            else:
                key = refresh._idempotency_key(name, public, trigger=_TRIGGER, explicit=None,
                    reconcile=False, manual_retry_unknown=True)
                resolved[task_id] = {"filename": name, "email": email, "account_id": account_id,
                    "config_snapshot_revision": captured.get("config_snapshot_revision")}
                specs[task_id] = {"task_type": refresh.TASK_TYPE, "account_id": account_id, "email": email,
                    "trigger": _TRIGGER, "source_system": "native_operations", "source_id": key,
                    "idempotency_key": key, "resource_family": refresh.RESOURCE_FAMILY,
                    "data": {"credential_filename": name, "resource_family": refresh.RESOURCE_FAMILY,
                             "manual_retry_unknown": True},
                    "config_snapshot": snapshot, "config_allowlist": refresh._CONFIG_ALLOWLIST}
    return {"specs": specs, "replies": output, "resolved": resolved, "deactivated": deactivated}


def prepare_legacy(conn, tasks: dict[int, dict], accounts: dict[int, dict], snapshot=None,
                   *, locked_account_ids: set[int] | None = None) -> dict:
    """同连接预检，不创建或去重候选；调用方按原选择顺序统一仲裁资源族。"""
    prepared = {"specs": {}, "replies": {}, "resolved": {}}
    if not tasks:
        return prepared
    if snapshot is None:
        snapshot = refresh._snapshot_for_submission()
    if locked_account_ids is not None:
        locked_account_ids = {int(value) for value in locked_account_ids}
    rows, deactivated = list(tasks.items()), {}
    for offset in range(0, len(rows), _CHUNK_SIZE):
        chunk = _prepare_chunk(conn, dict(rows[offset:offset + _CHUNK_SIZE]), accounts, snapshot,
                               locked_account_ids)
        for key in prepared:
            prepared[key].update(chunk[key])
        deactivated.update(chunk["deactivated"])
    # 旧人工入口的停用凭据同步是尽力写回；全部实际账号完成锁归属校验后再集合写回。
    marked = list(deactivated.items())
    for offset in range(0, len(marked), _CHUNK_SIZE):
        try:
            with conn.transaction():
                _mark_deactivated(conn, dict(marked[offset:offset + _CHUNK_SIZE]))
        except Exception:
            logger.exception("批量同步停用账号到 Codex OAuth 凭据失败")
    return prepared


def project_prepared(conn, selected_specs: list[dict], created: list[dict]) -> None:
    """只投影本叶已受理的新 Run，与调用方的集合落库共用事务。"""
    rows = [{**receipt, "account_id": spec["account_id"]}
            for spec, receipt in zip(selected_specs, created, strict=True)
            if receipt.get("accepted") and not receipt.get("busy")]
    for offset in range(0, len(rows), _CHUNK_SIZE):
        _project_queued(conn, rows[offset:offset + _CHUNK_SIZE])


def format_prepared(prepared: dict, created_by_task: dict[int, dict]) -> dict[int, tuple[dict, int]]:
    """补齐原 refresh 回执；busy 可引用其他领域在本波新建的赢家 Run。"""
    output = dict(prepared["replies"])
    for task_id, result in created_by_task.items():
        metadata = prepared["resolved"][task_id]
        if result.get("busy"):
            payload = _busy(metadata["filename"], metadata["email"], {
                "task_id": result.get("task_id"), "id": result.get("run_id"), "status": result.get("status")})
        else:
            payload = {**result, **metadata}
        output[task_id] = _reply(payload)
    return output


def _submit_chunk(conn, tasks: dict[int, dict], accounts: dict[int, dict], snapshot) -> tuple[dict, bool]:
    prepared = prepare_legacy(conn, tasks, accounts, snapshot)
    selected, pending, duplicates = {}, {}, {}
    for task_id, spec in prepared["specs"].items():
        family = (spec["account_id"], spec["resource_family"])
        if family in pending:
            duplicates[task_id] = pending[family]
        else:
            pending[family] = task_id
            selected[task_id] = spec
    created = create_specs(list(selected.values()), conn=conn)
    project_prepared(conn, list(selected.values()), created)
    created_by_task = dict(zip(selected, created, strict=True))
    for task_id, winner in duplicates.items():
        created_by_task[task_id] = {**created_by_task[winner], "accepted": False, "busy": True}
    output = format_prepared(prepared, created_by_task)
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
