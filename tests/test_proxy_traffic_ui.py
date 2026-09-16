from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = (
    ROOT / "webui/templates/index.html",
    ROOT / "webui/templates/index_legacy.html",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_modern_and_legacy_templates_expose_an_independent_proxy_traffic_page():
    for path in TEMPLATES:
        source = _read(path)
        assert 'data-tab="proxy-traffic"' in source
        assert 'id="tab-proxy-traffic"' in source
        assert "代理与流量" in source
        assert 'js/proxy_traffic.js' in source


def test_proxy_traffic_contract_is_explicit_and_secret_free():
    source = _read(ROOT / "webui/static/js/proxy_traffic.js")
    assert "const PROXY_TRAFFIC_API" in source
    assert "'/api/proxy-traffic'" in source
    for field in (
        "current_leases",
        "history",
        "traffic",
        "provider",
        "exit_ip",
        "purpose",
        "operation_task_id",
        "operation_run_id",
        "registration_job_id",
        "route_attempt",
        "upload_bytes",
        "download_bytes",
        "total_bytes",
        "failed_request_count",
        "unfinished_request_count",
        "unknown_size_request_count",
    ):
        assert field in source
    assert "proxy_url" not in source
    assert "username" not in source
    assert "password" not in source


def test_proxy_traffic_page_covers_views_filters_states_refresh_and_details():
    source = _read(ROOT / "webui/static/js/proxy_traffic.js")
    for value in (
        "current",
        "history",
        "traffic",
        "is-${kind}",
        "btnRefreshProxyTraffic",
        "proxyTrafficQuery",
        "proxyTrafficProvider",
        "proxyTrafficState",
        "proxyTrafficPurpose",
        "aria-expanded",
    ):
        assert value in source


def test_navigation_registers_proxy_traffic_in_both_navigation_modules():
    modern = _read(ROOT / "webui/static/js/modern/common.js")
    legacy = _read(ROOT / "webui/static/js/legacy/common.js")
    assert "proxy-traffic" in modern
    assert "proxy-traffic" in legacy
    assert "loadProxyTraffic" in modern
    assert "loadProxyTraffic" in legacy


def test_proxy_traffic_styles_support_focus_reduced_motion_and_narrow_tables():
    source = _read(ROOT / "webui/static/css/proxy-traffic.css")
    assert ".proxy-traffic-table-wrap" in source
    assert "overflow-x: auto" in source
    assert ":focus-visible" in source
    assert "prefers-reduced-motion" in source
    assert "@media (max-width: 860px)" in source
    assert "@media (max-width: 560px)" in source


def test_account_page_template_does_not_gain_proxy_traffic_columns():
    source = _read(ROOT / "webui/templates/index.html")
    account_page = source.split('<div id="tab-accounts"', 1)[1].split('<div id="tab-codex"', 1)[0]
    assert "代理与流量" not in account_page
    assert "exit_ip" not in account_page
