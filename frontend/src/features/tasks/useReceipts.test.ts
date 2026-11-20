// @vitest-environment jsdom
import {effectScope} from 'vue';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {tasksApi} from '../../api/tasks';
import {useReceipts} from './useReceipts';
vi.mock('../../api/tasks', async importOriginal => ({...await importOriginal<typeof import('../../api/tasks')>(), tasksApi: {receipts: vi.fn()}}));
let scope: ReturnType<typeof effectScope>;
beforeEach(() => { vi.useFakeTimers(); vi.mocked(tasksApi.receipts).mockReset(); scope = effectScope(); Object.defineProperty(document, 'hidden', {configurable: true, value: false}); });
afterEach(() => { scope.stop(); vi.useRealTimers(); });
const response = (items: Awaited<ReturnType<typeof tasksApi.receipts>>['items']) => ({ok: true, items});
const project = (reference: Parameters<typeof tasksApi.receipts>[0][number], status: string) =>
  ({task_id: String(reference.task_id), run_id: reference.run_id === null ? null : String(reference.run_id), status, message: ''});
describe('提交回执', () => {
  it('每轮最多20项，下一轮轮转，关闭后不再轮询', async () => {
    vi.mocked(tasksApi.receipts).mockImplementation(async references => response(references.map(item => project(item, 'running'))));
    const receipts = scope.run(useReceipts)!;
    receipts.track(Array.from({length: 25}, (_, i) => ({accepted: true, task_id: i + 1})), '刷新');
    receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
    expect(tasksApi.receipts).toHaveBeenCalledTimes(1);
    expect(vi.mocked(tasksApi.receipts).mock.calls[0]?.[0]).toHaveLength(20);
    await vi.advanceTimersByTimeAsync(2000);
    expect(vi.mocked(tasksApi.receipts).mock.calls[1]?.[0][0]?.task_id).toBe(21);
    receipts.setVisible(false); await vi.advanceTimersByTimeAsync(10000);
    expect(tasksApi.receipts).toHaveBeenCalledTimes(2);
  });
  it('指定Run的旧回执不被新的成功Run误报成功', async () => {
    vi.mocked(tasksApi.receipts).mockResolvedValue(response([{task_id: '1', run_id: null, status: 'success', message: ''}]));
    const receipts = scope.run(useReceipts)!;
    receipts.track([{accepted: true, task_id: 1, run_id: 10}, {accepted: true, task_id: 1}], '刷新'); receipts.setVisible(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(receipts.items.value.map(item => item.status)).toEqual(['queued', 'success']);
    expect(receipts.error.value).toContain('部分执行记录暂未读到');
  });
});

it('100项按20项有界读取，全部完成后停止且保留最终回执', async () => {
  vi.mocked(tasksApi.receipts).mockImplementation(async references => response(references.map(item => project(item, 'success'))));
  const receipts = scope.run(useReceipts)!;
  receipts.track(Array.from({length: 100}, (_, i) => ({accepted: true, task_id: i + 1, run_id: i + 1001})), '上传');
  receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
  expect(tasksApi.receipts).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(8000);
  expect(receipts.items.value).toHaveLength(100); expect(receipts.pending.value).toHaveLength(0);
  expect(receipts.items.value.every(item => item.status === 'success')).toBe(true);
  await vi.advanceTimersByTimeAsync(10000);
  expect(tasksApi.receipts).toHaveBeenCalledTimes(5);
  expect(vi.mocked(tasksApi.receipts).mock.calls.map(([references]) => references.length)).toEqual([20, 20, 20, 20, 20]);
});

it('读取失败保留排队事实，指定Run终态分别展示失败和成功', async () => {
  vi.mocked(tasksApi.receipts).mockRejectedValueOnce(new Error('网络中断')).mockResolvedValueOnce(response([
    {task_id: '1', run_id: '10', status: 'failed', message: 'Sub2API 鉴权失败'},
  ]));
  const receipts = scope.run(useReceipts)!;
  receipts.track([{accepted: true, task_id: 1, run_id: 10}], '上传'); receipts.setVisible(true);
  await vi.advanceTimersByTimeAsync(0);
  expect(receipts.items.value[0]?.status).toBe('queued'); expect(receipts.error.value).toContain('暂未读到');
  await vi.advanceTimersByTimeAsync(2000);
  expect(receipts.items.value[0]?.status).toBe('failed'); expect(receipts.items.value[0]?.message).toBe('Sub2API 鉴权失败');
});

it('受理中状态继续读取回执，不提前归入失败', async () => {
  vi.mocked(tasksApi.receipts).mockResolvedValue(response([{task_id: '1', run_id: null, status: 'running', message: ''}]));
  const receipts = scope.run(useReceipts)!;
  receipts.track([{accepted: true, task_id: 1, status: 'accepted'}], '刷新');
  expect(receipts.pending.value).toHaveLength(1);
  receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
  expect(tasksApi.receipts).toHaveBeenCalledTimes(1);
  expect(receipts.items.value[0]?.status).toBe('running');
});

it('恢复重交相同task/run不重复或回退终态，同task不同run独立保留', async () => {
  vi.mocked(tasksApi.receipts).mockResolvedValueOnce(response([{task_id: '17', run_id: '8', status: 'failed', message: '上传失败'}]))
    .mockResolvedValueOnce(response([{task_id: '17', run_id: '9', status: 'success', message: ''}]));
  const receipts = scope.run(useReceipts)!;
  receipts.track([{accepted: true, task_id: 17, run_id: 8}], '原上传');
  receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
  expect(receipts.items.value[0]).toMatchObject({status: 'failed', label: '原上传', message: '上传失败'});
  receipts.setVisible(false);
  receipts.track([{accepted: true, task_id: 17, run_id: 8, status: 'queued'},
    {accepted: true, task_id: 17, run_id: 9}], '重交上传');
  receipts.track([{accepted: true, task_id: 17, run_id: 9}], '重复Run');
  expect(receipts.items.value).toHaveLength(2);
  expect(receipts.items.value[0]).toMatchObject({run_id: 8, status: 'failed', label: '原上传', message: '上传失败'});
  expect(receipts.items.value[1]).toMatchObject({run_id: 9, status: 'queued', label: '重交上传'});
  expect(tasksApi.receipts).toHaveBeenCalledTimes(1);
  receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
  expect(receipts.items.value.map(item => [item.run_id, item.status])).toEqual([[8, 'failed'], [9, 'success']]);
  expect(tasksApi.receipts).toHaveBeenCalledTimes(2);
});

it('页面隐藏会中止在途读取，迟到回执不能替换原状态或重新开始轮询', async () => {
  let finish!: (value: Awaited<ReturnType<typeof tasksApi.receipts>>) => void;
  let signal: AbortSignal | undefined;
  vi.mocked(tasksApi.receipts).mockImplementation((_references, currentSignal) => {
    signal = currentSignal;
    return new Promise(resolve => { finish = resolve; });
  });
  const receipts = scope.run(useReceipts)!;
  receipts.track([{accepted: true, task_id: 17, run_id: 29}], '上传');
  receipts.setVisible(true);
  Object.defineProperty(document, 'hidden', {configurable: true, value: true});
  document.dispatchEvent(new Event('visibilitychange'));
  expect(signal?.aborted).toBe(true);
  finish(response([{task_id: '17', run_id: '29', status: 'success', message: ''}]));
  await vi.advanceTimersByTimeAsync(10000);
  expect(receipts.items.value[0]?.status).toBe('queued');
  expect(receipts.pending.value).toHaveLength(1);
  expect(receipts.loading.value).toBe(false);
  expect(tasksApi.receipts).toHaveBeenCalledTimes(1);
});
