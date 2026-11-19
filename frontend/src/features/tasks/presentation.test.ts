import {mount} from '@vue/test-utils';
import {describe, expect, it} from 'vitest';
import {canRetry, canStop, eligible, planResult, resultText, errorText, failureStageText, resultDetails, label, formatDateTime} from './presentation';
import TaskResultCell from './TaskResultCell.vue';
import type {OperationTask} from '../../api/tasks';
const task = (patch: Partial<OperationTask>): OperationTask => ({id: 1, task_type: 'plan_check', ...patch});
describe('任务公开表现和动作资格', () => {
  it('复用时间格式器后仍采用本地时区并区分缺失和无效时间', () => {
    const formatter = new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    });
    for (const value of ['2026-01-01T23:59:59Z', '2026-07-01T00:00:00+08:00', '2026-01-01T23:59:59Z']) {
      expect(formatDateTime(value)).toBe(formatter.format(new Date(value)));
    }
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('invalid')).toBe('无效时间：invalid');
  });
  it('允许有来源的响应未知任务重跑，活动和废号任务不可重跑', () => {
    const retryable = task({status: 'request_unknown', next_actions: [{action: 'retry'}]});
    expect(canRetry(retryable)).toBe(true);
    expect(canRetry({...retryable, status: 'running'})).toBe(false);
    expect(canRetry({...retryable, target_status: 'account_deactivated'})).toBe(false);
    expect(canRetry({...retryable, result_summary: {requested_status: 'deactivated'}})).toBe(false);
  });
  it('取消与终止沿用原生任务边界，批量取消只选排队项', () => {
    const queued = task({status: 'queued', source_system: 'native_operations'});
    expect(canStop(queued)).toBe(true);
    expect(eligible(queued, 'cancel')).toBe(true);
    expect(eligible(queued, 'terminate')).toBe(false);
    expect(eligible({...queued, status: 'running'}, 'delete')).toBe(false);
    expect(canStop({...queued, source_system: 'registration_jobs'})).toBe(false);
  });
  it('提链成功后的支付失败不覆盖提链事实', () => {
    expect(resultText(task({task_type: 'extract_link', status: 'failed', error_message: '支付失败',
      result_summary: {extraction_status: 'success', payment_status: 'failed', link_type: 'plus'}})))
      .toBe('提链成功 · PLUS · 支付失败');
  });
  it('国家查询失败的历史优惠明确标识为历史，空国家数组忽略旧多国结果', () => {
    const summary = {current_plan_type: 'free', plan_check_countries: ['US'], plan_check_country_results: [{country: 'US', status: 'failed',
      last_success_at: '2026-11-01', result: {account_promotions: [{plan: 'plus', kind: 'free_trial'}]}}]};
    expect(planResult(summary, 'failed', true)).toContain('全部失败 · Plus 免费 · 历史');
    expect(planResult({...summary, plan_check_countries: [], account_promotions: [{plan: 'plus', kind: 'none'}, {plan: 'go', kind: 'none'}]}, 'success', true)).toBe('free · 无优惠');
  });
  it('错误摘要保留根因且不重复', () => {
    expect(errorText({summary: '邮箱验证失败', cause_summary: '收码超时'})).toBe('邮箱验证失败 · 收码超时');
    expect(errorText({summary: '邮箱验证失败 · 收码超时', cause_summary: '收码超时'})).toBe('邮箱验证失败 · 收码超时');
  });
  it('Sub2API 扫描完成只依据任务状态，不依据旧摘要 ok', () => {
    for (const status of ['unsupported', 'failed']) {
      expect(resultText(task({task_type: 'sub2api_scan', status, result_summary: {ok: true}})))
        .toBe('扫描未完成，请查看任务日志');
      expect(resultText(task({task_type: 'sub2api_scan', status, result_summary: {ok: true, error_code: 'scan_not_supported'}})))
        .toBe('scan_not_supported');
    }
    expect(resultText(task({task_type: 'sub2api_scan', status: 'success', result_summary: {ok: false}})))
      .toBe('Sub2API 异常扫描已完成');
  });
  it('手机验证诊断在结果详情保留逐次细因和代码，并转义远端文本', () => {
    const value = task({task_type: 'codex_retry', status: 'failed', error_message: '手机验证失败', error_code: 'phone_attempts_exhausted',
      error_info: {summary: '手机验证失败', cause_summary: '第 2 次：当前号码触发风控 <phone>',
        code: 'phone_verification_failed', cause_code: 'codex_phone_verification_failed', cause_display_code: 'CODEX-PHONE-SEND'},
      result_summary: {ok: false}});
    expect(resultDetails(value)).toBe('手机验证失败 · 第 2 次：当前号码触发风控 <phone>');
    const wrapper = mount(TaskResultCell, {props: {task: value}});
    try {
      expect(wrapper.get('summary').attributes('title')).toContain('第 2 次：当前号码触发风控 <phone>');
      expect(wrapper.get('.list-result-details').text()).toContain('CODEX-PHONE-SEND');
      expect(wrapper.get('.list-result-details').text()).toContain('第 2 次：当前号码触发风控 <phone>');
      for (const code of ['phone_attempts_exhausted', 'phone_verification_failed', 'codex_phone_verification_failed']) {
        expect(wrapper.get('.list-result-details').text()).toContain(code);
        expect(wrapper.get('summary').attributes('title')).toContain(code);
        expect(wrapper.get('summary').text()).not.toContain(code);
      }
      expect([...wrapper.get('summary').text()].length).toBeLessThanOrEqual(10);
      expect(wrapper.find('phone').exists()).toBe(false);
      expect(value.status).toBe('failed');
      expect(value.result_summary?.ok).toBe(false);
    } finally { wrapper.unmount(); }
  });
});

it('Codex 授权分别展示上传成功、失败、停止与未启用', () => {
  const summary = (extra: Record<string, unknown> = {}) => resultText(task({task_type: 'codex_retry', status: 'success', result_summary: {ok: true, credential_confirmed: true, ...extra}}));
  expect(summary({sub2api_sync: {status: 'success'}})).toBe('授权成功 · sub2api 已启用');
  expect(summary({sub2api_sync: {status: 'failed'}})).toBe('授权成功 · sub2api 同步失败');
  expect(summary({sub2api_sync: {status: 'cancelled'}})).toBe('授权成功 · sub2api 同步已停止');
  expect(summary()).toBe('授权成功 · 凭证已确认');
  expect(summary({credential_confirmed: false})).toBe('授权成功');
});

it('MFA 诊断纠正失败步骤，调试暂停保持独立状态语义', () => {
  expect(failureStageText(task({task_type: 'token_refresh', status: 'failed', failure_stage: 'email_otp',
    result_summary: {auth_diagnostics: {operation: 'password_email_fallback', cause_operation: 'mfa_verify'}}}))).toBe('失败于 TOTP 验证');
  expect(label('status', 'debug_paused')).toBe('调试暂停');
});
it('套餐展开保留国家错误、历史时点和所有优惠支付方式', () => {
  const details = resultDetails(task({status: 'failed', result_summary: {
    country_failures: [{country: 'US', summary: '平台拒绝请求'}], plan_check_countries: ['US'],
    plan_check_country_results: [{country: 'US', status: 'failed', error: 'HTTP 403', last_success_at: '2026-11-01T00:00:00Z', result: {
      account_promotions: [{plan: 'plus', kind: 'free_trial', checkout_status: 'success', payment_method_types: ['card']}, {plan: 'plus', kind: 'discount', discount_percentage: 50, payment_method_types: ['upi']}],
    }}],
  }}));
  for (const expected of ['US：平台拒绝请求', 'US（历史）', 'HTTP 403', '上次成功查询', 'Plus: 免费', 'Plus: 五折', '银行卡', 'UPI']) expect(details).toContain(expected);
});
