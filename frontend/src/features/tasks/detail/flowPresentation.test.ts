import { mount } from '@vue/test-utils';
import { beforeAll, describe, expect, it } from 'vitest';
import { phaseMarkers, phaseRelations, phaseState, phaseSteps } from './flowPresentation';
import type { Step } from './model';
import TaskProgress from './TaskProgress.vue';
import TaskFailure from './TaskFailure.vue';
import StepEvidence from './StepEvidence.vue';
import StepRelations from './StepRelations.vue';

beforeAll(() => { HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); }; });

const execution = (extra: Partial<NonNullable<Step['execution']>> = {}): NonNullable<Step['execution']> => ({
  kind: 'stage', condition: null, dependency_state: 'unknown', waits_for: [], parallel_group: null,
  retry: { state: 'unknown', attempt_count: null, event_ids: [] }, source: 'runtime_contract', ...extra,
});
const step = (extra: Partial<Step> = {}): Step => ({ id: 'auth', label: '登录验证', state: 'success', ...extra });

describe('阶段与依赖展示', () => {
  it('有首次记录仍不能推断依赖或并行，不重排阶段', () => {
    const steps = [step({ id: 'query', observed_order: 2, execution: execution() }), step({ observed_order: 1 })];
    expect(phaseSteps(steps)).toEqual(steps);
    expect(phaseRelations(steps[0]!)).toContainEqual({ label: '首次记录', value: '第 2 个被记录的阶段' });
    expect(phaseRelations(steps[0]!)).toContainEqual({ label: '关系记录', value: '没有足够证据确定依赖或并行关系' });
    expect(phaseMarkers(steps[0]!)).not.toContain('并行分支');
  });
  it('区分未触发条件与缺少记录，并保留条件跳过阶段', () => {
    const disabled = step({ state: 'skipped', execution: execution({ kind: 'conditional', condition: { label: '启用套餐查询', state: 'not_met', evidence: 'run_config' } }) });
    const unknown = step({ id: 'unknown', state: 'pending', execution: execution({ kind: 'conditional', condition: { label: '启用同步', state: 'unknown', evidence: '' } }) });
    expect(phaseSteps([disabled, unknown, step({ state: 'skipped', id: 'unused' })])).toEqual([disabled, unknown]);
    expect(phaseState(disabled)).toBe('条件未满足');
    expect(phaseRelations(unknown)).toContainEqual({ label: '触发条件', value: '启用同步 · 未确认' });
    const childCondition = { ...disabled, execution: execution({ ...disabled.execution, kind: 'child_task' }) };
    expect(phaseSteps([childCondition])).toEqual([childCondition]);
  });
  it('区分等待子任务、前置失败与依赖满足', () => {
    const child = step({ execution: execution({ kind: 'child_task', dependency_state: 'waiting', waits_for: [{ task_id: 2, status: 'running', evidence: 'child_summary' }] }) });
    expect(phaseState(child)).toBe('等待子任务');
    const failedChild = step({ state: 'success', execution: execution({ kind: 'child_task', dependency_state: 'blocked', waits_for: [{ task_id: 2, status: 'failed', evidence: 'child_summary' }] }) });
    expect(phaseState(failedChild)).toBe('子任务未完成');
    expect(phaseRelations(failedChild)).toContainEqual({ label: '依赖状态', value: '子任务未成功完成' });
    expect(phaseState(step({ state: 'not_executed', execution: execution({ dependency_state: 'blocked' }) }))).toBe('前置阶段失败');
    const ready = step({ depends_on: ['preflight'], execution: execution({ dependency_state: 'satisfied' }) });
    expect(phaseState(ready)).toBe('已完成');
    expect(phaseRelations(ready, [step({ id: 'preflight', label: '配置预检' })])).toContainEqual({ label: '依赖阶段', value: '配置预检' });
  });
  it('多个正常阶段实例不描述为重试，无 ID 子任务不拼接空标识', () => {
    const data = step({ execution: execution(), step_instances: [{ state: 'success', message: 'JP 查询' }, { state: 'success', message: 'IN 查询' }] });
    const wrapper = mount(StepEvidence, { props: { step: data } });
    expect(wrapper.text()).toContain('阶段实例（2）');
    expect(wrapper.text()).not.toContain('尝试');
    wrapper.unmount();
    const relation = mount(StepRelations, { props: { step: step({ execution: execution({ waits_for: [{ evidence: 'awaiting_steps' }] }) }) } });
    expect(relation.text()).toContain('子任务关联标识未记录');
    expect(relation.text()).not.toContain('#');
    relation.unmount();
  });
  it('只显示显式并行与实际重试次数，不以事件数量替代次数', () => {
    const retry = { state: 'observed' as const, attempt_count: null, event_ids: ['1', '2', '3'] };
    const retried = step({ execution: execution({ parallel_group: 'account-enrichment', retry }) });
    expect(phaseMarkers(retried)).toEqual(['并行分支', '有重试记录']);
    expect(phaseRelations(retried)).toContainEqual({ label: '重试', value: '有重试记录' });
    const recovered = step({ execution: execution({ retry: { ...retry, state: 'recovered', attempt_count: 2 } }) });
    expect(phaseState(recovered)).toBe('重试已恢复');
    expect(phaseRelations(recovered)).toContainEqual({ label: '重试', value: '重试已恢复 · 2 次尝试' });
  });
  it('紧凑阶段保留筛选行为，依赖说明默认折叠且不显示固定步骤编号', async () => {
    const data = step({ execution: execution({ kind: 'conditional', condition: { label: '启用登录', state: 'met', evidence: 'stage_event' } }) });
    const wrapper = mount(TaskProgress, { props: { progress: { task_id: 1, run_id: 10, revision: '1', main_steps: [data], outcome: { status: 'success' } }, filter: null, active: true, context: '1:10' } });
    expect(wrapper.find('.tc-flow-relations').attributes('open')).toBeUndefined();
    expect(wrapper.find('.tc-step-index').exists()).toBe(false);
    expect(wrapper.find('.tc-progress-track').attributes('aria-label')).toContain('排列不代表固定顺序');
    await wrapper.find('.tc-step-select').trigger('click');
    expect(wrapper.emitted('filter')).toEqual([['auth']]);
    await wrapper.setProps({ filter: 'auth' });
    await wrapper.find('.tc-step-select').trigger('click');
    expect(wrapper.emitted('filter')?.[1]).toEqual([null]);
    wrapper.unmount();
  });
  it('Codex 补跑主栏展示有记录的四种状态，模板占位留在折叠详情', () => {
    const wrapper = mount(TaskProgress, { props: {
      taskType: 'codex_retry', filter: null, active: true, context: '1:10',
      progress: { task_id: 1, run_id: 10, revision: '1', outcome: { status: 'running' }, main_steps: [
        step({ id: 'callback', observed_order: 1 }),
        step({ id: 'phone_verify', state: 'skipped', observed_order: 2 }),
        step({ id: 'sync', state: 'failed', observed_order: 3 }),
        step({ id: 'credential', state: 'running', observed_order: 4 }),
        step({ id: 'consent', label: '确认授权', state: 'pending', display_status: 'record_incomplete', evidence: 'unobserved', event_ids: ['99'] }),
      ] },
    } });
    const statuses = wrapper.findAll('.tc-step-status');
    expect(statuses.map(item => item.text())).toEqual(['已完成', '已跳过', '失败', '执行中']);
    expect(statuses.map(item => item.classes().find(name => name.startsWith('tc-badge--')) || '')).toEqual(
      ['tc-badge--success', '', 'tc-badge--danger', 'tc-badge--active'],
    );
    expect(wrapper.get('.tc-progress-track').text()).not.toContain('确认授权');
    expect(wrapper.get('.tc-flow-relations').text()).toContain('确认授权');
    wrapper.unmount();
  });
  it('共用泛化分类但原文不同的失败保留两个原因与原始证据', () => {
    const wrapper = mount(TaskFailure, { props: {
      failure: { label: '登录验证', message: '验证码过期', error_info: { summary: '登录失败', cause_summary: '验证码无效' } },
      execution: { error_message: '网络握手中断', error_info: { summary: '登录失败' } },
    } });
    expect(wrapper.find('summary').text()).toContain('验证码无效');
    expect(wrapper.find('.tc-failure-secondary').exists()).toBe(true);
    expect(wrapper.find('pre').text()).toContain('验证码过期');
    expect(wrapper.find('pre').text()).toContain('网络握手中断');
    wrapper.unmount();
  });
  it('相同具体分类也不能合并不同的原始失败，技术证据保留位置和子任务引用', () => {
    const wrapper = mount(TaskFailure, { props: {
      failure: { step_id: 'authenticate', label: '登录验证', stage: 'email_otp', event_id: 7,
        child_task_id: 20, message: '第一个邮箱等待超时', error_info: { cause_summary: '验证码等待超时' } },
      execution: { error_message: '第二个邮箱等待超时', error_info: { cause_summary: '验证码等待超时' } },
    } });
    expect(wrapper.find('.tc-failure-secondary').exists()).toBe(true);
    expect(wrapper.find('pre').text()).toContain('"stage": "email_otp"');
    expect(wrapper.find('pre').text()).toContain('"child_task_id": 20');
    expect(wrapper.find('pre').text()).toContain('第一个邮箱等待超时');
    expect(wrapper.find('pre').text()).toContain('第二个邮箱等待超时');
    wrapper.unmount();
  });
});
