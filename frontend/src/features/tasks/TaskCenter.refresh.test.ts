// @vitest-environment jsdom
import {flushPromises, mount} from '@vue/test-utils';
import {nextTick} from 'vue';
import {expect, it, vi} from 'vitest';
import TaskCenter from './TaskCenter.vue';
import {tasksApi} from '../../api/tasks';

vi.mock('../../api/tasks', async importOriginal => ({...await importOriginal<typeof import('../../api/tasks')>(), tasksApi: {list: vi.fn()}}));

it('显式刷新接口重新获取筛选统计而不重新请求批次导航', async () => {
  vi.mocked(tasksApi.list).mockResolvedValue({ok: true, items: [], total: 0, page: 1, page_size: 20, revision: 'empty'});
  const wrapper = mount(TaskCenter, {global: {stubs: {TaskDetail: true}}});
  try {
    wrapper.vm.setVisible(true); await flushPromises();
    await wrapper.vm.refresh(); await flushPromises();
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({include_facets: 0}), expect.any(AbortSignal));
    await wrapper.vm.refresh({metadata: true}); await flushPromises();
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({include_facets: 1, include_batches: 0}), expect.any(AbortSignal));
  } finally { wrapper.unmount(); }
});

it.each([false, true])('后台轮询保留列表与空状态，主动刷新仍显示反馈（有记录：%s）', async populated => {
  vi.useFakeTimers();
  Object.defineProperty(document, 'hidden', {configurable: true, value: false});
  const response = {ok: true as const, items: populated ? [{id: 7, task_type: 'plan_check', status: 'success'}] : [],
    total: populated ? 40 : 0, page: 1, page_size: 20, revision: 'stable'};
  let finish!: (value: typeof response) => void;
  vi.mocked(tasksApi.list).mockReset().mockResolvedValueOnce(response)
    .mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const wrapper = mount(TaskCenter, {global: {stubs: {TaskDetail: true}}});
  try {
    wrapper.vm.setVisible(true);
    await vi.advanceTimersByTimeAsync(0);
    const before = wrapper.get('.tc-table tbody tr').element;
    if (populated) await wrapper.get('[aria-label="选择任务 #7"]').setValue(true);
    await vi.advanceTimersByTimeAsync(5000);
    expect(tasksApi.list).toHaveBeenCalledTimes(2);
    expect(wrapper.get('#btnRefreshTasksV2').text()).toBe('刷新');
    expect(wrapper.get('#btnRefreshTasksV2').attributes('disabled')).toBeUndefined();
    expect(wrapper.get('.tc-table tbody tr').element).toBe(before);
    expect(wrapper.find('.ui-spinner').exists()).toBe(false);
    if (populated) {
      expect(wrapper.get('[aria-label="选择任务 #7"]').element).toHaveProperty('checked', true);
      expect(wrapper.get('.list-pagination__next').attributes('disabled')).toBeUndefined();
    } else expect(wrapper.get('.ui-table-state').text()).toContain('没有匹配的任务');

    finish(response);
    await vi.advanceTimersByTimeAsync(0);
    const manual = wrapper.vm.refresh();
    await nextTick();
    expect(wrapper.get('#btnRefreshTasksV2').text()).toBe('刷新中…');
    expect(wrapper.get('#btnRefreshTasksV2').attributes('disabled')).toBeDefined();
    finish(response);
    await manual;
  } finally {
    wrapper.unmount();
    vi.useRealTimers();
  }
});
