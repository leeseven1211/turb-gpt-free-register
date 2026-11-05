# -*- coding: utf-8 -*-
"""业务执行分类、共享许可上下文及 PostgreSQL 准入门面。"""
from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.storage.operations import permits
from core.storage import postgres

logger = logging.getLogger(__name__)


class ConcurrencyPolicyError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


class ConcurrencyStoreUnavailable(RuntimeError):
    code = "scheduler_store_unavailable"


@dataclass(frozen=True)
class AdmissionClass:
    key: str
    label: str
    config_key: str
    default_limit: int = 3
    control: bool = False
    unit: str = "独立执行单元"


_DEFINITIONS = (
    ("registration_roxy", "Roxy 注册", "REGISTRATION_ROXY_WORKERS", 3),
    ("registration_proto2", "Proto2 注册", "REGISTRATION_PROTO2_WORKERS", 3),
    ("live_check", "查活", "ACCOUNT_LIVE_CHECK_WORKERS", 3),
    ("token_refresh", "刷新 AT", "ACCOUNT_TOKEN_REFRESH_WORKERS", 3),
    ("plan_check", "查套餐", "ACCOUNT_PLAN_CHECK_WORKERS", 3),
    ("deactivation_mail", "查封号邮件", "ACCOUNT_DEACTIVATION_MAIL_WORKERS", 3),
    ("password_setup", "补密码", "ACCOUNT_PASSWORD_SETUP_WORKERS", 3),
    ("password_change", "改密码", "ACCOUNT_PASSWORD_CHANGE_WORKERS", 3),
    ("twofa_setup", "补 2FA", "ACCOUNT_TWOFA_SETUP_WORKERS", 3),
    ("twofa_change", "改 2FA", "ACCOUNT_TWOFA_CHANGE_WORKERS", 3),
    ("account_setup_retry", "多步骤账号配置", "ACCOUNT_SETUP_WORKERS", 3),
    ("email_change", "换绑邮箱", "ACCOUNT_EMAIL_CHANGE_WORKERS", 3),
    ("account_inspection", "一键巡检", "ACCOUNT_INSPECTION_WORKERS", 3),
    ("codex_retry", "Codex 授权", "CODEX_OAUTH_WORKERS", 3),
    ("codex_token_refresh", "刷新 Codex Token", "CODEX_TOKEN_REFRESH_WORKERS", 3),
    ("sub2api_sync", "Sub2API 上传与同步", "SUB2API_SYNC_WORKERS", 3),
    ("extract_link", "提链", "EXTRACT_LINK_WORKERS", 3),
    ("email_import", "邮箱导入", "EMAIL_IMPORT_WORKERS", 1),
    ("sub2api_scan", "Sub2API 异常扫描", "SUB2API_SCAN_WORKERS", 1),
    ("maintenance_check", "手动维护检查", "MAINTENANCE_CHECK_WORKERS", 1),
)
POLICIES = {row[0]: AdmissionClass(*row) for row in _DEFINITIONS}
# 旧补全 handler 仍包含真实业务，必须按多步骤账号配置计数。
_ALIASES = {"twofa_retry": "account_setup_retry", "account_completion": "account_setup_retry",
            "sub2api_manual_upload": "sub2api_sync", "sentinel_maintenance_check": "maintenance_check"}
_PROVIDER_KEYS = {"legacy": "EXTRACT_LINK_LEGACY_CONCURRENCY", "lumen_flow": "EXTRACT_LINK_LUMEN_FLOW_CONCURRENCY",
                  "huanguang": "EXTRACT_LINK_HUANGUANG_CONCURRENCY", "anguang": "EXTRACT_LINK_ANGUANG_CONCURRENCY"}


def resolve_admission_class(run: Mapping[str, Any] | str) -> AdmissionClass:
    name = str(run if isinstance(run, str) else run.get("task_type") or "").strip()
    if name in {"registration", "registration_resume"}:
        data = run.get("data") or {} if isinstance(run, Mapping) else {}
        driver = str(data.get("registration_driver") or data.get("driver") or "roxy")
        name = "registration_proto2" if driver == "protocol_oss_2" else "registration_roxy" if driver == "roxy" else f"registration_{driver}"
    name = _ALIASES.get(name, name)
    if name not in POLICIES:
        raise ConcurrencyPolicyError("concurrency_policy_missing", f"任务类型没有并发策略：{name}")
    return POLICIES[name]


def register_admission_alias(task_type: str, canonical_type: str) -> None:
    """适配器必须显式声明计量归属，不能由未登记类型自行选择免槽。"""
    name = str(task_type or "").strip()
    spec = resolve_admission_class(str(canonical_type))
    if not name or name in POLICIES:
        raise ConcurrencyPolicyError("concurrency_policy_invalid", "规范类型不能被别名覆盖")
    if name in _ALIASES and _ALIASES[name] != spec.key:
        raise ConcurrencyPolicyError("concurrency_policy_invalid", "同一任务类型不能改变并发归属")
    _ALIASES[name] = spec.key


def order_dispatch_candidates(runs: list[dict]) -> list[dict]:
    """共享游标首先选择下一类型，防止本地只提交一项时从未看见其他类型。"""
    cursor = permits.dispatch_cursor()
    last_type = str(cursor["task_type"] or "")

    def rank(run):
        spec = resolve_admission_class(run)
        batch = str(run.get("batch_key") or (f"operation:{run['batch_id']}" if run.get("batch_id") else ""))
        last_batch = str((cursor.get("batches") or {}).get(spec.key) or "")
        return (spec.key <= last_type, spec.key, batch <= last_batch, batch,
                int(run.get("dispatch_position") or 0))

    return sorted(runs, key=rank)


@dataclass
class ExecutionContext:
    permit_id: str
    execution_id: str
    execution_key: str
    task_type: str
    claimed_run: dict[str, Any]
    policy_revision: int = 0
    released: bool = False
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    domain_schema: str = field(default_factory=postgres.schema_name)
    _domain_url: str = field(default_factory=postgres.database_url, repr=False)


@dataclass(frozen=True)
class AdmissionResult:
    context: ExecutionContext | None = None
    blocked_by: tuple[str, ...] = ()

    @property
    def admitted(self) -> bool:
        return self.context is not None

    def __bool__(self) -> bool:
        return self.admitted


_CURRENT: ContextVar[ExecutionContext | None] = ContextVar("business_execution_permit", default=None)
_RELEASE_PENDING: dict[tuple[str, str], tuple[ExecutionContext, str]] = {}
_RELEASE_LOCK = threading.Lock()
_RELEASE_RETRY_THREAD: threading.Thread | None = None


def current_execution() -> ExecutionContext | None:
    return _CURRENT.get()


def _policy(conn) -> tuple[dict[str, int], int, bool]:
    from config.concurrency import policy_values
    from core.storage import runtime_config

    raw = runtime_config.read_values(conn=conn)
    try:
        values = policy_values(raw if raw is not None else {})
    except (TypeError, ValueError) as exc:
        raise ConcurrencyPolicyError("concurrency_policy_invalid", str(exc)) from exc
    return values, runtime_config.current_revision(conn=conn), raw is not None and "CONCURRENCY_POLICY_REVISION" not in raw


def try_admit_and_claim(*, execution_key: str, task_type: str,
                        claim: Callable[[Any, str], Mapping | None], execution_id: str | None = None,
                        batch_key: str | None = None, batch_limit: int | None = None,
                        provider_key: str | None = None, provider_limit: int | None = None,
                        run_id: int | None = None, metadata: Mapping | None = None,
                        extra_scopes: list[dict] | None = None) -> AdmissionResult:
    classification = resolve_admission_class(task_type)
    execution_id = str(execution_id or uuid.uuid4().hex)
    if not execution_key or not callable(claim):
        raise ConcurrencyPolicyError("concurrency_policy_invalid", "准入缺少稳定执行身份或原子认领函数")
    owner = permits.current_owner()

    def policy(conn):
        values, revision, migration_required = _policy(conn)
        scopes = [{"kind": "global", "key": "deployment", "limit": values["GLOBAL_TASK_WORKERS"]},
                  {"kind": "type", "key": classification.key, "limit": values[classification.config_key]}]
        if batch_key is not None and batch_limit is not None:
            scopes.append({"kind": "batch", "key": str(batch_key), "limit": int(batch_limit)})
        if provider_key is not None:
            from core.storage import runtime_config
            raw = runtime_config.read_values(conn=conn) or {}
            limit = int(raw.get(_PROVIDER_KEYS.get(str(provider_key), ""), provider_limit or 1))
            scopes.append({"kind": "provider", "key": str(provider_key), "limit": limit})
        scopes.extend(dict(scope) for scope in (extra_scopes or []))
        if any(isinstance(scope["limit"], bool) or int(scope["limit"]) < 1 for scope in scopes):
            raise ConcurrencyPolicyError("concurrency_policy_invalid", "并发上限必须是正整数")
        return scopes, revision, ["concurrency_policy_migration_required"] if migration_required else []

    try:
        result = permits.try_admit(execution_key=str(execution_key), task_type=classification.key,
                                  execution_id=execution_id, run_id=run_id, batch_key=str(batch_key or ""),
                                  owner=owner, metadata=dict(metadata or {}), policy=policy, claim=claim)
    except ConcurrencyPolicyError:
        raise
    except Exception as exc:
        raise ConcurrencyStoreUnavailable("并发存储不可用，暂停新准入") from exc
    if not result.get("permit_id"):
        return AdmissionResult(blocked_by=tuple(result.get("blocked_by") or ()))
    return AdmissionResult(ExecutionContext(result["permit_id"], execution_id, str(execution_key), classification.key,
                                           result["claimed_run"], int(result["policy_revision"])))


def heartbeat_permit(permit_id: str, execution_id: str, *, state: str | None = None,
                     schema: str | None = None, database_url: str | None = None) -> bool:
    if state is not None and state not in {"reserved", "executing", "cleaning", "debug_hold"}:
        raise ConcurrencyPolicyError("concurrency_policy_invalid", "无效执行许可状态")
    return permits.heartbeat(permit_id, execution_id, state=state, schema=schema, database_url=database_url)


def set_execution_state(context: ExecutionContext, state: str) -> bool:
    return heartbeat_permit(context.permit_id, context.execution_id, state=state,
                            schema=context.domain_schema, database_url=context._domain_url)


def release_permit(permit_id: str, execution_id: str, reason: str = "worker_exit", *,
                   schema: str | None = None, database_url: str | None = None) -> bool:
    return permits.release(permit_id, execution_id, reason=reason, schema=schema, database_url=database_url)


def release_execution(context: ExecutionContext, *, reason: str = "worker_exit") -> bool:
    global _RELEASE_RETRY_THREAD
    if context.released:
        return False
    permits.mark_execution_exited(context.permit_id, context.execution_id)
    context._stop.set()
    try:
        result = release_permit(context.permit_id, context.execution_id, reason,
                                schema=context.domain_schema, database_url=context._domain_url)
        context.released = True
        permits.clear_execution_exit(context.permit_id, context.execution_id)
        with _RELEASE_LOCK:
            _RELEASE_PENDING.pop((context.permit_id, context.execution_id), None)
        return result
    except Exception:
        logger.exception("执行已退出，许可释放暂不可用，保留占用并重试：permit_id=%s", context.permit_id)
        with _RELEASE_LOCK:
            _RELEASE_PENDING[(context.permit_id, context.execution_id)] = (context, reason)
            if _RELEASE_RETRY_THREAD is None or not _RELEASE_RETRY_THREAD.is_alive():
                _RELEASE_RETRY_THREAD = threading.Thread(target=_retry_releases, name="execution-permit-release", daemon=True)
                _RELEASE_RETRY_THREAD.start()
        return False


def _retry_releases() -> None:
    global _RELEASE_RETRY_THREAD
    while True:
        threading.Event().wait(1)
        with _RELEASE_LOCK:
            pending = list(_RELEASE_PENDING.values())
            if not pending:
                _RELEASE_RETRY_THREAD = None
                return
        for context, reason in pending:
            release_execution(context, reason=reason)


@contextmanager
def execution_scope(context: ExecutionContext):
    """同步内部步骤继承当前许可，心跳只证明所有者存活，不触发业务重跑。"""
    if not validate_execution(context):
        raise ConcurrencyPolicyError("permit_owner_lost", "当前执行许可已失效")
    existing = current_execution()
    if existing is not None:
        if existing.permit_id != context.permit_id or existing.execution_id != context.execution_id:
            raise ConcurrencyPolicyError("concurrency_policy_invalid", "禁止在已有许可下嵌套另一个执行许可")
        yield context
        return
    if not permits.heartbeat(context.permit_id, context.execution_id, state="executing", thread_id=threading.get_ident(),
                             schema=context.domain_schema, database_url=context._domain_url):
        raise ConcurrencyPolicyError("permit_owner_lost", "当前执行许可已失效")
    token = _CURRENT.set(context)
    stop = threading.Event()

    def renew():
        while not stop.wait(10):
            try:
                if not heartbeat_permit(context.permit_id, context.execution_id,
                                        schema=context.domain_schema, database_url=context._domain_url):
                    logger.error("执行许可归属已变化：permit_id=%s", context.permit_id)
                    return
            except Exception:
                logger.exception("执行许可心跳暂不可用，保留占用并停止新准入")

    thread = threading.Thread(target=renew, name=f"execution-permit-{context.permit_id[:8]}", daemon=True)
    thread.start()
    try:
        yield context
    finally:
        stop.set()
        thread.join(timeout=1)
        _CURRENT.reset(token)


active_execution_keys = permits.active_execution_keys
active_execution_ids = permits.active_execution_ids
recover_execution_permits = permits.recover_execution_permits
owner_liveness = permits.owner_liveness
admission_lock = permits.admission_lock
admission_transaction = permits.admission_transaction


def validate_execution(context: ExecutionContext) -> bool:
    return not context.released and permits.validate(context.permit_id, context.execution_id,
                                                     schema=context.domain_schema, database_url=context._domain_url)


def has_active_execution(execution_key: str, *, conn=None) -> bool:
    return str(execution_key) in active_execution_keys(conn=conn)


def get_concurrency_status(*, include_details: bool = False) -> dict[str, Any]:
    from core.storage import postgres

    try:
        permits.ensure_tables()
        with postgres.connect() as conn:
            values, revision, migration_required = _policy(conn)
        active, scopes, requests = permits.status_rows()
        queued_by_type, unknown_types, scheduled = _queued_counts()
    except ConcurrencyPolicyError:
        raise
    except Exception as exc:
        raise ConcurrencyStoreUnavailable("并发状态存储不可用") from exc
    states = {name: sum(row["state"] == name for row in active) for name in ("reserved", "executing", "cleaning", "debug_hold")}
    global_status = {"limit": values["GLOBAL_TASK_WORKERS"], "occupied": len(active), **states,
                     "draining": len(active) > values["GLOBAL_TASK_WORKERS"]}
    types = []
    for spec in POLICIES.values():
        queued = [row for row in requests if row["task_type"] == spec.key]
        types.append({"key": spec.key, "label": spec.label, "config_key": spec.config_key,
                      "limit": values[spec.config_key], "occupied": sum(row["task_type"] == spec.key for row in active),
                      "draining": sum(row["task_type"] == spec.key for row in active) > values[spec.config_key],
                      "queued": queued_by_type.get(spec.key, {}).get("queued", 0),
                      "oldest_ready_at": queued_by_type.get(spec.key, {}).get("oldest_ready_at"),
                      "task_types": [spec.key, *[alias for alias, canonical in _ALIASES.items() if canonical == spec.key]],
                      "blocked_by": list(dict.fromkeys(code for row in queued for code in row["blocked_by"]))})
    result = {"scope": postgres.schema_name(), "policy_revision": revision,
              "observed_at": datetime.now(timezone.utc).isoformat(), "global": global_status,
              "types": types, "migration_required": migration_required,
              "unknown_types": unknown_types, "scheduled": scheduled,
              "providers": [], "batches": [], "remote_orders": []}
    try:
        for kind, target in (("provider", "providers"), ("batch", "batches")):
            keys = sorted({row["scope_key"] for row in scopes if row["scope_kind"] == kind})
            result[target] = [{"key": key, "occupied": sum(row["units"] for row in scopes if row["scope_kind"] == kind and row["scope_key"] == key),
                               "limit": _additional_scope_limit(kind, key, requests, scopes)} for key in keys[:100]]
        result["remote_orders"], result["remote_waiting"] = _remote_order_status()
    except Exception as exc:
        raise ConcurrencyStoreUnavailable("业务附加容量状态暂不可用") from exc
    result["queued"] = sum(row["queued"] for row in types)
    if include_details:
        result["executions"] = [{key: row.get(key) for key in ("permit_id", "execution_key", "run_id", "task_type", "state", "verification_state", "acquired_at")} for row in active]
    return result


status_snapshot = get_concurrency_status


def _additional_scope_limit(kind, key, requests, scopes):
    from core.storage import postgres, runtime_config
    from core.storage.operations import store

    with postgres.connect() as conn:
        if kind == "provider":
            raw = runtime_config.read_values(conn=conn) or {}
            return int(raw.get(_PROVIDER_KEYS.get(key, ""), 1))
        if kind == "batch" and key.startswith("operation:"):
            with conn.cursor() as cur:
                cur.execute(f"SELECT data->>'workers' FROM {store._table('operation_batches')} WHERE id=%s", (int(key.split(":", 1)[1]),))
                row = cur.fetchone()
                return int(row[0]) if row and row[0] else None
    for request in requests:
        for scope in request["scopes"]:
            if scope["kind"] == kind and scope["key"] == key:
                return int(scope["limit"])
    for scope in scopes:
        if scope["scope_kind"] == kind and scope["scope_key"] == key and scope.get("limit_snapshot"):
            return int(scope["limit_snapshot"])
    return None


def _remote_order_status():
    from core.storage import postgres, runtime_config
    from core.storage.operations import store

    with postgres.connect() as conn, conn.cursor() as cur:
        raw = runtime_config.read_values(conn=conn) or {}
        cur.execute(f"""SELECT payment_provider,COUNT(*) FROM {store._table('extract_link_payment_orders')}
            WHERE payment_state IN ('pending','unknown') AND NOT (summary ? 'related_payment_order_id')
            GROUP BY payment_provider""")
        orders = [{"key": row[0], "occupied": int(row[1]),
                   "limit": int(raw.get("EXTRACT_LINK_PAYMENT_XXSYUN_CONCURRENCY", 1)) if row[0] == "xxsyun" else None}
                  for row in cur.fetchall()]
        cur.execute(f"""SELECT COUNT(*) FROM {store._table('operation_runs')} r
            JOIN {store._table('operation_tasks')} t ON t.last_run_id=r.id
            WHERE t.task_type='extract_link' AND r.status='queued' AND r.next_attempt_at>now()""")
        waiting = int(cur.fetchone()[0])
    return orders, waiting


def _queued_counts() -> dict[str, dict]:
    """统计事实队列，兼容注册投影按 source 排除，不能拿扫描候选冒充总数。"""
    from psycopg.rows import dict_row
    from core.storage import postgres, records
    from core.storage.operations import store

    store.init()
    result: dict[str, dict] = {}
    unknown_types: dict[str, int] = {}
    scheduled = 0
    with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"""SELECT t.task_type,
                jsonb_build_object('registration_driver',r.data->>'registration_driver') AS data,
                COUNT(*) AS queued,MIN(r.created_at) AS oldest
            FROM {store._table('operation_runs')} r
            JOIN {store._table('operation_tasks')} t ON t.last_run_id=r.id
            WHERE r.status='queued' AND r.cancel_requested_at IS NULL
              AND (r.next_attempt_at IS NULL OR r.next_attempt_at<=now())
              AND r.source_system<>'registration_jobs'
              AND t.task_type<>'account_inspection_batch'
            GROUP BY t.task_type,r.data->>'registration_driver'""")
        rows = list(cur.fetchall())
        cur.execute(f"""SELECT COUNT(*) FROM {store._table('operation_runs')} r
            JOIN {store._table('operation_tasks')} t ON t.last_run_id=r.id
            WHERE r.status='queued' AND r.cancel_requested_at IS NULL AND r.next_attempt_at>now()
              AND t.task_type<>'extract_link'""")
        scheduled = int(cur.fetchone()["count"])
        cur.execute(f"""SELECT job_type AS task_type,
                jsonb_build_object('registration_driver',data #>> '{{config_snapshot,registration_driver}}') AS data,
                COUNT(*) AS queued,MIN(created_at) AS oldest
            FROM {postgres.qualified(records.JOBS.name)} WHERE status='pending'
            GROUP BY job_type,data #>> '{{config_snapshot,registration_driver}}'""")
        for row in cur.fetchall():
            row = dict(row)
            if row["task_type"] == "twofa_retry":
                row["task_type"] = "account_setup_retry"
            rows.append(row)
        cur.execute(f"SELECT COUNT(*) AS queued,MIN(created_at) AS oldest FROM {store._table('operation_task_dependencies')} WHERE status='ready'")
        dependency = cur.fetchone()
        if dependency["queued"]:
            rows.append({"task_type": "account_setup_retry", "data": {}, **dependency})
    for row in rows:
        try:
            spec = resolve_admission_class(row)
        except ConcurrencyPolicyError:
            name = str(row.get("task_type") or "")
            unknown_types[name] = unknown_types.get(name, 0) + int(row["queued"])
            continue
        entry = result.setdefault(spec.key, {"queued": 0, "oldest_ready_at": None})
        entry["queued"] += int(row["queued"])
        value = row.get("oldest")
        value = value.isoformat() if hasattr(value, "isoformat") else str(value or "") or None
        if value and (entry["oldest_ready_at"] is None or value < entry["oldest_ready_at"]):
            entry["oldest_ready_at"] = value
    return result, [{"task_type": name, "queued": count, "code": "concurrency_policy_missing"}
                    for name, count in sorted(unknown_types.items())], scheduled
