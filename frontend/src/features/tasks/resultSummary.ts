import type {OperationTask} from '../../api/tasks';
import {taskWaitingLabel} from './statusDisplay';
import {shortErrorLabel} from '../../shared/errorLabels';
import {record} from './presentation';

export type ResultTone = 'success' | 'warning' | 'danger' | 'neutral' | 'active';
export interface TaskResultSummary {label: string; secondary?: string; tone: ResultTone}
const summary = (label: string, tone: ResultTone = 'neutral', secondary?: string): TaskResultSummary =>
  ({label, ...(secondary ? {secondary} : {}), tone});
const list = (value: unknown) => Array.isArray(value) ? value.map(record) : [];
const text = (value: unknown) => String(value || '').toLowerCase();
const unconfirmed = new Set(['unknown', 'request_unknown', 'attention_required', 'manual_reconcile', 'unconfirmed', 'password_confirmation_pending', 'credential_pending_confirmation']);
const failed = new Set(['failed', 'error', 'deactivated']);

function hasSpecificError(task: OperationTask): boolean {
  // Follow the backend classifier: a confirmed cause can coexist with an unknown
  // remote outcome. Missing receipts/diagnostics are not evidence of that cause.
  const info = task.error_info;
  if (!info) return false;
  for (const field of ['cause_code', 'code'] as const) {
    const code = text(info[field]).trim();
    if (!code) continue;
    if (unconfirmed.has(code) || ['unknown.unclassified', 'task.pending'].includes(code)
      || /(?:_receipt_missing|_failure_diagnostics_missing|_evidence_missing|_unconfirmed|_request_unknown|\.confirmation|\.safety)$/.test(code)) return false;
    if (shortErrorLabel({[field]: code}) !== shortErrorLabel()) return true;
  }
  return false;
}

const waitingLabels: Record<string, string> = {
  executor_capacity: '等待执行空位', resource_capacity: '等待资源空位', global_capacity: '等待全局空位',
  type_capacity: '等待本类空位', batch_paused: '等待批次继续', batch_capacity: '等待批次空位',
  provider_capacity: '等待平台空位', account_busy: '等待账号空闲', remote_order_capacity: '等待订单名额',
  not_due: '等待下次查询', execution_active: '等待执行退出', fairness_turn: '等待调度轮次',
  concurrency_policy_migration_required: '并发配置待迁移', scheduler_store_unavailable: '调度存储异常', permit_owner_lost: '执行许可变更',
};

/** 已登记任务的完成用语；它只描述操作完成，不推断远端状态。 */
export const taskCompletionLabels: Record<string, string> = {
  registration: '注册完成', registration_resume: '续注册完成', twofa_retry: '验证配置完成',
  account_setup_retry: '账号配置完成', password_setup: '密码已补齐', password_change: '密码已修改',
  twofa_setup: '双重验证已设', twofa_change: '双重验证已改', account_completion: '账号已补全',
  email_change: '换绑已完成', codex_retry: '授权已完成', codex_token_refresh: '令牌刷新完成',
  sub2api_sync: '凭证同步完成', sub2api_manual_upload: '凭证上传完成', sub2api_scan: '异常扫描完成',
  live_check: '查活完成', token_refresh: '刷新完成', plan_check: '套餐查询完成', deactivation_mail: '邮件检查完成',
  extract_link: '提链流程完成', account_inspection: '账号巡检完成', account_inspection_batch: '批次巡检完成',
  c2a_session_reimport: '令牌导入完成', sentinel_maintenance_check: '维护检查完成',
};

function extractionSummary(task: OperationTask, errorLabel: string): TaskResultSummary {
  const r = record(task.result_summary), status = text(task.status);
  const extraction = text(r.extraction_status), payment = text(r.payment_status);
  const extracted = ['succeeded', 'success'].includes(extraction) || (!extraction && r.ok === true && r.has_link === true);
  if (extracted) {
    if (['failed', 'error'].includes(payment)) return summary('提链成功', 'danger', '支付失败');
    if (['succeeded', 'success', 'paid'].includes(payment)) return summary('提链成功', 'success', '支付成功');
    if (unconfirmed.has(payment)) return summary('提链成功', 'warning', '支付待确认');
    if (['pending', 'pending_payment', 'processing'].includes(payment) || r.mode === 'manual_payment' && payment === 'not_started') {
      return summary('提链成功', 'warning', r.mode === 'manual_payment' ? '待手动支付' : '支付处理中');
    }
    if (['cancelled', 'stopped', 'interrupted'].includes(status)) return summary('提链成功', 'warning', '后续已中断');
    if (unconfirmed.has(status) || unconfirmed.has(text(task.internal_status))) return summary('提链成功', 'warning', '后续待确认');
    if (['failed', 'partial_success'].includes(status)) return summary('提链成功', 'danger', '后续失败');
    return summary('提链成功', 'success');
  }
  if (failed.has(extraction)) return summary(errorLabel, 'danger');
  if (hasSpecificError(task)) return summary(errorLabel, 'danger');
  if (unconfirmed.has(extraction)) return summary('提链待确认', 'warning');
  if (['pending', 'queued'].includes(extraction)) return summary('等待提链', 'warning');
  if (extraction === 'running') return summary('提链中', 'active');
  if (status === 'cancelled') return summary('已取消');
  if (['stopped', 'interrupted'].includes(status)) return summary('执行已中断', 'warning');
  if (unconfirmed.has(status) || unconfirmed.has(text(task.internal_status))) return summary('提链待确认', 'warning');
  if (task.error_message || task.error_info || r.ok === false || status === 'failed') return summary(errorLabel, 'danger');
  if (r.ok === true) return summary('提链流程完成', 'success');
  return summary('提链结果缺失', 'warning');
}

function planSummary(task: OperationTask, errorLabel: string): TaskResultSummary {
  const r = record(task.result_summary), status = text(task.status);
  const disabled = Array.isArray(r.plan_check_countries) && r.plan_check_countries.length === 0;
  const countries = disabled ? [] : list(r.plan_check_country_results).filter(country => country.country);
  const successCount = countries.length ? countries.filter(country => country.status === 'success').length : Number(r.country_success_count || 0);
  const failedCount = countries.length ? countries.filter(country => ['failed', 'cancelled'].includes(text(country.status))).length : !disabled && Array.isArray(r.failed_countries) ? r.failed_countries.length : 0;
  const total = countries.length || (!disabled ? Number(r.country_total_count || 0) : 0);
  const offers: Record<string, unknown>[] = countries.length ? countries.flatMap(country => {
    const current = country.status === 'success';
    const snapshot = record(country.result);
    if (!current && !country.last_success_at) return [];
    return list(snapshot.account_promotions).map(offer => ({...offer, stale: !current || offer.stale === true}));
  }) : list(r.account_promotions);
  const historical = offers.some(offer => offer.stale === true)
    || countries.some(country => country.status !== 'success' && country.last_success_at && Object.keys(record(country.result)).length > 0);
  if (failedCount > 0 && successCount > 0 || !disabled && r.plan_check_partial === true) return summary('部分失败', 'warning', historical ? '含历史数据' : undefined);
  if (total > 0 && failedCount >= total) return historical ? summary('查询失败', 'danger', '含历史数据') : summary(errorLabel, 'danger');
  if (hasSpecificError(task)) return summary(errorLabel, 'danger');
  if (unconfirmed.has(status) || unconfirmed.has(text(task.internal_status)) || unconfirmed.has(text(r.status))) return summary('查询待确认', 'warning', historical ? '含历史数据' : undefined);
  if (task.error_message || task.error_info || status === 'failed' || r.ok === false) return historical ? summary('查询失败', 'danger', '含历史数据') : summary(errorLabel, 'danger');
  if (status === 'partial_success') return summary('部分完成', 'warning', historical ? '含历史数据' : undefined);
  if (countries.some(country => ['queued', 'running'].includes(text(country.status)))) return summary('部分仍待查询', 'warning');
  if (!Object.keys(r).length) return summary('套餐结果缺失', 'warning');
  const plan = ({free: '免费套餐', plus: 'Plus', go: 'Go', pro: 'Pro', team: '团队套餐', business: '商业套餐', enterprise: '企业套餐'} as Record<string, string>)[text(r.current_plan_type || r.plan_type)] || '已查询';
  if (historical) return summary(plan, 'warning', '含历史数据');
  const priority: Record<string, number> = {free_trial: 0, discount: 1, other_promo: 2, unknown: 3, pending: 4, failed: 5, cancelled: 5, none: 6, not_applicable: 7};
  const offer = [...offers].sort((a, b) => (priority[text(a.kind)] ?? 3) - (priority[text(b.kind)] ?? 3)
    || Number(b.plan === 'plus') - Number(a.plan === 'plus'))[0];
  if (offer) {
    const offerPlan = offer.plan === 'plus' ? 'Plus' : offer.plan === 'go' ? 'Go' : '';
    const label = ({free_trial: `${offerPlan}免费`, discount: `${offerPlan}折扣`, other_promo: '其他优惠',
      none: '无优惠', not_applicable: '优惠不适用', unknown: '优惠待复查', pending: '优惠待查询', failed: '优惠查询失败', cancelled: '优惠已取消'} as Record<string, string>)[text(offer.kind)] || '优惠待复查';
    return summary(plan, ['unknown', 'pending', 'failed', 'cancelled'].includes(text(offer.kind)) ? 'warning' : 'success', label);
  }
  // Legacy single-country records use explicit promotion evidence; absence is not “no offers”.
  if (r.plus_trial_eligible === true || r.plus_promo_kind === 'free_trial') return summary(plan, 'success', 'Plus免费');
  if (r.plus_discount_eligible === true || r.plus_promo_kind === 'discount') return summary(plan, 'success', 'Plus折扣');
  if (r.plus_promo_kind === 'none' || r.plus_promo_eligible === false) return summary(plan, 'success', '无优惠');
  return summary(plan, 'neutral', '优惠待复查');
}

/**
 * 列表专用的语义短摘要：默认可见文字总计不超过 10 个 Unicode 字符。
 * errorLabel 来自共享错误目录；原始日志、错误码、国家明细只在详情中展示。
 * 不使用字符串截断或自由文本猜测结果，不改变任务的执行/重跑判定。
 */
export function taskResultSummary(task: OperationTask, errorLabel = '执行异常'): TaskResultSummary {
  const r = record(task.result_summary), status = text(task.status), kind = task.task_type;
  // Reject an unregistered long label at the boundary rather than silently cutting its meaning.
  const error = errorLabel && [...errorLabel].length <= 10 ? errorLabel : '执行异常';
  if (task.debug_pause) return summary('调试已暂停', 'warning');
  if (['queued', 'pending'].includes(status)) {
    const reason = task.admission_wait_reasons?.[0]?.code || task.admission_wait_reason || '';
    return summary(waitingLabels[String(reason)] || '等待执行', 'warning');
  }
  if (status === 'waiting') {
    const reason = task.admission_wait_reasons?.[0]?.code || task.admission_wait_reason || '';
    return summary(waitingLabels[String(reason)] || taskWaitingLabel(task), 'warning');
  }
  if (status === 'running') return summary('执行中', 'active');
  if (['stopping', 'cancelling'].includes(status)) return summary('正在停止', 'warning');
  if (status === 'settling') return summary('正在收尾', 'active');
  if (kind === 'extract_link') return extractionSummary(task, error);
  if (kind === 'email_change' && r.email_change_confirmed === true) return summary('邮箱已换绑', 'success', record(r.post_change_live_check).accepted ? '刷新已排队' : '刷新待处理');
  if (kind === 'codex_retry' && r.ok === true) {
    const sync = text(record(r.sub2api_sync).status);
    if (sync === 'failed') return summary('授权成功', 'warning', '同步失败');
    if (sync === 'cancelled') return summary('授权成功', 'warning', '同步已停止');
    if (sync === 'success') return summary('授权成功', 'success', '同步已完成');
    return summary('授权成功', 'success', r.credential_confirmed === true ? '凭证已确认' : undefined);
  }
  if (kind === 'codex_token_refresh' && r.ok === true) return summary('令牌已刷新', r.sub2_sync === 'failed' ? 'warning' : 'success', r.sub2_sync === 'failed' ? '同步失败' : undefined);
  if (kind === 'sub2api_manual_upload' && r.uploaded === true && (status !== 'success' || r.ok === false)) return summary('上传已完成', 'warning', '回写待确认');
  if (kind === 'sub2api_sync' && r.superseded === true) return summary('新凭证已接续');
  if (kind === 'account_inspection') {
    if (r.inspection_outcome === 'deactivated_skipped') return summary('已废账号跳过');
    if (r.inspection_outcome === 'deleted_skipped') return summary('已删账号跳过');
    if (r.inspection_outcome === 'valid') return summary('令牌本地有效', 'success');
    if (r.inspection_outcome === 'refreshed') return summary('令牌已刷新', r.plan_ok === false ? 'warning' : 'success', r.plan_ok === false ? '查套餐失败' : undefined);
  }
  if (kind === 'plan_check') return planSummary(task, error);
  if (status === 'cancelled') return summary('已取消');
  if (['stopped', 'interrupted'].includes(status)) return summary('执行已中断', 'warning');
  if (hasSpecificError(task)) return summary(error, 'danger');
  if (unconfirmed.has(status) || unconfirmed.has(text(task.internal_status)) || unconfirmed.has(text(r.status))) return summary('结果待确认', 'warning');
  if (['deactivated', 'account_deactivated'].includes(text(task.target_status)) || status === 'deactivated') return summary('账号已停用', 'danger');
  if (task.error_message || task.error_info || failed.has(status) || kind !== 'sub2api_scan' && r.ok === false) return summary(error, 'danger');
  if (status === 'partial_success') return summary('部分完成', 'warning');
  if (kind === 'sub2api_scan') return status === 'success' ? summary(taskCompletionLabels[kind]!, 'success') : summary('扫描未完成', 'warning');
  if (kind === 'registration' || kind === 'registration_resume') {
    const target = ({account_available: '账号可用', email_verification_pending: '邮箱待验证', credential_valid: '凭证有效', credential_pending_confirmation: '凭证待确认', not_created: '账号未创建', in_progress: '账号处理中'} as Record<string, string>)[text(task.target_status)];
    if (target) return summary(target, ['account_available', 'credential_valid'].includes(text(task.target_status)) ? 'success' : 'warning');
  }
  if (kind === 'deactivation_mail' && typeof r.detected === 'boolean') return summary(r.detected ? '发现封号邮件' : '未见封号邮件', r.detected ? 'warning' : 'neutral');
  if (kind === 'live_check' && r.ok === true) return summary('账号正常', 'success');
  if (kind === 'token_refresh' && r.ok === true) return summary('令牌已刷新', 'success');
  if (kind === 'account_inspection_batch' && Number(r.failed_count) > 0) return summary('巡检已完成', 'warning', '存在失败');
  if (status === 'success' || r.ok === true) return summary(taskCompletionLabels[kind] || '任务已完成', 'success');
  return summary('结果未记录');
}
