import { computed, onScopeDispose, readonly, ref, shallowRef, watch } from 'vue';
import { readBulkPage, type BulkListDependencies, type BulkNavigation } from './contracts';

const filterKeys = ['q', 'operation', 'state', 'created_from', 'created_to'] as const;
export type BulkListFilter = (typeof filterKeys)[number];
type Filters = Partial<Record<BulkListFilter, string>>;

function listNavigation(source: BulkNavigation): BulkNavigation {
  const result: BulkNavigation = { tab: 'bulk', view: 'list', cursor: source.cursor || '' };
  for (const key of filterKeys) result[key] = source[key] || '';
  return result;
}

function dateBoundary(value: string, followingDay: boolean) {
  const date = new Date(`${value}T00:00:00`);
  const [year, month, day] = value.split('-').map(Number);
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
    date.getFullYear() !== year ||
    date.getMonth() + 1 !== month ||
    date.getDate() !== day
  ) {
    throw new Error('创建日期无效，请调整筛选条件');
  }
  // 使用本地日历的次日零点，包含整天并兼容夏令时切换。
  if (followingDay) date.setDate(date.getDate() + 1);
  return date.toISOString();
}

function queryFor(nav: BulkNavigation) {
  const query = new URLSearchParams({ page_size: '20' });
  if (nav.cursor) query.set('cursor', nav.cursor);
  if (nav.q) query.set('q', nav.q);
  if (nav.operation) query.set('operation_key[]', nav.operation);
  if (nav.state) query.set('control_state[]', nav.state);
  if (nav.created_from) query.set('created_from', dateBoundary(nav.created_from, false));
  if (nav.created_to) query.set('created_before', dateBoundary(nav.created_to, true));
  return query;
}

/** The shell starts refreshes and owns the polling timer. */
export function useBulkList(source: () => BulkNavigation, deps: BulkListDependencies) {
  const navigation = shallowRef(listNavigation(source()));
  const page = shallowRef<ReturnType<typeof readBulkPage> | null>(null);
  const previousCursors = shallowRef<string[]>([]);
  const hasPrevious = computed(() => previousCursors.value.length > 0);
  const visible = ref(false);
  const loading = ref(false);
  const error = ref('');
  let disposed = false;
  let controller: AbortController | undefined;
  let pending: Promise<void> | undefined;

  function cancel() {
    controller?.abort();
    controller = undefined;
    pending = undefined;
    loading.value = false;
  }

  function changeRange(next: BulkNavigation) {
    if (
      next.cursor === navigation.value.cursor &&
      filterKeys.every((key) => next[key] === navigation.value[key])
    )
      return false;
    cancel();
    navigation.value = next;
    page.value = null;
    error.value = '';
    return true;
  }

  function refresh(poll = false, canRender?: () => boolean): Promise<void> {
    if (disposed || !visible.value || source().view !== 'list') return Promise.resolve();
    if (pending) return pending;
    const request = new AbortController();
    controller = request;
    loading.value = true;
    const read = async () => {
      try {
        const response = await deps.api.request(`/batches?${queryFor(navigation.value)}`, {
          method: 'GET',
          signal: request.signal,
        });
        if (request.signal.aborted || (canRender && !canRender())) return;
        const previous = page.value;
        const next = readBulkPage(response);
        page.value = next;
        error.value = '';
        if (
          poll &&
          previous &&
          (previous.items.length !== next.items.length ||
            previous.items.some((row, i) => row.id !== next.items[i]?.id))
        ) {
          deps.callbacks.notify?.('批次列表已更新');
        }
      } catch (cause) {
        if (request.signal.aborted || (cause instanceof Error && cause.name === 'AbortError')) return;
        error.value = cause instanceof Error ? cause.message : '读取批次失败，请重试';
        if (cause instanceof Error && 'status' in cause && cause.status === 401 && !error.value.includes('登录'))
          error.value += '，请重新登录后返回';
      }
    };
    // Keep cleanup asynchronous even if query construction or the adapter throws synchronously.
    pending = read().finally(() => {
      if (controller !== request) return;
      controller = undefined;
      pending = undefined;
      loading.value = false;
    });
    return pending;
  }

  function transition(extra: Partial<BulkNavigation>) {
    changeRange(listNavigation({ ...navigation.value, ...extra }));
    deps.callbacks.updateNavigation(extra);
    return refresh();
  }

  function applyFilters(filters: Filters) {
    previousCursors.value = [];
    return transition({ ...filters, cursor: '' });
  }

  function next() {
    if (!visible.value || loading.value || !page.value?.nextCursor) return;
    const cursor = page.value.nextCursor;
    previousCursors.value = [...previousCursors.value, navigation.value.cursor || ''];
    return transition({ cursor });
  }

  function previous() {
    const stack = previousCursors.value;
    if (!visible.value || loading.value || !stack.length) return;
    previousCursors.value = stack.slice(0, -1);
    return transition({ cursor: stack[stack.length - 1]! });
  }

  function first() {
    if (!visible.value || loading.value || !navigation.value.cursor) return;
    previousCursors.value = [];
    return transition({ cursor: '' });
  }

  function setVisible(value: boolean) {
    visible.value = value;
    if (!value) cancel();
  }

  watch(
    source,
    (nav) => {
      if (nav.view !== 'list') {
        cancel();
        return;
      }
      if (!changeRange(listNavigation(nav))) return;
      previousCursors.value = [];
      if (visible.value) void refresh();
    },
    { deep: true },
  );

  onScopeDispose(() => {
    disposed = true;
    cancel();
  });
  return {
    navigation: readonly(navigation),
    items: computed(() => page.value?.items ?? []),
    summary: computed(() => page.value?.summary ?? {}),
    nextCursor: computed(() => page.value?.nextCursor ?? null),
    loading: readonly(loading),
    visible: readonly(visible),
    error: readonly(error),
    hasPrevious,
    stale: computed(() => !page.value),
    refresh,
    setVisible,
    applyFilters,
    next,
    previous,
    first,
    resetFilters: () => applyFilters({ q: '', operation: '', state: '', created_from: '', created_to: '' }),
  };
}
