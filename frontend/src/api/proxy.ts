import { isAbort, request } from './client';
import type {
  ProxyPage,
  ProxyPoolSnapshot,
  ProxyRecordView,
  ProxySummary,
  ProxyTrafficApi,
} from '../features/proxy/contracts';
// JSON.parse rounds bigint IDs before Vue can format them. Consume whole JSON strings
// (including escapes) so numbers in labels and URLs are never rewritten.
const integerIds = new Set([
  'id',
  'account_id',
  'operation_task_id',
  'operation_run_id',
  'registration_job_id',
  'registration_attempt_id',
  'registration_run_id',
]);
function parseProxyPage(text: string): unknown {
  const tokens = /("(?:[^"\\]|\\.)*")(?:(\s*:\s*)(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?))?/g;
  const exact = text.replace(tokens, (match: string, key: string, colon?: string, numeric?: string) => {
    if (!colon || !numeric || !/^\d+$/.test(numeric) || Number.isSafeInteger(Number(numeric))) return match;
    return integerIds.has(JSON.parse(key)) ? key + colon + JSON.stringify(numeric) : match;
  });
  return JSON.parse(exact);
}
const paths = {
  current: '/api/proxy-traffic/current',
  history: '/api/proxy-traffic/history',
  traffic: '/api/proxy-traffic/traffic',
};
export function normalizeProxyPage(view: ProxyRecordView, value: unknown): ProxyPage {
  const payload = value as Record<string, unknown> | null;
  if (!payload || typeof payload !== 'object' || payload.ok !== true) throw new Error('代理列表接口响应无效');
  if (payload.view != null && payload.view !== view) throw new Error('代理列表接口视图不匹配');
  if (!Array.isArray(payload.items)) throw new Error('代理列表接口缺少 items');
  const count = Number(payload.count),
    total = Number(payload.total),
    limit = Number(payload.limit),
    offset = Number(payload.offset);
  if (
    !Number.isInteger(count) ||
    count < 0 ||
    count !== payload.items.length ||
    !Number.isInteger(total) ||
    total < count ||
    !Number.isInteger(limit) ||
    limit < 1 ||
    !Number.isInteger(offset) ||
    offset < 0
  )
    throw new Error('代理列表分页字段无效');
  return {
    items: payload.items,
    count,
    total,
    limit,
    offset,
    has_more: typeof payload.has_more === 'boolean' ? payload.has_more : offset + count < total,
    aggregate: payload.aggregate as ProxyPage['aggregate'],
  };
}
export function createProxyApi(): ProxyTrafficApi {
  return {
    async page(view, query, signal) {
      const params = new URLSearchParams({
        limit: String(query.size),
        offset: String((query.page - 1) * query.size),
        window: query.window,
        purpose: view === 'traffic' ? 'all' : query.purpose,
        state: query.state,
        search: query.search.trim(),
      });
      return normalizeProxyPage(view, await request(paths[view] + '?' + params, { signal }, parseProxyPage));
    },
    async summary(signal) {
      const payload = await request<ProxySummary>('/api/proxy-traffic/summary', { signal });
      if (
        payload?.ok !== true ||
        !Number.isFinite(Number(payload.total_bytes)) ||
        !Number.isFinite(Number(payload.today_bytes))
      )
        throw new Error('流量统计接口响应无效');
      return payload;
    },
    async pool(signal) {
      try {
        const payload = await request<ProxyPoolSnapshot>('/api/proxy-pool', { signal });
        return payload?.ok === true && payload.policy && payload.counts && typeof payload.counts === 'object'
          ? {
              ...payload,
              items: Array.isArray(payload.items) ? payload.items : [],
              country_pools: Array.isArray(payload.country_pools) ? payload.country_pools : [],
            }
          : null;
      } catch (error) {
        if (isAbort(error)) throw error;
        return null;
      }
    },
  };
}
