// @vitest-environment jsdom
import {mount} from '@vue/test-utils';
import {afterEach, describe, expect, it} from 'vitest';
import TaskTable from './TaskTable.vue';
import {admissionText} from './presentation';
import type {OperationTask} from '../../api/tasks';
const props = {items: [{id: 1, task_type: 'token_refresh', status: 'queued', source_system: 'native_operations',
  admission_wait_reasons: [{code: 'global_capacity', occupied: 10, limit: 10}]}], selected: new Set<number>(), loading: false, busy: false, error: ''};
afterEach(() => { localStorage.clear(); });
describe('任务表格保留的交互', () => {
  it('只读服务端等待原因，未知原因按文本显示', () => {
    expect(admissionText(props.items[0]!)).toBe('等待全局空位（10/10）');
    const wrapper = mount(TaskTable, {props: {...props, items: [{...props.items[0]!, admission_wait_reasons: [{code: '<img src=x onerror=alert(1)>'}]}]}});
    expect(wrapper.find('img').exists()).toBe(false); expect(wrapper.text()).toContain('调度等待原因未登记'); wrapper.unmount();
  });
  it('单条排队取消保留 terminate 兼容接口，运行中任务不显示删除', async () => {
    const wrapper = mount(TaskTable, {props});
    await wrapper.findAll('button').find(button => button.text() === '取消')!.trigger('click');
    expect(wrapper.emitted('action')?.[0]).toEqual([props.items[0], 'terminate']);
    expect(wrapper.findAll('button').some(button => button.text() === '删除')).toBe(false); wrapper.unmount();
  });
  it('恢复已保存列宽并支持键盘调整与恢复默认', async () => {
    localStorage.setItem('turb_task_center_columns', JSON.stringify([40, 100, 118, 198, 108, 112, 145, 88, 128, 168, 250, 145]));
    const wrapper = mount(TaskTable, {props});
    expect(wrapper.findAll('col')[1]!.attributes('style')).toContain('100px');
    await wrapper.get('button[aria-label="调整ID列宽，方向键调整"]').trigger('keydown', {key: 'ArrowRight'});
    expect(wrapper.findAll('col')[1]!.attributes('style')).toContain('110px');
    expect(JSON.parse(localStorage.getItem('turb_task_center_columns')!)[1]).toBe(110);
    wrapper.vm.resetColumns(); await wrapper.vm.$nextTick();
    expect(wrapper.findAll('col')[1]!.attributes('style')).toContain('72px'); expect(localStorage.getItem('turb_task_center_columns')).toBeNull(); wrapper.unmount();
  });
});

describe('任务列表只收敛状态展示', () => {
  const task = (patch: Partial<OperationTask> = {}): OperationTask => ({id: 7, task_type: 'token_refresh', status: 'failed', target_status: 'failed', ...patch});
  const table = (item: OperationTask) => mount(TaskTable, {props: {...props, items: [item]}});

  it('同为失败只保留执行标签，并保留原始状态与详情入口', async () => {
    const item = task({internal_status: 'request_unknown', internal_target_status: 'request_unknown'});
    const before = structuredClone(item), wrapper = table(item);
    expect(wrapper.get('td[data-label="执行状态"] .tc-badge').text()).toBe('失败');
    expect(wrapper.get('td[data-label="执行状态"] .tc-badge').attributes('title')).toContain('request_unknown');
    expect(wrapper.get('td[data-label="目标状态"]').find('.tc-badge').exists()).toBe(false);
    await wrapper.get('.tc-task-id').trigger('click');
    expect(wrapper.emitted('detail')).toEqual([[7]]);
    expect(item).toEqual(before);
    wrapper.unmount();
  });

  it.each(['request_unknown', 'attention_required', 'manual_reconcile', 'password_confirmation_pending'])(
    '%s 的旧记录不显示两份失败，也不把缺回执说成成功', status => {
      const wrapper = table(task({status, target_status: status}));
      expect(wrapper.get('td[data-label="执行状态"] .tc-badge').text()).toBe('失败');
      expect(wrapper.get('td[data-label="目标状态"]').find('.tc-badge').exists()).toBe(false);
      expect(wrapper.get('td[data-label="结果 / 错误"]').text()).toContain('待确认');
      wrapper.unmount();
    });

  it('多次运行重跑期间不把上次目标失败当作当前执行失败或隐藏', async () => {
    const item = task({status: 'queued', run_count: 3, last_run_no: 3, error_message: '上次运行错误'});
    const wrapper = table(item);
    expect(wrapper.get('td[data-label="执行状态"]').text()).toBe('排队中');
    expect(wrapper.get('td[data-label="目标状态"]').text()).toBe('失败');
    expect(wrapper.get('td[data-label="运行次数"]').text()).toContain('3 次');
    await wrapper.setProps({items: [{...item, status: 'running'}]});
    expect(wrapper.get('td[data-label="执行状态"]').text()).toBe('进行中');
    expect(wrapper.get('td[data-label="目标状态"]').text()).toBe('失败');
    wrapper.unmount();
  });

  it('等待子任务属于进行中，并保留最多一行补充说明', () => {
    const wrapper = table(task({status: 'waiting', target_status: 'pending', next_actions: [{action: 'await_child'}]}));
    const execution = wrapper.get('td[data-label="执行状态"]');
    expect(execution.get('.tc-badge').text()).toBe('进行中');
    expect(execution.findAll('.tc-subline')).toHaveLength(1);
    expect(execution.get('.tc-cell-line').text()).toBe('等待子任务');
    expect(wrapper.get('td[data-label="目标状态"]').find('.tc-badge').exists()).toBe(false);
    expect(wrapper.get('td[data-label="结果 / 错误"]').text()).toContain('等待子任务');
    expect(wrapper.get('td[data-label="结果 / 错误"]').text()).not.toContain('等待执行');
    wrapper.unmount();
  });

  it('等待原因与调试说明只占第二行，不把暂停时的目标失败隐藏', async () => {
    const wrapper = table(task({status: 'waiting', admission_wait_reasons: [{code: 'account_busy'}]}));
    expect(wrapper.get('td[data-label="执行状态"] .tc-subline').text()).toBe('账号正由其他任务使用');
    await wrapper.setProps({items: [task({debug_pause: {reason: 'manual'}})]});
    const execution = wrapper.get('td[data-label="执行状态"]');
    expect(execution.get('.tc-badge').text()).toBe('已暂停');
    expect(execution.findAll('.tc-subline')).toHaveLength(1);
    expect(execution.get('.tc-cell-line').text()).toBe('等待结束调试');
    expect(wrapper.get('td[data-label="目标状态"]').text()).toBe('失败');
    wrapper.unmount();
  });

  it.each([['stopping', '停止中'], ['cancelling', '停止中'], ['settling', '收尾中']])(
    '%s 不提前显示已经结束', (status, secondary) => {
      const wrapper = table(task({status, target_status: 'in_progress', source_system: 'native_operations'}));
      expect(wrapper.get('td[data-label="执行状态"] .tc-badge').text()).toBe('进行中');
      expect(wrapper.get('td[data-label="执行状态"] .tc-subline').text()).toBe(secondary);
      expect(wrapper.get('td[data-label="操作"]').text()).not.toContain('删除');
      wrapper.unmount();
    });

  it.each([
    ['success', 'completed', '已完成', '—'], ['partial_success', 'failed', '部分完成', '失败'],
    ['failed', 'account_available', '失败', '账号可用'], ['failed', 'credential_valid', '失败', '凭证有效'],
    ['success', 'credential_pending_confirmation', '已完成', '凭证待核验'],
    ['cancelled', 'cancelled', '已停止', '—'], ['stopped', 'cancelled', '已停止', '—'],
    ['interrupted', 'account_available', '已停止', '账号可用'],
  ])('%s/%s 只隐藏冗余目标信息', (status, target_status, execution, target) => {
    const wrapper = table(task({status, target_status}));
    expect(wrapper.get('td[data-label="执行状态"]').text()).toBe(execution);
    expect(wrapper.get('td[data-label="目标状态"]').text()).toBe(target);
    wrapper.unmount();
  });
});
