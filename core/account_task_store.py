# -*- coding: utf-8 -*-
"""账号操作任务实例存储。

这里只保存任务状态、阶段事件和脱敏后的结果摘要。账号密码、AT、验证码、
邮箱正文和带凭据的代理地址均不写入该库。
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _PROJECT_ROOT / "data" / "account_tasks.db"
_LOCK = threading.RLock()
_READY_PATH: Path | None = None

_TERMINAL_STATUSES = {"success", "failed", "deactivated", "unsupported", "cancelled", "interrupted"}
_SECRET_KEY_PARTS = ("password", "otp", "secret", "authorization", "cookie")
_PROXY_CREDENTIAL_RE = re.compile(r"(?P<scheme>https?://)[^/@\s]+@", re.IGNORECASE)
_PROXY_AUTH_RE = re.compile(r"(?<![\w/])[^\s:@/]+:[^\s@/]+@")
_PROXY_FOUR_PART_RE = re.compile(r"(?P<endpoint>(?:\d{1,3}\.){3}\d{1,3}:\d+):[^:\s]+:[^:\s]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}\b")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init() -> None:
    global _READY_PATH
    with _LOCK:
        resolved = _DB_PATH.resolve()
        if _READY_PATH == resolved and _DB_PATH.exists():
            return
        with _connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS account_action_batches (
                    id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    total_count INTEGER NOT NULL DEFAULT 0,
                    queued_count INTEGER NOT NULL DEFAULT 0,
                    running_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS account_action_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_uuid TEXT NOT NULL UNIQUE,
                    batch_id TEXT,
                    task_type TEXT NOT NULL,
                    account_id INTEGER,
                    email_snapshot TEXT NOT NULL DEFAULT '',
                    trigger TEXT NOT NULL,
                    status TEXT NOT NULL,
                    validation_method TEXT,
                    network_route TEXT,
                    proxy_mode TEXT,
                    proxy_provider TEXT,
                    proxy_region TEXT,
                    proxy_used TEXT,
                    result_summary_json TEXT,
                    error TEXT,
                    queued_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    duration_ms INTEGER,
                    FOREIGN KEY(batch_id) REFERENCES account_action_batches(id)
                );

                CREATE TABLE IF NOT EXISTS account_action_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    message TEXT NOT NULL,
                    detail_json TEXT,
                    FOREIGN KEY(task_id) REFERENCES account_action_tasks(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_account_tasks_created
                    ON account_action_tasks(id DESC);
                CREATE INDEX IF NOT EXISTS idx_account_tasks_account
                    ON account_action_tasks(account_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_account_tasks_status
                    ON account_action_tasks(status, id DESC);
                CREATE INDEX IF NOT EXISTS idx_account_task_events_task
                    ON account_action_events(task_id, id);
                """
            )
        _READY_PATH = resolved


def _redact_text(value: object, limit: int = 1000) -> str:
    text = str(value or "")
    text = _PROXY_CREDENTIAL_RE.sub(r"\g<scheme>***@", text)
    text = _JWT_RE.sub("[REDACTED_AT]", text)
    return text[:limit]


def _redact_proxy(value: object) -> str:
    text = _redact_text(value, 220)
    text = _PROXY_AUTH_RE.sub("***:***@", text)
    return _PROXY_FOUR_PART_RE.sub(r"\g<endpoint>:***:***", text)


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if isinstance(value, dict):
        out = {}
        for raw_key, raw_value in list(value.items())[:80]:
            key = str(raw_key)
            lowered = key.lower()
            if (
                any(part in lowered for part in _SECRET_KEY_PARTS)
                or lowered in {"token", "access_token", "refresh_token", "id_token"}
                or lowered.endswith("_access_token")
                or lowered.endswith("_refresh_token")
            ):
                continue
            if lowered in {"proxy", "proxy_url", "proxy_used"}:
                out[key[:80]] = _redact_proxy(raw_value)
                continue
            out[key[:80]] = _scrub(raw_value, depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_scrub(item, depth + 1) for item in list(value)[:80]]
    if isinstance(value, (str, bytes)):
        return _redact_text(value, 1000)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(value, 300)


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(_scrub(value), ensure_ascii=False, separators=(",", ":"))


def _decode_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    for key in ("result_summary_json", "detail_json"):
        if key not in item:
            continue
        raw = item.pop(key)
        target = key.removesuffix("_json")
        try:
            item[target] = json.loads(raw) if raw else None
        except (TypeError, ValueError):
            item[target] = None
    return item


def create_batch(*, action_type: str, trigger: str, total_count: int) -> str:
    init()
    batch_id = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute(
            """INSERT INTO account_action_batches
               (id, action_type, trigger, total_count, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (batch_id, str(action_type), str(trigger), max(0, int(total_count)), _now()),
        )
    return batch_id


def create_task(
    *,
    task_type: str,
    account_id: int | None,
    email: str,
    trigger: str,
    batch_id: str | None = None,
) -> int:
    init()
    now = _now()
    with _connect() as conn:
        cursor = conn.execute(
            """INSERT INTO account_action_tasks
               (task_uuid, batch_id, task_type, account_id, email_snapshot, trigger, status, queued_at)
               VALUES (?, ?, ?, ?, ?, ?, 'queued', ?)""",
            (
                uuid.uuid4().hex,
                batch_id,
                str(task_type or "unknown")[:60],
                int(account_id) if account_id is not None else None,
                str(email or "")[:320],
                str(trigger or "manual")[:80],
                now,
            ),
        )
        task_id = int(cursor.lastrowid)
        conn.execute(
            """INSERT INTO account_action_events
               (task_id, created_at, level, stage, message)
               VALUES (?, ?, 'INFO', 'queued', ?)""",
            (task_id, now, "任务已加入队列"),
        )
        _refresh_batch(conn, batch_id)
    return task_id


def append_event(
    task_id: int | None,
    *,
    stage: str,
    message: str,
    level: str = "INFO",
    detail: dict | None = None,
) -> None:
    if not task_id:
        return
    init()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO account_action_events
               (task_id, created_at, level, stage, message, detail_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                int(task_id),
                _now(),
                str(level or "INFO").upper()[:16],
                str(stage or "event")[:80],
                _redact_text(message, 1200),
                _json(detail),
            ),
        )


def start_task(task_id: int | None, *, message: str = "开始执行") -> None:
    if not task_id:
        return
    init()
    now = _now()
    with _connect() as conn:
        row = conn.execute("SELECT batch_id FROM account_action_tasks WHERE id=?", (int(task_id),)).fetchone()
        if row is None:
            return
        conn.execute(
            "UPDATE account_action_tasks SET status='running', started_at=? WHERE id=?",
            (now, int(task_id)),
        )
        conn.execute(
            """INSERT INTO account_action_events
               (task_id, created_at, level, stage, message)
               VALUES (?, ?, 'INFO', 'running', ?)""",
            (int(task_id), now, _redact_text(message, 1200)),
        )
        _refresh_batch(conn, row["batch_id"])


def _duration_ms(started_at: str | None, finished_at: str) -> int | None:
    if not started_at:
        return None
    try:
        return max(0, int((datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000))
    except (TypeError, ValueError):
        return None


def finish_task(
    task_id: int | None,
    *,
    status: str,
    message: str,
    error: str | None = None,
    result_summary: dict | None = None,
    route: dict | None = None,
    validation_method: str | None = None,
) -> None:
    if not task_id:
        return
    init()
    final_status = str(status or "failed").lower()
    if final_status not in _TERMINAL_STATUSES:
        final_status = "failed"
    now = _now()
    route = _scrub(route or {})
    with _connect() as conn:
        row = conn.execute(
            "SELECT batch_id, started_at FROM account_action_tasks WHERE id=?",
            (int(task_id),),
        ).fetchone()
        if row is None:
            return
        conn.execute(
            """UPDATE account_action_tasks SET
               status=?, validation_method=?, network_route=?, proxy_mode=?, proxy_provider=?,
               proxy_region=?, proxy_used=?, result_summary_json=?, error=?, finished_at=?, duration_ms=?
               WHERE id=?""",
            (
                final_status,
                str(validation_method or "")[:80] or None,
                str(route.get("network_route") or "")[:80] or None,
                str(route.get("proxy_mode") or "")[:80] or None,
                str(route.get("proxy_provider") or "")[:80] or None,
                str(route.get("proxy_region") or "")[:80] or None,
                _redact_proxy(route.get("proxy_used")) or None,
                _json(result_summary),
                _redact_text(error, 1200) or None,
                now,
                _duration_ms(row["started_at"], now),
                int(task_id),
            ),
        )
        conn.execute(
            """INSERT INTO account_action_events
               (task_id, created_at, level, stage, message, detail_json)
               VALUES (?, ?, ?, 'complete', ?, ?)""",
            (
                int(task_id),
                now,
                "ERROR" if final_status in {"failed", "interrupted"} else "INFO",
                _redact_text(message, 1200),
                _json(result_summary),
            ),
        )
        _refresh_batch(conn, row["batch_id"])


def _refresh_batch(conn: sqlite3.Connection, batch_id: str | None) -> None:
    if not batch_id:
        return
    counts = {
        str(row["status"]): int(row["n"])
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM account_action_tasks WHERE batch_id=? GROUP BY status",
            (batch_id,),
        )
    }
    queued = counts.get("queued", 0)
    running = counts.get("running", 0)
    success = counts.get("success", 0)
    failed = sum(counts.get(key, 0) for key in ("failed", "deactivated", "unsupported", "cancelled", "interrupted"))
    completed_at = _now() if queued == 0 and running == 0 and (success + failed) > 0 else None
    conn.execute(
        """UPDATE account_action_batches SET queued_count=?, running_count=?, success_count=?,
           failed_count=?, completed_at=? WHERE id=?""",
        (queued, running, success, failed, completed_at, batch_id),
    )


def recover_interrupted() -> int:
    init()
    now = _now()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, batch_id, started_at FROM account_action_tasks WHERE status IN ('queued','running')"
        ).fetchall()
        for row in rows:
            conn.execute(
                """UPDATE account_action_tasks SET status='interrupted', error=?, finished_at=?, duration_ms=?
                   WHERE id=?""",
                (
                    "WebUI 重启导致任务中断，请重新执行",
                    now,
                    _duration_ms(row["started_at"], now),
                    int(row["id"]),
                ),
            )
            conn.execute(
                """INSERT INTO account_action_events
                   (task_id, created_at, level, stage, message)
                   VALUES (?, ?, 'ERROR', 'interrupted', ?)""",
                (int(row["id"]), now, "WebUI 重启导致任务中断，请重新执行"),
            )
        for batch_id in {row["batch_id"] for row in rows if row["batch_id"]}:
            _refresh_batch(conn, batch_id)
    return len(rows)


def list_tasks(
    *,
    page: int = 1,
    page_size: int = 50,
    task_type: str = "",
    status: str = "",
    q: str = "",
) -> dict:
    init()
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))
    where: list[str] = []
    params: list[Any] = []
    if task_type:
        where.append("task_type=?")
        params.append(str(task_type))
    if status:
        where.append("status=?")
        params.append(str(status))
    if q:
        where.append("(email_snapshot LIKE ? OR CAST(account_id AS TEXT) LIKE ? OR CAST(id AS TEXT) LIKE ?)")
        needle = f"%{str(q).strip()}%"
        params.extend((needle, needle, needle))
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    offset = (page - 1) * page_size
    with _connect() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM account_action_tasks{clause}", params).fetchone()[0])
        rows = conn.execute(
            f"SELECT * FROM account_action_tasks{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        ).fetchall()
    return {
        "ok": True,
        "items": [_decode_row(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_task(task_id: int) -> dict | None:
    init()
    with _connect() as conn:
        task = conn.execute("SELECT * FROM account_action_tasks WHERE id=?", (int(task_id),)).fetchone()
        if task is None:
            return None
        events = conn.execute(
            "SELECT * FROM account_action_events WHERE task_id=? ORDER BY id",
            (int(task_id),),
        ).fetchall()
    item = _decode_row(task) or {}
    item["events"] = [_decode_row(row) for row in events]
    return item
