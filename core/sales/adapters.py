"""链动小铺协议适配器。

该模块只负责协议和字段转换，业务状态的持久化与重试由销售服务层负责。
"""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
import json
import os
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import SalesError


Transport = Callable[..., dict]


def _validate_base_url(value: str, code: str) -> str:
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise SalesError(code, "来源地址必须是无凭据的 http/https 地址")
    return raw.rstrip("/") + "/"


def _env_value(name: str, code: str) -> str:
    key = str(name or "").strip()
    value = os.environ.get(key, "").strip() if key else ""
    if not value and key and str(os.environ.get("PYTHON_DOTENV_DISABLED") or "").strip().lower() not in {
        "1", "true", "yes", "on", "y",
    }:
        try:
            from config.env_loader import read_env_file

            value = str(read_env_file().get(key) or "").strip()
        except (ImportError, OSError, ValueError):
            value = ""
    if not value:
        raise SalesError(code, "鉴权环境变量未配置", 401)
    return value


def _timestamp(value: Any) -> str | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SalesError("shop_response_invalid", "远端时间字段格式无效")
    if number > 100_000_000_000:
        number /= 1000
    try:
        return datetime.fromtimestamp(number, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        raise SalesError("shop_response_invalid", "远端时间字段超出范围")


def _as_list(data: Any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        return data["list"]
    raise SalesError("shop_response_invalid", "远端分页响应缺少 list")


def _page_total(data: Any) -> int:
    if not isinstance(data, dict) or isinstance(data.get("total"), bool):
        raise SalesError("shop_response_invalid", "远端分页响应缺少 total")
    try:
        total = int(data.get("total"))
    except (TypeError, ValueError):
        raise SalesError("shop_response_invalid", "远端 total 格式无效")
    if total < 0:
        raise SalesError("shop_response_invalid", "远端 total 不能为负数")
    return total


def _order_count(value: Any, field: str) -> int:
    if value in (None, ""):
        return 0
    try:
        if isinstance(value, bool):
            raise ValueError
        count = int(value)
    except (TypeError, ValueError):
        raise SalesError("shop_response_invalid", f"订单{field}格式无效")
    if count < 0:
        raise SalesError("shop_response_invalid", f"订单{field}不能为负数")
    return count


class _LiandongTransport:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token

    def __call__(self, path: str, body: dict, **kwargs) -> dict:
        method = str(kwargs.get("method") or "POST").upper()
        url = urljoin(self.base_url, path.lstrip("/"))
        request = Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            method=method,
            headers={
                "Content-Type": "application/json",
                "Merchant-Token": self.token,
                "User-Agent": "Turb-Sales/1",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code == 401:
                raise SalesError("shop_auth_invalid", "链动鉴权无效", 401) from exc
            raise SalesError("shop_http_error", "链动 HTTP 请求失败", exc.code) from exc
        except TimeoutError as exc:
            raise SalesError("shop_timeout", "链动请求超时") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise SalesError("shop_timeout", "链动请求超时") from exc
            raise SalesError("shop_network_error", "链动请求未完成") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SalesError("shop_response_invalid", "链动响应不是有效 JSON") from exc
        except Exception as exc:
            raise SalesError("shop_network_error", "链动请求未完成") from exc
        if not isinstance(payload, dict):
            raise SalesError("shop_response_invalid", "链动响应不是 JSON 对象")
        return payload


def _invoke_transport(transport: Transport, path: str, body: dict, **kwargs) -> dict:
    try:
        signature = inspect.signature(transport)
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
        if accepts_kwargs:
            call_kwargs = kwargs
        else:
            call_kwargs = {
                key: value for key, value in kwargs.items()
                if key in signature.parameters
            }
    except (TypeError, ValueError):
        call_kwargs = {}
    result = transport(path, body, **call_kwargs)
    if not isinstance(result, dict):
        raise SalesError("shop_response_invalid", "传输层未返回 JSON 对象")
    return result


class LiandongAdapter:
    def __init__(self, shop: dict, *, transport: Transport | None = None):
        self.shop = dict(shop or {})
        self.base_url = _validate_base_url(
            self.shop.get("base_url") or "https://wzyp.cn",
            "shop_url_invalid",
        )
        token = _env_value(self.shop.get("token_env"), "shop_auth_missing")
        self.transport = transport or _LiandongTransport(self.base_url, token)
        self._transport_headers = {"Merchant-Token": token}

    def _request(self, path: str, body: dict, *, method: str = "POST") -> dict:
        try:
            response = _invoke_transport(
                self.transport,
                path,
                body,
                method=method,
                headers=dict(self._transport_headers),
            )
        except SalesError:
            raise
        except TimeoutError as exc:
            raise SalesError("shop_timeout", "链动请求超时") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise SalesError("shop_timeout", "链动请求超时") from exc
            raise SalesError("shop_network_error", "链动请求未完成") from exc
        except OSError as exc:
            raise SalesError("shop_network_error", "链动请求未完成") from exc
        code = response.get("code")
        try:
            code = int(code)
        except (TypeError, ValueError):
            pass
        if code == 401:
            raise SalesError("shop_auth_invalid", "链动鉴权无效", 401)
        if code == 0:
            return response
        if code != 1:
            raise SalesError("shop_protocol_error", "链动返回了无法识别的业务码")
        return response

    def _paged(self, path: str, body: dict) -> list[dict]:
        page = 1
        page_size = int(body.get("pageSize") or 100)
        expected = None
        rows: list[dict] = []
        while True:
            response = self._request(
                path,
                {**body, "current": page, "pageSize": page_size},
            )
            response_code = response.get("code")
            try:
                response_code = int(response_code)
            except (TypeError, ValueError):
                pass
            if response_code == 0:
                message = str(response.get("msg") or response.get("message") or "")
                if "商品" in message and "不存在" in message:
                    raise SalesError("product_not_found", "商品不存在", 404)
                raise SalesError("shop_protocol_error", "链动分页请求被拒绝")
            data = response.get("data")
            batch = _as_list(data)
            total = _page_total(data)
            if expected is None:
                expected = total
            elif total != expected:
                raise SalesError("shop_response_invalid", "远端分页 total 在读取中发生变化")
            rows.extend(batch)
            if len(rows) >= expected:
                return rows[:expected]
            if not batch:
                raise SalesError("shop_response_incomplete", "远端分页在 total 前结束")
            page += 1

    def check(self) -> dict:
        response = self._request("/merchantApi/user/userinfo", {})
        data = response.get("data")
        if not isinstance(data, dict) or data.get("id") in (None, ""):
            raise SalesError("shop_response_invalid", "链动商户身份响应缺少 ID")
        return {
            "external_shop_id": str(data["id"]),
            "capabilities": {
                "products": True,
                "inventory": True,
                "import_inventory": True,
                "orders": True,
            },
        }

    def products(self) -> list[dict]:
        rows = self._paged(
            "/merchantApi/Goods/list",
            {"goods_type": "card", "is_proxy": 0, "status": 999},
        )
        products = []
        for row in rows:
            if not isinstance(row, dict) or row.get("id") in (None, ""):
                raise SalesError("shop_response_invalid", "商品响应缺少商品 ID")
            goods_key = row.get("goods_key") or row.get("key") or row.get("goodsKey")
            if goods_key in (None, ""):
                raise SalesError("shop_response_invalid", "商品响应缺少 goods_key")
            try:
                price = row.get("price", 0)
                price = float(price) if isinstance(price, str) else price
            except (TypeError, ValueError):
                raise SalesError("shop_response_invalid", "商品价格格式无效")
            products.append({
                "external_product_id": str(row["id"]),
                "goods_key": str(goods_key),
                "name": str(row.get("name") or ""),
                "status": "active" if str(row.get("status", row.get("goods_status"))) == "1" else "inactive",
                "price": price,
            })
        return products

    def inventory(self, external_product_id: str) -> list[dict]:
        try:
            goods_id = int(str(external_product_id))
        except (TypeError, ValueError):
            raise SalesError("product_not_found", "商品 ID 无效", 404)
        rows = self._paged(
            "/merchantApi/goodsCardStorage/list",
            {
                "goods_id": goods_id,
                "keywords": "",
                "status": "",
                "first": "",
            },
        )
        inventory = []
        for row in rows:
            if not isinstance(row, dict) or row.get("id") in (None, ""):
                raise SalesError("shop_response_invalid", "库存响应缺少库存 ID")
            status = row.get("status")
            if status not in (0, 1, "0", "1"):
                raise SalesError("shop_response_invalid", "库存状态无法分类")
            inventory.append({
                "external_inventory_id": str(row["id"]),
                "content": str(row.get("secret") or ""),
                "status": "sold" if int(status) == 1 else "available",
                "created_at": _timestamp(row.get("create_time")),
            })
        return inventory

    def import_inventory(self, external_product_id: str, lines: list[str]) -> dict:
        try:
            goods_id = int(str(external_product_id))
        except (TypeError, ValueError):
            raise SalesError("product_not_found", "商品 ID 无效", 404)
        response = self._request(
            "/merchantApi/GoodsCardStorage/add",
            {
                "goods_id": goods_id,
                "content": "\n".join(str(line) for line in lines),
                "first": 0,
                "remove_repeat": 1,
            },
        )
        if response.get("code") == 0:
            message = str(response.get("msg") or response.get("message") or "")
            if "商品不存在" in message or "商品" in message and "不存在" in message:
                raise SalesError("product_not_found", "商品不存在", 404)
            if any(word in message for word in ("重复", "去重", "已存在")) or not message:
                return {"duplicate_only": True}
            raise SalesError("shop_import_rejected", "链动拒绝库存导入")
        return {"duplicate_only": False}

    def orders(self) -> list[dict]:
        summaries = self._paged(
            "/merchantApi/order/list",
            {
                "status": "",
                "trade_no": "",
                "contact": "",
                "card_no": "",
                "start_time": 0,
                "end_time": 0,
                "agent_id": None,
                "parent_id": None,
            },
        )
        result = []
        status_map = {0: "unpaid", 1: "paid", 2: "closed", 3: "refunded"}
        for summary in summaries:
            if not isinstance(summary, dict) or not summary.get("trade_no"):
                raise SalesError("shop_response_invalid", "订单响应缺少订单号")
            detail_response = self._request(
                "/merchantApi/Order/orderInfo",
                {"trade_no": str(summary["trade_no"])},
            )
            detail = detail_response.get("data")
            if not isinstance(detail, dict):
                raise SalesError("shop_response_invalid", "订单详情响应无效")
            response = detail.get("response")
            cards = response.get("cards") if isinstance(response, dict) else None
            if cards is None:
                cards = []
            if not isinstance(cards, list) or any(not isinstance(card, str) for card in cards):
                raise SalesError("shop_response_invalid", "订单卡密响应必须是字符串数组")
            raw_status = detail.get("status", summary.get("status"))
            try:
                raw_status = int(raw_status)
            except (TypeError, ValueError):
                pass
            status = status_map.get(raw_status)
            if status is None:
                raise SalesError("shop_response_invalid", "订单状态无法分类")
            goods = detail.get("goods")
            if not isinstance(goods, dict):
                goods = summary.get("goods") if isinstance(summary.get("goods"), dict) else {}
            goods_key = goods.get("goods_key") or goods.get("key")
            if goods_key in (None, ""):
                raise SalesError("shop_response_invalid", "订单响应缺少 goods_key")
            result.append({
                "order_ref": str(detail.get("trade_no") or summary["trade_no"]),
                "goods_key": str(goods_key),
                "status": status,
                "quantity": _order_count(
                    detail.get("quantity", summary.get("quantity", 0)),
                    "quantity",
                ),
                "sendout": _order_count(
                    detail.get("sendout", summary.get("sendout", 0)),
                    "sendout",
                ),
                "cards": cards,
                "amount": detail.get("total_amount", summary.get("total_amount")),
                "fee": detail.get("fee", summary.get("fee")),
                "fee_payer": detail.get("fee_payer", summary.get("fee_payer")),
                "paid_at": _timestamp(detail.get("success_time", summary.get("success_time"))),
            })
        return result
