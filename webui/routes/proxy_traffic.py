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


def _filter_args() -> dict[str, str]:
    window = str(request.args.get("window", "all") or "all").strip().lower()
    if window not in {"all", "1h", "24h", "7d"}:
        raise ValueError("时间范围必须是 all、1h、24h 或 7d")
    return {
        "window": window,
        "state": str(request.args.get("state", "all") or "all").strip()[:40] or "all",
        "purpose": str(request.args.get("purpose", "") or "").strip()[:80],
        "search": str(request.args.get("search", "") or "").strip()[:160],
    }


def _lease_page(view: str, logger) -> tuple[Any, int] | Any:
    limit, offset = _page_args()
    try:
        filters = _filter_args()
        items, total = proxy_lease_store.list_page_with_total(
            view=view, limit=limit, offset=offset, **filters,
        )
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
        "total": total,
        "has_more": max(0, int(offset or 0)) + len(items) < total,
        "limit": max(1, min(500, int(limit or 200))),
        "offset": max(0, int(offset or 0)),
    })


def _traffic_items(limit: int, offset: int, *, available_only: bool = False, **filters: str) -> list[dict[str, Any]]:
    return browser_traffic.list_summaries(
        limit=limit,
        offset=offset,
        available_only=available_only,
        **filters,
    )


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

    @blueprint.get("/api/proxy-traffic/summary")
    def api_proxy_traffic_summary():
        try:
            metrics = browser_traffic.summary_metrics()
            filter_values = proxy_lease_store.distinct_filter_values()
            purposes = set(filter_values.get("purpose", []))
        except Exception as exc:  # pragma: no cover - driver failures vary by deployment
            logger.exception("读取代理与流量全局摘要失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}"}), 503
        return jsonify({
            "ok": True,
            **metrics,
            "purposes": sorted(purposes),
            "lease_states": sorted(set(filter_values.get("state", []))),
            "browser_states": ["available"],
        })

    @blueprint.get("/api/proxy-traffic/traffic")
    @blueprint.get("/api/proxy-traffic/summaries")
    def api_proxy_traffic_summaries():
        limit, offset = _page_args()
        try:
            filters = _filter_args()
            items, total = browser_traffic.list_summaries_with_total(
                limit=limit,
                offset=offset,
                available_only=True,
                **filters,
            )
            aggregate = browser_traffic.aggregate_summaries(items)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:  # pragma: no cover - driver failures vary by deployment
            logger.exception("读取浏览器流量摘要失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}"}), 503
        return jsonify({
            "ok": True,
            "items": items,
            "count": len(items),
            "total": total,
            "has_more": max(0, int(offset or 0)) + len(items) < total,
            "aggregate": aggregate,
            "limit": max(1, min(500, int(limit or 200))),
            "offset": max(0, int(offset or 0)),
        })

    return blueprint
