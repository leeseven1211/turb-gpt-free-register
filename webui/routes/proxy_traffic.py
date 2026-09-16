# -*- coding: utf-8 -*-
"""Authenticated, read-only proxy lease and browser traffic APIs."""
from __future__ import annotations

from flask import jsonify, request

from core import browser_traffic, proxy_lease_store
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext


def _optional_int_arg(name: str) -> int | None:
    raw = str(request.args.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc


def _common_filters() -> dict:
    return {
        "account_id": _optional_int_arg("account_id"),
        "purpose": str(request.args.get("purpose") or "").strip() or None,
        "registration_job_id": _optional_int_arg("registration_job_id"),
        "operation_task_id": _optional_int_arg("operation_task_id"),
        "operation_run_id": _optional_int_arg("operation_run_id"),
        "limit": max(1, min(1000, int(request.args.get("limit") or 200))),
    }


def create_proxy_traffic_blueprint(_context: WebUIContext):
    bp = LegacyEndpointBlueprint("proxy_traffic", __name__)

    @bp.get("/api/proxy-traffic")
    def api_proxy_traffic():
        try:
            filters = _common_filters()
            view = str(request.args.get("view") or "current").strip().lower()
            items = proxy_lease_store.query_leases(view=view, **filters)
            return jsonify({"ok": True, "view": view, "items": items, "total": len(items)})
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @bp.get("/api/proxy-traffic/current")
    def api_proxy_traffic_current():
        try:
            filters = _common_filters()
            items = proxy_lease_store.query_leases(view="current", **filters)
            return jsonify({"ok": True, "view": "current", "items": items, "total": len(items)})
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @bp.get("/api/proxy-traffic/history")
    def api_proxy_traffic_history():
        try:
            filters = _common_filters()
            items = proxy_lease_store.query_leases(view="history", **filters)
            return jsonify({"ok": True, "view": "history", "items": items, "total": len(items)})
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @bp.get("/api/proxy-traffic/traffic")
    def api_proxy_traffic_summary():
        try:
            filters = _common_filters()
            return jsonify({"ok": True, **browser_traffic.query_traffic(**filters)})
        except (TypeError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    return bp
