# -*- coding: utf-8 -*-
"""Capture and reuse the account-entitlement response seen during registration.

The ChatGPT session response exposes the basic plan type, while the homepage
loads the accounts/check endpoint for trial and offer eligibility. This module
captures that response from the registration browser when available. It keeps
the raw response in browser memory only; callers receive the normalized,
credential-free result from core.chatgpt_plan.parse_accounts_check.
"""
from __future__ import annotations

import time
from typing import Any

from core.chatgpt_plan import parse_accounts_check
_CAPTURE_KEY = "__turb_registration_plan_response"
_ACCOUNTS_CHECK_PATH = "/backend-api/accounts/check/v4-2023-04-27"

CAPTURE_SCRIPT = r"""
(() => {
  if (window.__turbRegistrationPlanCaptureInstalled) return;
  window.__turbRegistrationPlanCaptureInstalled = true;
  const isTarget = url => String(url || '').includes('/backend-api/accounts/check/');
  const save = (url, status, data) => {
    try {
      if (!isTarget(url) || !data || typeof data !== 'object' || !data.accounts) return;
      window.__turb_registration_plan_response = {
        url: String(url || ''),
        status: Number(status || 0),
        data,
        captured_at: new Date().toISOString()
      };
    } catch (_) {}
  };

  const originalFetch = window.fetch;
  if (typeof originalFetch === 'function') {
    window.fetch = async function(...args) {
      const response = await originalFetch.apply(this, args);
      try {
        const clone = response.clone();
        clone.json().then(data => save(response.url || (args[0] && args[0].url) || args[0], response.status, data)).catch(() => {});
      } catch (_) {}
      return response;
    };
  }

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__turbPlanUrl = url;
    return originalOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function(...args) {
    this.addEventListener('load', () => {
      try {
        const url = this.responseURL || this.__turbPlanUrl || '';
        if (!isTarget(url)) return;
        const data = typeof this.response === 'object' && this.response !== null
          ? this.response : JSON.parse(this.responseText || '{}');
        save(url, this.status, data);
      } catch (_) {}
    });
    return originalSend.apply(this, args);
  };
})();
"""


def _raw_result_valid(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("data"), dict)
        and isinstance(value["data"].get("accounts"), dict)
    )


def _normalize_capture(raw: Any, token: str) -> dict | None:
    if not _raw_result_valid(raw):
        return None
    try:
        result = parse_accounts_check(raw["data"], token=token)
    except Exception:
        return None
    if not result.get("ok"):
        return None
    result.update({
        "trigger": "registration_browser_response",
        "source": "browser_response",
        "captured_at": str(raw.get("captured_at") or ""),
        "http_status": int(raw.get("status") or 200),
    })
    return result


def install_playwright(context: Any, page: Any | None = None) -> None:
    """Install capture hooks on a Playwright context and its current page."""
    try:
        context.add_init_script(CAPTURE_SCRIPT)
    except Exception:
        pass
    if page is not None:
        try:
            page.evaluate(CAPTURE_SCRIPT)
        except Exception:
            pass


def read_playwright(context: Any, page: Any | None, token: str, wait_seconds: float = 2.5) -> dict | None:
    """Read a normalized capture from any live page in the context."""
    deadline = time.monotonic() + max(0.0, float(wait_seconds or 0.0))
    while True:
        pages = []
        try:
            pages = list(getattr(context, "pages", []) or [])
        except Exception:
            pass
        if page is not None and page not in pages:
            pages.insert(0, page)
        for candidate in pages:
            try:
                raw = candidate.evaluate(f"() => window.{_CAPTURE_KEY}")
            except Exception:
                continue
            result = _normalize_capture(raw, token)
            if result:
                return result
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.1)


def install_selenium(driver: Any) -> None:
    """Install capture hooks for Selenium/Cloak drivers via CDP and current page."""
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": CAPTURE_SCRIPT})
    except Exception:
        pass
    try:
        driver.execute_script(CAPTURE_SCRIPT)
    except Exception:
        pass


def read_selenium(driver: Any, token: str, wait_seconds: float = 2.5) -> dict | None:
    """Read a normalized capture from the active Selenium window."""
    deadline = time.monotonic() + max(0.0, float(wait_seconds or 0.0))
    while True:
        try:
            raw = driver.execute_script(f"return window.{_CAPTURE_KEY};")
        except Exception:
            raw = None
        result = _normalize_capture(raw, token)
        if result:
            return result
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.1)


def fetch_selenium(driver: Any, token: str, timeout_seconds: float = 12.0) -> dict | None:
    """Query entitlements inside the signed-in ChatGPT browser session.

    A standalone requests session can receive a 403 even when the registration
    browser is already authenticated, because its cookies/browser fingerprint
    do not match. This fallback keeps the request in the real page and returns
    only the normalized, credential-free result.
    """
    token = str(token or "").strip()
    if not token:
        return None
    try:
        try:
            driver.set_script_timeout(max(1.0, float(timeout_seconds)))
        except Exception:
            pass
        raw = driver.execute_async_script(
            r"""
            const token = arguments[0];
            const path = arguments[1];
            const done = arguments[arguments.length - 1];
            const finish = value => { try { done(value); } catch (_) {} };
            const headers = {
              accept: '*/*',
              authorization: `Bearer ${token}`,
              'oai-language': navigator.language || 'en-US',
              'x-openai-target-path': path,
              'x-openai-target-route': path,
            };
            try {
              const deviceId = localStorage.getItem('oai-device-id')
                || localStorage.getItem('oai-did')
                || localStorage.getItem('device_id');
              if (deviceId) headers['oai-device-id'] = deviceId;
            } catch (_) {}
            fetch(`${path}?timezone_offset_min=-`, {
              method: 'GET',
              credentials: 'include',
              headers,
            }).then(async response => {
              let data = null;
              try { data = await response.json(); } catch (_) {}
              finish({
                status: Number(response.status || 0),
                data,
                captured_at: new Date().toISOString(),
              });
            }).catch(error => finish({error: String(error || 'browser fetch failed')}));
            """,
            token,
            _ACCOUNTS_CHECK_PATH,
        )
    except Exception:
        return None
    result = _normalize_capture(raw, token)
    if result:
        result["source"] = "browser_fallback_request"
    return result


def read_or_fetch_selenium(
    driver: Any,
    token: str,
    wait_seconds: float = 2.5,
    fetch_timeout_seconds: float = 12.0,
) -> dict | None:
    """Prefer a naturally captured response, then query in the same browser."""
    captured = read_selenium(driver, token, wait_seconds=wait_seconds)
    if captured:
        return captured
    return fetch_selenium(driver, token, timeout_seconds=fetch_timeout_seconds)
