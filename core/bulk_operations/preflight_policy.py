"""套餐预检 v1 的有限资格契约；不加载驱动、部署能力或实时配置。"""
from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping


PLAN_CHECK_POLICY = "plan_check_db_v1"
REGISTRATION_TYPES = ("registration", "registration_resume")
REGISTRATION_STATUSES = ("pending", "queued", "running", "stopping", "cancelling", "settling", "waiting", "debug_paused")
# Python str.strip 的完整空白集；SQL不能用默认BTRIM替代它。
PYTHON_WHITESPACE = "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
RULES = (
    ("missing", "not_executable", "account_missing"),
    ("deactivated", "not_executable", "account_deactivated"),
    ("email_missing", "not_executable", "account_email_missing"),
    ("run_busy", "waiting_account", "account_busy"),
    ("registration_busy", "waiting_account", "registration_in_progress"),
    ("token_missing", "not_executable", "access_token_missing"),
)


def effective_settings(settings):
    """保留旧preflight_many一层config_snapshot包装约定。"""
    value = settings.get("config_snapshot", settings) or {}
    return dict(value) if isinstance(value, Mapping) else {}


def plan_check_result(account, *, blocker_run_id, registration_busy, settings):
    value = account or {}
    facts = {
        "missing": not account,
        "deactivated": any(str(value.get(key) or "").strip().lower() == "deactivated"
                           for key in ("account_status", "codex_status", "codex_credential_state")),
        "email_missing": not str(value.get("email") or "").strip(),
        "run_busy": blocker_run_id is not None,
        "registration_busy": registration_busy,
        "token_missing": not value.get("access_token") and not settings.get("auto_refresh_at_enabled", True),
    }
    for predicate, status, reason in RULES:
        if facts[predicate]:
            return {"disposition": status, "reason_code": reason,
                    "blocker_run_id": blocker_run_id if predicate == "run_busy" else None}
    return {"disposition": "ready", "reason_code": None, "blocker_run_id": None}


def sql_result_cases(facts):
    """只接受服务器固定表达式；顺序、状态和错误码与Python规则共享。"""
    return tuple("CASE " + " ".join(f"WHEN {facts[name]} THEN '{rule[index]}'"
                 for rule in RULES for name in (rule[0],)) + f" ELSE {default} END"
                 for index, default in ((1, "'ready'"), (2, "NULL::text")))


def prepare_plan_check(targets, *, settings, conn, account_table, run_table, job_table, active_statuses):
    """旧分页回调的数据库资格材料，供显式回退和领域适配器共用。"""
    def identity(target):
        return int(target.get("account_id") or target.get("entity_id") or target.get("target_id") or 0)

    ids = sorted({identity(target) for target in targets if identity(target) > 0})
    with conn.cursor() as cur:
        cur.execute(f"""SELECT id,email,email_invalid,codex_status,codex_credential_state,
            data->>'account_status' AS account_status,
            CASE WHEN account_has_access_token THEN 'present' ELSE '' END AS access_token
            FROM {account_table} WHERE id=ANY(%s)""", (ids,))
        accounts = {int(row["id"]): dict(row) for row in cur.fetchall()}
        cur.execute(f"SELECT id,account_id FROM {run_table} WHERE account_id=ANY(%s) AND status=ANY(%s) ORDER BY id",
                    (ids, list(active_statuses)))
        active = {}
        for row in cur.fetchall():
            active.setdefault(int(row["account_id"]), int(row["id"]))
        emails = [str(row.get("email") or "").strip().lower() for row in accounts.values() if row.get("email")]
        cur.execute(f"""SELECT account_id,email FROM {job_table}
            WHERE COALESCE(NULLIF(job_type,''),'registration')=ANY(%s) AND status=ANY(%s)
              AND (account_id=ANY(%s) OR LOWER(BTRIM(email))=ANY(%s))""",
                    (list(REGISTRATION_TYPES), list(REGISTRATION_STATUSES), ids, emails))
        jobs = list(cur.fetchall())
    busy_accounts = {int(row.get("account_id") or 0) for row in jobs}
    busy_emails = {str(row.get("email") or "").strip().lower() for row in jobs}
    result = []
    for target in targets:
        account_id = identity(target)
        account = accounts.get(account_id)
        busy = account_id in busy_accounts or str((account or {}).get("email") or "").strip().lower() in busy_emails
        result.append({"target": dict(target), "account": account,
                       **plan_check_result(account, blocker_run_id=active.get(account_id), registration_busy=busy, settings=settings)})
    return result


def plan_check_receipts(targets, **kwargs):
    checked_at = datetime.now(timezone.utc).isoformat()
    return [{"target_id": item["target"].get("id") or item["target"].get("target_id"),
             "status": item["disposition"], "reason_code": item["reason_code"],
             "blocker_run_id": item["blocker_run_id"], "checked_at": checked_at}
            for item in prepare_plan_check(targets, **kwargs)]
