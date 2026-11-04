"""只通过认证页面实际提供的链接进入密码页。"""
from __future__ import annotations

import time
from urllib.parse import urlsplit

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By

from core.auth.browser.auth_context import checkpoint, current_execution_context


class PasswordEntryNavigationError(RuntimeError):
    """密码链接已选择，但这次点击没有确认进入目标页。"""

    code = "password_entry_navigation_failed"


def _trusted_path(url: object) -> str | None:
    try:
        parsed = urlsplit(str(url or ""))
        if (parsed.scheme == "https" and parsed.hostname == "auth.openai.com"
                and parsed.port in (None, 443) and not parsed.username and not parsed.password):
            return parsed.path
    except ValueError:
        pass
    return None


def open_offered_password_entry(driver, *, timeout: float, allow_create: bool = True,
                               allow_login: bool = True) -> str | None:
    """点击一次当前页面提供的可用密码链接；无入口时沿用原认证分支。"""
    checkpoint()
    if _trusted_path(driver.current_url) is None:
        return None
    paths = tuple(path for path, allowed in (
        ("/log-in/password", allow_login), ("/create-account/password", allow_create),
    ) if allowed)
    offered = {}
    for element in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        try:
            if (not element.is_displayed() or not element.is_enabled()
                    or str(element.get_attribute("aria-disabled") or "").lower() == "true"):
                continue
            path = _trusted_path(element.get_attribute("href"))
            if path in paths and path not in offered:
                offered[path] = element
        except StaleElementReferenceException:
            continue
    selected = next((path for path in paths if path in offered), None)
    if selected is None:
        return None
    context = current_execution_context()
    remaining = max(0.0, float(timeout))
    if context is not None:
        remaining = min(remaining, context.remaining(remaining))
    if remaining <= 0:
        raise PasswordEntryNavigationError("密码入口导航预算已耗尽，未点击链接")
    deadline = time.monotonic() + remaining
    element = offered[selected]
    checkpoint()
    try:
        unchanged = (_trusted_path(driver.current_url) is not None
                     and _trusted_path(element.get_attribute("href")) == selected)
    except StaleElementReferenceException:
        raise PasswordEntryNavigationError("密码入口在点击前已被替换，未点击旧链接") from None
    if not unchanged:
        raise PasswordEntryNavigationError("密码入口在点击前已变化，未点击旧链接")
    previous_timeout = getattr(getattr(driver, "timeouts", None), "page_load", None)
    try:
        if isinstance(previous_timeout, (int, float)):
            driver.set_page_load_timeout(remaining)
        try:
            # Selenium 的原生点击保留真实 href/query；点击未确认时不追加其它点击方式。
            element.click()
        except TimeoutException:
            if _trusted_path(driver.current_url) != selected:
                raise PasswordEntryNavigationError("密码入口点击后导航超时，未重复点击") from None
        except Exception:
            checkpoint()
            raise PasswordEntryNavigationError("密码入口点击未确认，未重复点击") from None
        while True:
            checkpoint()
            path = _trusted_path(driver.current_url)
            if path == selected:
                return selected
            if path is None:
                raise PasswordEntryNavigationError("密码入口点击后离开可信认证来源，未重复点击")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PasswordEntryNavigationError("密码入口点击后未进入所选密码页，未重复点击")
            time.sleep(min(0.1, remaining))
    finally:
        if isinstance(previous_timeout, (int, float)):
            driver.set_page_load_timeout(previous_timeout)


__all__ = ["PasswordEntryNavigationError", "open_offered_password_entry"]
