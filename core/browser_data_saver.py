# -*- coding: utf-8 -*-
"""Optional-resource blocking for local registration browsers.

The registration path uses a Roxy-controlled Selenium browser. This module
keeps the saving boundary deliberately narrow: optional resource types such as
images/media and explicitly configured telemetry/ad URLs are blocked, while
documents, core scripts, stylesheets, XHR/fetch, WebSockets, and auth/challenge
URLs remain available.
"""
from __future__ import annotations

import logging
from collections import Counter
from fnmatch import fnmatchcase
from typing import Any

from config import browser as _cfg

logger = logging.getLogger(__name__)

_RESOURCE_TYPE_ALIASES = {
    "images": "image",
    "img": "image",
    "videos": "media",
    "video": "media",
    "audio": "media",
    "fonts": "font",
    "tracks": "texttrack",
    "track": "texttrack",
}
_KNOWN_RESOURCE_TYPES = {
    "document", "stylesheet", "image", "media", "font", "script",
    "texttrack", "xhr", "fetch", "eventsource", "websocket", "manifest", "other",
}
_URL_EXTENSIONS_BY_TYPE = {
    "image": (".apng", ".avif", ".bmp", ".gif", ".ico", ".jfif", ".jpeg", ".jpg", ".png", ".svg", ".webp"),
    "media": (".3gp", ".avi", ".flac", ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4", ".mpeg", ".ogg", ".wav", ".webm"),
    "font": (".eot", ".otf", ".ttf", ".woff", ".woff2"),
    "manifest": (".webmanifest", "/manifest.json"),
    "texttrack": (".vtt", ".srt"),
    "stylesheet": (".css",),
    "script": (".js", ".mjs"),
}
_POST_AUTH_URL_PATTERNS = (
    # After the auth/profile form is submitted, registration only needs the
    # session JSON document. Do not load the ChatGPT SPA or auth static chunks.
    "**://chatgpt.com/cdn/assets/**",
    "**://auth-cdn.oaistatic.com/assets/**",
)


def _as_items(value: Any, *, lower: bool = True) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.replace(",", "\n").splitlines()
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]
    result = [str(item or "").strip() for item in raw if str(item or "").strip()]
    return [item.lower() for item in result] if lower else result


def configured_resource_types() -> list[str]:
    result: list[str] = []
    for item in _as_items(getattr(_cfg, "BROWSER_DATA_SAVER_BLOCKED_RESOURCE_TYPES", ()), lower=True):
        item = _RESOURCE_TYPE_ALIASES.get(item, item)
        if item in _KNOWN_RESOURCE_TYPES and item not in result:
            result.append(item)
    return result


def configured_url_patterns() -> list[str]:
    result: list[str] = []
    for item in _as_items(getattr(_cfg, "BROWSER_DATA_SAVER_BLOCKED_URL_PATTERNS", ()), lower=False):
        if item not in result:
            result.append(item)
    return result


class BrowserDataSaver:
    """Install and report narrow CDP URL blocking for one browser session."""

    def __init__(self, *, label: str = "Browser") -> None:
        self.label = str(label or "Browser")
        self.enabled = bool(getattr(_cfg, "BROWSER_DATA_SAVER_MODE", False))
        self.resource_types = configured_resource_types() if self.enabled else []
        self.url_patterns = configured_url_patterns() if self.enabled else []
        self.blocked_count = 0
        self.blocked_by_type: Counter[str] = Counter()
        self.blocked_by_url_pattern: Counter[str] = Counter()
        self._selenium_patterns: list[str] = []
        self._driver = None
        self._post_auth_activated = False
        self._stopped = False
        self.method = "disabled"

    def _matching_url_pattern(self, url: str) -> str | None:
        for pattern in self.url_patterns:
            try:
                if fnmatchcase(str(url or ""), pattern):
                    return pattern
            except Exception:
                continue
        return None

    def _record_blocked(self, resource_type: str, *, url_pattern: str | None = None) -> None:
        normalized = _RESOURCE_TYPE_ALIASES.get(str(resource_type or "other").lower(), str(resource_type or "other").lower())
        self.blocked_count += 1
        self.blocked_by_type[normalized or "other"] += 1
        if url_pattern:
            self.blocked_by_url_pattern[url_pattern] += 1

    def install_selenium(self, driver: Any) -> "BrowserDataSaver":
        if not self.enabled:
            return self
        self._driver = driver
        self._apply_selenium_blocklist()
        return self

    def _apply_selenium_blocklist(self) -> None:
        patterns: list[str] = []
        for resource_type in self.resource_types:
            patterns.extend(f"*{extension}*" for extension in _URL_EXTENSIONS_BY_TYPE.get(resource_type, ()))
        # CDP Network.setBlockedURLs uses '*' rather than Playwright's '**'.
        patterns.extend(pattern.replace("**", "*") for pattern in self.url_patterns)
        self._selenium_patterns = list(dict.fromkeys(patterns))
        if not self._selenium_patterns:
            self.method = "enabled_no_rules"
            return self
        try:
            try:
                self._driver.execute_cdp_cmd("Network.enable", {})
            except Exception:
                pass
            self._driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": self._selenium_patterns})
            self.method = "selenium.cdp.Network.setBlockedURLs"
            if not self._post_auth_activated:
                logger.info(
                    "[%s] 省流量模式已启用：资源类型=%s，URL规则=%s",
                    self.label,
                    ",".join(self.resource_types) or "-",
                    len(self.url_patterns),
                )
        except Exception as exc:
            if self._post_auth_activated:
                logger.warning("[%s] 切换 post-auth 省流量规则失败，保留原规则：%s: %s", self.label, type(exc).__name__, str(exc)[:180])
            else:
                self.method = "install_failed"
                logger.warning("[%s] 安装省流量拦截失败，继续不拦截：%s: %s", self.label, type(exc).__name__, str(exc)[:180])

    def activate_post_auth(self) -> bool:
        """Block the ChatGPT SPA only after the auth/profile form is submitted."""
        if not self.enabled or self._stopped or self._post_auth_activated:
            return False
        self._post_auth_activated = True
        for pattern in _POST_AUTH_URL_PATTERNS:
            if pattern not in self.url_patterns:
                self.url_patterns.append(pattern)
        self._apply_selenium_blocklist()
        logger.info(
            "[%s] 已切换 post-auth 省流量规则：新增静态资源规则=%s",
            self.label,
            len(_POST_AUTH_URL_PATTERNS),
        )
        return True

    def observe_cdp_event(self, method: str, params: dict[str, Any], request: dict[str, Any] | None = None) -> bool:
        """Recognize a CDP inspector block for optional diagnostics."""
        if not self.enabled or method != "Network.loadingFailed":
            return False
        if str(params.get("blockedReason") or "").lower() != "inspector":
            return False
        item = request or {}
        url = str(item.get("url") or "")
        resource_type = str(
            item.get("resourceType") or item.get("resource_type") or "other"
        ).strip().lower() or "other"
        if self._selenium_patterns and not any(fnmatchcase(url, pattern) for pattern in self._selenium_patterns):
            return False
        if not self._selenium_patterns and resource_type not in self.resource_types:
            return False
        if isinstance(item, dict):
            # The CDP observer still reports requestWillBeSent/postData for an
            # inspector-blocked request. Mark it so the traffic summary does
            # not mistake that unsent body for provider-side traffic.
            item["_data_saver_blocked"] = True
        self._record_blocked(resource_type, url_pattern=self._matching_url_pattern(url))
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "data_saver_enabled": bool(self.enabled),
            "data_saver_method": self.method,
            "data_saver_blocked_resource_types": list(self.resource_types),
            "data_saver_blocked_url_patterns": list(self.url_patterns),
            "data_saver_post_auth_activated": bool(self._post_auth_activated),
            "data_saver_blocked_count": int(self.blocked_count),
            "data_saver_blocked_by_type": dict(sorted(self.blocked_by_type.items())),
            "data_saver_blocked_by_url_pattern": dict(sorted(self.blocked_by_url_pattern.items())),
        }

    def stop(self) -> dict[str, Any]:
        self._stopped = True
        snapshot = self.snapshot()
        if snapshot["data_saver_enabled"]:
            logger.info(
                "[%s] 省流量汇总：拦截 %s 个请求，类型=%s，URL规则=%s",
                self.label,
                snapshot["data_saver_blocked_count"],
                snapshot["data_saver_blocked_by_type"],
                snapshot["data_saver_blocked_by_url_pattern"],
            )
        return snapshot


__all__ = ["BrowserDataSaver", "configured_resource_types", "configured_url_patterns"]
