// @vitest-environment jsdom
import {effectScope} from 'vue';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {tasksApi} from '../../api/tasks';
import {useReceipts} from './useReceipts';
vi.mock('../../api/tasks', async importOriginal => ({...await importOriginal<typeof import('../../api/tasks')>(), tasksApi: {detail: vi.fn()}}));
let scope: ReturnType<typeof effectScope>;
beforeEach(() => { vi.useFakeTimers(); vi.mocked(tasksApi.detail).mockReset(); scope = effectScope(); Object.defineProperty(document, 'hidden', {configurable: true, value: false}); });
afterEach(() => { scope.stop(); vi.useRealTimers(); });
describe('提交回执', () => {
  it('每轮最多20项，下一轮轮转，关闭后不再轮询', async () => {
    vi.mocked(tasksApi.detail).mockImplementation(async id => ({ok: true, task: {id, task_type: 'token_refresh', status: 'running'}}));
    const receipts = scope.run(useReceipts)!;
    receipts.track(Array.from({length: 25}, (_, i) => ({accepted: true, task_id: i + 1})), '刷新');
    receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
    expect(tasksApi.detail).toHaveBeenCalledTimes(20);
    await vi.advanceTimersByTimeAsync(2000);
    expect(vi.mocked(tasksApi.detail).mock.calls[20]?.[0]).toBe(21);
    receipts.setVisible(false); await vi.advanceTimersByTimeAsync(10000);
    expect(tasksApi.detail).toHaveBeenCalledTimes(40);
  });
  it('指定Run的旧回执不被新的成功Run误报成功', async () => {
    vi.mocked(tasksApi.detail).mockResolvedValue({ok: true, task: {id: 1, task_type: 'token_refresh', status: 'success', runs: [{id: 20, status: 'success'}]}});
    const receipts = scope.run(useReceipts)!;
    receipts.track([{accepted: true, task_id: 1, run_id: 10}], '刷新'); receipts.setVisible(true);
    await vi.advanceTimersByTimeAsync(0);
    expect(receipts.items.value[0]?.status).toBe('queued'); expect(receipts.error.value).toContain('暂未读到');
  });
});

it('100项按20项有界读取，全部完成后停止且保留最终回执', async () => {
  vi.mocked(tasksApi.detail).mockImplementation(async id => ({ok: true, task: {id, task_type: 'sub2api_manual_upload', status: 'success', runs: [{id: Number(id) + 1000, status: 'success'}]}}));
  const receipts = scope.run(useReceipts)!;
  receipts.track(Array.from({length: 100}, (_, i) => ({accepted: true, task_id: i + 1, run_id: i + 1001})), '上传');
  receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
  expect(tasksApi.detail).toHaveBeenCalledTimes(20);
  await vi.advanceTimersByTimeAsync(8000);
  expect(receipts.items.value).toHaveLength(100); expect(receipts.pending.value).toHaveLength(0);
  expect(receipts.items.value.every(item => item.status === 'success')).toBe(true);
  await vi.advanceTimersByTimeAsync(10000); expect(tasksApi.detail).toHaveBeenCalledTimes(100);
});

it('读取失败保留排队事实，指定Run终态分别展示失败和成功', async () => {
  vi.mocked(tasksApi.detail).mockRejectedValueOnce(new Error('网络中断')).mockResolvedValueOnce({ok: true, task: {id: 1, task_type: 'sub2api_manual_upload', status: 'success', runs: [{id: 10, status: 'failed', error_message: 'Sub2API 鉴权失败'}]}});
  const receipts = scope.run(useReceipts)!;
  receipts.track([{accepted: true, task_id: 1, run_id: 10}], '上传'); receipts.setVisible(true);
  await vi.advanceTimersByTimeAsync(0);
  expect(receipts.items.value[0]?.status).toBe('queued'); expect(receipts.error.value).toContain('暂未读到');
  await vi.advanceTimersByTimeAsync(2000);
  expect(receipts.items.value[0]?.status).toBe('failed'); expect(receipts.items.value[0]?.message).toBe('Sub2API 鉴权失败');
});

it('受理中状态继续读取回执，不提前归入失败', async () => {
  vi.mocked(tasksApi.detail).mockResolvedValue({ok: true, task: {id: 1, task_type: 'token_refresh', status: 'running'}});
  const receipts = scope.run(useReceipts)!;
  receipts.track([{accepted: true, task_id: 1, status: 'accepted'}], '刷新');
  expect(receipts.pending.value).toHaveLength(1);
  receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
  expect(tasksApi.detail).toHaveBeenCalledTimes(1);
  expect(receipts.items.value[0]?.status).toBe('running');
});

it('恢复重交相同task/run不重复或回退终态，同task不同run独立保留', async () => {
  vi.mocked(tasksApi.detail).mockResolvedValue({ok: true, task: {id: 17, task_type: 'sub2api_manual_upload', status: 'success', runs: [
    {id: 8, status: 'failed', error_message: '上传失败'}, {id: 9, status: 'success'},
  ]}});
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
  expect(tasksApi.detail).toHaveBeenCalledTimes(1);
  receipts.setVisible(true); await vi.advanceTimersByTimeAsync(0);
  expect(receipts.items.value.map(item => [item.run_id, item.status])).toEqual([[8, 'failed'], [9, 'success']]);
  expect(tasksApi.detail).toHaveBeenCalledTimes(2);
});
