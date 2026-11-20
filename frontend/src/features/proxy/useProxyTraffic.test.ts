import { effectScope, nextTick } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useProxyTraffic } from './useProxyTraffic';
import type {
  ProxyTrafficApi,
  ProxyQuery,
  ProxyRecordView,
  ProxyRow,
  ProxySummary,
  ProxyPoolSnapshot,
} from './contracts';
const scopes: ReturnType<typeof effectScope>[] = [];
function page(items: ProxyRow[] = [{ id: 1, lease_id: 'lease-1' }], total = 80, offset = 0, limit = 20) {
  return { items, count: items.length, total, offset, limit, has_more: offset + items.length < total };
}
function setup() {
  const requests: { view: ProxyRecordView; query: ProxyQuery; signal?: AbortSignal }[] = [];
  let read = (view: ProxyRecordView, query: ProxyQuery, _signal?: AbortSignal) =>
    Promise.resolve(page([{ id: 1, lease_id: view }], 80, (query.page - 1) * query.size, query.size));
  const api: ProxyTrafficApi = {
    page: (view, query, signal) => {
      requests.push({ view, query: { ...query }, signal });
      return read(view, query, signal);
    },
    summary: vi.fn(async () => ({
      ok: true,
      total_bytes: 1024,
      today_bytes: 100,
      today_request_count: 0,
      today_browser_count: 7,
      today_route_count: 3,
      purposes: ['plan-check'],
      lease_states: ['leased', 'released'],
    })),
    pool: vi.fn(async () => ({ policy: {}, counts: { ready: 1 } })),
  };
  const scope = effectScope();
  scopes.push(scope);
  const owner = scope.run(() => useProxyTraffic({ api }))!;
  return {
    owner,
    requests,
    api,
    setRead: (fn: typeof read) => {
      read = fn;
    },
  };
}
async function settle() {
  await nextTick();
  for (let i = 0; i < 16; i++) await Promise.resolve();
  await nextTick();
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((yes) => {
    resolve = yes;
  });
  return { resolve, promise };
}
beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(document, 'hidden', { configurable: true, value: false });
});
afterEach(() => {
  scopes.splice(0).forEach((scope) => scope.stop());
  vi.useRealTimers();
});
describe('single proxy read owner', () => {
  it('does no hidden read, coalesces first visible load and polls only while visible', async () => {
    const h = setup();
    await h.owner.load();
    expect(h.requests).toHaveLength(0);
    h.owner.setVisible(true);
    await Promise.all([h.owner.load(), h.owner.load()]);
    await settle();
    expect(h.requests).toHaveLength(3);
    expect(h.requests[0]!.query).toEqual({
      page: 1,
      size: 20,
      window: 'all',
      purpose: 'all',
      state: 'all',
      search: '',
    });
    await vi.advanceTimersByTimeAsync(30000);
    await settle();
    expect(h.requests).toHaveLength(6);
    h.owner.setVisible(false);
    await vi.advanceTimersByTimeAsync(60000);
    expect(h.requests).toHaveLength(6);
  });
  it('an initial targeted update still initializes all lists and global facets', async () => {
    const h = setup(),
      old = deferred<ReturnType<typeof page>>();
    h.setRead(() => old.promise);
    h.owner.setVisible(true);
    await settle();
    h.owner.setState('history', 'released');
    h.setRead((view, q) => Promise.resolve(page([{ id: 2, lease_id: view }], 1, 0, q.size)));
    await settle();
    expect(h.requests.slice(3).map((r) => r.view)).toEqual(['current', 'history', 'traffic']);
    expect(h.owner.summary.value?.total_bytes).toBe(1024);
    expect(h.api.pool).toHaveBeenCalledTimes(2);
    old.resolve(page([{ id: 99 }]));
    await settle();
    expect(h.owner.pages.current.items[0]?.id).toBe(2);
  });
  it('does not start a correction read after the page becomes hidden', async () => {
    const h = setup();
    h.owner.setVisible(true);
    await settle();
    const late = deferred<ReturnType<typeof page>>();
    h.setRead(() => late.promise);
    h.owner.setPage('history', 4);
    await settle();
    const before = h.requests.length;
    h.owner.setVisible(false);
    late.resolve(page([], 1, 60));
    await settle();
    expect(h.requests).toHaveLength(before);
  });
  it('late summary and pool cannot publish after hiding', async () => {
    const h = setup(),
      metrics = deferred<ProxySummary>(),
      inventory = deferred<ProxyPoolSnapshot | null>();
    h.api.summary = () => metrics.promise;
    h.api.pool = () => inventory.promise;
    h.owner.setVisible(true);
    await settle();
    h.owner.setVisible(false);
    metrics.resolve({ total_bytes: 999, today_bytes: 999 });
    inventory.resolve({ policy: {}, counts: { ready: 99 } });
    await settle();
    expect(h.owner.summary.value).toBeNull();
    expect(h.owner.pool.value).toBeNull();
    expect(h.owner.loading.value).toBe(false);
  });
  it('shares search/window/purpose but keeps state and pages per view', async () => {
    const h = setup();
    h.owner.setVisible(true);
    await settle();
    h.requests.length = 0;
    h.owner.updateFilters({ search: ' token ', purpose: 'plan-check', window: '24h' });
    await vi.advanceTimersByTimeAsync(260);
    await settle();
    expect(h.requests).toHaveLength(3);
    expect(h.requests.find((r) => r.view === 'history')!.query).toMatchObject({
      search: ' token ',
      purpose: 'plan-check',
      window: '24h',
      page: 1,
    });
    h.requests.length = 0;
    h.owner.setState('history', 'released');
    await settle();
    expect(h.requests.map((r) => r.view)).toEqual(['history']);
    expect(h.requests[0]!.query.state).toBe('released');
    expect(h.owner.pages.traffic.state).toBe('all');
  });
  it('invalidates immediately during debounce so late old lists, summary and pool cannot commit', async () => {
    const h = setup(),
      old = deferred<ReturnType<typeof page>>();
    h.setRead(() => old.promise);
    h.owner.setVisible(true);
    await settle();
    h.owner.updateFilters({ search: 'new' });
    expect(h.requests[0]!.signal?.aborted).toBe(true);
    old.resolve(page([{ id: 99, lease_id: 'stale' }]));
    await settle();
    expect(h.owner.pages.current.items).toEqual([]);
    expect(h.owner.summary.value).toBeNull();
    h.setRead((view, query) => Promise.resolve(page([{ id: 2, lease_id: view + '-new' }], 1, 0, query.size)));
    await vi.advanceTimersByTimeAsync(260);
    await settle();
    expect(h.owner.pages.current.items[0]?.id).toBe(2);
    expect(h.owner.summary.value?.today_request_count).toBe(0);
  });
  it('hiding/document hiding aborts reads and a return refreshes once with final filters', async () => {
    const h = setup(),
      old = deferred<ReturnType<typeof page>>();
    h.setRead(() => old.promise);
    h.owner.setVisible(true);
    await settle();
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    document.dispatchEvent(new Event('visibilitychange'));
    expect(h.requests[0]!.signal?.aborted).toBe(true);
    h.owner.updateFilters({ window: '7d' });
    old.resolve(page([{ id: 88 }]));
    await settle();
    expect(h.owner.pages.current.items).toEqual([]);
    h.setRead((_v, q) => Promise.resolve(page([{ id: 3 }], 1, 0, q.size)));
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    document.dispatchEvent(new Event('visibilitychange'));
    await settle();
    expect(h.requests).toHaveLength(6);
    expect(h.owner.pages.current.items[0]?.id).toBe(3);
  });
  it('corrects a shrinking final page once and resets page on size/filter changes', async () => {
    const h = setup();
    h.owner.setVisible(true);
    await settle();
    h.requests.length = 0;
    h.setRead((_view, q) =>
      Promise.resolve(page(q.page === 2 ? [{ id: 22 }] : [], 21, (q.page - 1) * q.size, q.size)),
    );
    h.owner.setPage('history', 4);
    await settle();
    expect(h.requests.map((r) => r.query.page)).toEqual([4, 2]);
    expect(h.owner.pages.history.page).toBe(2);
    h.requests.length = 0;
    h.owner.setPage('history', 1);
    h.owner.setSize('history', 50);
    await settle();
    expect(h.requests).toHaveLength(1);
    expect(h.requests[0]!.query).toMatchObject({ page: 1, size: 50 });
  });
  it('keeps inventory and other records while paging or filtering one table', async () => {
    const h = setup(),
      pool = vi.fn(async () => ({ policy: {}, counts: { ready: 9 } }));
    h.api.pool = pool;
    h.owner.setVisible(true);
    await settle();
    h.requests.length = 0;
    const inventory = h.owner.pool.value;
    const traffic = h.owner.pages.traffic.items;

    h.owner.setPage('history', 2);
    await settle();
    h.owner.setSize('history', 50);
    await settle();
    h.owner.setState('history', 'released');
    await settle();

    expect(h.requests.map(({ view, query }) => [view, query.page, query.size, query.state])).toEqual([
      ['history', 2, 20, 'all'],
      ['history', 1, 50, 'all'],
      ['history', 1, 50, 'released'],
    ]);
    expect(h.owner.pool.value).toBe(inventory);
    expect(h.owner.pages.traffic.items).toBe(traffic);
    expect(pool).toHaveBeenCalledTimes(1);
    expect(h.api.summary).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(30000);
    await settle();
    expect(h.requests.slice(3).map(({ view }) => view)).toEqual(['current', 'history', 'traffic']);
    expect(pool).toHaveBeenCalledTimes(2);
    expect(h.api.summary).toHaveBeenCalledTimes(2);
  });
  it('库存读取失败后在分页时补读库存，恢复后继续局部分页', async () => {
    const h = setup();
    vi.mocked(h.api.pool).mockResolvedValueOnce(null);
    h.owner.setVisible(true);
    await settle();
    expect(h.owner.pool.value).toBeNull();
    expect(h.owner.summary.value?.total_bytes).toBe(1024);
    h.requests.length = 0;

    h.owner.setPage('history', 2);
    await settle();
    expect(h.owner.pool.value?.counts.ready).toBe(1);

    h.owner.setPage('history', 3);
    await settle();
    expect(h.requests.map(({ view, query }) => [view, query.page])).toEqual([
      ['history', 2],
      ['history', 3],
    ]);
    expect(h.api.pool).toHaveBeenCalledTimes(2);
    expect(h.api.summary).toHaveBeenCalledTimes(1);
  });
  it('keeps a pending global filter when an immediate table-specific change cancels its timer', async () => {
    const h = setup();
    h.owner.setVisible(true);
    await settle();
    h.requests.length = 0;

    h.owner.updateFilters({ search: 'shared' });
    h.owner.setState('history', 'released');
    await settle();

    expect(h.requests.map(({ view }) => view)).toEqual(['current', 'history', 'traffic']);
    expect(h.requests.every(({ query }) => query.search === 'shared')).toBe(true);
    expect(h.requests[1]?.query.state).toBe('released');
    expect(h.api.pool).toHaveBeenCalledTimes(2);
  });
  it('completes a full refresh after a targeted change aborts it in flight', async () => {
    const h = setup(),
      old = deferred<ReturnType<typeof page>>();
    h.owner.setVisible(true);
    await settle();
    h.requests.length = 0;
    h.setRead(() => old.promise);
    await vi.advanceTimersByTimeAsync(30000);
    await settle();

    h.setRead((view) => Promise.resolve(page([{ id: 2, lease_id: view }], 80)));
    h.owner.setState('history', 'released');
    await settle();
    old.resolve(page([{ id: 99 }]));
    await settle();

    expect(h.requests.slice(0, 3).every(({ signal }) => signal?.aborted)).toBe(true);
    expect(h.requests.slice(3).map(({ view }) => view)).toEqual(['current', 'history', 'traffic']);
    expect(h.owner.pages.current.items[0]?.id).toBe(2);
    expect(h.api.pool).toHaveBeenCalledTimes(3);
  });
  it('discards a late targeted response after a new targeted request', async () => {
    const h = setup(),
      old = deferred<ReturnType<typeof page>>();
    h.owner.setVisible(true);
    await settle();
    h.requests.length = 0;
    h.setRead(() => old.promise);
    h.owner.setPage('history', 2);
    await settle();
    h.setRead((_view, q) => Promise.resolve(page([{ id: 50 }], 80, 0, q.size)));
    h.owner.setSize('history', 50);
    await settle();
    old.resolve(page([{ id: 99 }], 80, 20));
    await settle();

    expect(h.requests.map(({ view }) => view)).toEqual(['history', 'history']);
    expect(h.requests[0]?.signal?.aborted).toBe(true);
    expect(h.owner.pages.history.items[0]?.id).toBe(50);
    expect(h.api.pool).toHaveBeenCalledTimes(1);
  });
  it('refreshes only changed tables when switching table before a targeted response arrives', async () => {
    const h = setup(),
      old = deferred<ReturnType<typeof page>>();
    h.owner.setVisible(true);
    await settle();
    h.requests.length = 0;
    h.setRead(() => old.promise);
    h.owner.setPage('history', 2);
    await settle();
    h.setRead((view, q) =>
      Promise.resolve(page([{ id: q.page, lease_id: view }], 80, (q.page - 1) * q.size, q.size)),
    );
    h.owner.setState('traffic', 'available');
    await settle();
    old.resolve(page([{ id: 99 }], 80, 20));
    await settle();

    expect(h.requests[0]?.signal?.aborted).toBe(true);
    expect(h.requests.slice(1).map(({ view }) => view).sort()).toEqual(['history', 'traffic']);
    expect(h.owner.pages.history.items[0]?.id).toBe(2);
    expect(h.owner.pages.traffic.items[0]?.lease_id).toBe('traffic');
    expect(h.api.pool).toHaveBeenCalledTimes(1);
  });
  it('freezes the opened record across poll/filter/page and closes on module or subview navigation', async () => {
    const h = setup();
    h.owner.setVisible(true);
    await settle();
    h.owner.openDetail('history', h.owner.pages.history.items[0]!);
    expect(h.owner.detail.value?.row.lease_id).toBe('history');
    h.owner.pages.history.items[0]!.lease_id = 'mutated';
    await h.owner.load();
    expect(h.owner.detail.value?.row.lease_id).toBe('history');
    h.owner.setRecordView('traffic');
    expect(h.owner.detail.value).toBeNull();
    h.owner.openDetail('traffic', { id: 5 });
    h.owner.setView('records');
    h.owner.setView('pool');
    expect(h.owner.detail.value).toBeNull();
  });
  it('retains unrelated snapshots on a targeted failure and recovers with a full retry', async () => {
    const h = setup();
    const inventory = { policy: {}, counts: { ready: 9 } };
    const pool = vi.fn(async () => inventory);
    h.api.pool = pool;
    h.owner.setVisible(true);
    await settle();
    h.setRead(() => Promise.reject(new Error('fixture offline')));
    await h.owner.load('history');
    expect(h.owner.pages.history.items).toEqual([]);
    expect(h.owner.pages.current.items[0]?.lease_id).toBe('current');
    expect(h.owner.summary.value?.total_bytes).toBe(1024);
    expect(h.owner.error.value).toBe('fixture offline');
    expect(h.owner.pool.value).toBe(inventory);
    expect(pool).toHaveBeenCalledTimes(1);

    h.setRead((view) => Promise.resolve(page([{ id: 3, lease_id: view }])));
    await h.owner.load();
    expect(h.owner.error.value).toBe('');
    expect(h.owner.pages.current.items[0]?.id).toBe(3);
    expect(pool).toHaveBeenCalledTimes(2);
  });
});
