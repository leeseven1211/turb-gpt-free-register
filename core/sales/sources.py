"""销售账号来源适配器。"""

from __future__ import annotations

import json
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from .adapters import _env_value, _invoke_transport, _validate_base_url
from .errors import SalesError


Transport = Callable[..., dict]


def _account_password(row: dict) -> str:
    extra = row.get("extra_json") or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            extra = {}
    candidates = []
    if isinstance(extra, dict):
        candidates.extend(
            extra.get(key)
            for key in ("account_password", "login_password", "registration_password")
        )
    candidates.extend(
        row.get(key)
        for key in ("account_password", "login_password", "registration_password")
    )
    for value in candidates:
        if value is not None and str(value).strip():
            return str(value)
    return ""


def _delivery_line(row: dict) -> str:
    """按核心账号字段构造邮箱----密码----2FA 三段交付资料。"""
    return "----".join((
        str(row.get("email") or ""),
        _account_password(row),
        str(row.get("totp_secret") or ""),
    ))


def _normalize_email(email: str) -> str:
    return str(email or "").strip().casefold()


class _RemoteTransport:
    def __init__(self, base_url: str, auth_code: str):
        self.base_url = base_url
        self.auth_code = auth_code

    def __call__(self, path: str, body: dict, **kwargs) -> dict:
        method = str(kwargs.get("method") or "GET").upper()
        url = urljoin(self.base_url, path.lstrip("/"))
        data = None
        if method == "GET":
            params = {
                key: value for key, value in body.items()
                if value is not None and value != ""
            }
            if params:
                url += ("&" if "?" in url else "?") + urlencode(params)
        else:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Auth-Code": self.auth_code,
                "User-Agent": "Turb-Sales/1",
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code == 401:
                raise SalesError("source_auth_invalid", "账号来源鉴权无效", 401) from exc
            raise SalesError("source_http_error", "账号来源 HTTP 请求失败", exc.code) from exc
        except TimeoutError as exc:
            raise SalesError("source_timeout", "账号来源请求超时") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise SalesError("source_timeout", "账号来源请求超时") from exc
            raise SalesError("source_network_error", "账号来源请求未完成") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SalesError("source_response_invalid", "账号来源响应不是有效 JSON") from exc
        except Exception as exc:
            raise SalesError("source_network_error", "账号来源请求未完成") from exc
        if not isinstance(payload, dict):
            raise SalesError("source_response_invalid", "账号来源响应不是 JSON 对象")
        return payload


class AccountSource:
    def __init__(self, source: dict, *, transport: Transport | None = None):
        self.source = dict(source or {})
        self.source_id = str(self.source.get("id") or "")
        self.kind = str(self.source.get("kind") or "local").lower()
        if self.kind not in {"local", "remote"}:
            raise SalesError("source_kind_invalid", "不支持的账号来源类型")
        self.transport = transport
        if self.kind == "remote":
            self.base_url = _validate_base_url(
                self.source.get("base_url"),
                "source_url_invalid",
            )
            auth = _env_value(self.source.get("auth_env"), "source_auth_missing")
            self._transport_headers = {"X-Auth-Code": auth}
            self.transport = transport or _RemoteTransport(self.base_url, auth)

    def _remote_request(self, path: str, body: dict, *, method: str = "GET") -> dict:
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
            raise SalesError("source_timeout", "账号来源请求超时") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise SalesError("source_timeout", "账号来源请求超时") from exc
            raise SalesError("source_network_error", "账号来源请求未完成") from exc
        except OSError as exc:
            raise SalesError("source_network_error", "账号来源请求未完成") from exc
        if response.get("ok") is False:
            code = str(response.get("error_code") or "")
            if code in {"unauthorized", "auth_invalid", "forbidden"}:
                raise SalesError("source_auth_invalid", "账号来源鉴权无效", 401)
            raise SalesError("source_protocol_error", "账号来源返回了失败响应")
        if response.get("ok") is not None and response.get("ok") is not True:
            raise SalesError("source_response_invalid", "账号来源响应状态无效")
        return response

    def _remote_pages(self, *, q: str = "") -> list[dict]:
        page = 1
        page_size = 500
        total = None
        rows: list[dict] = []
        while True:
            response = self._remote_request(
                "/api/accounts",
                {
                    "archived": "all",
                    "paged": 1,
                    "page": page,
                    "page_size": page_size,
                    "include_facets": 0,
                    "q": q,
                },
                method="GET",
            )
            items = response.get("items")
            if not isinstance(items, list):
                raise SalesError("source_response_invalid", "账号来源响应缺少 items")
            try:
                current_total = int(response.get("total", len(items)))
            except (TypeError, ValueError):
                raise SalesError("source_response_invalid", "账号来源 total 格式无效")
            if total is None:
                total = current_total
            elif total != current_total:
                raise SalesError("source_response_invalid", "账号来源分页 total 发生变化")
            rows.extend(item for item in items if isinstance(item, dict))
            if len(rows) >= total:
                return rows[:total]
            if not items:
                raise SalesError("source_response_incomplete", "账号来源分页在 total 前结束")
            page += 1

    @staticmethod
    def _public_account(row: dict, delivery_line: str) -> dict:
        return {
            "id": int(row["id"]),
            "email": str(row.get("email") or ""),
            "plan": str(row.get("plan") or row.get("current_plan_type") or row.get("plan_type") or ""),
            "archived": bool(row.get("archived")),
            "delivery_line": delivery_line,
        }

    @staticmethod
    def _material_by_id(response: dict, account_ids: list[int]) -> dict[int, str]:
        values = response.get("values")
        if not isinstance(values, list):
            raise SalesError("source_response_incomplete", "账号来源资料未完整返回")
        by_id = {}
        for item in values:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            try:
                account_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            value = item.get("value")
            if value is not None and str(value).strip():
                by_id[account_id] = str(value)
        if any(account_id not in by_id for account_id in account_ids):
            raise SalesError("source_response_incomplete", "账号来源资料未完整返回")
        return by_id

    def accounts(self, account_ids: list[int]) -> list[dict]:
        wanted = []
        for value in account_ids or []:
            try:
                wanted.append(int(value))
            except (TypeError, ValueError):
                continue
        wanted = list(dict.fromkeys(wanted))
        if self.kind == "local":
            from core import db

            result = []
            for account_id in wanted:
                row = db.get_account(account_id)
                if row:
                    result.append(self._public_account(row, _delivery_line(row)))
            return result

        result = []
        for account_id in wanted:
            rows = self._remote_pages(q=f"ID:{account_id}")
            for row in rows:
                if str(row.get("id")) == str(account_id):
                    result.append(self._public_account(row, ""))
        if result:
            ids = [row["id"] for row in result]
            material_response = self._remote_request(
                "/api/accounts/secret-bulk",
                {"account_ids": ids, "field": "account_credentials_line"},
                method="POST",
            )
            by_id = self._material_by_id(
                material_response,
                [row["id"] for row in result],
            )
            for row in result:
                row["delivery_line"] = by_id[row["id"]]
        return result

    def find_accounts(self, emails: list[str]) -> list[dict]:
        normalized = list(dict.fromkeys(
            value for value in (_normalize_email(email) for email in emails) if value
        ))
        if self.kind == "local":
            from core import db

            candidates = []
            for email in normalized:
                offset = 0
                page_size = 500
                while True:
                    page = db.list_accounts_page(
                        limit=page_size,
                        offset=offset,
                        archived="all",
                        q=email,
                    )
                    if not isinstance(page, dict) or not isinstance(page.get("items"), list):
                        raise SalesError("source_response_invalid", "本地账号分页响应无效")
                    rows = page["items"]
                    candidates.extend(
                        row for row in rows
                        if _normalize_email(row.get("email")) == email
                    )
                    try:
                        total = int(page.get("total", len(rows)))
                    except (TypeError, ValueError):
                        raise SalesError("source_response_invalid", "本地账号分页 total 无效")
                    offset += len(rows)
                    if offset >= total:
                        break
                    if not rows:
                        raise SalesError("source_response_incomplete", "本地账号分页在 total 前结束")
            return [
                self._public_account(row, _delivery_line(row))
                for row in candidates
            ]

        candidates = []
        for email in normalized:
            candidates.extend(self._remote_pages(q=f"邮箱:{email}"))
        unique = {}
        for row in candidates:
            if not isinstance(row, dict) or row.get("id") in (None, ""):
                continue
            if _normalize_email(row.get("email")) in normalized:
                unique[int(row["id"])] = row
        if not unique:
            return []
        material_response = self._remote_request(
            "/api/accounts/secret-bulk",
            {
                "account_ids": list(unique),
                "field": "account_credentials_line",
            },
            method="POST",
        )
        by_id = self._material_by_id(material_response, list(unique))
        return [
            self._public_account(row, by_id[int(row["id"])])
            for row in unique.values()
        ]

    def archive(self, account_id: int) -> bool:
        try:
            account_id = int(account_id)
        except (TypeError, ValueError):
            raise SalesError("source_account_not_found", "账号 ID 无效", 404)
        current_rows = [
            row for row in self._remote_pages(q=f"ID:{account_id}")
            if str(row.get("id")) == str(account_id)
        ] if self.kind == "remote" else []
        current = self.accounts([account_id]) if self.kind == "local" else current_rows
        if not current:
            raise SalesError("source_account_not_found", "来源账号不存在", 404)
        if bool(current[0].get("archived")):
            return True
        if self.kind == "local":
            from core import db

            if not db.archive_account(account_id, True):
                raise SalesError("source_archive_failed", "来源账号归档失败")
            readback = self.accounts([account_id])
        else:
            self._remote_request(
                f"/api/accounts/{account_id}/archive",
                {"archived": True},
                method="POST",
            )
            readback = [
                row for row in self._remote_pages(q=f"ID:{account_id}")
                if str(row.get("id")) == str(account_id)
            ]
        if not readback or not bool(readback[0].get("archived")):
            raise SalesError("source_archive_unconfirmed", "来源账号归档未确认")
        return True
