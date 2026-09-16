# -*- coding: utf-8 -*-
"""Authenticated proxy lease and browser traffic read APIs."""
from __future__ import annotations

from typing import Any

from flask import jsonify, request

from core import browser_traffic, proxy_lease_store
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext


def _page_args() -> tuple[int, int]:
    limit = request.args.get("limit", default=200, type=int)
    offset = request.args.get("offset", default=0, type=int)
    return (limit if limit is not None else 200, offset if offset is not None else 0)


def _lease_page(view: str, logger) -> tuple[Any, int] | Any:
    limit, offset = _page_args()
    try:
        items = proxy_lease_store.list_page(view=view, limit=limit, offset=offset)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:  # pragma: no cover - driver failures vary by deployment
        logger.exception("读取代理租约页面失败: view=%s", view)
        return jsonify({"ok": False, "error": f"{type(exc).__name__}"}), 503
    return jsonify({
        "ok": True,
        "view": view,
        "items": items,
        "count": len(items),
        "limit": max(1, min(500, int(limit or 200))),
        "offset": max(0, int(offset or 0)),
    })


def _traffic_items(limit: int, offset: int) -> list[dict[str, Any]]:
    return browser_traffic.list_summaries(limit=limit, offset=offset)


def create_proxy_traffic_blueprint(context: WebUIContext):
    blueprint = LegacyEndpointBlueprint("proxy_traffic", __name__)
    logger = context.logger

    @blueprint.get("/api/proxy-traffic")
    def api_proxy_traffic():
        """Return the aggregate shape consumed by the proxy/traffic page."""
        limit, offset = _page_args()
        try:
            current_leases = proxy_lease_store.list_page(
                view="current", limit=limit, offset=offset,
            )
            lease_history = proxy_lease_store.list_page(
                view="history", limit=limit, offset=offset,
            )
            browser_items = _traffic_items(limit, offset)
        except Exception as exc:  # pragma: no cover - driver failures vary by deployment
            logger.exception("读取代理与流量聚合页面失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}"}), 503
        return jsonify({
            "ok": True,
            "current_leases": current_leases,
            "lease_history": lease_history,
            "browser_traffic": browser_items,
        })

    @blueprint.get("/api/proxy-traffic/current")
    def api_proxy_traffic_current():
        return _lease_page("current", logger)

    @blueprint.get("/api/proxy-traffic/history")
    def api_proxy_traffic_history():
        return _lease_page("history", logger)

    @blueprint.get("/api/proxy-traffic/traffic")
    @blueprint.get("/api/proxy-traffic/summaries")
    def api_proxy_traffic_summaries():
        limit, offset = _page_args()
        try:
            items = _traffic_items(limit, offset)
            aggregate = browser_traffic.aggregate_summaries(items)
        except Exception as exc:  # pragma: no cover - driver failures vary by deployment
            logger.exception("读取浏览器流量摘要失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}"}), 503
        return jsonify({
            "ok": True,
            "items": items,
            "count": len(items),
            "aggregate": aggregate,
            "limit": max(1, min(500, int(limit or 200))),
            "offset": max(0, int(offset or 0)),
        })

    return blueprint
