import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ExtractStatsPage from './ExtractStatsPage.vue';

const fixture = (start = '2026-10-21') => ({
  ok: true, date_from: start, date_to: '2026-11-19', generated_at: '2026-11-18T20:10:05Z',
  totals: {total: 70, extracted: 60, paid: 30, plus_confirmed: 25, failed: 10, extraction_failed: 10,
    payment_failed: 5, extraction_rate: 60 / 70, payment_rate: 30 / 35, avg_seconds: 125},
  daily: [{date: '2026-11-18', total: 50, extracted: 41, paid: 22, plus_confirmed: 20, failed: 6},
    {date: '2026-11-19', total: 20, extracted: 19, paid: 8, plus_confirmed: 5, failed: 4}],
  providers: [{provider_id: 'synthetic', total: 70, paid: 30, extraction_rate: 0, payment_rate: null}],
  failures: [{label: '少量', code: 'low', count: 2}, {label: '<img src=x>', code: 'high', count: 8}],
  modes: [{mode: 'manual_payment', total: 40}], current: {awaiting_payment: 15, needs_review: 4}
});
const wrappers: ReturnType<typeof mount>[] = [];
function setup(visible = true) {
  const wrapper = mount(ExtractStatsPage, {props: {deps: {visible}}});
  wrappers.push(wrapper);
  return wrapper;
}
function json(data: unknown) { return Response.json(data); }
function pending() {
  let resolve!: (value: Response) => void;
  const promise = new Promise<Response>(done => {resolve = done;});
  return {promise, resolve};
}
beforeEach(() => { Object.defineProperty(document, 'hidden', {configurable: true, value: false}); });
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); vi.unstubAllGlobals(); });

it('reads the default 30-day aggregation only and displays its Beijing scope, daily rows and ratios', async () => {
  const fetch = vi.fn(async () => json(fixture())); vi.stubGlobal('fetch', fetch);
  const page = setup(); await flushPromises();
  expect(fetch).toHaveBeenCalledExactlyOnceWith('/api/extract-workbench/analytics?days=30', expect.objectContaining({method: 'GET'}));
  expect(page.get('[data-extract-stats-status]').text()).toBe('更新于 04:10:05');
  expect(page.get('.es-today').findAll('dd').map(row => row.text())).toEqual(['19', '5', '15', '4']);
  expect(page.get('.es-scope').text()).toContain('2026-10-21 — 2026-11-19');
  expect(page.get('.es-conversion').text()).toContain('出链 60 · 失败 10');
  expect(page.get('.es-conversion').text()).toContain('支付 30 · 失败 5');
  expect(page.get('.es-conversion').text()).toContain('2 分 5 秒');
  expect(page.get('svg[role=img]').findAll('circle')).toHaveLength(6);
  expect(page.get('.es-daily-details').findAll('tbody th')[1].text()).toBe('2026-11-19');
  expect(page.get('.es-daily-details').findAll('tbody tr')[1].findAll('td').map(cell => cell.text())).toEqual(['20','19','8','5','4']);
  expect(page.get('.es-failures li').text()).toContain('<img src=x>');
  expect(page.find('img').exists()).toBe(false);
  expect(page.get('.es-provider-table').text()).toContain('0.0%');
  expect(page.get('.es-provider-table').text()).toContain('—');
  expect(page.get('.es-modes').text()).toContain('57.1%');
  expect(page.findAll('a')).toHaveLength(0);
});

it('keeps results only for their filter and retries the selected days and provider', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(json(fixture())).mockRejectedValueOnce(new Error('离线'))
    .mockResolvedValueOnce(json({ok: false, error: '暂时不可用'})).mockResolvedValueOnce(json({ok: true}))
    .mockResolvedValueOnce(json({...fixture('当前筛选'), totals: {}, daily: [], providers: [], failures: [], modes: []}));
  vi.stubGlobal('fetch', fetch);
  const page = setup(); await flushPromises();
  await page.get('[data-extract-stats-refresh]').trigger('click'); await flushPromises();
  expect(page.get('[role=alert]').text()).toContain('保留上次统计');
  expect(page.get('.es-scope').text()).toContain('2026-10-21');
  await page.get('[data-extract-stats-days="90"]').trigger('click'); await flushPromises();
  expect(page.find('.es-scope').exists()).toBe(false);
  expect(page.get('[role=alert]').text()).toContain('暂时不可用');
  await page.get('[data-extract-stats-provider]').setValue('synthetic'); await flushPromises();
  expect(page.get('[role=alert]').text()).toContain('统计响应格式不完整');
  await page.get('[data-extract-stats-retry]').trigger('click'); await flushPromises();
  expect(fetch.mock.calls.at(-1)?.[0]).toBe('/api/extract-workbench/analytics?days=90&provider_id=synthetic');
  expect(page.find('[role=alert]').exists()).toBe(false);
  expect(page.get('.es-scope').text()).toContain('当前筛选');
  expect(page.get('.es-current').text()).toContain('当前所选平台');
  expect(page.get('.es-today').findAll('dd').map(cell=>cell.text())).toEqual(['0','0','15','4']);
  expect(page.find('svg[role=img]').exists()).toBe(false);
  for (const text of ['没有提链任务', '暂无平台数据', '暂无失败记录', '暂无模式数据']) expect(page.text()).toContain(text);
});

it('ignores out-of-order responses and stops reading while the page or document is hidden', async () => {
  const older = pending(), newer = pending(), hidden = pending();
  const fetch = vi.fn().mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    .mockReturnValueOnce(hidden.promise).mockResolvedValueOnce(json(fixture('返回后')));
  vi.stubGlobal('fetch', fetch);
  const page = setup(false); await flushPromises(); expect(fetch).not.toHaveBeenCalled();
  page.vm.setVisible(true);
  await page.get('[data-extract-stats-days="7"]').trigger('click');
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
  older.resolve(json(fixture('过期'))); await flushPromises();
  expect(page.get('section.extract-stats-page').attributes('aria-busy')).toBe('true');
  newer.resolve(json(fixture('已选择'))); await flushPromises();
  expect(page.get('.es-scope').text()).toContain('已选择');
  await page.get('[data-extract-stats-refresh]').trigger('click');
  Object.defineProperty(document, 'hidden', {configurable: true, value: true}); document.dispatchEvent(new Event('visibilitychange'));
  hidden.resolve(json(fixture('后台'))); await flushPromises();
  expect(page.get('.es-scope').text()).toContain('已选择');
  page.vm.setVisible(false);
  Object.defineProperty(document,'hidden',{configurable:true,value:false}); document.dispatchEvent(new Event('visibilitychange'));
  expect(fetch).toHaveBeenCalledTimes(3);
  page.vm.setVisible(true); await flushPromises();
  expect(page.get('.es-scope').text()).toContain('返回后');
});

it('keeps an unusable daily response retryable and tolerates absent optional breakdowns', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(json({totals: {}, daily: [null]}))
    .mockResolvedValueOnce(json({totals: {}, daily: [{total: 1}], failures: {}, providers: 'missing', modes: [null]}));
  vi.stubGlobal('fetch', fetch);
  const page = setup(); await flushPromises();
  expect(page.get('[role=alert]').text()).toContain('统计响应格式不完整');
  await page.get('[data-extract-stats-retry]').trigger('click'); await flushPromises();
  expect(page.find('[role=alert]').exists()).toBe(false);
  expect(page.get('.es-trend svg').findAll('circle')).toHaveLength(3);
  expect(page.text()).toContain('暂无平台数据');
});
