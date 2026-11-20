"""Exercise the current accounts Vue bundle and shell against synthetic HTTP data."""
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from jinja2 import Environment, FileSystemLoader


WEBUI = Path(__file__).resolve().parents[2] / 'webui'


@pytest.mark.parametrize('width', [1440, 375])
def test_current_page_shows_compact_status_and_complete_detail(width):
    playwright = pytest.importorskip('playwright.sync_api')
    template = Environment(loader=FileSystemLoader(WEBUI / 'templates')).get_template('index.html')
    html = template.render(url_for=lambda _, filename, **kwargs: f'/static/{filename}')
    assert (WEBUI / 'static/task-center/accounts.js').is_file(), '缺少当前账号 Vue 构建产物'
    reason = '合成诊断 <状态已变更>，请核对原始记录。'
    defaults = {
        'has_access_token': False, 'has_account_password': False, 'totp_enabled': False,
        'email_invalid': False, 'email_invalid_reason': None, 'email_invalid_at': None,
        'email_invalid_source': None, 'plus_promo_kind': '', 'plus_promo_eligible': False,
        'plus_trial_eligible': False, 'plus_discount_eligible': False,
        'account_promotions': None, 'promotion_query_snapshot': None,
        'plan_check_country_results': [],
    }
    rows = [dict(defaults, **row) for row in [
        {'id': 7, 'email': 'first@example.test', 'current_plan_type': 'A&B',
         'has_account_password': True,
         'live_check_status': 'failed', 'live_check_http_status': 401, 'live_check_error': reason,
         'codex_status': 'failed', 'codex_error': reason,
         'extract_link_status': 'running', 'extract_link_message': '等待上游回复，稍后会再次读取任务记录'},
        {'id': 8, 'email': 'second@example.test', 'account_status_reason': '历史停用记录',
         'live_check_status': 'live', 'live_checked_at': '2026-11-15T10:20:00'},
        {'id': 9, 'email': 'third@example.test', 'codex_credential_state': 'pending_confirmation'},
    ]]
    reads, unexpected, assets = [], [], []

    def respond(route):
        request = route.request
        target = urlsplit(request.url)
        if target.hostname != 'accounts.test' or request.method != 'GET':
            unexpected.append((request.method, target.hostname, target.path))
            return route.abort()
        if target.path == '/':
            return route.fulfill(content_type='text/html', body=html)
        if target.path.startswith('/static/'):
            asset = (WEBUI / target.path.lstrip('/')).resolve()
            if not asset.is_relative_to((WEBUI / 'static').resolve()) or not asset.is_file():
                unexpected.append(('missing-static', target.path))
                return route.abort()
            assets.append(target.path)
            return route.fulfill(path=asset)
        query = parse_qs(target.query)
        if target.path.startswith('/api/accounts'):
            reads.append((target.path, query))
        if target.path in ('/api/accounts', '/api/accounts/plan-check-status'):
            number = int(query.get('page', ['1'])[0])
            size = int(query['page_size'][0])
            page_rows = rows if number == 1 else [dict(defaults, id=17, email='page-two@example.test')]
            payload = {
                'ok': True, 'items': page_rows, 'total': 21, 'page': number, 'page_size': size,
                'offset': (number - 1) * size, 'limit': size, 'revision': 'synthetic-current',
            }
            if target.path.endswith('/plan-check-status'):
                payload.update(items=[dict(row, plan_details_revision='synthetic-details',
                                           plan_summary={'promotions': [], 'countries': []}) for row in page_rows],
                               status_fields=[], queue={'workers': 1, 'registration_workers': 1,
                                                        'queue_limit': 100, 'min_interval': 0, 'jitter': 0})
            else:
                payload.update(compact=True, facets={}, search_terms=[])
            return route.fulfill(json=payload)
        if target.path == '/api/accounts/7/roxy-profile':
            return route.fulfill(json={'ok': True, 'profile_id': None, 'window_name': None})
        if target.path == '/api/accounts/7/plan-details':
            return route.fulfill(json={'ok': True, 'item': {
                'account_promotions': None, 'promotion_query_snapshot': None, 'plan_check_country_results': [],
            }})
        if target.path == '/api/accounts/7/secret' and query == {'field': ['account_password']}:
            return route.fulfill(json={'ok': True, 'value': 'password-from-secret-api'})
        if target.path.startswith('/api/accounts'):
            unexpected.append(('unhandled-accounts', target.path, query))
            return route.abort()
        # The real shared shell starts its overview and settings reads locally.
        return route.fulfill(json={'ok': True, 'features': {}, 'accounts': 0, 'email_sources': {}})

    with playwright.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip('本机未安装隔离 Chromium 测试运行时')
        browser = runtime.chromium.launch()
        try:
            page = browser.new_page(viewport={'width': width, 'height': 840}, has_touch=width < 600,
                                    timezone_id='Asia/Shanghai')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_default_timeout(5000)
            page.add_init_script("""
                window.syntheticCopies = [];
                Object.defineProperty(navigator, 'clipboard', {configurable: true,
                    value: {writeText: async text => window.syntheticCopies.push(text)}});
            """)
            page.route('**/*', respond)
            page.goto('https://accounts.test/')
            assert not reads, '隐藏账号页不能提前读取账号列表'
            page.evaluate("activateTab('accounts', false, 'none')")
            items = page.locator('#accounts-list-root tr[data-account-row]')
            playwright.expect(items).to_have_count(3)
            assert '/static/task-center/accounts.js' in assets
            batch_summary = page.locator('#accountsMoreActionsV2 summary')
            batch_menu = page.locator('#accountsMoreActionsV2 .toolbar-overflow-menu')
            batch_summary.click()
            playwright.expect(batch_menu.locator('button')).to_have_count(34)
            assert batch_menu.evaluate("""menu => {
                const panel = menu.getBoundingClientRect();
                const table = document.querySelector('.ac-table-scroll').getBoundingClientRect();
                const overlapTop = Math.max(panel.top, table.top);
                return overlapTop + 4 < Math.min(panel.bottom, table.bottom)
                    && menu.contains(document.elementFromPoint(panel.left + 16, overlapTop + 4));
            }"""), '表格滚动区与批量菜单重叠时，菜单应当可点击'
            page.keyboard.press('Escape')
            playwright.expect(batch_menu).to_be_hidden()
            playwright.expect(batch_summary).to_be_focused()
            pagination = page.get_by_role('navigation', name='账号列表分页')
            playwright.expect(pagination.get_by_label('每页条数')).to_have_value('20')
            assert next(query['page_size'] for path, query in reads if path == '/api/accounts') == ['20']
            first = items.first
            if width >= 600:
                assert first.locator('.col-account-status').inner_text().splitlines() == ['Token 异常', 'HTTP 401']
                assert first.locator('.col-status').inner_text().splitlines() == ['失败', '执行异常']
                assert first.locator('.col-status .account-cell-line--sub').get_attribute('title') == reason
                assert first.locator('.col-plan .account-cell-line--sub').inner_text() == '提链中'
                assert items.nth(1).locator('.col-account-status').inner_text().splitlines() == ['查活通过', '11-15 10:20']
                assert items.nth(2).locator('.col-status').inner_text() == '凭据核验缺失'
                first.get_by_role('button', name='详情', exact=True).click()
            else:
                playwright.expect(first.locator('.acc-mobile-dot.is-bad')).to_be_visible()
                playwright.expect(items.nth(1).locator('.acc-mobile-dot.is-ok')).to_be_visible()
                playwright.expect(items.nth(2).locator('.acc-mobile-dot.is-warn')).to_be_visible()
                assert first.locator('.acc-mobile-meta').inner_text() == 'A&B · 2FA 未验证 · Codex 失败'
                first.locator('[data-account-detail-id="7"]').first.tap()
            drawer = page.get_by_role('dialog', name='first@example.test', exact=True)
            playwright.expect(drawer).to_be_visible()
            assert reason in drawer.inner_text()
            assert rows[0]['extract_link_message'] in drawer.inner_text()
            assert 'A&B' in drawer.inner_text()
            assert drawer.locator('script,img').count() == 0
            drawer.get_by_role('button', name='关闭账号详情').click()
            playwright.expect(drawer).not_to_be_visible()
            first.get_by_role('button', name='更多账号操作').click()
            menu = page.locator('[data-account-menu="7"]')
            menu.get_by_role('button', name='复制账号密码', exact=True).click()
            page.wait_for_function("window.syntheticCopies.length === 1")
            assert page.evaluate('window.syntheticCopies') == ['password-from-secret-api']
            assert ('/api/accounts/7/secret', {'field': ['account_password']}) in reads
            pagination.get_by_role('button', name='下一页').click()
            playwright.expect(items).to_have_count(1)
            playwright.expect(items.first).to_contain_text('page-two@example.test')
            playwright.expect(pagination).to_contain_text('共 21 条')
            list_reads = [query for path, query in reads if path == '/api/accounts']
            assert list_reads[-1]['page'] == ['2']
            assert list_reads[-1]['page_size'] == ['20']
            assert list_reads[-1]['include_facets'] == ['0']
            with page.expect_response(lambda response: urlsplit(response.url).path == '/api/accounts') as refreshed:
                page.locator('#btnRefreshAccountsV2').click()
            refreshed_query = parse_qs(urlsplit(refreshed.value.url).query)
            assert refreshed_query['page'] == ['2']
            assert refreshed_query['page_size'] == ['20']
            assert 'include_facets' not in refreshed_query
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), '页面不应横向溢出'
            assert not unexpected, unexpected
            assert not errors, errors
        finally:
            browser.close()
