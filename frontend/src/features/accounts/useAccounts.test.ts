// @vitest-environment jsdom
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';
import {effectScope, nextTick} from 'vue';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import type {AccountFacets, AccountPlanDetailsResponse, AccountRow, AccountSearchTerm,
  AccountStatusRow, AccountStatusesResponse, AccountsListResponse, AccountsReadApi} from '../../api/accounts';
import {ApiError} from '../../api/client';
import {createAccountQueryAdapter, type AccountQueryAdapter, type AccountQuerySpec} from './queryAdapter';
import {useAccounts} from './useAccounts';

const querySource = readFileSync(resolve(process.cwd(), '../webui/static/js/shared/account-query.js'), 'utf8');
const scopes: ReturnType<typeof effectScope>[] = [];
function realQueryAdapter() {
  const sandbox = {window: {} as {AccountQuery: AccountQueryAdapter}, URLSearchParams,
    accountListQueryParams() { throw new Error('controller 不得从旧 DOM 重读查询'); }};
  runInNewContext(querySource, sandbox, {filename: 'account-query.js'});
  return createAccountQueryAdapter(sandbox.window.AccountQuery);
}
function row(id: number, fields: Partial<AccountRow> = {}): AccountRow {
  return {id, email: `account-${id}@example.test`, has_access_token: false,
    has_account_password: false, totp_enabled: false, email_invalid: false,
    email_invalid_at: null, email_invalid_reason: null, email_invalid_source: null,
    plus_promo_kind: '', plus_promo_eligible: false, plus_trial_eligible: false,
    plus_discount_eligible: false, ...fields};
}
function statusRow(id: number, fields: Partial<AccountStatusRow> = {}): AccountStatusRow {
  return {id, email: `account-${id}@example.test`, has_access_token: false,
    has_account_password: false, email_invalid: false, email_invalid_at: null,
    email_invalid_reason: null, email_invalid_source: null, last_password_auth_status: null,
    plan_promotion_country: null, plan_details_revision: 'v1',
    plan_summary: {promotions: null, countries: []}, ...fields};
}
function listResult(items: AccountRow[] = [row(1), row(2)], options: {
  total?: number; page?: number; size?: number; revision?: string;
  facets?: AccountFacets; terms?: AccountSearchTerm[];
} = {}): AccountsListResponse {
  const {total = items.length, page = 1, size = 10, revision = 'list-1', facets = {}, terms = []} = options;
  return {ok: true, compact: true, items, total, page, page_size: size,
    offset: (page - 1) * size, limit: size, revision, facets, search_terms: terms};
}
function statusResult(items: AccountStatusRow[] = [statusRow(1), statusRow(2)], options: {
  total?: number; page?: number; size?: number; revision?: string; fields?: string[];
} = {}): AccountStatusesResponse {
  const {total = items.length, page = 1, size = 10, revision = 'status-1', fields = []} = options;
  return {ok: true, items, total, page, page_size: size, offset: (page - 1) * size,
    limit: size, revision, status_fields: fields,
    queue: {workers: 1, registration_workers: 1, queue_limit: 100, min_interval: 0, jitter: 0}};
}
function detailsResult(title: string): AccountPlanDetailsResponse {
  return {ok: true, item: {account_promotions: [{plan: 'plus', title}],
    promotion_query_snapshot: null, plan_check_country_results: []}};
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return {promise, resolve, reject};
}
async function settle() {
  await nextTick();
  for (let index = 0; index < 16; index++) await Promise.resolve();
  await nextTick();
}
function documentHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', {configurable: true, value: hidden});
  document.dispatchEvent(new Event('visibilitychange'));
}
type ReadCall = {query: AccountQuerySpec; page: number; size: number;
  params: Record<string, string>; signal?: AbortSignal; includeFacets?: boolean};
type DetailsCall = {id: string; signal?: AbortSignal};
function setup() {
  const adapter = realQueryAdapter();
  const listCalls: ReadCall[] = [];
  const statusCalls: ReadCall[] = [];
  const detailsCalls: DetailsCall[] = [];
  const handlers = {
    list: async (call: ReadCall): Promise<AccountsListResponse> => listResult([row(1), row(2)], {page: call.page, size: call.size}),
    statuses: async (call: ReadCall): Promise<AccountStatusesResponse> => statusResult(undefined, {page: call.page, size: call.size}),
    details: async (_call: DetailsCall): Promise<AccountPlanDetailsResponse> => detailsResult('full-details'),
  };
  function readCall(query: AccountQuerySpec, page: number, size: number, signal?: AbortSignal): ReadCall {
    return {query, page, size, signal,
      params: Object.fromEntries(adapter.toLegacy(query, {paged: '1', page, page_size: size}))};
  }
  const api: AccountsReadApi = {
    list(query, page, size, signal, options) {
      const call = {...readCall(query, page, size, signal), includeFacets: options?.includeFacets ?? true};
      listCalls.push(call); return handlers.list(call);
    },
    statuses(query, page, size, signal) {
      const call = readCall(query, page, size, signal); statusCalls.push(call); return handlers.statuses(call);
    },
    planDetails(id, signal) {
      const call = {id, signal}; detailsCalls.push(call); return handlers.details(call);
    },
  };
  const scope = effectScope(); scopes.push(scope);
  const owner = scope.run(() => useAccounts(adapter, api))!;
  return {owner, adapter, scope, handlers, listCalls, statusCalls, detailsCalls};
}
beforeEach(() => {
  vi.useFakeTimers();
  Object.defineProperty(document, 'hidden', {configurable: true, value: false});
});
afterEach(() => {
  scopes.forEach(scope => scope.stop()); scopes.length = 0;
  vi.useRealTimers(); vi.restoreAllMocks();
});

describe('Accounts owner 分页和选择身份', () => {
  it('初次显示只读第 1 页的 20 条，重复显示不重复读，也不隐式取详情', async () => {
    const h = setup(); await h.owner.refresh(); await settle();
    expect(h.listCalls).toHaveLength(0);
    h.owner.setVisible(true); h.owner.setVisible(true); await settle();
    expect(h.listCalls).toHaveLength(1);
    expect(h.listCalls[0]!.params).toMatchObject({paged: '1', page: '1', page_size: '20', archived: '0'});
    expect(h.listCalls[0]!.params).not.toHaveProperty('limit');
    expect(h.owner.page.value).toBe(1); expect(h.owner.size.value).toBe(20);
    expect(h.detailsCalls).toHaveLength(0);
  });

  it('同条件翻页和改每页条数复用短期筛选统计，数据行和总数仍实时获取', async () => {
    const h = setup();
    const sampleFacets = {source: [{value: 'outlook', count: 60}]};
    h.handlers.list = async call => listResult(call.page === 1 ? [row(1)] : [row(2)], {
      total: call.page === 1 ? 60 : 59, page: call.page, size: call.size,
      facets: call.includeFacets ? sampleFacets : {},
    });
    h.owner.setVisible(true); await settle();
    expect(h.listCalls.at(-1)?.includeFacets).toBe(true);
    h.owner.setPage(2); await settle();
    expect(h.listCalls.at(-1)?.includeFacets).toBe(false);
    expect(h.owner.items.value[0]?.id).toBe(2);
    expect(h.owner.total.value).toBe(59);
    expect(h.owner.facets.value).toEqual(sampleFacets);
    h.owner.setSize(30); await settle();
    expect(h.listCalls.at(-1)).toMatchObject({page: 1, size: 30, includeFacets: false});
    vi.setSystemTime(Date.now() + 30001);
    h.owner.setPage(2); await settle();
    expect(h.listCalls.at(-1)?.includeFacets).toBe(true);
    await h.owner.refresh();
    expect(h.listCalls.at(-1)?.includeFacets).toBe(true);
    h.owner.setArchived(true); await settle();
    expect(h.listCalls.at(-1)?.includeFacets).toBe(true);
  });

  it('页选只改变当前页，跨页选择经刷新和 size 变更保留', async () => {
    const h = setup();
    h.handlers.list = async call => listResult(call.page === 1 ? [row(1), row(2)] : [row(11), row(12)],
      {page: call.page, size: call.size, total: 60});
    h.owner.setVisible(true); await settle(); h.owner.togglePage(true);
    expect(h.owner.pageSelected.value).toBe(true); expect(h.owner.pageIndeterminate.value).toBe(false);
    h.owner.setPage(2); await settle(); h.owner.togglePage(true); h.owner.toggle('11', false);
    expect(h.owner.pageSelected.value).toBe(false); expect(h.owner.pageIndeterminate.value).toBe(true);
    expect([...h.owner.selected.value].sort()).toEqual(['1', '12', '2']);
    h.owner.togglePage(false); expect([...h.owner.selected.value].sort()).toEqual(['1', '2']);
    await h.owner.refresh(); expect([...h.owner.selected.value].sort()).toEqual(['1', '2']);
    h.owner.setSize(30); await settle();
    expect(h.owner.page.value).toBe(1); expect(h.owner.size.value).toBe(30);
    expect([...h.owner.selected.value].sort()).toEqual(['1', '2']);
    expect(h.owner.getAccountSelectionSnapshot({requireEmails: true}).expectedEmails).toEqual({
      '1': 'account-1@example.test', '2': 'account-2@example.test'});
  });

  it('快照优先当前页最新邮箱，离页保留选中时邮箱，确认期间变化不能改动快照', async () => {
    const h = setup(); let currentEmail = 'selected@example.test';
    h.handlers.list = async call => listResult(call.page === 1 ? [row(1, {email: currentEmail})] : [row(11)],
      {page: call.page, size: call.size, total: 21});
    h.owner.setVisible(true); await settle(); h.owner.toggle('1', true);
    h.owner.setPage(2); await settle(); h.owner.toggle('11', true);
    expect(h.owner.getAccountSelectionSnapshot({requireEmails: true}).expectedEmails).toEqual({
      '1': 'selected@example.test', '11': 'account-11@example.test'});
    h.owner.setPage(1); await settle(); currentEmail = 'latest@example.test'; await h.owner.refresh();
    const snapshot = h.owner.getAccountSelectionSnapshot({requireEmails: true});
    expect(snapshot.ids).toEqual(['1', '11']);
    expect(snapshot.expectedEmails).toEqual({'1': 'latest@example.test', '11': 'account-11@example.test'});
    expect(snapshot.source).toBe('accounts');
    expect(Object.isFrozen(snapshot)).toBe(true); expect(Object.isFrozen(snapshot.ids)).toBe(true);
    expect(Object.isFrozen(snapshot.expectedEmails)).toBe(true); expect(Object.isFrozen(snapshot.query)).toBe(true);
    expect(Object.isFrozen(snapshot.query.filters)).toBe(true); expect(Object.isFrozen(snapshot.query.plan)).toBe(true);
    expect(Object.isFrozen(snapshot.query.filters.source)).toBe(true);
    h.owner.setPage(2); await settle(); h.owner.clearSelection();
    h.owner.commitQuery(h.adapter.normalize({q: 'name:changed', filters: {email: 'new@example.test'}})); await settle();
    currentEmail = 'rebound@example.test';
    expect(snapshot.ids).toEqual(['1', '11']);
    expect(snapshot.expectedEmails).toEqual({'1': 'latest@example.test', '11': 'account-11@example.test'});
    expect(snapshot.query.q).toBe(''); expect(snapshot.query.filters.email).toBe('');
  });

  it('清选及确认移除同时删除邮箱记忆，单行动作仍可从当前页建立邮箱快照', async () => {
    const h = setup();
    h.handlers.list = async call => listResult(call.page === 1 ? [row(1), row(2)] : [row(11)], {page: call.page, total: 21});
    h.owner.setVisible(true); await settle(); h.owner.togglePage(true);
    const single = h.owner.getAccountSelectionSnapshot({ids: ['2'], requireEmails: true});
    expect(single.ids).toEqual(['2']); expect(single.expectedEmails).toEqual({'2': 'account-2@example.test'});
    h.owner.removeAcknowledgedSelection(['1']); h.owner.setPage(2); await settle();
    expect([...h.owner.selected.value]).toEqual(['2']);
    expect(() => h.owner.getAccountSelectionSnapshot({ids: ['1'], requireEmails: true})).toThrow();
    h.owner.clearSelection();
    expect(h.owner.selectedEmails.value).toEqual({});
    expect(h.owner.getAccountSelectionSnapshot().expectedEmails).toEqual({});
    expect(() => h.owner.getAccountSelectionSnapshot({ids: ['2'], requireEmails: true})).toThrow();
  });

  it('邮箱动作缺少映射或超过 500 个唯一 ID 时在读取外部动作前失败', async () => {
    const h = setup(); h.handlers.list = async () => listResult([row(1, {email: null})]);
    h.owner.setVisible(true); await settle(); h.owner.toggle('1', true);
    expect(() => h.owner.getAccountSelectionSnapshot({requireEmails: true})).toThrow();
    expect(() => h.owner.getAccountSelectionSnapshot({ids: Array.from({length: 501}, (_, index) => String(index + 1)), requireEmails: true})).toThrow(/500/);
    expect(h.detailsCalls).toHaveLength(0);
  });

  it.each([null, ''])('当前页邮箱已清为 %s 时不回退选中时旧邮箱', async email => {
    const h = setup(); let currentEmail: string | null = 'old@example.test';
    h.handlers.list = async () => listResult([row(1, {email: currentEmail})]);
    h.owner.setVisible(true); await settle(); h.owner.toggle('1', true);
    const frozen = h.owner.getAccountSelectionSnapshot({requireEmails: true});
    currentEmail = email; await h.owner.refresh();
    expect(() => h.owner.getAccountSelectionSnapshot({requireEmails: true})).toThrow();
    expect(() => h.owner.getAccountSelectionSnapshot({ids: ['1'], requireEmails: true})).toThrow();
    expect(frozen.expectedEmails).toEqual({'1': 'old@example.test'});
  });

  it('动作 context 是独立冻结数据，后续列表更新不改账号和公开 rowHints', async () => {
    const h = setup(); h.owner.setVisible(true); await settle(); h.owner.toggle('1', true);
    const context = h.owner.getActionContext({requireEmails: true});
    expect(context.accountIds).toEqual(['1']);
    expect(context.expectedEmails).toEqual({'1': 'account-1@example.test'});
    expect(context.querySnapshot.q).toBe(''); expect(context.archived).toBe('0');
    expect(context.rowHints[0]?.id).toBe(1);
    expect(Object.isFrozen(context)).toBe(true); expect(Object.isFrozen(context.rowHints)).toBe(true);
    expect(Object.isFrozen(context.rowHints[0])).toBe(true);
    expect(context.rowHints[0]).not.toBe(h.owner.items.value[0]);
    h.handlers.list = async () => listResult([row(1, {email: 'rebound@example.test'})]); await h.owner.refresh();
    expect(context.rowHints[0]?.email).toBe('account-1@example.test');
    expect(context.expectedEmails).toEqual({'1': 'account-1@example.test'});
  });
});

describe('Accounts owner 查询与列表竞态', () => {
  it.each([
    ['q', {q: '备注:"a/b 待整理"'}], ['id', {filters: {id: '#1,11'}}],
    ['email/name', {filters: {email: '姓名,别名+mail@example.test'}}],
    ['enum', {filters: {source: ['future_source']}}], ['plan', {plan: ['plus']}],
    ['date', {date_from: '2026-11-01', date_to: '2026-11-15'}], ['archived', {archived: 'only'}],
  ])('提交 %s 清空跨页 ID 和邮箱并回第一页', async (_name, raw) => {
    const h = setup(); h.handlers.list = async call => listResult([row(call.page)], {total: 100, page: call.page});
    h.owner.setVisible(true); await settle(); h.owner.toggle('1', true); h.owner.setPage(2); await settle(); h.owner.toggle('2', true);
    h.owner.commitQuery(h.adapter.normalize(raw as object)); await settle();
    expect(h.owner.page.value).toBe(1); expect(h.owner.selected.value.size).toBe(0);
    expect(h.owner.selectedEmails.value).toEqual({});
    expect(h.listCalls.at(-1)!.page).toBe(1);
  });

  it('归档、清全部和零计数未知枚举保留准确查询范围', async () => {
    const h = setup(); h.handlers.list = async () => listResult([], {total: 0, facets: {source: [{value: 'known', count: 2}]}});
    h.owner.setArchived(true); h.owner.updateFilters({source: ['future_source']}); h.owner.setVisible(true); await settle();
    expect(h.owner.facets.value.source).toContainEqual({value: 'future_source', count: 0});
    expect(h.owner.query.value.filters.source).toEqual(['future_source']);
    expect(h.owner.total.value).toBe(0); expect(h.owner.pages.value).toBe(1);
    h.owner.resetFilters(); await settle();
    expect(h.listCalls.at(-1)!.params.archived).toBe('only');
    expect(h.owner.query.value.filters.source).toEqual([]);
    expect(h.owner.selected.value.size).toBe(0);
  });

  it('中文 IME 只在 compositionend 后防抖，Enter 立即提交，clear 清除已提交 q', async () => {
    const h = setup(); h.owner.setVisible(true); await settle(); h.owner.toggle('1', true);
    h.owner.compositionStart(); h.owner.setSearchDraft('邮'); await vi.advanceTimersByTimeAsync(500);
    expect(h.listCalls).toHaveLength(1); expect(h.owner.query.value.q).toBe('');
    expect([...h.owner.selected.value]).toEqual(['1']);
    h.owner.compositionEnd('邮箱:测试'); await vi.advanceTimersByTimeAsync(249);
    expect(h.listCalls).toHaveLength(1); await vi.advanceTimersByTimeAsync(1); await settle();
    expect(h.listCalls).toHaveLength(2); expect(h.listCalls[1]!.params.q).toBe('邮箱:测试');
    expect(h.owner.selected.value.size).toBe(0);
    h.owner.setSearchDraft('备注:"next/value"'); h.owner.submitSearch(); await settle();
    expect(h.listCalls.at(-1)!.params.q).toBe('备注:"next/value"');
    const count = h.listCalls.length; await vi.advanceTimersByTimeAsync(250); expect(h.listCalls).toHaveLength(count);
    h.owner.clearSearch(); await settle();
    expect(h.owner.query.value.q).toBe(''); expect(h.owner.draftSearch.value).toBe('');
  });

  it('删除 chip 原样采用服务端 query_without，保留引号内空格和斜杠', async () => {
    const h = setup();
    const term: AccountSearchTerm = {field: 'plan', label: '套餐', value: 'plus', display_value: 'Plus', query_without: '备注:"a/b 待整理" 姓名:"Li Hong"'};
    h.handlers.list = async () => listResult([row(1)], {terms: [term]});
    h.owner.commitQuery(h.adapter.normalize({q: '套餐:plus 备注:"a/b 待整理" 姓名:"Li Hong"'}));
    h.owner.setVisible(true); await settle(); h.owner.toggle('1', true);
    h.owner.removeSearchTerm(h.owner.searchTerms.value[0]!); await settle();
    expect(h.listCalls.at(-1)!.params.q).toBe('备注:"a/b 待整理" 姓名:"Li Hong"');
    expect(h.owner.selected.value.size).toBe(0);
  });

  it('A 迟到成功不能清 B 的 loading，也不能替换 B 的 rows/facets/terms/total', async () => {
    const h = setup(); const old = deferred<AccountsListResponse>(); const fresh = deferred<AccountsListResponse>();
    h.handlers.list = call => call.query.q === 'fresh' ? fresh.promise : old.promise;
    h.owner.setVisible(true); await settle();
    h.owner.commitQuery(h.adapter.normalize({q: 'fresh'})); await settle();
    expect(h.listCalls[0]!.signal?.aborted).toBe(true); expect(h.owner.loading.value).toBe(true);
    old.resolve(listResult([row(99)], {total: 99, facets: {plan: [{value: 'wrong', count: 99}]}})); await settle();
    expect(h.owner.items.value).toEqual([]); expect(h.owner.loading.value).toBe(true);
    const term: AccountSearchTerm = {field: 'name', label: '姓名', value: 'fresh', display_value: 'fresh', query_without: ''};
    fresh.resolve(listResult([row(2)], {total: 1, facets: {plan: [{value: 'plus', count: 1}]}, terms: [term]})); await settle();
    expect(h.owner.items.value.map(item => item.id)).toEqual([2]); expect(h.owner.total.value).toBe(1);
    expect(h.owner.facets.value.plan).toEqual([{value: 'plus', count: 1}]); expect(h.owner.searchTerms.value).toEqual([term]);
    expect(h.owner.error.value).toBe(''); expect(h.owner.loading.value).toBe(false);
  });

  it('旧 invalid 错误晚于新成功不能覆盖错误状态或暂停新 q 的轮询', async () => {
    const h = setup(); const old = deferred<AccountsListResponse>();
    h.handlers.list = call => call.query.q === 'good' ? Promise.resolve(listResult()) : old.promise;
    h.owner.setVisible(true); await settle(); h.owner.updateQuery({q: 'good'}); await settle();
    old.reject(new ApiError('旧查询语法错误', 400, 'account_search_invalid')); await settle();
    expect(h.owner.items.value.map(item => item.id)).toEqual([1, 2]);
    expect(h.owner.error.value).toBe(''); expect(h.owner.invalidSearch.value).toBe(false);
    await vi.advanceTimersByTimeAsync(5000); expect(h.statusCalls).toHaveLength(1);
    expect(h.statusCalls[0]!.params.q).toBe('good');
  });

  it('当前 invalid 清空数据和分面并停轮询，修正后重新读取和轮询', async () => {
    const h = setup();
    const term: AccountSearchTerm = {field: 'name', label: '姓名', value: 'old', display_value: 'old', query_without: ''};
    h.handlers.list = async call => {
      if (call.query.q === 'broken:"') throw new ApiError('引号未闭合', 400, 'account_search_invalid');
      return listResult(undefined, {facets: {plan: [{value: 'plus', count: 2}]}, terms: [term]});
    };
    h.owner.setVisible(true); await settle(); h.owner.updateQuery({q: 'broken:"'}); await settle();
    expect(h.owner.invalidSearch.value).toBe(true); expect(h.owner.error.value).toBe('引号未闭合');
    expect(h.owner.items.value).toEqual([]); expect(h.owner.total.value).toBe(0);
    expect(h.owner.searchTerms.value).toEqual([]); expect(h.owner.facets.value).toEqual({});
    await vi.advanceTimersByTimeAsync(15000); expect(h.statusCalls).toHaveLength(0);
    h.owner.updateQuery({q: 'fixed'}); await settle();
    expect(h.owner.invalidSearch.value).toBe(false); expect(h.owner.items.value).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(5000); expect(h.statusCalls).toHaveLength(1);
    expect(h.statusCalls[0]!.params.q).toBe('fixed');
  });

  it('普通刷新失败保留同查询数据，新查询失败保留数据但 stale 且不能勾选', async () => {
    const h = setup(); h.owner.setVisible(true); await settle();
    h.handlers.list = async () => { throw new ApiError('服务暂不可用', 503); };
    await h.owner.refresh(); expect(h.owner.items.value.map(item => item.id)).toEqual([1, 2]);
    expect(h.owner.error.value).toBe('服务暂不可用'); expect(h.owner.stale.value).toBe(false);
    h.owner.updateFilters({email: 'different@example.test'}); await settle();
    expect(h.owner.items.value.map(item => item.id)).toEqual([1, 2]); expect(h.owner.stale.value).toBe(true);
    expect(() => h.owner.toggle('1', true)).toThrow(/尚未加载/);
    expect(() => h.owner.togglePage(true)).toThrow(/尚未加载/);
    expect(h.owner.selected.value.size).toBe(0);
    h.handlers.list = async () => listResult([row(3)]); await h.owner.refresh();
    expect(h.owner.items.value.map(item => item.id)).toEqual([3]); expect(h.owner.stale.value).toBe(false);
    expect(h.owner.error.value).toBe('');
  });

  it('删除导致末页越界只回查最后一页一次，真实 total=0 不用旧 rows 补值', async () => {
    const h = setup(); h.handlers.list = async call => listResult([row(1)], {total: 100, page: call.page});
    h.owner.setVisible(true); await settle(); h.listCalls.length = 0;
    h.handlers.list = async call => listResult(call.page === 1 ? [row(2)] : [], {total: 1, page: call.page});
    h.owner.setPage(5); await settle();
    expect(h.listCalls.map(call => call.page)).toEqual([5, 1]); expect(h.owner.page.value).toBe(1);
    expect(h.owner.items.value.map(item => item.id)).toEqual([2]);
    h.handlers.list = async () => listResult([], {total: 0}); await h.owner.refresh();
    expect(h.owner.total.value).toBe(0); expect(h.owner.pages.value).toBe(1); expect(h.owner.items.value).toEqual([]);
  });
  it('分页器同步回首页和修改容量只请求最终页，直接刷新仍可等待', async () => {
    const h = setup();
    h.handlers.list = async call => listResult([row(call.page)], {total: 60, page: call.page, size: call.size});
    h.owner.setVisible(true); await settle(); h.owner.setPage(2); await settle();
    h.listCalls.length = 0;
    h.owner.setPage(1); h.owner.setSize(30); await settle();
    expect(h.listCalls.map(call => [call.page, call.size])).toEqual([[1,30]]);
    const pending = deferred<AccountsListResponse>(); h.handlers.list = () => pending.promise;
    let completed = false;
    const refreshing = h.owner.refresh().then(() => { completed = true; });
    await settle(); expect(completed).toBe(false);
    pending.resolve(listResult([row(9)], {total: 60, size: 30})); await refreshing;
    expect(h.owner.items.value[0]?.id).toBe(9); expect(completed).toBe(true);
  });
});

describe('Accounts owner status 唯一轮询与生命周期', () => {
  it('只有一个 5 秒 timer，重复 visible 不增加轮询，隐藏后完全停止', async () => {
    const h = setup(); h.owner.setVisible(true); h.owner.setVisible(true); await settle();
    await vi.advanceTimersByTimeAsync(4999); expect(h.statusCalls).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1); expect(h.statusCalls).toHaveLength(1);
    h.owner.setVisible(true); h.owner.setVisible(true);
    await vi.advanceTimersByTimeAsync(5000); expect(h.statusCalls).toHaveLength(2);
    h.owner.setVisible(false); await vi.advanceTimersByTimeAsync(20000);
    expect(h.statusCalls).toHaveLength(2); expect(h.detailsCalls).toHaveLength(0);
    h.owner.setVisible(true); h.owner.setVisible(true); await settle();
    expect(h.listCalls).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(5000); expect(h.statusCalls).toHaveLength(3);
  });

  it('list 未完成时不发 status，status 未完成时不重叠；刷新会失效旧 status', async () => {
    const h = setup(); const pendingList = deferred<AccountsListResponse>(); const pendingStatus = deferred<AccountStatusesResponse>();
    h.handlers.list = () => pendingList.promise; h.handlers.statuses = () => pendingStatus.promise;
    h.owner.setVisible(true); await settle(); await vi.advanceTimersByTimeAsync(10000);
    expect(h.statusCalls).toHaveLength(0);
    pendingList.resolve(listResult()); await settle(); await vi.advanceTimersByTimeAsync(5000);
    expect(h.statusCalls).toHaveLength(1); expect(h.owner.polling.value).toBe(true);
    await vi.advanceTimersByTimeAsync(15000); expect(h.statusCalls).toHaveLength(1);
    h.handlers.list = async () => listResult([row(1, {email: 'new@example.test'}), row(2)]);
    await h.owner.refresh(); expect(h.statusCalls[0]!.signal?.aborted).toBe(true);
    pendingStatus.resolve(statusResult([statusRow(1, {email: 'stale@example.test'}), statusRow(2)])); await settle();
    expect(h.owner.items.value[0]?.email).toBe('new@example.test');
    expect(h.listCalls).toHaveLength(2);
  });

  it('隐藏会 abort list；隐藏期间只保存最终查询，旧读取即使忽略 abort 也不写入', async () => {
    const h = setup(); const pending = deferred<AccountsListResponse>(); h.handlers.list = () => pending.promise;
    h.owner.setVisible(true); await settle(); h.owner.setVisible(false);
    expect(h.listCalls[0]!.signal?.aborted).toBe(true);
    h.owner.setArchived(true); h.owner.updateFilters({source: ['future_source']}); await h.owner.refresh();
    pending.resolve(listResult([row(99)])); await settle(); await vi.advanceTimersByTimeAsync(15000);
    expect(h.listCalls).toHaveLength(1); expect(h.statusCalls).toHaveLength(0); expect(h.owner.items.value).toEqual([]);
    h.handlers.list = async () => listResult([row(2)]); h.owner.setVisible(true); await settle();
    expect(h.listCalls).toHaveLength(2);
    expect(h.listCalls[1]!.params).toMatchObject({archived: 'only', source: 'future_source', page: '1'});
    expect(h.owner.items.value.map(item => item.id)).toEqual([2]);
  });

  it('document 隐藏会 abort status；恢复只读一次且不改变筛选和选择', async () => {
    const h = setup(); h.owner.updateFilters({source: ['outlook']}); h.owner.setVisible(true); await settle();
    h.owner.toggle('1', true); const pending = deferred<AccountStatusesResponse>(); h.handlers.statuses = () => pending.promise;
    const polling = h.owner.pollStatuses(); await settle(); documentHidden(true);
    expect(h.statusCalls[0]!.signal?.aborted).toBe(true);
    pending.resolve(statusResult([statusRow(1, {email: 'hidden@example.test'}), statusRow(2)])); await polling;
    await vi.advanceTimersByTimeAsync(15000); expect(h.statusCalls).toHaveLength(1);
    expect(h.owner.items.value[0]?.email).toBe('account-1@example.test');
    documentHidden(false); await settle();
    expect(h.listCalls).toHaveLength(2); expect(h.listCalls[1]!.params.source).toBe('outlook');
    expect([...h.owner.selected.value]).toEqual(['1']);
    h.owner.setVisible(false); documentHidden(true); documentHidden(false); await settle();
    expect(h.listCalls).toHaveLength(2);
  });

  it('scope 卸载取消 list、搜索防抖和监听；迟到请求与恢复事件均无写入或新读取', async () => {
    const h = setup(); const pending = deferred<AccountsListResponse>(); h.handlers.list = () => pending.promise;
    h.owner.setVisible(true); await settle(); h.owner.setSearchDraft('scheduled'); h.scope.stop();
    expect(h.listCalls[0]!.signal?.aborted).toBe(true);
    pending.resolve(listResult([row(99)])); await settle(); await vi.advanceTimersByTimeAsync(15000);
    documentHidden(true); documentHidden(false); h.owner.setVisible(true); await h.owner.refresh(); await settle();
    expect(h.listCalls).toHaveLength(1); expect(h.statusCalls).toHaveLength(0);
    expect(h.owner.items.value).toEqual([]); expect(h.owner.loading.value).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('换页后的旧 status 不合并旧邮箱、不触发多余全量刷新', async () => {
    const h = setup();
    h.handlers.list = async call => listResult(call.page === 1 ? [row(1), row(2)] : [row(11), row(12)], {page: call.page, total: 40});
    h.owner.setVisible(true); await settle(); const pending = deferred<AccountStatusesResponse>(); h.handlers.statuses = () => pending.promise;
    const polling = h.owner.pollStatuses(); await settle(); h.owner.setPage(2); await settle();
    expect(h.statusCalls[0]!.signal?.aborted).toBe(true);
    pending.resolve(statusResult([statusRow(1, {email: 'old@example.test'}), statusRow(2)], {total: 40})); await polling; await settle();
    expect(h.owner.items.value.map(item => item.id)).toEqual([11, 12]); expect(h.owner.page.value).toBe(2);
    expect(h.listCalls).toHaveLength(2); expect(h.owner.error.value).toBe('');
  });

  it('status_fields 中缺失值删除旧字段，显式 null 保留，同 revision 不再次写入', async () => {
    const h = setup();
    h.handlers.list = async () => listResult([row(1, {plan_check_error: 'old failure', extract_link_error: 'old extract', note: 'untouched'})]);
    h.handlers.statuses = async () => statusResult([statusRow(1, {extract_link_error: null})],
      {fields: ['plan_check_error', 'extract_link_error'], revision: 'same'});
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    expect(Object.hasOwn(h.owner.items.value[0]!, 'plan_check_error')).toBe(false);
    expect(h.owner.items.value[0]!.extract_link_error).toBeNull(); expect(h.owner.items.value[0]!.note).toBe('untouched');
    const acceptedRows = h.owner.items.value;
    h.handlers.statuses = async () => statusResult([statusRow(1, {extract_link_error: 'should not repaint'})],
      {fields: ['extract_link_error'], revision: 'same'});
    await h.owner.pollStatuses();
    expect(h.owner.items.value).toBe(acceptedRows); expect(h.owner.items.value[0]!.extract_link_error).toBeNull();
    expect(h.listCalls).toHaveLength(1); expect(h.detailsCalls).toHaveLength(0);
  });

  it.each([
    ['IDs', [statusRow(1), statusRow(3)], 2],
    ['length', [statusRow(1)], 2],
    ['total', [statusRow(1), statusRow(2)], 3],
  ] as const)('status %s 变化只触发一次列表刷新并保留选择', async (_kind, items, total) => {
    const h = setup(); h.owner.setVisible(true); await settle(); h.owner.toggle('1', true);
    h.handlers.statuses = async () => statusResult([...items], {total});
    await h.owner.pollStatuses(); await settle();
    expect(h.listCalls).toHaveLength(2); expect([...h.owner.selected.value]).toEqual(['1']);
    expect(h.detailsCalls).toHaveLength(0);
  });

  it.each(['plan_check_status', 'extract_link_status'] as const)('%s 从运行到终态要完整刷新一次', async field => {
    const h = setup(); let reads = 0;
    h.handlers.list = async () => listResult([row(1, {[field]: reads++ === 0 ? 'running' : 'success', note: reads > 1 ? 'after terminal' : 'before'})]);
    h.handlers.statuses = async () => statusResult([statusRow(1, {[field]: 'success'})], {fields: [field]});
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses(); await settle();
    expect(h.listCalls).toHaveLength(2); expect(h.owner.items.value[0]?.note).toBe('after terminal');
  });
});

describe('Accounts owner 详情版本和消费者', () => {
  it('列表已有完整公开详情时不隐式 GET，也不编造 compact revision', async () => {
    const h = setup();
    h.handlers.list = async () => listResult([row(1, {account_promotions: [{plan: 'plus', title: 'from list'}],
      promotion_query_snapshot: {}, plan_check_country_results: []})]);
    h.owner.setVisible(true); await settle();
    const drawer = h.owner.openPlanDetailsConsumer('1');
    const result = await drawer.loadPlanDetails('1', drawer.openGeneration);
    expect(result.accountId).toBe('1'); expect(result.revision).toBe('');
    expect(result.item.account_promotions?.[0]?.title).toBe('from list');
    expect(h.detailsCalls).toHaveLength(0); drawer.release();
  });

  it('tooltip 与 drawer 同 ID/revision 只发一次 GET，同版本状态后复用完整详情', async () => {
    const h = setup(); const pending = deferred<AccountPlanDetailsResponse>(); h.handlers.details = () => pending.promise;
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    const tooltip = h.owner.openPlanDetailsConsumer('1'); const drawer = h.owner.openPlanDetailsConsumer('1');
    expect(tooltip.openGeneration).not.toBe(drawer.openGeneration);
    const tipResult = tooltip.loadPlanDetails('1', tooltip.openGeneration);
    const drawerResult = drawer.loadPlanDetails('1', drawer.openGeneration); await settle();
    expect(h.detailsCalls).toHaveLength(1); expect(h.detailsCalls[0]!.id).toBe('1');
    pending.resolve(detailsResult('complete country/promotion evidence'));
    const [tip, detail] = await Promise.all([tipResult, drawerResult]);
    expect(tip.revision).toBe('v1'); expect(detail).toEqual(tip);
    expect(detail.item.account_promotions?.[0]?.title).toBe('complete country/promotion evidence');
    h.handlers.statuses = async () => statusResult(undefined, {revision: 'status-2'}); await h.owner.pollStatuses();
    const cached = await drawer.loadPlanDetails('1', drawer.openGeneration);
    expect(cached.item.account_promotions?.[0]?.title).toBe('complete country/promotion evidence');
    expect(h.detailsCalls).toHaveLength(1); tooltip.release(); drawer.release();
  });

  it('v1 读取未完成时 status 升为 v2，两个消费者只收到共享的 v2', async () => {
    const h = setup(); const first = deferred<AccountPlanDetailsResponse>(); const second = deferred<AccountPlanDetailsResponse>();
    h.handlers.details = () => h.detailsCalls.length === 1 ? first.promise : second.promise;
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    const tooltip = h.owner.openPlanDetailsConsumer('1'); const drawer = h.owner.openPlanDetailsConsumer('1');
    const delivered: string[] = [];
    const tipResult = tooltip.loadPlanDetails('1', tooltip.openGeneration).then(value => { delivered.push(value.revision); return value; });
    const drawerResult = drawer.loadPlanDetails('1', drawer.openGeneration).then(value => { delivered.push(value.revision); return value; });
    await settle(); expect(h.detailsCalls).toHaveLength(1);
    h.handlers.statuses = async () => statusResult([statusRow(1, {plan_details_revision: 'v2'}), statusRow(2)], {revision: 'status-2'});
    await h.owner.pollStatuses(); expect(h.detailsCalls[0]!.signal?.aborted).toBe(true);
    first.resolve(detailsResult('obsolete v1')); await settle();
    expect(delivered).toEqual([]); expect(h.detailsCalls).toHaveLength(2);
    second.resolve(detailsResult('current v2'));
    const results = await Promise.all([tipResult, drawerResult]);
    expect(delivered).toEqual(['v2', 'v2']);
    expect(results.map(value => value.item.account_promotions?.[0]?.title)).toEqual(['current v2', 'current v2']);
    expect(h.owner.items.value[0]?.account_promotions?.[0]?.title).not.toBe('obsolete v1');
    expect(h.detailsCalls).toHaveLength(2); tooltip.release(); drawer.release();
  });

  it('释放 tooltip 只拒绝自己的待交付结果，不使同版本 drawer 失去共享请求', async () => {
    const h = setup(); const pending = deferred<AccountPlanDetailsResponse>(); h.handlers.details = () => pending.promise;
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    const tooltip = h.owner.openPlanDetailsConsumer('1'); const drawer = h.owner.openPlanDetailsConsumer('1');
    const tipResult = tooltip.loadPlanDetails('1', tooltip.openGeneration).then(value => ({value}), error => ({error}));
    const drawerResult = drawer.loadPlanDetails('1', drawer.openGeneration); await settle();
    tooltip.release(); pending.resolve(detailsResult('drawer still open'));
    const tip = await tipResult;
    expect('error' in tip && tip.error.name).toBe('AbortError');
    const result = await drawerResult; expect(result.item.account_promotions?.[0]?.title).toBe('drawer still open');
    expect(h.detailsCalls).toHaveLength(1); drawer.release();
  });

  it('关闭旧 drawer 并打开另一账号后，旧 generation 迟到拒绝且新账号独立交付', async () => {
    const h = setup(); const old = deferred<AccountPlanDetailsResponse>(); const next = deferred<AccountPlanDetailsResponse>();
    h.handlers.details = call => call.id === '1' ? old.promise : next.promise;
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    const first = h.owner.openPlanDetailsConsumer('1');
    const oldResult = first.loadPlanDetails('1', first.openGeneration).then(value => ({value}), error => ({error}));
    await settle(); first.release();
    const second = h.owner.openPlanDetailsConsumer('2'); expect(second.openGeneration).not.toBe(first.openGeneration);
    const newResult = second.loadPlanDetails('2', second.openGeneration); await settle();
    old.resolve(detailsResult('wrong closed account')); next.resolve(detailsResult('right account'));
    const previous = await oldResult; expect('error' in previous && previous.error.name).toBe('AbortError');
    const current = await newResult; expect(current.accountId).toBe('2');
    expect(current.item.account_promotions?.[0]?.title).toBe('right account');
    await expect(h.owner.loadPlanDetails('2', first.openGeneration)).rejects.toMatchObject({name: 'AbortError'});
    second.release();
  });

  it('同版本 HTTP 失败交付给消费者，不自动循环重试详情 GET', async () => {
    const h = setup(); h.handlers.details = async () => { throw new ApiError('明细暂不可用', 503); };
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    const drawer = h.owner.openPlanDetailsConsumer('1');
    await expect(drawer.loadPlanDetails('1', drawer.openGeneration)).rejects.toMatchObject({message: '明细暂不可用', status: 503});
    await vi.advanceTimersByTimeAsync(15000); expect(h.detailsCalls).toHaveLength(1);
    expect(h.owner.items.value.map(item => item.id)).toEqual([1, 2]); drawer.release();
  });

  it.each(['resolve', 'reject'] as const)('最后一个消费者关闭后 v1 %s，版本已升 v2 也不隐式 GET', async completion => {
    const h = setup(); const pending = deferred<AccountPlanDetailsResponse>(); h.handlers.details = () => pending.promise;
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    const drawer = h.owner.openPlanDetailsConsumer('1');
    const result = drawer.loadPlanDetails('1', drawer.openGeneration).then(value => ({value}), error => ({error}));
    await settle(); drawer.release();
    h.handlers.statuses = async () => statusResult([statusRow(1, {plan_details_revision: 'v2'}), statusRow(2)], {revision: 'status-2'});
    await h.owner.pollStatuses();
    if (completion === 'resolve') pending.resolve(detailsResult('closed old details'));
    else pending.reject(new DOMException('old request aborted', 'AbortError'));
    const outcome = await result; expect('error' in outcome && outcome.error.name).toBe('AbortError');
    await settle(); expect(h.detailsCalls).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(10000); expect(h.detailsCalls).toHaveLength(1);
  });

  it('跨页仍打开的消费者可复用详情；显式关闭后释放缓存，重访同 revision 需要新详情', async () => {
    const h = setup();
    h.handlers.list = async call => listResult(call.page === 1 ? [row(1)] : [row(11)], {page: call.page, total: 21});
    h.handlers.statuses = async call => statusResult([statusRow(call.page === 1 ? 1 : 11)], {page: call.page, total: 21, revision: `page-${call.page}`});
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    const old = h.owner.openPlanDetailsConsumer('1'); await old.loadPlanDetails('1', old.openGeneration);
    expect(h.detailsCalls).toHaveLength(1); h.owner.setPage(2); await settle();
    const stillOpen = await old.loadPlanDetails('1', old.openGeneration);
    expect(stillOpen.accountId).toBe('1'); expect(h.detailsCalls).toHaveLength(1);
    old.release();
    await expect(old.loadPlanDetails('1', old.openGeneration)).rejects.toMatchObject({name: 'AbortError'});
    h.owner.setPage(1); await settle(); await h.owner.pollStatuses();
    const current = h.owner.openPlanDetailsConsumer('1'); await current.loadPlanDetails('1', current.openGeneration);
    expect(h.detailsCalls).toHaveLength(2); current.release();
  });

  it('卸载中止详情读取并拒绝已销毁消费者，忽略 abort 的迟到结果不能写回', async () => {
    const h = setup(); const pending = deferred<AccountPlanDetailsResponse>(); h.handlers.details = () => pending.promise;
    h.owner.setVisible(true); await settle(); await h.owner.pollStatuses();
    const drawer = h.owner.openPlanDetailsConsumer('1');
    const result = drawer.loadPlanDetails('1', drawer.openGeneration).then(value => ({value}), error => ({error}));
    await settle(); h.scope.stop(); expect(h.detailsCalls[0]!.signal?.aborted).toBe(true);
    pending.resolve(detailsResult('after unmount')); const outcome = await result;
    expect('error' in outcome && outcome.error.name).toBe('AbortError');
    expect(h.owner.items.value[0]?.account_promotions?.[0]?.title).not.toBe('after unmount');
    expect(vi.getTimerCount()).toBe(0);
  });
});
