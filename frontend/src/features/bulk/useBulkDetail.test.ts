import {effectScope, ref} from 'vue';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {flushPromises} from '@vue/test-utils';
import type {BulkDetailDependencies, BulkNavigation, BulkRecord} from './contracts';
import {useBulkDetail} from './useBulkDetail';

const scopes: ReturnType<typeof effectScope>[] = [];
afterEach(() => scopes.splice(0).forEach(scope => scope.stop()));
const batch = '9007199254740993', round = '9007199254740995';
const detail = (extra: BulkRecord = {}) => ({id: batch, operation_key: 'plan_check', summary_revision: 7, target_count: 20, summary: {failed: 11, partial_success: 2, not_executed: 3, cancelled: 4}, control: {state: 'active', revision: 9, paused: false}, rounds_head: [], ...extra});
function fixture(initial: Partial<BulkNavigation> = {}) {
  const navigation = ref<BulkNavigation>({tab: 'bulk', view: 'detail', batch_id: batch, ...initial});
  let clock = 100_000;
  const request = vi.fn(async <T>(path: string): Promise<T> => (path.includes('/targets?') ? {items: [{canonical_target_id: '41', account_id: '9'}], page: {has_more: true, next_cursor: 'next', page_size: 50}} : path.includes('/report?') ? {operation_key: 'plan_check', phase: 'running', summary_revision: 7} : detail()) as T);
  const submit = vi.fn(async <T>(): Promise<T> => ({id: round, state: 'preparing'} as T));
  const callbacks: BulkDetailDependencies['callbacks'] = {navigate: vi.fn(), updateNavigation: vi.fn(extra => {navigation.value = {...navigation.value, ...extra};}), notify: vi.fn(), formatDateTime: String, openTask: vi.fn(), copyBatch: vi.fn()};
  const deps = {api: {request}, intents: {submit, pending: () => [], recover: vi.fn()}, callbacks, now: () => clock} as BulkDetailDependencies;
  const scope = effectScope(); scopes.push(scope);
  const state = scope.run(() => useBulkDetail(() => navigation.value, deps))!;
  return {navigation, request, submit, callbacks, state, scope, advance: () => {clock += 10_001;}};
}
describe('批次详情范围与写入契约', () => {
  it('报告独立于结果筛选与游标，IDs不转成Number', async () => {
    const h = fixture({round_id: round, result_state: 'failed', cursor: 'opaque/+='}); await flushPromises();
    const urls = h.request.mock.calls.map(([path]) => new URL(path, 'http://local'));
    const target = urls.find(url => url.pathname.endsWith('/targets'))!;
    expect(target.searchParams.get('cursor')).toBe('opaque/+='); expect(target.searchParams.get('state[]')).toBe('failed');
    const report = urls.find(url => url.pathname.endsWith('/report'))!;
    expect(report.pathname).toBe(`/batches/${batch}/report`); expect(Object.fromEntries(report.searchParams)).toEqual({view: 'round', round_id: round});
  });
  it('跨页保留canonical选择，换筛选清除；直达cursor不虚构前页', async () => {
    const h = fixture({cursor: 'external'}); await flushPromises();
    expect(h.state.hasPrevious.value).toBe(false); h.state.toggleTarget('41', true);
    await h.state.next(); await flushPromises(); expect([...h.state.selected.value]).toEqual(['41']); expect(h.state.hasPrevious.value).toBe(true);
    await h.state.setFilter('failed'); await flushPromises(); expect(h.state.selected.value.size).toBe(0); expect(h.navigation.value.cursor).toBe('');
  });
  it('旧范围响应与abort忽略不会污染新详情或报告', async () => {
    const h = fixture(); await flushPromises(); let release!: (x: unknown) => void;
    h.request.mockImplementationOnce(() => new Promise(resolve => {release = resolve;}));
    const old = h.state.refresh(); const signal = (h.request.mock.calls.at(-1) as unknown as [string, RequestInit])[1].signal;
    h.navigation.value = {...h.navigation.value, batch_id: '42'}; await flushPromises();
    expect(signal?.aborted).toBe(true); release(detail({name: '旧范围'})); await old;
    expect(h.state.detail.value?.name).not.toBe('旧范围');
  });
  it('确认前冻结重跑body，路由变化取消未提交确认', async () => {
    const h = fixture({round_id: round}); await flushPromises();
    await h.state.retry(false, 'unsuccessful');
    expect(h.state.confirmation.value?.body).toMatchObject({source: {view: 'round', round_id: round, observed_summary_revision: 7, observed_target_count: 20}, selection: {kind: 'result_filter', states: ['failed', 'partial_success', 'not_executed', 'cancelled']}});
    h.navigation.value = {...h.navigation.value, batch_id: '42'}; await flushPromises();
    await h.state.confirm(); expect(h.submit).not.toHaveBeenCalled(); expect(h.state.confirmation.value).toBeNull();
  });
  it.each(['failed', 'partial_success', 'not_executed', 'cancelled', 'unsuccessful'])('重跑集合%s有固定revision与计数', async choice => {
    const h = fixture(); await flushPromises(); await h.state.retry(false, choice); if(h.state.confirmation.value) await h.state.confirm();
    expect(h.submit).toHaveBeenCalledWith(`retry:${batch}`, `/batches/${batch}/rounds`, expect.objectContaining({source: expect.objectContaining({observed_summary_revision: 7}), retry_mode: 'automatic', selection: {kind: 'result_filter', states: choice === 'unsuccessful' ? ['failed', 'partial_success', 'not_executed', 'cancelled'] : [choice]}}));
    expect(h.state.pendingRound.value).toBe(round);
  });
  it('勾选重跑发送名单目标ID，控制四动作有正确batch/round范围', async () => {
    const h = fixture({round_id: round}); await flushPromises(); h.state.toggleTarget('41', true); await h.state.retry(true);
    expect(h.submit.mock.calls[0]).toEqual([`retry:${batch}`, `/batches/${batch}/rounds`, expect.objectContaining({selection: {kind: 'targets', target_ids: ['41']}})]);
    for(const action of ['pause', 'resume', 'cancel_not_started', 'request_stop']) {
      h.state.detail.value = detail({control: {state: 'active', revision: 9, paused: action === 'resume'}});
      await h.state.control(action); if(h.state.confirmation.value) await h.state.confirm();
      expect(h.submit).toHaveBeenLastCalledWith(`control:${batch}:${action}`, `/batches/${batch}/control`, {action, expected_control_revision: 9, scope: ['pause', 'resume'].includes(action) ? {kind: 'batch'} : {kind: 'round', round_id: round}});
    }
  });
  it('禁用/取消不写入，冲突刷新，401和断网展示错误而不虚报成功', async () => {
    const h = fixture(); await flushPromises(); h.state.detail.value = detail({control: {state: 'ended', revision: 9}});
    await h.state.control('pause'); expect(h.submit).not.toHaveBeenCalled(); h.state.detail.value = detail();
    await h.state.control('request_stop'); h.state.cancelConfirmation(); expect(h.submit).not.toHaveBeenCalled();
    for(const error of [Object.assign(new Error('修订冲突'), {code: 'control_revision_conflict'}), Object.assign(new Error('请登录'), {status: 401}), new Error('断网')]) {
      h.submit.mockRejectedValueOnce(error); await h.state.control('pause'); expect(h.state.actionError.value).toContain(error.message);
    }
    expect(h.callbacks.notify).not.toHaveBeenCalled();
  });
  it('报告节流，结束revision变化立即刷新；失败保留报告', async () => {
    const h = fixture(); await flushPromises(); const reports = () => h.request.mock.calls.filter(([p]) => p.includes('/report?')).length;
    expect(reports()).toBe(1); await h.state.refresh(); expect(reports()).toBe(1); h.advance(); await h.state.refresh(); expect(reports()).toBe(2);
    h.request.mockImplementationOnce(async <T>() => detail({control: {state: 'ended', revision: 9}, summary_revision: 8}) as T);
    await h.state.refresh(); expect(reports()).toBe(3);
    h.request.mockRejectedValueOnce(new Error('报告离线')); await h.state.refreshReport(true);
    expect(h.state.report.value?.operation_key).toBe('plan_check'); expect(h.state.reportError.value).toContain('报告离线');
  });
  it('轮次追加去重保留selected，销毁中止未完成读取', async () => {
    const h = fixture({round_id: round}); await flushPromises();
    h.state.detail.value = detail({selected_round: {id: round, round_no: 4}});
    h.request.mockResolvedValueOnce(detail({rounds_head: [{id: '11', round_no: 5}], selected_round: {id: round, round_no: 4}, rounds_next_cursor: 'older'}));
    await h.state.refresh(); h.request.mockResolvedValueOnce({items: [{id: '11', round_no: 5}, {id: '10', round_no: 3}], page: {next_cursor: null, has_more: false, page_size: 20}});
    await h.state.moreRounds(); expect(h.state.rounds.value.map(r => r.id)).toEqual(['11', round, '10']);
    let release!: (v: unknown) => void; h.request.mockImplementationOnce(() => new Promise(resolve => {release = resolve;}));
    const refresh = h.state.refresh(); const signal = (h.request.mock.calls.at(-1) as unknown as [string, RequestInit])[1].signal;
    h.scope.stop(); expect(signal?.aborted).toBe(true); release(detail({name: '销毁后'})); await refresh; expect(h.state.detail.value?.name).not.toBe('销毁后');
  });
  it('隐藏中止报告，恢复后读新报告；旧响应不可回写',async()=>{
    const h=fixture();await flushPromises();let release!:(value:unknown)=>void;
    h.request.mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;}));const old=h.state.refreshReport(true);const signal=(h.request.mock.calls.at(-1) as unknown as [string,RequestInit])[1].signal;
    h.state.setVisible(false);expect(signal?.aborted).toBe(true);expect(h.state.needsPolling.value).toBe(false);release({operation_key:'plan_check',old:true});await old;expect(h.state.report.value?.old).toBeUndefined();
    const previous=h.request.mock.calls.length;await h.state.refresh(true);expect(h.request).toHaveBeenCalledTimes(previous);h.state.setVisible(true);await h.state.refresh(true);expect(h.state.report.value?.operation_key).toBe('plan_check');
  });
  it('换轮次立即清报告，旧报告迟到不替换新轮次',async()=>{
    const h=fixture();await flushPromises();let release!:(value:unknown)=>void;
    h.request.mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;}));const old=h.state.refreshReport(true);
    h.navigation.value={...h.navigation.value,round_id:round};expect(h.state.report.value).toBeNull();await flushPromises();release({operation_key:'plan_check',old:true});await old;expect(h.state.report.value?.old).toBeUndefined();
  });
  it('确认冻结revision与选中列表，后续刷新不偷换请求',async()=>{
    const h=fixture();await flushPromises();for(let index=1;index<=10;index++)h.state.toggleTarget(String(index),true);await h.state.retry(true);
    const captured=h.state.confirmation.value!.body;h.state.clearSelection();h.state.detail.value=detail({summary_revision:100});await h.state.confirm();expect(h.submit).toHaveBeenCalledWith(`retry:${batch}`,`/batches/${batch}/rounds`,captured);expect(captured.source).toMatchObject({observed_summary_revision:7,observed_target_count:10});
  });
  it('重跑准备取消只通知归属不变，pending/能力禁止控制',async()=>{
    const h=fixture();await flushPromises();h.state.pendingRound.value=round;
    h.request.mockResolvedValueOnce(detail({rounds_head:[{id:round,round_no:2,state:'completed',completion_reason:'cancelled_before_freeze'}]}));await h.state.refresh();expect(h.state.pendingRound.value).toBeNull();expect(h.callbacks.notify).toHaveBeenLastCalledWith('重跑准备已取消，当前结果归属不变。');
    h.state.detail.value=detail({control:{state:'active',pending:true}});await h.state.control('pause');expect(h.submit).not.toHaveBeenCalled();h.state.detail.value=detail({capabilities:{request_stop:false}});await h.state.control('request_stop');expect(h.state.confirmation.value).toBeNull();
  });
  it('同scope并发refresh复用读取，Shell重复activate不取消前次',async()=>{
    const h=fixture();await flushPromises();let release!:(value:unknown)=>void;h.request.mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;}));const first=h.state.refresh();const signal=(h.request.mock.calls.at(-1) as unknown as [string,RequestInit])[1].signal;const count=h.request.mock.calls.length;const second=h.state.refresh();expect(h.request).toHaveBeenCalledTimes(count);expect(signal?.aborted).toBe(false);release(detail());await Promise.all([first,second]);
  });
});
