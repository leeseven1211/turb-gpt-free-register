import type {BulkRecord} from './contracts';
export const operationNames: Record<string, string> = {
  plan_check: '查套餐',
  token_refresh: '刷新 AT',
  password_setup: '补密码',
  twofa_setup: '补 2FA',
  codex_retry: '补 Codex',
  account_completion: '组合补全',
};
export const object = (value: unknown): BulkRecord =>
  value !== null && typeof value === 'object' && !Array.isArray(value) ? (value as BulkRecord) : {};
export const rows = (value: unknown): BulkRecord[] => (Array.isArray(value) ? value.map(object) : []);
export const operationLabel = (value: unknown): string =>
  operationNames[String(value)] || String(value || '—');
export function numeric(value: unknown): number | null {
  if (typeof value !== 'number' && (typeof value !== 'string' || !value.trim())) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}
export const number = (value: unknown): string =>
  numeric(value) === null ? '—' : Math.floor(Number(value)).toLocaleString('zh-CN');
export function duration(value: unknown): string {
  const seconds = numeric(value);
  if (seconds === null) return '—';
  if (seconds < 60)
    return `${seconds === 0 ? '0' : seconds < 1 ? seconds.toFixed(2) : seconds.toFixed(1).replace(/\.0$/, '')} 秒`;
  const rounded = Math.round(seconds),
    hours = Math.floor(rounded / 3600),
    minutes = Math.floor((rounded % 3600) / 60),
    rest = rounded % 60;
  return (
    [hours ? `${hours} 小时` : '', minutes ? `${minutes} 分` : '', rest ? `${rest} 秒` : '']
      .filter(Boolean)
      .join(' ') || '0 秒'
  );
}
export function scopeText(report: BulkRecord): string {
  const view = object(report.view);
  if (view.kind !== 'round') return '当前结果 · 每个账号取最近一轮';
  const round = numeric(view.round_no);
  if (round === null || !Number.isSafeInteger(round) || round < 1) return '所选轮次 · 固定名单';
  return round === 1 ? '首轮名单' : `重跑 ${round - 1} · 固定名单`;
}
const planNames: Record<string, string> = {
  free: 'Free',
  plus: 'Plus',
  pro: 'Pro',
  team: 'Team',
  business: 'Business',
  enterprise: 'Enterprise',
  go: 'Go',
  unknown: '尚未确认',
};
const offerNames: Record<string, string> = {
  free_trial: '免费试用',
  half_price: '半价优惠',
  discount: '折扣优惠',
  other_discount: '其他折扣',
  other_promo: '其他优惠',
};
function nameOf(labels: Record<string, string>, value: unknown, fallback: string): string {
  const key = typeof value === 'string' ? value : '';
  return Object.hasOwn(labels, key) ? labels[key] : key || fallback;
}
export const planName = (value: unknown) => nameOf(planNames, value, '尚未确认');
export const offerName = (value: unknown) => nameOf(offerNames, value, '其他优惠');
export function railWidth(value: unknown, max: number) {
  return `${Math.max(0, Math.min(100, max > 0 ? ((numeric(value) || 0) / max) * 100 : 0))}%`;
}
export interface BusinessGroup {
  title: string;
  items: {title: string; value: number; unit: '项' | '个'}[];
}
const names: Record<string, string> = {
  'account.confirmed_no_offer': '本次确认无优惠',
  'account.plan.free': '套餐 · Free',
  'account.plan.plus': '套餐 · Plus',
  'account.plan.pro': '套餐 · Pro',
  'account.plan.team': '套餐 · Team',
  'account.plan.go': '套餐 · Go',
  confirmed_no_offer_accounts: '本次确认无优惠',
  no_offer: '无优惠',
  free_trial: '免费试用',
  half_price: '半价优惠',
  other_discount: '其他折扣',
  success: '成功',
  failed: '失败',
  partial_success: '部分成功',
  confirmed: '已确认',
  newly_set: '新设置',
  already_set: '验证已有密码',
  newly_enabled: '新启用',
  already_satisfied: '原本已满足',
  usable_credential: '可用凭证',
  credential_pending_confirmation: '凭证缺失',
  confirmed_accounts: '已确认账号',
  country_success: '查询成功',
  country_failed: '查询失败',
  'country_query.success': '国家项查询成功',
  'country_query.failed': '国家项查询失败',
  plan: '套餐',
  plans: '套餐分布',
  promotion: '优惠',
  promotions: '优惠分布',
  countries: '国家项',
  password: '密码',
  twofa: '2FA',
  codex: 'Codex',
  access_token: 'AT',
  plan_check: '套餐查询',
  free: 'Free',
  plus: 'Plus',
  team: 'Team',
  pro: 'Pro',
  unknown: '记录缺失',
  none: '无优惠',
  not_executed: '未执行',
  attention_required: '失败',
  pending: '待执行',
  'account.password_setup.confirmed': '密码已确认',
  'account.twofa_setup.confirmed': '2FA 已确认',
  'account.codex.credential_confirmed': 'Codex 凭证已确认',
  'account.token_refresh.confirmed': 'AT 刷新成功',
  'account.token_refresh.failed': 'AT 刷新失败',
};
for (const [kind, name] of Object.entries({none: '无优惠', ...offerNames}))
  names[`account.plus_offer.${kind}`] = `优惠 · ${name}`;
for (const [kind, name] of Object.entries({
  unchanged: '优惠未变化',
  new_offer: '新增优惠',
  offer_removed: '优惠消失',
  changed: '优惠变化',
  not_comparable: '历史条件不可比较',
}))
  names[`account.comparison.${kind}`] = name;
for (const [step, name] of Object.entries({
  password: '密码',
  twofa: '2FA',
  codex: 'Codex',
  access_token: 'AT',
  plan_check: '套餐',
})) {
  names[`step.${step}.confirmed`] = `${name} · 已完成`;
  names[`step.${step}.pending`] = `${name} · 待完成`;
}

export function businessGroups(value: unknown): BusinessGroup[] {
  const metrics = {...object(value)};
  if (Object.hasOwn(metrics, 'account.token_refresh.unconfirmed')) {
    metrics['account.token_refresh.failed'] =
      (numeric(metrics['account.token_refresh.failed']) || 0) +
      (numeric(metrics['account.token_refresh.unconfirmed']) || 0);
    delete metrics['account.token_refresh.unconfirmed'];
  }
  const groups = new Map<string, BusinessGroup>();
  function walk(source: BulkRecord, prefix = '', depth = 0) {
    if (depth > 3) return;
    for (const [key, item] of Object.entries(source)) {
      if (['schema', 'schema_version', 'version', 'updated_at'].includes(key)) continue;
      const name = nameOf(names, key, key);
      const title = prefix ? `${prefix} · ${name}` : name;
      if (typeof item === 'number') {
        const group =
          key.startsWith('country_query.') || key.startsWith('country_')
            ? '国家查询项'
            : key.startsWith('account.plan.')
              ? '套餐分布'
              : key.startsWith('account.plus_offer.') ||
                  key.startsWith('account.comparison.') ||
                  key === 'account.confirmed_no_offer'
                ? '优惠结果'
                : key.startsWith('step.')
                  ? '补全项目'
                  : '执行结果';
        if (!groups.has(group)) groups.set(group, {title: group, items: []});
        groups.get(group)!.items.push({title, value: item, unit: group === '国家查询项' ? '项' : '个'});
      } else if (item && typeof item === 'object') walk(object(item), title, depth + 1);
    }
  }
  walk(metrics);
  return [...groups.values()];
}
