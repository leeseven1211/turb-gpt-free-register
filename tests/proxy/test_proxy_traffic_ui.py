"""Exercise the real shell and the checked-in proxy bundle on synthetic HTTP data."""
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from jinja2 import Environment, FileSystemLoader

WEBUI = Path(__file__).resolve().parents[2] / 'webui'


def test_sidebar_inventory_records_filters_and_paging_use_only_monitoring_reads():
    api = pytest.importorskip('playwright.sync_api')
    html = Environment(loader=FileSystemLoader(WEBUI / 'templates')).get_template('index.html').render(
        url_for=lambda _, filename, **options: '/static/' + filename)
    reads = []
    static_reads = []
    unexpected = []

    def respond(route):
        url = urlsplit(route.request.url)
        if url.hostname != 'console.test' or route.request.method != 'GET':
            unexpected.append((route.request.method, url.path))
            return route.abort()
        if url.path == '/':
            return route.fulfill(content_type='text/html', body=html)
        if url.path.startswith('/static/'):
            static_reads.append(url.path)
            return route.fulfill(path=WEBUI / url.path.lstrip('/'))
        query = parse_qs(url.query)
        if url.path == '/api/proxy-pool':
            payload = {'ok': True, 'policy': {'max_size': 7}, 'counts': {'ready': 3},
                       'items': [{'resource_id': 'sample-resource', 'exit_ip': '192.0.2.0/24', 'password': 'PRIVATE_SAMPLE'}]}
        elif url.path == '/api/proxy-traffic/summary':
            payload = {'ok': True, 'total_bytes': 2048, 'today_bytes': 500, 'today_request_count': 0,
                       'today_browser_count': 4, 'today_route_count': 1, 'lease_states': ['released']}
        elif url.path in {f'/api/proxy-traffic/{view}' for view in ('current', 'history', 'traffic')}:
            view = url.path.split('/')[-1]
            offset = int(query['offset'][0])
            row = {'id': offset + 1, 'lease_id': f'lease-{offset}', 'state': 'released', 'source': 'protocol_http',
                   'availability': 'available', 'total_bytes': 12, 'operation_task_id': 9007199254740997}
            payload = {'ok': True, 'view': view, 'items': [row], 'total': 21, 'limit': 20, 'offset': offset, 'count': 1}
        else:
            # The legacy shell bootstraps its own overview/settings. Stub every such request locally.
            if url.path.startswith('/api/proxy'):
                unexpected.append((route.request.method, url.path))
            return route.fulfill(json={'ok': True, 'accounts': 0, 'features': {}, 'email_sources': {}})
        reads.append((url.path, query))
        return route.fulfill(json=payload)

    with api.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip('本机未安装隔离 Chromium 测试运行时')
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': 1400, 'height': 900})
        page.set_default_timeout(5000)
        page.route('**/*', respond)
        page.goto('http://console.test/')
        assert not reads
        assert not any(url.startswith('/static/proxy/') for url in static_reads)
        page.locator('[data-tab="proxy-traffic"]').click()
        page.get_by_text('sample-resource', exact=True).wait_for()
        assert page.locator('[data-proxy-summary="poolCapacity"]').inner_text() == '3 / 7'
        counts = Counter(path for path, _ in reads)
        assert counts == {path: 1 for path in ('/api/proxy-pool', '/api/proxy-traffic/summary',
                                               '/api/proxy-traffic/current', '/api/proxy-traffic/history', '/api/proxy-traffic/traffic')}
        nav = page.locator('[data-module-subnav="proxy-traffic"]')
        nav.get_by_role('button', name='租约与流量').click()
        assert page.locator('[data-proxy-summary="todayRequestCount"]').inner_text() == '0'
        page.get_by_role('tab', name='线路历史').click()
        panel = page.locator('[data-proxy-panel="history"]')
        panel.get_by_role('button', name='筛选状态').click()
        page.locator('[data-proxy-filter-option="released"]').click()
        panel.get_by_role('button', name='下一页').click()
        panel.get_by_text('lease-20', exact=True).wait_for()
        assert any(path.endswith('/history') and query['offset'] == ['20'] and query['state'] == ['released'] for path, query in reads)
        panel.locator('[data-proxy-detail]').click()
        dialog = page.get_by_role('dialog', name='线路历史详情')
        assert '9007199254740997' in dialog.inner_text()
        assert 'PRIVATE_SAMPLE' not in page.locator('#proxy-page-root').text_content()
        page.keyboard.press('Escape')
        nav.get_by_role('button', name='代理池库存').click()
        assert page.locator('[data-proxy-module-panel="pool"]').is_visible()
        assert not page.locator('[data-proxy-module-panel="records"]').is_visible()
        page.go_back()
        assert page.locator('[data-proxy-module-panel="records"]').is_visible()
        assert page.locator('[data-proxy-view="history"]').get_attribute('aria-selected') == 'true'
        assert not unexpected
        browser.close()
