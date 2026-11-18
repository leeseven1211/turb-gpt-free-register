import {computed, nextTick, onScopeDispose, reactive, ref} from 'vue';
import {codexApi, emptyCodexFilters, type CodexFilters, type CodexFacets, type CodexRow} from '../../api/codex';
import {isAbort} from '../../api/client';

/** The page owns queries and filename selection; the shell calls explicit methods. */
export function useCodexList() {
  const filters = reactive<CodexFilters>(emptyCodexFilters());
  const items = ref<CodexRow[]>([]), facets = ref<CodexFacets>({});
  const total = ref(0), page = ref(1), size = ref(20), archived = ref(false);
  const selected = ref(new Set<string>()), loading = ref(false), error = ref(''), visible = ref(false);
  const pages = computed(() => Math.max(1, Math.ceil(total.value / size.value)));
  const textFields = new Set<keyof CodexFilters>(['q', 'account_id', 'sub2api_id']);
  let generation = 0, scheduled = 0, disposed = false;
  let controller: AbortController | null = null;
  let debounce: ReturnType<typeof setTimeout> | undefined;

  function invalidate() {
    ++generation; ++scheduled;
    clearTimeout(debounce); debounce = undefined;
    controller?.abort(); controller = null;
    loading.value = false;
  }
  function canRead() { return !disposed && visible.value && !document.hidden; }
  function queueRefresh(delay = 0) {
    // Invalidate immediately: even a response arriving during text debounce is stale.
    invalidate();
    const ticket = scheduled;
    if (!canRead()) return;
    const run = () => { if (ticket === scheduled && canRead()) void refresh(); };
    if (delay) debounce = setTimeout(run, delay);
    else void nextTick(run);
  }
  function keepSelectedFacets(incoming: CodexFacets): CodexFacets {
    const result = {...incoming};
    for (const key of ['plan', 'status', 'oauth_status'] as const) {
      const entries = (incoming[key] || []).filter(item => item.value && (key !== 'status' || item.value !== 'archived'));
      const value = filters[key];
      result[key] = value && !entries.some(item => item.value === value)
        ? [...entries, {value, count: 0}]
        : entries;
    }
    return result;
  }
  async function refresh(): Promise<void> {
    invalidate();
    if (!canRead()) return;
    const id = generation;
    const requestController = new AbortController();
    controller = requestController;
    loading.value = true;
    try {
      // A single correction handles deletion of the last page without an unbounded loop.
      for (let correction = 0; correction < 2; correction++) {
        const query = {page: page.value, size: size.value, archived: archived.value, filters: {...filters}};
        const result = await codexApi.list(query, requestController.signal);
        if (id !== generation || !canRead()) return;
        const count = Number(result.total);
        total.value = Number.isFinite(count) ? Math.max(0, Math.floor(count)) : 0;
        if (page.value > pages.value) {
          page.value = pages.value;
          if (!correction) continue;
          items.value = [];
          error.value = '列表范围已变化，请刷新后重试';
          return;
        }
        items.value = result.accounts || [];
        facets.value = keepSelectedFacets(result.facets || {});
        error.value = '';
        return;
      }
    } catch (cause) {
      if (id === generation && !isAbort(cause)) {
        error.value = cause instanceof Error ? cause.message : 'Codex 凭证加载失败';
      }
    } finally {
      if (id === generation) { loading.value = false; controller = null; }
    }
  }
  function setVisible(value: boolean) {
    if (disposed || value === visible.value) return;
    visible.value = value;
    if (value) queueRefresh();
    else invalidate();
  }
  function setArchived(value: boolean) {
    if (disposed || value === archived.value) return;
    archived.value = value; selected.value = new Set();
    items.value = []; facets.value = {}; total.value = 0; page.value = 1; error.value = '';
    queueRefresh();
  }
  function setPage(value: number) {
    if (disposed || !Number.isFinite(value)) return;
    const next = Math.min(pages.value, Math.max(1, Math.floor(value)));
    if (next === page.value) return;
    page.value = next; queueRefresh();
  }
  function setSize(value: number) {
    if (disposed || !Number.isFinite(value) || value < 1) return;
    const next = Math.min(500, Math.floor(value));
    if (next === size.value) return;
    size.value = next; page.value = 1; queueRefresh();
  }
  function updateFilters(value: Partial<CodexFilters>) {
    if (disposed) return;
    const changed = (Object.keys(filters) as (keyof CodexFilters)[])
      .filter(key => value[key] !== undefined && value[key] !== filters[key]);
    if (!changed.length) return;
    for (const key of changed) filters[key] = value[key]!;
    page.value = 1;
    const onlyText = changed.every(key => textFields.has(key));
    if (!onlyText) selected.value = new Set();
    queueRefresh(onlyText ? 250 : 0);
  }
  function resetFilters() {
    if (disposed) return;
    Object.assign(filters, emptyCodexFilters());
    selected.value = new Set(); page.value = 1; queueRefresh();
  }
  function toggle(filename: string, checked: boolean) {
    const next = new Set(selected.value);
    checked ? next.add(filename) : next.delete(filename);
    selected.value = next;
  }
  function togglePage(checked: boolean) {
    const next = new Set(selected.value);
    for (const item of items.value) checked ? next.add(item.filename) : next.delete(item.filename);
    selected.value = next;
  }
  const visibilityChanged = () => {
    if (document.hidden) invalidate();
    else if (visible.value) queueRefresh();
  };
  document.addEventListener('visibilitychange', visibilityChanged);
  onScopeDispose(() => {
    disposed = true; invalidate();
    document.removeEventListener('visibilitychange', visibilityChanged);
  });
  return {filters, items, facets, total, page, size, pages, archived, selected, loading, error, visible,
    refresh, setVisible, setArchived, setPage, setSize, updateFilters, resetFilters, toggle, togglePage};
}
