import {effectScope, nextTick, ref} from 'vue';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {flushPromises} from '@vue/test-utils';
import type {BulkListDependencies, BulkNavigation, BulkPageData, BulkRecord} from './contracts';
import {useBulkList} from './useBulkList';

const scopes: ReturnType<typeof effectScope>[] = [];
afterEach(() => {scopes.splice(0).forEach(scope => scope.stop());});
function page(id = '9007199254740993', cursor: string | null = null, summary?: BulkRecord): BulkPageData {
  return {items: [{id, name: '批次'}], page: {has_more: !!cursor, next_cursor: cursor, page_size: 20}, ...(summary ? {summary} : {})};
}
function fixture(initial: Partial<BulkNavigation> = {}) {
  const navigation = ref<BulkNavigation>({tab: 'bulk', view: 'list', ...initial});
  const request = vi.fn<(path: string, options?: RequestInit) => Promise<unknown>>().mockResolvedValue(page());
  const callbacks: BulkListDependencies['callbacks'] = {
    navigate: vi.fn(), updateNavigation: vi.fn(extra => {navigation.value = {...navigation.value, ...extra};}),
    notify: vi.fn(), formatDateTime: String, openTask: vi.fn(),
  };
  const scope = effectScope(); scopes.push(scope);
  const list = scope.run(() => useBulkList(() => navigation.value, {api: {request: <T>(path: string, options?: RequestInit) => request(path, options) as Promise<T>}, callbacks}))!;
  list.setVisible(true); void list.refresh();
  return {navigation, request, callbacks, list, scope};
}

describe('批次列表读取与游标归属', () => {
  it('真实参数保留bigint与游标，不从本页构造total', async () => {
    const h = fixture({q: '批次 甲', operation: 'plan_check', state: 'paused', cursor: 'opaque/+==' , created_from: '2026-11-01', created_to: '2026-11-16'});
    await flushPromises();
    const url = new URL(h.request.mock.calls[0]![0], 'http://local');
    expect(url.pathname).toBe('/batches');
    expect(Object.fromEntries(url.searchParams)).toMatchObject({page_size: '20', q: '批次 甲', 'operation_key[]': 'plan_check', 'control_state[]': 'paused', cursor: 'opaque/+=='});
    expect(url.searchParams.get('created_from')).toBe(new Date('2026-11-01T00:00:00').toISOString());
    expect(url.searchParams.get('created_to')).toBe(new Date('2026-11-16T23:59:59').toISOString());
    expect(h.list.items.value[0]?.id).toBe('9007199254740993');
    expect(h.list.summary.value).toEqual({});
    expect(h.list.hasPrevious.value).toBe(false);
  });

  it('前页仅取真实访问历史，改筛选清空游标并写回导航', async () => {
    const h = fixture(); await flushPromises();
    h.request.mockResolvedValueOnce(page('2', 'next.two'));
    await h.list.refresh();
    h.request.mockResolvedValueOnce(page('1', null));
    await h.list.next(); await flushPromises();
    expect(h.list.navigation.value.cursor).toBe('next.two');
    expect(h.list.hasPrevious.value).toBe(true);
    expect(h.callbacks.updateNavigation).toHaveBeenLastCalledWith({cursor: 'next.two'});
    await h.list.previous(); await flushPromises();
    expect(h.list.navigation.value.cursor).toBe('');
    expect(h.list.hasPrevious.value).toBe(false);
    await h.list.applyFilters({q: 'different', state: 'ended'}); await flushPromises();
    expect(h.callbacks.updateNavigation).toHaveBeenLastCalledWith({q: 'different', state: 'ended', cursor: ''});
    expect(new URL(h.request.mock.calls.at(-1)![0], 'http://local').searchParams.has('cursor')).toBe(false);
  });

  it('浏览器恢复游标不虚构上一页，明确回到起点才清除游标', async () => {
    const h = fixture(); await flushPromises();
    h.navigation.value = {tab: 'bulk', view: 'list', cursor: 'history-only'};
    await flushPromises();
    expect(h.list.hasPrevious.value).toBe(false);
    await h.list.previous();
    expect(h.list.navigation.value.cursor).toBe('history-only');
    await h.list.first(); await flushPromises();
    expect(h.list.navigation.value.cursor).toBe('');
  });

  it('较旧请求即使不响应abort也不能覆盖新筛选，导航回声不重复读取', async () => {
    const h = fixture(); await flushPromises();
    let resolveOld!: (value: BulkPageData) => void;
    h.request.mockImplementationOnce(() => new Promise(resolve => {resolveOld = resolve as typeof resolveOld;}));
    const old = h.list.refresh();
    const signal = h.request.mock.calls.at(-1)![1]?.signal;
    h.request.mockResolvedValueOnce(page('27', null, {total_batches: 7}));
    await h.list.applyFilters({q: 'new'}); await flushPromises();
    expect(signal?.aborted).toBe(true);
    const count = h.request.mock.calls.length;
    resolveOld(page('11', null, {total_batches: 100})); await old; await nextTick();
    expect(h.list.items.value[0]?.id).toBe('27');
    expect(h.list.summary.value.total_batches).toBe(7);
    expect(h.request).toHaveBeenCalledTimes(count);
  });

  it('同范围刷新失败保留已读行，cursor错误只报告不自动跳范围', async () => {
    const h = fixture({cursor: 'expired'}); await flushPromises();
    h.request.mockRejectedValueOnce(Object.assign(new Error('游标不属于当前范围'), {code: 'cursor_scope_mismatch', status: 422}));
    await h.list.refresh();
    expect(h.list.items.value[0]?.id).toBe('9007199254740993');
    expect(h.list.error.value).toContain('游标不属于当前范围');
    expect(h.list.navigation.value.cursor).toBe('expired');
    expect(h.callbacks.updateNavigation).not.toHaveBeenCalled();
  });

  it('销毁中止读取且迟到响应不更新，没有内部轮询定时器', async () => {
    const h = fixture(); await flushPromises();
    let resolve!: (value: BulkPageData) => void;
    h.request.mockImplementationOnce(() => new Promise(done => {resolve = done as typeof resolve;}));
    const pending = h.list.refresh(); const signal = h.request.mock.calls.at(-1)![1]?.signal;
    h.scope.stop(); expect(signal?.aborted).toBe(true);
    resolve(page('99')); await pending;
    expect(h.list.items.value[0]?.id).toBe('9007199254740993');
  });

  it('同范围正在读取时共享请求，不被下一次轮询反复取消', async () => {
    const h = fixture(); await flushPromises();
    let resolve!: (value: BulkPageData) => void;
    h.request.mockImplementationOnce(() => new Promise(done => {resolve = done as typeof resolve;}));
    const first = h.list.refresh(); const signal = h.request.mock.calls.at(-1)![1]?.signal;
    const second = h.list.refresh();
    expect(h.request).toHaveBeenCalledTimes(2);
    expect(signal?.aborted).toBe(false);
    resolve(page('41')); await Promise.all([first, second]);
    expect(h.list.items.value[0]?.id).toBe('41');
  });

  it('隐藏中止请求并忽略晚到响应，恢复可见只由Shell显式刷新', async () => {
    const h = fixture(); await flushPromises();
    let resolve!: (value: BulkPageData) => void;
    h.request.mockImplementationOnce(() => new Promise(done => {resolve = done as typeof resolve;}));
    const pending = h.list.refresh(); const signal = h.request.mock.calls.at(-1)![1]?.signal;
    h.list.setVisible(false); expect(signal?.aborted).toBe(true);
    h.navigation.value = {tab: 'bulk', view: 'list', cursor: 'hidden-cursor'};
    await flushPromises(); await h.list.refresh();
    expect(h.request).toHaveBeenCalledTimes(2);
    resolve(page('99')); await pending;
    expect(h.list.items.value[0]?.id).toBe('9007199254740993');
    h.list.setVisible(true); await flushPromises();
    expect(h.request).toHaveBeenCalledTimes(2);
    await h.list.refresh();
    expect(h.request).toHaveBeenCalledTimes(3);
    expect(h.request.mock.calls.at(-1)![0]).toContain('cursor=hidden-cursor');
  });
});
