import { computed, nextTick, onScopeDispose, reactive, ref, shallowRef } from 'vue';
import { isAbort } from '../../api/client';
import { createProxyApi } from '../../api/proxy';
import type {
  ProxyDetailSnapshot,
  ProxyModuleView,
  ProxyPage,
  ProxyPoolSnapshot,
  ProxyQuery,
  ProxyRecordView,
  ProxyRow,
  ProxySummary,
  ProxyTrafficDeps,
} from './contracts';
const views: ProxyRecordView[] = ['current', 'history', 'traffic'];
const newPage = () => ({
  page: 1,
  size: 20,
  total: 0,
  state: 'all',
  items: [] as ProxyRow[],
  aggregate: undefined as ProxyPage['aggregate'],
});
export function useProxyTraffic(deps: ProxyTrafficDeps = {}) {
  const api = deps.api ?? createProxyApi(),
    visible = ref(false),
    view = ref<ProxyModuleView>(deps.view ?? 'pool'),
    recordView = ref<ProxyRecordView>('current');
  const filters = reactive({ window: 'all', purpose: 'all', search: '' }),
    pages = reactive({ current: newPage(), history: newPage(), traffic: newPage() });
  const summary = shallowRef<ProxySummary | null>(null),
    pool = shallowRef<ProxyPoolSnapshot | null>(null),
    detail = shallowRef<ProxyDetailSnapshot | null>(null);
  const loading = ref(false),
    error = ref(''),
    openFilter = ref<string | null>(null),
    scrollRevision = reactive({ current: 0, history: 0, traffic: 0 });
  const documentVisible = ref(!document.hidden),
    active = computed(() => visible.value && documentVisible.value);
  let generation = 0,
    scheduled = 0,
    disposed = false,
    controller: AbortController | null = null;
  let debounce: ReturnType<typeof setTimeout> | undefined, timer: ReturnType<typeof setTimeout> | undefined;
  let running: { key: string; promise: Promise<void> } | null = null;
  const pendingScroll = new Set<ProxyRecordView>();
  const canRead = () => !disposed && visible.value && !document.hidden;
  function invalidate() {
    generation++;
    scheduled++;
    controller?.abort();
    controller = null;
    clearTimeout(debounce);
    clearTimeout(timer);
    debounce = timer = undefined;
    running = null;
    loading.value = false;
  }
  function schedulePoll() {
    clearTimeout(timer);
    if (canRead())
      timer = setTimeout(() => {
        timer = undefined;
        void load();
      }, 30000);
  }
  function queue(target: ProxyRecordView | null = null, delay = 0) {
    invalidate();
    const ticket = scheduled;
    if (!canRead()) return;
    const run = () => {
      debounce = undefined;
      if (ticket === scheduled && canRead()) void load(target);
    };
    if (delay) debounce = setTimeout(run, delay);
    else void nextTick(run);
  }
  function query(name: ProxyRecordView): ProxyQuery {
    const state = pages[name];
    return {
      page: state.page,
      size: state.size,
      window: filters.window,
      purpose: name === 'traffic' ? 'all' : filters.purpose,
      state: state.state,
      search: filters.search,
    };
  }
  async function readPage(name: ProxyRecordView, q: ProxyQuery, signal: AbortSignal) {
    let result = await api.page(name, q, signal),
      page = q.page;
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
    if (result.total === 0) return { result, page: 1 };
    if (result.offset >= result.total) {
      page = Math.max(1, Math.ceil(result.total / q.size));
      result = await api.page(name, { ...q, page }, signal);
      if (result.total === 0) page = 1;
    }
    return { result, page };
  }
  function apply(name: ProxyRecordView, value: { result: ProxyPage; page: number }) {
    Object.assign(pages[name], {
      items: value.result.items,
      total: value.result.total,
      page: value.page,
      aggregate: value.result.aggregate,
    });
  }
  async function load(target: ProxyRecordView | null = null): Promise<void> {
    if (!canRead()) return;
    if (!summary.value) target = null;
    const names = target ? [target] : views,
      queries = Object.fromEntries(names.map((name) => [name, query(name)])) as Record<
        ProxyRecordView,
        ProxyQuery
      >;
    const key = JSON.stringify([target, queries]);
    if (running?.key === key) return running.promise;
    invalidate();
    const ticket = generation,
      readController = new AbortController();
    controller = readController;
    loading.value = true;
    const task = (async () => {
      try {
        const inventory = api.pool(readController.signal).catch((cause) => {
          if (isAbort(cause)) throw cause;
          return null;
        });
        const [results, metrics, inventoryResult] = await Promise.all([
          Promise.all(
            names.map(async (name) => ({
              name,
              ...(await readPage(name, queries[name], readController.signal)),
            })),
          ),
          target ? Promise.resolve(null) : api.summary(readController.signal),
          inventory,
        ]);
        if (ticket !== generation || !canRead()) return;
        results.forEach((result) => {
          apply(result.name, result);
          if (pendingScroll.delete(result.name)) scrollRevision[result.name]++;
        });
        if (metrics) summary.value = metrics;
        pool.value = inventoryResult;
        error.value = '';
        deps.onReady?.();
      } catch (cause) {
        if (ticket !== generation || !canRead() || isAbort(cause)) return;
        views.forEach((name) => {
          pages[name].items = [];
          pages[name].total = 0;
        });
        summary.value = null;
        pool.value = null;
        error.value = cause instanceof Error ? cause.message : String(cause);
      } finally {
        if (ticket === generation) {
          loading.value = false;
          controller = null;
          running = null;
          schedulePoll();
        }
      }
    })();
    running = { key, promise: task };
    return task;
  }
  function closeDetail(options: { restoreFocus?: boolean } = {}) {
    const opener = detail.value?.opener;
    detail.value = null;
    if (options.restoreFocus !== false && opener?.isConnected)
      void nextTick(() => opener.focus({ preventScroll: true }));
  }
  function setVisible(value: boolean) {
    if (disposed || visible.value === value) return;
    visible.value = value;
    if (value) queue();
    else {
      invalidate();
      openFilter.value = null;
      closeDetail({ restoreFocus: false });
    }
  }
  function setView(value: ProxyModuleView) {
    if (disposed || !['pool', 'records'].includes(value) || view.value === value) return;
    view.value = value;
    openFilter.value = null;
    closeDetail({ restoreFocus: false });
  }
  function setRecordView(value: ProxyRecordView) {
    if (disposed || !views.includes(value) || recordView.value === value) return;
    recordView.value = value;
    openFilter.value = null;
    closeDetail({ restoreFocus: false });
  }
  function updateFilters(patch: Partial<typeof filters>) {
    const changed = (Object.keys(patch) as (keyof typeof filters)[]).filter(
      (key) => patch[key] !== undefined && patch[key] !== filters[key],
    );
    if (!changed.length || disposed) return;
    changed.forEach((key) => {
      filters[key] = patch[key]!;
    });
    views.forEach((name) => {
      pages[name].page = 1;
      pendingScroll.add(name);
    });
    queue(null, changed.every((key) => key === 'search') ? 260 : 0);
  }
  function setState(name: ProxyRecordView, value: string) {
    if (disposed || pages[name].state === value) return;
    pages[name].state = value;
    pages[name].page = 1;
    pendingScroll.add(name);
    queue(name);
  }
  function setPage(name: ProxyRecordView, value: number) {
    if (disposed || !Number.isFinite(value)) return;
    const state = pages[name],
      next = Math.min(Math.max(1, Math.ceil(state.total / state.size)), Math.max(1, Math.floor(value)));
    if (next === state.page) return;
    state.page = next;
    pendingScroll.add(name);
    queue(name);
  }
  function setSize(name: ProxyRecordView, value: number) {
    if (disposed || ![20, 50, 100].includes(value) || pages[name].size === value) return;
    pages[name].size = value;
    pages[name].page = 1;
    pendingScroll.add(name);
    queue(name);
  }
  function resetFilters() {
    Object.assign(filters, { window: 'all', purpose: 'all', search: '' });
    views.forEach((name) => {
      pages[name].state = 'all';
      pages[name].page = 1;
      pendingScroll.add(name);
    });
    queue();
  }
  function removeFilter(key: string) {
    if (key.startsWith('state:')) setState(key.slice(6) as ProxyRecordView, 'all');
    else if (key === 'search') updateFilters({ search: '' });
    else if (key === 'window' || key === 'purpose') updateFilters({ [key]: 'all' });
  }
  function openDetail(name: 'history' | 'traffic', row: ProxyRow, opener: HTMLElement | null = null) {
    if (disposed || !canRead()) return;
    detail.value = { view: name, row: JSON.parse(JSON.stringify(row)) as ProxyRow, opener };
  }
  function visibilityChanged() {
    documentVisible.value = !document.hidden;
    if (document.hidden) {
      invalidate();
      openFilter.value = null;
      closeDetail({ restoreFocus: false });
    } else if (visible.value) queue();
  }
  document.addEventListener('visibilitychange', visibilityChanged);
  function dispose() {
    if (disposed) return;
    disposed = true;
    invalidate();
    closeDetail({ restoreFocus: false });
    document.removeEventListener('visibilitychange', visibilityChanged);
  }
  onScopeDispose(dispose);
  if (deps.visible) setVisible(true);
  return {
    visible,
    active,
    documentVisible,
    view,
    recordView,
    filters,
    pages,
    summary,
    pool,
    detail,
    loading,
    error,
    openFilter,
    scrollRevision,
    load,
    setVisible,
    setView,
    setRecordView,
    updateFilters,
    setState,
    setPage,
    setSize,
    resetFilters,
    removeFilter,
    openDetail,
    closeDetail,
    dispose,
  };
}
export type ProxyTrafficOwner = ReturnType<typeof useProxyTraffic>;
