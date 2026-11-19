from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader


WEBUI = Path(__file__).resolve().parents[2] / 'webui'


@pytest.mark.parametrize('width', [1440, 375])
def test_current_page_shows_compact_status_and_complete_detail(width):
    playwright = pytest.importorskip('playwright.sync_api')
    template = Environment(loader=FileSystemLoader(WEBUI / 'templates')).get_template('index.html')
    html = template.render(url_for=lambda _, filename, **kwargs: f'/static/{filename}')
    reason = '合成诊断 <状态已变更>，请核对原始记录。'
    rows = [
        {'id': 7, 'email': 'first@example.test', 'current_plan_type': 'A&B',
         'live_check_status': 'failed', 'live_check_http_status': 401, 'live_check_error': reason,
         'codex_status': 'failed', 'codex_error': reason,
         'extract_link_status': 'running', 'extract_link_message': '等待上游回复，稍后会再次读取任务记录'},
        {'id': 8, 'email': 'second@example.test', 'account_status_reason': '历史停用记录',
         'live_check_status': 'live', 'live_checked_at': '2026-11-15T10:20:00'},
        {'id': 9, 'email': 'third@example.test', 'codex_credential_state': 'pending_confirmation'},
    ]
    with playwright.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip('本机未安装隔离 Chromium 测试运行时')
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 840}, has_touch=width < 600)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_default_timeout(5000)
        page.route('**/*', lambda route: route.abort())
        page.route('http://accounts.test/', lambda route: route.fulfill(content_type='text/html', body=html))
        for pattern in ('css/**/*.css', 'js/shared/**/*.js', 'js/pages/registration/page.js', 'js/pages/accounts/page.js'):
            for asset in (WEBUI / 'static').glob(pattern):
                url = f'http://accounts.test/static/{asset.relative_to(WEBUI / "static")}'
                page.route(url, lambda route, request, asset=asset: route.fulfill(path=asset))
        page.route('**/api/accounts?*', lambda route: route.fulfill(json={'items': rows, 'total': len(rows)}))
        page.route('**/api/accounts/7/roxy-profile', lambda route: route.fulfill(json={}))
        page.goto('http://accounts.test/')
        page.evaluate("""async () => {
          document.querySelector('#tab-overview').classList.add('hidden');
          document.querySelector('#tab-accounts').classList.remove('hidden');
          document.querySelector('#tab-accounts').dataset.moduleView = 'active';
          await loadAccounts();
        }""")
        items = page.locator('#accountsBodyV2 > tr')
        first = items.first
        assert items.count() == 3
        if width >= 600:
            assert first.locator('.col-account-status').inner_text().splitlines() == ['Token 异常', 'HTTP 401']
            assert first.locator('.col-status').inner_text().splitlines() == ['失败', '执行异常']
            assert first.locator('.col-status .account-cell-line--sub').get_attribute('title') == reason
            assert first.locator('.col-plan .account-cell-line--sub').inner_text() == '提链中'
            assert items.nth(1).locator('.col-account-status').inner_text().splitlines() == ['查活通过', '11-15 10:20']
            assert items.nth(2).locator('.col-status').inner_text() == '凭据核验缺失'
            first.get_by_role('button', name='详情', exact=True).click()
        else:
            assert first.locator('.acc-mobile-dot.is-bad').is_visible()
            assert items.nth(1).locator('.acc-mobile-dot.is-ok').is_visible()
            assert items.nth(2).locator('.acc-mobile-dot.is-warn').is_visible()
            assert first.locator('.acc-mobile-meta').inner_text() == 'A&B · 2FA 未验证 · Codex 失败'
            first.get_by_role('button', name='Token 异常 first@example.test').tap()
        drawer = page.get_by_role('dialog', name='first@example.test')
        assert not errors, errors
        assert drawer.is_visible()
        assert reason in drawer.inner_text()
        assert rows[0]['extract_link_message'] in drawer.inner_text()
        browser.close()
