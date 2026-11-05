"""补密码线路隔离只接受明确的代理连接故障证据。"""
from __future__ import annotations


def is_proxy_transport_failure(error: BaseException) -> bool:
    """沿异常链检查代理专属标记，不将普通超时、HTTP 或业务拒绝归为坏线路。"""
    seen = set()
    current = error
    while isinstance(current, BaseException) and id(current) not in seen:
        seen.add(id(current))
        if type(current).__name__ == "ProxyError":
            return True
        message = str(current).lower()
        if any(marker in message for marker in (
            "connect tunnel failed", "proxy connect aborted", "could not resolve proxy",
            "failed to connect to proxy", "err_proxy_connection_failed",
            "err_tunnel_connection_failed", "cannot connect to proxy",
        )):
            return True
        current = current.__cause__ or current.__context__
    return False
