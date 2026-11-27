# -*- coding: utf-8 -*-
"""Team 预检的单行集合聚合；不展开账号状态或读取认证材料。"""
from __future__ import annotations

from contextlib import nullcontext

from psycopg import Error as PostgresError
from psycopg.rows import dict_row

from core.storage import postgres
from core.teams.errors import TeamError

_ACTIVE_SQL = "'queued','running','waiting','cancelling','settling','stopping'"
_CATEGORIES = (
    "unavailable", "another_team", "already_member", "same_team_active",
    "missing_auth", "resume_invite", "new",
)


def _normalized_email(expression):
    """保持与现有账号表达式索引相同的规范化形式。"""
    return f"lower(btrim(COALESCE({expression},'')))"


def _bigint_id(value):
    """先检查无损十进制长度，避免超长合法引用触发 Python 整数转换限制。"""
    text = str(value)
    if len(text) > 19:
        return None
    number = int(text)
    return number if 0 < number < 2**63 else None


def _array_parameters(ids, emails, frozen):
    """预编码绑定数组，避免 psycopg 对十万项逐个执行 Python 适配。"""
    number_array = "{" + ",".join("NULL" if value is None else str(value) for value in ids) + "}"
    if not any(frozen):
        # 多数组 unnest 会为短数组补 NULL；没有冻结身份时不传重复空值。
        return number_array, "{}", "{}"
    email_array = "{" + ",".join(
        "NULL" if value is None else '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        for value in emails
    ) + "}"
    frozen_array = "{" + ",".join("t" if value else "f" for value in frozen) + "}"
    return number_array, email_array, frozen_array


def _statement():
    accounts, members, invitations, workspaces, ownership = (
        postgres.qualified(name) for name in (
            "registered_accounts", "team_members", "team_invitations",
            "team_workspaces", "team_account_ownership",
        )
    )
    counts = ",".join(
        f"COALESCE(sum(target_count) FILTER (WHERE category='{category}'),0) AS {category}_count"
        for category in _CATEGORIES
    )
    return f"""
        WITH selected AS (
            SELECT account_id,expected_email,COALESCE(identity_frozen,FALSE) AS identity_frozen
            FROM unnest(%s::bigint[],%s::text[],%s::boolean[])
            AS s(account_id,expected_email,identity_frozen)
        ), targets AS MATERIALIZED (
            SELECT s.account_id AS selected_id,s.expected_email,s.identity_frozen,a.id,a.email,
                   a.deactivated,a.account_status_text,a.email_invalid,
                   a.account_has_access_token,a.account_has_password
            FROM selected s LEFT JOIN {accounts} a ON a.id=s.account_id
        ), unlinked_members AS MATERIALIZED (
            SELECT a.id AS account_id,{_normalized_email("a.email")} AS normalized_email,m.team_id
            FROM targets a JOIN {members} m ON m.account_id IS NULL
              AND {_normalized_email("m.email")}={_normalized_email("a.email")}
            WHERE {_normalized_email("a.email")}<>'' AND m.membership_state='joined'
        ), unlinked_invitations AS MATERIALIZED (
            SELECT a.id AS account_id,{_normalized_email("a.email")} AS normalized_email,i.id,i.team_id,
                   i.invitation_state,i.membership_state,i.execution_status,
                   i.active,i.seat_reserved,i.updated_at
            FROM targets a JOIN {invitations} i ON i.account_id IS NULL
              AND {_normalized_email("i.email_snapshot")}={_normalized_email("a.email")}
            WHERE {_normalized_email("a.email")}<>''
        ), fallback_emails AS (
            SELECT normalized_email FROM unlinked_members
            UNION SELECT normalized_email FROM unlinked_invitations
        ), unique_accounts AS MATERIALIZED (
            SELECT {_normalized_email("original.email")} AS normalized_email,
                   min(original.id) AS account_id
            FROM {accounts} original
            JOIN fallback_emails e ON e.normalized_email={_normalized_email("original.email")}
            GROUP BY {_normalized_email("original.email")} HAVING count(*)=1
        ), member_relations AS (
            SELECT a.id AS account_id,m.team_id
            FROM targets a JOIN {members} m ON m.account_id=a.id
            WHERE m.membership_state='joined'
            UNION ALL
            SELECT m.account_id,m.team_id FROM unlinked_members m
            JOIN unique_accounts u ON u.normalized_email=m.normalized_email
              AND u.account_id=m.account_id
        ), target_invitations AS (
            SELECT a.id AS account_id,i.id,i.team_id,i.invitation_state,i.membership_state,
                   i.execution_status,i.active,i.seat_reserved,i.updated_at
            FROM targets a JOIN {invitations} i ON i.account_id=a.id
            UNION ALL
            SELECT i.account_id,i.id,i.team_id,i.invitation_state,i.membership_state,
                   i.execution_status,i.active,i.seat_reserved,i.updated_at
            FROM unlinked_invitations i
            JOIN unique_accounts u ON u.normalized_email=i.normalized_email
              AND u.account_id=i.account_id
        ), invitation_flags AS (
            SELECT account_id,
                   bool_or(team_id<>%s AND
                       (active OR seat_reserved OR invitation_state='pending' OR membership_state='joined'))
                       AS other_team,
                   bool_or(team_id=%s AND active AND execution_status IN ({_ACTIVE_SQL})) AS executing,
                   bool_or(team_id=%s AND
                       (seat_reserved OR invitation_state='pending' OR membership_state='joined')) AS occupied,
                   (array_agg(invitation_state ORDER BY updated_at DESC,id DESC)
                       FILTER (WHERE team_id=%s))[1]='pending' AS latest_pending
            FROM target_invitations GROUP BY account_id
        ), member_flags AS (
            SELECT account_id,bool_or(team_id<>%s) AS other_team,
                   bool_or(team_id=%s) AS joined
            FROM member_relations GROUP BY account_id
        ), other_owners AS (
            SELECT o.account_id FROM {ownership} o JOIN targets a ON a.id=o.account_id
            WHERE o.team_id<>%s
            UNION
            SELECT w.manager_account_id FROM {workspaces} w JOIN targets a ON a.id=w.manager_account_id
            WHERE w.id<>%s
        ), all_flags AS (
            SELECT account_id,other_team,joined,FALSE AS executing,
                   FALSE AS occupied,FALSE AS latest_pending
            FROM member_flags
            UNION ALL
            SELECT account_id,other_team,FALSE,executing,occupied,latest_pending
            FROM invitation_flags
            UNION ALL
            SELECT account_id,TRUE,FALSE,FALSE,FALSE,FALSE FROM other_owners
        ), relation_flags AS (
            SELECT account_id,bool_or(other_team) AS other_team,bool_or(joined) AS joined,
                   bool_or(executing) AS executing,bool_or(occupied) AS occupied,
                   bool_or(latest_pending) AS latest_pending
            FROM all_flags GROUP BY account_id
        ), classified AS (
            SELECT CASE
                       WHEN a.id IS NULL OR a.deactivated OR
                            a.account_status_text IN ('deactivated','disabled','deleted','banned') OR
                            CASE WHEN NOT a.identity_frozen THEN FALSE
                                 WHEN a.email IS NOT DISTINCT FROM a.expected_email THEN FALSE
                                 ELSE {_normalized_email("a.email")}<>
                                      {_normalized_email("a.expected_email")}
                            END THEN 'unavailable'
                       WHEN f.other_team THEN 'another_team'
                       WHEN f.joined THEN 'already_member'
                       WHEN f.executing THEN 'same_team_active'
                       WHEN NOT a.account_has_access_token AND NOT a.account_has_password
                            AND a.email_invalid THEN 'missing_auth'
                       WHEN f.latest_pending THEN 'resume_invite'
                       ELSE 'new'
                   END AS category,COALESCE(f.occupied,FALSE) AS occupied
            FROM targets a LEFT JOIN relation_flags f ON f.account_id=a.id
        ), buckets AS (
            SELECT category,count(*) AS target_count,
                   count(*) FILTER (WHERE NOT occupied) AS additional_count
            FROM classified GROUP BY category
        )
        SELECT {counts},%s::integer AS requested_count,COALESCE(sum(target_count),0) AS unique_count,
               %s::integer-COALESCE(sum(target_count),0) AS duplicate_count,
               COALESCE(sum(target_count) FILTER (
                   WHERE category IN ('new','resume_invite','same_team_active')),0) AS eligible_count,
               COALESCE(sum(additional_count) FILTER (
                   WHERE category IN ('new','resume_invite','same_team_active')),0) AS additional_required
        FROM buckets
    """


def _parameters(team_id, account_ids, expected_emails):
    unique = list(dict.fromkeys(account_ids))
    expected = expected_emails or {}
    # API 接收无损十进制字符串；超出 bigint 的引用仍作为不存在目标参与统计。
    ids = [_bigint_id(value) for value in unique]
    emails = [expected.get(value) for value in unique] if expected else ()
    frozen = [value is not None for value in emails] if expected else ()
    return [
        *_array_parameters(ids, emails, frozen), *([int(team_id)] * 8),
        len(account_ids), len(account_ids),
    ]


def _query(statement, params, *, conn):
    try:
        context = nullcontext(conn) if conn is not None else postgres.connect(row_factory=dict_row)
        with context as db, db.cursor(row_factory=dict_row) as cur:
            cur.execute(statement, params)
            row = cur.fetchone()
            return dict(row) if row is not None else None
    except PostgresError:
        raise TeamError(
            "team_store_unavailable", "Team 存储暂不可用", status=503, retryable=True,
        ) from None


def _result(row):
    additional = int(row.pop("additional_required"))
    return {"counts": {key: int(value) for key, value in row.items()},
            "additional_required": additional}


def summary(team_id, account_ids, expected_emails=None, *, conn=None):
    """按 domain 优先级返回七类计数及已有占位净并集所需的额外席位。"""
    return _result(_query(
        _statement(), _parameters(team_id, account_ids, expected_emails), conn=conn,
    ))


def snapshot(team_id, account_ids, expected_emails=None, *, conn=None):
    """一次读取预检、Team 窄快照与容量事实，三者来自相同数据库快照。"""
    # repository 先完成初始化，避免 joins 首次导入时触发相互引用。
    from core.storage.teams import repository
    from core.storage.teams.joins import _occupancy_sql

    statement = f"""
        WITH workspace AS MATERIALIZED (
            SELECT id,snapshot_sequence,last_synced_at,purchased_seats,planned_member_limit,
                   members_complete,invitations_complete
            FROM {repository.table("team_workspaces")} WHERE id=%s
        )
        SELECT w.id AS _team_id,w.snapshot_sequence AS _snapshot_sequence,
               w.last_synced_at AS _last_synced_at,w.purchased_seats,w.planned_member_limit,
               w.members_complete,w.invitations_complete,
               CASE WHEN w.members_complete AND w.invitations_complete
                    THEN ({_occupancy_sql()}) ELSE NULL END AS occupied_count,
               evaluated.*
        FROM workspace w CROSS JOIN ({_statement()}) evaluated
    """
    row = _query(
        statement,
        [int(team_id), int(team_id), int(team_id),
         *_parameters(team_id, account_ids, expected_emails)],
        conn=conn,
    )
    if row is None:
        raise TeamError("team_not_found", "Team 不存在", status=404)
    team = {
        "id": row.pop("_team_id"),
        "snapshot_sequence": row.pop("_snapshot_sequence"),
        "last_synced_at": row.pop("_last_synced_at"),
    }
    facts = {key: row.pop(key) for key in (
        "purchased_seats", "planned_member_limit", "members_complete",
        "invitations_complete", "occupied_count",
    )}
    return {**_result(row), "team": team, "facts": facts}
