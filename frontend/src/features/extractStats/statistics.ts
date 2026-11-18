import {request} from '../../api/client';

export const ranges = [7, 30, 90] as const;
export type RangeDays = typeof ranges[number];
type Metric = 'total' | 'extracted' | 'paid' | 'plus_confirmed' | 'failed' | 'processing'
  | 'awaiting_payment' | 'needs_review' | 'extraction_failed' | 'payment_failed'
  | 'extraction_rate' | 'payment_rate' | 'avg_seconds';
export type Metrics = Partial<Record<Metric, number | null>>;
export type Daily = Metrics & {date: string};
export interface Statistics {
  date_from?: string;
  date_to?: string;
  generated_at?: string;
  totals: Metrics;
  current?: Metrics;
  daily: Daily[];
  providers?: (Metrics & {provider_id: string})[];
  failures?: {code?: string; label?: string; count: number}[];
  modes?: (Metrics & {mode: string})[];
}
export interface StatsDependencies {
  visible?: boolean;
  onReady?: () => void;
}

export function analyticsURL(days: RangeDays, provider: string) {
  const params = new URLSearchParams({days: String(days)});
  if (provider) params.set('provider_id', provider);
  return `/api/extract-workbench/analytics?${params}`;
}
function isRow(value: unknown) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function optionalRows<T>(value: T[] | undefined): T[] {
  return Array.isArray(value) ? value.filter(isRow) : [];
}
export async function readStatistics(days: RangeDays, provider: string, signal: AbortSignal): Promise<Statistics> {
  const data = await request<Statistics>(analyticsURL(days, provider), {method: 'GET', signal});
  if (!isRow(data?.totals) || !Array.isArray(data.daily) || !data.daily.every(isRow)) {
    throw new Error('统计响应格式不完整');
  }
  return {
    ...data,
    providers: optionalRows(data.providers),
    failures: optionalRows(data.failures),
    modes: optionalRows(data.modes),
  };
}
export const providerLabels = new Map([
  ['legacy', '虾扯蛋链'], ['lumen_flow', 'Lumen Flow'], ['huanguang', '幻光提链'], ['anguang', '暗光（XXSYUN 一条龙）'],
]);
export function providerLabel(id: string) {
  return providerLabels.get(id === 'lumen' ? 'lumen_flow' : id) ?? (id || '未记录平台');
}
const modeLabels = new Map([['extract_only','仅提链'], ['manual_payment','手动支付'], ['auto_payment','自动支付']]);
export function modeLabel(id: string) { return modeLabels.get(id) ?? (id || '未记录模式'); }
export function count(value: unknown) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : 0;
}
const numbers = new Intl.NumberFormat('zh-CN');
export function number(value: unknown) { return numbers.format(count(value)); }
function validMeasure(value: unknown) {
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0;
}
export function rate(value: unknown) {
  return validMeasure(value) && Number(value) <= 1 ? `${(Number(value) * 100).toFixed(1)}%` : '—';
}
export function duration(value: unknown) {
  if (!validMeasure(value)) return '—';
  const seconds = Math.round(Number(value));
  if (seconds < 60) return `${seconds} 秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
  return `${Math.floor(seconds / 3600)} 小时 ${Math.floor(seconds % 3600 / 60)} 分`;
}
const beijingClock = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
});
export function updatedAt(value?: string) {
  const stamp = Date.parse(value ?? '');
  return Number.isFinite(stamp) ? `更新于 ${beijingClock.format(stamp)}` : '统计已更新';
}
