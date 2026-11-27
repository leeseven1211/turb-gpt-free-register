import {computed, nextTick, onScopeDispose, readonly, ref, shallowRef} from 'vue';
import {ApiError, isAbort} from '../../api/client';
import type {AccountFacets, AccountPlanDetails, AccountQueueSettings, AccountRow, AccountSearchTerm,
  AccountStatusRow, AccountsReadApi} from '../../api/accounts';
import type {AccountQueryAdapter, AccountQuerySpec} from './queryAdapter';

export type AccountViewRow = Partial<Omit<AccountRow, keyof AccountStatusRow | keyof AccountPlanDetails>>
  & Partial<AccountStatusRow> & Partial<AccountPlanDetails>
  & Pick<AccountRow, 'id' | 'email' | 'has_access_token' | 'has_account_password' | 'totp_enabled' | 'email_invalid'
    | 'email_invalid_reason' | 'email_invalid_at' | 'email_invalid_source'
    | 'plus_promo_kind' | 'plus_promo_eligible' | 'plus_trial_eligible' | 'plus_discount_eligible'>;
export interface AccountSelectionSnapshot {
  query: AccountQuerySpec;
  ids: readonly string[];
  expectedEmails: Readonly<Record<string, string>>;
  created_at: string;
  source: 'accounts';
  generation: number;
}
export interface AccountPlanDetailsSnapshot {
  accountId: string;
  revision: string;
  item: AccountPlanDetails;
}
export interface AccountActionContext {
  accountIds: readonly string[];
  expectedEmails: Readonly<Record<string, string>>;
  querySnapshot: AccountQuerySpec;
  archived: string;
  rowHints: readonly AccountViewRow[];
}
interface DetailEntry {
  revision: string;
  version: number;
  details?: AccountPlanDetails;
  request?: {version: number; controller: AbortController; promise: Promise<AccountPlanDetailsSnapshot>};
}
const FACET_TTL_MS = 30_000;
const detailKeys = ['account_promotions', 'promotion_query_snapshot', 'plan_check_country_results'] as const;
const facetKeys = ['source', 'registration_driver', 'token', 'password', 'plan', 'promotion', 'totp',
  'risk', 'codex', 'account_status', 'email_status'] as const;

function copy<T>(value: T): T {
  if (Array.isArray(value)) return value.map(copy) as T;
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, copy(item)])) as T;
  return value;
}
function freeze<T>(value: T): T {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}
function snapshot<T>(value: T): T { return freeze(copy(value)); }
function idOf(value: string | number): string {
  const id = String(value);
  if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) throw new Error('账号 ID 无效');
  return id;
}
function aborted(): never { throw new DOMException('读取已失效', 'AbortError'); }
function fullDetails(row: AccountViewRow): AccountPlanDetails {
  return copy({account_promotions: row.account_promotions ?? null,
    promotion_query_snapshot: row.promotion_query_snapshot ?? null,
    plan_check_country_results: row.plan_check_country_results ?? []});
}

/** One owner for the committed query, current page, cross-page selection and detail reads. */
export function useAccounts(adapter: AccountQueryAdapter, api: AccountsReadApi) {
  const query = shallowRef(adapter.normalize());
  const items = shallowRef<AccountViewRow[]>([]), facets = shallowRef<AccountFacets>({});
  const searchTerms = shallowRef<AccountSearchTerm[]>([]), queue = shallowRef<AccountQueueSettings | null>(null);
  const total = ref(0), page = ref(1), size = ref(20), loading = ref(false), polling = ref(false);
  const visible = ref(false), error = ref(''), invalidSearch = ref(false), draftSearch = ref('');
  const selected = shallowRef<ReadonlySet<string>>(new Set());
  const selectedEmails = shallowRef<Readonly<Record<string, string>>>({});
  const renderedSignature = ref('');
  const pages = computed(() => Math.max(1, Math.ceil(total.value / size.value)));
  const signature = computed(() => adapter.toLegacy(query.value, {paged: '1', page: page.value, page_size: size.value}).toString());
  const stale = computed(() => renderedSignature.value !== signature.value);
  const pageSelected = computed(() => items.value.length > 0 && items.value.every(row => selected.value.has(String(row.id))));
  const pageIndeterminate = computed(() => !pageSelected.value && items.value.some(row => selected.value.has(String(row.id))));
  let epoch = 0, refreshTicket = 0, selectionGeneration = 0, consumerGeneration = 0, disposed = false, composing = false;
  let listController: AbortController | undefined, statusController: AbortController | undefined;
  let pollTimer: ReturnType<typeof setTimeout> | undefined, searchTimer: ReturnType<typeof setTimeout> | undefined;
  let refreshTimer: ReturnType<typeof setTimeout> | undefined, statusRevision = '', invalidQuery: string | undefined;
  let facetSnapshot: {filter: string; readAt: number} | undefined;
  const details = new Map<string, DetailEntry>();
  const consumers = new Map<number, string>();
  const documentVisible = () => typeof document === 'undefined' || !document.hidden;
  const canRead = () => !disposed && visible.value && documentVisible();
  const current = (generation: number, key: string) => generation === epoch && key === signature.value && canRead();

  function hasDetailConsumers(accountId: string) {
    return [...consumers.values()].some(id => id === accountId);
  }
  function pruneDetails() {
    const retained = new Set([...items.value.map(row => String(row.id)), ...consumers.values()]);
    for (const [id, entry] of details) if (!retained.has(id)) {
      entry.request?.controller.abort(); details.delete(id);
    }
  }
  function cancelDetails() {
    for (const entry of details.values()) {
      entry.request?.controller.abort(); entry.request = undefined; ++entry.version;
    }
  }
  function invalidate() {
    ++epoch; ++refreshTicket;
    listController?.abort(); statusController?.abort(); listController = statusController = undefined;
    clearTimeout(pollTimer); clearTimeout(refreshTimer); pollTimer = refreshTimer = undefined;
    loading.value = polling.value = false;
  }
  function schedulePoll() {
    clearTimeout(pollTimer); pollTimer = undefined;
    if (canRead() && invalidQuery !== query.value.q) pollTimer = setTimeout(() => { void pollStatuses(); }, 5000);
  }
  function keepSelectedFacets(incoming: AccountFacets): AccountFacets {
    const result = copy(incoming);
    for (const key of facetKeys) {
      const chosen = key === 'plan' ? query.value.plan : query.value.filters[key];
      if (!chosen.length) continue;
      const entries = result[key] ?? [];
      result[key] = [...entries, ...chosen.filter(value => !entries.some(item => item.value === value))
        .map(value => ({value, count: 0}))];
    }
    return result;
  }
  function acceptFullRows(rows: AccountRow[]) {
    items.value = copy(rows);
    for (const row of items.value) {
      const id = String(row.id), old = details.get(id);
      // Full list has complete public details but no detail revision. Do not invent one.
      old?.request?.controller.abort();
      details.set(id, {revision: '', version: (old?.version ?? 0) + 1, details: fullDetails(row)});
    }
    pruneDetails();
  }
  async function readPage(reuseFacets: boolean): Promise<void> {
    invalidate();
    if (!canRead()) return;
    const generation = epoch, controller = new AbortController();
    const filter = adapter.toLegacy(query.value).toString();
    const includeFacets = !reuseFacets || facetSnapshot?.filter !== filter || Date.now() - facetSnapshot.readAt >= FACET_TTL_MS;
    if (includeFacets) facetSnapshot = undefined;
    listController = controller; loading.value = true;
    try {
      for (let correction = 0; correction < 2; correction++) {
        const key = signature.value, spec = copy(query.value), requestedPage = page.value, requestedSize = size.value;
        const needsFacets = includeFacets && !facetSnapshot;
        const result = await api.list(spec, requestedPage, requestedSize, controller.signal, {includeFacets: needsFacets});
        if (!current(generation, key)) return;
        if (needsFacets) {
          facets.value = keepSelectedFacets(result.facets);
          facetSnapshot = {filter, readAt: Date.now()};
        }
        const lastPage = Math.max(1, Math.ceil(result.total / requestedSize));
        if (requestedPage > lastPage) {
          page.value = lastPage;
          if (!correction) continue;
          error.value = '列表范围已变化，请刷新后重试';
          return;
        }
        acceptFullRows(result.items);
        total.value = result.total; searchTerms.value = copy(result.search_terms);
        renderedSignature.value = key; statusRevision = ''; error.value = ''; invalidSearch.value = false; invalidQuery = undefined;
        return;
      }
    } catch (cause) {
      if (generation !== epoch || !canRead() || isAbort(cause)) return;
      error.value = cause instanceof Error ? cause.message : '加载账号失败';
      if (cause instanceof ApiError && cause.code === 'account_search_invalid') {
        invalidQuery = query.value.q; invalidSearch.value = true;
        facetSnapshot = undefined;
        items.value = []; total.value = 0; searchTerms.value = []; facets.value = {};
        pruneDetails();
      }
    } finally {
      if (generation === epoch) { loading.value = false; listController = undefined; schedulePoll(); }
    }
  }
  function refresh(): Promise<void> { return readPage(false); }
  function applyStatus(row: AccountViewRow, incoming: AccountStatusRow, fields: string[]): AccountViewRow {
    const merged = copy(row) as unknown as Record<string, unknown>;
    for (const key of fields) delete merged[key];
    Object.assign(merged, copy(incoming));
    const id = String(row.id), old = details.get(id);
    if (!old || old.revision !== incoming.plan_details_revision) {
      // Old consumers join the latest version even when fetch ignores cancellation.
      old?.request?.controller.abort();
      details.set(id, {revision: incoming.plan_details_revision, version: (old?.version ?? 0) + 1});
      const promotions = (value: typeof incoming.plan_summary.promotions) => value?.map(item => {
        const plan = item.plan;
        return {...item, plan: typeof plan === 'string' && plan.trim() ? plan : 'plus'};
      }) ?? null;
      merged.account_promotions = promotions(incoming.plan_summary.promotions);
      merged.plan_check_country_results = incoming.plan_summary.countries.map(country => {
        const {promotions: values, ...state} = country;
        return {...state, ...(Array.isArray(values) ? {result: {account_promotions: promotions(values)}} : {})};
      });
      delete merged.promotion_query_snapshot;
    }
    return merged as unknown as AccountViewRow;
  }
  async function pollStatuses(): Promise<void> {
    clearTimeout(pollTimer); pollTimer = undefined;
    if (!canRead() || loading.value || polling.value || stale.value || invalidQuery === query.value.q) { schedulePoll(); return; }
    const generation = epoch, key = signature.value, controller = new AbortController();
    statusController = controller; polling.value = true;
    try {
      const result = await api.statuses(copy(query.value), page.value, size.value, controller.signal);
      if (!current(generation, key)) return;
      const byId = new Map(items.value.map(row => [String(row.id), row]));
      if (result.total !== total.value || result.items.length !== items.value.length
        || result.items.some((row,index) => String(row.id) !== String(items.value[index]?.id))
        || new Set(result.items.map(row => row.id)).size !== result.items.length) {
        await refresh(); return;
      }
      queue.value = copy(result.queue);
      if (statusRevision === result.revision) return;
      const active = (value: unknown) => value === 'queued' || value === 'running';
      let needsReload = false;
      items.value = result.items.map(incoming => {
        const row = byId.get(String(incoming.id))!;
        if ((active(row.plan_check_status) && !active(incoming.plan_check_status))
          || (active(row.extract_link_status) && !active(incoming.extract_link_status))) needsReload = true;
        return applyStatus(row, incoming, result.status_fields);
      });
      statusRevision = result.revision;
      if (needsReload) await refresh();
    } catch (cause) {
      if (current(generation, key) && cause instanceof ApiError && cause.code === 'account_search_invalid') {
        invalidQuery = query.value.q; invalidSearch.value = true; error.value = cause instanceof Error ? cause.message : '筛选语法无效';
        facetSnapshot = undefined;
        items.value = []; total.value = 0; facets.value = {}; searchTerms.value = []; pruneDetails();
      }
      // Keep the existing list on ordinary polling failures, matching the legacy page.
    } finally {
      if (generation === epoch) { polling.value = false; statusController = undefined; schedulePoll(); }
    }
  }
  function requestRefresh(delay = 0, reuseFacets = false) {
    // Invalidate immediately, but read only the final synchronous page/size state.
    invalidate();
    if (!canRead()) return;
    const ticket = refreshTicket;
    const execute = () => {
      if (ticket === refreshTicket && canRead()) void readPage(reuseFacets);
    };
    if (delay) refreshTimer = setTimeout(execute, delay);
    else void nextTick(execute);
  }
  function clearSelection() {
    selected.value = new Set(); selectedEmails.value = {}; ++selectionGeneration;
  }
  function commitQuery(raw: object, delay = 0) {
    if (disposed) return;
    const next = adapter.normalize(raw);
    clearTimeout(searchTimer); searchTimer = undefined;
    if (adapter.toLegacy(next).toString() === adapter.toLegacy(query.value).toString() && next.limit === query.value.limit) {
      draftSearch.value = next.q; return;
    }
    query.value = copy(next); draftSearch.value = next.q; page.value = 1; clearSelection();
    invalidSearch.value = false; error.value = ''; invalidQuery = undefined;
    requestRefresh(delay);
  }
  function updateQuery(patch: Partial<AccountQuerySpec>, delay = 0) { commitQuery({...copy(query.value), ...copy(patch)}, delay); }
  function updateFilters(patch: Partial<AccountQuerySpec['filters']>, delay = 0) {
    updateQuery({filters: {...copy(query.value.filters), ...copy(patch)}}, delay);
  }
  function setArchived(value: boolean) { updateQuery({archived: value ? 'only' : '0'}); }
  function setViewScope(view: 'active' | 'team' | 'archived') {
    if (view === 'team') updateQuery({team_scope: 'team', archived: 'all'});
    else if (view === 'archived') updateQuery({team_scope: 'all', archived: 'only'});
    else updateQuery({team_scope: 'non_team', archived: '0'});
  }
  function resetFilters() { commitQuery(adapter.normalize({archived: query.value.archived, team_scope: query.value.team_scope})); }
  function setPage(value: number) {
    if (disposed || !Number.isFinite(value)) return;
    const next = Math.min(pages.value, Math.max(1, Math.floor(value)));
    if (next !== page.value) { page.value = next; requestRefresh(0, true); }
  }
  function setSize(value: number) {
    if (disposed || !Number.isFinite(value) || value < 1) return;
    const next = Math.min(500, Math.floor(value));
    if (next !== size.value) { size.value = next; page.value = 1; requestRefresh(0, true); }
  }
  function setSearchDraft(value: string) {
    draftSearch.value = value; clearTimeout(searchTimer); searchTimer = undefined;
    if (!composing && !disposed) searchTimer = setTimeout(() => { updateQuery({q: draftSearch.value}); }, 250);
  }
  function compositionStart() { composing = true; clearTimeout(searchTimer); searchTimer = undefined; }
  function compositionEnd(value: string) { composing = false; setSearchDraft(value); }
  function submitSearch() { if (!composing) { clearTimeout(searchTimer); updateQuery({q: draftSearch.value}); } }
  function clearSearch() { composing = false; clearTimeout(searchTimer); updateQuery({q: ''}); }
  function removeSearchTerm(term: AccountSearchTerm) { updateQuery({q: term.query_without}); }
  function toggle(accountId: string, checked: boolean) {
    if (disposed) return;
    if (checked && (stale.value || invalidSearch.value)) throw new Error('当前筛选结果尚未加载');
    const id = idOf(accountId), row = items.value.find(item => String(item.id) === id);
    if (checked && !row) throw new Error('账号不在当前页');
    const ids = new Set(selected.value), emails = {...selectedEmails.value};
    if (checked) {
      ids.add(id);
      if (row?.email?.trim()) emails[id] = row.email;
      else delete emails[id];
    }
    else { ids.delete(id); delete emails[id]; }
    selected.value = ids; selectedEmails.value = emails; ++selectionGeneration;
  }
  function togglePage(checked: boolean) {
    for (const row of items.value) toggle(String(row.id), checked);
  }
  function removeAcknowledgedSelection(ids: readonly string[]) {
    for (const id of ids) toggle(id, false);
  }
  function getAccountSelectionSnapshot(options: {ids?: readonly string[]; requireEmails?: boolean} = {}): AccountSelectionSnapshot {
    const ids = [...new Set((options.ids ?? [...selected.value]).map(idOf))], emails: Record<string, string> = {};
    const currentRows = new Map(items.value.map(row => [String(row.id), row]));
    for (const id of ids) {
      // A present row is authoritative even when its email is missing.
      const email = currentRows.has(id) ? currentRows.get(id)?.email : selectedEmails.value[id];
      if (email) emails[id] = email;
    }
    if (options.requireEmails && (ids.length > 500 || ids.some(id => !emails[id]?.trim()))) {
      throw new Error(ids.length > 500 ? '一次最多处理 500 个账号' : '账号邮箱快照不完整，请刷新后重新选择');
    }
    return snapshot({query: query.value, ids, expectedEmails: emails, created_at: new Date().toISOString(),
      source: 'accounts' as const, generation: selectionGeneration});
  }
  function getActionContext(options: {ids?: readonly string[]; requireEmails?: boolean} = {}): AccountActionContext {
    const value = getAccountSelectionSnapshot(options), ids = new Set(value.ids);
    return snapshot({accountIds: value.ids, expectedEmails: value.expectedEmails, querySnapshot: value.query,
      archived: value.query.archived, rowHints: items.value.filter(row => ids.has(String(row.id)))});
  }
  function getRowSnapshot(accountId: string): AccountViewRow | undefined {
    const row = items.value.find(item => String(item.id) === accountId);
    return row ? snapshot(row) : undefined;
  }
  async function ensureDetails(accountId: string): Promise<AccountPlanDetailsSnapshot> {
    if (!canRead() || !hasDetailConsumers(accountId)) aborted();
    const entry = details.get(accountId);
    if (!entry) aborted();
    if (entry.details) return snapshot({accountId, revision: entry.revision, item: entry.details});
    if (entry.request) return entry.request.promise;
    const controller = new AbortController(), version = entry.version;
    const promise: Promise<AccountPlanDetailsSnapshot> = api.planDetails(accountId, controller.signal).then(async result => {
      if (!canRead() || !hasDetailConsumers(accountId)) aborted();
      const latest = details.get(accountId);
      if (!latest) aborted();
      if (latest !== entry || latest.version !== version) return ensureDetails(accountId);
      latest.details = copy(result.item);
      items.value = items.value.map(row => String(row.id) === accountId ? {...row, ...copy(result.item)} : row);
      return snapshot({accountId, revision: latest.revision, item: latest.details});
    }, cause => {
      if (!canRead() || !hasDetailConsumers(accountId)) aborted();
      const latest = details.get(accountId);
      if (latest && (latest !== entry || latest.version !== version)) return ensureDetails(accountId);
      throw cause;
    }).finally(() => {
      if (entry.request?.promise === promise) entry.request = undefined;
      pruneDetails();
    });
    entry.request = {version, controller, promise};
    return promise;
  }
  async function loadPlanDetails(accountId: string, openGeneration: number): Promise<AccountPlanDetailsSnapshot> {
    const id = idOf(accountId);
    for (;;) {
      if (consumers.get(openGeneration) !== id || !canRead()) aborted();
      const owner = details.get(id), version = owner?.version;
      let result: AccountPlanDetailsSnapshot;
      try { result = await ensureDetails(id); }
      catch (cause) {
        if (consumers.get(openGeneration) !== id || !canRead()) aborted();
        throw cause;
      }
      if (consumers.get(openGeneration) !== id || !canRead()) aborted();
      // Cover revision changes between the shared promise settling and this consumer resuming.
      if (details.get(id) !== owner || owner?.version !== version) continue;
      return result;
    }
  }
  function openPlanDetailsConsumer(accountId: string) {
    const id = idOf(accountId), openGeneration = ++consumerGeneration;
    if (!details.has(id)) throw new Error('账号详情已失效，请刷新列表');
    consumers.set(openGeneration, id);
    return {openGeneration, loadPlanDetails,
      release() {
        if (!consumers.delete(openGeneration)) return;
        // Keep page caches, but only an open consumer may keep a request alive.
        // Releasing one lease must not cancel another consumer's shared read.
        if (!hasDetailConsumers(id)) {
          const entry = details.get(id);
          if (entry?.request) {
            entry.request.controller.abort(); entry.request = undefined; ++entry.version;
          }
        }
        pruneDetails();
      }};
  }
  function setVisible(value: boolean) {
    if (disposed || value === visible.value) return;
    visible.value = value;
    if (value) requestRefresh();
    else { invalidate(); cancelDetails(); consumers.clear(); pruneDetails(); }
  }
  function visibilityChanged() {
    if (!documentVisible()) { invalidate(); cancelDetails(); }
    else if (visible.value) requestRefresh();
  }
  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', visibilityChanged);
  onScopeDispose(() => {
    disposed = true; invalidate(); clearTimeout(searchTimer); cancelDetails(); consumers.clear(); details.clear();
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', visibilityChanged);
  });
  return {query: readonly(query), items: readonly(items), facets: readonly(facets), searchTerms: readonly(searchTerms),
    queue: readonly(queue), total: readonly(total), page: readonly(page), size: readonly(size), pages,
    selected: readonly(selected), selectedEmails: readonly(selectedEmails), loading: readonly(loading), polling: readonly(polling),
    visible: readonly(visible), error: readonly(error), invalidSearch: readonly(invalidSearch), draftSearch: readonly(draftSearch),
    renderedSignature: readonly(renderedSignature), signature, stale, pageSelected, pageIndeterminate,
    refresh, pollStatuses, setVisible, setPage, setSize, setArchived, setViewScope, commitQuery, updateQuery, updateFilters, resetFilters,
    setSearchDraft, compositionStart, compositionEnd, submitSearch, clearSearch, removeSearchTerm,
    toggle, togglePage, clearSelection, removeAcknowledgedSelection, getAccountSelectionSnapshot, getActionContext,
    getRowSnapshot, openPlanDetailsConsumer, loadPlanDetails};
}
