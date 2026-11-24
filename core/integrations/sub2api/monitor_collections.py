"""一轮 Sub2API 巡检在内存分类，集合提交本地修复与子任务。"""
from __future__ import annotations

import hashlib
import importlib
import json
import os

from psycopg.rows import dict_row

from config import email as email_config
from core import db
from core.accounts.credentials import get_account_totp_secret_candidate
from core.operations import task_gateway
from core.storage import postgres as pg, records, sub2api
from core.storage import sub2api_monitor as storage
from core.storage.codex import bulk_submission as codex_storage
from core.storage.operations import bulk_submission


def password(account):
    extra = account.get("extra_json") or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (ValueError, TypeError):
            extra = {}
    keys = ("account_password", "login_password", "registration_password")
    value = str(next((extra.get(key) for key in keys if isinstance(extra, dict) and extra.get(key)), "")).strip()
    if not value:
        value = str(next((account.get(key) for key in keys if account.get(key)), "")).strip()
    return value


class Scan:
    def __init__(self, backend, accounts, facts):
        self.backend, self.accounts = backend, accounts
        self.states = facts["states"]
        self.credentials = facts["credentials"]
        self.by_filename = {row["filename"]: row for row in self.credentials}
        self.runs, self.active, self.jobs = facts["runs"], facts["active"], facts["jobs"]
        self.changed, self.oauth, self.sync = {}, [], []
        self.material = None
        self.secrets = None

    def save(self, account_id, state, **changes):
        fields = {key: value for key, value in state.items() if key in sub2api._REPAIR_FIELDS}
        fields.update(changes)
        value = {**fields, "backend": self.backend, "account_id": account_id}
        self.states[account_id] = value
        self.changed[account_id] = value
        return value

    def login_ready(self, account):
        if account.get("email_invalid"):
            return False
        secret = get_account_totp_secret_candidate(account)
        if str(account.get("twofa_status") or "").lower() in {"success", "enabled"} and not secret:
            return False
        if password(account):
            return True
        if not bool(getattr(email_config, "USE_EMAIL_SERVICE", True)):
            return False
        source, email = str(account.get("email_source") or "").strip(), str(account.get("email") or "").lower()
        if not source:
            return False
        if self.material is None:
            self.material = storage.login_material([
                row for row in self.accounts.values() if not password(row) and not row.get("email_invalid")
            ])
        if "+" in email.partition("@")[0] and email in self.material["bindings"]:
            return True
        row = self.material["pools"].get(source, {}).get(email)
        if source in {"cloudflare_domain", "icloud_hide"}:
            return bool(row)
        if source == "outlook":
            from core.email.outlook import client

            if client._cache_key(email) in client._CONTEXT_CACHE:
                return True
            if not row:
                row = account
            def first(*keys):
                for source_row in (row, account if account is not row else None):
                    for key in keys:
                        value = str((source_row or {}).get(key) or "").strip()
                        if value:
                            return value
                return ""

            return all((first("email") or email, first("password"), first("client_id", "clientId"),
                        first("refresh_token", "refreshToken")))
        if source == "generic_api":
            from core.email.generic_api import client

            cached = client._CONTEXT_CACHE.get(email)
            if cached is not None:
                client._require_account_usable(cached)
                return True
            if not row:
                return False
            from core.email.generic_api.client import GenericApiEmailAccount, _require_account_usable

            candidate = GenericApiEmailAccount(email=row["email"], code_url=row["code_url"],
                expires_at=row.get("expires_at"), expires_at_epoch=row.get("expires_at_epoch"))
            _require_account_usable(candidate)
            return True
        if source == "email_butler":
            from core.email.email_butler import client

            if client.get_account_context(email):
                return True
            if not row or row.get("status") == "tombstone":
                return False
            profile = self.material["profiles"].get(int(row.get("local_inbox_profile_id") or row.get("inbox_profile_id") or 0))
            if not profile or profile.get("state") != "active" or profile.get("connector") != "forward_butler":
                return False
            if self.secrets is None:
                from config.runtime import read_persisted_values

                self.secrets = read_persisted_values()
            reference = str(profile.get("credential_ref") or "")
            if not str(self.secrets.get(reference) or os.environ.get(reference) or "").strip():
                return False
            from core.email.email_butler.v2 import normalize_base

            normalize_base(str((profile.get("inbox_locator") or {}).get("api_base") or ""))
            return True
        if source in {"mailcode", "xigua"}:
            module = importlib.import_module(f"core.email.{source}.client")
            identity = module._identity()
            matches = [row for row in self.material["orders"]
                       if row["provider"] == source and row["supplier_ref"] == identity
                       and str(row["email"]).lower() == email]
            if len(matches) > 1:
                return False
            if not matches:
                return False
            # 沿用供应商本地反序列化的资格检查，不猜测缺失订单资料。
            return bool(module._account(matches[0]))
        if source in {"gptmail", "cloudflare", "mailnest", "cloudmail", "remail"}:
            # 这些客户端只读进程缓存，不查询数据库或申请新邮箱。
            module = importlib.import_module(f"core.email.{source}.client")
            return bool(module.get_account_context(email))
        return False

    def queue_sync(self, account_id, state, filename, generation):
        targets = list(state.get("remote_account_ids") or [])
        items = [row for row in self.jobs if row["filename"] == filename
                 and row["generation"] == generation and row["remote_account_id"] in targets]
        if {row["remote_account_id"] for row in items} != set(targets):
            credential = self.by_filename.get(filename)
            if not credential:
                return {"accepted": False, "items": []}
            self.sync.append({"account_id": account_id, "email": self.accounts[account_id]["email"],
                              "filename": filename, "credential_id": credential["id"],
                              "generation": generation, "remote_account_ids": targets})
            old_by_target = {row["remote_account_id"]: row for row in items}
            items = [old_by_target.get(target, {"remote_account_id": target, "status": "pending"})
                     for target in targets]
        return {"accepted": True, "items": items}

    def start_reauth(self, account, state, generation):
        current = self.save(account["id"], state, stage="reauth_submitting", source_generation=generation,
                            run_id=None, task_id=None, last_code="reauth_submitting",
                            attempt_count=int(state.get("attempt_count") or 0) + 1)
        self.oauth.append((account, current))

    def flush(self, summary, *, include_retries, now, cooldown):
        from core.codex import operation_service

        snapshot, unavailable = None, None
        if self.oauth:
            snapshot = operation_service._config_snapshot()
            unavailable = operation_service._deployment_unavailable(snapshot)
            ready, reason = operation_service._feature_ready(snapshot)
            if not unavailable and not ready:
                unavailable = {"accepted": False, "error": reason}
        with pg.connect(row_factory=dict_row) as conn:
            # 先保存补传意图并锁定所有待投递任务，再进入账号准入，沿用补传生产者锁序。
            storage.queue_sync_many(conn, self.backend, self.sync)
            storage.enqueue_due_many(self.backend, include_retries=include_retries, conn=conn,
                                     held_accounts={account["id"] for account, _ in self.oauth})
            current_accounts, unavailable_accounts = storage.locked_accounts(conn, [account["id"] for account, _ in self.oauth])
            busy = storage.active_runs(conn, [account["id"] for account, _ in self.oauth])
            specs, selected = [], []
            for account, state in self.oauth:
                account_id = account["id"]
                if account_id in unavailable_accounts:
                    self.save(account_id, state, stage="cooldown", last_code="reauth_queue_failed",
                              manual_requested=False, next_attempt_at=now + cooldown)
                    summary["reasons"]["reauth_queue_failed"] = summary["reasons"].get("reauth_queue_failed", 0) + 1
                    continue
                if account_id in busy:
                    owned = busy[account_id]
                    self.save(account_id, state, stage="reauth_wait", run_id=owned["id"],
                              task_id=owned["task_id"], last_code="reauth_pending")
                    continue
                current = current_accounts.get(account_id)
                if (unavailable or not current or db.account_is_deactivated(current)
                        or str(current.get("email") or "").strip().casefold() != str(account["email"]).strip().casefold()):
                    self.save(account_id, state, stage="cooldown", last_code="reauth_queue_failed",
                              manual_requested=False, next_attempt_at=now + cooldown)
                    summary["reasons"]["reauth_queue_failed"] = summary["reasons"].get("reauth_queue_failed", 0) + 1
                    continue
                targets = {"backend_identity": self.backend, "remote_account_ids": list(state["remote_account_ids"])}
                key = hashlib.sha256(json.dumps([self.backend, account_id, state["source_generation"],
                                                targets["remote_account_ids"], state["attempt_count"]],
                                               separators=(",", ":")).encode()).hexdigest()
                specs.append({"task_type": "codex_retry", "account_id": account_id, "email": account["email"],
                              "trigger": "sub2api_monitor", "source_id": "sub2api-reauth:" + key,
                              "data": {"sub2api_targets": targets}, "config_snapshot": snapshot,
                              "config_allowlist": ("oauth_driver", "auth_source", "phone_enabled", "sms_provider", "sms_country",
                                                   "account_proxy_mode", "account_proxy_modes", "auto_upload_sub2api")})
                selected.append((account, state))
            receipts = bulk_submission.create_specs(specs, conn=conn)
            codex_storage.project_queued(conn, [
                {"account_id": account["id"], **result}
                for (account, _), result in zip(selected, receipts, strict=True)
            ])
            for (account, state), result in zip(selected, receipts, strict=True):
                self.save(account["id"], state, stage="reauth_wait", run_id=result["run_id"],
                          task_id=result["task_id"], last_code="reauth_pending")
            storage.save_repairs(conn, self.backend, self.changed)
        summary["reauth_queued"] += len(receipts)
        if receipts or self.sync:
            task_gateway.notify_dispatch()
