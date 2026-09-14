# -*- coding: utf-8 -*-
"""Unauthenticated process liveness and database/worker readiness probes.

``webui.runtime.runtime_status()`` is the only worker-state dependency. The
current read-only contract is ``ready``, ``started``, ``pid``, ``started_at``,
and the four component mappings ``executor``, ``codex_dispatcher``,
``dependency_dispatcher`` and ``projection_worker``. The three dispatcher /
projection components are required to report boolean ``started`` and
``alive`` (or an explicit ``healthy``) values. A missing component, an error,
or a dead thread is never ready. The executor is lazy and may be absent, but
an executor error is still a readiness failure.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask import jsonify

from core import postgres_store
from webui import runtime
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext

_REQUIRED_RUNTIME_WORKER_KEYS = (
    "codex_dispatcher",
    "dependency_dispatcher",
    "projection_worker",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _database_check() -> dict[str, Any]:
    """Run a cheap read-only PostgreSQL probe without returning connection data."""
    try:
        if not postgres_store.database_url():
            return {"ok": False, "status": "unconfigured", "error": "database_url_missing"}
        with postgres_store.connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        if row != (1,):
            return {"ok": False, "status": "failed", "error": "database_probe_invalid"}
        return {"ok": True, "status": "ok"}
    except Exception as exc:  # pragma: no cover - exact driver errors vary by platform
        return {"ok": False, "status": "failed", "error": f"{type(exc).__name__}"}


def _component_check(name: str, value: object, *, required: bool) -> dict[str, Any]:
    """Validate one process-local worker state without exposing its payload."""
    if value is None and not required:
        return {"ok": True, "status": "lazy"}
    if not isinstance(value, dict):
        return {"ok": False, "status": "missing" if required else "invalid", "error": f"{name}_status_invalid"}
    if value.get("error") not in (None, "", False, 0, {}):
        return {"ok": False, "status": "failed", "error": f"{name}_error"}
    if not required:
        return {"ok": True, "status": "available"}

    started = value.get("started") is True
    if "alive" in value:
        alive = value.get("alive") is True
    elif "healthy" in value:
        alive = value.get("healthy") is True
    else:
        alive = False
    result: dict[str, Any] = {
        "ok": started and alive,
        "status": "ok" if started and alive else "not_ready",
        "started": started,
        "alive": alive,
    }
    if isinstance(value.get("name"), str):
        result["name"] = value["name"]
    if not started:
        result["error"] = f"{name}_not_started"
    elif not alive:
        result["error"] = f"{name}_not_alive"
    return result


def _runtime_check() -> dict[str, Any]:
    """Normalize runtime state and require every critical dispatcher thread."""
    status_reader = getattr(runtime, "runtime_status", None)
    if not callable(status_reader):
        return {"ok": False, "status": "unavailable", "error": "runtime_status_missing"}
    try:
        raw = status_reader()
    except Exception as exc:  # pragma: no cover - defensive boundary for worker diagnostics
        return {"ok": False, "status": "failed", "error": f"{type(exc).__name__}"}
    if not isinstance(raw, dict):
        return {"ok": False, "status": "invalid", "error": "runtime_status_not_object"}

    started = raw.get("started") is True
    runtime_ready = raw.get("ready") is True
    component_results = {
        name: _component_check(name, raw.get(name), required=True)
        for name in _REQUIRED_RUNTIME_WORKER_KEYS
    }
    executor_result = _component_check("executor", raw.get("executor"), required=False)
    workers_ready = all(bool(result.get("ok")) for result in component_results.values())
    errors = [
        str(result["error"])
        for result in component_results.values()
        if result.get("error")
    ]
    if executor_result.get("error"):
        errors.append(str(executor_result["error"]))
    if raw.get("error") not in (None, "", False, 0, {}):
        errors.append("runtime_error")
    ready = started and runtime_ready and workers_ready and executor_result["ok"] and not errors
    result: dict[str, Any] = {
        "ok": ready,
        "status": "ok" if ready else "not_ready",
        "started": started,
        "runtime_ready": runtime_ready,
        "workers_ready": workers_ready,
        "workers": component_results,
        "executor": executor_result,
    }
    if isinstance(raw.get("pid"), int) and not isinstance(raw.get("pid"), bool):
        result["pid"] = int(raw["pid"])
    started_at = raw.get("started_at")
    if isinstance(started_at, (int, float)) and not isinstance(started_at, bool):
        result["started_at"] = float(started_at)
    elif started_at is not None:
        result["started_at"] = str(started_at)
    if not started:
        result["error"] = "runtime_not_started"
    elif not runtime_ready:
        result["error"] = "runtime_not_ready"
    elif not workers_ready:
        result["error"] = errors[0] if errors else "workers_not_ready"
    elif not executor_result["ok"]:
        result["error"] = str(executor_result.get("error") or "executor_not_ready")
    elif errors:
        result["error"] = errors[0]
    return result


def _readiness_payload() -> tuple[dict[str, Any], int]:
    database = _database_check()
    worker_runtime = _runtime_check()
    ready = bool(database.get("ok")) and bool(worker_runtime.get("ok"))
    return (
        {
            "ok": ready,
            "status": "ready" if ready else "not_ready",
            "checked_at": _utc_now(),
            "checks": {
                "database": database,
                "runtime": worker_runtime,
            },
        },
        200 if ready else 503,
    )


def create_health_blueprint(_context: WebUIContext):
    """Create public health endpoints used by process managers and release checks."""
    blueprint = LegacyEndpointBlueprint("health", __name__)

    @blueprint.get("/healthz")
    def healthz():
        """Return process liveness without touching PostgreSQL or workers."""
        return jsonify({"ok": True, "status": "alive", "checked_at": _utc_now()})

    @blueprint.get("/readyz")
    def readyz():
        """Return database and worker readiness with an honest HTTP status."""
        payload, status_code = _readiness_payload()
        return jsonify(payload), status_code

    return blueprint
