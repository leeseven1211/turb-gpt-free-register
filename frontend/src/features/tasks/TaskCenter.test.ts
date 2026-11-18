// @vitest-environment jsdom
import {DOMWrapper, flushPromises, mount} from '@vue/test-utils';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import TaskCenter from './TaskCenter.vue';
import TaskFilters from './TaskFilters.vue';
import TaskFilterFields from './TaskFilterFields.vue';
import {filterColumns} from './filterDefinitions';
import {emptyFilters, tasksApi} from '../../api/tasks';
vi.mock('../../api/tasks', async importOriginal => ({...await importOriginal<typeof import('../../api/tasks')>(), tasksApi: {list: vi.fn(), detail: vi.fn(), action: vi.fn(), bulk: vi.fn()}}));
const wrappers: ReturnType<typeof mount>[] = [];
beforeEach(() => {
  vi.useFakeTimers(); vi.mocked(tasksApi.list).mockReset(); vi.mocked(tasksApi.action).mockReset(); vi.mocked(tasksApi.detail).mockReset(); vi.mocked(tasksApi.bulk).mockReset();
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} });
  vi.mocked(tasksApi.list).mockResolvedValue({ok: true, items: [
    {id: 1, task_type: 'plan_check', status: 'failed', next_actions: [{action: 'retry'}]},
    {id: 2, task_type: 'plan_check', status: 'running', source_system: 'native_operations'},
  ], total: 2, page: 1, page_size: 20, revision: 'r1'});
  vi.mocked(tasksApi.action).mockResolvedValue({ok: true});
  Object.defineProperty(document, 'hidden', {configurable: true, value: false});
});
afterEach(() => { wrappers.forEach(wrapper => wrapper.unmount()); wrappers.length = 0; vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });
describe('任务中心组件', () => {
  it('停止与取消筛选文案可区分，提交仍是各自原始单值', async () => {
    const wrapper = mount(TaskFilterFields, {props: {column: filterColumns.find(column => column.key === 'status')!, modelValue: emptyFilters(), facets: {status: [
      {value: 'stopping', label: '停止中', count: 2}, {value: 'cancelling', label: '停止中', count: 3},
    ]}}}); wrappers.push(wrapper);
    for (const [value, text] of [['stopping', '请求停止'], ['cancelling', '请求取消']]) {
      const option = wrapper.get<HTMLInputElement>(`input[value="${value}"]`);
      expect(option.element.closest('label')?.textContent).toContain(text);
      await option.setValue(true);
      expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({...emptyFilters(), status: value});
    }
  });
  it('跨页打开合并筛选后只发一次首屏请求', async () => {
    const wrapper = mount(TaskCenter, {global: {stubs: {TaskDetail: true}}}); wrappers.push(wrapper);
    wrapper.vm.setVisible(true);
    await wrapper.vm.open({filters: {type: 'token_refresh', target: 'demo@example.test'}});
    await flushPromises(); await vi.advanceTimersByTimeAsync(300);
    expect(tasksApi.list).toHaveBeenCalledTimes(1);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({type: 'token_refresh', target: 'demo@example.test'}), expect.any(AbortSignal));
  });
  it('单条重跑直接调用原接口，选择后只允许符合资格的批量操作', async () => {
    const confirm = vi.spyOn(window, 'confirm');
    const wrapper = mount(TaskCenter, {global: {stubs: {TaskDetail: true}}}); wrappers.push(wrapper);
    wrapper.vm.setVisible(true); await flushPromises();
    await wrapper.get('input[aria-label="选择任务 #1"]').setValue(true);
    expect(wrapper.text()).toContain('已选 1 项');
    const retry = wrapper.findAll('button').find(button => button.text() === '重跑')!;
    await retry.trigger('click'); await flushPromises();
    expect(tasksApi.action).toHaveBeenCalledWith(1, 'retry'); expect(confirm).not.toHaveBeenCalled();
  });
  it('回执从其他页面传入后请求导航，指定任务可查看', async () => {
    const wrapper = mount(TaskCenter, {global: {stubs: {TaskDetail: true}}}); wrappers.push(wrapper);
    wrapper.vm.track([{accepted: true, task_id: 5, run_id: 9}], '手动上传');
    expect(wrapper.emitted('navigate')).toHaveLength(1);
    await flushPromises();
    expect(wrapper.text()).toContain('手动上传 #5');
  });
  it('外部筛选在表头标记已选，统计缺少组合类型时菜单仍保留该条件', async () => {
    const wrapper = mount(TaskCenter, {attachTo: document.body, global: {stubs: {TaskDetail: true}}}); wrappers.push(wrapper);
    wrapper.vm.setVisible(true);
    await wrapper.vm.open({filters: {type: 'password_setup,twofa_setup', result: '超时'}}); await flushPromises();
    const trigger = wrapper.get('thead button[aria-label="筛选类型"]');
    expect(trigger.classes()).toContain('is-active');
    expect(wrapper.get('thead button[aria-label="筛选结果 / 错误"]').classes()).toContain('is-active');
    await trigger.trigger('click'); await flushPromises();
    expect(trigger.attributes('aria-expanded')).toBe('true');
    const chosen = new DOMWrapper(document.body).get<HTMLInputElement>('.tc-filter-popover input[value="password_setup,twofa_setup"]');
    expect(chosen.element.checked).toBe(true);
    expect(chosen.element.closest('label')?.textContent).toContain('补密码、补 2FA');
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({type: 'password_setup,twofa_setup', result: '超时'}), expect.any(AbortSignal));
  });
  it('表头执行状态按原 status 字段筛选，并从后续页回到第一页', async () => {
    vi.mocked(tasksApi.list).mockImplementation(async query => ({ok: true, items: [], total: 45, page: query.page, page_size: 20, revision: 'r1'}));
    const wrapper = mount(TaskCenter, {attachTo: document.body, global: {stubs: {TaskDetail: true}}}); wrappers.push(wrapper);
    wrapper.vm.setVisible(true); await flushPromises();
    await wrapper.findAll('button').find(button => button.text() === '下一页')!.trigger('click'); await flushPromises();
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({page: 2}), expect.any(AbortSignal));
    const trigger = wrapper.get('thead button[aria-label="筛选执行状态"]');
    await trigger.trigger('click'); await flushPromises();
    await new DOMWrapper(document.body).get<HTMLInputElement>('.tc-filter-popover input[value="failed"]').setValue(true);
    await flushPromises(); await vi.advanceTimersByTimeAsync(300);
    expect(tasksApi.list).toHaveBeenLastCalledWith(expect.objectContaining({status: 'failed', page: 1, include_facets: 1}), expect.any(AbortSignal));
    // 方向键产生 change 时继续浏览选项，明确点击才收起菜单。
    expect(trigger.attributes('aria-expanded')).toBe('true');
    new DOMWrapper(document.body).get('input[type="radio"][value="failed"]').element.dispatchEvent(new MouseEvent('click', {detail: 1, bubbles: true}));
    await flushPromises();
    expect(trigger.attributes('aria-expanded')).toBe('false');
    expect(trigger.classes()).toContain('is-active');
  });
  it('手机筛选使用受控菜单，清除日期同时移除起止值并保留目标', async () => {
    const filters = {...emptyFilters(), target: 'demo@example.test', created_from: '2026-11-01', created_to: '2026-11-13'};
    const wrapper = mount(TaskFilters, {attachTo: document.body, props: {modelValue: filters, facets: {}, open: true}}); wrappers.push(wrapper);
    await flushPromises();
    const page = new DOMWrapper(document.body);
    await page.get('.tc-filter-column-picker select').setValue('created');
    expect(page.findAll<HTMLInputElement>('.tc-filter-popover input[type="date"]').map(input => input.element.value)).toEqual(['2026-11-01', '2026-11-13']);
    await page.findAll('.tc-filter-popover button').find(button => button.text() === '清除此列')!.trigger('click');
    expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({...filters, created_from: '', created_to: ''});
    expect(wrapper.emitted('update:open')?.at(-1)).toEqual([false]);
  });
});

it('回执保留手动开合、滚动和同一Run按钮焦点，navigate false不跳页或请求', async () => {
  vi.mocked(tasksApi.detail).mockResolvedValue({ok: true, task: {id: 17, task_type: 'sub2api_manual_upload', status: 'running', runs: [{id: 29, status: 'running'}, {id: 30, status: 'running'}]}});
  const wrapper = mount(TaskCenter, {attachTo: document.body, global: {stubs: {TaskDetail: true}}}); wrappers.push(wrapper);
  wrapper.vm.track([{accepted: true, task_id: 17, run_id: 29}, {accepted: true, task_id: 17, run_id: 30}], '上传', {navigate: false});
  await flushPromises();
  expect(wrapper.emitted('navigate')).toBeUndefined(); expect(tasksApi.detail).not.toHaveBeenCalled();
  const details = wrapper.get('.tc-receipts details').element as HTMLDetailsElement;
  expect(details.open).toBe(false);
  wrapper.vm.setVisible(true); await flushPromises();
  details.open = true;
  const list = wrapper.get('.tc-receipt-list').element; list.scrollTop = 240;
  const button = wrapper.findAll('.tc-receipt-list button')[1]!.element as HTMLButtonElement; button.focus();
  await vi.advanceTimersByTimeAsync(2001); await flushPromises();
  expect(wrapper.get('.tc-receipts details').element).toBe(details); expect(details.open).toBe(true);
  expect(list.scrollTop).toBe(240); expect(document.activeElement).toBe(button);
  details.open = false; await vi.advanceTimersByTimeAsync(2001); expect(details.open).toBe(false);
});

it('批量删除只提交非活动选择，保留跳过原因；单条删除使用既有确认', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.mocked(tasksApi.bulk).mockResolvedValue({ok: true, accepted_count: 0, skipped: [{task_id: 1, error: '任务状态已变化'}], skipped_count: 1});
  const wrapper = mount(TaskCenter, {global: {stubs: {TaskDetail: true}}}); wrappers.push(wrapper);
  wrapper.vm.setVisible(true); await flushPromises();
  await wrapper.get('input[aria-label="全选当前页任务"]').setValue(true);
  await wrapper.findAll('.tc-bulk-actions button').find(button => button.text().startsWith('删除'))!.trigger('click'); await flushPromises();
  expect(tasksApi.bulk).toHaveBeenCalledWith('delete', [1]); expect(wrapper.text()).toContain('任务状态已变化');
  await wrapper.findAll('.tc-row-actions button').find(button => button.text() === '删除')!.trigger('click'); await flushPromises();
  expect(tasksApi.action).toHaveBeenCalledWith(1, 'delete'); expect(confirm).toHaveBeenCalledTimes(2);
});

it('批量取消按实际回执区分已取消与取消中，并保留跳过和运行中选择', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  const items = [11, 12, 13, 14].map(id => ({id, task_type: 'token_refresh', status: id === 14 ? 'running' : 'queued', source_system: 'native_operations'}));
  vi.mocked(tasksApi.list).mockResolvedValue({ok: true, items, total: 4, page: 1, page_size: 20, revision: 'cancel-before'});
  vi.mocked(tasksApi.bulk).mockResolvedValue({ok: true, accepted_count: 2, skipped_count: 1,
    accepted: [{task_id: 11, state: 'cancelled'}, {task_id: 12, state: 'cancelling'}],
    skipped: [{task_id: 13, error: '任务状态已变化，请刷新后重试'}]});
  const wrapper = mount(TaskCenter, {global: {stubs: {TaskDetail: true}}}); wrappers.push(wrapper);
  wrapper.vm.setVisible(true); await flushPromises();
  await wrapper.get('input[aria-label="全选当前页任务"]').setValue(true);
  await wrapper.findAll('.tc-bulk-actions button').find(button => button.text().startsWith('取消排队'))!.trigger('click');
  await flushPromises();
  expect(tasksApi.bulk).toHaveBeenCalledWith('cancel', [11, 12, 13]);
  expect(wrapper.get('.tc-feedback').text()).toContain('已取消 1 个，取消中 1 个，跳过 1 个');
  expect(wrapper.get('.tc-feedback').text()).toContain('#13：任务状态已变化，请刷新后重试');
  const checked = wrapper.findAll<HTMLInputElement>('tbody input[type="checkbox"]').filter(input => input.element.checked);
  expect(checked.map(input => input.attributes('aria-label'))).toEqual(['选择任务 #13', '选择任务 #14']);
});
