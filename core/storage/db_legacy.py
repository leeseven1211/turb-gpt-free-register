# -*- coding: utf-8 -*-
"""
业务数据持久化层。

配置 DATABASE_URL 后，PostgreSQL 是业务数据的唯一事实来源。

兼容导出仅保留仍有外部消费者的通用 API 邮箱、域名邮箱和 Codex 凭证产物；
账号、注册任务、Outlook 和 iCloud 邮箱池均只通过行级表读写。
"""
import hashlib
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from core import compat_export, postgres_store, record_store, task_run_log

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _PROJECT_ROOT
_LEGACY_DATA_DIR = _PROJECT_ROOT / "data"
_LOG_DIR = _PROJECT_ROOT / "注册日志"
_PLAN_CHECK_STALE_SECONDS = 120
_PLAN_CHECK_QUEUE_STALE_SECONDS = 1800


class SnapshotConflictError(RuntimeError):
    """旧兼容快照试图覆盖已被其他事务修改的行。"""

_GENERIC_API_EMAIL_JSON = _PROJECT_ROOT / "用于注册的API邮箱.json"
_GENERIC_API_EMAIL_TXT = _PROJECT_ROOT / "用于注册的API邮箱.txt"
_CODEX_DIR = _PROJECT_ROOT / "codex_accounts"
# 导出状态单独存：{ "codex-邮箱-plan.json": {"exported_at": "...", "exported_count": N} }
# 不污染 CPA 兼容的原文件
_CODEX_EXPORT_STATE = _PROJECT_ROOT / "codex_导出状态.json"
_CODEX_CREDENTIALS_COLLECTION = "codex_credentials"

_LOCK = threading.RLock()
_COMPAT_SCHEMA_LOCK_KEY = "turb-compat-schema-init"
_COMPAT_SCHEMA_READY_KEYS = {"registration": "", "operation": ""}

JOB_PROGRESS_STAGES = (
    ("network", "分配网络"),
    ("email", "准备邮箱"),
    ("browser", "启动浏览器"),
    ("page", "打开注册页"),
    ("submit_email", "提交邮箱"),
    ("auth_redirect", "认证跳转"),
    ("login_password", "账号密码"),
    ("email_otp", "邮箱验证码"),
    ("profile", "填写资料"),
    ("token", "获取 Token"),
    ("codex", "Codex 授权"),
    ("twofa", "设置 2FA"),
    ("plan_check", "查套餐"),
    ("complete", "完成"),
)
_JOB_PROGRESS_KEYS = tuple(key for key, _label in JOB_PROGRESS_STAGES)
_JOB_PROGRESS_STATES = {"pending", "running", "success", "failed", "skipped", "stopped"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_storage() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    """从 PostgreSQL 读取集合。PG 不可用时直接抛错，不回退兼容文件。

    回退看起来更"健壮"，实际是让两份副本悄悄分叉——读到旧文件、写回 PG，
    中间的变更就没了。宁可响亮失败。
    """
    _ensure_storage()
    collection = _collection_name(path)
    found, payload = postgres_store.load_collection(collection)
    if found:
        return payload
    # PG 里还没有这个集合：用兼容文件做一次性种子。迁移完成后此路径会移除。
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    postgres_store.save_collection(collection, payload)
    return payload


def _write_json(path: Path, data: Any) -> None:
    _ensure_storage()
    postgres_store.save_collection(_collection_name(path), data)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def _collection_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(_PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


# ============================================================
# 表接缝：_load_X / _save_X 仅保留兼容 façade；业务写入直接走 record_store
#
# 保留"整表 list[dict] 进出"的形状，是为了让导出和迁移期旧测试可读；它们不再
# 是普通业务写入口。真正需要行级语义的地方（抢占、热点单字段更新、跨表事务）
# 直接调用 record_store，避免旧快照重新覆盖当前行。
# ============================================================

def _load_table(spec) -> list[dict]:
    return record_store.list_rows(spec, order_by="id")


def _row_signature(row: dict) -> str:
    """用于判断一行是否变化。派生字段不参与，避免它自己触发一次写。"""
    return json.dumps(
        {k: v for k, v in row.items() if k != "copy_line"},
        ensure_ascii=False, sort_keys=True, default=str,
    )


def _sync_table(spec, rows: list[dict], *, conn=None) -> None:
    """兼容接缝：逐行应用显式 payload，绝不把它当成全表快照。

    正常业务写入口不应调用本函数；它只为迁移期私有 façade 和旧测试保留。旧实现
    会先读整表、用全量快照覆盖字段，并删除快照中缺失的当前行，这两种行为都会把
    并发新增或更新抹掉。现在只处理调用者明确给出的行，不扫描、不删除；带有
    ``__record_version`` 的旧快照还会经过 ``xmin`` 乐观校验。没有版本的现有行
    也拒绝覆盖（相同行则 no-op），任何冲突都抛出 ``SnapshotConflictError``，不能
    让上层把“没有写入”误报成成功。
    """

    def _apply(active) -> None:
        for row in rows:
            payload = dict(row or {})
            rid = payload.pop("id", None)
            version = payload.pop("__record_version", None)
            if rid is None:
                new_id = record_store.insert_row(spec, payload, conn=active)
                row["id"] = new_id
                continue
            rid = int(rid)
            if version is not None:
                applied = record_store.patch_row_if_version(
                    spec, rid, payload, str(version), conn=active,
                )
                if not applied:
                    raise SnapshotConflictError(
                        f"{spec.name}#{rid} 的兼容快照版本已变化，拒绝覆盖"
                    )
                continue
            existing = record_store.get_row(spec, rid, conn=active)
            if existing is None:
                record_store.insert_row(spec, {**payload, "id": rid}, conn=active)
            elif _row_signature(existing) != _row_signature({**payload, "id": rid}):
                # 没有 xmin 就无法区分“调用方有意修改的字段”和“旧快照里的
                # 陈旧字段”。宁可显式拒绝，也不能把整个旧快照重新 patch 回去。
                raise SnapshotConflictError(
                    f"{spec.name}#{rid} 缺少快照版本，拒绝覆盖现有行"
                )

    if conn is not None:
        _apply(conn)
        return
    with record_store.transaction() as own:
        _apply(own)


def _next_id(items: list[dict]) -> int:
    ids = [int(item.get("id") or 0) for item in items]
    return (max(ids) if ids else 0) + 1


def _outlook_line(row: dict) -> str:
    return "----".join([
        row.get("email") or "",
        row.get("password") or "",
        row.get("client_id") or "",
        row.get("refresh_token") or "",
    ])


def _generic_api_email_line(row: dict) -> str:
    return "----".join([
        row.get("email") or "",
        row.get("code_url") or "",
    ])


def _account_password(row: dict) -> str:
    """读取 OpenAI 账号密码，不把邮箱池 password 当成账号密码。"""
    raw_extra = row.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    if isinstance(raw_extra, dict):
        password = (
            raw_extra.get("account_password")
            or raw_extra.get("login_password")
            or raw_extra.get("registration_password")
            or ""
        )
        if password:
            return str(password).strip()
    return str(
        row.get("account_password")
        or row.get("login_password")
        or row.get("registration_password")
        or ""
    ).strip()


def _account_line(row: dict) -> str:
    """生成账号整行：邮箱素材、Token、OpenAI 密码和 TOTP 密钥。"""
    base = row.get("original_email_line") or row.get("email") or ""
    token = row.get("access_token") or ""
    password = _account_password(row)
    totp = row.get("totp_secret") or ""
    parts = [base, token]
    if password or totp:
        parts.append(password)
    if totp:
        parts.append(totp)
    return "----".join(parts)


def _registered_email_line(row: dict) -> str:
    """生成注册成功邮箱素材行。"""
    return row.get("original_email_line") or row.get("email") or ""


def _sync_generic_api_email_txt(rows: list[dict]) -> None:
    available_rows = [r for r in rows if r.get("status") == "available"]
    lines = [_generic_api_email_line(r) for r in sorted(available_rows, key=lambda x: int(x.get("id") or 0))]
    _GENERIC_API_EMAIL_TXT.write_text(("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8")


def _load_outlook() -> list[dict]:
    return _load_table(record_store.OUTLOOK_POOL)


def _save_outlook(rows: list[dict]) -> None:
    """仅兼容旧测试/迁移；现有行没有版本时拒绝快照覆盖。"""
    _sync_table(record_store.OUTLOOK_POOL, rows)


def _load_generic_api_emails() -> list[dict]:
    return _load_table(record_store.GENERIC_API_POOL)


def _export_generic_api_emails() -> None:
    rows = _load_generic_api_emails()
    for row in rows:
        row["copy_line"] = _generic_api_email_line(row)
    _write_json(_GENERIC_API_EMAIL_JSON, rows)
    _sync_generic_api_email_txt(rows)


def _save_generic_api_emails(rows: list[dict]) -> None:
    """仅兼容旧测试/迁移；现有行没有版本时拒绝快照覆盖。"""
    _sync_table(record_store.GENERIC_API_POOL, rows)
    compat_export.schedule("generic_api_emails")


def _load_accounts() -> list[dict]:
    return _load_table(record_store.ACCOUNTS)


def _save_accounts(rows: list[dict]) -> None:
    """仅兼容旧测试/迁移；现有行没有版本时拒绝快照覆盖。"""
    _sync_table(record_store.ACCOUNTS, rows)


def _load_jobs() -> list[dict]:
    return _load_table(record_store.JOBS)


def _save_jobs(rows: list[dict]) -> None:
    """仅兼容旧测试/迁移；现有行没有版本时拒绝快照覆盖。"""
    _sync_table(record_store.JOBS, rows)


compat_export.register("generic_api_emails", _export_generic_api_emails)


def _patch_row_and_export(spec, row_id: int, changes: dict, kind: str) -> bool:
    """单行更新的快路径。

    走 _load_X/_save_X 那条接缝要读全表并逐行比对签名（243 个账号约 210 ms）；
    只改一行时没必要——直接发一条 UPDATE 即可（约 18 ms）。热路径用这个，
    需要整表语义的地方（批量导入、跨表事务）仍走接缝。
    """
    changed = record_store.patch_row(spec, int(row_id), changes)
    if changed and kind not in {"accounts", "jobs", "outlook", "icloud_hide_emails"}:
        compat_export.schedule(kind)
    return changed


def _patch_account(acc_id: int, changes: dict) -> bool:
    return _patch_row_and_export(record_store.ACCOUNTS, acc_id, changes, "accounts")


def _ensure_compat_schema(name: str, initializer) -> None:
    """Initialize one compatibility schema once per process/schema, safely."""
    ready_key = f"{postgres_store.database_url()}::{postgres_store.schema_name()}"
    with _LOCK:
        if _COMPAT_SCHEMA_READY_KEYS.get(name) == ready_key:
            return
    # The local flag avoids taking a database lock on every projection write. The
    # transaction-level lock is only needed while each worker initializes its own
    # view of the shared, additive compatibility schema.
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, _COMPAT_SCHEMA_LOCK_KEY)
        with _LOCK:
            if _COMPAT_SCHEMA_READY_KEYS.get(name) == ready_key:
                return
        initializer()
        with _LOCK:
            _COMPAT_SCHEMA_READY_KEYS[name] = ready_key


def _sync_operation_job(job_id: int) -> None:
    """迁移期兼容桥：旧注册执行写入后，立即刷新统一任务投影。

    旧表仍是回滚落点，因此投影异常不能反过来覆盖或删除旧数据；异常会完整记录，
    `migrate_unified_task_center.py --apply` 可随时幂等修复。
    """
    try:
        from core import operation_task_store

        _ensure_compat_schema("operation", operation_task_store.init)
        operation_task_store.sync_registration_job(int(job_id))
    except Exception:
        logger.exception("同步统一任务中心失败：registration_job_id=%s", job_id)


def _ensure_registration_attempt_job(row: dict) -> None:
    """Create/link the durable Attempt before the compatibility projection.

    ``registration_jobs`` remains the legacy execution row, but every new job and
    retry must carry an explicit Attempt link.  Failures here are surfaced to the
    caller: silently creating an unlinked execution would make recovery unsafe.
    """
    from core.storage import registration

    _ensure_compat_schema("registration", registration.init)
    job_data = row.get("data") if isinstance(row.get("data"), dict) else {}
    attempt = registration.ensure_attempt_for_job(int(row["id"]), data=job_data)
    attempt_id = int(attempt["id"])
    row["attempt_id"] = attempt_id
    record_store.patch_row(record_store.JOBS, int(row["id"]), {"attempt_id": attempt_id})
    # A legacy job is still one concrete execution.  Persist its Run #1 at the
    # same compatibility boundary; retries receive another Run under this Attempt.
    registration.start_run(
        attempt_id,
        job_id=int(row["id"]),
        action_type=str(row.get("job_type") or "registration"),
        execution_id=row.get("execution_id"),
        worker_pid=row.get("worker_pid"),
        data=job_data,
    )


def _patch_job(job_id: int, changes: dict) -> bool:
    changed = _patch_row_and_export(record_store.JOBS, job_id, changes, "jobs")
    if changed:
        _sync_operation_job(job_id)
    return changed


def _save_together(*pairs) -> None:
    """仅兼容显式快照调用；普通业务写入不再使用此 helper。"""
    with record_store.transaction() as conn:
        for spec, rows, _kind in pairs:
            _sync_table(spec, rows, conn=conn)
    for _spec, _rows, kind in pairs:
        if kind and kind not in {"accounts", "jobs", "outlook", "icloud_hide_emails"}:
            compat_export.schedule(kind)


def _find_by_email(rows: list[dict], email: str) -> dict | None:
    target = (email or "").lower()
    return next((r for r in rows if (r.get("email") or "").lower() == target), None)


def _decorate_account(row: dict) -> dict:
    out = dict(row)
    out["note"] = out.get("note") or ""
    out["note_updated_at"] = out.get("note_updated_at") or ""
    plan_status = out.get("plan_check_status")
    if plan_status in {"queued", "running"}:
        try:
            stamp_key = "plan_check_queued_at" if plan_status == "queued" else "plan_check_started_at"
            stale_after = _PLAN_CHECK_QUEUE_STALE_SECONDS if plan_status == "queued" else _PLAN_CHECK_STALE_SECONDS
            started_at = datetime.fromisoformat(str(out.get(stamp_key) or ""))
            if (datetime.now() - started_at).total_seconds() >= stale_after:
                out["plan_check_status"] = "failed"
                out["plan_check_error"] = "上次套餐查询状态已超时，可重新查询"
                out["plan_check_stale"] = True
        except (TypeError, ValueError):
            out["plan_check_status"] = "failed"
            out["plan_check_error"] = "上次套餐查询状态异常，可重新查询"
            out["plan_check_stale"] = True
    out["copy_line"] = _account_line(out)
    return out


def decorate_account(row: dict) -> dict:
    """管理读模型使用的稳定账号装饰入口。"""
    return _decorate_account(row)


def _account_matches_plan_filter(row: dict, plan_filter: str | None = None) -> bool:
    """账号套餐过滤。plus 表示已开通 Plus（兼容 plus/chatgpt_plus/plus_trial 等标记）。"""
    f = str(plan_filter or "").strip().lower()
    if not f or f in {"all", "any"}:
        return True
    plan = str(row.get("current_plan_type") or row.get("plan_type") or "").strip().lower()
    if f == "plus":
        # “free(可Plus试用)”/plus_trial_eligible 只是可试用，不算已开通 Plus。
        # 只有套餐字段本身是 Plus/ChatGPT Plus/plus_* 且不含 free 时才命中。
        return "plus" in plan and "free" not in plan
    if f == "free":
        return plan == "free"
    return plan == f


def _decorate_outlook(row: dict, account_by_email: dict[str, dict] | None = None) -> dict:
    out = dict(row)
    out["copy_line"] = _outlook_line(out)
    account = None
    if account_by_email is not None:
        account = account_by_email.get((out.get("email") or "").lower())
    if account:
        out["registered_account_id"] = account.get("id")
        out["access_token"] = account.get("access_token")
        out["access_token_preview"] = (
            (account.get("access_token") or "")[:40] + "..."
            if account.get("access_token")
            else ""
        )
        out["account_copy_line"] = _account_line(account)
        out["totp_secret"] = account.get("totp_secret")
    return out


def _decorate_generic_api_email(row: dict, account_by_email: dict[str, dict] | None = None) -> dict:
    out = dict(row)
    out["copy_line"] = _generic_api_email_line(out)
    out["password"] = out.get("password") or ""
    out["client_id"] = out.get("client_id") or ""
    out["refresh_token"] = out.get("refresh_token") or ""
    account = None
    if account_by_email is not None:
        account = account_by_email.get((out.get("email") or "").lower())
    if account:
        out["registered_account_id"] = account.get("id")
        out["access_token"] = account.get("access_token")
        out["access_token_preview"] = (
            (account.get("access_token") or "")[:40] + "..."
            if account.get("access_token")
            else ""
        )
        out["account_copy_line"] = _account_line(account)
        out["totp_secret"] = account.get("totp_secret")
    return out


def _get_conn() -> None:
    """兼容旧入口：初始化文件存储目录。"""
    _ensure_storage()
    return None


def _row_to_dict(row: dict | None) -> dict | None:
    return dict(row) if row is not None else None


def _locked_row_by_email(conn, spec, email: str) -> dict | None:
    """在调用者事务中按不区分大小写的邮箱读取并锁定一行。"""
    table = postgres_store.qualified(spec.name)
    with conn.cursor() as cur:
        cur.execute(
            f'SELECT * FROM {table} WHERE lower("email") = lower(%s) '
            "ORDER BY id LIMIT 1 FOR UPDATE",
            (str(email or "").strip(),),
        )
        return record_store.merge_row(spec, cur.fetchone())


# ============================================================
# registered_accounts
# ============================================================

def insert_account(
    *,
    email: str,
    access_token: str,
    totp_secret: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
    plan_type: str | None = None,
    expires_at: str | None = None,
    device_id: str | None = None,
    proxy_used: str | None = None,
    email_source: str | None = None,
    extra: dict | None = None,
    codex_status: str | None = None,   # success / failed / skipped / missing
    codex_error: str | None = None,    # 失败原因（仅 codex_status=failed 时有意义）
) -> int:
    """插入或更新注册成功账号，并在同一事务中收口关联邮箱素材。"""
    normalized_email = str(email or "").strip()
    if not normalized_email:
        raise ValueError("账号邮箱不能为空")

    # transaction() 自身也会防御性 init，但这里显式初始化保证新 worktree/新
    # schema 的首个查询不会在 _locked_row_by_email 处撞到尚未创建的表。
    record_store.init()
    account_changed = False
    outlook_changed = False
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, f"registered-account:{normalized_email.lower()}")
        existing = _locked_row_by_email(conn, record_store.ACCOUNTS, normalized_email)
        outlook_row = _locked_row_by_email(conn, record_store.OUTLOOK_POOL, normalized_email)
        now = _now()
        changes: dict[str, Any] = {
            "access_token": access_token,
            "updated_at": now,
        }
        optional = {
            "totp_secret": totp_secret,
            "user_id": user_id,
            "user_name": user_name,
            "plan_type": plan_type,
            "expires_at": expires_at,
            "device_id": device_id,
            "proxy_used": proxy_used,
            "email_source": email_source,
            "codex_status": codex_status,
            "codex_error": codex_error,
        }
        changes.update({key: value for key, value in optional.items() if value is not None})
        if extra:
            merged_extra = {**_account_extra(existing or {}), **extra}
            # A final registration checkpoint is authoritative for 2FA.  The
            # intermediate checkpoint intentionally leaves this marker behind,
            # but a later success must remove it instead of preserving stale
            # derived state through the generic metadata merge.
            twofa = extra.get("twofa")
            if isinstance(twofa, dict) and str(twofa.get("status") or "").strip().lower() == "success":
                merged_extra.pop("totp_setup_pending", None)
            changes["extra_json"] = json.dumps(
                merged_extra, ensure_ascii=False,
            )

        if access_token:
            # expires_at 是 ChatGPT Session 到期时间；AT 自身到期时间来自 JWT exp，
            # 两者分开保存，避免页面和刷新调度误判。
            from core.chatgpt_plan import token_claims

            claims = token_claims(access_token)
            changes["token_expires_at"] = claims.get("token_expires_at")
            changes["token_expired"] = claims.get("token_expired")

        if outlook_row is not None:
            changes.update({
                "password": outlook_row.get("password"),
                "client_id": outlook_row.get("client_id"),
                "refresh_token": outlook_row.get("refresh_token"),
                "original_email_line": _outlook_line(outlook_row),
            })

        if existing is None:
            account_payload = {"email": normalized_email, "created_at": now, **changes}
            row_id = record_store.insert_row(record_store.ACCOUNTS, account_payload, conn=conn)
            account_changed = True
        else:
            row_id = int(existing["id"])
            account_changed = record_store.patch_row(
                record_store.ACCOUNTS, row_id, changes, conn=conn,
            )

        if outlook_row is not None:
            pool_changes: dict[str, Any] = {
                "status": "used",
                "used_at": outlook_row.get("used_at") or now,
                "registered_account_id": row_id,
                "access_token": access_token,
                "completed_at": now,
            }
            if totp_secret:
                pool_changes["totp_secret"] = totp_secret
            outlook_changed = record_store.patch_row(
                record_store.OUTLOOK_POOL, int(outlook_row["id"]), pool_changes, conn=conn,
            )

    return row_id


def update_account_codex_status(email: str, codex_status: str, codex_error: str | None = None) -> bool:
    """
    单独更新某账号的 codex_status / codex_error（手动补跑 Codex 时用）。
    返回是否找到该账号。
    """
    row = record_store.get_row_by(record_store.ACCOUNTS, "email", email, lower=True)
    if row is None:
        return False
    return _patch_account(int(row["id"]), {
        "codex_status": codex_status,
        "codex_error": codex_error,
        "updated_at": _now(),
    })


def update_account_codex_operation_state(
    email: str,
    *,
    credential_state: str | None = None,
    execution_status: str | None = None,
    last_run_status: str | None = None,
    error: str | None = None,
    active_run_id: int | None = None,
) -> bool:
    """更新 Codex 三轴状态，同时维护旧 codex_status 的只读兼容语义。

    一次重新授权失败不能抹掉此前有效的凭证资产；因此仅凭证确认成功、明确过期或
    账号停用时才改变资产态。active_run_id=0 表示清空当前执行引用。
    """
    row = record_store.get_row_by(record_store.ACCOUNTS, "email", email, lower=True)
    if row is None:
        return False
    changes: dict[str, Any] = {"updated_at": _now()}
    if credential_state is not None:
        changes["codex_credential_state"] = str(credential_state)
    if execution_status is not None:
        changes["codex_execution_status"] = str(execution_status)
    if last_run_status is not None:
        changes["codex_last_run_status"] = str(last_run_status)
    if active_run_id is not None:
        changes["codex_active_run_id"] = None if int(active_run_id or 0) <= 0 else int(active_run_id)
    if error is not None or last_run_status == "success":
        changes["codex_error"] = error

    asset = str(credential_state if credential_state is not None else row.get("codex_credential_state") or "").lower()
    legacy = str(row.get("codex_status") or "").lower()
    result = str(last_run_status or "").lower()
    if asset == "valid":
        changes["codex_status"] = "success"
    elif asset == "pending_confirmation":
        changes["codex_status"] = "pending_confirmation"
    elif asset == "deactivated" or result == "deactivated":
        changes["codex_status"] = "deactivated"
    elif legacy != "success":
        if result in {"failed", "cancelled", "interrupted", "attention_required"}:
            changes["codex_status"] = "stopped" if result == "cancelled" else result
        elif execution_status in {"queued", "running", "cancelling"}:
            changes["codex_status"] = "retrying"
    return _patch_account(int(row["id"]), changes)


def _account_extra(row: dict) -> dict:
    raw = row.get("extra_json") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = {}
    return dict(raw) if isinstance(raw, dict) else {}


def _mutate_account_extra(
    email: str,
    mutate: Callable[[dict, dict], dict | None],
    *,
    sync_totp: bool = False,
) -> bool:
    """Read/modify metadata under one database row lock, including pool sync.

    JSONB merging protects distinct top-level fields but extra_json is itself
    one serialized object. Its read and write must share this transaction to
    preserve another process's password, MFA, or registration checkpoints.
    ``mutate`` only changes in-memory data and must not perform remote I/O.
    """
    pool_changed = False
    with record_store.transaction() as conn:
        row = _locked_row_by_email(conn, record_store.ACCOUNTS, email)
        if row is None:
            return False
        extra = _account_extra(row)
        changes = mutate(row, extra)
        if changes is None:
            return True
        changed = record_store.patch_row(record_store.ACCOUNTS, int(row["id"]), {
            **changes,
            "extra_json": json.dumps(extra, ensure_ascii=False) if extra else None,
            "updated_at": _now(),
        }, conn=conn)
        if sync_totp and "totp_secret" in changes:
            # Keep lock ordering account -> pool, matching insert_account.
            pool = _locked_row_by_email(conn, record_store.OUTLOOK_POOL, email)
            if pool is not None:
                pool_changed = record_store.patch_row(
                    record_store.OUTLOOK_POOL, int(pool["id"]),
                    {"totp_secret": changes["totp_secret"]}, conn=conn,
                )
    return changed


def update_account_login_password(email: str, password: str, *, source: str = "post_registration") -> bool:
    """保存账号当前 OpenAI 密码；旧函数名保留以兼容调用方。"""
    normalized = str(password or "").strip()
    if not normalized:
        return False

    def mutate(_row, extra):
        extra["account_password"] = normalized
        extra.pop("login_password", None)
        extra.pop("login_password_source", None)
        extra.pop("registration_password", None)
        return {}

    return _mutate_account_extra(email, mutate)


def update_account_password_capability(
    email: str,
    *,
    eligible: bool,
    reason: str | None = None,
    evidence: str | None = None,
) -> bool:
    """Persist the remote capability result without changing credentials."""
    capability = {
        "eligible": bool(eligible),
        "reason": str(reason or "")[:160],
        "checked_at": _now(),
    }
    if evidence:
        capability["evidence"] = str(evidence)[:160]

    def mutate(_row, extra):
        extra["account_password_capability"] = capability
        return {}

    return _mutate_account_extra(email, mutate)


def update_account_totp_secret(
    email: str,
    totp_secret: str,
    *,
    setup_pending: bool | None = None,
) -> bool:
    """只更新账号的 TOTP secret/设置检查点，并同步关联邮箱素材。"""
    secret = str(totp_secret or "").strip()
    if not secret:
        return False

    def mutate(_row, extra):
        if setup_pending is not None:
            if setup_pending:
                extra["totp_setup_pending"] = True
            else:
                extra.pop("totp_setup_pending", None)
                extra.pop("totp_pending_secret", None)
                extra.pop("totp_previous_secret", None)
                extra.pop("totp_rotation_disabled", None)
        return {"totp_secret": secret}

    return _mutate_account_extra(email, mutate, sync_totp=True)


def stage_account_totp_secret(email: str, totp_secret: str) -> bool:
    """Store a replacement TOTP secret without changing the active secret."""
    secret = str(totp_secret or "").strip()
    if not secret:
        return False

    def mutate(_row, extra):
        extra["totp_pending_secret"] = secret
        return {}

    return _mutate_account_extra(email, mutate)


def mark_account_totp_disabled_for_rotation(email: str) -> bool:
    """Record remote MFA disablement while preserving the old secret for audit."""

    def mutate(row, extra):
        old_secret = str(row.get("totp_secret") or "").strip()
        if old_secret:
            extra["totp_previous_secret"] = old_secret
        extra["totp_rotation_disabled"] = True
        return {"totp_secret": None}

    return _mutate_account_extra(email, mutate, sync_totp=True)


def clear_account_totp_pending(email: str) -> bool:
    """Discard an unactivated replacement TOTP secret."""

    def mutate(_row, extra):
        if "totp_pending_secret" not in extra:
            return None
        extra.pop("totp_pending_secret", None)
        return {}

    return _mutate_account_extra(email, mutate)


def update_account_twofa_status(email: str, status: str, message: str) -> bool:
    """更新账号 2FA 结果，并在成功时清除待激活检查点。"""
    normalized = str(status or "").strip().lower() or "failed"

    def mutate(_row, extra):
        extra["twofa"] = {
            "status": normalized,
            "ok": normalized == "success",
            "message": str(message or "")[:300],
        }
        if normalized == "success":
            extra.pop("totp_setup_pending", None)
        return {}

    return _mutate_account_extra(email, mutate)


def update_account_token_metadata(acc_id: int, access_token: str) -> bool:
    """只同步当前 AT 的 JWT 到期信息，不改动账号状态或 Token 内容。"""
    from core.chatgpt_plan import token_claims
    claims = token_claims(access_token)
    row = record_store.get_row(record_store.ACCOUNTS, int(acc_id))
    if row is None or str(row.get("access_token") or "").strip() != str(access_token or "").strip():
        return False
    expires_at = claims.get("token_expires_at")
    expired = claims.get("token_expired")
    if row.get("token_expires_at") == expires_at and row.get("token_expired") == expired:
        return True   # 内容没变就不写，避免无谓地触发一次兼容导出
    changed = record_store.claim_row(record_store.ACCOUNTS, acc_id, changes={
        "token_expires_at": expires_at,
        "token_expired": expired,
        "updated_at": _now(),
    }, guard="BTRIM(COALESCE(data->>'access_token', '')) = %s",
        guard_params=(str(access_token or "").strip(),))
    return changed


def update_account_session(email: str, access_token: str, *, expires_at: str | None = None) -> bool:
    """保存重新登录取得的新 ChatGPT 会话，并把注册检查点推进到已注册。

    账号配置补跑过去只在浏览器里取得 session，却没有写回本地，导致任务显示成功而
    账号仍无 Token。这里作为所有账号级重新登录的统一收口，保留原密码/2FA 信息，
    只更新会话字段和注册检查点。
    """
    normalized_email = str(email or "").strip()
    normalized_token = str(access_token or "").strip()
    if not normalized_email or not normalized_token:
        return False
    from core.chatgpt_plan import token_claims

    claims = token_claims(normalized_token)
    account_id = None

    def mutate(row, extra):
        nonlocal account_id
        account_id = int(row["id"])
        extra["registration_checkpoint"] = "registered"
        extra.pop("registration_pending_reason", None)
        return {
            "access_token": normalized_token,
            "expires_at": expires_at if expires_at is not None else row.get("expires_at"),
            "token_expires_at": claims.get("token_expires_at"),
            "token_expired": claims.get("token_expired"),
        }

    changed = _mutate_account_extra(normalized_email, mutate)
    if changed:
        jobs = record_store.list_rows(
            record_store.JOBS,
            where='"account_id"=%s OR lower("email")=lower(%s)',
            params=(account_id, normalized_email),
            order_by="id",
        )
        for job in jobs:
            _sync_operation_job(int(job["id"]))
    return changed


def sync_account_token_metadata(items: list[tuple[int, str]]) -> int:
    """批量回填 AT 到期信息，只 patch 仍持有该 Token 的目标账号。"""
    from core.chatgpt_plan import token_claims

    tokens = {int(acc_id): str(token or "").strip() for acc_id, token in items if str(token or "").strip()}
    if not tokens:
        return 0
    changed = 0
    for acc_id, token in tokens.items():
        row = record_store.get_row(record_store.ACCOUNTS, acc_id)
        if row is None or str(row.get("access_token") or "").strip() != token:
            continue
        claims = token_claims(token)
        expires_at = claims.get("token_expires_at")
        expired = claims.get("token_expired")
        if row.get("token_expires_at") == expires_at and row.get("token_expired") == expired:
            continue
        if record_store.claim_row(
            record_store.ACCOUNTS,
            acc_id,
            changes={
                "token_expires_at": expires_at,
                "token_expired": expired,
                "updated_at": _now(),
            },
            guard="data->>'access_token' = %s",
            guard_params=(token,),
        ):
            changed += 1
    return changed


def _stage_claim_guard(prefix: str, *, require_alive: bool = False) -> tuple[str, list]:
    """构造"未被占用，或占用已超时"的 SQL 判据。

    改造前这段是"读出来判断状态，再写回去"，两个进程会同时读到 idle 然后都以为
    抢到了——`threading.RLock` 只在进程内有效，而 CLI 与 WebUI 是两个进程。
    改成条件 UPDATE 后，判据和写入在同一条语句里，由数据库保证互斥。

    时间戳是 ISO 字符串，字典序即时间序，可以直接比较。缺失、空串或不像时间戳
    的值一律视为已超时——这保留了原实现"解析失败就放行"的语义，否则一行脏数据
    会让这个账号永远无法再被领取。
    """
    now = datetime.now()
    queue_before = (now - timedelta(seconds=_PLAN_CHECK_QUEUE_STALE_SECONDS)).isoformat(timespec="seconds")
    run_before = (now - timedelta(seconds=_PLAN_CHECK_STALE_SECONDS)).isoformat(timespec="seconds")
    status = f'"{prefix}_status"'
    guard = (
        f"(COALESCE({status}, '') NOT IN ('queued', 'running')"
        f" OR ({status} = 'queued' AND (COALESCE(data->>'{prefix}_queued_at', '') !~ '^[0-9]{{4}}-'"
        f"      OR data->>'{prefix}_queued_at' < %s))"
        f" OR ({status} = 'running' AND (COALESCE(data->>'{prefix}_started_at', '') !~ '^[0-9]{{4}}-'"
        f"      OR data->>'{prefix}_started_at' < %s)))"
    )
    params = [queue_before, run_before]
    if require_alive:
        guard = f"deactivated = FALSE AND {guard}"
    return guard, params


def _claim_account_stage(acc_id: int, prefix: str, changes: dict, *, require_alive: bool = False) -> bool:
    guard, params = _stage_claim_guard(prefix, require_alive=require_alive)
    return record_store.claim_row(
        record_store.ACCOUNTS, int(acc_id),
        changes=changes, guard=guard, guard_params=params,
    )


def _mark_account_stage_running(acc_id: int, prefix: str, changes: dict) -> bool:
    """仅当该阶段确实处于 queued/running 时才置为 running。"""
    return record_store.claim_row(
        record_store.ACCOUNTS, int(acc_id),
        changes=changes,
        guard=f"COALESCE(\"{prefix}_status\", '') IN ('queued', 'running')",
    )


def claim_account_plan_check(
    acc_id: int | None = None,
    email: str | None = None,
    trigger: str = "manual",
) -> bool:
    """原子占用账号的套餐查询；已有未超时查询时返回 False。"""
    if acc_id is None:
        row = get_account_by_email(email or "")
        if row is None:
            return False
        acc_id = int(row["id"])
    now = _now()
    return _claim_account_stage(acc_id, "plan_check", {
        "plan_check_status": "queued",
        "plan_check_trigger": str(trigger or "manual"),
        "plan_check_queued_at": now,
        "plan_check_started_at": None,
        "plan_check_completed_at": None,
        "plan_check_error": None,
        "updated_at": now,
    })


def mark_account_plan_check_running(acc_id: int) -> bool:
    """把已排队的套餐查询标记为执行中。"""
    now = _now()
    return _mark_account_stage_running(acc_id, "plan_check", {
        "plan_check_status": "running",
        "plan_check_started_at": now,
        "plan_check_error": None,
        "updated_at": now,
    })


def recover_interrupted_plan_checks(
    *, excluded_account_ids: Iterable[int] | None = None,
) -> int:
    """服务启动时把上次进程遗留的内存队列状态恢复为可重试失败。"""
    now = _now()
    excluded = sorted({int(item) for item in (excluded_account_ids or ())})
    where = '"plan_check_status" IN (%s, %s)'
    params: list[Any] = ["queued", "running"]
    if excluded:
        where += ' AND "id" <> ALL(%s)'
        params.append(excluded)
    recovered = record_store.patch_rows_where(
        record_store.ACCOUNTS,
        changes={
            "plan_check_status": "failed",
            "plan_check_ok": False,
            "plan_check_error": "WebUI 重启导致套餐查询中断，请重新查询",
            "plan_check_completed_at": now,
            "updated_at": now,
        },
        where=where,
        params=params,
    )
    return recovered


def update_account_plan_check(acc_id: int | None = None, email: str | None = None, result: dict | None = None) -> bool:
    """更新账号套餐/Plus 试用资格查询结果。"""
    result = result or {}
    row = (
        record_store.get_row(record_store.ACCOUNTS, int(acc_id))
        if acc_id is not None
        else record_store.get_row_by(record_store.ACCOUNTS, "email", email or "", lower=True)
    )
    if row is None:
        return False

    now = _now()
    ok = bool(result.get("ok"))
    checked_at = result.get("checked_at") or now
    changes: dict[str, Any] = {
        "plan_check_status": "success" if ok else "failed",
        "plan_check_ok": ok,
        "plan_checked_at": checked_at,
        "plan_check_completed_at": now,
        "plan_check_http_status": result.get("http_status"),
        "plan_check_error": None if ok else result.get("error"),
    }

    if result.get("account_id"):
        changes["account_id"] = result.get("account_id")
    # 查询失败只更新本次错误和网络信息，不覆盖上一次成功拿到的套餐、
    # 试用资格、优惠及有效期，避免临时网络故障把真实权益清空。
    if ok:
        if result.get("current_plan_type"):
            changes["current_plan_type"] = result.get("current_plan_type")
            changes["plan_type"] = result.get("current_plan_type")
        for key in ("subscription_plan", "expires_at", "renews_at", "cancels_at",
                    "billing_period", "billing_currency"):
            if result.get(key) is not None:
                changes[f"plan_{key}" if key in {"expires_at", "renews_at", "cancels_at"} else key] = result.get(key)
        if result.get("has_active_subscription") is not None:
            changes["has_active_subscription"] = bool(result.get("has_active_subscription"))
        if result.get("is_delinquent") is not None:
            changes["is_delinquent"] = bool(result.get("is_delinquent"))
        for key in (
            "discount_type", "discount_amount", "discount_duration_num_periods",
            "discount_expires_at", "discount_cancellation_policy",
            "discount_promo_campaign_id", "last_purchase_origin_platform", "last_will_renew",
        ):
            if result.get(key) is not None:
                changes[key] = result.get(key)

        changes.update({
            "plus_trial_eligible": bool(result.get("plus_trial_eligible")),
            "plus_trial_campaign_id": result.get("plus_trial_campaign_id"),
            "plus_trial_title": result.get("plus_trial_title"),
            "plus_trial_discount_percentage": result.get("plus_trial_discount_percentage"),
            "plus_trial_duration_num_periods": result.get("plus_trial_duration_num_periods"),
            "plus_trial_duration_period": result.get("plus_trial_duration_period"),
            "eligible_offer_ids": result.get("eligible_offer_ids") or [],
            "plan_last_success_at": checked_at,
            "plan_last_success_result_json": json.dumps(result, ensure_ascii=False),
        })
        # 额度是套餐查询的附带快照。额度接口偶发失败时保留上次成功的
        # 窗口和类型，只更新独立的失败状态，避免把真实额度清空。
        quota_status = result.get("quota_status")
        if quota_status:
            quota_checked_at = result.get("quota_checked_at") or checked_at
            changes.update({
                "quota_status": quota_status,
                "quota_checked_at": quota_checked_at,
                "quota_http_status": result.get("quota_http_status"),
            })
            if quota_status == "success":
                changes.update({
                    "quota_type": result.get("quota_type") or "未返回额度窗口",
                    "quota_windows": result.get("quota_windows") or [],
                    "quota_error": None,
                    "quota_last_success_at": quota_checked_at,
                })
            else:
                changes["quota_error"] = result.get("quota_error") or "额度查询失败"
    changes.update({
        "plan_check_proxy_mode": result.get("proxy_mode"),
        "plan_check_network_route": result.get("network_route"),
        "plan_check_proxy_used": result.get("proxy_used"),
        "plan_check_proxy_fallback_reason": result.get("proxy_fallback_reason"),
        "token_expired": result.get("token_expired"),
        "token_expires_at": result.get("token_expires_at"),
        "plan_check_result_json": json.dumps(result, ensure_ascii=False),
        "updated_at": now,
    })
    return _patch_account(int(row["id"]), changes)


def claim_account_extract(acc_id: int, trigger: str = "manual", link_type: str = "pix") -> bool:
    """原子占用账号提链任务；已有未超时任务时返回 False。"""
    now = _now()
    return _claim_account_stage(acc_id, "extract_link", {
        "extract_link_status": "queued",
        "extract_link_ok": False,
        "extract_link_trigger": str(trigger or "manual"),
        "extract_link_type": str(link_type or "pix").lower(),
        "extract_link_queued_at": now,
        "extract_link_started_at": None,
        "extract_link_completed_at": None,
        "extract_link_error": None,
        "extract_link_message": "已入队",
        "updated_at": now,
    })


def mark_account_extract_running(acc_id: int) -> bool:
    """把提链任务标记为运行中。"""
    now = _now()
    return _mark_account_stage_running(acc_id, "extract_link", {
        "extract_link_status": "running",
        "extract_link_started_at": now,
        "extract_link_error": None,
        "extract_link_message": "任务运行中",
        "updated_at": now,
    })


def update_account_extract(acc_id: int, result: dict | None = None) -> bool:
    """更新账号提链任务结果/进度。"""
    result = result or {}
    if record_store.get_row(record_store.ACCOUNTS, int(acc_id)) is None:
        return False
    now = _now()
    status = str(result.get("status") or ("success" if result.get("ok") else "failed"))
    ok = bool(result.get("ok")) and status == "success"
    changes: dict[str, Any] = {
        "extract_link_status": status,
        "extract_link_ok": ok,
        "extract_link_checked_at": result.get("checked_at") or now,
        "extract_link_error": None if ok or status == "running" else result.get("error"),
        "updated_at": now,
    }
    if status in {"success", "failed", "stopped"}:
        changes["extract_link_completed_at"] = now
    for key in ("message", "job_id", "link_type", "cdk_remaining"):
        if result.get(key) is not None:
            changes[f"extract_link_{key}"] = result.get(key)
    payload = result.get("result") if isinstance(result.get("result"), dict) else {}
    if payload:
        changes.update({
            "extract_link_long_url": payload.get("long_url"),
            "extract_link_copy_paste": payload.get("copy_paste"),
            "extract_link_image_url_png": payload.get("image_url_png"),
            "extract_link_image_url_svg": payload.get("image_url_svg"),
            "extract_link_payment_method": payload.get("payment_method"),
            "extract_link_payment_link_type": payload.get("payment_link_type"),
            "extract_link_expires_at": payload.get("expires_at"),
            "extract_link_result_json": json.dumps(payload, ensure_ascii=False),
        })
        if payload.get("cdk_remaining") is not None:
            changes["extract_link_cdk_remaining"] = payload.get("cdk_remaining")
    return _patch_account(int(acc_id), changes)


def mark_extract_link_type_failed(acc_id: int, link_type: str, error: str | None = None) -> bool:
    """记录某账号已失败的提链类型，后续提炼自动跳过该类型。"""
    normalized = str(link_type or "").strip().lower()
    if not normalized:
        return False
    row = record_store.get_row(record_store.ACCOUNTS, int(acc_id))
    if row is None:
        return False
    failed = row.get("extract_link_failed_types")
    if isinstance(failed, str):
        try:
            failed = json.loads(failed)
        except (TypeError, ValueError):
            failed = []
    if not isinstance(failed, list):
        failed = []
    failed_types = {
        str(item or "").strip().lower()
        for item in failed
        if str(item or "").strip()
    }
    failed_types.add(normalized)
    changes = {
        "extract_link_failed_types": sorted(failed_types),
        "extract_link_last_failed_type": normalized,
        "extract_link_last_failed_at": _now(),
        "updated_at": _now(),
    }
    if error:
        changes["extract_link_last_failed_error"] = str(error)[:500]
    return _patch_account(acc_id, changes)


def recover_interrupted_extract_links(
    *, excluded_account_ids: Iterable[int] | None = None,
) -> int:
    """服务启动时恢复上次进程中断的提链状态。"""
    now = _now()
    excluded = sorted({int(item) for item in (excluded_account_ids or ())})
    where = '"extract_link_status" IN (%s, %s)'
    params: list[Any] = ["queued", "running"]
    if excluded:
        where += ' AND "id" <> ALL(%s)'
        params.append(excluded)
    recovered = record_store.patch_rows_where(
        record_store.ACCOUNTS,
        changes={
            "extract_link_status": "failed",
            "extract_link_ok": False,
            "extract_link_error": "WebUI 重启导致提链任务中断，请重新提链",
            "extract_link_completed_at": now,
            "updated_at": now,
        },
        where=where,
        params=params,
    )
    return recovered


def _account_matches_query(row: dict, q: str | None) -> bool:
    q = str(q or "").strip().lower()
    if not q:
        return True
    try:
        return q in "\n".join(str(v) for v in row.values()).lower()
    except Exception:
        return False


def _parse_iso_dt(value: str | None, end_of_day: bool = False) -> datetime | None:
    """宽松解析 ISO 日期/时间字符串；支持 YYYY-MM-DD 或完整 ISO；解析失败返回 None。

    end_of_day=True 时，纯日期（YYYY-MM-DD）按当天 23:59:59.999999 解析，
    用于 date_to 过滤（保证包含截止当天）；完整时间串原样返回。
    """
    if not value:
        return None
    text = str(value).strip()
    try:
        if len(text) == 10 and text[4] == "-":
            if end_of_day:
                return datetime.fromisoformat(text + "T23:59:59.999999")
            return datetime.fromisoformat(text + "T00:00:00")
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _filtered_decorated_accounts(archived: str | bool | None = False, plan_filter: str | None = None, q: str | None = None, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    rows = _load_accounts()
    if archived in (True, "1", "true", "yes", "only"):
        rows = [r for r in rows if bool(r.get("archived"))]
    elif archived in ("all", "include"):
        pass
    else:
        rows = [r for r in rows if not bool(r.get("archived"))]
    decorated = [_decorate_account(r) for r in rows]
    decorated = [r for r in decorated if _account_matches_plan_filter(r, plan_filter)]
    decorated = [r for r in decorated if _account_matches_query(r, q)]
    # 按创建时间筛选（date_from/date_to 为 ISO 字符串或 YYYY-MM-DD）
    if date_from or date_to:
        d_from = _parse_iso_dt(date_from)
        d_to = _parse_iso_dt(date_to, end_of_day=True)
        if d_from or d_to:
            filtered = []
            for r in decorated:
                ct = _parse_iso_dt(str(r.get("created_at") or ""))
                if ct is None:
                    continue
                if d_from and ct < d_from:
                    continue
                if d_to and ct > d_to:
                    continue
                filtered.append(r)
            decorated = filtered
    return sorted(decorated, key=lambda x: int(x.get("id") or 0), reverse=True)


def list_account_plan_check_statuses(limit: int = 5000, offset: int = 0, archived: str | bool | None = False, plan_filter: str | None = None, q: str | None = None) -> dict:
    """返回不含 Token/邮箱密码的套餐查询轻量状态快照。"""
    fields = (
        "id", "email", "archived",
        "plan_type", "current_plan_type", "plus_trial_eligible",
        "plan_check_status", "plan_check_ok", "plan_check_error",
        "plan_check_trigger", "plan_check_queued_at", "plan_check_started_at",
        "plan_check_completed_at", "plan_checked_at", "plan_last_success_at",
        "quota_status", "quota_checked_at", "quota_http_status", "quota_error",
        "quota_type", "quota_windows", "quota_last_success_at",
        "plan_check_network_route", "plan_check_proxy_used", "plan_check_proxy_fallback_reason",
        "expires_at", "plan_expires_at", "plan_renews_at", "renews_at",
        "billing_period", "billing_currency", "discount_amount", "discount_type",
        "discount_expires_at", "discount_promo_campaign_id",
        "extract_link_status", "extract_link_ok", "extract_link_type",
        "extract_link_message", "extract_link_error",
        "extract_link_long_url", "extract_link_copy_paste",
        "extract_link_image_url_png", "extract_link_image_url_svg",
        "extract_link_expires_at",
        "codex_status", "codex_error",
    )
    with _LOCK:
        all_rows = _filtered_decorated_accounts(archived=archived, plan_filter=plan_filter, q=q)
        total = len(all_rows)
        limit = max(1, int(limit))
        offset = max(0, int(offset or 0))
        rows = all_rows[offset: offset + limit]
        items = []
        for row in rows:
            item = {"id": row.get("id"), "email": row.get("email")}
            for key in fields:
                value = row.get(key)
                if key in ("id", "email"):
                    continue
                if value is not None and value != "":
                    item[key] = value
            plan = str(row.get("current_plan_type") or row.get("plan_type") or "").lower()
            if not any(x in plan for x in ("plus", "pro", "team", "go")):
                for expire_key in ("expires_at", "plan_expires_at", "plan_renews_at", "renews_at"):
                    item.pop(expire_key, None)
            item["has_access_token"] = bool(str(row.get("access_token") or "").strip())
            items.append(item)
        latest = max((str(row.get("updated_at") or "") for row in all_rows), default="")
        # updated_at 目前只有秒级精度；一次快速查询可能在同一秒内完成
        # queued -> running -> success/failed，导致 revision 不变，前端跳过合并状态，
        # 页面就会一直停在“查询中”。把轻量状态本身纳入签名，保证状态变化可被轮询发现。
        revision_payload = json.dumps(
            [
                {
                    "id": row.get("id"),
                    "updated_at": row.get("updated_at"),
                    "plan_check_status": row.get("plan_check_status"),
                    "plan_check_ok": row.get("plan_check_ok"),
                    "plan_check_error": row.get("plan_check_error"),
                    "current_plan_type": row.get("current_plan_type"),
                    "plan_type": row.get("plan_type"),
                    "plus_trial_eligible": row.get("plus_trial_eligible"),
                    "quota_status": row.get("quota_status"),
                    "quota_checked_at": row.get("quota_checked_at"),
                    "quota_error": row.get("quota_error"),
                    "quota_type": row.get("quota_type"),
                    "quota_windows": row.get("quota_windows"),
                    "extract_link_status": row.get("extract_link_status"),
                    "codex_status": row.get("codex_status"),
                }
                for row in all_rows
            ],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        revision_sig = hashlib.sha1(revision_payload.encode("utf-8")).hexdigest()[:12]
        return {"items": items, "total": total, "offset": offset, "limit": limit, "revision": f"{total}:{latest}:{revision_sig}"}


def list_accounts(limit: int = 500, offset: int = 0, archived: str | bool | None = False, plan_filter: str | None = None, q: str | None = None, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    with _LOCK:
        rows = _filtered_decorated_accounts(archived=archived, plan_filter=plan_filter, q=q, date_from=date_from, date_to=date_to)
        return rows[max(0, int(offset or 0)): max(0, int(offset or 0)) + max(1, int(limit))]


def list_accounts_page(limit: int = 50, offset: int = 0, archived: str | bool | None = False, plan_filter: str | None = None, q: str | None = None, date_from: str | None = None, date_to: str | None = None) -> dict:
    with _LOCK:
        rows = _filtered_decorated_accounts(archived=archived, plan_filter=plan_filter, q=q, date_from=date_from, date_to=date_to)
        total = len(rows)
        limit = max(1, int(limit))
        offset = max(0, int(offset or 0))
        items = rows[offset: offset + limit]
        latest = max((str(row.get("updated_at") or "") for row in rows), default="")
        return {"items": items, "total": total, "offset": offset, "limit": limit, "revision": f"{total}:{latest}"}


def get_account(acc_id: int) -> dict | None:
    # 单行查询而不是加载全表：get_retry_info 之类会对每条任务调一次，
    # 全表读会退化成 N+1。
    row = record_store.get_row(record_store.ACCOUNTS, int(acc_id))
    return _decorate_account(row) if row else None


def get_account_by_email(email: str) -> dict | None:
    row = record_store.get_row_by(record_store.ACCOUNTS, "email", email, lower=True)
    return _decorate_account(row) if row else None


def update_account_note(acc_id: int, note: str) -> bool:
    """更新单个已注册账号备注。note 为空字符串时表示清空备注。"""
    now = _now()
    return _patch_account(acc_id, {
        "note": str(note or ""),
        "note_updated_at": now,
        "updated_at": now,
    })


def update_account_registration_proxy(
    acc_id: int,
    *,
    provider: str | None = None,
    region: str | None = None,
) -> bool:
    """保存账号注册时的代理来源和实际出口国家，供后续账号功能按地区申请新租约。"""
    if record_store.get_row(record_store.ACCOUNTS, int(acc_id)) is None:
        return False
    changes: dict[str, Any] = {"updated_at": _now()}
    if provider is not None:
        changes["registration_proxy_provider"] = str(provider or "").strip() or None
    if region is not None:
        normalized = str(region or "").strip().upper()
        changes["registration_proxy_region"] = normalized if len(normalized) == 2 else None
    return _patch_account(int(acc_id), changes)


def backfill_account_registration_proxy_context() -> int:
    """从历史成功注册任务补齐账号的代理来源/实际国家；已有值不覆盖。"""
    accounts = record_store.list_rows(record_store.ACCOUNTS, order_by="id")
    jobs = record_store.list_rows(record_store.JOBS, order_by="id DESC")
    changed = 0
    for row in accounts:
        if row.get("registration_proxy_provider") and row.get("registration_proxy_region"):
            continue
        account_id = int(row.get("id") or 0)
        email = str(row.get("email") or "").strip().lower()
        job = next((
            item for item in jobs
            if (
                (account_id and int(item.get("account_id") or 0) == account_id)
                or (email and str(item.get("email") or "").strip().lower() == email)
            )
            and (
                str(item.get("proxy_provider") or "").strip()
                or len(str(item.get("proxy_region") or "").strip()) == 2
            )
        ), None)
        if not job:
            continue
        provider = str(job.get("proxy_provider") or "").strip()
        region = str(job.get("proxy_region") or "").strip().upper()
        row_changed = False
        if not row.get("registration_proxy_provider") and provider:
            if record_store.claim_row(
                record_store.ACCOUNTS,
                account_id,
                changes={"registration_proxy_provider": provider, "updated_at": _now()},
                guard="COALESCE(data->>'registration_proxy_provider', '') = %s",
                guard_params=("",),
            ):
                row_changed = True
        if not row.get("registration_proxy_region") and len(region) == 2:
            if record_store.claim_row(
                record_store.ACCOUNTS,
                account_id,
                changes={"registration_proxy_region": region, "updated_at": _now()},
                guard="COALESCE(data->>'registration_proxy_region', '') = %s",
                guard_params=("",),
            ):
                row_changed = True
        if row_changed:
            changed += 1
    return changed


def update_account_deactivation_mail(acc_id: int, result: dict | None = None) -> bool:
    """保存封号邮件扫描状态，不读取或修改 OAuth Token。"""
    result = result or {}
    row = record_store.get_row(record_store.ACCOUNTS, int(acc_id))
    if row is None:
        return False
    now = _now()
    status = str(result.get("status") or "failed")
    changes: dict[str, Any] = {
        "deactivation_mail_scan_status": status,
        "deactivation_mail_scan_trigger": str(result.get("trigger") or ""),
        "updated_at": now,
    }
    if status == "queued":
        changes["deactivation_mail_scan_queued_at"] = now
    elif status == "running":
        changes["deactivation_mail_scan_started_at"] = now
    elif status == "success":
        detected = bool(result.get("detected"))
        # 已确认的封号通知是持久证据，后续缩短回溯窗口不能把它清掉。
        if detected:
            changes["deactivation_mail_detected"] = True
        changes["deactivation_mail_checked_at"] = result.get("checked_at") or now
        changes["deactivation_mail_error"] = None
        if detected:
            changes.update({
                "deactivation_mail_received_at": result.get("received_at") or "",
                "deactivation_mail_subject": str(result.get("subject") or "")[:300],
                "deactivation_mail_sender": str(result.get("sender") or "")[:200],
                "deactivation_mail_message_id": str(result.get("message_id") or "")[:300],
                "deactivation_mail_confidence": str(result.get("confidence") or "high"),
            })
    elif status in {"failed", "unsupported"}:
        changes["deactivation_mail_checked_at"] = result.get("checked_at") or now
        changes["deactivation_mail_error"] = str(result.get("error") or "")[:500]
    return _patch_account(int(acc_id), changes)


def update_account_liveness(acc_id: int, result: dict | None = None) -> bool:
    """写回账号查活结果；成功时同步刷新最新 access_token 和账号基础信息。"""
    result = result or {}
    if record_store.get_row(record_store.ACCOUNTS, int(acc_id)) is None:
        return False
    now = _now()
    ok = bool(result.get("ok"))
    status = str(result.get("status") or ("live" if ok else "failed"))
    changes: dict[str, Any] = {
        "live_check_status": status,
        "live_check_ok": ok,
        "live_checked_at": result.get("checked_at") or now,
        "live_check_error": None if ok else result.get("error"),
        "updated_at": now,
    }
    # 认证路径是账号最近一次刷新 AT 的低敏摘要；密码、TOTP、Token 和
    # 原始响应仍不进入账号行。普通 AT probe 没有 auth_method，不覆盖这组
    # “最近认证”字段，避免查活把刷新 AT 的事实抹掉。
    if result.get("auth_method"):
        changes["last_auth_method"] = str(result.get("auth_method"))[:80]
    if result.get("password_auth_status"):
        changes["last_password_auth_status"] = str(result.get("password_auth_status"))[:40]
    if "fallback_used" in result:
        changes["last_auth_fallback_used"] = bool(result.get("fallback_used"))
    if result.get("error") and result.get("auth_method"):
        changes["last_auth_error_code"] = str(result.get("error"))[:100]
    elif result.get("ok") and result.get("auth_method"):
        changes["last_auth_error_code"] = None
    if result.get("fingerprint"):
        from core.auth_fingerprint import clean_safe_fingerprint_summary, safe_fingerprint_summary_text

        fingerprint = clean_safe_fingerprint_summary(result.get("fingerprint"))
        if fingerprint:
            changes["last_auth_fingerprint"] = fingerprint
            changes["last_auth_fingerprint_text"] = safe_fingerprint_summary_text(fingerprint)
    try:
        changes["live_check_http_status"] = int(result.get("http_status"))
    except (TypeError, ValueError):
        changes["live_check_http_status"] = None

    if status == "deactivated":
        changes.update({
            "account_status": "deactivated",
            "account_status_reason": result.get("error") or "账号已删除/停用/封禁",
            "account_status_at": result.get("checked_at") or now,
            "codex_status": "deactivated",
            "codex_error": result.get("error") or "账号已删除/停用/封禁",
        })

    if ok:
        token = str(result.get("access_token") or "").strip()
        if token:
            changes["access_token"] = token
            from core.chatgpt_plan import token_claims

            claims = token_claims(token)
            changes["token_expires_at"] = claims.get("token_expires_at")
            changes["token_expired"] = claims.get("token_expired")
        session = result.get("session") or {}
        user = session.get("user") or {}
        account = session.get("account") or {}
        if user.get("id"):
            changes["user_id"] = user.get("id")
        if user.get("name") is not None:
            changes["user_name"] = user.get("name")
        if account.get("planType"):
            changes["plan_type"] = account.get("planType")
        if session.get("expires"):
            changes["expires_at"] = session.get("expires")
        if result.get("device_id"):
            changes["device_id"] = result.get("device_id")
        if result.get("proxy_used"):
            changes["live_check_proxy_used"] = result.get("proxy_used")
        changes["live_check_error"] = None
    return _patch_account(int(acc_id), changes)


def mark_account_deactivated(
    acc_id: int,
    reason: str | None = None,
    *,
    source: str | None = None,
) -> bool:
    """Persist a confirmed account deactivation from any account-operation path."""
    normalized_reason = str(reason or "account_deactivated").strip()[:500]
    now = _now()
    changes = {
        "account_status": "deactivated",
        "account_status_reason": normalized_reason,
        "account_status_at": now,
        "codex_status": "deactivated",
        "codex_error": normalized_reason,
        "updated_at": now,
    }
    if source:
        changes["account_status_source"] = str(source).strip()[:80]
    return _patch_account(int(acc_id), changes)


def account_is_deactivated(account: dict | None) -> bool:
    """判断账号是否已被明确标记为封号/停用；历史记录缺字段时视为正常。"""
    return str((account or {}).get("account_status") or "").strip().lower() == "deactivated"


def claim_account_live_check(acc_id: int, trigger: str = "manual") -> bool:
    """原子占用账号查活任务；已有未超时任务或账号已封时返回 False。"""
    now = _now()
    return _claim_account_stage(acc_id, "live_check", {
        "live_check_status": "queued",
        "live_check_ok": False,
        "live_check_trigger": str(trigger or "manual"),
        "live_check_queued_at": now,
        "live_check_started_at": None,
        "live_checked_at": None,
        "live_check_error": None,
        "live_check_http_status": None,
        "updated_at": now,
    }, require_alive=True)


def recover_interrupted_live_checks(
    *, excluded_account_ids: Iterable[int] | None = None,
) -> int:
    """服务启动时恢复上次进程中断的查活状态，避免 queued/running 卡死。"""
    now = _now()
    excluded = sorted({int(item) for item in (excluded_account_ids or ())})
    where = '"live_check_status" IN (%s, %s)'
    params: list[Any] = ["queued", "running"]
    if excluded:
        where += ' AND "id" <> ALL(%s)'
        params.append(excluded)
    recovered = record_store.patch_rows_where(
        record_store.ACCOUNTS,
        changes={
            "live_check_status": "failed",
            "live_check_ok": False,
            "live_check_error": "WebUI 重启或任务异常中断，请重新查活",
            "live_checked_at": now,
            "updated_at": now,
        },
        where=where,
        params=params,
    )
    return recovered


def mark_account_live_check_running(acc_id: int) -> bool:
    """把账号查活任务标记为运行中。"""
    now = _now()
    return _mark_account_stage_running(acc_id, "live_check", {
        "live_check_status": "running",
        "live_check_started_at": now,
        "live_check_error": None,
        "live_check_http_status": None,
        "updated_at": now,
    })


def update_accounts_note(account_ids: list[int] | None, note: str) -> tuple[list[dict], list[dict]]:
    """
    批量更新已注册账号备注。
    返回 (updated, skipped)，updated/skipped 元素含 id/email。
    """
    ids = {int(x) for x in (account_ids or []) if str(x).strip().lstrip("-").isdigit()}
    if not ids:
        return [], []
    now = _now()
    text = str(note or "")
    rows = record_store.patch_rows_where_returning(
        record_store.ACCOUNTS,
        changes={"note": text, "note_updated_at": now, "updated_at": now},
        where="id = ANY(%s)",
        params=(sorted(ids),),
    )
    rows.sort(key=lambda row: int(row.get("id") or 0))
    seen_ids = {int(row["id"]) for row in rows}
    updated = [
        {"id": int(row["id"]), "email": row.get("email"), "note": text, "note_updated_at": now}
        for row in rows
    ]
    skipped = [{"id": item, "reason": "账号不存在"} for item in sorted(ids - seen_ids)]
    return updated, skipped


def archive_account(acc_id: int, archived: bool = True) -> bool:
    """归档/取消归档单个已注册账号。归档不会删除 token，只影响默认账号列表查询。"""
    now = _now()
    changed = record_store.patch_row(record_store.ACCOUNTS, int(acc_id), {
        "archived": bool(archived),
        "archived_at": now if archived else None,
        "updated_at": now,
    })
    return changed


def archive_accounts(account_ids: list[int] | None, archived: bool = True) -> tuple[list[dict], list[dict]]:
    """批量归档/取消归档账号。返回 (updated, skipped)。"""
    ids = {int(x) for x in (account_ids or []) if str(x).strip().lstrip("-").isdigit()}
    if not ids:
        return [], []
    now = _now()
    rows = record_store.patch_rows_where_returning(
        record_store.ACCOUNTS,
        changes={
            "archived": bool(archived),
            "archived_at": now if archived else None,
            "updated_at": now,
        },
        where="id = ANY(%s)",
        params=(sorted(ids),),
    )
    rows.sort(key=lambda row: int(row.get("id") or 0))
    seen_ids = {int(row["id"]) for row in rows}
    updated = [
        {
            "id": int(row["id"]),
            "email": row.get("email"),
            "archived": bool(archived),
            "archived_at": now if archived else None,
        }
        for row in rows
    ]
    skipped = [{"id": item, "reason": "账号不存在"} for item in sorted(ids - seen_ids)]
    return updated, skipped


def count_accounts() -> int:
    return record_store.count_rows(record_store.ACCOUNTS)


def delete_account(acc_id: int | None = None, email: str | None = None) -> bool:
    """删除一个已注册账号记录。"""
    deleted, _ = delete_accounts(
        account_ids=[acc_id] if acc_id is not None else None,
        emails=[email] if email else None,
    )
    return bool(deleted)


def delete_accounts(account_ids: list[int] | None = None, emails: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    """
    批量删除已注册账号。
    返回 (deleted, skipped)，deleted 元素含 id/email。
    """
    ids = {int(x) for x in (account_ids or []) if str(x).strip().isdigit()}
    email_set = {(e or "").lower() for e in (emails or []) if e}
    clauses, params = [], []
    if ids:
        clauses.append("id = ANY(%s)")
        params.append(sorted(ids))
    if email_set:
        clauses.append("lower(email) = ANY(%s)")
        params.append(sorted(email_set))
    if not clauses:
        return [], []
    rows = record_store.delete_rows_where_returning(
        record_store.ACCOUNTS,
        where=" OR ".join(f"({clause})" for clause in clauses),
        params=params,
    )
    rows.sort(key=lambda row: int(row.get("id") or 0))
    deleted = [{"id": int(row["id"]), "email": row.get("email")} for row in rows]
    seen_ids = {int(row["id"]) for row in rows}
    seen_emails = {str(row.get("email") or "").lower() for row in rows}
    skipped = [{"id": item, "reason": "账号不存在"} for item in sorted(ids - seen_ids)]
    skipped += [{"email": item, "reason": "账号不存在"} for item in sorted(email_set - seen_emails)]
    return deleted, skipped


# ============================================================
# outlook_pool
# ============================================================

_POOL_EXPORT_KINDS = {
    record_store.GENERIC_API_POOL.name: "generic_api_emails",
    record_store.DOMAIN_POOL.name: "domain_emails",
}

_POOL_SOURCE_SPECS = {
    "outlook": record_store.OUTLOOK_POOL,
    "generic_api": record_store.GENERIC_API_POOL,
    "cloudflare_domain": record_store.DOMAIN_POOL,
    "icloud_hide": record_store.ICLOUD_HIDE_POOL,
}


def _pool_row_by_email(spec, email: str) -> dict | None:
    return record_store.get_row_by(spec, "email", str(email or "").strip(), lower=True)


def _release_pool_email(spec, email: str, *, status: str, note: str | None = None, extra: dict | None = None) -> bool:
    row = _pool_row_by_email(spec, email)
    if row is None:
        return False
    changes = dict(extra or {})
    changes["status"] = status
    changes["used_at"] = None if status == "available" else row.get("used_at") or _now()
    if note is not None:
        changes["note"] = note
    changed = record_store.patch_row(spec, int(row["id"]), changes)
    kind = _POOL_EXPORT_KINDS.get(spec.name)
    if changed and kind:
        compat_export.schedule(kind)
    return changed


def _delete_pool_email(spec, email: str) -> bool:
    rows = record_store.delete_rows_where_returning(
        spec,
        where="lower(email) = lower(%s)",
        params=(str(email or "").strip(),),
    )
    kind = _POOL_EXPORT_KINDS.get(spec.name)
    if rows and kind:
        compat_export.schedule(kind)
    return bool(rows)


def _pool_summary(spec, statuses: tuple[str, ...]) -> dict:
    result = {status: 0 for status in statuses}
    table = postgres_store.qualified(spec.name)
    from psycopg.rows import dict_row
    record_store.init()
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COALESCE(status, 'available') AS status, COUNT(*) AS count FROM {table} GROUP BY 1")
        rows = cur.fetchall()
    for row in rows:
        result[str(row["status"])] = int(row["count"])
    result["total"] = sum(int(row["count"]) for row in rows)
    return result


def email_pool_secret(source: str, email: str, field: str) -> str:
    """按需读取一条邮箱素材的敏感字段；普通列表永不调用。"""
    spec = _POOL_SOURCE_SPECS.get(str(source or "").strip())
    if spec is None:
        raise ValueError("邮箱来源非法")
    row = _pool_row_by_email(spec, email)
    if row is None:
        raise LookupError("邮箱不存在")
    account = None
    if row.get("registered_account_id"):
        account = record_store.get_row(record_store.ACCOUNTS, int(row["registered_account_id"]))
    if account is None:
        account = record_store.get_row_by(record_store.ACCOUNTS, "email", row.get("email"), lower=True)
    key = str(field or "").strip()
    if key == "access_token":
        return str((account or {}).get("access_token") or row.get("access_token") or "")
    if key == "account_copy_line":
        return _account_line(account) if account else ""
    if key == "copy_line":
        if spec is record_store.OUTLOOK_POOL:
            return _outlook_line(row)
        if spec is record_store.GENERIC_API_POOL:
            return _generic_api_email_line(row)
        return str(row.get("email") or "")
    if key in {"password", "client_id", "refresh_token", "code_url"}:
        return str(row.get(key) or "")
    raise ValueError("不支持的敏感字段")

def import_outlook_accounts(records: list[dict]) -> tuple[int, int]:
    """
    批量导入 Outlook 账号。
    records 元素：{email, password, client_id, refresh_token}
    返回 (新增数, 跳过数)。
    """
    inserted = skipped = 0
    with record_store.transaction() as conn:
        for raw in records:
            email = (raw.get("email") or "").strip()
            if not email:
                skipped += 1
                continue
            now = _now()
            row_id = record_store.insert_row_if_absent(record_store.OUTLOOK_POOL, "email", {
                "email": email,
                "password": (raw.get("password") or "").strip(),
                "client_id": (raw.get("client_id") or raw.get("clientId") or "").strip(),
                "refresh_token": (raw.get("refresh_token") or raw.get("refreshToken") or "").strip(),
                "access_token": (raw.get("access_token") or "").strip(),
                "totp_secret": (raw.get("totp_secret") or "").strip(),
                "status": "available",
                "used_at": None,
                "note": None,
                "imported_at": now,
                "created_at": now,
            }, conn=conn)
            if row_id is None:
                skipped += 1
            else:
                inserted += 1
    return inserted, skipped


def import_registered_email_accounts(records: list[dict], source: str | None) -> tuple[int, int]:
    """
    把邮箱素材直接导入为“已注册成功账号”，用于跳过注册、直接在账号页补跑 Codex 授权。

    source:
      - outlook: records 元素 {email,password,client_id,refresh_token[,access_token,totp_secret]}
      - generic_api: records 元素 {email,code_url[,access_token,totp_secret]}

    返回 (新增账号数, 跳过数)。已存在账号会跳过；邮箱池中已存在的素材会复用并标记 used。
    """
    source = (source or "").strip().lower()
    if source not in ("outlook", "generic_api"):
        raise ValueError("source 必须显式传入 outlook / generic_api")

    record_store.init()
    inserted = skipped = 0
    accounts_changed = outlook_changed = generic_changed = False
    import_note = "导入为已注册账号，用于 Codex 授权"
    with record_store.transaction() as conn:
        for raw in records:
            email = (raw.get("email") or "").strip()
            if not email:
                skipped += 1
                continue

            # 账号唯一性与对应邮箱池的状态变更必须一起判定；事务级业务键锁住
            # 跨进程的“检查后插入”窗口，数据库 identity 负责生成新 ID。
            record_store.advisory_xact_lock(conn, f"registered-account:{email.lower()}")
            if _locked_row_by_email(conn, record_store.ACCOUNTS, email) is not None:
                skipped += 1
                continue

            now = _now()
            original_line = email
            pool_spec = (
                record_store.GENERIC_API_POOL
                if source == "generic_api"
                else record_store.OUTLOOK_POOL
            )
            pool_row = _locked_row_by_email(conn, pool_spec, email)

            if source == "generic_api":
                code_url = (raw.get("code_url") or raw.get("url") or "").strip()
                if not code_url:
                    skipped += 1
                    continue
                pool_changes = {
                    "code_url": code_url,
                    "status": "used",
                    "used_at": (pool_row or {}).get("used_at") or now,
                    "completed_at": (pool_row or {}).get("completed_at") or now,
                    "note": (pool_row or {}).get("note") or import_note,
                }
                if pool_row is None:
                    pool_payload = {"email": email, **pool_changes, "imported_at": now}
                    pool_id = record_store.insert_row(pool_spec, pool_payload, conn=conn)
                    pool_row = {**pool_payload, "id": pool_id}
                else:
                    pool_row = {**pool_row, **pool_changes}
                original_line = _generic_api_email_line(pool_row)
            else:
                password = (raw.get("password") or "").strip()
                client_id = (raw.get("client_id") or raw.get("clientId") or "").strip()
                refresh_token = (raw.get("refresh_token") or raw.get("refreshToken") or "").strip()
                if not (password and client_id and refresh_token):
                    skipped += 1
                    continue
                pool_changes = {
                    "password": password,
                    "client_id": client_id,
                    "refresh_token": refresh_token,
                    "status": "used",
                    "used_at": (pool_row or {}).get("used_at") or now,
                    "completed_at": (pool_row or {}).get("completed_at") or now,
                    "note": (pool_row or {}).get("note") or import_note,
                }
                if pool_row is None:
                    pool_payload = {"email": email, **pool_changes, "imported_at": now}
                    pool_id = record_store.insert_row(pool_spec, pool_payload, conn=conn)
                    pool_row = {**pool_payload, "id": pool_id}
                else:
                    pool_row = {**pool_row, **pool_changes}
                original_line = _outlook_line(pool_row)

            access_token = (raw.get("access_token") or raw.get("token") or "").strip()
            totp_secret = (raw.get("totp_secret") or raw.get("totp") or "").strip() or None
            account = {
                "email": email,
                "created_at": now,
                "access_token": access_token,
                "totp_secret": totp_secret,
                "user_id": raw.get("user_id"),
                "user_name": raw.get("user_name") or "Imported Account",
                "plan_type": raw.get("plan_type"),
                "expires_at": raw.get("expires_at"),
                "device_id": raw.get("device_id"),
                "proxy_used": raw.get("proxy_used"),
                "email_source": source,
                "extra_json": json.dumps({"imported_registered": True}, ensure_ascii=False),
                "codex_status": raw.get("codex_status") or "",
                "codex_error": raw.get("codex_error"),
                "updated_at": now,
                "original_email_line": original_line,
            }
            if source == "outlook":
                account.update({
                    "password": pool_row.get("password"),
                    "client_id": pool_row.get("client_id"),
                    "refresh_token": pool_row.get("refresh_token"),
                })
            account_id = record_store.insert_row(record_store.ACCOUNTS, account, conn=conn)

            pool_changes.update({
                "registered_account_id": account_id,
                "access_token": access_token,
            })
            if totp_secret:
                pool_changes["totp_secret"] = totp_secret
            record_store.patch_row(pool_spec, int(pool_row["id"]), pool_changes, conn=conn)
            inserted += 1
            accounts_changed = True
            if source == "outlook":
                outlook_changed = True
            else:
                generic_changed = True

    if generic_changed:
        compat_export.schedule("generic_api_emails")
    return inserted, skipped


def claim_next_outlook() -> dict | None:
    """原子领取一个可用 Outlook 账号并标记为 used。"""
    row = record_store.claim_next_row(
        record_store.OUTLOOK_POOL,
        changes={"status": "used", "used_at": _now(), "note": None},
        where="status = %s",
        params=("available",),
    )
    return _decorate_outlook(row) if row else None


def release_outlook(email: str, status: str = "available", note: str | None = None) -> bool:
    """把账号状态改回 available，或标记为 used/failed/disabled。"""
    return _release_pool_email(record_store.OUTLOOK_POOL, email, status=status, note=note)


def release_unconsumed_outlook(email: str, note: str | None = None) -> bool:
    """原子回收未生成本地账号且仍为 used 的 Outlook 邮箱。"""
    address = str(email or "").strip()
    changes: dict[str, Any] = {"status": "available", "used_at": None}
    if note is not None:
        changes["note"] = note
    account_table = postgres_store.qualified(record_store.ACCOUNTS.name)
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, f"registered-account:{address.lower()}")
        rows = record_store.patch_rows_where_returning(
            record_store.OUTLOOK_POOL,
            changes=changes,
            where=(
                'lower("email") = lower(%s) AND "status" = %s '
                f"AND NOT EXISTS (SELECT 1 FROM {account_table} a "
                'WHERE lower(a."email") = lower(%s))'
            ),
            params=(address, "used", address),
            conn=conn,
        )
    return bool(rows)


def delete_outlook(email: str) -> bool:
    """从邮箱池彻底删除一个邮箱（按 email 匹配）。返回是否删到。"""
    return _delete_pool_email(record_store.OUTLOOK_POOL, email)


def list_outlook_pool(status: str | None = None, limit: int = 500) -> list[dict]:
    with _LOCK:
        account_by_email = {
            (a.get("email") or "").lower(): a
            for a in _load_accounts()
        }
        rows = _load_outlook()
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows = sorted(rows, key=lambda x: int(x.get("id") or 0), reverse=True)
        return [_decorate_outlook(r, account_by_email) for r in rows[:limit]]


def outlook_pool_summary() -> dict:
    return _pool_summary(record_store.OUTLOOK_POOL, ("available", "used", "failed"))


def get_outlook_by_email(email: str) -> dict | None:
    row = _pool_row_by_email(record_store.OUTLOOK_POOL, email)
    return _decorate_outlook(row) if row else None


# ============================================================
# generic_api email pool
# ============================================================

def import_generic_api_emails(records: list[dict]) -> tuple[int, int]:
    """
    批量导入通用 API 取码邮箱。
    records 元素：{email, code_url}
    返回 (新增数, 跳过数)。
    """
    inserted = skipped = 0
    with record_store.transaction() as conn:
        for raw in records:
            email = (raw.get("email") or "").strip()
            code_url = (raw.get("code_url") or raw.get("url") or "").strip()
            if not email or not code_url:
                skipped += 1
                continue
            now = _now()
            row_id = record_store.insert_row_if_absent(record_store.GENERIC_API_POOL, "email", {
                "email": email,
                "code_url": code_url,
                "access_token": (raw.get("access_token") or "").strip(),
                "totp_secret": (raw.get("totp_secret") or "").strip(),
                "status": "available",
                "used_at": None,
                "note": None,
                "imported_at": now,
                "created_at": now,
            }, conn=conn)
            if row_id is None:
                skipped += 1
            else:
                inserted += 1
    if inserted:
        compat_export.schedule("generic_api_emails")
    return inserted, skipped


def claim_next_generic_api_email() -> dict | None:
    """原子领取一个可用通用 API 邮箱并标记为 used。"""
    row = record_store.claim_next_row(
        record_store.GENERIC_API_POOL,
        changes={"status": "used", "used_at": _now(), "note": None},
        where="status = %s",
        params=("available",),
    )
    if row:
        compat_export.schedule("generic_api_emails")
    return _decorate_generic_api_email(row) if row else None


def release_generic_api_email(email: str, status: str = "available", note: str | None = None) -> bool:
    """把通用 API 邮箱状态改回 available，或标记为 failed/used。"""
    return _release_pool_email(record_store.GENERIC_API_POOL, email, status=status, note=note)


def release_unconsumed_generic_api_email(email: str, note: str | None = None) -> bool:
    """原子回收未生成本地账号且仍为 used 的通用 API 邮箱。"""
    address = str(email or "").strip()
    changes: dict[str, Any] = {"status": "available", "used_at": None}
    if note is not None:
        changes["note"] = note
    account_table = postgres_store.qualified(record_store.ACCOUNTS.name)
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, f"registered-account:{address.lower()}")
        rows = record_store.patch_rows_where_returning(
            record_store.GENERIC_API_POOL,
            changes=changes,
            where=(
                'lower("email") = lower(%s) AND "status" = %s '
                f"AND NOT EXISTS (SELECT 1 FROM {account_table} a "
                'WHERE lower(a."email") = lower(%s))'
            ),
            params=(address, "used", address),
            conn=conn,
        )
    if rows:
        compat_export.schedule("generic_api_emails")
    return bool(rows)


def delete_generic_api_email(email: str) -> bool:
    """从通用 API 邮箱池彻底删除一个邮箱。"""
    return _delete_pool_email(record_store.GENERIC_API_POOL, email)


def list_generic_api_email_pool(status: str | None = None, limit: int = 500) -> list[dict]:
    with _LOCK:
        account_by_email = {
            (a.get("email") or "").lower(): a
            for a in _load_accounts()
        }
        rows = _load_generic_api_emails()
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows = sorted(rows, key=lambda x: int(x.get("id") or 0), reverse=True)
        return [_decorate_generic_api_email(r, account_by_email) for r in rows[:limit]]


def generic_api_email_pool_summary() -> dict:
    return _pool_summary(record_store.GENERIC_API_POOL, ("available", "used", "failed"))


def get_generic_api_email_by_email(email: str) -> dict | None:
    row = _pool_row_by_email(record_store.GENERIC_API_POOL, email)
    return _decorate_generic_api_email(row) if row else None


# ============================================================
# Codex 授权账号（PostgreSQL 是事实来源，codex_accounts/ 仅为兼容导出）
# ============================================================

_CODEX_PLANS = {"free", "plus", "team", "pro", "enterprise"}
_CODEX_STATE_FIELDS = (
    "exported_at", "exported_count", "sub2_uploaded_at", "sub2_uploaded_count",
    "sub2_sync_error", "oauth_refresh_attempted_at", "oauth_refresh_error",
    "archived", "archived_at",
)


def _validate_codex_filename(filename: str) -> str:
    name = str(filename or "").strip()
    if not name.startswith("codex-") or not name.endswith(".json"):
        raise ValueError(f"非法文件名: {filename}")
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError(f"非法文件名: {filename}")
    return name


def _codex_identity(filename: str, content: dict) -> tuple[str, str]:
    without_prefix = Path(filename).stem.removeprefix("codex-")
    parts = without_prefix.rsplit("-", 1)
    inferred_plan = parts[1].lower() if len(parts) == 2 and parts[1].lower() in _CODEX_PLANS else ""
    fallback_email = parts[0] if inferred_plan else without_prefix
    return str(content.get("email") or fallback_email), inferred_plan


def _codex_payload(filename: str, content: dict) -> dict:
    from core.codex_token_refresh_service import oauth_metadata

    rendered = json.dumps(content, ensure_ascii=False, indent=2) + "\n"
    email, plan = _codex_identity(filename, content)
    oauth = oauth_metadata(content)
    now = _now()
    return {
        "filename": filename,
        "email": email,
        "plan": plan,
        "account_id": str(content.get("account_id") or ""),
        "mtime": now,
        "updated_at": now,
        "oauth_status": oauth.get("oauth_status"),
        "oauth_expires_at": oauth.get("oauth_expires_at"),
        # 写入全新的 OAuth 凭证代表完整授权已经成功完成；清掉此前
        # refresh_token 失效留下的重授权标记，避免新凭证仍被显示为“需重授权”。
        # 这些字段位于 JSONB 中，upsert 时会用 null 覆盖旧值。
        "oauth_refresh_attempted_at": None,
        "oauth_refresh_error": None,
        "content": content,
        "type": content.get("type", "codex"),
        "last_refresh": content.get("last_refresh", ""),
        "expired": content.get("expired", ""),
        "access_token_preview": str(content.get("access_token") or "")[:32],
        "size": len(rendered.encode("utf-8")),
        "oauth_seconds_left": oauth.get("oauth_seconds_left"),
        "oauth_refreshable": oauth.get("oauth_refreshable"),
        "oauth_auto_refresh": oauth.get("oauth_auto_refresh"),
    }


def _codex_identity_lock_key(filename: str, content: dict) -> tuple[str, tuple[Any, ...]]:
    """返回 Codex 凭证的大小写不敏感身份和数据库锁参数。"""
    email, plan = _codex_identity(filename, content)
    account_id = str(content.get("account_id") or "").strip()
    if account_id:
        return f"codex-account:{account_id}", ("account_id", account_id)
    plan = str(plan or "").strip().lower()
    return f"codex-email:{email.strip().lower()}:{plan}", ("email_plan", email, plan)


def _upsert_codex_credential_record(filename: str, content: dict) -> int:
    """按账号身份原子保存凭证，并保留 OAuth 返回的邮箱大小写。"""
    payload = _codex_payload(filename, content)
    lock_key, identity = _codex_identity_lock_key(filename, content)
    table = postgres_store.qualified(record_store.CODEX_CREDENTIALS.name)

    with record_store.transaction() as conn, conn.cursor() as cur:
        # 同一账号的不同邮箱大小写会映射到同一 advisory lock，避免两个授权
        # worker 同时查不到旧记录后各自插入一行。
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
        if identity[0] == "account_id":
            cur.execute(
                f"SELECT id FROM {table} WHERE account_id = %s ORDER BY updated_at DESC, id DESC LIMIT 1 FOR UPDATE",
                (identity[1],),
            )
        else:
            cur.execute(
                f"""
                SELECT id FROM {table}
                 WHERE lower(COALESCE(email, '')) = lower(%s)
                   AND lower(COALESCE(plan, '')) = lower(%s)
                 ORDER BY updated_at DESC, id DESC
                 LIMIT 1 FOR UPDATE
                """,
                identity[1:],
            )
        existing = cur.fetchone()
        if existing:
            # 不带 created_at，避免一次重新授权把原始创建时间改掉；其余字段和
            # JSONB 内容使用 patch_row 的服务端合并语义，保留导出/同步统计。
            changes = dict(payload)
            changes.pop("created_at", None)
            record_store.patch_row(
                record_store.CODEX_CREDENTIALS,
                int(existing["id"]),
                changes,
                conn=conn,
            )
            return int(existing["id"])
        return record_store.upsert_row_by(
            record_store.CODEX_CREDENTIALS,
            "filename",
            payload,
            conn=conn,
        )


def _codex_public_row(row: dict) -> dict:
    from core.codex_token_refresh_service import oauth_metadata, refresh_error_requires_reauth, sub2api_status_requires_reauth

    content = row.get("content") if isinstance(row.get("content"), dict) else {}
    oauth = oauth_metadata(content)
    return {
        "filename": row.get("filename"),
        "path": str(_CODEX_DIR / str(row.get("filename") or "")),
        "email": row.get("email") or content.get("email") or "",
        "plan": row.get("plan") or "",
        "account_id": row.get("account_id") or content.get("account_id") or "",
        "type": row.get("type") or content.get("type", "codex"),
        "last_refresh": row.get("last_refresh") or content.get("last_refresh", ""),
        "expired": row.get("expired") or content.get("expired", ""),
        "access_token_preview": row.get("access_token_preview") or str(content.get("access_token") or "")[:32],
        "size": int(row.get("size") or 0),
        "mtime": row.get("mtime") or row.get("updated_at"),
        "exported_at": row.get("exported_at"),
        "exported_count": int(row.get("exported_count") or 0),
        "sub2_uploaded_at": row.get("sub2_uploaded_at"),
        "sub2_uploaded_count": int(row.get("sub2_uploaded_count") or 0),
        "sub2_sync_error": row.get("sub2_sync_error"),
        "sub2api_status": row.get("sub2api_status"),
        "sub2api_http_status": row.get("sub2api_http_status"),
        "oauth_refresh_attempted_at": row.get("oauth_refresh_attempted_at"),
        "oauth_refresh_error": row.get("oauth_refresh_error"),
        "archived": bool(row.get("archived")),
        "archived_at": row.get("archived_at"),
        **oauth,
        "oauth_reauth_required": (
            refresh_error_requires_reauth(row.get("oauth_refresh_error"))
            or sub2api_status_requires_reauth(row.get("sub2api_http_status"))
        ),
    }


def _sync_codex_credentials_collection() -> dict:
    """兼容旧调用：返回数据库行映射；不会扫描目录，也不会在 GET 中写数据。"""
    return {
        str(row.get("filename")): row
        for row in record_store.list_rows(record_store.CODEX_CREDENTIALS, order_by="id")
    }


def _export_codex_credentials() -> None:
    """从数据库重建 CPA 兼容文件和旧导出状态文件。"""
    _CODEX_DIR.mkdir(parents=True, exist_ok=True)
    state: dict[str, dict] = {}
    for row in record_store.list_rows(record_store.CODEX_CREDENTIALS, order_by="id"):
        filename = _validate_codex_filename(str(row.get("filename") or ""))
        content = row.get("content")
        if not isinstance(content, dict):
            continue
        path = _CODEX_DIR / filename
        temporary = path.with_name(path.name + f".tmp.{uuid.uuid4().hex}")
        temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        metadata = {field: row.get(field) for field in _CODEX_STATE_FIELDS if row.get(field) not in (None, False, 0, "")}
        if metadata:
            state[filename] = metadata
    _write_json(_CODEX_EXPORT_STATE, state)


compat_export.register("codex_credentials", _export_codex_credentials)


def save_codex_credential_record(filename: str, content: dict) -> None:
    """原子写入凭证行；兼容文件由后台去抖导出。"""
    name = _validate_codex_filename(filename)
    if not isinstance(content, dict):
        raise ValueError("Codex 凭证必须是 JSON 对象")
    _upsert_codex_credential_record(name, content)
    compat_export.schedule("codex_credentials")


def write_codex_credential(filename: str, content: dict) -> None:
    """覆盖一份数据库中的 Codex 凭证，不依赖兼容文件是否存在。"""
    name = _validate_codex_filename(filename)
    if record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", name) is None:
        raise ValueError(f"凭证不存在: {name}")
    save_codex_credential_record(name, content)


def _load_codex_export_state() -> dict:
    """兼容旧测试/内部调用：导出状态同样从凭证行投影。"""
    result = {}
    for row in record_store.list_rows(record_store.CODEX_CREDENTIALS, order_by="id"):
        state = {field: row.get(field) for field in _CODEX_STATE_FIELDS if field not in {"archived"} and row.get(field) not in (None, "")}
        state["archived"] = bool(row.get("archived"))
        result[str(row.get("filename"))] = state
    return result


def _save_codex_export_state(state: dict) -> None:
    """兼容入口：只更新已存在的凭证行，不再保存独立事实副本。"""
    for filename, changes in (state or {}).items():
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        if row:
            record_store.patch_row(record_store.CODEX_CREDENTIALS, int(row["id"]), dict(changes or {}))
    compat_export.schedule("codex_credentials")


def list_codex_accounts(archived: str | bool | None = "0", date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """读取数据库中的 Codex 凭证元数据；列表请求不访问兼容目录。"""
    where = []
    params: list[Any] = []
    if archived in (True, "1", "true", "yes", "only"):
        where.append("archived IS TRUE")
    elif archived not in ("all", "include"):
        where.append("archived IS FALSE")
    if date_from:
        where.append("LEFT(COALESCE(mtime, updated_at), 10) >= %s")
        params.append(str(date_from)[:10])
    if date_to:
        where.append("LEFT(COALESCE(mtime, updated_at), 10) <= %s")
        params.append(str(date_to)[:10])
    rows = record_store.list_rows(
        record_store.CODEX_CREDENTIALS,
        where=" AND ".join(where),
        params=params,
        order_by="COALESCE(mtime, updated_at) DESC, id DESC",
    )
    return [_codex_public_row(row) for row in rows]


def _codex_row(filename: str) -> dict | None:
    return record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", _validate_codex_filename(filename))


def _patch_codex(filename: str, changes: dict) -> dict | None:
    row = _codex_row(filename)
    if row is None:
        return None
    record_store.patch_row(record_store.CODEX_CREDENTIALS, int(row["id"]), changes)
    compat_export.schedule("codex_credentials")
    return {**row, **changes}


def archive_codex(filename: str, archived: bool = True) -> dict | None:
    now = _now() if archived else None
    row = _patch_codex(filename, {"archived": bool(archived), "archived_at": now})
    return None if row is None else {"archived": bool(archived), "archived_at": now}


def read_codex_credential(filename: str) -> tuple[str, str]:
    name = _validate_codex_filename(filename)
    row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", name)
    content = row.get("content") if row else None
    if not isinstance(content, dict):
        raise ValueError(f"凭证不存在: {name}")
    return json.dumps(content, ensure_ascii=False, indent=2) + "\n", name


def _increment_codex_state(filename: str, *, counter: str, timestamp: str, extra: dict | None = None) -> dict:
    """数据库端原子递增状态计数，避免并发下载互相覆盖。"""
    from psycopg.rows import dict_row

    name = _validate_codex_filename(filename)
    now = _now()
    table = postgres_store.qualified(record_store.CODEX_CREDENTIALS.name)
    promoted_counter = counter == "exported_count"
    extra = dict(extra or {})
    extra[timestamp] = now
    record_store.init()
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        if promoted_counter:
            cur.execute(
                f"UPDATE {table} SET exported_count = exported_count + 1, "
                "data = data || %s::jsonb, updated_at = %s WHERE filename = %s RETURNING *",
                (json.dumps(extra, ensure_ascii=False), now, name),
            )
        else:
            extra_without_counter = dict(extra)
            cur.execute(
                f"UPDATE {table} SET data = data || jsonb_build_object(%s::text, "
                f"COALESCE(NULLIF(data->>(%s::text), '')::BIGINT, 0) + 1) || %s::jsonb, "
                "updated_at = %s WHERE filename = %s RETURNING *",
                (counter, counter, json.dumps(extra_without_counter, ensure_ascii=False), now, name),
            )
        raw = cur.fetchone()
    if raw is None:
        raise ValueError(f"凭证不存在: {name}")
    compat_export.schedule("codex_credentials")
    return record_store.merge_row(record_store.CODEX_CREDENTIALS, raw)


def mark_codex_exported(filename: str) -> dict:
    return _increment_codex_state(filename, counter="exported_count", timestamp="exported_at")


def mark_codex_sub2_uploaded(filename: str) -> dict:
    return _increment_codex_state(
        filename,
        counter="sub2_uploaded_count",
        timestamp="sub2_uploaded_at",
        extra={"sub2_sync_error": None},
    )


def mark_codex_sub2_sync_error(filename: str, error: str | None) -> dict:
    row = _patch_codex(filename, {"sub2_sync_error": str(error or "")[:500] or None})
    if row is None:
        raise ValueError(f"凭证不存在: {filename}")
    return row


def mark_codex_oauth_refresh(filename: str, *, error: str | None = None) -> dict:
    row = _patch_codex(filename, {
        "oauth_refresh_attempted_at": _now(),
        "oauth_refresh_error": str(error or "")[:500] or None,
    })
    if row is None:
        raise ValueError(f"凭证不存在: {filename}")
    return row


def reset_codex_exported(filename: str) -> None:
    row = _patch_codex(filename, {"exported_count": 0, "exported_at": None})
    if row is None:
        raise ValueError(f"凭证不存在: {filename}")


def delete_codex_credential(filename: str) -> bool:
    """删除数据库凭证，并精确删除同名兼容文件；不会递归操作目录。"""
    name = _validate_codex_filename(filename)
    path = _CODEX_DIR / name
    with _LOCK:
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", name)
        if row is None:
            return False
        with record_store.transaction() as conn:
            record_store.delete_rows(record_store.CODEX_CREDENTIALS, [int(row["id"])], conn=conn)
            if path.exists() and path.is_file():
                path.unlink()
        compat_export.schedule("codex_credentials")
        return True


def codex_accounts_summary() -> dict:
    total = record_store.count_rows(record_store.CODEX_CREDENTIALS, where="archived IS FALSE")
    exported = record_store.count_rows(
        record_store.CODEX_CREDENTIALS,
        where="archived IS FALSE AND exported_count > 0",
    )
    return {"total": total, "exported": exported, "pending": total - exported}


# ============================================================
# registration_jobs
# ============================================================

def _new_job_row(
    *,
    email_source: str,
    job_type: str = "registration",
    parent_job_id: int | None = None,
    root_job_id: int | None = None,
    retry_attempt: int = 0,
    retry_action: str | None = None,
    email: str | None = None,
    account_id: int | None = None,
    batch_id: str | None = None,
    batch_index: int | None = None,
    batch_size: int | None = None,
    batch_workers: int | None = None,
    data: dict | None = None,
) -> dict:
    job_uuid = str(uuid.uuid4())
    log_file = task_run_log.build_path(
        task_uuid=job_uuid,
        run_no=max(1, int(retry_attempt or 0) + 1),
        run_uuid=job_uuid,
    )
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    return {
        "job_uuid": job_uuid,
        "job_type": job_type,
        "parent_job_id": parent_job_id,
        "root_job_id": root_job_id,
        "retry_attempt": int(retry_attempt or 0),
        "retry_action": retry_action,
        "email_source": email_source,
        "batch_id": str(batch_id or job_uuid),
        "batch_index": int(batch_index or 1),
        "batch_size": int(batch_size or 1),
        "batch_workers": int(batch_workers or 1),
        "email": email,
        "status": "pending",
        "error_message": None,
        "log_file": log_file,
        "started_at": None,
        "completed_at": None,
        "account_id": account_id,
        "progress_stage": None,
        "progress_updated_at": None,
        "progress_steps": {},
        "data": dict(data or {}),
        "proxy_provider": None,
        "proxy_status": None,
        "proxy_endpoint": None,
        "proxy_exit_ip": None,
        "proxy_region": None,
        "proxy_acquired_at": None,
        "proxy_expires_at": None,
        "created_at": _now_utc(),
    }


def create_job(
    email_source: str,
    *,
    batch_id: str | None = None,
    batch_index: int | None = None,
    batch_size: int | None = None,
    batch_workers: int | None = None,
    data: dict | None = None,
) -> dict:
    """创建一个首次执行的 pending 注册任务。"""
    # 显式 init 是新 schema 首次调用的前置条件；不能把建表责任推迟到
    # _locked_row_by_email/其它业务查询之后。
    record_store.init()
    row = _new_job_row(
        email_source=email_source,
        batch_id=batch_id,
        batch_index=batch_index,
        batch_size=batch_size,
        batch_workers=batch_workers,
        data=data,
    )
    with record_store.transaction() as conn:
        row["id"] = record_store.insert_row(record_store.JOBS, row, conn=conn)
    _ensure_registration_attempt_job(row)
    _sync_operation_job(int(row["id"]))
    return dict(row)


def create_retry_job(
    source_job_id: int,
    *,
    job_type: str,
    email_source: str,
    email: str | None = None,
    account_id: int | None = None,
    batch_id: str | None = None,
    batch_index: int | None = None,
    batch_size: int | None = None,
    batch_workers: int | None = None,
    data: dict | None = None,
) -> tuple[dict, bool]:
    """原子创建重试子任务；同一任务链已有活跃任务时直接复用。"""
    record_store.init()
    source_id = int(source_job_id)
    row: dict | None = None
    with record_store.transaction() as conn:
        source = record_store.get_row(record_store.JOBS, source_id, conn=conn)
        if source is None:
            raise LookupError("任务不存在")
        root_id = int(source.get("root_job_id") or source_id)

        # 只有 retry 创建者需要串行化；事务级 advisory lock 跨进程有效，且不会
        # 把所有任务写入都退化为一个全局锁。拿锁后必须重新读取 source/active，
        # 因为等待期间另一个进程可能已经创建了子任务。
        record_store.advisory_xact_lock(conn, f"registration-retry:{root_id}")
        source = record_store.get_row(record_store.JOBS, source_id, conn=conn)
        if source is None:
            raise LookupError("任务不存在")
        if source.get("status") not in ("success", "failed", "partial_success", "stopped", "cancelled"):
            raise ValueError(f"当前状态不支持重试：{source.get('status')}")

        active_states = ("pending", "running", "stopping")
        placeholders = ", ".join("%s" for _ in active_states)
        active_rows = record_store.list_rows(
            record_store.JOBS,
            where=f'id <> %s AND "root_job_id" = %s AND "status" IN ({placeholders})',
            params=(source_id, root_id, *active_states),
            order_by="id",
            limit=1,
            conn=conn,
        )
        active = active_rows[0] if active_rows else None
        if active is not None:
            if active.get("job_type", "registration") != job_type:
                raise ValueError(f"已有其他类型重试任务 #{active.get('id')} 在排队或运行中")
            return dict(active), False

        history_rows = record_store.list_rows(
            record_store.JOBS,
            where='id = %s OR "root_job_id" = %s',
            params=(root_id, root_id),
            order_by="id",
            conn=conn,
        )
        attempts = []
        for item in history_rows:
            try:
                attempts.append(int(item.get("retry_attempt") or 0))
            except (TypeError, ValueError):
                continue
        row = _new_job_row(
            email_source=email_source,
            job_type=job_type,
            parent_job_id=source_id,
            root_job_id=root_id,
            retry_attempt=(max(attempts) if attempts else 0) + 1,
            retry_action={
                "codex_retry": "codex",
                "twofa_retry": "twofa",
                "registration_resume": "registration_resume",
            }.get(job_type, "registration"),
            email=email,
            account_id=account_id,
            batch_id=batch_id,
            batch_index=batch_index,
            batch_size=batch_size,
            batch_workers=batch_workers,
            data=data,
        )
        row["id"] = record_store.insert_row(record_store.JOBS, row, conn=conn)

    _ensure_registration_attempt_job(row)
    _sync_operation_job(int(row["id"]))
    return dict(row), True


def update_job(
    job_id: int,
    *,
    status: str | None = None,
    email: str | None = None,
    error: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    account_id: int | None = None,
    proxy_provider: str | None = None,
    proxy_status: str | None = None,
    proxy_endpoint: str | None = None,
    proxy_exit_ip: str | None = None,
    proxy_region: str | None = None,
    proxy_acquired_at: str | None = None,
    proxy_expires_at: str | None = None,
) -> None:
    changes = {
        key: value
        for key, value in {
            "status": status,
            "email": email,
            "error_message": error,
            "started_at": started_at,
            "completed_at": completed_at,
            "account_id": account_id,
            "proxy_provider": proxy_provider,
            "proxy_status": proxy_status,
            "proxy_endpoint": proxy_endpoint,
            "proxy_exit_ip": proxy_exit_ip,
            "proxy_region": proxy_region,
            "proxy_acquired_at": proxy_acquired_at,
            "proxy_expires_at": proxy_expires_at,
        }.items()
        if value is not None
    }
    if changes:
        # 任务状态和进度由多个线程同时更新，不能再用全量快照写回；否则停止请求
        # 可能刚写入 stopping，就被另一个线程的旧快照覆盖回 running。
        _patch_job(job_id, changes)


def transition_job_status(
    job_id: int,
    from_statuses: tuple[str, ...] | list[str] | set[str],
    to_status: str,
    **changes,
) -> bool:
    """只在当前状态仍属于 from_statuses 时完成一次状态转换。"""
    allowed = tuple(str(item) for item in from_statuses if str(item))
    if not allowed:
        return False
    placeholders = ", ".join("%s" for _ in allowed)
    changes = dict(changes)
    changes["status"] = str(to_status)
    changed = record_store.claim_row(
        record_store.JOBS,
        int(job_id),
        changes=changes,
        guard=f'"status" IN ({placeholders})',
        guard_params=allowed,
    )
    if changed:
        _sync_operation_job(job_id)
    return changed


def claim_job_for_execution(job_id: int, *, started_at: str | None = None) -> bool:
    """原子领取排队任务；停止/取消先落库时，工作线程不得再启动。"""
    return transition_job_status(
        job_id,
        ("pending",),
        "running",
        started_at=started_at or _now(),
    )


def cancel_pending_jobs(*, batch_id: str | None = None) -> int:
    """一次性取消排队任务；可限定到某个批次。"""
    where = '"status" = %s'
    params: list[Any] = ["pending"]
    if batch_id:
        where += ' AND "batch_id" = %s'
        params.append(str(batch_id))
    candidates = record_store.list_rows(
        record_store.JOBS,
        where=where,
        params=params,
        order_by="id",
    )
    changed = record_store.patch_rows_where(
        record_store.JOBS,
        changes={
            "status": "cancelled",
            "completed_at": _now(),
            "error_message": "用户手动取消",
        },
        where=where,
        params=params,
    )
    for row in candidates:
        _sync_operation_job(int(row["id"]))
    return changed


def update_job_progress(
    job_id: int,
    stage: str,
    state: str = "running",
    detail: str | None = None,
) -> None:
    """原子更新注册阶段；进入新阶段时自动结束仍在运行的前置阶段。"""
    stage = str(stage or "").strip()
    state = str(state or "running").strip().lower()
    if stage not in _JOB_PROGRESS_KEYS:
        raise ValueError(f"未知任务阶段: {stage}")
    if state not in _JOB_PROGRESS_STATES:
        raise ValueError(f"未知阶段状态: {state}")

    with _LOCK:
        row = record_store.get_row(record_store.JOBS, int(job_id))
        if row is None:
            return
        now = _now()
        steps = row.get("progress_steps")
        if not isinstance(steps, dict):
            steps = {}

        current_index = _JOB_PROGRESS_KEYS.index(stage)
        if state == "running":
            for prior_key in _JOB_PROGRESS_KEYS[:current_index]:
                prior = steps.get(prior_key)
                if isinstance(prior, dict) and prior.get("state") == "running":
                    prior["state"] = "success"
                    prior["completed_at"] = now

        route_attempt_no = max(1, int(row.get("route_attempt_no") or 1))
        item = steps.get(stage)
        if not isinstance(item, dict):
            item = {}
        if state == "running" and (
            item.get("state") != "running"
            or int(item.get("route_attempt_no") or route_attempt_no) != route_attempt_no
        ):
            occurrences = item.get("occurrences")
            if not isinstance(occurrences, list):
                occurrences = []
            if item.get("started_at"):
                occurrences.append({
                    key: item.get(key)
                    for key in ("state", "started_at", "completed_at", "detail", "route_attempt_no")
                    if item.get(key) is not None
                })
            item = {
                "state": "running",
                "started_at": now,
                "route_attempt_no": route_attempt_no,
            }
            if occurrences:
                item["occurrences"] = occurrences[-20:]
        elif state in {"success", "failed", "skipped", "stopped"}:
            item["started_at"] = item.get("started_at") or now
            item["completed_at"] = now
            item["route_attempt_no"] = route_attempt_no
        item["state"] = state
        if detail is not None:
            item["detail"] = str(detail)[:300]
        steps[stage] = item
        changes = {
            "progress_steps": steps,
            "progress_stage": stage,
            "progress_updated_at": now,
        }
        if not row.get("route_attempt_no"):
            changes["route_attempt_no"] = route_attempt_no
        _patch_job(job_id, changes)


def begin_job_route_attempt(
    job_id: int,
    *,
    retry_kind: str,
    retry_reason: str | None = None,
) -> int:
    """Start another automatic route attempt without joining stage durations.

    A registration job can rebuild its browser/proxy and execute the same stages
    again.  Preserve the previous route as an immutable summary and clear the
    current-stage projection so the next route receives fresh timestamps.
    """
    with _LOCK:
        row = record_store.get_row(record_store.JOBS, int(job_id))
        if row is None:
            raise LookupError("任务不存在")
        now = _now()
        current_no = max(1, int(row.get("route_attempt_no") or 1))
        steps = row.get("progress_steps")
        if not isinstance(steps, dict):
            steps = {}
        history = row.get("route_attempts")
        if not isinstance(history, list):
            history = []
        started_values = [
            str(item.get("started_at"))
            for item in steps.values()
            if isinstance(item, dict) and item.get("started_at")
        ]
        fallback_started = row.get("started_at")
        if isinstance(fallback_started, datetime):
            fallback_started = fallback_started.isoformat()
        history.append({
            "route_attempt_no": current_no,
            "status": "retried",
            "started_at": min(started_values) if started_values else fallback_started,
            "completed_at": now,
            "retry_kind": str(retry_kind or "automatic_retry")[:80],
            "retry_reason": str(retry_reason or "")[:300] or None,
            "progress_steps": steps,
        })
        next_no = current_no + 1
        _patch_job(job_id, {
            "route_attempt_no": next_no,
            "internal_retry_count": max(0, int(row.get("internal_retry_count") or 0)) + 1,
            "internal_retry_kind": str(retry_kind or "automatic_retry")[:80],
            "internal_retry_last_reason": str(retry_reason or "")[:300] or None,
            "route_attempts": history[-10:],
            "progress_steps": {},
            "progress_stage": None,
            "progress_updated_at": now,
        })
        return next_no


def record_job_otp_evidence(
    job_id: int,
    *,
    request_kind: str | None = None,
    ui_ack: str | None = None,
    detail: str | None = None,
    failure_code: str | None = None,
) -> None:
    """Append redacted OTP request/delivery evidence to one execution row."""
    with _LOCK:
        row = record_store.get_row(record_store.JOBS, int(job_id))
        if row is None:
            return
        events = row.get("otp_evidence")
        if not isinstance(events, list):
            events = []
        event = {
            "recorded_at": _now(),
            "request_kind": str(request_kind or "")[:40] or None,
            "ui_ack": str(ui_ack or "")[:40] or None,
            "detail": str(detail or "")[:240] or None,
        }
        events.append({key: value for key, value in event.items() if value is not None})
        changes = {
            "otp_evidence": events[-20:],
            "otp_request_count": sum(1 for item in events if item.get("request_kind") in {"initial", "resend", "resume_login"}),
        }
        if failure_code:
            changes["otp_failure_code"] = str(failure_code)[:80]
        _patch_job(job_id, changes)


def finish_job_progress(
    job_id: int,
    *,
    success: bool,
    detail: str | None = None,
    failure_state: str = "failed",
) -> None:
    """收口任务进度：保留具体失败节点，并用“完成”节点展示任务总耗时。"""
    with _LOCK:
        row = record_store.get_row(record_store.JOBS, int(job_id))
        if row is None:
            return
        now = _now()
        steps = row.get("progress_steps")
        if not isinstance(steps, dict):
            steps = {}
        current = str(row.get("progress_stage") or "email")
        if current not in _JOB_PROGRESS_KEYS:
            current = "email"

        overall_started_at = row.get("started_at") or row.get("created_at") or now
        work_stage_keys = tuple(key for key in _JOB_PROGRESS_KEYS if key != "complete")

        if success:
            for key in work_stage_keys:
                item = steps.get(key)
                if not isinstance(item, dict) or item.get("state") in {None, "pending"}:
                    # 没有任何流程上报的节点就是没有执行，不能因为任务整体
                    # 成功/部分成功就在 UI 上伪装成“成功 0 秒”。
                    item = {
                        **(item if isinstance(item, dict) else {}),
                        "state": "skipped",
                        "started_at": now,
                        "completed_at": now,
                        "detail": "该步骤未执行",
                    }
                    steps[key] = item
                    continue
                # 已由具体流程上报的终态不能被任务级 success 覆盖；例如账号
                # 注册成功但 Codex 授权失败时，仍应保留失败节点供 UI 提示。
                if item.get("state") not in {"skipped", "success", "failed", "stopped"}:
                    item["state"] = "success"
                item["completed_at"] = item.get("completed_at") or now
                steps[key] = item
        else:
            terminal_state = "stopped" if failure_state == "stopped" else "failed"
            # 套餐查询可能在 Codex 失败后继续成功。此时当前节点已经是 plan_check，
            # 不能把它误改成失败；优先保留流程中真正失败/停止的节点。
            failed_key = next((
                key for key in work_stage_keys
                if isinstance(steps.get(key), dict)
                and steps[key].get("state") in {"failed", "stopped"}
            ), None)
            target_key = failed_key or (current if current != "complete" else "email")
            item = steps.get(target_key)
            if not isinstance(item, dict):
                item = {"started_at": now}
            if item.get("state") not in {"failed", "stopped"}:
                item["state"] = terminal_state
            item["completed_at"] = now
            if detail is not None and not item.get("detail"):
                item["detail"] = str(detail)[:300]
            steps[target_key] = item

            # 失败节点之后、又没有流程上报的步骤均未执行。显式补成 skipped，
            # 避免终态任务仍显示一串“待执行”的编号节点。
            target_index = work_stage_keys.index(target_key)
            for key in work_stage_keys[target_index + 1:]:
                later = steps.get(key)
                if isinstance(later, dict) and later.get("state") not in {None, "pending"}:
                    continue
                steps[key] = {
                    **(later if isinstance(later, dict) else {}),
                    "state": "skipped",
                    "started_at": now,
                    "completed_at": now,
                    "detail": "前置步骤未完成，未执行",
                }

        complete_state = "success" if success else ("stopped" if failure_state == "stopped" else "failed")
        complete_item = steps.get("complete")
        if not isinstance(complete_item, dict):
            complete_item = {}
        complete_item.update({
            "state": complete_state,
            "started_at": overall_started_at,
            "completed_at": now,
            "detail": (
                "任务已完成"
                if success
                else str(detail or ("任务已停止" if complete_state == "stopped" else "任务失败"))[:300]
            ),
        })
        steps["complete"] = complete_item
        _patch_job(job_id, {
            "progress_stage": "complete",
            "progress_steps": steps,
            "progress_updated_at": now,
        })


def recover_interrupted_registration_jobs(
    *,
    excluded_account_ids: Iterable[int] | None = None,
    excluded_source_ids: Iterable[str | int] | None = None,
) -> int:
    """启动时把上个进程遗留的排队/运行任务收口为可重试失败状态。"""
    record_store.init()
    detail = "WebUI 进程重启导致任务中断；浏览器和接码资源将在启动恢复阶段回收，请重新执行任务"
    now = _now()
    recovered_rows: list[dict] = []
    account_changed = False
    active_states = ("pending", "running", "stopping")
    placeholders = ", ".join("%s" for _ in active_states)
    excluded_accounts = sorted({int(item) for item in (excluded_account_ids or ())})
    excluded_sources = sorted({str(item).strip() for item in (excluded_source_ids or ()) if str(item).strip()})
    where_parts = [f'"status" IN ({placeholders})']
    where_params: list[Any] = list(active_states)
    if excluded_accounts:
        where_parts.append('("account_id" IS NULL OR "account_id" <> ALL(%s))')
        where_params.append(excluded_accounts)
    if excluded_sources:
        where_parts.append('"id"::text <> ALL(%s)')
        where_params.append(excluded_sources)
    with record_store.transaction() as conn:
        rows = record_store.list_rows(
            record_store.JOBS,
            where=" AND ".join(where_parts),
            params=where_params,
            order_by="id",
            conn=conn,
        )
        for row in rows:
            current = str(row.get("progress_stage") or "email")
            if current not in _JOB_PROGRESS_KEYS:
                current = "email"
            steps = row.get("progress_steps")
            if not isinstance(steps, dict):
                steps = {}
            item = steps.get(current)
            if not isinstance(item, dict):
                item = {"started_at": row.get("started_at") or now}
            item.update({"state": "failed", "detail": detail[:300], "completed_at": now})
            steps[current] = item
            changes: dict[str, Any] = {
                "status": "failed",
                "error_message": detail,
                "completed_at": now,
                "progress_steps": steps,
                "progress_stage": current,
                "progress_updated_at": now,
            }
            if row.get("proxy_status") in {"acquiring", "leased"}:
                changes["proxy_status"] = "interrupted"
            if not record_store.claim_row(
                record_store.JOBS,
                int(row["id"]),
                changes=changes,
                guard=f'"status" IN ({placeholders})',
                guard_params=active_states,
                conn=conn,
            ):
                # 另一个进程已经收口/领取了这行；不能把它的更新覆盖回旧状态。
                continue
            recovered_row = dict(row)
            recovered_row.update(changes)
            recovered_rows.append(recovered_row)

            if str(row.get("job_type") or "") == "codex_retry":
                email = str(row.get("email") or "").strip()
                account = record_store.get_row_by(
                    record_store.ACCOUNTS, "email", email, lower=True, conn=conn,
                ) if email else None
                if account is not None and str(account.get("codex_status") or "") == "retrying":
                    account_changed = record_store.claim_row(
                        record_store.ACCOUNTS,
                        int(account["id"]),
                        changes={
                            "codex_status": "failed",
                            "codex_error": "WebUI 进程重启导致 Codex OAuth 中断，请重新补跑",
                            "updated_at": now,
                        },
                        guard='"codex_status" = %s',
                        guard_params=("retrying",),
                        conn=conn,
                    ) or account_changed

    recovered = len(recovered_rows)
    for row in recovered_rows:
        _sync_operation_job(int(row["id"]))
    try:
        from core.storage import registration

        registration.recover_interrupted_runs(
            excluded_account_ids=excluded_accounts,
            excluded_source_ids=excluded_sources,
        )
    except Exception:
        logger.exception("恢复 RegistrationRun 失败")
    return recovered


def list_jobs(limit: int = 100) -> list[dict]:
    return record_store.list_rows(record_store.JOBS, order_by="id DESC", limit=max(1, int(limit)))


def get_job(job_id: int) -> dict | None:
    return record_store.get_row(record_store.JOBS, int(job_id))


def get_latest_registration_job_for_account(account_id: int) -> dict | None:
    """Find the newest registration execution that can be resumed for an account."""
    rows = record_store.list_rows(
        record_store.JOBS,
        where='"account_id" = %s AND "job_type" IN (%s, %s)',
        params=(int(account_id), "registration", "registration_resume"),
        order_by='"id" DESC',
        limit=1,
    )
    return rows[0] if rows else None


def count_registration_jobs_by_batch_email(batch_id: str, email: str) -> int:
    """统计一个批次里已经写入某邮箱的注册任务数。

    这一步用于兼容批次邮箱去重表上线前已经存在的任务：即使旧任务没有对应的
    claim 行，也不能再把同一个邮箱发给当前批次的新任务。
    """
    batch = str(batch_id or "").strip()
    address = str(email or "").strip().lower()
    if not batch or not address:
        return 0
    return record_store.count_rows(
        record_store.JOBS,
        where='"batch_id" = %s AND lower("email") = %s',
        params=(batch, address),
    )


def claim_registration_batch_email(
    batch_id: str,
    email: str,
    *,
    job_id: int | None = None,
    email_source: str | None = None,
) -> bool:
    """原子登记批次邮箱，返回该邮箱是否首次出现在此批次。

    领取失败后邮箱池仍可回收，但 claim 记录故意保留到批次结束，避免后续排队任务
    再拿到同一地址。claim_key 使用规范化邮箱，大小写差异也视为重复。
    """
    batch = str(batch_id or "").strip()
    address = str(email or "").strip().lower()
    if not batch or not address:
        return True

    # 先检查历史 registration_jobs，覆盖该保护上线前已经产生的重复任务。
    if count_registration_jobs_by_batch_email(batch, address) > 0:
        return False

    claimed_at = _now()
    claim_key = f"{batch}\x1f{address}"
    row_id = record_store.insert_row_if_absent(
        record_store.REGISTRATION_BATCH_EMAIL_CLAIMS,
        "claim_key",
        {
            "claim_key": claim_key,
            "batch_id": batch,
            "email": address,
            "job_id": int(job_id) if job_id is not None else None,
            "email_source": str(email_source or "").strip() or None,
            "claimed_at": claimed_at,
        },
    )
    return row_id is not None


def get_successful_retry_for_job(job_id: int) -> dict | None:
    """返回同一任务链中已成功的其他重试任务，用于保留原任务历史状态并阻止重复重试。

    条件下推到 SQL：get_retry_info 会对列表里每一条任务调用本函数，全表扫描
    在这里会退化成 N+1。root_job_id 上有索引。
    """
    source = record_store.get_row(record_store.JOBS, int(job_id))
    if source is None:
        return None
    root_id = int(source.get("root_job_id") or source.get("id") or 0)
    matches = record_store.list_rows(
        record_store.JOBS,
        where='"root_job_id" = %s AND "status" = %s AND id <> %s',
        params=(root_id, "success", int(job_id)),
        order_by="id DESC",
        limit=1,
    )
    return matches[0] if matches else None


def get_successful_retries_for_jobs(jobs: list[dict]) -> dict[int, dict]:
    """一次查询返回每条任务同链上的成功重试，供管理列表批量投影。"""
    rows = [row for row in (jobs or []) if row.get("id") is not None]
    if not rows:
        return {}
    roots = sorted({int(row.get("root_job_id") or row.get("id") or 0) for row in rows})
    successes = record_store.list_rows(
        record_store.JOBS,
        where='"root_job_id" = ANY(%s) AND "status" = %s',
        params=(roots, "success"),
        order_by="id DESC",
    )
    by_root: dict[int, list[dict]] = {}
    for success in successes:
        root_id = int(success.get("root_job_id") or success.get("id") or 0)
        by_root.setdefault(root_id, []).append(success)
    out: dict[int, dict] = {}
    for row in rows:
        job_id = int(row["id"])
        root_id = int(row.get("root_job_id") or job_id)
        match = next((item for item in by_root.get(root_id, []) if int(item.get("id") or 0) != job_id), None)
        if match is not None:
            out[job_id] = match
    return out


def get_accounts_for_jobs(jobs: list[dict]) -> dict[int, dict]:
    """按 account_id / email 批量关联账号；最多两次 SQL，不做逐任务查找。"""
    rows = [row for row in (jobs or []) if row.get("id") is not None]
    if not rows:
        return {}
    account_ids = sorted({int(row["account_id"]) for row in rows if row.get("account_id") is not None})
    emails = sorted({str(row.get("email") or "").strip().lower() for row in rows if str(row.get("email") or "").strip()})
    accounts: list[dict] = []
    if account_ids:
        accounts.extend(record_store.list_rows(
            record_store.ACCOUNTS,
            where="id = ANY(%s)",
            params=(account_ids,),
            order_by="id DESC",
        ))
    # emails 是排序后的 list；用集合差避免已经按 id 找到的账号重复查询。
    found_emails = {str(account.get("email") or "").strip().lower() for account in accounts}
    missing_emails = [email for email in emails if email not in found_emails]
    if missing_emails:
        accounts.extend(record_store.list_rows(
            record_store.ACCOUNTS,
            where="lower(email) = ANY(%s)",
            params=(missing_emails,),
            order_by="id DESC",
        ))
    decorated = [_decorate_account(account) for account in accounts]
    by_id = {int(account["id"]): account for account in decorated}
    by_email = {str(account.get("email") or "").strip().lower(): account for account in decorated}
    out: dict[int, dict] = {}
    for row in rows:
        account = by_id.get(int(row["account_id"])) if row.get("account_id") is not None else None
        if account is None:
            account = by_email.get(str(row.get("email") or "").strip().lower())
        if account is not None:
            out[int(row["id"])] = account
    return out


def delete_job(job_id: int, *, delete_log: bool = True, allow_running: bool = False) -> bool:
    """
    删除一个注册任务记录；默认同时删除该任务日志文件。返回是否删除到记录。
    默认不删除 running 任务，避免后台线程仍在执行但前端记录消失。
    """
    deleted, _skipped = delete_jobs(
        [job_id], delete_log=delete_log, allow_running=allow_running
    )
    return bool(deleted)


def delete_jobs(job_ids: list[int], *, delete_log: bool = True, allow_running: bool = False) -> tuple[list[dict], list[dict]]:
    """一条 SQL 批量删除任务；状态判断与删除原子完成。"""
    ids = {int(value) for value in (job_ids or [])}
    if not ids:
        return [], []
    where = "id = ANY(%s)"
    params: list[Any] = [sorted(ids)]
    if not allow_running:
        where += " AND COALESCE(status, '') NOT IN ('running', 'stopping')"
    rows = record_store.delete_rows_where_returning(
        record_store.JOBS,
        where=where,
        params=params,
    )
    seen = {int(row["id"]) for row in rows}
    missing = ids - seen
    current = {
        int(row["id"]): row
        for row in record_store.list_rows(
            record_store.JOBS,
            where="id = ANY(%s)",
            params=(sorted(missing),),
            order_by="id",
        )
    } if missing else {}
    skipped = [
        {
            "id": job_id,
            "reason": "运行中，不能删除" if current.get(job_id, {}).get("status") in {"running", "stopping"} else "任务不存在",
        }
        for job_id in sorted(missing)
    ]
    if rows:
        try:
            from core import operation_task_store

            operation_task_store.mark_registration_jobs_deleted(int(row["id"]) for row in rows)
        except Exception:
            logger.exception("标记统一任务来源已删除失败：job_ids=%s", sorted(seen))
    if delete_log:
        for row in rows:
            log_file = row.get("log_file")
            if not log_file:
                continue
            try:
                Path(str(log_file)).unlink(missing_ok=True)
            except Exception:
                pass
    return rows, skipped


# ============================================================
# 迁移与路径
# ============================================================


def migrate_legacy_files() -> dict:
    """
    把历史 accounts/*.json、outlook_accounts.txt、outlook_accounts_used.json
    迁移到当前 PostgreSQL 主存储及兼容导出文件。多次调用是幂等的。
    """
    summary = {
        "accounts_imported": 0,
        "outlook_imported": 0,
        "outlook_skipped": 0,
    }
    accounts_dir = _PROJECT_ROOT / "accounts"
    if accounts_dir.exists():
        for jf in accounts_dir.glob("*.json"):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if not data.get("email") or not data.get("access_token"):
                    continue
                extra = data.get("extra") or {}
                user = extra.get("user") or {}
                account = extra.get("account") or {}
                insert_account(
                    email=data["email"],
                    access_token=data["access_token"],
                    totp_secret=data.get("totp_secret"),
                    user_id=user.get("id"),
                    user_name=user.get("name"),
                    plan_type=account.get("planType"),
                    expires_at=extra.get("expires"),
                    device_id=extra.get("device_id"),
                    extra=extra,
                )
                summary["accounts_imported"] += 1
            except Exception:
                continue

    for txt in (_PROJECT_ROOT / "outlook_accounts.txt",):
        if txt.exists():
            records = []
            for line in txt.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("----")
                # 支持 4 段或 6 段格式
                if len(parts) == 4:
                    email, password, client_id, refresh_token = (p.strip() for p in parts)
                elif len(parts) == 6:
                    email, password, client_id, refresh_token, _, _ = (p.strip() for p in parts)
                else:
                    continue
                records.append({
                    "email": email,
                    "password": password,
                    "client_id": client_id,
                    "refresh_token": refresh_token,
                })
            ins, skip = import_outlook_accounts(records)
            summary["outlook_imported"] += ins
            summary["outlook_skipped"] += skip

    used = _PROJECT_ROOT / "outlook_accounts_used.json"
    if used.exists():
        try:
            emails = json.loads(used.read_text(encoding="utf-8"))
            for email in emails:
                release_outlook(email, status="used")
        except Exception:
            pass

    return summary


def db_path() -> Path:
    """兼容旧名称，返回当前文件存储目录。"""
    return _DATA_DIR


def storage_paths() -> dict:
    return {
        "logs_dir": str(_LOG_DIR),
    }


# ============================================================
# Domain email pool（Cloudflare 域名邮箱跟踪）
# ============================================================

_DOMAIN_EMAIL_JSON = _PROJECT_ROOT / "用于注册的域名邮箱.json"


def _load_domain_pool() -> list[dict]:
    return _load_table(record_store.DOMAIN_POOL)


def _export_domain_pool() -> None:
    rows = _load_domain_pool()
    _write_json(_DOMAIN_EMAIL_JSON, rows)


def _save_domain_pool(rows: list[dict]) -> None:
    _sync_table(record_store.DOMAIN_POOL, rows)
    compat_export.schedule("domain_emails")


def _find_domain_email(rows: list[dict], email: str) -> dict | None:
    target = (email or "").lower()
    return next((r for r in rows if (r.get("email") or "").lower() == target), None)


def claim_next_domain_email(email: str) -> dict:
    """记录一个新的域名邮箱地址到池中（标记为 available）。"""
    target = str(email or "").strip()
    existing = _pool_row_by_email(record_store.DOMAIN_POOL, target)
    if existing:
        return existing
    row_id = record_store.upsert_row_by(record_store.DOMAIN_POOL, "email", {
        "email": target,
        "status": "available",
        "used_at": None,
        "note": None,
        "created_at": _now(),
    })
    compat_export.schedule("domain_emails")
    return record_store.get_row(record_store.DOMAIN_POOL, row_id) or {}


def release_domain_email(email: str, status: str = "available", note: str | None = None) -> bool:
    """更新域名邮箱状态。"""
    return _release_pool_email(record_store.DOMAIN_POOL, email, status=status, note=note)


def release_unconsumed_domain_email(email: str, note: str | None = None) -> bool:
    """原子回收未生成本地账号且仍为 used 的域名邮箱。"""
    address = str(email or "").strip()
    changes: dict[str, Any] = {"status": "available", "used_at": None}
    if note is not None:
        changes["note"] = note
    account_table = postgres_store.qualified(record_store.ACCOUNTS.name)
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, f"registered-account:{address.lower()}")
        rows = record_store.patch_rows_where_returning(
            record_store.DOMAIN_POOL,
            changes=changes,
            where=(
                'lower("email") = lower(%s) AND "status" = %s '
                f"AND NOT EXISTS (SELECT 1 FROM {account_table} a "
                'WHERE lower(a."email") = lower(%s))'
            ),
            params=(address, "used", address),
            conn=conn,
        )
    if rows:
        compat_export.schedule("domain_emails")
    return bool(rows)


def get_domain_email_by_email(email: str) -> dict | None:
    return _pool_row_by_email(record_store.DOMAIN_POOL, email)


def list_domain_email_pool(status: str | None = None, limit: int = 500) -> list[dict]:
    with _LOCK:
        rows = sorted(_load_domain_pool(), key=lambda x: int(x.get("id") or 0), reverse=True)
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return [dict(r) for r in rows[:limit]]


def domain_email_pool_summary() -> dict:
    return _pool_summary(record_store.DOMAIN_POOL, ("available", "used", "failed"))


def delete_domain_email(email: str) -> bool:
    """从域名邮箱池删除一个邮箱。"""
    return _delete_pool_email(record_store.DOMAIN_POOL, email)


# ============================================================
# iCloud Hide My Email pool（本地状态镜像）
# ============================================================

def _load_icloud_hide_pool() -> list[dict]:
    return _load_table(record_store.ICLOUD_HIDE_POOL)


def _save_icloud_hide_pool(rows: list[dict]) -> None:
    _sync_table(record_store.ICLOUD_HIDE_POOL, rows)


def _find_icloud_hide_email(rows: list[dict], email: str) -> dict | None:
    target = (email or "").strip().lower()
    return next((r for r in rows if (r.get("email") or "").strip().lower() == target), None)


def sync_icloud_hide_aliases(aliases: list[dict], account_id: str, *, full_snapshot: bool = True) -> dict:
    """把 sidecar 返回的 HME 别名同步到本地池，保留本地领取/失败状态。"""
    record_store.init()
    account_key = str(account_id or "").strip()
    now = _now()
    inserted = updated = disabled = 0
    remote_emails: set[str] = set()
    with record_store.transaction() as conn:
        for raw in aliases or []:
            email = str(raw.get("email") or "").strip()
            if not email or "@" not in email:
                continue
            normalized_email = email.lower()
            remote_emails.add(normalized_email)
            active = bool(raw.get("active", True))

            # 与 insert_account 使用同一个业务键，避免同步恰好跨过账号创建提交
            # 时把已注册别名误判成 available。
            record_store.advisory_xact_lock(conn, f"registered-account:{normalized_email}")
            registered = record_store.get_row_by(
                record_store.ACCOUNTS, "email", email, lower=True, conn=conn,
            ) is not None
            row = _locked_row_by_email(conn, record_store.ICLOUD_HIDE_POOL, email)
            if row is None:
                status = "used" if registered else ("available" if active else "disabled")
                payload = {
                    "email": email,
                    "status": status,
                    "used_at": now if status == "used" else None,
                    "note": None,
                    "account_id": account_key,
                    "anonymous_id": str(raw.get("anonymousId") or raw.get("anonymous_id") or "").strip(),
                    "label": str(raw.get("label") or "").strip(),
                    "remote_created_at": str(raw.get("createdAt") or raw.get("created_at") or "").strip(),
                    "remote_active": active,
                    "synced_at": now,
                }
                row_id = record_store.insert_row(
                    record_store.ICLOUD_HIDE_POOL, payload, conn=conn,
                )
                row = {**payload, "id": row_id}
                inserted += 1
            else:
                updated += 1

            changes: dict[str, Any] = {
                "account_id": account_key,
                "anonymous_id": str(raw.get("anonymousId") or raw.get("anonymous_id") or "").strip(),
                "label": str(raw.get("label") or "").strip(),
                "remote_created_at": str(raw.get("createdAt") or raw.get("created_at") or "").strip(),
                "remote_active": active,
                "synced_at": now,
            }
            remove_data_keys: tuple[str, ...] = ()
            if registered:
                changes.update({
                    "status": "used",
                    "used_at": row.get("used_at") or now,
                })
                remove_data_keys = ("disabled_reason",)
            elif not active and row.get("status") == "available":
                changes.update({
                    "status": "disabled",
                    "disabled_reason": "remote_inactive",
                })
                disabled += 1
            elif (
                active
                and row.get("status") == "disabled"
                and (
                    row.get("disabled_reason") in {"remote_inactive", "remote_missing"}
                    # Older forward-target compatibility checks disabled the
                    # row without recording a reason. Once the remote alias
                    # is active again, treat that legacy route-only state as
                    # recoverable; explicit/manual disables remain disabled.
                    or (not row.get("disabled_reason") and not row.get("note"))
                )
            ):
                changes.update({
                    "status": "available",
                    "used_at": None,
                })
                remove_data_keys = ("disabled_reason",)
            record_store.patch_row(
                record_store.ICLOUD_HIDE_POOL,
                int(row["id"]),
                changes,
                conn=conn,
                remove_data_keys=remove_data_keys,
            )

        if full_snapshot:
            existing_rows = record_store.list_rows(
                record_store.ICLOUD_HIDE_POOL,
                where='"account_id" = %s',
                params=(account_key,),
                order_by="id",
                conn=conn,
            )
            for row in existing_rows:
                if str(row.get("email") or "").strip().lower() in remote_emails:
                    continue
                if row.get("status") == "available":
                    record_store.patch_row(
                        record_store.ICLOUD_HIDE_POOL,
                        int(row["id"]),
                        {
                            "status": "disabled",
                            "disabled_reason": "remote_missing",
                            "remote_active": False,
                            "synced_at": now,
                        },
                        conn=conn,
                    )
                    disabled += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "disabled": disabled,
        "total": record_store.count_rows(record_store.ICLOUD_HIDE_POOL),
    }


def claim_next_icloud_hide_email(
    account_id: str | None = None,
    *,
    account_ids: list[str] | None = None,
) -> dict | None:
    """原子领取一个已同步且仍激活的 iCloud 隐藏邮箱。"""
    if account_ids is not None:
        normalized_ids = [str(value or "").strip() for value in account_ids if str(value or "").strip()]
        if not normalized_ids:
            return None
    else:
        normalized_ids = None
    where = ["status = %s", "COALESCE(data->>'remote_active', 'true') <> 'false'"]
    params: list[Any] = ["available"]
    if account_id:
        where.append("account_id = %s")
        params.append(str(account_id))
    if normalized_ids is not None:
        where.append("account_id = ANY(%s)")
        params.append(normalized_ids)
    row = record_store.claim_next_row(
        record_store.ICLOUD_HIDE_POOL,
        changes={"status": "used", "used_at": _now(), "note": None},
        where=" AND ".join(where),
        params=params,
    )
    return row


def release_icloud_hide_email(email: str, status: str = "available", note: str | None = None) -> bool:
    """更新 HME 别名的本地池状态；不会停用或删除 Apple 侧地址。"""
    extra = {"disabled_reason": "manual" if status == "disabled" else None}
    return _release_pool_email(record_store.ICLOUD_HIDE_POOL, email, status=status, note=note, extra=extra)


def release_unconsumed_icloud_hide_email(email: str, note: str | None = None) -> bool:
    """原子回收未生成本地账号且仍为 used 的 HME 别名。"""
    address = str(email or "").strip()
    changes: dict[str, Any] = {"status": "available", "used_at": None}
    if note is not None:
        changes["note"] = note
    account_table = postgres_store.qualified(record_store.ACCOUNTS.name)
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, f"registered-account:{address.lower()}")
        rows = record_store.patch_rows_where_returning(
            record_store.ICLOUD_HIDE_POOL,
            changes=changes,
            where=(
                'lower("email") = lower(%s) AND "status" = %s '
                "AND COALESCE(data->>'remote_active', 'true') <> 'false' "
                f"AND NOT EXISTS (SELECT 1 FROM {account_table} a "
                'WHERE lower(a."email") = lower(%s))'
            ),
            params=(address, "used", address),
            conn=conn,
        )
    return bool(rows)


def get_icloud_hide_email_by_email(email: str) -> dict | None:
    return _pool_row_by_email(record_store.ICLOUD_HIDE_POOL, email)


def list_icloud_hide_email_pool(status: str | None = None, limit: int = 500) -> list[dict]:
    with _LOCK:
        rows = sorted(_load_icloud_hide_pool(), key=lambda x: int(x.get("id") or 0), reverse=True)
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return [dict(row) for row in rows[:limit]]


def icloud_hide_email_pool_summary() -> dict:
    return _pool_summary(record_store.ICLOUD_HIDE_POOL, ("available", "used", "failed", "disabled"))


def icloud_hide_email_pool_summary_by_account(account_ids: list[str] | None = None) -> list[dict]:
    """按 sidecar 账号汇总本地 HME 别名池状态。"""
    normalized_ids = None
    if account_ids is not None:
        normalized_ids = [str(value or "").strip() for value in account_ids if str(value or "").strip()]
        if not normalized_ids:
            return []

    table = postgres_store.qualified(record_store.ICLOUD_HIDE_POOL.name)
    from psycopg.rows import dict_row

    where = ""
    params: tuple[Any, ...] = ()
    if normalized_ids is not None:
        where = ' WHERE "account_id" = ANY(%s)'
        params = (normalized_ids,)
    record_store.init()
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            f'''SELECT COALESCE("account_id", '') AS account_id,
                       COALESCE(status, 'available') AS status,
                       COUNT(*) AS count
                  FROM {table}{where}
                 GROUP BY 1, 2
                 ORDER BY 1, 2''',
            params,
        )
        rows = cur.fetchall()

    statuses = ("available", "used", "failed", "disabled")
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        account_key = str(row["account_id"] or "")
        item = grouped.setdefault(
            account_key,
            {"account_id": account_key, **{status: 0 for status in statuses}, "total": 0},
        )
        status = str(row["status"] or "available")
        count = int(row["count"] or 0)
        if status not in item:
            item[status] = 0
        item[status] += count
        item["total"] += count
    return [grouped[key] for key in sorted(grouped)]


def delete_icloud_hide_email(email: str) -> bool:
    """只删除 turb 的本地镜像；Apple 侧别名不受影响，下次同步可能重新出现。"""
    return _delete_pool_email(record_store.ICLOUD_HIDE_POOL, email)


compat_export.register("domain_emails", _export_domain_pool)
