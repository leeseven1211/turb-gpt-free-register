"""Persistent, HME-only result delivery. Importing this module does no work.

The original endpoint, credential reference and payload are immutable snapshots.
Registration commits its local result and this event in one transaction; only the
runtime worker performs HTTP. Ordinary mailbox lease mutations are never queued.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from core import postgres_store, record_store

logger = logging.getLogger(__name__)
_IGNORED = {"request_unknown", "unknown", "running", "reserved", "available"}
_SUCCESS = {"used", "success", "succeeded", "registered"}
_LEASE_SECONDS = 120
_worker_lock = threading.Lock()
_worker: threading.Thread | None = None
_stop = threading.Event()


def _table():
    return postgres_store.qualified(record_store.EMAIL_USAGE_REPORTS.name)


def _address(value):
    return str(value or "").strip().lower()


def _lock(cursor, address):
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ("email-usage:" + address,))


def has_success(email, *, cursor=None):
    if cursor is None:
        with record_store.transaction() as conn, conn.cursor() as current:
            return has_success(email, cursor=current)
    # This is also the local result's success guard. Wait for an in-flight
    # success enqueue before allowing a caller to commit a later failure.
    _lock(cursor, _address(email))
    cursor.execute(f"SELECT 1 FROM {_table()} WHERE address_norm = %s AND result = 'ok' LIMIT 1", (_address(email),))
    return bool(cursor.fetchone())


def _route(address, source, row, cursor):
    """Resolve only exact persisted identities; never consult current config."""
    row = dict(row or {})
    conn = cursor.connection
    legacy_identity = str(row.get("acquisition_id") or "") if _address(row.get("address")) == address else ""
    profile_id = row.get("local_inbox_profile_id") or row.get("inbox_profile_id") or (row.get("derivation_policy") or {}).get("inbox_profile_id")
    if not profile_id:
        allocations = record_store.list_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS,
            where="LOWER(address) = %s", params=(address,), limit=1, conn=conn)
        if allocations:
            profile_id = allocations[0].get("inbox_profile_id")
            legacy_identity = str(allocations[0].get("acquisition_id") or "")
    profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, int(profile_id), conn=conn) if profile_id else None
    if profile is None and not profile_id:
        from core.email_butler_client import _hme_profile_key
        profiles = record_store.list_rows(record_store.EMAIL_INBOX_PROFILES,
            where="inbox_key = %s", params=(_hme_profile_key(address),), order_by="revision DESC", limit=1, conn=conn)
        profile = profiles[0] if profiles else None
    if profile:
        identity = profile.get("butler_identity") or {}
        if profile.get("connector") != "forward_butler" or (source != "icloud_hide" and identity.get("provider") != "icloud_hme" and row.get("provider") != "icloud_hme"):
            return None
        locator = profile.get("inbox_locator") or {}
        if _address(identity.get("email")) != address:
            identity = {}
        return {"profile_id": profile["id"], "api_base": str(locator.get("api_base") or ""),
            "credential_ref": str(profile.get("credential_ref") or ""), "identity": identity,
            "operation_identity": legacy_identity,
            "route_state": profile.get("state"), "handoff": row.get("butler_handoff") or {}}
    # Historical confirmed HME claims retain their original connection even if
    # they predate fixed inbox profiles.
    intents = record_store.list_rows(record_store.EMAIL_BUTLER_CLAIM_INTENTS,
        where="address_norm = %s AND status = 'claimed'", params=(address,), order_by="id DESC", limit=1, conn=conn)
    if intents:
        intent = intents[0]
        mailbox = intent.get("mailbox") or {}
        if mailbox.get("provider") == "icloud_hme":
            return {"profile_id": None, "api_base": intent["api_base"], "credential_ref": intent["credential_ref"],
                "identity": {"acquisition_id": intent["acquisition_id"]}, "route_state": "active", "handoff": {}}
    if profile_id and source == "icloud_hide":
        return {"profile_id": profile_id, "api_base": "", "credential_ref": "", "identity": {},
            "route_state": "missing", "handoff": row.get("butler_handoff") or {}}
    return None


def enqueue(email, *, status, source, row=None, claim=None, cursor=None):
    """Enqueue within the caller's transaction, or create one for legacy callers."""
    state, address = str(status or "").strip().lower(), _address(email)
    if not address or state in _IGNORED:
        return None
    if cursor is None:
        with record_store.transaction() as conn, conn.cursor() as current:
            return enqueue(address, status=state, source=source, row=row, claim=claim, cursor=current)
    route = _route(address, source, row, cursor)
    if route is None:
        return None
    _lock(cursor, address)
    result = "ok" if state in _SUCCESS else "provider_error"
    if result != "ok" and has_success(address, cursor=cursor):
        return None
    handoff = route["handoff"]
    identity = str(handoff.get("acquisition_id") or route.get("operation_identity") or route["identity"].get("acquisition_id") or address)
    operation_id = hashlib.sha256(f"turb-hme:{identity}:{result}".encode()).hexdigest()
    event_key = hashlib.sha256(f"{route['api_base']}:{operation_id}".encode()).hexdigest()
    payload = {"email": address, "status": result, "service": "openai", "consumer": "turb-gpt-register",
        "message": "Turb registration result: " + ("used" if result == "ok" else "failed"), "operation_id": operation_id}
    # Remote permanent handoff ownership is unrelated to the local task owner.
    for key in ("acquisition_id", "owner_kind", "owner_id"):
        if handoff.get(key):
            payload[key] = str(handoff[key])
    if result == "ok":
        cursor.execute(f"UPDATE {_table()} SET state = 'superseded', updated_at = %s "
            "WHERE address_norm = %s AND result <> 'ok' AND state IN ('pending', 'blocked')",
            (record_store._now(), address))
    rows = record_store.list_rows(record_store.EMAIL_USAGE_REPORTS, where="event_key = %s", params=(event_key,), conn=cursor.connection)
    if rows:
        return rows[0]
    blocked = route["route_state"] != "active" or not route["api_base"] or not route["credential_ref"]
    event_id = record_store.insert_row(record_store.EMAIL_USAGE_REPORTS, {
        "event_key": event_key, "operation_id": operation_id, "address_norm": address, "source": source,
        "result": result, "state": "blocked" if blocked else "pending", "attempts": 0,
        "profile_id": route["profile_id"], "api_base": route["api_base"], "credential_ref": route["credential_ref"],
        "payload": payload, "last_error": "fixed_route_unavailable" if blocked else None,
    }, conn=cursor.connection)
    return record_store.get_row(record_store.EMAIL_USAGE_REPORTS, event_id, conn=cursor.connection)


def record_legacy_result(email, *, status, source="icloud_hide", note=None):
    """Atomically retain an old child allocation and its exact HME report."""
    address, state = _address(email), str(status or "").strip().lower()
    with record_store.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)} "
            "WHERE LOWER(address) = %s AND source = %s ORDER BY id LIMIT 1 FOR UPDATE", (address, source))
        row = record_store.merge_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, cur.fetchone())
        if not row:
            return False
        if state in _IGNORED:
            return True
        _lock(cur, address)
        if state not in _SUCCESS and has_success(address, cursor=cur):
            return True
        changes = {"last_task_outcome": "used" if state in _SUCCESS else state}
        if state in _SUCCESS:
            changes["state"] = "used"
        elif state == "replaced":
            changes["state"] = "replaced"
        elif state in {"disabled", "retired"}:
            changes["state"] = "retired"
        record_store.patch_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, row["id"], changes, conn=conn)
        enqueue(address, status=state, source=source, row=row, cursor=cur)
        return True


def _claim_next():
    with record_store.transaction() as conn, conn.cursor() as cur:
        # Take the address advisory lock before any event row lock, matching
        # enqueue. A persisted sending lease spans the HTTP call after commit.
        cur.execute(f"SELECT id, address_norm FROM {_table()} WHERE "
            "(state = 'pending' AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())) "
            "OR (state = 'sending' AND lease_until <= NOW()) ORDER BY id LIMIT 50")
        candidates = list(cur.fetchall())
        for candidate in candidates:
            address = candidate["address_norm"]
            cur.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s, 0)) AS locked", ("email-usage:" + address,))
            if not cur.fetchone()["locked"]:
                continue
            cur.execute(f"SELECT * FROM {_table()} WHERE id = %s AND "
                "((state = 'pending' AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())) "
                "OR (state = 'sending' AND lease_until <= NOW())) FOR UPDATE SKIP LOCKED", (candidate["id"],))
            row = record_store.merge_row(record_store.EMAIL_USAGE_REPORTS, cur.fetchone())
            if not row:
                continue
            if row["result"] != "ok" and has_success(address, cursor=cur):
                record_store.patch_row(record_store.EMAIL_USAGE_REPORTS, row["id"], {"state": "superseded"}, conn=conn)
                continue
            cur.execute(f"SELECT 1 FROM {_table()} WHERE address_norm = %s AND id <> %s "
                "AND state = 'sending' AND lease_until > NOW() LIMIT 1", (address, row["id"]))
            if cur.fetchone():
                continue
            changes = {"state": "sending", "lease_owner": uuid.uuid4().hex,
                "lease_until": datetime.now(timezone.utc) + timedelta(seconds=_LEASE_SECONDS), "attempts": row["attempts"] + 1}
            record_store.patch_row(record_store.EMAIL_USAGE_REPORTS, row["id"], changes, conn=conn)
            return {**row, **changes}
    return None


def _finish(event, *, delivered=False, blocked=False, error=None):
    with record_store.transaction() as conn, conn.cursor() as cur:
        _lock(cur, event["address_norm"])
        cur.execute(f"SELECT * FROM {_table()} WHERE id = %s AND state = 'sending' AND lease_owner = %s FOR UPDATE",
            (event["id"], event["lease_owner"]))
        current = cur.fetchone()
        if not current:
            return
        state = "delivered" if delivered else "blocked" if blocked else "pending"
        if event["result"] != "ok" and has_success(event["address_norm"], cursor=cur):
            state = "superseded"
        delay = min(3600, 5 * (2 ** min(int(event["attempts"]), 10)))
        record_store.patch_row(record_store.EMAIL_USAGE_REPORTS, event["id"], {
            "state": state, "lease_owner": None, "lease_until": None,
            "next_attempt_at": datetime.now(timezone.utc) + timedelta(seconds=delay) if state == "pending" else None,
            "delivered_at": datetime.now(timezone.utc) if delivered else None, "last_error": error,
        }, conn=conn)


def dispatch_once():
    """Deliver one claimed event using one bounded, idempotent HTTP attempt."""
    event = _claim_next()
    if not event:
        return False
    try:
        from config.runtime import read_persisted_values
        from core import email_butler_client as butler
        parsed = urlsplit(event["api_base"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            _finish(event, blocked=True, error="fixed_route_unavailable")
            return True
        reference = event["credential_ref"]
        key = str(read_persisted_values().get(reference) or os.environ.get(reference) or "").strip()
        if not key:
            _finish(event, blocked=True, error="original_credential_missing")
            return True
        butler._request("POST", "/identities/report", json=event["payload"], api_base=event["api_base"], api_key=key, timeout=10)
    except Exception as exc:
        code = getattr(exc, "status_code", None)
        blocked = isinstance(code, int) and 400 <= code < 500 and code not in {408, 425, 429}
        # Exception text may contain URL credentials, mailbox data or OTPs.
        _finish(event, blocked=blocked, error=f"http_{code}" if isinstance(code, int) else "delivery_unavailable")
    else:
        _finish(event, delivered=True)
    return True


def worker_status():
    counts = {state: 0 for state in ("pending", "sending", "delivered", "blocked", "superseded")}
    with record_store.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT state, count(*) AS n FROM {_table()} GROUP BY state")
        for row in cur.fetchall():
            if row["state"] in counts:
                counts[row["state"]] = int(row["n"])
    return {"alive": bool(_worker and _worker.is_alive()), "counts": counts}


def _run_worker():
    while not _stop.is_set():
        try:
            if dispatch_once():
                continue
        except Exception as exc:
            logger.warning("HME result worker unavailable (%s)", type(exc).__name__)
        _stop.wait(3)


def start_worker():
    global _worker
    with _worker_lock:
        if _worker and _worker.is_alive():
            return False
        record_store.init()
        _stop.clear()
        _worker = threading.Thread(target=_run_worker, name="email-usage-reports", daemon=True)
        _worker.start()
        return True
