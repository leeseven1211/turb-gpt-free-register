// @vitest-environment jsdom
import {effectScope, nextTick} from 'vue';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {tasksApi, type OperationList} from '../../api/tasks';
import {useTaskList} from './useTaskList';
vi.mock('../../api/tasks', async importOriginal => ({...await importOriginal<typeof import('../../api/tasks')>(), tasksApi: {list: vi.fn()}}));
const scopes: ReturnType<typeof effectScope>[] = [];
function setup() { const scope = effectScope(); scopes.push(scope); return scope.run(useTaskList)!; }
function response(id: number): OperationList { return {ok: true, items: [{id, task_type: 'plan_check', status: 'success'}], total: 1, page: 1, page_size: 20, revision: String(id)}; }
beforeEach(() => { vi.useFakeTimers(); vi.mocked(tasksApi.list).mockReset(); Object.defineProperty(document, 'hidden', {configurable: true, value: false}); });
afterEach(() => { scopes.forEach(scope => scope.stop()); scopes.length = 0; vi.useRealTimers(); });
describe('任务列表请求生命周期', () => {
  it('枚举与日期立即读取，同一轮多个条件及页码归一只发一次请求', async () => {
    vi.mocked(tasksApi.list).mockImplementation(async query => ({...response(1), total: 100, page: query.page}));
    const list = setup(); list.setVisible(true); await nextTick(); await nextTick();
    list.page.value = 3; await nextTick(); await nextTick();
    vi.mocked(tasksApi.list).mockClear();
    list.filters.status = 'failed'; list.filters.type = 'token_refresh'; list.filters.created_from = '2026-11-01';
    await nextTick(); await nextTick();
    expect(tasksApi.list).toHaveBeenCalledTimes(1);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({status: 'failed', type: 'token_refresh', created_from: '2026-11-01', page: 1, include_facets: 1}), expect.any(AbortSignal));
    await vi.advanceTimersByTimeAsync(300);
    expect(tasksApi.list).toHaveBeenCalledTimes(1);
    list.filters.created_to = '2026-11-13'; await nextTick(); await nextTick();
    expect(tasksApi.list).toHaveBeenCalledTimes(2);
  });
  it('文本编辑保留260毫秒防抖，后续页筛选归一不提前请求', async () => {
    vi.mocked(tasksApi.list).mockImplementation(async query => ({...response(1), total: 100, page: query.page}));
    const list = setup(); list.setVisible(true); await nextTick(); await nextTick();
    list.page.value = 3; await nextTick(); await nextTick();
    vi.mocked(tasksApi.list).mockClear();
    list.filters.target = 'a'; await nextTick();
    expect(list.page.value).toBe(1);
    await vi.advanceTimersByTimeAsync(200);
    list.filters.target = 'ab'; await nextTick();
    await vi.advanceTimersByTimeAsync(259);
    expect(tasksApi.list).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(tasksApi.list).toHaveBeenCalledTimes(1);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({target: 'ab', page: 1}), expect.any(AbortSignal));
  });
  it('离散筛选取代待发文本读取，隐藏页取消待发刷新', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue(response(1));
    const list = setup(); list.setVisible(true); await nextTick(); await nextTick();
    vi.mocked(tasksApi.list).mockClear();
    list.filters.target = 'fixture'; await nextTick();
    await vi.advanceTimersByTimeAsync(100);
    list.filters.status = 'failed'; await nextTick(); await nextTick();
    expect(tasksApi.list).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(300);
    expect(tasksApi.list).toHaveBeenCalledTimes(1);
    list.filters.type = 'token_refresh'; list.setVisible(false); await nextTick(); await nextTick();
    await vi.advanceTimersByTimeAsync(300);
    expect(tasksApi.list).toHaveBeenCalledTimes(1);
  });
  it('后来的筛选结果不会被迟到的请求覆盖', async () => {
    let resolveOld!: (result: OperationList) => void;
    vi.mocked(tasksApi.list).mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; })).mockResolvedValue(response(2));
    const list = setup(); list.setVisible(true); await nextTick();
    list.filters.status = 'failed'; await nextTick(); await vi.advanceTimersByTimeAsync(261);
    expect(list.items.value[0]?.id).toBe(2);
    resolveOld(response(1)); await Promise.resolve(); await nextTick();
    expect(list.items.value[0]?.id).toBe(2);
  });
  it('可见时轮询不带统计，隐藏后停止请求', async () => {
    vi.mocked(tasksApi.list).mockResolvedValue(response(1));
    const list = setup(); list.setVisible(true); await nextTick(); await vi.advanceTimersByTimeAsync(0);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({include_facets: 1, include_batches: 0}), expect.any(AbortSignal));
    await vi.advanceTimersByTimeAsync(5001);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({include_facets: 0, include_batches: 0}), expect.any(AbortSignal));
    list.setVisible(false); const calls = vi.mocked(tasksApi.list).mock.calls.length;
    await vi.advanceTimersByTimeAsync(20000); expect(tasksApi.list).toHaveBeenCalledTimes(calls);
  });
  it('同一筛选条件切换页码和每页条数时复用统计，过期后重新读取', async () => {
    const statistics = {status: [{value: 'failed', count: 100}]};
    const request = vi.mocked(tasksApi.list);
    request.mockImplementation(async query => ({
      ...response(1), total: 100, page: query.page, page_size: query.page_size,
      ...(query.include_facets ? {facets: statistics} : {}),
    }));
    const list = setup();
    list.applyFilters({status: 'failed'});
    list.setVisible(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(request).toHaveBeenLastCalledWith(
      expect.objectContaining({status: 'failed', page: 1, page_size: 20, include_facets: 1}), expect.any(AbortSignal),
    );

    list.page.value = 2;
    await vi.advanceTimersByTimeAsync(0);
    expect(request).toHaveBeenLastCalledWith(
      expect.objectContaining({status: 'failed', page: 2, page_size: 20, include_facets: 0}), expect.any(AbortSignal),
    );
    list.size.value = 50;
    await vi.advanceTimersByTimeAsync(0);
    expect(request).toHaveBeenLastCalledWith(
      expect.objectContaining({status: 'failed', page: 2, page_size: 50, include_facets: 0}), expect.any(AbortSignal),
    );
    expect(list.facets.value).toEqual(statistics);

    list.filters.status = 'success';
    await vi.advanceTimersByTimeAsync(0);
    expect(request).toHaveBeenLastCalledWith(
      expect.objectContaining({status: 'success', page: 1, page_size: 50, include_facets: 1}), expect.any(AbortSignal),
    );
    await vi.advanceTimersByTimeAsync(30_000);
    expect(request).toHaveBeenLastCalledWith(
      expect.objectContaining({status: 'success', page: 1, page_size: 50, include_facets: 1}), expect.any(AbortSignal),
    );
  });
  it('刷新失败保留已展示结果并给出可重试错误', async () => {
    vi.mocked(tasksApi.list).mockResolvedValueOnce(response(7)).mockRejectedValue(new Error('网络中断'));
    const list = setup(); await list.refresh(); await list.refresh();
    expect(list.items.value[0]?.id).toBe(7); expect(list.error.value).toBe('网络中断');
  });
  it('相同 revision 保留列表对象和选择，筛选变化重新获取统计和列表', async () => {
    vi.mocked(tasksApi.list).mockImplementation(async () => ({...response(1), facets: {status: [{value: 'success', count: 1}]}}));
    const list = setup(); list.setVisible(true); await nextTick(); await vi.advanceTimersByTimeAsync(0);
    const first = list.items.value;
    const facets = list.facets.value;
    list.toggle(1, true);
    vi.mocked(tasksApi.list).mockImplementation(async () => response(1));
    await list.refresh();
    expect(list.items.value).toBe(first);
    expect(list.facets.value).toBe(facets);
    expect(list.selected.value.has(1)).toBe(true);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({include_facets: 0, include_batches: 0}), expect.any(AbortSignal));
    list.filters.status = 'failed'; await nextTick(); await vi.advanceTimersByTimeAsync(261);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({status: 'failed', include_facets: 1, include_batches: 0}), expect.any(AbortSignal));
    expect(list.items.value).not.toBe(first);
    expect(list.selected.value.size).toBe(0);
  });
  it('手动刷新绕过统计缓存并替换在途请求，迟到轮询不会覆盖最新统计', async () => {
    let resolvePolling!: (result: OperationList) => void;
    vi.mocked(tasksApi.list).mockResolvedValueOnce(response(1))
      .mockImplementationOnce(() => new Promise(resolve => { resolvePolling = resolve; }))
      .mockResolvedValue({...response(2), facets: {status: [{value: 'failed', count: 2}]}});
    const list = setup(); await list.refresh();
    const polling = list.refresh();
    const pollingSignal = vi.mocked(tasksApi.list).mock.calls[1]![1]!;
    expect(vi.mocked(tasksApi.list).mock.calls[1]![0]).toMatchObject({include_facets: 0, include_batches: 0});
    await list.refresh({metadata: true});
    expect(pollingSignal.aborted).toBe(true);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({include_facets: 1, include_batches: 0}), expect.any(AbortSignal));
    resolvePolling({...response(1), facets: {status: [{value: 'success', count: 1}]}}); await polling;
    expect(list.items.value[0]?.id).toBe(2);
    expect(list.facets.value.status).toEqual([{value: 'failed', count: 2}]);
    await list.refresh({metadata: true});
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({include_facets: 1}), expect.any(AbortSignal));
  });
});
