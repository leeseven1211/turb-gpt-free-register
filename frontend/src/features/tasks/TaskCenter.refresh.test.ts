// @vitest-environment jsdom
import {flushPromises, mount} from '@vue/test-utils';
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
