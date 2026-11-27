import type {components} from './accounts-schema';
import {ApiError, request} from './client';
import type {AccountQueryAdapter, AccountQuerySpec} from '../features/accounts/queryAdapter';

export type AccountTeamMembershipItem = components['schemas']['AccountTeamMembership'];
export type AccountRow = components['schemas']['AccountRow'];
export type AccountStatusRow = components['schemas']['AccountStatusRow'];
export type AccountFacets = components['schemas']['AccountFacets'];
export type AccountSearchTerm = components['schemas']['AccountSearchTerm'];
export type AccountsListResponse = components['schemas']['AccountsListResponse'];
export type AccountStatusesResponse = components['schemas']['AccountStatusesResponse'];
export type AccountPlanDetails = components['schemas']['AccountPlanDetails'];
export type AccountPlanDetailsResponse = components['schemas']['AccountPlanDetailsResponse'];
export type AccountQueueSettings = components['schemas']['AccountQueueSettings'];
export interface AccountsReadApi {
  list(query: AccountQuerySpec, page: number, size: number, signal?: AbortSignal,
    options?: {includeFacets?: boolean}): Promise<AccountsListResponse>;
  statuses(query: AccountQuerySpec, page: number, size: number, signal?: AbortSignal): Promise<AccountStatusesResponse>;
  planDetails(accountId: string, signal?: AbortSignal): Promise<AccountPlanDetailsResponse>;
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function integer(value: unknown, minimum: number): boolean {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum;
}
function pageEnvelope(value: unknown): value is Record<string, unknown> {
  return record(value) && value.ok === true && Array.isArray(value.items)
    && integer(value.total, 0) && integer(value.page, 1) && integer(value.page_size, 1)
    && integer(value.offset, 0) && integer(value.limit, 1) && typeof value.revision === 'string';
}
function malformed(): never {
  throw new ApiError('账号查询返回了无效的响应，请刷新后重试。', 200, 'account_response_invalid');
}

/** Validate the envelope only; never rewrite optional row projections or unknown enums. */
export function createAccountsApi(query: AccountQueryAdapter): AccountsReadApi {
  return {
    async list(spec, page, size, signal, options) {
      const params = query.toLegacy(spec, {paged: '1', page, page_size: size});
      if (options?.includeFacets === false) params.set('include_facets', '0');
      const payload = await request<unknown>(`/api/accounts?${params}`, {signal});
      if (!pageEnvelope(payload) || payload.compact !== true || !record(payload.facets)
        || !Array.isArray(payload.search_terms)) malformed();
      return payload as AccountsListResponse;
    },
    async statuses(spec, page, size, signal) {
      const params = query.toLegacy(spec, {paged: '1', page, page_size: size});
      params.set('compact', '1');
      const payload = await request<unknown>(`/api/accounts/plan-check-status?${params}`, {signal});
      if (!pageEnvelope(payload) || !record(payload.queue) || !Array.isArray(payload.status_fields)
        || !payload.status_fields.every(field => typeof field === 'string')) malformed();
      return payload as AccountStatusesResponse;
    },
    async planDetails(accountId, signal) {
      if (!/^[1-9]\d*$/.test(accountId)) throw new Error('账号 ID 无效');
      const payload = await request<unknown>(`/api/accounts/${encodeURIComponent(accountId)}/plan-details`, {signal});
      if (!record(payload) || payload.ok !== true || !record(payload.item)
        || !Object.hasOwn(payload.item, 'account_promotions')
        || !Object.hasOwn(payload.item, 'promotion_query_snapshot')
        || !Array.isArray(payload.item.plan_check_country_results)) malformed();
      return payload as AccountPlanDetailsResponse;
    },
  };
}
