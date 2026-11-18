import {computed, onScopeDispose, readonly, ref, shallowRef, watch} from 'vue';
import type {BulkListDependencies, BulkNavigation, BulkPageData, BulkRecord} from './contracts';
import {bulkId, bulkObject} from './contracts';

export type BulkListFilter = 'q' | 'operation' | 'state' | 'created_from' | 'created_to';
const filterKeys: BulkListFilter[] = ['q', 'operation', 'state', 'created_from', 'created_to'];
function normalize(source: BulkNavigation): BulkNavigation {
  return {tab: 'bulk', view: 'list', cursor: source.cursor || '', ...Object.fromEntries(filterKeys.map(key => [key, source[key] || '']))};
}
function signature(source: BulkNavigation) {return JSON.stringify([source.cursor || '', ...filterKeys.map(key => source[key] || '')]);}
function params(source: BulkNavigation) {
  const query = new URLSearchParams({page_size: '20'});
  if (source.cursor) query.set('cursor', source.cursor);
  if (source.q) query.set('q', source.q);
  if (source.operation) query.set('operation_key[]', source.operation);
  if (source.state) query.set('control_state[]', source.state);
  for (const key of ['created_from', 'created_to'] as const) {
    if (!source[key]) continue;
    const date = new Date(`${source[key]}T${key === 'created_to' ? '23:59:59' : '00:00:00'}`);
    if (Number.isNaN(date.getTime())) throw new Error('创建日期无效，请调整筛选条件');
    query.set(key, date.toISOString());
  }
  return query.toString();
}

/** Read ownership only. The containing page owns visibility and polling. */
export function useBulkList(source: () => BulkNavigation, deps: BulkListDependencies) {
  const navigation = shallowRef(normalize(source()));
  const items = shallowRef<BulkRecord[]>([]), summary = shallowRef<BulkRecord>({});
  const nextCursor = ref<string | null>(null), previousCursors = shallowRef<string[]>([]);
  const loading = ref(false), visible = ref(false), error = ref(''), renderedSignature = ref('');
  const hasPrevious = computed(() => previousCursors.value.length > 0);
  const stale = computed(() => renderedSignature.value !== signature(navigation.value));
  let generation = 0, disposed = false, controller: AbortController | undefined;
  let pending: Promise<void> | undefined, pendingSignature = '';
  function invalidate() {generation++; controller?.abort(); controller = undefined; pending = undefined; pendingSignature = ''; loading.value = false;}
  function refresh(): Promise<void> {
    if (disposed || !visible.value || source().view !== 'list') return Promise.resolve();
    const key = signature(navigation.value);
    if (pending && pendingSignature === key) return pending;
    invalidate(); const ticket = generation, request = new AbortController();
    controller = request; loading.value = true; pendingSignature = key;
    pending = read(ticket, key, request);
    return pending;
  }
  async function read(ticket: number, key: string, request: AbortController) {
    try {
      const result = await deps.api.request<BulkPageData>(`/batches?${params(navigation.value)}`, {signal: request.signal});
      if (disposed || !visible.value || ticket !== generation || key !== signature(navigation.value)) return;
      if (!Array.isArray(result.items)) throw new Error('批次列表响应格式无效');
      const rows = result.items.map(value => {const row = bulkObject(value); bulkId(row.id); return {...row};});
      const page = bulkObject(result.page);
      if (page.next_cursor != null && typeof page.next_cursor !== 'string') throw new Error('批次分页响应格式无效');
      items.value = rows; summary.value = result.summary ? {...bulkObject(result.summary)} : {};
      nextCursor.value = typeof page.next_cursor === 'string' && page.next_cursor ? page.next_cursor : null;
      renderedSignature.value = key; error.value = '';
    } catch (cause) {
      if (disposed || !visible.value || ticket !== generation || (cause instanceof Error && cause.name === 'AbortError')) return;
      error.value = cause instanceof Error ? cause.message : '读取批次失败，请重试';
      if (cause && typeof cause === 'object' && 'status' in cause && cause.status === 401) error.value += '，请重新登录后返回';
    } finally {if (ticket === generation) {loading.value = false; controller = undefined; pending = undefined; pendingSignature = '';}}
  }
  async function transition(extra: Partial<BulkNavigation>) {
    navigation.value = normalize({...navigation.value, ...extra});
    deps.callbacks.updateNavigation(extra);
    await refresh();
  }
  async function applyFilters(filters: Partial<Record<BulkListFilter, string>>) {
    previousCursors.value = [];
    await transition({...filters, cursor: ''});
  }
  async function next() {
    if (!visible.value || loading.value || stale.value || !nextCursor.value) return;
    previousCursors.value = [...previousCursors.value, navigation.value.cursor || ''];
    await transition({cursor: nextCursor.value});
  }
  async function previous() {
    if (!visible.value || loading.value || !hasPrevious.value) return;
    const stack = previousCursors.value;
    const cursor = stack[stack.length - 1]!;
    previousCursors.value = stack.slice(0, -1);
    await transition({cursor});
  }
  async function first() {
    if (!visible.value || loading.value || !navigation.value.cursor) return;
    previousCursors.value = [];
    await transition({cursor: ''});
  }
  function resetFilters() {return applyFilters({q: '', operation: '', state: '', created_from: '', created_to: ''});}
  function setVisible(value: boolean) {
    visible.value = Boolean(value);
    if (!visible.value) invalidate();
  }
  watch(source, value => {
    if (value.view !== 'list') {invalidate(); return;}
    const incoming = normalize(value);
    if (signature(incoming) === signature(navigation.value) && (loading.value || renderedSignature.value)) return;
    navigation.value = incoming; previousCursors.value = [];
    if (visible.value) void refresh();
  }, {immediate: true, deep: true});
  onScopeDispose(() => {disposed = true; invalidate();});
  return {navigation: readonly(navigation), items: readonly(items), summary: readonly(summary), nextCursor: readonly(nextCursor),
    loading: readonly(loading), visible: readonly(visible), error: readonly(error), hasPrevious, stale, refresh, setVisible, applyFilters, resetFilters, next, previous, first};
}
