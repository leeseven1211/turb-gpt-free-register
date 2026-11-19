import {describe, expect, it} from 'vitest';
import type {OperationTask} from '../../api/tasks';
import {labels, resultDetails} from './presentation';
import {taskCompletionLabels, taskResultSummary} from './resultSummary';

const task = (task_type: string, result_summary: Record<string, unknown> = {}, patch: Partial<OperationTask> = {}): OperationTask =>
  ({id: 1, task_type, status: 'success', result_summary, ...patch});
const visible = (value: ReturnType<typeof taskResultSummary>) => value.label + (value.secondary || '');

describe('任务列表语义短摘要', () => {
  it('Sub2API 扫描只以成功终态显示完成，旧 ok 不覆盖未支持或失败状态', () => {
    expect(taskResultSummary(task('sub2api_scan', {ok: true}, {status: 'unsupported'})))
      .toEqual({label: '扫描未完成', tone: 'warning'});
    expect(taskResultSummary(task('sub2api_scan', {ok: true}, {status: 'failed'})))
      .toEqual({label: '执行异常', tone: 'danger'});
    expect(taskResultSummary(task('sub2api_scan', {ok: false}, {status: 'success'})))
      .toEqual({label: '异常扫描完成', tone: 'success'});
  });
  it('为所有登记任务类型及未知类型提供十字以内的结果和终态兜底', () => {
    for (const type of Object.keys(labels.task_type)) expect(taskCompletionLabels[type]).toBeTruthy();
    for (const type of [...Object.keys(taskCompletionLabels), 'future_task_type']) {
      for (const status of ['queued', 'running', 'waiting', 'settling', 'stopping', 'cancelled', 'stopped', 'interrupted', 'failed', 'success', 'partial_success', 'request_unknown', '']) {
        const value = taskResultSummary(task(type, {}, {status}));
        expect([...visible(value)].length, `${type}/${status}: ${visible(value)}`).toBeLessThanOrEqual(10);
        expect(visible(value)).not.toMatch(/undefined|\{|\.\.\.|…/);
      }
    }
    expect(taskResultSummary(task('future_task_type', {}, {status: ''})).label).toBe('结果未记录');
    expect(taskResultSummary(task('token_refresh', {}, {status: 'failed', error_message: '401 Unauthorized'}), '凭证失效').label).toBe('凭证失效');
  });

  it('提链成功不被支付失败覆盖，支付成功不代表套餐已升级', () => {
    for (const [payment, expected] of [
      ['failed', '支付失败'], ['unknown', '支付待确认'], ['processing', '支付处理中'], ['succeeded', '支付成功'],
    ]) {
      const value = taskResultSummary(task('extract_link', {extraction_status: 'success', payment_status: payment}, {status: 'failed', error_message: '支付接口异常'}));
      expect(value.label).toBe('提链成功');
      expect(value.secondary).toBe(expected);
      expect([...visible(value)].length).toBeLessThanOrEqual(10);
      expect(visible(value)).not.toContain('升级');
    }
    expect(taskResultSummary(task('extract_link', {extraction_status: 'success', payment_status: 'not_started', mode: 'manual_payment'})).secondary).toBe('待手动支付');
    expect(taskResultSummary(task('extract_link', {extraction_status: 'failed', ok: true, has_link: true}, {status: 'failed'}), '平台拒绝请求').label).toBe('平台拒绝请求');
    expect(taskResultSummary(task('extract_link', {extraction_status: 'unknown'}, {status: 'failed'})).label).toBe('提链待确认');
    expect(taskResultSummary(task('extract_link')).label).toBe('提链结果缺失');
  });

  it('保留授权、换绑、令牌刷新、上传的独立成果与后续异常', () => {
    const values = [
      taskResultSummary(task('codex_retry', {ok: true, sub2api_sync: {status: 'failed'}})),
      taskResultSummary(task('codex_retry', {ok: true, sub2api_sync: {status: 'cancelled'}})),
      taskResultSummary(task('codex_retry', {ok: true, sub2api_sync: {status: 'success'}})),
      taskResultSummary(task('codex_retry', {ok: true, credential_confirmed: true})),
      taskResultSummary(task('email_change', {email_change_confirmed: true, post_change_live_check: {accepted: false}})),
      taskResultSummary(task('email_change', {email_change_confirmed: true, post_change_live_check: {accepted: true}})),
      taskResultSummary(task('codex_token_refresh', {ok: true, sub2_sync: 'failed'})),
      taskResultSummary(task('sub2api_manual_upload', {uploaded: true, ok: false}, {status: 'failed'})),
      taskResultSummary(task('account_inspection', {inspection_outcome: 'refreshed', plan_ok: false})),
    ];
    expect(values.map(visible)).toEqual(['授权成功同步失败', '授权成功同步已停止', '授权成功同步已完成', '授权成功凭证已确认',
      '邮箱已换绑刷新待处理', '邮箱已换绑刷新已排队', '令牌已刷新同步失败', '上传已完成回写待确认', '令牌已刷新查套餐失败']);
    for (const value of values) expect([...visible(value)].length).toBeLessThanOrEqual(10);
  });

  it('套餐保留部分失败和历史快照，完整国家与优惠信息仍由详情提供', () => {
    const value = task('plan_check', {current_plan_type: 'free', plan_check_country_results: [
      {country: 'JP', status: 'success', result: {account_promotions: [{plan: 'plus', kind: 'discount', discount_percentage: 50}]}},
      {country: 'VN', status: 'failed', last_success_at: '2026-11-01', error: 'HTTP 429', result: {account_promotions: [{plan: 'plus', kind: 'free_trial'}]}},
    ]});
    expect(taskResultSummary(value)).toEqual({label: '部分失败', secondary: '含历史数据', tone: 'warning'});
    expect(resultDetails(value)).toContain('VN');
    expect(resultDetails(value)).toContain('HTTP 429');
    expect(resultDetails(value)).toContain('上次成功查询');
    const countries = value.result_summary!.plan_check_country_results as unknown[];
    const failed = task('plan_check', {current_plan_type: 'free', plan_check_country_results: [countries[1]]}, {status: 'failed'});
    expect(visible(taskResultSummary(failed))).toBe('查询失败含历史数据');
    const disabled = {...value, result_summary: {...value.result_summary, plan_check_countries: [], plan_check_partial: true, account_promotions: [{plan: 'go', kind: 'none'}, {plan: 'plus', kind: 'none'}]}};
    expect(visible(taskResultSummary(disabled))).toBe('免费套餐无优惠');
  });

  it('套餐优惠摘要不截断外部套餐名称，未知优惠不说成无优惠', () => {
    for (const plan of ['free', 'plus', 'enterprise', 'future-super-long-plan-name']) {
      for (const kind of ['free_trial', 'discount', 'other_promo', 'none', 'not_applicable', 'pending', 'unknown', 'failed']) {
        const value = taskResultSummary(task('plan_check', {current_plan_type: plan, account_promotions: [{plan: 'plus', kind}]}));
        expect([...visible(value)].length, visible(value)).toBeLessThanOrEqual(10);
      }
    }
    expect(visible(taskResultSummary(task('plan_check', {current_plan_type: 'free'})))).toBe('免费套餐优惠待复查');
    expect(taskResultSummary(task('plan_check', {current_plan_type: 'free'}, {status: 'partial_success'}))).toEqual({label: '部分完成', tone: 'warning'});
  });

  it('结构化具体原因优先于待确认状态，缺回执和未分类错误不伪装成已知原因', () => {
    for (const taskType of ['token_refresh', 'plan_check', 'extract_link']) {
      const base = task(taskType, {status: 'request_unknown', extraction_status: 'unknown'}, {status: 'failed', internal_status: 'request_unknown'});
      for (const [info, label] of [
        [{cause_code: 'email_otp_no_mail', reconcile_required: true}, '验证码未送达'],
        [{code: 'lease_expired', remote_state_impact: 'unknown'}, '邮箱租约已过期'],
        [{cause_code: 'password_verify_http_error', cause_display_code: 'OA-PWD-401'}, '密码请求未授权'],
      ] as const) {
        const value = taskResultSummary({...base, error_info: info}, label);
        expect(value).toEqual({label, tone: 'danger'});
        expect(visible(value)).not.toContain('停用');
        expect([...visible(value)].length).toBeLessThanOrEqual(10);
        expect(base.internal_status).toBe('request_unknown');
      }
      for (const info of [undefined, {code: 'request_unknown'}, {cause_code: 'email_otp_receipt_missing'},
        {cause_code: 'email_otp_evidence_missing'}, {code: 'unknown.unclassified'}, {cause_code: 'future_unknown_cause'}]) {
        const value = taskResultSummary({...base, error_info: info, error_message: 'email_otp_no_mail'}, '验证码未送达');
        expect(value.label).toContain('待确认');
      }
    }
  });

  it('既有错误来自分类目录，未确认响应不伪装成成功或废号', () => {
    const value = task('token_refresh', {status: 'request_unknown', error: 'HTTP 401'}, {status: 'failed', error_message: 'HTTP 401'});
    expect(taskResultSummary(value, '认证被拒绝')).toEqual({label: '结果待确认', tone: 'warning'});
    expect(taskResultSummary({...value, result_summary: {}, internal_status: 'request_unknown'}, '认证被拒绝').label).toBe('结果待确认');
    expect(taskResultSummary(task('token_refresh', {}, {status: 'failed', error_message: 'HTTP 401'}), '认证被拒绝').label).toBe('认证被拒绝');
    expect(taskResultSummary(task('token_refresh', {}, {status: 'failed'}), '一个未登记并且长度超限的错误摘要').label).toBe('执行异常');
    expect(taskResultSummary(task('account_inspection', {inspection_outcome: 'valid'})).label).toBe('令牌本地有效');
    expect(taskResultSummary(task('account_inspection', {inspection_outcome: 'deactivated_skipped'})).label).toBe('已废账号跳过');
    expect(taskResultSummary(task('sub2api_sync', {superseded: true})).label).toBe('新凭证已接续');
  });

  it('排队与调试状态优先旧错误，等待原因使用简短分类', () => {
    const queued = task('token_refresh', {}, {status: 'queued', error_message: '旧错误', admission_wait_reason: 'account_busy'});
    expect(taskResultSummary(queued)).toEqual({label: '等待账号空闲', tone: 'warning'});
    expect(taskResultSummary({...queued, debug_pause: {reason: 'manual'}})).toEqual({label: '调试已暂停', tone: 'warning'});
    expect(taskResultSummary({...queued, status: 'waiting', admission_wait_reason: ''})).toEqual({label: '等待中', tone: 'warning'});
    expect(taskResultSummary({...queued, status: 'waiting', admission_wait_reason: '', next_actions: [{action: 'await_child'}]})).toEqual({label: '等待子任务', tone: 'warning'});
    expect(taskResultSummary({...queued, status: 'waiting'})).toEqual({label: '等待账号空闲', tone: 'warning'});
  });
});
