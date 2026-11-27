"""账号贩卖区 WebUI API。"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, request

from core.sales import jobs, service, store
from core.sales.adapters import _env_value
from core.sales.errors import SalesError
from webui.runtime import WebUIContext

_SOURCE_FIELDS = {"id", "name", "kind", "base_url", "auth_env", "enabled"}
_SHOP_FIELDS = {"id", "name", "platform", "base_url", "token_env", "enabled", "owner_id", "sync_interval"}
_STATUS_FIELDS = {"item_ids", "status", "channel", "price", "currency", "sold_at", "note"}


def _response(payload, status=200):
    return jsonify({"ok": True, **payload}), status


def _body(fields):
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise SalesError("sales_invalid_body", "请求体必须是 JSON 对象")
    if set(value) - fields:
        raise SalesError("sales_invalid_field", "请求包含不支持的字段")
    return value


def _query_number(field, default, maximum, *, optional=False):
    value = request.args.get(field)
    if optional and not value:
        return None
    if value is None:
        return default
    try:
        number = int(value)
    except ValueError:
        number = 0
    if not 1 <= number <= maximum:
        raise SalesError("sales_invalid_query", f"{field} 必须是 1 至 {maximum} 的整数")
    return number


def _validate_configuration(data):
    for field in ("name", "id", "kind", "base_url", "auth_env", "token_env", "platform", "owner_id"):
        if field not in data or (field == "id" and type(data[field]) is int):
            continue
        if not isinstance(data[field], str) or "\x00" in data[field] or len(data[field]) > 2048:
            raise SalesError("sales_invalid_field", f"{field} 格式不正确")
    url = data.get("base_url")
    if url:
        try:
            parts = urlsplit(url)
            valid = (parts.scheme in {"http", "https"} and parts.hostname and parts.port != 0
                     and parts.username is None and parts.password is None and not parts.query and not parts.fragment
                     and not any(char.isspace() or char == "\\" for char in url))
        except ValueError:
            valid = False
        if not valid:
            raise SalesError("sales_invalid_base_url", "基础地址须为无凭据的 HTTP 或 HTTPS 地址")
    for field in ("auth_env", "token_env"):
        value = data.get(field)
        if value and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", value):
            raise SalesError("sales_invalid_env_reference", f"{field} 必须是环境变量名称")
    if "enabled" in data and type(data["enabled"]) is not bool:
        raise SalesError("sales_invalid_field", "enabled 必须为布尔值")
    return data


def _source_public(source):
    return {**source, "auth_configured": source["kind"] == "local" or _configured(source["auth_env"])}


def _shop_public(shop):
    return {**shop, "token_configured": _configured(shop["token_env"])}


def _configured(env_name):
    try:
        return bool(_env_value(env_name, "sales_configuration_missing"))
    except SalesError:
        return False


def _save_source():
    data = _validate_configuration(_body(_SOURCE_FIELDS))
    if not isinstance(data.get("id"), str):
        raise SalesError("sales_invalid_source_id", "来源 ID 必须是字符串")
    return _source_public(service.save_source(data))


def _save_shop():
    data = _validate_configuration(_body(_SHOP_FIELDS))
    if "id" in data:
        jobs.positive_id(data["id"])
    if "sync_interval" in data and (type(data["sync_interval"]) is not int or not 1 <= data["sync_interval"] <= 2**31 - 1):
        raise SalesError("sales_invalid_sync_interval", "同步周期必须是正整数")
    if "platform" in data and data["platform"] != "liandong":
        raise SalesError("sales_platform_unsupported", "当前支持链动小铺")
    return _shop_public(service.save_shop(data))


def create_sales_blueprint(_context: WebUIContext):
    bp = Blueprint("sales", __name__, url_prefix="/api/sales")

    @bp.errorhandler(SalesError)
    def sales_error(error):
        return jsonify({"ok": False, "error_code": error.code, "error": str(error)}), error.status

    @bp.route("/sources", methods=["GET", "POST"])
    def sales_sources():
        if request.method == "POST":
            return _response({"source": _save_source()})
        return _response({"sources": [_source_public(row) for row in store.list_sources()]})

    @bp.route("/shops", methods=["GET", "POST"])
    def sales_shops():
        if request.method == "POST":
            return _response({"shop": _save_shop()})
        return _response({"shops": [_shop_public(row) for row in store.list_shops()], "executor_id": service.executor_id()})

    @bp.get("/shops/<int:shop_id>/products")
    def sales_products(shop_id):
        if store.get_shop(shop_id) is None:
            raise SalesError("sales_shop_not_found", "店铺不存在", 404)
        return _response({"products": store.list_products(shop_id)})

    @bp.post("/shops/<int:shop_id>/check")
    def sales_shop_check(shop_id):
        if request.get_data(cache=True):
            _body(set())
        return _response(service.check_shop(shop_id))

    @bp.get("/items")
    def sales_items():
        status = request.args.get("status", "")
        if status not in {"", "all", "for_sale", "listed", "sold"}:
            raise SalesError("sales_invalid_status", "销售状态必须是全部、待售、已上架或已售出")
        return _response(store.list_items(
            page=_query_number("page", 1, 2**31 - 1), page_size=_query_number("page_size", 20, 200),
            status="" if status == "all" else status,
            shop_id=_query_number("shop_id", None, 2**63 - 1, optional=True),
            source_id=request.args.get("source_id", ""), q=request.args.get("q", ""),
        ))

    @bp.post("/items/add")
    def sales_items_add():
        data = _body({"source_id", "account_ids"})
        return _response(service.add_accounts(data.get("source_id"), data.get("account_ids")))

    @bp.post("/items/status")
    def sales_items_status():
        return _response(service.change_status(_body(_STATUS_FIELDS)))

    @bp.post("/list")
    def sales_list():
        data = _body({"shop_id", "product_id", "item_ids", "request_key"})
        return _response(service.submit_listing(
            data.get("shop_id"), data.get("product_id"), data.get("item_ids"), data.get("request_key"),
        ), 202)

    @bp.post("/shops/<int:shop_id>/sync")
    def sales_sync(shop_id):
        data = _body({"request_key"}) if request.get_data(cache=True) else {}
        return _response(service.submit_sync(shop_id, data.get("request_key")), 202)

    @bp.get("/jobs")
    def sales_jobs():
        return _response({"jobs": service.list_jobs(limit=_query_number("limit", 20, 200))})

    @bp.get("/items/<int:item_id>/events")
    def sales_item_events(item_id):
        if store.get_item(item_id) is None:
            raise SalesError("item_not_found", "销售条目不存在", 404)
        return _response({"events": store.list_events(item_id)})

    return bp
