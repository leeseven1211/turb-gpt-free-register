import {effectScope, nextTick} from 'vue';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {useCodexList} from './useCodexList';

const scopes: ReturnType<typeof effectScope>[] = [];
const calls: {url: URL; signal?: AbortSignal | null}[] = [];
let fetchResponse: (url: URL, init: RequestInit) => Promise<Response>;
function result(filenames = ['first.json'], total = filenames.length, page = 1, facets: Record<string, unknown[]> = {}): Response {
  return Response.json({ok: true, accounts: filenames.map(filename => ({filename, email: 'same@example.test', plan: 'free', exported: false, archived: false})), total, page, page_size: 20, offset: (page - 1) * 20, limit: 20, revision: String(page), facets, summary: {total, exported: 0, pending: total}});
}
function setup() { const scope = effectScope(); scopes.push(scope); return scope.run(useCodexList)!; }
async function settle() { await nextTick(); for (let i = 0; i < 12; i++) await Promise.resolve(); await nextTick(); }
function deferred() { let resolve!: (response: Response) => void; const promise = new Promise<Response>(done => {resolve = done;}); return {resolve, promise}; }
beforeEach(() => {
  vi.useFakeTimers(); calls.length = 0;
  Object.defineProperty(document, 'hidden', {configurable: true, value: false});
  fetchResponse = async url => result([`page-${url.searchParams.get('page')}.json`], 100, Number(url.searchParams.get('page')));
  vi.stubGlobal('fetch', vi.fn((input: string, init: RequestInit = {}) => {
    const url = new URL(String(input), 'http://localhost');
    calls.push({url, signal: init.signal});
    return fetchResponse(url, init);
  }));
});
afterEach(() => { scopes.forEach(scope => scope.stop()); scopes.length = 0; vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('Codex 列表状态与请求生命周期', () => {
  it('初始隐藏不请求，首次显示用分页而非全量，持续显示不增加轮询', async () => {
    const list = setup(); await settle(); await list.refresh();
    expect(calls).toHaveLength(0);
    list.setVisible(true); list.setVisible(true); await settle();
    expect(calls).toHaveLength(1);
    expect(calls[0]!.url.pathname).toBe('/api/codex');
    expect(Object.fromEntries(calls[0]!.url.searchParams)).toMatchObject({paged: '1', page: '1', page_size: '20', archived: '0'});
    expect(list.items.value.map(item => item.filename)).toEqual(['page-1.json']);
    expect(list.loading.value).toBe(false);
    await vi.advanceTimersByTimeAsync(60000);
    expect(calls).toHaveLength(1);
  });
  it('跨页选择按filename保留，同邮箱文件不合并，取消页选不影响其他页', async () => {
    fetchResponse = async url => result(Number(url.searchParams.get('page')) === 1 ? ['a.json', 'b.json'] : ['c.json', 'd.json'], 40, Number(url.searchParams.get('page')));
    const list = setup(); list.setVisible(true); await settle(); list.togglePage(true);
    list.setPage(2); await settle(); list.togglePage(true); list.toggle('c.json', false);
    expect([...list.selected.value]).toEqual(['a.json', 'b.json', 'd.json']);
    await list.refresh(); expect([...list.selected.value]).toEqual(['a.json', 'b.json', 'd.json']);
    list.togglePage(false); expect([...list.selected.value]).toEqual(['a.json', 'b.json']);
    list.toggle('a.json', false); expect([...list.selected.value]).toEqual(['b.json']);
  });
  it('文本筛选250ms防抖并保留跨页选择，页码回一不会提前发请求', async () => {
    const list = setup(); list.setVisible(true); await settle(); list.setPage(3); await settle(); list.toggle('off-page.json', true);
    calls.length = 0;
    list.updateFilters({q: 'a'}); await settle(); expect(list.page.value).toBe(1);
    await vi.advanceTimersByTimeAsync(200);
    list.updateFilters({q: 'abc', account_id: 'opaque-id'}); await settle();
    await vi.advanceTimersByTimeAsync(249); expect(calls).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1); await settle();
    expect(calls).toHaveLength(1);
    expect(Object.fromEntries(calls[0]!.url.searchParams)).toMatchObject({q: 'abc', account_id: 'opaque-id', page: '1'});
    expect([...list.selected.value]).toEqual(['off-page.json']);
  });
  it('离散条件取代待发文本请求，同轮日期/状态只读一次并清选择', async () => {
    const list = setup(); list.setVisible(true); await settle(); list.toggle('selected.json', true); calls.length = 0;
    list.updateFilters({q: 'pending'}); await vi.advanceTimersByTimeAsync(100);
    list.updateFilters({status: 'exported'}); list.updateFilters({date_from: '2026-11-01', date_to: '2026-11-14'}); await settle();
    expect(list.selected.value.size).toBe(0); expect(calls).toHaveLength(1);
    expect(Object.fromEntries(calls[0]!.url.searchParams)).toMatchObject({q: 'pending', status: 'exported', date_from: '2026-11-01', date_to: '2026-11-14'});
    await vi.advanceTimersByTimeAsync(300); expect(calls).toHaveLength(1);
  });
  it('改变筛选时立刻失效旧请求，等待防抖期间旧响应也不能污染', async () => {
    const old = deferred(); fetchResponse = async () => old.promise;
    const list = setup(); list.setVisible(true); await settle(); const signal = calls[0]!.signal;
    list.updateFilters({q: 'new'});
    expect(signal?.aborted).toBe(true);
    old.resolve(result(['wrong-old.json'])); await settle(); expect(list.items.value).toEqual([]);
    fetchResponse = async () => result(['right-new.json']);
    await vi.advanceTimersByTimeAsync(250); await settle();
    expect(list.items.value.map(item => item.filename)).toEqual(['right-new.json']);
  });
  it('归档切换清范围且最后一个范围获胜，迟到活跃响应不覆盖', async () => {
    const active = deferred(); fetchResponse = async url => url.searchParams.get('archived') === 'only' ? result(['archived.json']) : active.promise;
    const list = setup(); list.setVisible(true); await settle(); list.toggle('old.json', true);
    list.setArchived(true); expect(list.selected.value.size).toBe(0); expect(list.total.value).toBe(0); await settle();
    expect(list.archived.value).toBe(true); expect(list.items.value[0]?.filename).toBe('archived.json');
    active.resolve(result(['old-active.json'])); await settle();
    expect(list.items.value[0]?.filename).toBe('archived.json');
    expect(calls.map(call => call.url.searchParams.get('archived'))).toEqual(['0', 'only']);
  });
  it('隐藏时归档/筛选只改状态，恢复只请求最终查询，隐藏迟到结果失效', async () => {
    const pending = deferred(); fetchResponse = async () => pending.promise;
    const list = setup(); list.setVisible(true); await settle(); list.setVisible(false);
    expect(calls[0]!.signal?.aborted).toBe(true);
    list.setArchived(true); list.updateFilters({plan: 'future'}); await list.refresh();
    pending.resolve(result(['hidden-old.json'])); await settle(); await vi.advanceTimersByTimeAsync(60000);
    expect(calls).toHaveLength(1); expect(list.items.value).toEqual([]);
    fetchResponse = async () => result(['restored.json']); list.setVisible(true); await settle();
    expect(calls).toHaveLength(2); expect(Object.fromEntries(calls[1]!.url.searchParams)).toMatchObject({archived: 'only', plan: 'future'});
    expect(list.items.value[0]?.filename).toBe('restored.json');
  });
  it('document隐藏取消读取，回到前台仅可见页面刷新且没有新增周期任务', async () => {
    const pending = deferred(); fetchResponse = async () => pending.promise;
    const list = setup(); list.setVisible(true); await settle();
    Object.defineProperty(document, 'hidden', {configurable: true, value: true}); document.dispatchEvent(new Event('visibilitychange'));
    expect(calls[0]!.signal?.aborted).toBe(true);
    pending.resolve(result(['discard.json'])); await settle(); expect(list.items.value).toEqual([]);
    fetchResponse = async () => result(['foreground.json']);
    Object.defineProperty(document, 'hidden', {configurable: true, value: false}); document.dispatchEvent(new Event('visibilitychange')); await settle();
    expect(list.items.value[0]?.filename).toBe('foreground.json');
    list.setVisible(false); document.dispatchEvent(new Event('visibilitychange')); await settle(); expect(calls).toHaveLength(2);
  });
  it('显式刷新失效先前读取，最新错误保留已读数据并可重试', async () => {
    const list = setup(); list.setVisible(true); await settle(); const old = deferred(); fetchResponse = async () => old.promise;
    const pending = list.refresh(); await settle(); const oldSignal = calls.at(-1)!.signal;
    fetchResponse = async () => Response.json({ok: false, error: '网络暂不可用'}, {status: 503}); await list.refresh();
    expect(oldSignal?.aborted).toBe(true); expect(list.error.value).toBe('网络暂不可用'); expect(list.items.value[0]?.filename).toBe('page-1.json');
    old.resolve(result(['stale-success.json'])); await pending;
    expect(list.error.value).toBe('网络暂不可用'); expect(list.items.value[0]?.filename).toBe('page-1.json');
    fetchResponse = async () => result(['retry-ok.json']); await list.refresh();
    expect(list.error.value).toBe(''); expect(list.items.value[0]?.filename).toBe('retry-ok.json');
  });
  it('共享分页同时发页码归一和size更新只读取最终页一次', async () => {
    const list = setup(); list.setVisible(true); await settle(); list.setPage(3); await settle(); calls.length = 0;
    list.setPage(1); list.setSize(50); await settle();
    expect(calls).toHaveLength(1); expect(Object.fromEntries(calls[0]!.url.searchParams)).toMatchObject({page: '1', page_size: '50'});
    list.setPage(999); await settle(); expect(list.page.value).toBe(2);
    list.setSize(NaN); list.setPage(NaN); await settle();
    expect(list.size.value).toBe(50); expect(Number.isFinite(list.page.value)).toBe(true);
  });
  it('删除导致末页越界时只回查一次，真实零总数不回退成旧条数', async () => {
    const list = setup(); list.setVisible(true); await settle(); calls.length = 0;
    fetchResponse = async url => result(Number(url.searchParams.get('page')) > 1 ? [] : ['last.json'], 1, Number(url.searchParams.get('page')));
    list.setPage(5); await settle();
    expect(calls.map(call => call.url.searchParams.get('page'))).toEqual(['5', '1']);
    expect(list.page.value).toBe(1); expect(list.items.value[0]?.filename).toBe('last.json');
    fetchResponse = async () => result([], 0); await list.refresh();
    expect(list.total.value).toBe(0); expect(list.pages.value).toBe(1); expect(list.items.value).toEqual([]);
  });
  it('连续缩小的总量最多两次读取，不递归追赶变化中的末页', async () => {
    fetchResponse = async url => result(['seed.json'], 1000, Number(url.searchParams.get('page')));
    const list = setup(); list.setVisible(true); await settle(); calls.length = 0;
    fetchResponse = async url => result([], url.searchParams.get('page') === '50' ? 200 : 0, Number(url.searchParams.get('page')));
    list.setPage(50); await settle();
    expect(calls.map(call => call.url.searchParams.get('page'))).toEqual(['50', '10']);
    expect(list.loading.value).toBe(false); expect(list.page.value).toBe(1);
    expect(list.error.value).toContain('刷新');
    await vi.advanceTimersByTimeAsync(60000); expect(calls).toHaveLength(2);
  });
  it('未知已选枚举保留，归档不混入状态筛选，全清不丢当前归档范围', async () => {
    fetchResponse = async () => result(['selected.json'], 1, 1, {plan: [{value: 'free', count: 1}], status: [{value: 'archived', count: 1}, {value: 'exported', count: 2}]});
    const list = setup(); list.setArchived(true); list.updateFilters({plan: 'future', status: 'future-state'}); list.setVisible(true); await settle();
    expect(list.filters.plan).toBe('future');
    expect(list.facets.value.plan).toContainEqual({value: 'future', count: 0});
    expect(list.facets.value.status?.map(item => item.value)).toEqual(['exported', 'future-state']);
    list.toggle('selected.json', true); list.resetFilters(); await settle();
    expect(Object.values(list.filters).every(value => value === '')).toBe(true); expect(list.selected.value.size).toBe(0);
    expect(list.archived.value).toBe(true); expect(calls.at(-1)!.url.searchParams.get('archived')).toBe('only');
  });
  it('scope卸载移除所有等待刷新和可见性监听，迟到结果不回写', async () => {
    const pending = deferred(); fetchResponse = async () => pending.promise;
    const list = setup(); list.setVisible(true); await settle(); list.updateFilters({q: 'scheduled'}); scopes[0]!.stop();
    pending.resolve(result(['disposed.json'])); await settle(); await vi.advanceTimersByTimeAsync(500);
    document.dispatchEvent(new Event('visibilitychange')); list.setVisible(true); await list.refresh(); await settle();
    expect(calls).toHaveLength(1); expect(list.items.value).toEqual([]); expect(list.loading.value).toBe(false);
  });
});
