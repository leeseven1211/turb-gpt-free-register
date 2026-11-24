"""Codex 执行类批量受理；集合预取与入队，不执行 OAuth 或第三方上传。"""
from __future__ import annotations

from core import db
from core.operations import task_gateway
from core.storage import records
from core.storage.codex import bulk_submission as storage
from core.storage.operations import schema

_REAUTH_CONFIG_FIELDS = (
    "oauth_driver", "auth_source", "phone_enabled", "sms_provider", "sms_country",
    "account_proxy_mode", "account_proxy_modes", "auto_upload_sub2api",
)
_REFRESH_CONFIG_FIELDS = ("request_timeout",)


def _names(values):
    return list(dict.fromkeys(str(value or "").strip() for value in values if isinstance(value, str)))


def _ids(values):
    output, invalid = [], []
    for value in values:
        try:
            if type(value) is not int and not (
                isinstance(value, str) and value.strip().isascii() and value.strip().isdigit()
            ):
                raise ValueError()
            number = int(value)
            if not 0 < number <= 2**63 - 1:
                raise ValueError()
        except (ValueError, TypeError):
            invalid.append({"id": value, "reason": "ID 非法", "reason_code": "invalid_id"})
            continue
        if number not in output:
            output.append(number)
    return output, invalid


def _filename_valid(name):
    return name.startswith("codex-") and name.endswith(".json") and not any(part in name for part in ("/", "\\", ".."))


def _credential_email(row, *, content_first=False):
    row = row or {}
    content = row.get("content") if isinstance(row.get("content"), dict) else {}
    value = content.get("email") if content_first else row.get("email")
    return str(value or row.get("email") or content.get("email") or "").strip()


def _submit(kind, *, account_ids=(), filenames=(), trigger="manual_bulk", title="Codex 批量任务"):
    from core.codex import operation_service as oauth, token_refresh_service as refresh
    from core.integrations.sub2api import client, manual_upload
    from core.storage.sub2api import credential_generation

    ids, skipped = _ids(account_ids)
    names = _names(filenames)
    for name in names:
        if not _filename_valid(name):
            skipped.append({"filename": name, "reason": "文件名非法", "reason_code": "invalid_filename"})
    valid_names = [name for name in names if _filename_valid(name)]
    if kind == "codex_retry":
        snapshot = oauth._config_snapshot()
        unavailable = oauth._deployment_unavailable(snapshot)
        if unavailable:
            return unavailable
        enabled, reason = oauth._feature_ready(snapshot)
        if not enabled:
            return {"accepted": False, "feature": "codex_retry", "error": reason, "unavailable": True}
    elif kind == "codex_token_refresh":
        snapshot = task_gateway.normalize_config_snapshot(refresh._snapshot_for_submission(),
                                                          allowlist=refresh._CONFIG_ALLOWLIST)
    else:
        snapshot = None
        backend = client.configured_backend_identity()
    records.init()
    schema.init_operation_schema()
    with records.transaction() as conn:
        initial = storage.credentials(conn, filenames=valid_names) if valid_names else []
        selected_accounts = storage.accounts(
            conn, account_ids=ids,
            emails=list({
                email.casefold() for row in initial
                for email in (_credential_email(row), _credential_email(row, content_first=True))
                if email
            }),
            for_update=False,
        )
        by_id = {row["id"]: row for row in selected_accounts}
        by_email = {str(row.get("email") or "").strip().casefold(): row for row in selected_accounts}
        # 凭证只在内存用于预检；最终 worker 仍按原 ID/代际重新校验。
        credential_rows = storage.credentials(
            conn, filenames=valid_names,
            emails=[str(by_id[number].get("email") or "").strip().casefold() for number in ids if number in by_id],
        )
        selected_accounts = storage.accounts(
            conn, account_ids=ids,
            emails=list({
                email.casefold() for row in credential_rows
                for email in (_credential_email(row), _credential_email(row, content_first=True))
                if email
            }),
        )
        by_id = {row["id"]: row for row in selected_accounts}
        by_email = {str(row.get("email") or "").strip().casefold(): row for row in selected_accounts}
        by_filename = {row["filename"]: row for row in credential_rows}
        credential_by_email = {}
        for row in credential_rows:
            credential_by_email.setdefault(str(row.get("email") or "").strip().casefold(), row)
        active = storage.active_runs(conn, by_id)
        fences = storage.refresh_fences(conn, by_id) if kind == "codex_token_refresh" else set()
        targets = []
        for number in ids:
            account = by_id.get(number)
            credential = credential_by_email.get(str((account or {}).get("email") or "").strip().casefold())
            if kind == "sub2api_manual_upload" and credential:
                account = by_email.get(_credential_email(credential, content_first=True).casefold())
            targets.append(({"id": number}, account, credential))
        for name in valid_names:
            credential = by_filename.get(name)
            account = by_email.get(_credential_email(
                credential, content_first=kind == "sub2api_manual_upload",
            ).casefold())
            targets.append(({"filename": name}, account, credential))
        specs, seen_accounts, selected = [], set(), []
        for identity, account, credential in targets:
            email = str((account or {}).get("email") or _credential_email(
                credential, content_first=kind == "sub2api_manual_upload",
            )).strip()
            base = {**identity, **({"email": email} if email else {})}
            account_id = (account or {}).get("id")
            code = reason = None
            if identity.get("filename") and credential is None:
                code, reason = "credential_missing", "Codex 凭证不存在"
            elif account is None and (kind != "sub2api_manual_upload" or "id" in identity):
                code, reason = "account_missing", "未找到对应的已注册账号"
            elif account and db.account_is_deactivated(account):
                code, reason = "account_deactivated", "账号已停用"
            elif kind == "sub2api_manual_upload" and credential and db.account_is_deactivated(
                by_email.get(_credential_email(credential).casefold())
            ):
                code, reason = "account_deactivated", "关联账号已停用"
            elif kind == "codex_retry" and account_id in seen_accounts:
                continue
            elif kind == "codex_token_refresh" and (
                account_id in fences or refresh._has_reconciliation_marker((credential or {}).get("oauth_refresh_error"))
            ):
                code, reason = "refresh_reconciliation_required", "上一次 refresh grant 结果待核验，禁止再次发送"
            elif account_id and (account_id in active or account_id in seen_accounts):
                code, reason = "account_busy", "该账号已有排队或运行中的账号操作"
            elif kind != "codex_retry" and not credential:
                code, reason = "credential_missing", "本地未找到对应 OAuth JSON"
            elif kind == "sub2api_manual_upload" and "id" in identity and account.get("codex_status") != "success":
                code, reason = "sub2api_oauth_incomplete", "尚未完成 Codex OAuth"
            elif kind != "codex_retry":
                auth = credential.get("content")
                if not isinstance(auth, dict):
                    code, reason = "credential_invalid", "Codex 凭证内容无效"
                elif str(credential.get("oauth_account_status") or "").lower() == "deactivated":
                    code, reason = "account_deactivated", "关联凭证已停用"
                elif refresh.refresh_error_requires_reauth(credential.get("oauth_refresh_error")):
                    code, reason = "reauthorization_required", "当前凭证需重新授权"
                elif kind == "codex_token_refresh" and (
                    not refresh.oauth_metadata(auth).get("oauth_refreshable")
                    or refresh.sub2api_status_requires_reauth(credential.get("sub2api_http_status"))
                ):
                    code, reason = "reauthorization_required", "当前凭证需要重新 OAuth 授权"
            if code:
                item = {**base, "reason": reason, "reason_code": code}
                if code == "account_busy" and account_id in active:
                    item.update(task_id=active[account_id]["task_id"], run_id=active[account_id]["id"])
                skipped.append(item)
                continue
            if account_id:
                seen_accounts.add(account_id)
            data = {}
            source_id = None
            if kind == "codex_token_refresh":
                data.update(credential_filename=credential["filename"], resource_family=refresh.RESOURCE_FAMILY)
                source_id = refresh._idempotency_key(credential["filename"], credential, trigger=trigger,
                                                      explicit=None, reconcile=False)
            elif kind == "sub2api_manual_upload":
                data.update(filename=credential["filename"], credential_id=credential["id"],
                            credential_generation=credential_generation(credential["content"]), backend_identity=backend)
            if credential:
                base["filename"] = credential["filename"]
            selected.append(base)
            specs.append({
                "task_type": kind, "account_id": account_id, "email": email,
                "trigger": trigger, "data": data, **({"source_id": source_id} if source_id else {}),
                **({"config_snapshot": snapshot,
                    "config_allowlist": _REFRESH_CONFIG_FIELDS if kind == "codex_token_refresh" else _REAUTH_CONFIG_FIELDS}
                   if snapshot is not None else {}),
            })
        previous = storage.existing_refresh_tasks(
            conn, [spec["source_id"] for spec in specs],
        ) if kind == "codex_token_refresh" else {}
        for spec in specs:
            prior = previous.get(spec.get("source_id"))
            if prior:
                # 同一凭证代际的刷新重发沿用原任务快照；配置变化不会创建第二次 grant。
                spec["config_snapshot"] = (prior.get("data") or {}).get("config_snapshot") or {}
        prior_batches = {row["batch_id"] for row in previous.values() if row.get("batch_id")}
        reused_only = bool(specs) and len(previous) == len(specs) and len(prior_batches) == 1
        if reused_only:
            first = next(iter(previous.values()))
            batch = {"id": first["batch_id"], "batch_uuid": first.get("batch_uuid")}
            created = [{**previous[spec["source_id"]], "accepted": True, "reused": True}
                       for spec in specs]
        else:
            batch = storage.create_batch(conn, kind, len(targets) + len(skipped), trigger, title)
            created = storage.create_tasks(conn, specs, batch["id"])
        if kind != "sub2api_manual_upload":
            storage.project_queued(conn, created)
        if not reused_only:
            storage.finish_batch(conn, batch["id"], skipped, bool(created))
        accepted = [{**identity, "accepted": True, "busy": False, "task_id": row["task_id"],
                     "run_id": row["run_id"], "account_id": row["account_id"], "email": row["email"],
                     "status": row["status"], "reused": row["reused"], "trigger": trigger}
                    for identity, row in zip(selected, created, strict=True)]
    if any(not item["reused"] for item in created):
        task_gateway.notify_dispatch()
    if kind == "sub2api_manual_upload":
        return {"ok": True, "accepted": True, "status": "queued", "queued": accepted,
                "queued_count": len(accepted), "uploaded": [], "uploaded_count": 0,
                "failed": [], "failed_count": 0, "skipped": skipped, "skipped_count": len(skipped),
                "batch_id": batch["id"]}
    return {"accepted": bool(accepted), "batch_id": batch["id"], "batch_uuid": batch["batch_uuid"],
            "started": accepted, "started_count": len(accepted), "skipped": skipped,
            **({"workers": oauth.configured_workers()} if kind == "codex_retry" else {})}


def submit_refresh(filenames, *, trigger="manual_bulk"):
    return _submit("codex_token_refresh", filenames=filenames, trigger=trigger, title="批量刷新 Codex OAuth Token")


def submit_reauthorization(*, account_ids=(), filenames=(), trigger="manual_bulk", title="批量补跑 Codex OAuth"):
    return _submit("codex_retry", account_ids=account_ids, filenames=filenames, trigger=trigger, title=title)


def submit_upload(*, account_ids=(), filenames=(), trigger="manual_upload"):
    return _submit("sub2api_manual_upload", account_ids=account_ids, filenames=filenames,
                   trigger=trigger, title="批量上传 Sub2API")


def cancel_reauthorization(*, account_ids=(), emails=()):
    """一次集合预取账号与活动 Run，再按精确 Run 发出取消信号。"""
    from core.storage.operations import runtime as operation_runtime
    ids, skipped = _ids(account_ids)
    normalized_emails = list(dict.fromkeys(
        str(value or "").strip() for value in emails if isinstance(value, str) and str(value or "").strip()
    ))
    records.init()
    with records.transaction() as conn:
        rows = storage.accounts(conn, account_ids=ids, emails=[value.casefold() for value in normalized_emails],
                                for_update=False)
        by_id = {int(row["id"]): row for row in rows}
        by_email = {str(row.get("email") or "").strip().casefold(): row for row in rows}
        active = storage.reauthorization_runs(conn, by_id)
        targets = [(("id", number), by_id.get(number)) for number in ids]
        targets.extend((("email", email), by_email.get(email.casefold())) for email in normalized_emails)
        targets.sort(key=lambda entry: (
            (active.get(int(entry[1]["id"])) or {}).get("id", 2**63) if entry[1] else 2**63,
            int(entry[1]["id"]) if entry[1] else 2**63,
        ))
        stopped = []
        seen = set()
        for (kind, value), account in targets:
            key = int(account["id"]) if account else f"{kind}:{value}"
            if key in seen:
                continue
            seen.add(key)
            shown_email = str((account or {}).get("email") or (value if kind == "email" else "")).strip()
            if account is None:
                skipped.append({kind: value, "reason": "账号不存在", "reason_code": "account_missing"})
                continue
            run = active.get(int(account["id"]))
            if not run:
                skipped.append({"id": int(account["id"]), "email": shown_email,
                                "reason": "未处于补跑中", "reason_code": "run_not_active"})
                continue
            try:
                result = operation_runtime.request_run_cancel(
                    int(run["id"]), reason="用户手动停止 Codex 补跑",
                    expected_status=run["status"], conn=conn,
                )
            except LookupError:
                skipped.append({"id": int(account["id"]), "email": shown_email,
                                "reason": "执行实例不存在", "reason_code": "run_missing"})
                continue
            if result.get("cancel_skipped"):
                skipped.append({"id": int(account["id"]), "email": shown_email,
                                "reason": result.get("message") or "任务状态已变化",
                                "reason_code": "run_state_changed"})
                continue
            cancelled = result.get("status") == "cancelled"
            stopped.append({"id": int(account["id"]), "email": shown_email,
                            "run_id": int(result["id"]), "running": not cancelled})
        storage.project_cancel_requested(conn, stopped)
    return {"ok": True, "stopped": stopped, "stopped_count": len(stopped),
            "skipped": skipped, "skipped_count": len(skipped)}
