# -*- coding: utf-8 -*-
"""Team 的窄字段读模型；查询不初始化数据库，也不读取账号凭据。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from psycopg import Error as PostgresError
from psycopg.rows import dict_row

from core.storage import postgres
from core.teams.errors import TeamError

_ACTIVE_SQL = "'queued','running','waiting','cancelling','settling','stopping'"
_TEAM_COLUMNS = (
    "id", "workspace_id", "manager_account_id", "revision", "manager_revision",
    "name", "display_name", "role", "purchased_seats", "planned_member_limit",
    "confirmed_member_count", "pending_invite_count", "members_complete",
    "invitations_complete", "members_synced_at", "invitations_synced_at",
    "last_synced_at", "last_sync_status", "permission_verified_at", "permissions",
    "last_snapshot_at", "snapshot_sequence", "created_at", "updated_at",
)
_MEMBER_COLUMNS = (
    "id", "team_id", "identity_key", "remote_user_id", "email", "account_id",
    "role", "membership_state", "joined_at", "last_verified_at", "last_task_id",
    "last_run_id", "execution_status", "source_revision", "created_at", "updated_at",
)
_INVITATION_COLUMNS = (
    "id", "team_id", "target_key", "account_id", "email_snapshot",
    "remote_invitation_id", "invitation_state", "membership_state",
    "execution_status", "stage", "waiting_reason_code", "reason_code",
    "error_message", "last_task_id", "last_run_id", "active", "seat_reserved",
    "execution_fence", "manager_revision", "local_saved", "last_verified_at",
    "created_at", "updated_at",
)


def _table(name):
    return postgres.qualified(name)


def _columns(alias, names):
    return ",".join(f"{alias}.{name}" for name in names)


@contextmanager
def _connection(conn=None):
    try:
        if conn is not None:
            yield conn
        else:
            with postgres.connect(row_factory=dict_row) as opened:
                yield opened
    except PostgresError:
        raise TeamError(
            "team_store_unavailable", "Team 存储暂不可用",
            status=503, retryable=True,
        ) from None


def _rows(conn, statement, values=()):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(statement, values)
        return [dict(row) for row in cur.fetchall()]


def _ids(values):
    """过滤超过 PostgreSQL bigint 范围的引用，不改变有效目标顺序。"""
    return list(dict.fromkeys(int(value) for value in values if 0 < int(value) < 2**63))


def _normalized_email(expression):
    """与账号现有表达式索引完全一致，避免每个目标扫描全账号表。"""
    return f"lower(btrim(COALESCE({expression},'')))"


def _target_email_ctes():
    """只对目标邮箱做一次全局去重，未关联事实不会按目标窗口误判唯一。"""
    normalized = _normalized_email("original.email")
    return f"""
        target_emails AS MATERIALIZED (
            SELECT DISTINCT normalized_email FROM targets WHERE normalized_email<>''
        ), unique_accounts AS MATERIALIZED (
            SELECT {normalized} AS normalized_email,min(original.id) AS account_id
            FROM {_table('registered_accounts')} original
            JOIN target_emails e ON e.normalized_email={normalized}
            GROUP BY {normalized} HAVING count(*)=1
        )
    """


def _team_select():
    return (
        f"SELECT {_columns('w', _TEAM_COLUMNS)},"
        "a.email AS manager_email,a.archived AS manager_archived,"
        "COALESCE(p.processing_count,0)::integer AS processing_count,"
        "md5(concat(w.id,':',w.updated_at,':',a.updated_at,':',"
        "COALESCE(p.processing_count,0),':',p.processing_updated_at)) AS _read_revision_key "
        f"FROM {_table('team_workspaces')} w "
        f"LEFT JOIN {_table('registered_accounts')} a ON a.id=w.manager_account_id "
        "LEFT JOIN LATERAL ("
        "SELECT count(DISTINCT COALESCE(i.account_id::text,i.target_key)) AS processing_count,"
        "max(i.updated_at) AS processing_updated_at "
        f"FROM {_table('team_invitations')} i "
        f"WHERE i.team_id=w.id AND i.active AND i.execution_status IN ({_ACTIVE_SQL})"
        ") p ON TRUE"
    )


def _account_select(table, alias, columns):
    email_column = "email_snapshot" if table == "team_invitations" else "email"
    selected = ",".join(
        f"COALESCE({alias}.account_id,a.id) AS account_id" if name == "account_id" else f"{alias}.{name}"
        for name in columns
    )
    return (
        f"SELECT {selected},"
        "a.email AS account_email,a.archived AS account_archived,"
        f"md5(concat({alias}.id,':',{alias}.updated_at,':',a.id,':',a.updated_at)) AS _read_revision_key "
        f"FROM {_table(table)} {alias} "
        "LEFT JOIN LATERAL (SELECT min(matches.id) AS account_id FROM ("
        f"SELECT original.id FROM {_table('registered_accounts')} original "
        f"WHERE {alias}.account_id IS NULL AND {_normalized_email(f'{alias}.{email_column}')}<>'' "
        f"AND {_normalized_email('original.email')}={_normalized_email(f'{alias}.{email_column}')} "
        "LIMIT 2) matches HAVING count(*)=1) matched ON TRUE "
        f"LEFT JOIN {_table('registered_accounts')} a ON a.id=COALESCE({alias}.account_id,matched.account_id)"
    )


def _filter(query, alias, fields, *, scope=(), values=(), search_fields=()):
    conditions, params = list(scope), list(values)
    for field in fields:
        if query.get(field) is not None:
            conditions.append(f"{alias}.{field}=%s")
            params.append(query[field])
    search = str(query.get("q") or "").strip()
    if search and search_fields:
        # q 是普通子串，不把用户输入的百分号和下划线当作 SQL 通配符。
        pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append("(" + " OR ".join(f"{field} ILIKE %s" for field in search_fields) + ")")
        params.extend(pattern for _ in search_fields)
    return (" AND ".join(conditions) if conditions else "TRUE"), params


def _page(conn, select, where, values, query, *, order, facets):
    """一次读取真实 total、完整范围修订及当前页，空页也保留 total。"""
    page, size = int(query.get("page", 1)), int(query.get("page_size", 20))
    source = select + " WHERE " + where
    include_facets = bool(query.get("include_facets"))
    facet_columns = []
    for name in facets if include_facets else ():
        facet_columns.append(
            f"'{name}',(SELECT COALESCE(jsonb_agg(jsonb_build_object("
            "'value',g.value,'count',g.count) ORDER BY g.value),'[]'::jsonb) "
            f"FROM (SELECT {name}::text AS value,count(*) AS count "
            f"FROM filtered GROUP BY {name}) g)"
        )
    facet_select = ",jsonb_build_object(" + ",".join(facet_columns) + ") AS _facets" if include_facets else ""
    statement = (
        f"WITH filtered AS MATERIALIZED ({source}),summary AS ("
        "SELECT count(*) AS _total,"
        "concat(count(*),':',md5(COALESCE(string_agg(_read_revision_key,',' ORDER BY id),''))) AS _revision"
        f"{facet_select} FROM filtered) "
        "SELECT p.*,s._total,s._revision FROM summary s LEFT JOIN LATERAL ("
        f"SELECT * FROM filtered ORDER BY {order} LIMIT %s OFFSET %s"
        ") p ON TRUE"
    )
    if include_facets:
        statement = statement.replace("SELECT p.*,s._total,s._revision FROM summary",
                                      "SELECT p.*,s._total,s._revision,s._facets FROM summary")
    rows = _rows(conn, statement, [*values, size, (page - 1) * size])
    result = {
        "items": [{key: value for key, value in row.items()
                   if key not in {"_total", "_revision", "_facets", "linked", "_read_revision_key"}}
                  for row in rows if row.get("id") is not None],
        "total": int(rows[0]["_total"]), "page": page, "page_size": size,
        "revision": rows[0]["_revision"],
    }
    if include_facets:
        result["facets"] = rows[0]["_facets"]
    return result


def get_team(team_id, *, for_update=False, conn=None):
    with _connection(conn) as db:
        rows = _rows(
            db, _team_select() + " WHERE w.id=%s" + (" FOR UPDATE OF w" if for_update else ""),
            (int(team_id),),
        )
        if not rows:
            return None
        row = rows[0]
        row.pop("_read_revision_key", None)
        return row


def list_teams(query=None, *, conn=None):
    query = query or {}
    where, values = _filter(
        query, "w", ("manager_account_id", "role", "last_sync_status"),
        search_fields=("w.name", "w.display_name", "w.id::text", "a.email"),
    )
    with _connection(conn) as db:
        return _page(
            db, _team_select(), where, values, query, order="id DESC",
            facets=("role", "last_sync_status"),
        )


def list_members(team_id, query=None, *, conn=None):
    query = {"membership_state": "joined", **(query or {})}
    where, values = _filter(
        query, "m", ("membership_state", "role"),
        scope=("m.team_id=%s",), values=(int(team_id),),
        search_fields=("m.email", "m.id::text", "m.account_id::text", "a.email"),
    )
    linked = query.get("linked", "all")
    if linked in {"linked", "unlinked"}:
        where += " AND a.id IS " + ("NOT NULL" if linked == "linked" else "NULL")
    select = _account_select("team_members", "m", _MEMBER_COLUMNS).replace(
        " FROM ", ",CASE WHEN a.id IS NULL THEN 'unlinked' ELSE 'linked' END AS linked FROM ", 1,
    )
    with _connection(conn) as db:
        return _page(
            db, select, where, values, query, order="id",
            facets=("membership_state", "role", "linked"),
        )


def list_invitations(team_id, query=None, *, conn=None):
    query = query or {}
    where, values = _filter(
        query, "i", ("invitation_state", "membership_state", "execution_status", "stage"),
        scope=("i.team_id=%s",), values=(int(team_id),),
        search_fields=("i.email_snapshot", "i.id::text", "i.account_id::text", "a.email"),
    )
    if query.get("join_request_id") is not None:
        where += (
            f" AND EXISTS (SELECT 1 FROM {_table('team_join_request_items')} r "
            f"JOIN {_table('team_join_requests')} j ON j.id=r.request_id "
            "WHERE r.invitation_id=i.id AND j.team_id=i.team_id AND j.id=%s)"
        )
        values.append(int(query["join_request_id"]))
    with _connection(conn) as db:
        return _page(
            db, _account_select("team_invitations", "i", _INVITATION_COLUMNS),
            where, values, query, order="updated_at DESC,id DESC",
            facets=("invitation_state", "membership_state", "execution_status", "stage"),
        )


def get_invitation(team_id, invitation_id, *, conn=None):
    with _connection(conn) as db:
        rows = _rows(
            db, _account_select("team_invitations", "i", _INVITATION_COLUMNS) +
            " WHERE i.team_id=%s AND i.id=%s",
            (int(team_id), int(invitation_id)),
        )
        if not rows:
            return None
        row = rows[0]
        row.pop("_read_revision_key", None)
        return row


def get_account_states(team_id, account_ids, *, conn=None):
    """在一个集合查询中取得账号能力、全部本地归属与本 Team 执行。"""
    ids = _ids(account_ids)
    if not ids:
        return {}
    accounts = _table("registered_accounts")
    workspaces = _table("team_workspaces")
    members = _table("team_members")
    invitations = _table("team_invitations")
    owners = _table("team_account_ownership")
    invitation_columns = ",".join(
        "a.id AS account_id" if name == "account_id" else f"i.{name}"
        for name in _INVITATION_COLUMNS
    )
    unlinked_invitation_columns = ",".join(
        "u.account_id" if name == "account_id" else f"i.{name}"
        for name in _INVITATION_COLUMNS
    )
    statement = f"""
        WITH targets AS MATERIALIZED (
            SELECT a.id,a.email,a.archived,a.email_invalid,a.deactivated,a.account_status_text,
                   a.account_has_access_token AS has_access_token,
                   a.account_has_password AS has_password,a.account_totp_enabled AS totp_enabled,
                   {_normalized_email("a.email")} AS normalized_email
            FROM {accounts} a WHERE a.id=ANY(%s::bigint[])
        ), {_target_email_ctes()}, member_relations AS MATERIALIZED (
            SELECT a.id AS account_id,m.team_id FROM targets a
            JOIN {members} m ON m.account_id=a.id WHERE m.membership_state='joined'
            UNION ALL
            SELECT u.account_id,m.team_id FROM unique_accounts u
            JOIN {members} m ON m.account_id IS NULL
              AND {_normalized_email("m.email")}=u.normalized_email
            WHERE m.membership_state='joined'
        ), target_invitations AS MATERIALIZED (
            SELECT {invitation_columns} FROM targets a JOIN {invitations} i ON i.account_id=a.id
            UNION ALL
            SELECT {unlinked_invitation_columns} FROM unique_accounts u
            JOIN {invitations} i ON i.account_id IS NULL
              AND {_normalized_email("i.email_snapshot")}=u.normalized_email
        ), relations AS (
            SELECT o.account_id,o.team_id FROM {owners} o JOIN targets a ON a.id=o.account_id
            UNION
            SELECT w.manager_account_id,w.id FROM {workspaces} w JOIN targets a ON a.id=w.manager_account_id
            UNION
            SELECT account_id,team_id FROM member_relations
            UNION
            SELECT account_id,team_id FROM target_invitations i
            WHERE i.active OR i.seat_reserved OR i.invitation_state='pending' OR i.membership_state='joined'
        ), ownership AS (
            SELECT r.account_id,TRUE AS has_owner,
                   COALESCE(jsonb_agg(jsonb_build_object(
                       'id',w.id::text,'workspace_id',w.workspace_id,
                       'name',w.name,'display_name',w.display_name
                   ) ORDER BY w.id) FILTER (WHERE w.id<>%s),'[]'::jsonb) AS other_teams
            FROM relations r JOIN {workspaces} w ON w.id=r.team_id GROUP BY r.account_id
        ), joined AS (
            SELECT DISTINCT account_id FROM member_relations WHERE team_id=%s
        ), local_invitations AS MATERIALIZED (
            SELECT * FROM target_invitations WHERE team_id=%s
        ), latest AS (
            SELECT DISTINCT ON (account_id) * FROM local_invitations
            ORDER BY account_id,updated_at DESC,id DESC
        ), executing AS (
            SELECT DISTINCT ON (account_id) * FROM local_invitations
            WHERE active AND execution_status IN ({_ACTIVE_SQL})
            ORDER BY account_id,updated_at DESC,id DESC
        ), reservations AS (
            SELECT account_id,bool_or(seat_reserved) AS reservation_active,
              bool_or(seat_reserved OR invitation_state='pending' OR membership_state='joined') AS already_occupied
            FROM local_invitations GROUP BY account_id
        )
        SELECT a.id,a.email,a.archived,a.has_access_token,a.has_password,a.totp_enabled,
               CASE WHEN a.email_invalid THEN 'invalid' ELSE 'unmarked' END AS email_status,
               (a.deactivated OR a.account_status_text IN
                   ('deactivated','disabled','deleted','banned')) AS account_unavailable,
               CASE WHEN a.has_access_token OR a.has_password THEN 'available'
                    WHEN a.email_invalid THEN 'missing' ELSE 'unknown' END AS auth_capability,
               COALESCE(o.other_teams,'[]'::jsonb) AS other_teams,
               j.account_id IS NOT NULL AS already_member,
               CASE WHEN e.id IS NOT NULL THEN to_jsonb(e) ELSE NULL END AS active_invitation,
               CASE WHEN i.id IS NOT NULL THEN to_jsonb(i) ELSE NULL END AS invitation,
               COALESCE(s.reservation_active,FALSE) AS reservation_active,
               COALESCE(s.already_occupied,FALSE) AS already_occupied,
               COALESCE(o.has_owner,FALSE) AS has_owner
        FROM targets a LEFT JOIN ownership o ON o.account_id=a.id
        LEFT JOIN joined j ON j.account_id=a.id LEFT JOIN latest i ON i.account_id=a.id
        LEFT JOIN executing e ON e.account_id=a.id LEFT JOIN reservations s ON s.account_id=a.id
    """
    with _connection(conn) as db:
        rows = _rows(db, statement, (ids, int(team_id), int(team_id), int(team_id)))
        return {row["id"]: row for row in rows}


def get_account_memberships(account_ids, *, conn=None):
    """为普通账号读取补充已确认关系；旧部署尚无 Team 表时返回空映射。"""
    ids = _ids(account_ids)
    if not ids:
        return {}
    members, teams = _table("team_members"), _table("team_workspaces")
    with _connection(conn) as db:
        available = _rows(
            db, "SELECT to_regclass(%s) IS NOT NULL AND to_regclass(%s) IS NOT NULL AS ready",
            (members, teams),
        )[0]["ready"]
        if not available:
            return {}
        rows = _rows(
            db, f"""
                WITH targets AS MATERIALIZED (
                    SELECT a.id,{_normalized_email("a.email")} AS normalized_email
                    FROM {_table("registered_accounts")} a WHERE a.id=ANY(%s::bigint[])
                ), {_target_email_ctes()}, resolved_members AS (
                    SELECT a.id AS resolved_account_id,m.id,m.team_id,m.role,m.membership_state,m.last_verified_at
                    FROM targets a
                    JOIN {members} m ON m.account_id=a.id WHERE m.membership_state='joined'
                    UNION ALL
                    SELECT u.account_id AS resolved_account_id,m.id,m.team_id,m.role,m.membership_state,m.last_verified_at
                    FROM unique_accounts u
                    JOIN {members} m ON m.account_id IS NULL
                      AND {_normalized_email("m.email")}=u.normalized_email
                    WHERE m.membership_state='joined'
                )
                SELECT DISTINCT ON (m.resolved_account_id,m.team_id)
                       m.resolved_account_id AS account_id,m.team_id::text AS team_id,w.workspace_id,w.name,w.display_name,
                       m.role,m.membership_state,m.last_verified_at
                FROM resolved_members m JOIN {teams} w ON w.id=m.team_id
                ORDER BY m.resolved_account_id,m.team_id,m.last_verified_at DESC NULLS LAST,m.id DESC
            """, (ids,),
        )
        result = {}
        for row in rows:
            account_id = row.pop("account_id")
            stamp = row.get("last_verified_at")
            if isinstance(stamp, datetime):
                row["last_verified_at"] = stamp.isoformat()
            result.setdefault(account_id, []).append(row)
        return result
