# -*- coding: utf-8 -*-
"""批量管理增量结构；不迁移或改写注册执行事实。"""

from __future__ import annotations

import re
import threading
from core.storage.operations import store

_LOCK = threading.RLock()
_READY_KEY = ""
_DDL = r"""
CREATE TABLE IF NOT EXISTS operation_selections (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  selection_kind TEXT NOT NULL CHECK (selection_kind IN ('account_query','explicit_ids','batch_targets','retry_members')),
  request_key TEXT NOT NULL UNIQUE,
  request_hash TEXT NOT NULL,
  query_version INTEGER NOT NULL CHECK (query_version > 0),
  query_spec JSONB NOT NULL CHECK (jsonb_typeof(query_spec)='object'),
  action_key TEXT NOT NULL,
  action_version INTEGER NOT NULL CHECK (action_version > 0),
  selection_revision BIGINT NOT NULL DEFAULT 0,
  parameters JSONB NOT NULL DEFAULT '{}', parameters_hash TEXT NOT NULL,
  config_revision TEXT NOT NULL, config_snapshot JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL CHECK (status IN ('preparing','ready','failed','expired','consumed')),
  total_count BIGINT CHECK (total_count >= 0),
  selected_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_by_batch_id BIGINT REFERENCES operation_batches(id) ON DELETE RESTRICT,
  consumed_by_round_id BIGINT,
  basis_batch_id BIGINT REFERENCES operation_batches(id) ON DELETE RESTRICT,
  observed_summary_revision BIGINT, basis_summary_revision BIGINT,
  counts_changed_since_request BOOLEAN NOT NULL DEFAULT FALSE,
  owner_id TEXT, lease_until TIMESTAMPTZ, fence BIGINT NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  error_code TEXT, error_detail JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status NOT IN ('ready','consumed') OR (selected_at IS NOT NULL AND total_count IS NOT NULL)),
  CHECK (NOT (consumed_by_batch_id IS NOT NULL AND consumed_by_round_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS operation_selection_targets (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  selection_id BIGINT NOT NULL REFERENCES operation_selections(id) ON DELETE RESTRICT,
  target_kind TEXT NOT NULL CHECK (target_kind IN ('account','credential')),
  target_id BIGINT NOT NULL, ordinal BIGINT NOT NULL CHECK (ordinal > 0),
  canonical_target_id BIGINT REFERENCES operation_selection_targets(id) ON DELETE RESTRICT,
  source_target_round_id BIGINT, source_run_id_snapshot BIGINT,
  display_snapshot JSONB NOT NULL DEFAULT '{}',
  match_evidence JSONB NOT NULL DEFAULT '{}', baseline JSONB NOT NULL DEFAULT '{}',
  latest_requested_round_id BIGINT,
  current_contribution JSONB NOT NULL DEFAULT '{"pending_submit":1}',
  current_projection_revision BIGINT NOT NULL DEFAULT 0,
  UNIQUE(selection_id,target_kind,target_id), UNIQUE(selection_id,ordinal)
);

CREATE TABLE IF NOT EXISTS operation_batch_controls (
  batch_id BIGINT PRIMARY KEY REFERENCES operation_batches(id) ON DELETE RESTRICT,
  manager_version INTEGER NOT NULL CHECK (manager_version=1),
  selection_id BIGINT NOT NULL UNIQUE REFERENCES operation_selections(id) ON DELETE RESTRICT,
  initial_round_id BIGINT,
  action_key TEXT NOT NULL, action_version INTEGER NOT NULL,
  result_version INTEGER NOT NULL, parameters JSONB NOT NULL, config_snapshot JSONB NOT NULL,
  config_revision TEXT NOT NULL,
  request_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('active','cancel_requested','stop_requested','ended')),
  is_paused BOOLEAN NOT NULL DEFAULT FALSE,
  control_revision BIGINT NOT NULL DEFAULT 1,
  summary_revision BIGINT NOT NULL DEFAULT 0,
  next_round_no BIGINT NOT NULL DEFAULT 2,
  desired_workers INTEGER NOT NULL CHECK (desired_workers > 0),
  counts JSONB NOT NULL, metrics JSONB NOT NULL DEFAULT '{}',
  projected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_expand_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at TIMESTAMPTZ, purge_started_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS operation_batch_rounds (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES operation_batch_controls(batch_id) ON DELETE RESTRICT,
  round_no BIGINT NOT NULL CHECK (round_no > 0),
  request_kind TEXT NOT NULL CHECK (request_kind IN ('initial','manual_retry')),
  request_key TEXT NOT NULL, request_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('preparing','active','settling','completed','failed')),
  member_selection_id BIGINT REFERENCES operation_selections(id) ON DELETE RESTRICT,
  target_count BIGINT CHECK (target_count >= 0),
  materialized_count BIGINT NOT NULL DEFAULT 0 CHECK (materialized_count >= 0),
  materialization_cursor BIGINT NOT NULL DEFAULT 0,
  unmaterialized_bucket TEXT NOT NULL DEFAULT 'pending_submit'
    CHECK (unmaterialized_bucket IN ('pending_submit','cancelled')),
  control_revision BIGINT NOT NULL DEFAULT 1,
  control_action TEXT NOT NULL DEFAULT 'none' CHECK (control_action IN ('none','cancel_not_started','request_stop')),
  control_command_id BIGINT,
  counts JSONB NOT NULL DEFAULT '{}', metrics JSONB NOT NULL DEFAULT '{}',
  summary_revision BIGINT NOT NULL DEFAULT 0,
  owner_id TEXT, lease_until TIMESTAMPTZ, fence BIGINT NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completion_reason TEXT, preparation_error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), frozen_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  UNIQUE(batch_id,round_no), UNIQUE(batch_id,request_key),
  CHECK (target_count IS NULL OR materialized_count <= target_count)
);

CREATE TABLE IF NOT EXISTS operation_batch_target_rounds (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES operation_batch_controls(batch_id) ON DELETE RESTRICT,
  round_id BIGINT NOT NULL REFERENCES operation_batch_rounds(id) ON DELETE RESTRICT,
  member_target_id BIGINT NOT NULL REFERENCES operation_selection_targets(id) ON DELETE RESTRICT,
  canonical_target_id BIGINT NOT NULL REFERENCES operation_selection_targets(id) ON DELETE RESTRICT,
  ordinal BIGINT NOT NULL,
  admission_state TEXT NOT NULL CHECK (admission_state IN
    ('pending_submit','waiting_account','submitted','not_executed','cancelled')),
  chain_state TEXT NOT NULL DEFAULT 'not_started'
    CHECK (chain_state IN ('not_started','started','waiting','closed')),
  chain_started_at TIMESTAMPTZ, chain_closed_at TIMESTAMPTZ,
  source_revision BIGINT NOT NULL DEFAULT 0,
  applied_revision BIGINT NOT NULL DEFAULT 0,
  owner_id TEXT, lease_until TIMESTAMPTZ, fence BIGINT NOT NULL DEFAULT 0,
  next_prepare_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  prepare_attempts INTEGER NOT NULL DEFAULT 0,
  blocker_task_id_snapshot BIGINT, blocker_run_id_snapshot BIGINT,
  retry_from_target_round_id BIGINT REFERENCES operation_batch_target_rounds(id) ON DELETE RESTRICT,
  outcome TEXT NOT NULL DEFAULT 'pending_submit',
  result_version INTEGER NOT NULL, result JSONB NOT NULL DEFAULT '{}',
  applied_contribution JSONB NOT NULL DEFAULT '{"pending_submit":1}',
  reason_code TEXT, projected_at TIMESTAMPTZ,
  next_execution_generation BIGINT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(round_id,canonical_target_id), UNIQUE(round_id,ordinal), UNIQUE(member_target_id,round_id),
  CHECK (applied_revision <= source_revision)
);

CREATE TABLE IF NOT EXISTS operation_batch_run_links (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  target_round_id BIGINT NOT NULL REFERENCES operation_batch_target_rounds(id) ON DELETE RESTRICT,
  task_id BIGINT REFERENCES operation_tasks(id) ON DELETE SET NULL,
  run_id BIGINT REFERENCES operation_runs(id) ON DELETE SET NULL,
  task_id_snapshot BIGINT NOT NULL, run_id_snapshot BIGINT NOT NULL,
  step_key TEXT NOT NULL, execution_generation BIGINT NOT NULL,
  relation TEXT NOT NULL CHECK (relation IN ('owned_root','owned_child','owned_continuation','external_blocker')),
  archive_state TEXT NOT NULL DEFAULT 'live' CHECK (archive_state IN ('live','pending','archived')),
  result_archive_ref TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(target_round_id,run_id_snapshot,relation)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_bulk_owned_run ON operation_batch_run_links(run_id_snapshot)
  WHERE relation IN ('owned_root','owned_child','owned_continuation');

CREATE UNIQUE INDEX IF NOT EXISTS uq_bulk_owned_generation ON operation_batch_run_links(target_round_id,step_key,execution_generation)
  WHERE relation IN ('owned_root','owned_child','owned_continuation');

CREATE TABLE IF NOT EXISTS operation_projection_outbox (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_key TEXT NOT NULL UNIQUE,
  consumer_kind TEXT NOT NULL CHECK (consumer_kind IN ('bulk_target','task_read_model')),
  target_round_id BIGINT REFERENCES operation_batch_target_rounds(id) ON DELETE RESTRICT,
  task_id BIGINT REFERENCES operation_tasks(id) ON DELETE SET NULL,
  task_id_snapshot BIGINT,
  source_kind TEXT NOT NULL, source_id BIGINT NOT NULL, source_revision BIGINT NOT NULL,
  event_kind TEXT NOT NULL,
  available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  attempts INTEGER NOT NULL DEFAULT 0, error_code TEXT,
  processed_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((consumer_kind='bulk_target' AND target_round_id IS NOT NULL)
    OR (consumer_kind='task_read_model' AND task_id_snapshot IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS operation_batch_control_commands (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES operation_batch_controls(batch_id) ON DELETE RESTRICT,
  request_key TEXT NOT NULL, request_hash TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('cancel_not_started','request_stop','pause','resume')),
  scope_kind TEXT NOT NULL CHECK (scope_kind IN ('batch','round')),
  scope_round_id BIGINT REFERENCES operation_batch_rounds(id) ON DELETE RESTRICT,
  through_round_no BIGINT NOT NULL,
  expected_control_revision BIGINT NOT NULL, result_control_revision BIGINT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('accepted','settling','completed','failed')),
  next_round_id BIGINT, settlement_cursor BIGINT NOT NULL DEFAULT 0,
  owner_id TEXT, lease_until TIMESTAMPTZ, fence BIGINT NOT NULL DEFAULT 0,
  error_code TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ,
  UNIQUE(batch_id,request_key),
  CHECK ((scope_kind='round')=(scope_round_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_selection_prepare ON operation_selections(next_attempt_at,id) WHERE status='preparing';

CREATE INDEX IF NOT EXISTS idx_selection_expire ON operation_selections(expires_at,id) WHERE status IN ('ready','failed');

CREATE INDEX IF NOT EXISTS idx_selection_canonical ON operation_selection_targets(canonical_target_id,selection_id);

CREATE INDEX IF NOT EXISTS idx_round_prepare ON operation_batch_rounds(next_attempt_at,id) WHERE state IN ('preparing','active');

CREATE INDEX IF NOT EXISTS idx_target_prepare ON operation_batch_target_rounds(next_prepare_at,id)
  WHERE admission_state IN ('pending_submit','waiting_account') AND chain_state='not_started';

CREATE INDEX IF NOT EXISTS idx_target_page ON operation_batch_target_rounds(round_id,outcome,ordinal,id);

CREATE INDEX IF NOT EXISTS idx_target_current ON operation_batch_target_rounds(canonical_target_id,round_id DESC);

CREATE INDEX IF NOT EXISTS idx_target_unsettled ON operation_batch_target_rounds(round_id,id)
  WHERE chain_state<>'closed' OR source_revision<>applied_revision;

CREATE INDEX IF NOT EXISTS idx_run_link_run ON operation_batch_run_links(run_id) WHERE run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_projection_pending ON operation_projection_outbox(consumer_kind,available_at,id)
  WHERE processed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_control_settle ON operation_batch_control_commands(state,id)
  WHERE state IN ('accepted','settling');
"""


def reset_ready() -> None:
    global _READY_KEY
    _READY_KEY = ""


def init() -> None:
    global _READY_KEY
    store.init()
    key = store.postgres_store.database_url() + "::" + store._schema_name()
    with _LOCK:
        if _READY_KEY == key:
            return
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (key + ":bulk-schema",))
            ddl = re.sub(r"\b(operation_[a-z_]+)\b", lambda m: store._table(m.group(1)), _DDL)
            for statement in ddl.split(";"):
                if statement.strip():
                    cur.execute(statement)
            cur.execute(
                f"ALTER TABLE {store._table('operation_selections')} ADD COLUMN IF NOT EXISTS preflight_summary JSONB NOT NULL DEFAULT '{{}}'"
            )
            cur.execute(
                f"ALTER TABLE {store._table('operation_selections')} ADD COLUMN IF NOT EXISTS preflight_at TIMESTAMPTZ"
            )
            cur.execute(
                f"ALTER TABLE {store._table('operation_batch_controls')} ADD COLUMN IF NOT EXISTS last_expand_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            )
            cur.execute(
                f"ALTER TABLE {store._table('operation_batch_controls')} ADD COLUMN IF NOT EXISTS is_paused BOOLEAN NOT NULL DEFAULT FALSE"
            )
            command_table = store._table("operation_batch_control_commands")
            cur.execute(
                "SELECT 1 FROM pg_constraint WHERE conname=%s AND conrelid=%s::regclass",
                ("ck_bulk_control_command_action_v2", command_table),
            )
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE {command_table} DROP CONSTRAINT IF EXISTS operation_batch_control_commands_action_check")
                cur.execute(f"ALTER TABLE {command_table} ADD CONSTRAINT ck_bulk_control_command_action_v2 CHECK (action IN ('cancel_not_started','request_stop','pause','resume'))")
            cur.execute(
                f"ALTER TABLE {store._table('operation_batch_target_rounds')} ADD COLUMN IF NOT EXISTS prepare_attempts INTEGER NOT NULL DEFAULT 0"
            )
            for table, column, target in (
                ("operation_batch_controls", "initial_round_id", "operation_batch_rounds"),
                ("operation_selections", "consumed_by_round_id", "operation_batch_rounds"),
                ("operation_selection_targets", "latest_requested_round_id", "operation_batch_rounds"),
                ("operation_selection_targets", "source_target_round_id", "operation_batch_target_rounds"),
                ("operation_batch_rounds", "control_command_id", "operation_batch_control_commands"),
            ):
                name = "fk_bulk_" + column
                cur.execute(
                    "SELECT 1 FROM pg_constraint WHERE conname=%s AND conrelid=%s::regclass",
                    (name, store._table(table)),
                )
                if not cur.fetchone():
                    cur.execute(
                        f"ALTER TABLE {store._table(table)} ADD CONSTRAINT {store._quote(name)} FOREIGN KEY ({column}) REFERENCES {store._table(target)}(id) DEFERRABLE INITIALLY DEFERRED"
                    )
            for table, columns in {
                "operation_selections": ("parameters", "config_snapshot", "error_detail"),
                "operation_selection_targets": (
                    "display_snapshot",
                    "match_evidence",
                    "baseline",
                    "current_contribution",
                ),
                "operation_batch_controls": ("parameters", "config_snapshot", "counts", "metrics"),
                "operation_batch_rounds": ("counts", "metrics"),
                "operation_batch_target_rounds": ("result", "applied_contribution"),
            }.items():
                for column in columns:
                    name = "ck_bulk_" + table.removeprefix("operation_")[:22] + "_" + column
                    cur.execute(
                        "SELECT 1 FROM pg_constraint WHERE conname=%s AND conrelid=%s::regclass",
                        (name, store._table(table)),
                    )
                    if not cur.fetchone():
                        cur.execute(
                            f"ALTER TABLE {store._table(table)} ADD CONSTRAINT {store._quote(name)} CHECK(jsonb_typeof({column})='object')"
                        )
            _install_guards(cur)
            _install_relationships(cur)
            _install_frozen_target_guard(cur)
        _READY_KEY = key


def require_readable() -> None:
    """读取入口只核验结构，不用 GET 触发业务表迁移。"""
    key = store.postgres_store.database_url() + "::" + store._schema_name()
    if _READY_KEY == key:
        return
    with store._connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (store._table("operation_batch_controls"),))
        available = cur.fetchone()
    if not available or next(iter(available.values())) is None:
        from core.storage.operations.bulk_common import BulkError

        raise BulkError("bulk_schema_not_ready", "批量任务结构尚未准备完成，请等待服务初始化。", 503)


def _install_guards(cur) -> None:
    """保留批次的执行引用不能被旧任务清理路径物理删除。"""
    fn = store._table("bulk_protect_owned_delete")
    links = store._table("operation_batch_run_links")
    targets = store._table("operation_batch_target_rounds")
    controls = store._table("operation_batch_controls")
    cur.execute(f"""CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(SELECT 1 FROM {links} l JOIN {targets} t ON t.id=l.target_round_id
                JOIN {controls} c ON c.batch_id=t.batch_id
                WHERE (CASE WHEN TG_TABLE_NAME='operation_runs' THEN l.run_id ELSE l.task_id END)=OLD.id
                AND l.relation <> 'external_blocker' AND c.purge_started_at IS NULL) THEN
        RAISE EXCEPTION '批次仍保留执行资料，禁止物理删除' USING ERRCODE='23503';
      END IF;
      RETURN OLD;
    END $$""")
    for table in ("operation_tasks", "operation_runs"):
        name = "bulk_preserve_owned"
        cur.execute("SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s", (store._table(table), name))
        if not cur.fetchone():
            cur.execute(
                f"CREATE TRIGGER {name} BEFORE DELETE ON {store._table(table)} FOR EACH ROW EXECUTE FUNCTION {fn}()"
            )


def _install_relationships(cur) -> None:
    """数据库直接写入也不能把目标、轮次或执行绑定到另一批。"""
    fn = store._table("bulk_validate_relationship")
    rounds = store._table("operation_batch_rounds")
    members = store._table("operation_selection_targets")
    controls = store._table("operation_batch_controls")
    runs = store._table("operation_runs")
    cur.execute(f"""CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='operation_batch_target_rounds' THEN
        IF NOT EXISTS(SELECT 1 FROM {rounds} r JOIN {controls} c ON c.batch_id=r.batch_id
                      JOIN {members} m ON m.id=NEW.member_target_id
                      JOIN {members} root ON root.id=NEW.canonical_target_id
                      WHERE r.id=NEW.round_id AND r.batch_id=NEW.batch_id AND m.selection_id=r.member_selection_id
                        AND COALESCE(m.canonical_target_id,m.id)=root.id AND root.selection_id=c.selection_id) THEN
          RAISE EXCEPTION '批量目标、轮次和根名单归属不一致' USING ERRCODE='23514';
        END IF;
      ELSE
        IF NEW.run_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM {runs} r WHERE r.id=NEW.run_id
                 AND r.task_id=NEW.task_id AND r.id=NEW.run_id_snapshot AND r.task_id=NEW.task_id_snapshot) THEN
          RAISE EXCEPTION '批量执行与逻辑任务归属不一致' USING ERRCODE='23514';
        END IF;
      END IF;
      RETURN NEW;
    END $$""")
    for name in ("operation_batch_target_rounds", "operation_batch_run_links"):
        cur.execute(
            "SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s",
            (store._table(name), "bulk_validate_relationship"),
        )
        if not cur.fetchone():
            cur.execute(
                f"CREATE TRIGGER bulk_validate_relationship BEFORE INSERT OR UPDATE ON {store._table(name)} FOR EACH ROW EXECUTE FUNCTION {fn}()"
            )


def _install_frozen_target_guard(cur) -> None:
    """一次语句集合校验固定证据，避免预检批量更新逐行读取选择状态。"""
    fn = store._table("bulk_protect_frozen_target_statement")
    cur.execute(f"""CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF EXISTS(
        SELECT 1 FROM bulk_old_targets old_target
        LEFT JOIN bulk_new_targets new_target ON new_target.id=old_target.id
        JOIN {store._table("operation_selections")} selection ON selection.id=old_target.selection_id
        WHERE selection.status IN ('ready','consumed')
          AND (new_target.id IS NULL OR ROW(new_target.selection_id,new_target.target_kind,new_target.target_id,new_target.ordinal,new_target.canonical_target_id,
                  new_target.source_target_round_id,new_target.source_run_id_snapshot,new_target.display_snapshot,new_target.match_evidence,new_target.baseline)
              IS DISTINCT FROM
              ROW(old_target.selection_id,old_target.target_kind,old_target.target_id,old_target.ordinal,old_target.canonical_target_id,
                  old_target.source_target_round_id,old_target.source_run_id_snapshot,old_target.display_snapshot,old_target.match_evidence,old_target.baseline))
      ) THEN
        RAISE EXCEPTION '固定名单身份和证据不得改写' USING ERRCODE='23514';
      END IF;
      RETURN NULL;
    END $$""")
    relation = store._table("operation_selection_targets")
    # 同名旧BEFORE ROW触发器必须替换；仅IF NOT EXISTS会让部署仍运行旧N次查询。
    cur.execute("SELECT tgtype,tgoldtable,tgnewtable FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s",
                (relation,"bulk_frozen_target"))
    previous = cur.fetchone()
    if previous and (previous["tgtype"] != 16 or previous["tgoldtable"] != "bulk_old_targets" or previous["tgnewtable"] != "bulk_new_targets"):
        cur.execute(f"DROP TRIGGER bulk_frozen_target ON {relation}")
        previous = None
    if not previous:
        cur.execute(f"""CREATE TRIGGER bulk_frozen_target AFTER UPDATE ON {relation}
            REFERENCING OLD TABLE AS bulk_old_targets NEW TABLE AS bulk_new_targets
            FOR EACH STATEMENT EXECUTE FUNCTION {fn}()""")
