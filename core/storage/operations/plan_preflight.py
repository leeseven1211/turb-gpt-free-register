"""已批准的套餐预检存储策略：同语句资格快照与一次目标写入。"""
from __future__ import annotations

from core.bulk_operations import preflight_policy as policy
from core.storage import records
from core.storage.operations.bulk_common import table
from core.storage.operations import store


def extra_account_columns():
    return ",a.id AS existing_account_id,a.data->>'account_status' AS account_status,a.codex_status"


def _normalize(expression):
    # Unicode邮箱不近似转换，由unsupported gate选择原Python分页回调。
    return f"translate(btrim(COALESCE({expression},''),p.whitespace),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"


def freeze(cur, *, query, args, selection_id, basis_revision, settings, display, match, baseline):
    facts = {
        "missing": "c.existing_account_id IS NULL",
        "deactivated": " OR ".join(f"{_normalize('c.' + field)} COLLATE \"C\"='deactivated'"
                                   for field in ("account_status", "codex_status", "codex_credential_state")),
        "email_missing": "c.normalized_email COLLATE \"C\"=''",
        "run_busy": "r.blocker_run_id IS NOT NULL",
        "registration_busy": "ba.account_id IS NOT NULL OR be.email IS NOT NULL",
        "token_missing": "NOT COALESCE(c.account_has_access_token,false) AND NOT p.auto_refresh",
    }
    status, reason = policy.sql_result_cases(facts)
    cur.execute(f"""WITH candidates AS MATERIALIZED ({query}),
      policy_input AS MATERIALIZED (SELECT %s::text whitespace,%s::boolean auto_refresh,
        pg_get_serial_sequence(%s,'id')::regclass target_sequence),
      normalized AS MATERIALIZED (
        SELECT c.id,c.existing_account_id,c.account_status,c.codex_status,c.codex_credential_state,
          c.email,c.account_has_access_token,(ordinal-1)/5000 AS page, {_normalize('c.email')} normalized_email
        FROM candidates c CROSS JOIN policy_input p),
      active_jobs AS MATERIALIZED (
        SELECT j.id,j.account_id,j.email,LOWER(BTRIM(j.email)) selection_email,
          {_normalize('j.email')} normalized_email
        FROM {records._qualified(records.JOBS)} j CROSS JOIN policy_input p
        WHERE COALESCE(NULLIF(j.job_type,''),'registration')=ANY(%s) AND j.status=ANY(%s)),
      unsupported AS MATERIALIZED (
        SELECT 1 WHERE current_setting('server_encoding')<>'UTF8'
        UNION ALL SELECT 1 FROM normalized WHERE octet_length(normalized_email)<>char_length(normalized_email)
        UNION ALL SELECT 1 FROM active_jobs WHERE octet_length(normalized_email)<>char_length(normalized_email)),
      active AS (
        SELECT r.account_id,min(r.id) blocker_run_id FROM {table('operation_runs')} r
        JOIN normalized c ON c.id=r.account_id WHERE r.status=ANY(%s) GROUP BY r.account_id),
      picked_job_ids AS (
        SELECT c.page,j.id FROM normalized c JOIN active_jobs j ON j.account_id=c.id
        UNION SELECT c.page,j.id FROM normalized c JOIN active_jobs j ON j.selection_email=c.normalized_email
          WHERE c.existing_account_id IS NOT NULL AND COALESCE(c.email,'')<>''),
      picked_jobs AS MATERIALIZED (
        SELECT picked.page,j.account_id,j.normalized_email AS email
        FROM picked_job_ids picked JOIN active_jobs j ON j.id=picked.id),
      busy_accounts AS (SELECT DISTINCT page,account_id FROM picked_jobs WHERE account_id IS NOT NULL),
      busy_emails AS (SELECT DISTINCT page,email COLLATE "C" AS email FROM picked_jobs),
      qualified AS MATERIALIZED (
        SELECT c.id, {status} preflight_status, {reason} preflight_reason, r.blocker_run_id
        FROM normalized c CROSS JOIN policy_input p
        LEFT JOIN active r ON r.account_id=c.id
        LEFT JOIN busy_accounts ba ON ba.page=c.page AND ba.account_id=c.id
        LEFT JOIN busy_emails be ON be.page=c.page AND be.email=c.normalized_email COLLATE "C"
        WHERE NOT EXISTS(SELECT 1 FROM unsupported)),
      identified AS MATERIALIZED (
        SELECT q.*,nextval(p.target_sequence) AS receipt_id FROM qualified q CROSS JOIN policy_input p),
      inserted AS (
        INSERT INTO {table('operation_selection_targets')}
          (id,selection_id,target_kind,target_id,ordinal,display_snapshot,match_evidence,baseline)
        OVERRIDING SYSTEM VALUE
        SELECT receipt_id,%s,'account',id,ordinal,{display},
          ({match}) || jsonb_build_object('preflight',jsonb_build_object(
            'target_id',receipt_id,'status',preflight_status,'reason_code',preflight_reason,
            'checked_at',statement_timestamp(),
            'blocker_run_id',CASE WHEN preflight_reason='account_busy' THEN blocker_run_id ELSE NULL END)),
          {baseline} FROM identified JOIN candidates USING(id)
        RETURNING match_evidence->'preflight'->>'status' AS status),
      totals AS (
        SELECT count(*) total_count,jsonb_build_object(
          'ready',count(*) FILTER(WHERE status='ready'),
          'waiting_account',count(*) FILTER(WHERE status='waiting_account'),
          'not_executable',count(*) FILTER(WHERE status='not_executable')) summary FROM inserted)
      UPDATE {table('operation_selections')} s SET total_count=totals.total_count,
        preflight_summary=totals.summary,preflight_at=statement_timestamp(),
        selected_at=statement_timestamp(),selection_revision=1,status='preparing',owner_id=NULL,lease_until=NULL,
        basis_summary_revision=%s,updated_at=now()
      FROM totals WHERE s.id=%s AND NOT EXISTS(SELECT 1 FROM unsupported) RETURNING s.*""",
                (*args, policy.PYTHON_WHITESPACE, bool(settings.get('auto_refresh_at_enabled', True)),
                 table('operation_selection_targets'),
                 list(policy.REGISTRATION_TYPES), list(policy.REGISTRATION_STATUSES), list(store._ACTIVE_RUN_STATUSES),
                 selection_id, basis_revision, selection_id))
    result = cur.fetchone()
    # No target/selection writes occur on unsupported input; caller retains locks
    # and runs the original callback transaction instead of mixing snapshots.
    return dict(result) if result else None


def fallback_receipts(targets, conn, *, settings):
    return policy.plan_check_receipts(
        targets, settings=settings, conn=conn, account_table=records._qualified(records.ACCOUNTS),
        run_table=table('operation_runs'), job_table=records._qualified(records.JOBS),
        active_statuses=store._ACTIVE_RUN_STATUSES)
