import { effectScope } from 'vue';
import { flushPromises } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { EventsResponse, LogsResponse, OperationDetail, ProgressResponse, TaskId } from '../../../api/tasks';
import { artifactUrl, failureMessage, matchesStep, mergeEvents, orderedEvents, stepDuration, visibleSteps, type Step } from './model';
import { useTaskDetail } from './useTaskDetail';

const step: Step = { id: 'authenticate', label: '登录验证', state: 'success', raw_stages: ['login', 'email_otp'] };
const taskResponse = (id: number, status = 'success'): OperationDetail => ({ ok: true, task: { id, task_type: 'plan_check', status,
  last_run_id: id * 10, runs: [{ id: id * 10, run_no: 1, status }, { id: id * 10 + 1, run_no: 2, status }] } });
const progressResponse = (id: number, runId: number): ProgressResponse => ({ ok: true,
  progress: { task_id: id, run_id: runId, revision: '1', main_steps: [step], outcome: { status: 'success' } } });
const eventsResponse = (id: number, more = false): EventsResponse => ({ ok: true, items: [{ id, message: `事件 ${id}` }], next_after_id: id, has_more: more });
const logsResponse = (cursor: number): LogsResponse => ({ ok: true, items: [{ message: `日志 ${cursor}` }], next_cursor: cursor, has_more: false, available: true, run_terminal: true });
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function fixture() {
  const api = {
    detail: vi.fn(async (id: TaskId) => taskResponse(Number(id))),
    progress: vi.fn(async (id: TaskId, run: TaskId) => progressResponse(Number(id), Number(run))),
    events: vi.fn(async () => eventsResponse(1)),
    logs: vi.fn(async () => logsResponse(100)),
  };
  const scope = effectScope();
  const finished = vi.fn();
  const detail = scope.run(() => useTaskDetail(api, finished))!;
  scopes.push(scope);
  return { api, detail, finished };
}
const scopes: ReturnType<typeof effectScope>[] = [];
afterEach(() => { scopes.splice(0).forEach(scope => scope.stop()); vi.useRealTimers(); });

describe('任务详情展示语义', () => {
  it('用权威步骤关联原始阶段，未关联记录不会混入筛选', () => {
    expect(matchesStep({ id: 1, stage: 'email_otp' }, 'authenticate', [step])).toBe(true);
    expect(matchesStep({ fields: { main_step_id: 'authenticate' } }, 'authenticate', [step], true)).toBe(true);
    expect(matchesStep({ id: 2, stage: 'payment' }, 'authenticate', [step])).toBe(false);
    expect(visibleSteps([step, { ...step, id: 'unused', state: 'skipped' }])).toEqual([step]);
  });
  it('明确主步骤优先于共用原始阶段，歧义历史记录不串到其他阶段', () => {
    const steps: Step[] = [{ id: 'refresh_dispatch', label: '刷新分派', state: 'success', raw_stages: ['dispatch'] },
      { id: 'codex_dispatch', label: '授权分派', state: 'success', raw_stages: ['dispatch'] }];
    const record = { id: 1, main_step_id: 'codex_dispatch', stage: 'dispatch' };
    expect(matchesStep(record, 'refresh_dispatch', steps)).toBe(false);
    expect(matchesStep(record, 'codex_dispatch', steps)).toBe(true);
    expect(matchesStep({ id: 1, stage: 'dispatch' }, 'refresh_dispatch', steps)).toBe(false);
    expect(matchesStep({ fields: { main_step_id: 'codex_dispatch', raw_stage: 'dispatch' } }, 'refresh_dispatch', steps, true)).toBe(false);
    expect(matchesStep({ id: 1, detail: { raw_stage: 'email_otp' } }, 'authenticate', [step])).toBe(true);
  });
  it('事件展示按校正时间排序，增量缓存去重且不改变游标次序', () => {
    const merged = mergeEvents([{ id: 3, created_at: '2026-01-02' }], [{ id: 3 }, { id: 4, created_at: '2026-01-01' }]);
    expect(merged.map(item => item.id)).toEqual([3, 4]);
    expect(orderedEvents(merged).map(item => item.id)).toEqual([4, 3]);
  });
  it('诊断不足如实展示，优先显示已分类原因，暂停耗时冻结', () => {
    expect(failureMessage({ message: '结果未知' })).toBe('失败诊断记录缺失');
    expect(failureMessage({ message: '结果未知', error_info: { cause_summary: '邮箱验证码等待超时' } })).toBe('邮箱验证码等待超时');
    expect(stepDuration({ ...step, state: 'debug_paused', started_at: '2026-01-01T00:00:00Z', debug_pause: { paused_at: '2026-01-01T00:00:10Z' } }, Date.now())).toBe(10000);
  });
  it('诊断链接只开放现有同源产物接口', () => {
    expect(artifactUrl('/api/operations/1/runs/2/debug/har')).toBe('/api/operations/1/runs/2/debug/har');
    expect(artifactUrl('javascript:alert(1)')).toBeNull();
    expect(artifactUrl('//example.com/file')).toBeNull();
  });
});

describe('详情请求与生命周期', () => {
  it('打开时分开请求当前 Run 的进度与事件，日志按需读取', async () => {
    const { api, detail, finished } = fixture();
    await detail.open(2);
    expect(detail.runId.value).toBe(20);
    expect(api.progress).toHaveBeenCalledWith(2, 20, expect.any(AbortSignal));
    expect(api.events).toHaveBeenCalledWith(2, 20, { limit: 500 }, expect.any(AbortSignal));
    expect(api.logs).not.toHaveBeenCalled();
    await detail.selectTab('logs');
    expect(api.logs).toHaveBeenCalledWith(2, 20, { limit: 500 }, expect.any(AbortSignal));
    expect(finished).toHaveBeenCalledTimes(1);
  });
  it('最近事件页有更早历史时，不把 has_more 当成向后游标', async () => {
    const { api, detail } = fixture();
    api.events.mockResolvedValueOnce(eventsResponse(900, true));
    await detail.open(1);
    expect(detail.eventsEarlier.value).toBe(true);
    expect(detail.eventsMore.value).toBe(false);
    await detail.loadEvents('next');
    expect(api.events).toHaveBeenCalledTimes(1);
    api.events.mockResolvedValueOnce(eventsResponse(500, true));
    await detail.loadEvents('start');
    expect(api.events).toHaveBeenLastCalledWith(1, 10, { after_id: 0, limit: 500 }, expect.any(AbortSignal));
    expect(detail.eventsMode.value).toBe('start');
    expect(detail.eventsEarlier.value).toBe(false);
    expect(detail.eventsMore.value).toBe(true);
    await detail.loadEvents();
    expect(api.events).toHaveBeenCalledTimes(2);
    api.events.mockResolvedValueOnce(eventsResponse(900));
    await detail.loadEvents('next');
    expect(api.events).toHaveBeenLastCalledWith(1, 10, { after_id: 500, limit: 500 }, expect.any(AbortSignal));
    expect(detail.events.value.map(item => item.id)).toEqual([500, 900]);
  });
  it('切换运行后忽略旧运行迟到的事件响应', async () => {
    const { api, detail } = fixture();
    await detail.open(1);
    const old = deferred<EventsResponse>();
    api.events.mockReturnValueOnce(old.promise);
    const pending = detail.loadEvents();
    api.events.mockResolvedValueOnce(eventsResponse(22));
    await detail.selectRun(11);
    old.resolve(eventsResponse(99));
    await pending;
    expect(detail.runId.value).toBe(11);
    expect(detail.events.value.map(item => item.id)).toEqual([22]);
  });
  it('指定历史运行不可用时不静默替换为最新运行', async () => {
    const { api, detail } = fixture();
    await detail.open(1, 99);
    expect(detail.runId.value).toBe(99);
    expect(detail.error.value).toContain('所选运行 #99 不存在或已不可用');
    expect(detail.progress.value).toBeNull();
    expect(api.progress).not.toHaveBeenCalled();
    expect(api.events).not.toHaveBeenCalled();
    await detail.selectRun(10);
    expect(detail.error.value).toBe('');
    expect(detail.progress.value?.run_id).toBe(10);
  });
  it('所选运行消失时清除证据且迟到事件不能重新填入', async () => {
    const { api, detail } = fixture();
    await detail.open(1, 10);
    const old = deferred<EventsResponse>();
    api.events.mockReturnValueOnce(old.promise);
    const pending = detail.loadEvents();
    api.detail.mockResolvedValueOnce({ ok: true, task: { ...taskResponse(1).task, runs: [{ id: 11, status: 'success' }] } });
    await detail.refresh();
    old.resolve(eventsResponse(99));
    await pending;
    expect(detail.runId.value).toBe(10);
    expect(detail.events.value).toEqual([]);
    expect(detail.progress.value).toBeNull();
  });
  it('外部传入步骤筛选保持到初次加载，手动切换运行清空旧步骤', async () => {
    const { detail } = fixture();
    await detail.open(1, 10, 'authenticate');
    expect(detail.stepFilter.value).toBe('authenticate');
    await detail.selectRun(11);
    expect(detail.stepFilter.value).toBeNull();
    expect(detail.progress.value?.run_id).toBe(11);
  });
  it('打开另一个任务时旧详情不能覆盖新详情', async () => {
    const { api, detail } = fixture();
    const old = deferred<OperationDetail>();
    api.detail.mockReturnValueOnce(old.promise);
    const pending = detail.open(1);
    await detail.open(2);
    old.resolve(taskResponse(1));
    await pending;
    expect(detail.task.value?.id).toBe(2);
    expect(detail.progress.value?.task_id).toBe(2);
  });
  it('自动增量读取不会抢占用户正在执行的从头读取', async () => {
    const { api, detail } = fixture();
    await detail.open(1);
    const pendingPage = deferred<EventsResponse>();
    api.events.mockReturnValueOnce(pendingPage.promise);
    const pending = detail.loadEvents('start');
    await detail.loadEvents();
    expect(api.events).toHaveBeenCalledTimes(2);
    pendingPage.resolve(eventsResponse(500, true));
    await pending;
    expect(detail.eventsMode.value).toBe('start');
    expect(detail.events.value[0]?.id).toBe(500);
  });
  it('自动轮询已读取过当前运行的事件时保持读取反馈静默', async () => {
    vi.useFakeTimers();
    const { api, detail } = fixture();
    api.detail.mockImplementation(async id => taskResponse(Number(id), 'running'));
    await detail.open(1);
    const pendingIncremental = deferred<EventsResponse>();
    api.events.mockReturnValueOnce(pendingIncremental.promise);

    await vi.advanceTimersByTimeAsync(2000);

    expect(api.events).toHaveBeenCalledTimes(2);
    expect(detail.eventsLoading.value).toBe(false);
    pendingIncremental.resolve(eventsResponse(2));
    await flushPromises();
  });
  it('自动轮询已读取过当前运行的日志时保持读取反馈静默', async () => {
    vi.useFakeTimers();
    const { api, detail } = fixture();
    api.detail.mockImplementation(async id => taskResponse(Number(id), 'running'));
    await detail.open(1);
    await detail.selectTab('logs');
    const pendingIncremental = deferred<LogsResponse>();
    api.logs.mockReturnValueOnce(pendingIncremental.promise);

    await vi.advanceTimersByTimeAsync(2000);

    expect(api.logs).toHaveBeenCalledTimes(2);
    expect(detail.logsLoading.value).toBe(false);
    pendingIncremental.resolve(logsResponse(101));
    await flushPromises();
  });
  it('静默事件读取在途时手动重试复用请求并显示反馈', async () => {
    vi.useFakeTimers();
    const { api, detail } = fixture();
    api.detail.mockImplementation(async id => taskResponse(Number(id), 'running'));
    await detail.open(1);
    const pendingIncremental = deferred<EventsResponse>();
    api.events.mockReturnValueOnce(pendingIncremental.promise);

    await vi.advanceTimersByTimeAsync(2000);
    const retry = detail.loadEvents();

    expect(detail.eventsLoading.value).toBe(true);
    expect(api.events).toHaveBeenCalledTimes(2);
    pendingIncremental.resolve(eventsResponse(2));
    await retry;
    expect(detail.eventsLoading.value).toBe(false);
  });
  it('静默日志读取在途时手动重试复用请求并显示反馈', async () => {
    vi.useFakeTimers();
    const { api, detail } = fixture();
    api.detail.mockImplementation(async id => taskResponse(Number(id), 'running'));
    await detail.open(1);
    await detail.selectTab('logs');
    const pendingIncremental = deferred<LogsResponse>();
    api.logs.mockReturnValueOnce(pendingIncremental.promise);

    await vi.advanceTimersByTimeAsync(2000);
    const retry = detail.loadLogs();

    expect(detail.logsLoading.value).toBe(true);
    expect(api.logs).toHaveBeenCalledTimes(2);
    pendingIncremental.resolve(logsResponse(101));
    await retry;
    expect(detail.logsLoading.value).toBe(false);
  });
  it('恢复可见时已读取过当前运行的事件保持静默', async () => {
    const { api, detail } = fixture();
    api.detail.mockImplementation(async id => taskResponse(Number(id), 'running'));
    await detail.open(1);
    detail.setVisible(false);
    const pendingRefresh = deferred<EventsResponse>();
    api.events.mockReturnValueOnce(pendingRefresh.promise);

    detail.setVisible(true);
    await flushPromises();

    expect(api.events).toHaveBeenCalledTimes(2);
    expect(detail.eventsLoading.value).toBe(false);
    pendingRefresh.resolve(eventsResponse(2));
    await flushPromises();
  });
  it('恢复可见时尚无详情主体仍显示首次读取反馈', async () => {
    const { api, detail } = fixture();
    const firstDetail = deferred<OperationDetail>();
    api.detail.mockReturnValueOnce(firstDetail.promise);
    const opening = detail.open(1);
    detail.setVisible(false);
    const visibleDetail = deferred<OperationDetail>();
    api.detail.mockReturnValueOnce(visibleDetail.promise);

    detail.setVisible(true);

    expect(detail.loading.value).toBe(true);
    visibleDetail.resolve(taskResponse(1, 'running'));
    await flushPromises();
    firstDetail.resolve(taskResponse(1, 'running'));
    await opening;
  });
  it('手动增量读取仍保留日志读取反馈', async () => {
    const { api, detail } = fixture();
    await detail.open(1);
    await detail.selectTab('logs');
    const pendingRetry = deferred<LogsResponse>();
    api.logs.mockReturnValueOnce(pendingRetry.promise);

    const pending = detail.loadLogs();
    expect(detail.logsLoading.value).toBe(true);
    pendingRetry.resolve(logsResponse(101));
    await pending;
    expect(detail.logsLoading.value).toBe(false);
  });
  it('进度读取失败保留上次完整快照，重试恢复后清除错误', async () => {
    const { api, detail } = fixture();
    await detail.open(1);
    const saved = detail.progress.value;
    api.progress.mockRejectedValueOnce(new Error('服务暂不可用'));
    await detail.refresh();
    expect(detail.progress.value).toBe(saved);
    expect(detail.progressError.value).toBe('服务暂不可用');
    await detail.refresh();
    expect(detail.progressError.value).toBe('');
  });
  it('详情接口同步抛错后仍可手动重试，不残留已完成的请求', async () => {
    const { api, detail } = fixture();
    await detail.open(1);
    const saved = detail.task.value;
    api.detail.mockImplementationOnce(() => { throw new Error('详情请求暂不可用'); });
    await detail.refresh();
    expect(detail.task.value).toBe(saved);
    expect(detail.error.value).toBe('详情请求暂不可用');
    expect(detail.loading.value).toBe(false);
    await detail.refresh();
    expect(detail.error.value).toBe('');
    expect(detail.loading.value).toBe(false);
  });
  it('隐藏和关闭时停止轮询，恢复可见后再读取', async () => {
    vi.useFakeTimers();
    const { api, detail } = fixture();
    api.detail.mockImplementation(async id => taskResponse(Number(id), 'running'));
    await detail.open(1);
    detail.setVisible(false);
    await vi.advanceTimersByTimeAsync(6000);
    expect(api.detail).toHaveBeenCalledTimes(1);
    detail.setVisible(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(api.detail).toHaveBeenCalledTimes(2);
    detail.close();
    await vi.advanceTimersByTimeAsync(6000);
    expect(api.detail).toHaveBeenCalledTimes(2);
  });
  it('日志使用服务端字节游标，与事件 ID 分开保存', async () => {
    const { api, detail } = fixture();
    await detail.open(1);
    await detail.selectTab('logs');
    api.logs.mockResolvedValueOnce(logsResponse(2048));
    await detail.loadLogs();
    expect(api.logs).toHaveBeenLastCalledWith(1, 10, { cursor: 100, limit: 500 }, expect.any(AbortSignal));
    await detail.loadLogs('start');
    expect(api.logs).toHaveBeenLastCalledWith(1, 10, { cursor: 0, limit: 500 }, expect.any(AbortSignal));
  });
});
