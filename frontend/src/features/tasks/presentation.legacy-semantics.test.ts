// @vitest-environment jsdom
import {mount} from '@vue/test-utils';
import {describe, expect, it} from 'vitest';
import type {OperationTask} from '../../api/tasks';
import TaskTable from './TaskTable.vue';
import {errorText, failureStageText, resultDetails, resultText} from './presentation';

const task = (patch: Partial<OperationTask> = {}): OperationTask => ({id: 1, task_type: 'plan_check', status: 'success', ...patch});
const goTrial = {plan: 'go', kind: 'free_trial', eligible: true, duration_num_periods: 1, duration_period: 'month'};
const plusDiscount = {plan: 'plus', kind: 'discount', eligible: true, discount_percentage: 50, duration_num_periods: 2, duration_period: 'month'};
const checked = {current_plan_type: 'free', account_promotions: [goTrial, plusDiscount]};
const planTask = (summary: Record<string, unknown>) => task({result_summary: summary});

describe('提链结果和错误诊断的既有语义', () => {
  it('以提链状态为事实，成功后分别保留支付失败、响应缺失、处理中和完成', () => {
    const extracted = {extraction_status: 'succeeded', payment_status: 'not_started', mode: 'extract_only', ok: false, message: '提炼失败'};
    const value = task({task_type: 'extract_link', result_summary: extracted});
    expect(resultText(value)).toBe('提链成功');
    expect(resultText(value, true)).toBe('提链成功');
    for (const [payment, status, expected] of [
      ['failed', 'failed', '支付失败'], ['unknown', 'attention_required', '支付响应缺失'],
      ['pending', 'partial_success', '支付处理中'], ['succeeded', 'success', '支付成功'],
    ]) expect(resultText({...value, status, error_message: '支付接口异常', result_summary: {...extracted, mode: 'auto_payment', payment_status: payment}}))
      .toBe(`提链成功 · ${expected}`);
    expect(resultText({...value, result_summary: {...extracted, mode: 'manual_payment', payment_status: 'pending'}})).toBe('提链成功 · 等待手动支付');
  });
  it('缺少摘要保留等待、运行、取消和结果缺失，明确提链失败覆盖旧成功标记', () => {
    for (const [status, expected] of [
      ['queued', '等待执行'], ['running', '执行中'], ['cancelled', '任务已取消'], ['stopped', '任务已中断'], ['interrupted', '任务已中断'],
      ['request_unknown', '提链失败 · 平台响应记录缺失'], ['attention_required', '提链失败 · 平台响应记录缺失'],
      ['partial_success', '提链失败 · 平台响应记录缺失'], ['unknown', '提链失败 · 平台响应记录缺失'],
      ['success', '提链结果未记录'], ['', '提链结果未记录'], ['failed', '提链失败'],
    ]) expect(resultText(task({task_type: 'extract_link', status}))).toBe(expected);
    expect(resultText(task({task_type: 'extract_link', status: 'failed', result_summary: {extraction_status: 'failed', ok: true, has_link: true, message: '提链成功'}}))).toBe('提链失败');
    expect(resultText(task({task_type: 'extract_link', result_summary: {extraction_status: 'unknown', ok: false}}))).toBe('提链失败 · 平台响应记录缺失');
  });
  it('历史摘要继续区分已有链接、完成、失败和平台原始消息', () => {
    const cases: [Record<string, unknown>, string][] = [
      [{ok: true, has_link: true, link_type: 'upi'}, '提链成功 · UPI'], [{ok: true, has_link: false}, '提炼完成'],
      [{ok: false}, '提炼失败'], [{ok: false, message: '平台拒绝请求'}, '平台拒绝请求'],
    ];
    for (const [result_summary, expected] of cases) expect(resultText(task({task_type: 'extract_link', result_summary}))).toBe(expected);
  });
  it('列表短摘要保留提链和支付事实，完整原因与代码移到展开内容并转义', () => {
    const value = task({task_type: 'extract_link', status: 'failed', error_message: '支付<失败>', error_info: {display_code: 'PAYMENT'},
      result_summary: {extraction_status: 'succeeded', payment_status: 'failed'}});
    const wrapper = mount(TaskTable, {props: {items: [value], selected: new Set<number>(), loading: false, busy: false, error: ''}});
    const cell = wrapper.get('td[data-label="结果 / 错误"]');
    const preview = cell.get('summary');
    expect(preview.text()).toBe('提链成功支付失败');
    expect([...preview.text()].length).toBeLessThanOrEqual(10);
    expect(preview.attributes('title')).toContain('支付<失败>');
    expect(cell.get('.list-result-details').text()).toContain('PAYMENT');
    expect(cell.get('.list-result-details').text()).toContain('支付<失败>');
    expect(cell.find('失败').exists()).toBe(false);
    wrapper.unmount();
  });
  it('失败步骤优先分类和 MFA 诊断，仅当证据匹配时纠正归因', () => {
    expect(failureStageText(task({task_type: 'extract_link', status: 'failed', failure_stage: 'access_token', failure_stage_label: '校验 Token', error_info: {stage: 'extraction'}}))).toBe('失败于 平台提链');
    const value = task({task_type: 'token_refresh', status: 'deactivated', failure_stage: 'login_password', failure_stage_label: '账号密码', error_info: {stage: 'login_password'}});
    expect(failureStageText({...value, result_summary: {auth_diagnostics: {operation: 'mfa_verify'}}})).toBe('失败于 TOTP 验证');
    expect(failureStageText({...value, result_summary: {auth_diagnostics: {operation: 'password_verify'}}})).toBe('失败于 账号密码');
    const email = {...value, failure_stage: 'email_otp', failure_stage_label: '邮箱验证', error_info: {stage: 'email_otp'}};
    expect(failureStageText({...email, result_summary: {auth_diagnostics: {operation: 'password_email_fallback', cause_operation: 'mfa_verify'}}})).toBe('失败于 TOTP 验证');
    expect(failureStageText({...email, result_summary: {auth_diagnostics: {operation: 'password_email_fallback', cause_operation: 'email_otp'}}})).toBe('失败于 邮箱验证');
    expect(errorText({summary: '密码验证返回 HTTP 401', cause_summary: '密码验证返回 HTTP 401'})).toBe('密码验证返回 HTTP 401');
  });
});

describe('套餐结果保留单次、多国和历史快照事实', () => {
  it('单次查询显示 Go 与 Plus，空国家列表和空计数不会制造国家统计', () => {
    const value = planTask({...checked, plan_check_countries: [], country_total_count: null, country_success_count: null});
    for (const expected of ['套餐 free', 'Go: 免费 1个月', 'Plus: 五折 2个月']) expect(resultDetails(value)).toContain(expected);
    expect(resultDetails(value)).not.toMatch(/国家查询|0\/0/);
  });
  it('仅有多国汇总时保留部分失败、所属国家和失败国家清单', () => {
    const value = planTask({current_plan_type: 'free', plan_check_countries: ['JP', 'VN', 'IN'], plan_check_partial: true,
      country_success_count: 1, country_total_count: 3, failed_countries: ['VN', 'IN'],
      account_promotions: [{...goTrial, country: 'JP'}, {plan: 'plus', kind: 'discount', discount_percentage: 20, country: 'VN', stale: true}]});
    expect(resultText(value, true)).toContain('部分失败');
    for (const expected of ['部分失败', '失败国家：VN、IN', 'JP', 'VN', 'Go: 免费']) expect(resultDetails(value)).toContain(expected);
    expect(resultDetails(value)).not.toMatch(/国家查询|个国家成功|1\/3/);
  });
  it('多国摘要只显示最佳优惠，展开保留每个国家的 Go 和 Plus', () => {
    const value = planTask({current_plan_type: 'free', plan_check_country_results: [
      {country: 'JP', status: 'success', result: {account_promotions: [goTrial, plusDiscount]}},
      {country: 'VN', status: 'success', result: {account_promotions: [{plan: 'go', kind: 'none'}, {...goTrial, plan: 'plus'}]}},
      {country: 'IN', status: 'success', result: {account_promotions: [{plan: 'go', kind: 'none'}, {plan: 'plus', kind: 'none'}]}},
    ]});
    expect(resultText(value, true)).toBe('free · Plus 免费 1个月');
    const details = resultDetails(value);
    expect(details).toMatch(/JP[\s\S]*Go: 免费 1个月[\s\S]*Plus: 五折 2个月/);
    expect(details).toMatch(/VN[\s\S]*Plus: 免费 1个月/);
    expect(details).toMatch(/IN[\s\S]*Plus: 无优惠/);
    expect(details).not.toMatch(/个国家成功|3\/3/);
  });
  it('免费优先折扣，同等优惠选择 Plus，当前记录优先相同历史记录', () => {
    const compact = (offers: Record<string, unknown>[]) => resultText(planTask({...checked, account_promotions: offers}), true);
    expect(compact([goTrial, plusDiscount])).toBe('free · Go 免费 1个月');
    expect(compact([goTrial, {...goTrial, plan: 'plus'}])).toBe('free · Plus 免费 1个月');
    expect(compact([{plan: 'go', kind: 'discount', discount_percentage: 20}, plusDiscount])).toBe('free · Plus 五折 2个月');
    for (const [kind, expected] of [['none', '无优惠'], ['pending', '待查询'], ['unknown', '待复查']]) {
      expect(compact(['go', 'plus'].map(plan => ({plan, kind})))).toBe(`free · ${expected}`);
    }
    expect(compact([{...goTrial, plan: 'plus', stale: true}, {...goTrial, plan: 'plus', stale: false}])).not.toContain('历史');
  });
  it('所有国家无优惠时合并摘要，展开仍保留各国完整结果', () => {
    const value = planTask({current_plan_type: 'free', plan_check_country_results: ['JP', 'VN'].map(country => ({country, status: 'success', result: {
      account_promotions: [{plan: 'go', kind: 'none'}, {plan: 'plus', kind: 'none'}],
    }}))});
    expect(resultText(value, true)).toBe('free · 无优惠');
    for (const country of ['JP', 'VN']) expect(resultDetails(value)).toMatch(new RegExp(`${country}[\\s\\S]*Go: 无优惠[\\s\\S]*Plus: 无优惠`));
  });
  it('部分失败标记历史优惠，展开保留失败原因和取消状态', () => {
    const value = planTask({current_plan_type: 'free', plan_check_partial: true, plan_check_country_results: [
      {country: 'JP', status: 'success', result: {account_promotions: [{plan: 'go', kind: 'none'}, plusDiscount]}},
      {country: 'VN', status: 'failed', error: 'HTTP 429', last_success_at: '2026-10-14 09:00:00', result: {account_promotions: [{plan: 'go', kind: 'none'}, {...goTrial, plan: 'plus', duration_num_periods: 2}]}},
      {country: 'IN', status: 'cancelled', error: '已取消'},
    ]});
    expect(resultText(value, true)).toBe('free · 部分失败 · Plus 免费 2个月 · 历史');
    for (const expected of ['VN', 'Plus: 免费 2个月', '显示上次成功快照', '本次查询失败: HTTP 429', 'IN', '已取消']) expect(resultDetails(value)).toContain(expected);
  });
  it('明确空国家列表覆盖旧国家快照，保留最新单次查询', () => {
    const value = planTask({...checked, plan_check_countries: [], plan_check_country_results: [{country: 'JP', status: 'success', result: {account_promotions: [{...goTrial, plan: 'plus', duration_num_periods: 12}]}}]});
    expect(resultText(value, true)).toBe('free · Go 免费 1个月');
    expect(resultDetails(value)).toContain('Plus: 五折 2个月');
    expect(resultDetails(value)).not.toMatch(/JP|12个月|国家查询/);
  });
  it('列表使用原生可聚焦展开入口显示完整套餐证据并转义 HTML', async () => {
    const value = planTask({current_plan_type: 'free', plan_check_country_results: [
      {country: 'JP', status: 'success', result: {account_promotions: [goTrial, plusDiscount]}},
      {country: 'VN', status: 'failed', error: '错误 " <img src=x> & 失败'},
    ]});
    const wrapper = mount(TaskTable, {props: {items: [value], selected: new Set<number>(), loading: false, busy: false, error: ''}});
    const details = wrapper.get('details');
    expect(details.get('summary').text()).toBe('部分失败');
    expect(details.find('img').exists()).toBe(false);
    expect(details.text()).toContain('错误 " <img src=x> & 失败');
    expect(details.text()).toContain('Plus: 五折 2个月');
    expect(wrapper.findAll('details')).toHaveLength(1);
    wrapper.unmount();
  });
});
