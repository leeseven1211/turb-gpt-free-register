import type {OperationTask, OperationRun, ErrorInfo, TaskAction} from '../../api/tasks';
import {shortErrorLabel} from '../../shared/errorLabels';
import {formatDateTime} from '../../shared/time';
export {formatDateTime} from '../../shared/time';

export const labels: Record<string, Record<string, string>> = {
  status: {
    queued:'排队中', pending:'排队中', running:'运行中', waiting:'等待中', stopping:'停止中', cancelling:'停止中', settling:'收尾中',
    failed:'失败', partial_success:'部分成功', password_confirmation_pending:'失败', success:'成功', stopped:'已停止', cancelled:'已取消', interrupted:'执行中断',
    debug_paused:'调试暂停', deactivated:'已停用', unsupported:'不支持', attention_required:'失败', request_unknown:'失败', manual_reconcile:'失败',
    available:'可用', used:'已使用', pending_sync:'导入处理中', tombstone:'本地已删除', replaced:'换绑后邮箱', disabled:'停用', exported:'已导出', unexported:'未导出', archived:'已归档',
  },
  source: {
    outlook:'Outlook', generic_api:'通用 API', cloudflare_domain:'域名邮箱', cloudflare_temp:'Cloudflare 临时邮箱',
    icloud_hide:'iCloud 隐藏邮箱', email_butler:'Email Butler', gptmail:'GPTMail', mailnest:'MailNest', remail:'Remail', cloudmail:'CloudMail', mailcode:'域名邮箱 MailCode', xigua:'西瓜邮箱',
  },
  registration_driver: {
    roxy:'roxy', roxy_oss:'roxy-public', protocol:'proto-local',
    protocol_oss:'proto-public', protocol_oss_2:'proto-sso', sentinel_rs:'rust-kernel', cloakbrowser:'CloakBrowser（历史）', unknown:'未记录',
  },
  token: {has:'有 Token', none:'无 Token'},
  account_token: {
    has:'正常', expired:'过期', invalid_401:'失效 · 401', invalid_403:'失效 · 403',
    invalid_other:'失效 · 其他', none:'无 Token',
  },
  password: {has:'本地已保存', none:'本地未保存'},
  totp: {enabled:'已启用', disabled:'未启用'},
  risk: {detected:'已收到', clear:'未发现', pending:'待处理'},
  promotion: {
    free_trial:'免费试用', half_price:'半价优惠', other_discount:'其他折扣', discount:'折扣优惠',
    other_promo:'其他优惠', none:'无优惠', unknown:'历史优惠待复查',
    pending:'待查询', failed:'查询失败', not_applicable:'不适用',
  },
  codex: {success:'已通过', retrying:'进行中', failed:'失败', stopped:'已停止', deactivated:'已停用', skipped:'已跳过', missing:'缺失'},
  account_status: {active:'未废号', deactivated:'已废号', unknown:'未查活'},
  task_type: {
    registration:'注册', registration_resume:'继续邮箱验证', twofa_retry:'2FA 配置补跑',
    account_setup_retry:'账号配置补跑', password_setup:'补密码', twofa_setup:'补 2FA', account_completion:'补全账号',
    email_change:'换绑邮箱', password_change:'修改密码', twofa_change:'修改 2FA',
    codex_retry:'Codex 补跑', codex_token_refresh:'Codex Token 刷新', sub2api_sync:'sub2api 凭据同步',
    live_check:'查活', token_refresh:'AT 刷新', plan_check:'查套餐', deactivation_mail:'查封号邮件', extract_link:'提炼',
    bulk_mutation:'批量数据操作', task_terminate_bulk:'批量终止任务',
  },
  trigger: {
    manual:'手动', manual_bulk:'手动批量', manual_retry:'失败重跑', scheduled:'定时',
    registration_auto:'注册后自动', registration_job_retry:'注册任务重试', token_refresh_scheduled:'AT 定时刷新',
    c2a_monitor:'C2A 异常巡检',
    codex_token_refresh_scheduled:'Codex 定时刷新', sub2api_monitor:'sub2api 异常巡检', sub2api_sync_retry:'sub2api 自动补传',
  },
  target_status: {
    not_created:'尚未创建', in_progress:'处理中', email_verification_pending:'待邮箱验证或资料补全',
    account_available:'账号可用', credential_valid:'凭证有效', credential_pending_confirmation:'凭据核验缺失',
    attention_required:'失败', deactivated:'账号已停用', account_deactivated:'账号已停用',
    cancelled:'已取消', failed:'失败', pending:'等待执行', request_unknown:'失败',
    manual_reconcile:'失败', completed:'已完成', unknown:'状态记录缺失',
  },
  stage: {
    queued:'进入队列', running:'执行中', preflight:'配置预检', network:'分配网络', network_route:'分配网络',
    driver:'启动浏览器', email:'准备邮箱', browser:'启动浏览器', page:'打开页面', submit_email:'提交邮箱',
    auth_redirect:'进入认证', email_otp:'邮箱验证', profile:'账号资料', token:'获取 Token', codex:'Codex 授权',
    login_password:'账号密码', mfa_challenge:'TOTP 验证', account_setup:'账号配置', access_token:'校验 Token', reauth:'重新登录',
    roxy_fallback:'浏览器回退', oauth:'Codex 授权', auth_url:'获取授权地址', login:'登录 OpenAI',
    phone_check:'检查手机验证', phone_acquire:'申请接码号码', phone_otp:'短信验证', consent:'确认授权',
    callback:'接收 OAuth 回调', credential_confirm:'确认远端凭证', credential_persist:'保存凭证', c2a_safety:'确认 C2A 安全策略', c2a_resolve:'定位 C2A 账号', c2a_update:'更新 C2A AT', cancelling:'正在停止',
    c2a_scan:'读取 C2A 异常账号', c2a_repair:'调度 C2A 修复',
    twofa:'设置 2FA', plan:'套餐信息', plan_check:'查询套餐', plan_request:'请求套餐', refresh_token:'刷新 Token',
    mailbox_scan:'扫描邮件', extract_link:'提炼', extraction:'平台提链', remote_sync:'原单状态查询', payment:'支付处理', login_mfa:'TOTP 验证', complete:'完成', interrupted:'执行中断', event:'事件',
  },
  run_count: {'0':'0 次', '1':'1 次', '2':'2 次', '3':'3 次', '4+':'4 次及以上'},
};
Object.assign(labels.task_type, {account_inspection: '账号巡检', account_inspection_batch: '巡检批次', sub2api_manual_upload: 'Sub2API 手动上传', sub2api_scan: 'Sub2API 异常扫描', c2a_session_reimport: 'C2A 重新导入', c2a_scan: 'C2A 异常巡检'});

export function label(group: string, value: unknown): string {
  const key = String(value || '');
  return labels[group]?.[key] || key || '—';
}
export function formatDuration(value: unknown): string {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  const ms = Math.max(0, Number(value));
  if (ms < 1000) return `${Math.round(ms)} 毫秒`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} 秒`;
  const seconds = Math.floor(ms / 1000);
  return seconds < 3600 ? `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
    : `${Math.floor(seconds / 3600)} 小时 ${Math.floor(seconds % 3600 / 60)} 分`;
}
export function errorText(info: ErrorInfo | null | undefined, raw: unknown = ''): string {
  const summary = String(info?.summary || raw || '错误原因未记录');
  const cause = String(info?.cause_summary || '').trim();
  return cause && !summary.includes(cause) ? `${summary} · ${cause}` : summary;
}
export function isActive(task: Pick<OperationTask, 'status'>): boolean {
  return ['queued', 'running', 'stopping', 'cancelling', 'settling', 'waiting'].includes(String(task.status));
}
export function canRetry(task: OperationTask): boolean {
  const summary = record(task.result_summary);
  const deactivated = task.status === 'deactivated' || ['deactivated', 'account_deactivated'].includes(String(task.target_status))
    || ['status', 'requested_status'].some(key => summary[key] === 'deactivated');
  return !isActive(task) && !deactivated && !!task.next_actions?.length;
}
export function canTerminate(task: OperationTask): boolean {
  return task.source_system === 'native_operations' && isActive(task) && task.status !== 'queued';
}
export function canStop(task: OperationTask): boolean {
  return task.source_system === 'native_operations' && (task.status === 'queued' || canTerminate(task));
}
export function eligible(task: OperationTask, action: TaskAction): boolean {
  return action === 'retry' ? canRetry(task) : action === 'cancel' ? task.status === 'queued'
    : action === 'delete' ? !isActive(task) : canTerminate(task);
}
export function statusTone(value: unknown): string {
  const status = String(value);
  if (['success', 'completed', 'account_available', 'credential_valid'].includes(status)) return 'success';
  if (['failed', 'attention_required', 'request_unknown', 'manual_reconcile', 'deactivated', 'account_deactivated'].includes(status)) return 'danger';
  if (['running', 'in_progress'].includes(status)) return 'active';
  if (['queued', 'waiting', 'partial_success', 'stopping', 'cancelling', 'settling'].includes(status)) return 'warning';
  return 'neutral';
}
export function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
const rows = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.map(record) : [];
export function admissionText(task: OperationTask | OperationRun): string {
  const reasons = task.admission_wait_reasons?.length ? task.admission_wait_reasons : task.admission_wait_reason ? [{code: task.admission_wait_reason}] : [];
  const names: Record<string, string> = {executor_capacity: '等待执行承载空位', resource_capacity: '等待业务资源空位', global_capacity: '等待全局空位',
    type_capacity: '等待本类空位', batch_paused: '等待批次继续', batch_capacity: '等待当前批次空位', provider_capacity: '等待平台空位',
    account_busy: '账号正由其他任务使用', remote_order_capacity: '等待远端订单名额', not_due: '等待下次平台查询',
    execution_active: '上一执行仍在退出或清理', fairness_turn: '等待公平调度轮次', concurrency_policy_migration_required: '等待配置并发迁移策略',
    scheduler_store_unavailable: '调度存储暂不可用', permit_owner_lost: '执行许可归属已变化'};
  return reasons.map(reason => {
    const known = names[String(reason.code)];
    const occupied = record(reason).occupied;
    const limit = record(reason).limit;
    return known ? known + (occupied != null && limit != null ? `（${occupied}/${limit}）` : '')
      : `调度等待原因未登记（${reason.code || '缺少原因代码'}）`;
  }).join('；');
}

function promotionKind(r: Record<string, unknown>): string {
  const explicit = String(r.plus_promo_kind || '').toLowerCase();
  if (['free_trial', 'discount', 'other_promo', 'none', 'unknown'].includes(explicit)) return explicit;
  const percentage = Number(r.plus_promo_discount_percentage ?? r.plus_trial_discount_percentage);
  const campaign = String(r.plus_promo_campaign_id || r.plus_trial_campaign_id || '').toLowerCase();
  const text = [campaign, r.plus_promo_title || r.plus_trial_title, r.plus_promo_promotion_type,
    r.plus_promo_promotion_type_label || r.plus_trial_promotion_type_label].join(' ').toLowerCase();
  if (percentage === 100) return 'free_trial';
  if ((percentage > 0 && percentage < 100) || /pct-off|discount|% off/.test(text)) return 'discount';
  if (text.includes('free trial') || campaign.includes('-free') || campaign.includes('trial')) return 'free_trial';
  if (text.trim()) return 'other_promo';
  if (r.plus_discount_eligible === true) return 'discount';
  return r.plus_promo_eligible === true || r.plus_trial_eligible === true ? 'unknown' : 'none';
}
function promotions(r: Record<string, unknown>): Record<string, unknown>[] {
  if (Array.isArray(r.account_promotions)) return ['go', 'plus'].flatMap(plan => {
    const matches = rows(r.account_promotions).filter(item => String(item.plan).toLowerCase() === plan);
    return matches.length ? matches.map(item => ({...item, plan})) : [{plan, kind: 'unknown'}];
  });
  const plan = String(r.current_plan_type || r.plan_type || '').toLowerCase();
  return [{plan: 'go', kind: 'pending'}, {plan: 'plus', kind: plan && plan !== 'free' ? 'not_applicable' : promotionKind(r),
    discount_percentage: r.plus_promo_discount_percentage ?? r.plus_trial_discount_percentage,
    duration_num_periods: r.plus_promo_duration_num_periods ?? r.plus_trial_duration_num_periods,
    duration_period: r.plus_promo_duration_period || r.plus_trial_duration_period}];
}
function promotionLabel(item: Record<string, unknown>): string {
  const units: Record<string, string> = {month: '个月', year: '年', week: '周', day: '天'};
  const count = Number(item.duration_num_periods), unit = units[String(item.duration_period)];
  const duration = count > 0 && unit ? ` ${count}${unit}` : '';
  if (item.kind === 'free_trial') return `免费${duration}`;
  if (item.kind === 'discount') {
    const n = Number(item.discount_percentage);
    return `${n === 50 ? '五折' : n > 0 && n < 100 ? `减 ${n}%` : '折扣'}${duration}`;
  }
  return ({other_promo: '其他优惠', none: '无优惠', unknown: '待复查', pending: '待查询', failed: '查询失败', cancelled: '已取消', not_applicable: '不适用'} as Record<string, string>)[String(item.kind)] || '待复查';
}
function bestPromotion(items: Record<string, unknown>[]): Record<string, unknown> {
  const priority: Record<string, number> = {free_trial: 0, discount: 1, other_promo: 2, unknown: 3, pending: 4, failed: 5, cancelled: 5, none: 6, not_applicable: 7};
  const duration = (item: Record<string, unknown>) => Number(item.duration_num_periods || 0) * ({day: 1, week: 7, month: 30, year: 365}[String(item.duration_period)] || 0);
  return [...items].sort((a, b) => (priority[String(a.kind)] ?? 3) - (priority[String(b.kind)] ?? 3)
    || (a.kind === 'discount' ? Number(b.discount_percentage || 0) - Number(a.discount_percentage || 0) : 0)
    || (['free_trial', 'discount'].includes(String(a.kind)) ? duration(b) - duration(a) : 0)
    || Number(b.plan === 'plus') - Number(a.plan === 'plus') || Number(!!a.stale) - Number(!!b.stale))[0] || {kind: 'pending'};
}
function offerText(items: Record<string, unknown>[], compact: boolean): string {
  const format = (item: Record<string, unknown>) => `${['free_trial', 'discount', 'other_promo'].includes(String(item.kind)) ? `${item.plan === 'go' ? 'Go' : 'Plus'} ` : ''}${promotionLabel(item)}${item.stale ? ' · 历史' : ''}`;
  return compact ? format(bestPromotion(items)) : items.map(item => `${item.plan === 'go' ? 'Go' : 'Plus'}: ${promotionLabel(item)}${item.stale ? '（历史）' : ''}`).join('；');
}
function countryPromotionGroups(r: Record<string, unknown>): {country: string; items: Record<string, unknown>[]}[] {
  if (Array.isArray(r.plan_check_countries) && !r.plan_check_countries.length) return [];
  const grouped = new Map<string, Record<string, unknown>[]>();
  for (const item of rows(r.account_promotions)) {
    const country = String(item.country || '').trim().toUpperCase();
    if (!country) continue;
    if (!grouped.has(country)) grouped.set(country, []);
    grouped.get(country)!.push({...item, country});
  }
  return [...grouped].map(([country, items]) => ({country, items: promotions({account_promotions: items})}));
}
export function planResult(r: Record<string, unknown>, status: string, compact = false): string {
  const prefix = r.current_plan_type ? `${compact ? '' : '套餐 '}${r.current_plan_type} · ` : '';
  const countriesDisabled = Array.isArray(r.plan_check_countries) && !r.plan_check_countries.length;
  const countries = countriesDisabled ? [] : rows(r.plan_check_country_results).filter(item => item.country);
  if (countries.length) {
    const success = countries.filter(item => item.status === 'success').length;
    const failed = countries.filter(item => ['failed', 'cancelled'].includes(String(item.status))).length;
    const active = countries.some(item => ['queued', 'running'].includes(String(item.status))) || ['queued', 'running'].includes(status);
    const state = failed === countries.length ? '全部失败' : ['failed', 'cancelled'].includes(status) && active
      ? status === 'cancelled' ? '已取消' : '查询中断' : failed && success ? '部分失败' : active ? '查询中' : '';
    const displays: {country: string; items: Record<string, unknown>[]}[] = countries.map(country => {
      const snapshot = record(country.result), hasSnapshot = !!Object.keys(snapshot).length && !!country.last_success_at;
      const pending = ['queued', 'running'].includes(String(country.status));
      const aborted = ['failed', 'cancelled'].includes(status);
      const items = country.status === 'success' ? promotions(snapshot).map(item => ({...item, stale: ['queued', 'running'].includes(status)}))
        : pending && !aborted ? [{kind: 'pending'}] : hasSnapshot ? promotions(snapshot).map(item => ({...item, stale: true}))
          : [{kind: country.status === 'cancelled' || status === 'cancelled' ? 'cancelled' : 'failed'}];
      return {country: String(country.country).toUpperCase(), items};
    });
    return prefix + [state, compact ? offerText(displays.flatMap(item => item.items), true)
      : displays.map(item => `${item.country} ${offerText(item.items, true)}`).join(' · ')].filter(Boolean).join(' · ');
  }
  const total = Number(r.country_total_count || (Array.isArray(r.plan_check_countries) ? r.plan_check_countries.length : 0));
  if (!countriesDisabled && total > 0) {
    const failed = Array.isArray(r.failed_countries) ? r.failed_countries
      .map(item => String(typeof item === 'object' ? record(item).country || '' : item || '').trim().toUpperCase()).filter(Boolean) : [];
    const success = Number(r.country_success_count || 0);
    const state = failed.length >= total && !success ? '全部失败' : failed.length && success ? '部分失败'
      : ['queued', 'running'].includes(status) ? '查询中' : '';
    const displays = countryPromotionGroups(r);
    const offers = displays.length ? compact ? offerText(displays.flatMap(item => item.items), true)
      : displays.map(item => `${item.country} ${offerText(item.items, true)}`).join(' · ')
      : Array.isArray(r.account_promotions) ? offerText(promotions(r), compact) : '';
    const summary = [state, !compact && failed.length ? `失败国家：${failed.join('、')}` : '', offers].filter(Boolean).join(' · ');
    if (summary) return prefix + summary;
  }
  if (!Array.isArray(r.account_promotions)) {
    const plan = String(r.current_plan_type || '');
    if (!plan) return '查询完成';
    return plan.toLowerCase() === 'free' ? `${prefix}Plus ${promotionLabel(promotions(r)[1]!)}` : `${compact ? '' : '套餐 '}${plan}`;
  }
  return prefix + offerText(promotions(r), compact);
}

function resultValue(task: OperationTask, compact = false): unknown {
  const status = String(task.status || '');
  if (status === 'queued') return admissionText(task) ? admissionText(task) : '等待执行';
  if (status === 'running') return '执行中';
  const result = record(task.result_summary);
  if (task.task_type === 'extract_link') {
    const extraction = String(result.extraction_status || '').toLowerCase();
    const payment = String(result.payment_status || '').toLowerCase();
    const extracted = ['succeeded', 'success'].includes(extraction)
      || (!extraction && result.ok === true && result.has_link === true);
    if (extracted) {
      const label = `提链成功${result.link_type ? ` · ${String(result.link_type).toUpperCase()}` : ''}`;
      if (['failed', 'error'].includes(payment)) return `${label} · 支付失败`;
      if (['succeeded', 'success', 'paid'].includes(payment)) return `${label} · 支付成功`;
      if (['unknown', 'request_unknown', 'attention_required'].includes(payment)) return `${label} · 支付响应缺失`;
      if (['pending', 'pending_payment', 'processing'].includes(payment)) {
        return `${label} · ${result.mode === 'manual_payment' ? '等待手动支付' : '支付处理中'}`;
      }
      if (result.mode === 'manual_payment' && payment === 'not_started') return `${label} · 等待手动支付`;
      if (['request_unknown', 'attention_required', 'partial_success'].includes(status)) return `${label} · 后续处理失败`;
      if (['cancelled', 'stopped', 'interrupted'].includes(status)) return `${label} · 任务已中断`;
      if (status === 'failed') return `${label} · 后续处理失败`;
      return label;
    }
    if (['failed', 'error'].includes(extraction)) return '提链失败';
    if (['unknown', 'request_unknown', 'attention_required'].includes(extraction)) return task.error_info?.summary || '提链失败 · 平台响应记录缺失';
    if (['pending', 'queued'].includes(extraction)) return '等待提链';
    if (extraction === 'running') return '提链中';
    if (status === 'cancelled') return '任务已取消';
    if (['stopped', 'interrupted'].includes(status)) return '任务已中断';
    if (['request_unknown', 'attention_required', 'partial_success', 'unknown'].includes(status)) return task.error_info?.summary || '提链失败 · 平台响应记录缺失';
    if (task.error_message) return errorText(task.error_info, task.error_message);
    if (Object.prototype.hasOwnProperty.call(result, 'ok')) {
      return result.message || result.status || (result.ok ? '提炼完成' : '提炼失败');
    }
    return result.message || (status === 'failed' ? '提链失败' : '提链结果未记录');
  }
  if (task.error_message) return errorText(task.error_info, task.error_message);
  if (task.task_type === 'registration' || task.task_type === 'registration_resume') {
    return label('target_status', task.target_status) || '注册执行已结束';
  }
  if (task.task_type === 'plan_check') return planResult(result, status, compact);
  if (task.task_type === 'deactivation_mail') {
    if (!Object.prototype.hasOwnProperty.call(result, 'detected')) return '-';
    return result.detected ? '发现封号邮件' : '未发现封号邮件';
  }
  if (task.task_type === 'live_check' || task.task_type === 'token_refresh') return result.ok ? '账号正常' : task.task_type === 'token_refresh' ? 'AT 刷新失败' : '查活失败';
  if (task.task_type === 'email_change') {
    if (result.email_change_confirmed) {
      return record(result.post_change_live_check).accepted ? '邮箱已换绑 · AT 刷新已排队' : '邮箱已换绑 · AT 刷新待处理';
    }
    return result.message || result.status || '邮箱换绑未完成';
  }
  if (['account_setup_retry','password_setup','password_change','twofa_setup','twofa_change','account_completion'].includes(task.task_type)) return result.ok ? (result.message || '账号配置操作已完成') : (result.message || '账号配置操作失败');
  if (task.task_type === 'codex_retry') {
    if (result.ok) {
      const syncStatus = record(result.sub2api_sync).status;
      if (syncStatus === 'success') return '授权成功 · sub2api 已启用';
      if (syncStatus === 'failed') return '授权成功 · sub2api 同步失败';
      if (syncStatus === 'cancelled') return '授权成功 · sub2api 同步已停止';
      return result.credential_confirmed ? '授权成功 · 凭证已确认' : '授权成功';
    }
    if (['attention_required','request_unknown'].includes(String(result.status))) return '授权失败 · 未取得有效凭据';
    return result.message || result.status || '补跑失败';
  }
  if (task.task_type === 'codex_token_refresh') {
    if (!result.ok) return 'OAuth Token 刷新失败';
    return result.sub2_sync === 'failed' ? 'Token 已刷新 · sub2 同步失败' : 'OAuth Token 已刷新';
  }
  if (task.task_type === 'c2a_session_reimport') return result.ok ? (result.message || 'C2A AT 已从本地重新导入') : result.error_code || result.message || 'C2A 重新导入失败，请查看任务日志';
  if (task.task_type === 'sub2api_manual_upload') return result.ok ? '手动上传 Sub2API 已完成' : result.error_code || result.message || '手动上传失败，请查看任务日志';
  if (task.task_type === 'c2a_scan') {
    if (status !== 'success') return errorText(task.error_info, result.error_code || result.message || 'C2A 异常扫描未完成，请查看任务日志');
    const parts = result.continuation_only
      ? ['C2A 修复接续检查已完成']
      : ['C2A 异常扫描已完成', `异常 ${result.remote_errors ?? 0} 条`];
    parts.push(`刷新入队 ${result.refresh_queued ?? 0}`, `同步入队 ${result.sync_queued ?? 0}`);
    const reasonEntries = Array.isArray(result.reasons)
      ? rows(result.reasons)
      : Object.entries(record(result.reasons)).map(([code, count]) => ({code, count}));
    const reasons = reasonEntries.flatMap(({code, count}) => {
      if (typeof code !== 'string' || !/^[a-z0-9_.-]{1,100}$/i.test(code) || !Number.isSafeInteger(count) || Number(count) <= 0) return [];
      const label = shortErrorLabel({cause_code: code});
      return [`${label === shortErrorLabel() ? code : label} ${count}`];
    });
    if (reasons.length) parts.push(reasons.join('、'));
    return parts.join(' · ');
  }
  if (task.task_type === 'sub2api_scan') return status === 'success' ? 'Sub2API 异常扫描已完成' : result.error_code || result.message || '扫描未完成，请查看任务日志';
  return Object.keys(result).length ? JSON.stringify(result) : '-';
}

export function resultText(task: OperationTask, compact = false): string {
  return String(resultValue(task, compact));
}

/** 失败步骤优先使用诊断证据，保留历史 MFA 归因纠正。 */
export function failureStageText(task: OperationTask): string {
  if (isActive(task)) return '';
  const summary = record(task.result_summary), diagnostics = record(summary.auth_diagnostics);
  const reported = String(task.failure_stage || summary.failure_stage || '');
  const operation = diagnostics.operation === 'password_email_fallback' ? diagnostics.cause_operation : diagnostics.operation;
  const mfa = ['token_refresh', 'live_check'].includes(task.task_type) && task.status !== 'success'
    && ['login_password', 'email_otp'].includes(reported) && ['mfa_verify', 'mfa_issue_challenge'].includes(String(operation));
  const classified = task.error_info?.stage;
  const stage = mfa ? 'mfa_challenge' : classified && !['unknown','complete','result','event','queued'].includes(classified) ? classified : reported;
  if (!stage) return '';
  const title = stage === reported && task.failure_stage_label ? task.failure_stage_label : label('stage', stage.replace(/_result$/, ''));
  return `失败于 ${title}`;
}

function promotionDetail(item: Record<string, unknown>): string {
  const parts = [`${item.plan === 'go' ? 'Go' : 'Plus'}: ${promotionLabel(item)}`];
  if (!['free_trial', 'discount', 'other_promo'].includes(String(item.kind))) return parts.join('；');
  const status = String(item.checkout_status || '');
  const country = String(item.country || '').toUpperCase(), checkoutCountry = String(item.checkout_country || '').toUpperCase();
  if (country && checkoutCountry && country !== checkoutCountry) return `${parts[0]}；支付方式: 待查询`;
  if (['failed', 'skipped'].includes(status)) {
    const error = String(item.checkout_error || '').replace(/https?:\/\/[^\s；，]+/gi, '[链接已隐藏]')
      .replace(/\b(?:cs_(?:live|test)|oaics|(?:pk|sk)_(?:live|test))_[a-z0-9_-]+\b/gi, '[结账标识已隐藏]')
      .replace(/\b[^\s；，]*secret[^\s；，]*\b/gi, '[凭据已隐藏]').slice(0, 240).trim();
    const http = Number(item.checkout_http_status);
    parts.push(status === 'failed' ? '支付方式查询失败' : '支付方式待查询');
    if (error || http >= 100 && http <= 599) parts.push(error || `HTTP ${http}`);
    return parts.join('；');
  }
  const methods = Array.isArray(item.payment_method_types) ? item.payment_method_types : [];
  const methodLabels: Record<string, string> = {card: '银行卡', link: 'Link', upi: 'UPI'};
  const safeMethods = [...new Set(methods.filter((value): value is string => typeof value === 'string').map(value => value.trim().toLowerCase())
    .filter(value => /^[a-z][a-z0-9_-]{0,63}$/.test(value) && !/^(?:cs_(?:live|test)|oaics|(?:pk|sk)_(?:live|test))(?:_|$)/.test(value) && !value.includes('secret'))
    .map(value => methodLabels[value] || value))];
  const amount = item.checkout_amount_due_minor, exponent = item.checkout_currency_exponent, currency = String(item.checkout_currency || '').toUpperCase();
  if (status === 'success' && typeof amount === 'number' && Number.isSafeInteger(amount) && amount >= 0 && typeof exponent === 'number' && Number.isInteger(exponent) && exponent >= 0 && exponent <= 3 && /^[A-Z]{3}$/.test(currency)) {
    const digits = String(amount).padStart(exponent + 1, '0');
    parts.push(`实际应付: ${exponent ? `${digits.slice(0, -exponent)}.${digits.slice(-exponent)}`.replace(/\.?0+$/, '') : digits} ${currency}`);
  }
  if (status === 'success' && ['cs_live', 'oaics'].includes(String(item.session_type))) parts.push(`结账会话: ${item.session_type}`);
  parts.push(`支付方式: ${safeMethods.join(' ') || (status === 'success' ? '未返回' : '待查询')}`);
  return parts.join('；');
}
/** 列表展开保留全部国家与优惠证据，摘要不会代替诊断详情。 */
export function resultDetails(task: OperationTask): string {
  if (task.task_type !== 'plan_check') return resultText(task);
  const r = record(task.result_summary);
  const parts = [resultText(task), ...rows(r.country_failures).map(item => `${item.country}：${item.summary || '诊断记录不完整'}`)];
  const disabled = Array.isArray(r.plan_check_countries) && !r.plan_check_countries.length;
  const countries = disabled ? [] : rows(r.plan_check_country_results).filter(item => item.country);
  if (!countries.length) {
    const groups = countryPromotionGroups(r);
    if (groups.length) parts.push(...groups.map(group => [
      `${group.country}${group.items.some(item => item.stale) ? '（历史）' : ''}`,
      ...group.items.map(promotionDetail),
    ].join('\n')));
    else parts.push(...promotions(r).map(promotionDetail));
  }
  for (const country of countries) {
    const snapshot = record(country.result), hasSnapshot = Object.keys(snapshot).length > 0 && !!country.last_success_at;
    const stale = country.status !== 'success' && hasSnapshot || ['queued', 'running'].includes(String(task.status));
    const context = [`${String(country.country).toUpperCase()}${stale ? '（历史）' : ''}`];
    if (country.status === 'success' || hasSnapshot) context.push(...promotions(snapshot).map(item => promotionDetail({...item, country: country.country})));
    else context.push(label('status', country.status));
    if (country.error || country.http_status) context.push(`本次查询${country.status === 'cancelled' ? '取消' : '失败'}: ${country.error || `HTTP ${country.http_status}`}`);
    if (country.checked_at) context.push(`查询于 ${formatDateTime(country.checked_at)}`);
    if (hasSnapshot && stale) context.push(`显示上次成功快照；上次成功查询: ${formatDateTime(country.last_success_at)}`);
    parts.push(context.join('\n'));
  }
  return parts.filter(Boolean).join('\n');
}
