import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {createAccountsApi} from './accounts';
import {createAccountQueryAdapter, type AccountQueryAdapter} from '../features/accounts/queryAdapter';

const legacySource = readFileSync(resolve(process.cwd(), '../webui/static/js/shared/account-query.js'), 'utf8');
function setup() {
  const sandbox = {window: {} as {AccountQuery: AccountQueryAdapter}, URLSearchParams};
  runInNewContext(legacySource, sandbox, {filename: 'account-query.js'});
  const query = createAccountQueryAdapter(sandbox.window.AccountQuery);
  return {query, api: createAccountsApi(query)};
}
function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {status, headers: {'Content-Type': 'application/json'}});
}
function emptyPage() {
  return {ok: true, compact: true, items: [], total: 0, page: 1, page_size: 10,
    offset: 0, limit: 10, revision: '0:fixture', facets: {}, search_terms: []};
}
afterEach(() => vi.unstubAllGlobals());

describe('账号列表 HTTP 读契约', () => {
  it('通过真实 AccountQuery 请求完整单页，保留所有筛选、公开投影和 envelope', async () => {
    const {api, query} = setup();
    const payload = {
      ok: true, compact: true, items: [{
        id: 17, email: 'fixture@example.test', has_access_token: false, has_account_password: true,
        totp_enabled: false, email_invalid: false, email_invalid_reason: null, email_invalid_at: null,
        email_invalid_source: null, archived: false, email_source: 'outlook', registration_driver: 'future_driver',
        plus_promo_kind: 'none', plus_promo_eligible: false, plus_trial_eligible: false,
        plus_discount_eligible: false, plan_check_ok: false, plan_check_status: 'failed',
        quota_http_status: 0, quota_windows: [], account_promotions: [],
        plan_check_country_results: [], promotion_query_snapshot: {version: 1, countries: []},
        registration_retry: {available: false, source_job_id: null, action: null, label: '不可重跑', reason: '未找到来源', active: false},
        fingerprint_summary: {browser: 'chrome/149/macOS', device_pixel_ratio: 2, language: 'en-US'},
        last_password_auth_status: 'unknown',
      }],
      total: 27, page: 2, page_size: 10, offset: 10, limit: 10, revision: 'opaque:revision',
      facets: {plan: [{value: 'future-plan', count: 0}], source: [{value: 'outlook', count: 27}]},
      search_terms: [{field: 'note', label: '备注', value: 'a/b & c', display_value: 'a/b & c', query_without: 'driver:protocol'}],
    };
    const fetch = vi.fn().mockResolvedValue(json(payload)); vi.stubGlobal('fetch', fetch);
    const controller = new AbortController();
    const spec = query.normalize({
      archived: 'only', q: 'note:"a/b & c" driver:protocol', date_from: '2026-11-01', date_to: '2026-11-15',
      plan: ['plus', 'free'], limit: 300000,
      filters: {id: '9007199254740993', email: 'some+name@example.test', source: ['outlook', 'icloud_hide'],
        registration_driver: ['future_driver', 'protocol_oss_2'], token: ['none', 'has'], password: ['has'],
        promotion: ['free_trial', 'none'], totp: ['disabled'], risk: ['pending'], codex: ['future_state'],
        account_status: ['active'], email_status: ['unmarked']},
    });
    expect(await api.list(spec, 2, 10, controller.signal)).toEqual(payload);
    expect(fetch).toHaveBeenCalledExactlyOnceWith(
      '/api/accounts?paged=1&page=2&page_size=10&archived=only&q=note%3A%22a%2Fb+%26+c%22+driver%3Aprotocol&date_from=2026-11-01&date_to=2026-11-15&email=some%2Bname%40example.test&plan=free%2Cplus&id=9007199254740993&source=icloud_hide%2Coutlook&registration_driver=future_driver%2Cprotocol_oss_2&token=has%2Cnone&password=has&promotion=free_trial%2Cnone&totp=disabled&risk=pending&codex=future_state&account_status=active&email_status=unmarked',
      {credentials: 'same-origin', signal: controller.signal},
    );
    // query.limit belongs to a fixed batch population; it must not override this page.
    expect(spec.limit).toBe(300000);
  });

  it('空查询仍保留旧参数空键，默认页面显式请求10条，零total不被改写', async () => {
    const {api, query} = setup();
    const fetch = vi.fn().mockResolvedValue(json(emptyPage())); vi.stubGlobal('fetch', fetch);
    const controller = new AbortController();
    expect(await api.list(query.normalize(), 1, 10, controller.signal)).toEqual(emptyPage());
    expect(fetch).toHaveBeenCalledExactlyOnceWith(
      '/api/accounts?paged=1&page=1&page_size=10&archived=0&q=&date_from=&date_to=&email=&plan=&id=&source=&registration_driver=&token=&password=&promotion=&totp=&risk=&codex=&account_status=&email_status=',
      {credentials: 'same-origin', signal: controller.signal},
    );
  });

  it('页状态查询使用相同条件并追加compact，返回清空字段和明细revision而不补取敏感详情', async () => {
    const {api, query} = setup();
    const payload = {ok: true, items: [{
      id: 17, email: 'fixture@example.test', has_access_token: false, has_account_password: false,
      email_invalid: false, email_invalid_reason: null, email_invalid_at: null, email_invalid_source: null,
      last_password_auth_status: null, plan_promotion_country: null,
      plan_details_revision: 'rev-2', plan_summary: {promotions: null, countries: [{
        country: 'JP', status: 'failed', http_status: 403, error: '禁止访问', promotions: [],
      }]}, plan_check_error: null, extract_link_error: null, extract_link_message: null, codex_error: null,
    }], total: 1, page: 3, page_size: 20, offset: 40, limit: 20, revision: 'status-rev',
      status_fields: ['plan_check_error', 'extract_link_error', 'codex_error'],
      queue: {workers: 3, registration_workers: 4, queue_limit: 100, min_interval: 0.4, jitter: 0.3}};
    const fetch = vi.fn().mockResolvedValue(json(payload)); vi.stubGlobal('fetch', fetch);
    const controller = new AbortController();
    const spec = query.normalize({archived: 'all', q: 'ID:17', filters: {email: 'fixture@example.test', promotion: ['none']}});
    expect(await api.statuses(spec, 3, 20, controller.signal)).toEqual(payload);
    expect(fetch).toHaveBeenCalledExactlyOnceWith(
      '/api/accounts/plan-check-status?paged=1&page=3&page_size=20&archived=all&q=ID%3A17&date_from=&date_to=&email=fixture%40example.test&plan=&id=&source=&registration_driver=&token=&password=&promotion=none&totp=&risk=&codex=&account_status=&email_status=&compact=1',
      {credentials: 'same-origin', signal: controller.signal},
    );
  });

  it.each([
    ['旧数组', [{id: 17, email: 'fixture@example.test'}]],
    ['null响应', null],
    ['只有items且缺分页元数据', {ok: true, items: []}],
  ])('分页客户端拒绝%s，不把它当空页或推导total', async (_name, payload) => {
    const {api, query} = setup();
    const fetch = vi.fn().mockResolvedValue(json(payload)); vi.stubGlobal('fetch', fetch);
    await expect(api.list(query.normalize(), 1, 10)).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('普通列表不会把完整status envelope误当列表成功响应', async () => {
    const {api, query} = setup();
    const fetch = vi.fn().mockResolvedValue(json({ok: true, items: [], total: 0, page: 1, page_size: 10,
      offset: 0, limit: 10, revision: 'status', status_fields: [], queue: {workers: 3}}));
    vi.stubGlobal('fetch', fetch);
    await expect(api.list(query.normalize(), 1, 10)).rejects.toThrow();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('高级搜索400保留顶层code与原消息，查询层不重试或改写搜索', async () => {
    const {api, query} = setup();
    const message = '注册地区不支持该值，请输入有效的两位国家代码，例如「地区:JP」或「地区:日本」。';
    const fetch = vi.fn().mockResolvedValue(json({ok: false, code: 'account_search_invalid', error: message}, 400));
    vi.stubGlobal('fetch', fetch);
    await expect(api.list(query.normalize({q: '地区:JJ'}), 1, 10))
      .rejects.toMatchObject({status: 400, code: 'account_search_invalid', message});
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(new URL(String(fetch.mock.calls[0]![0]), 'http://fixture.test').searchParams.get('q')).toBe('地区:JJ');
  });

  it.each([
    [401, {ok: false, error: '需要登录'}, '需要登录'],
    [503, {ok: false, error: {code: 'database_unavailable', message: '暂时不可用'}}, '暂时不可用'],
    [200, {ok: false, error: '业务读取失败'}, '业务读取失败'],
  ])('HTTP %s或业务错误不被默认值掩盖成空列表', async (status, payload, message) => {
    const {api, query} = setup();
    const fetch = vi.fn().mockResolvedValue(json(payload, status)); vi.stubGlobal('fetch', fetch);
    await expect(api.list(query.normalize(), 1, 10)).rejects.toMatchObject({status, message});
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('HTML登录响应保留鉴权失败，不输出原始页面', async () => {
    const {api, query} = setup();
    const fetch = vi.fn().mockResolvedValue(new Response('<html>private-response-content</html>',
      {status: 401, headers: {'Content-Type': 'text/html'}})); vi.stubGlobal('fetch', fetch);
    const error = await api.list(query.normalize(), 1, 10).catch(cause => cause);
    expect(error).toMatchObject({status: 401, message: '登录已失效，请重新登录后刷新。'});
    expect(error.message).not.toContain('private-response-content');
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('中止信号贯穿fetch且AbortError原样传播，不触发重试', async () => {
    const {api, query} = setup();
    const controller = new AbortController();
    const failure = new DOMException('取消读取', 'AbortError');
    const fetch = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init!.signal!.addEventListener('abort', () => reject(failure), {once: true});
    })); vi.stubGlobal('fetch', fetch);
    const pending = api.list(query.normalize(), 1, 10, controller.signal);
    controller.abort();
    await expect(pending).rejects.toBe(failure);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0]![1]).toMatchObject({credentials: 'same-origin', signal: controller.signal});
  });

  it('网络失败原样传播且不通过再次请求覆盖失败证据', async () => {
    const {api, query} = setup(); const failure = new TypeError('连接已中断');
    const fetch = vi.fn().mockRejectedValue(failure); vi.stubGlobal('fetch', fetch);
    await expect(api.statuses(query.normalize(), 1, 10)).rejects.toBe(failure);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
