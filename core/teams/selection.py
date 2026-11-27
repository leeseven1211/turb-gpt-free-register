"""Team 加入专用的固定名单读取，不复跑原筛选或读取账号凭据。"""
from __future__ import annotations

from datetime import datetime, timezone

from psycopg.rows import dict_row

from core.storage import postgres
from core.storage.operations import bulk_common
from core.teams.errors import TeamError


def _positive_id(value, field):
    text = str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else ""
    if (not text.isascii() or not text.isdecimal() or text.startswith("0") or len(text) > 19
            or not 0 < int(text) < 2**63):
        raise TeamError("parameter_invalid", "标识必须为正整数", status=422, field=field)
    return int(text)


def preflight_team_targets(targets, conn):
    """名单准备仅核对本地账号存在性，业务资格由目标 Team 预览核对。"""
    ids = [int(row["target_id"]) for row in targets]
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT id,email,deactivated FROM {postgres.qualified('registered_accounts')} WHERE id=ANY(%s)",
            (ids,),
        )
        accounts = {int(row["id"]): row for row in cur.fetchall()}
    at = datetime.now(timezone.utc).isoformat()
    results = []
    for target in targets:
        account = accounts.get(int(target["target_id"]))
        reason = ("account_missing" if account is None else
                  "account_deactivated" if account["deactivated"] else
                  "account_email_missing" if not str(account["email"] or "").strip() else None)
        results.append({"target_id": target["id"], "status": "not_executable" if reason else "ready",
                        "reason_code": reason, "checked_at": at, "blocker_run_id": None})
    return results


def read_team_selection(selection_id, selection_revision, team_id, *, for_consumption=False, conn=None):
    """读取固定账号与邮箱；消费调用持有同一事务行锁直到加入请求持久化。"""
    selected_id = _positive_id(selection_id, "selection_id")
    target_team_id = _positive_id(team_id, "team_id")
    if isinstance(selection_revision, bool) or not isinstance(selection_revision, int) or selection_revision < 1:
        raise TeamError("parameter_invalid", "名单修订无效", status=422, field="selection_revision")
    if for_consumption and conn is None:
        raise TeamError("selection_transaction_required", "名单事务缺失", status=500)
    if conn is None:
        with bulk_common.connect() as connection:
            return _read(connection, selected_id, selection_revision, target_team_id, for_consumption=False)
    return _read(conn, selected_id, selection_revision, target_team_id, for_consumption=for_consumption)


def _read(conn, selection_id, revision, team_id, *, for_consumption):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT to_regclass(%s) AS name", (bulk_common.table("operation_selections"),))
        if cur.fetchone()["name"] is None:
            raise TeamError("selection_not_found", "固定名单不存在", status=404)
        lock = " FOR UPDATE" if for_consumption else ""
        cur.execute(f"SELECT * FROM {bulk_common.table('operation_selections')} WHERE id=%s{lock}",
                    (selection_id,))
        selected = cur.fetchone()
        if selected is None:
            raise TeamError("selection_not_found", "固定名单不存在", status=404)
        if (selected["action_key"] != "team_join" or selected["action_version"] != 1
                or selected["selection_kind"] not in {"account_query", "explicit_ids"}):
            raise TeamError("selection_operation_mismatch", "名单操作不符")
        if str((selected["parameters"] or {}).get("team_id")) != str(team_id):
            raise TeamError("selection_team_mismatch", "名单团队不符")
        cur.execute("SELECT to_regclass(%s) AS name", (postgres.qualified("team_join_requests"),))
        existing_request = None
        if cur.fetchone()["name"] is not None:
            cur.execute(f"SELECT id FROM {postgres.qualified('team_join_requests')} WHERE selection_id=%s",
                        (selection_id,))
            existing_request = cur.fetchone()
        if existing_request or selected["status"] == "consumed":
            raise TeamError("selection_consumed", "名单已被使用",
                            details={"existing_join_request_id": str(existing_request["id"]) if existing_request else None})
        if selected["status"] == "expired" or selected["expires_at"] <= datetime.now(timezone.utc):
            raise TeamError("selection_expired", "固定名单已过期", status=410)
        if selected["status"] != "ready":
            raise TeamError("selection_not_ready", "固定名单尚未就绪")
        if int(selected["selection_revision"]) != revision:
            raise TeamError("selection_revision_mismatch", "名单修订不符")
        cur.execute(
            f"""SELECT target_id,display_snapshot FROM {bulk_common.table('operation_selection_targets')}
                WHERE selection_id=%s AND target_kind='account' ORDER BY ordinal""",
            (selection_id,),
        )
        targets = cur.fetchall()
    account_ids = [str(row["target_id"]) for row in targets]
    return {"selection_id": str(selection_id), "selection_revision": revision,
            "account_ids": account_ids,
            "expected_emails": {str(row["target_id"]): str((row["display_snapshot"] or {}).get("email") or "")
                                for row in targets}}
