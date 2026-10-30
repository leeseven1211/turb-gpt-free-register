"""已有会话复用与明确国家查询的代理池边界。"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from core.proxy import account_routes as account_proxy
from core.accounts.plans import client as chatgpt_plan
from core.proxy.provider import ProxyLease


def test_existing_session_does_not_acquire_an_unused_lease():
    session = SimpleNamespace(proxy="http://192.0.2.10:8080")
    with patch("core.proxy.account_routes.acquire_account_proxy") as acquire:
        route = chatgpt_plan.resolve_plan_check_route(session=session)
    acquire.assert_not_called()
    assert route["proxy"] == session.proxy
    assert "_route" not in route


def test_explicit_proxy_cannot_claim_requested_country_without_pool_validation():
    lease = ProxyLease("country-lease", "1024proxy", "http://192.0.2.20:8080", "192.0.2.20:8080", datetime.now(), region="US")
    with patch("core.proxy.pool.acquire_proxy", return_value=lease) as acquire:
        route = account_proxy.acquire_account_proxy(explicit_proxy="http://192.0.2.10:8080", region="US", purpose="plan-check")
    assert acquire.call_args.kwargs["country"] == "US"
    assert route.proxy_url == lease.proxy_url
    assert route.region == "US"


def test_explicit_same_chain_address_does_not_invent_country():
    with patch("core.proxy.pool.acquire_proxy") as acquire:
        route = account_proxy.acquire_account_proxy(explicit_proxy="http://192.0.2.10:8080", purpose="live-check")
    acquire.assert_not_called()
    assert route.region is None
