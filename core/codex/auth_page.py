"""Codex 专用认证页面上下文，沿用原会话的传输与状态。"""
from __future__ import annotations

import logging
import posixpath
import re
from collections.abc import Mapping
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit


logger = logging.getLogger("core.codex_oauth.auth_page")
_ORIGIN = "https://auth.openai.com"
_HEADER = "OpenAI-Auth-Page"
_ENTRY_PATH = re.compile(r"^/(?:api|authorize|oauth/authorize)(?:/|$)", re.I)
_SOURCES = {"document", "bootstrap", "password", "mfa", "continue", "request", "response", "redirect", "post"}


def _trusted_url(url):
    if not isinstance(url, str) or any(ord(char) <= 32 or ord(char) == 127 for char in url) or "\\" in url:
        return None
    try:
        parsed = urlsplit(urljoin(_ORIGIN + "/", url))
        if (parsed.scheme != "https" or parsed.hostname != "auth.openai.com"
                or parsed.port not in (None, 443) or parsed.username is not None or parsed.password is not None):
            return None
        return parsed
    except ValueError:
        return None


class CodexAuthPageSession:
    """代理一个 BrowserSession，保留原 Cookie、重试、缓存和身份。

    仅可信页面 URL 中显式且唯一的 ``auth_page`` 更新选定上下文。
    URL 缺少参数时保留上下文，显式空参数清除；API URL 不更新上下文。
    本适配器新增的运行诊断仅记录存在性与变化标记。
    """

    def __init__(self, session):
        object.__setattr__(self, "_base_session", session)
        object.__setattr__(self, "_auth_page", "")

    def __getattr__(self, name):
        return getattr(self._base_session, name)

    def __setattr__(self, name, value):
        if name in {"_base_session", "_auth_page"}:
            object.__setattr__(self, name, value)
        else:
            setattr(self._base_session, name, value)

    def _diagnose(self, source, *, auth_page_present=False, changed=False, header_present=False):
        source = source if isinstance(source, str) and source in _SOURCES else "unknown"
        logger.info(
            "[Codex 认证页面] source=%s auth_page_present=%s has_auth_page=%s changed=%s header_present=%s",
            source, auth_page_present, bool(self._auth_page), changed, header_present,
        )

    def observe_url(self, url, *, source="document") -> bool:
        """读取页面选定上下文，返回是否接受了显式参数。"""
        parsed = _trusted_url(url)
        if parsed is None:
            return False
        path = posixpath.normpath("/" + unquote(parsed.path).lstrip("/"))
        if "\\" in path or _ENTRY_PATH.match(path):
            return False
        values = [value for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key == "auth_page"]
        if not values:
            self._diagnose(source)
            return False
        if len(values) != 1 or any(ord(char) < 33 or ord(char) > 126 for char in values[0]):
            return False
        value = values[0]
        changed = value != self._auth_page
        self._auth_page = value
        self._diagnose(source, auth_page_present=True, changed=changed)
        return True

    def observe_payload(self, payload, *, source="continue", base_url=_ORIGIN + "/") -> bool:
        """按可信响应地址读取现有 JSON；已知官方 API helper 默认使用认证域。"""
        if (not isinstance(payload, Mapping) or _trusted_url(base_url) is None
                or urlsplit(base_url).scheme != "https" or not urlsplit(base_url).netloc):
            return False
        for item in (payload, payload.get("page")):
            if isinstance(item, Mapping):
                for key in ("continue_url", "authPageUrl", "external_url", "redirect_url", "url"):
                    target = item.get(key)
                    if _trusted_url(target) is not None and self.observe_url(urljoin(base_url, target), source=source):
                        return True
        return False

    def _headers(self, headers, *, include=False):
        if headers is None and not (include and self._auth_page):
            return None
        result = {key: value for key, value in (headers or {}).items() if key.lower() != _HEADER.lower()}
        if include and self._auth_page:
            result[_HEADER] = self._auth_page
        return result

    def get_auth_headers(self, *args, **kwargs):
        return self._headers(self._base_session.get_auth_headers(*args, **kwargs), include=True)

    def post(self, url, headers=None, **kwargs):
        parsed = _trusted_url(url)
        path = posixpath.normpath("/" + unquote(parsed.path).lstrip("/")) if parsed else ""
        include = bool(parsed and parsed.path.startswith("/api/accounts/")
                       and path.startswith("/api/accounts/") and "\\" not in path)
        outgoing = self._headers(headers, include=include)
        self._diagnose("post", header_present=bool(include and self._auth_page))
        return self._base_session.post(url, headers=outgoing, **kwargs)

    def get(self, url, headers=None, **kwargs):
        self.observe_url(url, source="request")
        response = self._base_session.get(url, headers=self._headers(headers), **kwargs)
        for item in [*(getattr(response, "history", None) or []), response]:
            item_url = getattr(item, "url", "")
            self.observe_url(item_url, source="response")
            if _trusted_url(item_url) is not None:
                locations = getattr(item, "headers", None) or {}
                location = next((value for key, value in locations.items() if key.lower() == "location"), None)
                if location and _trusted_url(location) is not None:
                    self.observe_url(urljoin(item_url, location), source="redirect")
        return response
