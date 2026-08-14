"""住宅代理租约管理 —— 从 proxy-pool 申请/归还家宽出口。

用法：
    >>> from core.proxy_lease import lease_proxy, release_proxy, ProxyLeaseError
    >>>
    >>> # 成功时返回 "socks5://..." 字符串
    >>> proxy_url = lease_proxy()
    >>> try:
    ...     do_registration(proxy=proxy_url)
    ... finally:
    ...     release_proxy(proxy_url)

Context manager 用法：
    >>> from core.proxy_lease import proxy_lease
    >>> with proxy_lease() as proxy_url:
    ...     do_registration(proxy=proxy_url)
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("proxy-lease")

# proxy-pool 地址和认证（与 turb 同机，走 localhost）
PROXY_POOL_BASE = "http://127.0.0.1:8000"
PROXY_POOL_USER = "admin"
PROXY_POOL_PASS = "6E8d_CqGYsVAJsST_uCP"

_RE_URL_USER = re.compile(r"socks5://([^:]+):")


class ProxyLeaseError(Exception):
    """租约操作失败。"""


def _auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(PROXY_POOL_USER, PROXY_POOL_PASS)


def _extract_export_user(proxy_url: str) -> str:
    """从 socks5://export_user:pass@host:port 中提取 export_user。"""
    m = _RE_URL_USER.search(proxy_url)
    if not m:
        raise ProxyLeaseError(f"无法从 URL 解析 export_user: {proxy_url}")
    return m.group(1)


def lease_proxy(
    country: str = "US",
    region: str = "Rand",
    rotate_minutes: int = 10,
    timeout: float = 30.0,
    retries: int = 2,
) -> str:
    """从 proxy-pool 申请一条独占住宅代理通道。

    返回 socks5:// 格式的代理 URL。
    异常时抛出 ProxyLeaseError。
    """
    url = f"{PROXY_POOL_BASE}/api/residential/lease"
    params = {
        "country": country,
        "region": region,
        "rotate_every_minutes": rotate_minutes,
    }

    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                url,
                params=params,
                auth=_auth(),
                timeout=timeout,
            )
            if resp.status_code == 401:
                raise ProxyLeaseError("proxy-pool 认证失败，检查管理后台用户名密码")
            if resp.status_code >= 400:
                detail = resp.text[:300]
                raise ProxyLeaseError(f"proxy-pool lease 返回 {resp.status_code}: {detail}")
            data = resp.json()
            proxy_url = data.get("url", "")
            if not proxy_url or not proxy_url.startswith("socks5://"):
                raise ProxyLeaseError(f"proxy-pool 返回无效 URL: {proxy_url}")
            logger.info(
                "leased proxy: %s (export_user=%s, exit_ip=%s)",
                proxy_url,
                data.get("export_user", "?"),
                data.get("exit_ip", "?"),
            )
            return proxy_url
        except ProxyLeaseError:
            raise
        except requests.Timeout:
            last_exc = ProxyLeaseError(f"proxy-pool lease 超时 ({timeout}s), attempt {attempt+1}/{retries+1}")
            logger.warning(str(last_exc))
            if attempt < retries:
                time.sleep(2)
        except Exception as e:
            last_exc = ProxyLeaseError(f"proxy-pool lease 失败: {e}")
            logger.warning(str(last_exc))
            if attempt < retries:
                time.sleep(2)

    raise last_exc or ProxyLeaseError("proxy-pool lease 失败（无详细原因）")


def release_proxy(proxy_url: str, timeout: float = 15.0) -> bool:
    """归还一条已租用的住宅代理通道。

    返回 True 表示成功归还，False 表示归还失败（通道可能已失效）。
    """
    try:
        export_user = _extract_export_user(proxy_url)
    except ProxyLeaseError as e:
        logger.warning("release: %s", e)
        return False

    url = f"{PROXY_POOL_BASE}/api/residential/release/{export_user}"
    try:
        resp = requests.post(url, auth=_auth(), timeout=timeout)
        if resp.status_code >= 400:
            logger.warning(
                "release proxy %s: status=%d detail=%s",
                export_user,
                resp.status_code,
                resp.text[:200],
            )
            return False
        data = resp.json()
        released = data.get("released", False)
        logger.info("released proxy: %s (deleted=%s)", export_user, released)
        return released
    except requests.Timeout:
        logger.warning("release proxy %s timeout", export_user)
        return False
    except Exception as e:
        logger.warning("release proxy %s error: %s", export_user, e)
        return False


class proxy_lease:
    """Context manager：自动申请 + 自动归还。

    Usage:
        with proxy_lease(country="US") as proxy_url:
            do_registration(proxy=proxy_url)
    """

    def __init__(
        self,
        country: str = "US",
        region: str = "Rand",
        rotate_minutes: int = 10,
        timeout: float = 30.0,
    ):
        self._country = country
        self._region = region
        self._rotate_minutes = rotate_minutes
        self._timeout = timeout
        self._proxy_url: Optional[str] = None

    def __enter__(self) -> str:
        self._proxy_url = lease_proxy(
            country=self._country,
            region=self._region,
            rotate_minutes=self._rotate_minutes,
            timeout=self._timeout,
        )
        return self._proxy_url

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._proxy_url:
            release_proxy(self._proxy_url)
        return False  # 不吞异常
