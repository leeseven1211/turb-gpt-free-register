import {describe, expect, it, vi} from 'vitest';
import {accountTaskReference, openAccountOperationTasks} from './taskNavigation';

describe('账号操作提交后的任务导航', () => {
  it.each([1, 100])('批量入口选择 %s 个账号时都只显示类型列表', async count => {
    const openTasks = vi.fn(), openTask = vi.fn();
    await openAccountOperationTasks({openTasks, openTask}, {
      single: false, type: 'token_refresh', target: 'first@example.test',
      result: {started_count: count, started: [{task_id: 71, run_id: 72}]},
    });
    expect(openTasks).toHaveBeenCalledExactlyOnceWith({filters: {type: 'token_refresh', target: ''}});
    expect(openTask).not.toHaveBeenCalled();
  });

  it('单账号优先打开本次任务详情，并保留大整数标识', async () => {
    const openTasks = vi.fn(), openTask = vi.fn();
    await openAccountOperationTasks({openTasks, openTask}, {
      single: true, type: 'token_refresh', target: 'one@example.test',
      result: {started: [{task_id: '9007199254740993', run_id: '9007199254740995'}]},
    });
    expect(openTask).toHaveBeenCalledExactlyOnceWith('9007199254740993', '9007199254740995');
    expect(openTasks).not.toHaveBeenCalled();
  });

  it('单账号没有任务标识时按账号和操作类型打开列表', async () => {
    const openTasks = vi.fn(), openTask = vi.fn();
    await openAccountOperationTasks({openTasks, openTask}, {
      single: true, type: 'plan_check', target: 'one@example.test', result: {accepted: true},
    });
    expect(openTasks).toHaveBeenCalledExactlyOnceWith({filters: {type: 'plan_check', target: 'one@example.test'}});
    expect(openTask).not.toHaveBeenCalled();
  });

  it('缺少原页详情入口时仍通过任务中心打开精确任务', async () => {
    const openTasks = vi.fn();
    await openAccountOperationTasks({openTasks}, {
      single: true, type: 'email_change', target: 'one@example.test', result: {task_id: '71', run_id: '72'},
    });
    expect(openTasks).toHaveBeenCalledExactlyOnceWith({
      filters: {type: 'email_change', target: 'one@example.test'}, taskId: 71, runId: 72,
    });
  });

  it.each(['started', 'queued', 'reused'])('读取 %s 中的任务，但不使用账号 id 或跳过项', field => {
    expect(accountTaskReference({[field]: [{id: 7}, {task_id: '71', run_id: '72'}]})).toEqual({taskId: 71, runId: 72});
    expect(accountTaskReference({skipped: [{task_id: 81}], failed: [{task_id: 91}], id: 7})).toBeNull();
  });

  it('同时返回旧任务和统一任务标识时使用统一任务', () => {
    expect(accountTaskReference({task_id: 17, run_id: 18, operation_task_id: '71', operation_run_id: '72'}))
      .toEqual({taskId: 71, runId: 72});
    expect(accountTaskReference({task_id: 71})).toEqual({taskId: 71, runId: null});
  });
});
