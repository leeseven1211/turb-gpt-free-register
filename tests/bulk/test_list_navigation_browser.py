"""Exercise the production bulk routes in Chromium with a loopback-only fixture server."""

from pathlib import Path
from threading import Event, Thread
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from flask import Flask, render_template, request as http_request
from werkzeug.serving import make_server


WEBUI = Path(__file__).resolve().parents[2] / 'webui'
BATCH_ID = '9007199254740993'
CURSOR = 'after/+42='
FIRST_NAME = '合成批次一'
SECOND_NAME = '合成批次二'


def batch(batch_id, name):
    return {
        'id': batch_id, 'name': name, 'operation': {'key': 'plan_check'},
        'control': {'state': 'ended'}, 'target_count': 3, 'summary': {'success': 2, 'failed': 1},
        'created_at': '2026-01-15T08:00:00Z', 'summary_revision': 1,
    }


@pytest.fixture
def release_delayed_response():
    gate = Event()
    yield gate
    gate.set()


@pytest.fixture
def blocked_report_asset(request):
    return getattr(request, 'param', None)


@pytest.fixture
def bulk_browser(request, release_delayed_response, blocked_report_asset):
    api = pytest.importorskip('playwright.sync_api')
    for asset in ('bulk.js', 'task-center.css'):
        assert (WEBUI / 'static' / 'task-center' / asset).is_file(), f'缺少批次页面构建产物 {asset}'
    app = Flask(__name__, static_folder=str(WEBUI / 'static'), template_folder=str(WEBUI / 'templates'))
    calls = []
    unexpected = []

    @app.get('/')
    def index():
        return render_template('index.html', asset_version='bulk-browser-test')

    def bulk_response(data):
        return {'ok': True, 'request_id': 'browser-fixture', 'data': data}

    @app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def fixture_api(path):
        if http_request.method != 'GET':
            unexpected.append((http_request.method, path))
            return {}, 405
        args = http_request.args.to_dict(flat=False)
        calls.append((path, args))
        if path == 'bulk/batches':
            second = args.get('cursor') == [CURSOR]
            missing = args.get('q') == ['无匹配']
            item = batch('42', SECOND_NAME) if second else batch(BATCH_ID, FIRST_NAME)
            if args.get('q') == ['滞后响应']:
                if not release_delayed_response.wait(10):
                    return {}, 504
                item = batch('43', '已离开页面的旧结果')
            more = not (missing or second)
            return bulk_response({
                'items': [] if missing else [item],
                'page': {'page_size': 20, 'has_more': more, 'next_cursor': CURSOR if more else None},
                'summary': {'total_batches': 0 if missing else 2, 'ended_batches': 0 if missing else 2},
            })
        if path == f'bulk/batches/{BATCH_ID}':
            return bulk_response(batch(BATCH_ID, FIRST_NAME))
        if path == f'bulk/batches/{BATCH_ID}/targets':
            return bulk_response({'items': [], 'page': {'next_cursor': None}})
        if path == f'bulk/batches/{BATCH_ID}/report':
            return bulk_response({
                'operation_key': 'plan_check', 'phase': 'completed', 'summary_revision': 1,
                'totals': {'accounts': 3, 'completed': 3, 'success': 2, 'failed': 1},
                'duration': {'sample_count': 3, 'avg_seconds': 75},
                'at_refresh': {'attempted_accounts': 2, 'succeeded_accounts': 1},
                'plans': [{'plan': 'plus', 'accounts': 2}],
                'offers': {'with_offer_accounts': 1, 'by_plan': [
                    {'plan': 'plus', 'accounts': 1, 'kinds': [{'kind': 'half_price', 'accounts': 1}]},
                ]},
                'business_summary': {'country_query.success': 7},
            })
        if path == 'bulk/catalog':
            return bulk_response({'operations': [{'key': 'plan_check', 'label': '查询套餐'}]})
        if path == 'bulk/query-facets':
            query = (args.get('query') or [''])[0]
            if '等待预览' in query and not release_delayed_response.wait(10):
                return {}, 504
            return bulk_response({'facets': {}, 'matched': 6410 if '等待预览' in query else 4})
        if path.startswith('bulk/'):
            unexpected.append((http_request.method, path))
            return {}, 404
        # Shared shell and overview reads use the same isolated server.
        return {}

    server = make_server('127.0.0.1', 0, app, threaded=True)
    origin = f'http://127.0.0.1:{server.server_port}'
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with api.sync_playwright() as runtime:
            if not Path(runtime.chromium.executable_path).exists():
                pytest.skip('本机未安装 Chromium 测试运行时')
            browser = runtime.chromium.launch()
            context = browser.new_context(service_workers='block', timezone_id='UTC',
                                          viewport={'width': 1280, 'height': 840})
            blocked_requests = []

            def only_loopback(route):
                target = urlsplit(route.request.url)
                if target.netloc != urlsplit(origin).netloc:
                    unexpected.append(('off-origin', route.request.url))
                    return route.abort()
                if target.path == blocked_report_asset:
                    blocked_requests.append(target.path)
                    return route.abort()
                return route.continue_()

            context.route('**/*', only_loopback)
            page = context.new_page()
            page.set_default_timeout(5000)
            page.clock.install()
            # API 客户端挂载时会捕获 fetch，因此在入口加载前安装迟到响应替身。
            page.add_init_script("""(() => {
                const originalFetch = window.fetch;
                window.fetch = (url, options) => {
                    const target = new URL(url, location.href);
                    if (target.pathname === '/api/bulk/batches' && target.searchParams.get('q') === '滞后响应') {
                        return originalFetch(url, {...options, signal: undefined});
                    }
                    return originalFetch(url, options);
                };
            })();""")
            page.on('pageerror', lambda error: unexpected.append(('pageerror', str(error))))

            def check_asset(response):
                if response.url.startswith(f'{origin}/static/') and response.status >= 400:
                    unexpected.append((response.status, response.url))

            page.on('response', check_asset)
            location = getattr(request, 'param', '')
            page.goto(f'{origin}/{location}')
            if not location:
                page.locator('button[data-tab="bulk"]').click()
            yield page, api.expect, calls
            context.close()
            browser.close()
            if blocked_report_asset:
                assert blocked_report_asset in blocked_requests
    finally:
        release_delayed_response.set()
        server.shutdown()
        thread.join()
        server.server_close()
    assert not unexpected


def search(page, query):
    page.get_by_role('button', name='筛选批次名称或编号').click()
    page.get_by_role('searchbox', name='名称或批次号').fill(query)
    page.get_by_role('button', name='查询', exact=True).click()


def list_query(page):
    fragment = urlsplit(page.url).fragment
    view, _, query = fragment.partition('?')
    assert view == 'bulk/list'
    return parse_qs(query)


@pytest.mark.parametrize('bulk_browser', [f'#bulk/detail?batch_id={BATCH_ID}'], indirect=True)
@pytest.mark.parametrize('blocked_report_asset', [
    pytest.param('/static/js/pages/bulk/report.js', id='vue-without-legacy-renderer'),
    pytest.param('/static/task-center/bulk.js', id='readonly-after-module-import-fails'),
], indirect=True)
def test_direct_detail_report_with_each_renderer(bulk_browser, blocked_report_asset):
    page, expect, calls = bulk_browser
    if blocked_report_asset.endswith('/report.js'):
        expect(page.get_by_role('heading', name=FIRST_NAME)).to_be_visible()
        expect(page.get_by_role('heading', name='账号明细')).to_be_visible()
        assert not any(path.endswith('/report') for path, _ in calls)
        page.get_by_role('button', name='查看报告').click()
    report = page.get_by_role('region', name='批次报告', exact=True)
    expect(report.get_by_role('heading', name='查套餐完成报告')).to_be_visible()
    expect(report.get_by_text('当前结果 · 每个账号取最近一轮 · 3 个账号')).to_be_visible()

    def assert_metric(section, title, expected):
        metric = section.get_by_text(title, exact=True).locator('..').locator('dd')
        expect(metric).to_have_text(expected)

    assert_metric(report.locator('.bulk-report-outcomes'), '成功', '2个')
    assert_metric(report.locator('.bulk-report-outcomes'), '失败', '1个')
    assert_metric(report.get_by_role('region', name='账号执行耗时'), '平均耗时', '1 分 15 秒')
    assert_metric(report.get_by_role('region', name='AT 检查与自动刷新'), '刷新成功', '1个')
    assert_metric(report.get_by_role('region', name='当前订阅套餐'), 'Plus', '2个')
    assert_metric(report.get_by_role('region', name='优惠结果'), '半价优惠', '1个')
    report.get_by_text('更多查询统计', exact=False).click()
    assert_metric(report.locator('details[open]'), '国家项查询成功', '7')
    assert [args for path, args in calls if path == f'bulk/batches/{BATCH_ID}/report'] == [
        {'view': ['current']},
    ]
    assert all(path != 'bulk/batches' for path, _ in calls)


def test_column_filters_and_cursor_navigation(bulk_browser):
    page, expect, calls = bulk_browser
    listing = page.get_by_role('region', name='批次列表', exact=True)
    row = listing.locator(f'tr[data-bulk-row="{BATCH_ID}"]')
    expect(row).to_contain_text(FIRST_NAME)
    expect(row.get_by_role('progressbar')).to_have_accessible_name('已结束 3 个，共 3 个')
    pager = listing.get_by_role('navigation', name='批次分页')
    previous = pager.get_by_role('button', name='上一页')
    following = pager.get_by_role('button', name='下一页')
    expect(previous).to_be_disabled()
    search(page, '合成')
    for label, choice in [('操作类型', '查询套餐'), ('状态', '已结束')]:
        listing.get_by_role('button', name=f'筛选{label}').click()
        page.get_by_role('radio', name=choice, exact=True).check()
        page.keyboard.press('Escape')
    listing.get_by_role('button', name='筛选创建时间').click()
    page.get_by_label('开始日期', exact=True).fill('2026-01-01')
    page.get_by_label('截止日期', exact=True).fill('2026-01-31')
    page.get_by_role('button', name='关闭创建时间筛选').click()
    expect(page.get_by_label('截止日期', exact=True)).to_be_hidden()
    following.click()
    expect(listing.get_by_role('button', name=SECOND_NAME)).to_be_visible()
    filtered = {
        'page_size': ['20'], 'q': ['合成'], 'operation_key[]': ['plan_check'], 'control_state[]': ['ended'],
        'created_from': ['2026-01-01T00:00:00.000Z'], 'created_before': ['2026-02-01T00:00:00.000Z'],
    }
    assert ('bulk/batches', dict(filtered, cursor=[CURSOR])) in calls
    assert list_query(page)['cursor'] == [CURSOR]
    expect(following).to_be_disabled()
    previous.click()
    expect(row).to_contain_text(FIRST_NAME)
    assert [args for path, args in calls if path == 'bulk/batches'][-1] == filtered
    assert 'cursor' not in list_query(page)
    expect(previous).to_be_disabled()
    listing.get_by_role('button', name='清除筛选').click()
    expect(listing.get_by_role('button', name='清除筛选')).to_have_count(0)
    expect(row.locator('[data-bulk-open]')).to_be_enabled()
    assert [args for path, args in calls if path == 'bulk/batches'][-1] == {'page_size': ['20']}


def test_legacy_routes_history_and_tab_visibility(bulk_browser):
    page, expect, calls = bulk_browser
    listing = page.get_by_role('region', name='批次列表', exact=True)
    row = listing.locator(f'tr[data-bulk-row="{BATCH_ID}"]')
    search(page, '合成')
    row.get_by_role('button', name=FIRST_NAME).click()
    expect(page.locator('.bulk-detail-page-heading h2')).to_have_text(FIRST_NAME)
    assert not any(path.endswith('/report') for path, _ in calls)
    assert urlsplit(page.url).fragment == f'bulk/detail?batch_id={BATCH_ID}'
    page.go_back()
    expect(row).to_be_visible()
    assert list_query(page)['q'] == ['合成']
    row.get_by_role('button', name='失败 1').click()
    expect(page.locator('[data-bulk-target-count-row] .list-filter-summary')).to_contain_text('失败')
    page.get_by_role('button', name='筛选结果状态').click()
    expect(page.get_by_role('radio', name='失败 1', exact=True)).to_be_checked()
    page.keyboard.press('Escape')
    expect(page.get_by_role('region', name='批次报告')).to_have_count(0)
    assert (f'bulk/batches/{BATCH_ID}/targets',
            {'view': ['current'], 'page_size': ['50'], 'state[]': ['failed']}) in calls
    page.go_back()
    row.get_by_role('button', name='查看报告').click()
    report = page.get_by_role('region', name='批次报告')
    expect(report.get_by_role('heading', name='查套餐完成报告')).to_be_visible()
    expect(report).to_be_focused()
    page.go_back()
    expect(row).to_be_visible()
    search(page, '无匹配')
    expect(listing.get_by_text('没有匹配的批次')).to_be_visible()
    listing.get_by_role('button', name='新建批次').click()
    expect(page.locator('[data-bulk-create-form]')).to_be_visible()
    assert urlsplit(page.url).fragment == 'bulk/create'
    page.go_back()
    expect(listing.get_by_text('没有匹配的批次')).to_be_visible()
    assert list_query(page)['q'] == ['无匹配']
    with page.expect_response(lambda response: urlsplit(response.url).path == '/api/bulk/batches'):
        page.clock.fast_forward(8000)
    expect(listing).to_have_attribute('aria-busy', 'false')
    page.locator('button[data-tab="overview"]').click()
    expect(listing).not_to_be_visible()
    count = sum(path == 'bulk/batches' for path, _ in calls)
    page.clock.fast_forward(15_000)
    assert sum(path == 'bulk/batches' for path, _ in calls) == count
    page.go_back()
    expect(listing.get_by_text('没有匹配的批次')).to_be_visible()
    assert list_query(page)['q'] == ['无匹配']


@pytest.mark.parametrize('bulk_browser', ['#bulk/list?' + urlencode({'q': '合成', 'cursor': CURSOR})],
                         indirect=True, ids=['cold-link'])
def test_direct_link_and_late_response_after_navigation(bulk_browser, release_delayed_response):
    page, expect, calls = bulk_browser
    listing = page.get_by_role('region', name='批次列表', exact=True)
    expect(listing.get_by_role('button', name=SECOND_NAME)).to_be_visible()
    reads = [args for path, args in calls if path == 'bulk/batches']
    assert reads == [{'page_size': ['20'], 'q': ['合成'], 'cursor': [CURSOR]}]
    listing.get_by_role('button', name='返回首页').click()
    first = listing.get_by_role('button', name=FIRST_NAME)
    expect(first).to_be_visible()
    assert list_query(page) == {'q': ['合成']}
    # 入口前安装的替身仅让合成慢响应在取消后继续完成。
    with page.expect_request(lambda req: parse_qs(urlsplit(req.url).query).get('q') == ['滞后响应']):
        search(page, '滞后响应')
    expect(listing).to_have_attribute('aria-busy', 'true')
    page.locator('button[data-tab="overview"]').click()
    expect(listing).not_to_be_visible()
    page.go_back()  # Return to the initial slow query, then leave it before either read completes.
    page.go_back()
    expect(first).to_be_visible()
    assert list_query(page) == {'q': ['合成']}
    with page.expect_response(lambda res: parse_qs(urlsplit(res.url).query).get('q') == ['滞后响应']) as late:
        release_delayed_response.set()
    assert late.value.json()['data']['items'][0]['name'] == '已离开页面的旧结果'
    page.wait_for_load_state('networkidle')
    expect(first).to_be_visible()
    expect(listing.get_by_text('已离开页面的旧结果')).to_have_count(0)


def test_create_back_button_keeps_pointer_target_during_preview(bulk_browser, release_delayed_response):
    page, expect, _ = bulk_browser
    listing = page.get_by_role('region', name='批次列表', exact=True)
    bulk = page.get_by_role('region', name='批量任务', exact=True)
    bulk.get_by_role('button', name='新建批次', exact=True).click()
    back = bulk.get_by_role('button', name='返回批次列表', exact=False)
    expect(back).to_be_visible()
    page.get_by_role('searchbox', name='邮箱或姓名').fill('等待预览')
    with page.expect_request(lambda req: '等待预览' in parse_qs(urlsplit(req.url).query).get('query', [''])[0]):
        page.clock.fast_forward(350)
    before = back.bounding_box()
    assert before is not None
    page.mouse.move(before['x'] + before['width'] / 2, before['y'] + before['height'] / 2)
    page.mouse.down()
    release_delayed_response.set()
    expect(page.locator('[data-bulk-side-warning]')).to_have_text('本批将处理 6410 个账号。')
    assert back.bounding_box() == before
    page.mouse.up()
    expect(listing).to_be_visible()
    assert urlsplit(page.url).fragment == 'bulk/list'
