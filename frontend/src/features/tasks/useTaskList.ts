import {computed, nextTick, onScopeDispose, reactive, ref, watch} from 'vue';
import {emptyFilters, tasksApi, type Facets, type OperationTask, type TaskFilters, type TaskId} from '../../api/tasks';
import {isAbort} from '../../api/client';

/** 列表拥有自己的请求、筛选、选择和轮询；页面外部只能通过显式方法访问。 */
export function useTaskList() {
  const filters = reactive<TaskFilters>(emptyFilters());
  const page = ref(1), size = ref(20), total = ref(0);
  const items = ref<OperationTask[]>([]), facets = ref<Facets>({});
  const selected = ref(new Set<TaskId>()), loading = ref(false), error = ref('');
  const visible = ref(false);
  const pages = computed(() => Math.max(1, Math.ceil(total.value / size.value)));
  let requestId = 0, controller: AbortController | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined, debounce: ReturnType<typeof setTimeout> | undefined;
  let queuedRefresh = 0;
  let metadataAt = 0, metadataQuery = '', revision = '';
  const textFilters = new Set<keyof TaskFilters>(['task_id', 'target', 'batch', 'result']);
  let normalizedChange: {metadata: boolean; delay: number} | null = null;
  function queueRefresh(options: {metadata?: boolean} = {}, delay = 0) {
    clearTimeout(debounce);
    const version = ++queuedRefresh;
    const load = () => {
      if (version === queuedRefresh && visible.value && !document.hidden) void refresh(options);
    };
    if (delay) debounce = setTimeout(load, delay);
    else void nextTick(load);
  }
  const schedule = () => {
    clearTimeout(timer);
    if (visible.value && !document.hidden) timer = setTimeout(() => void refresh(), 5000);
  };
  async function refresh(options: {metadata?: boolean} = {}) {
    clearTimeout(timer);
    clearTimeout(debounce);
    ++queuedRefresh;
    const query = {...filters, page: page.value, page_size: size.value};
    const signature = JSON.stringify(query);
    const metadata = options.metadata || metadataQuery !== signature || Date.now() - metadataAt >= 30000;
    const id = ++requestId;
    controller?.abort();
    controller = new AbortController();
    loading.value = true;
    try {
      const result = await tasksApi.list({...query, include_facets: metadata ? 1 : 0, include_batches: 0}, controller.signal);
      if (id !== requestId) return;
      total.value = Number(result.total || 0);
      if (page.value > pages.value) { page.value = pages.value; return; }
      const nextRevision = signature + (result.revision || JSON.stringify(result.items));
      if (revision !== nextRevision) {
        items.value = result.items || [];
        revision = nextRevision;
        const ids = new Set(items.value.map(item => item.id));
        selected.value = new Set([...selected.value].filter(value => ids.has(value)));
      }
      if (result.facets) facets.value = result.facets;
      if (metadata) { metadataAt = Date.now(); metadataQuery = signature; }
      error.value = '';
    } catch (cause) {
      if (id === requestId && !isAbort(cause)) error.value = cause instanceof Error ? cause.message : '任务列表加载失败';
    } finally {
      if (id === requestId) { loading.value = false; controller = null; schedule(); }
    }
  }
  function setVisible(value: boolean) {
    if (value === visible.value) return;
    visible.value = value;
    clearTimeout(timer);
    clearTimeout(debounce);
    if (value && !document.hidden) queueRefresh();
    else { ++queuedRefresh; controller?.abort(); ++requestId; loading.value = false; }
  }
  function applyFilters(value: Partial<TaskFilters>, replace = true) {
    Object.assign(filters, replace ? {...emptyFilters(), ...value} : value);
    page.value = 1;
    selected.value = new Set();
  }
  function toggle(id: TaskId, checked: boolean) {
    const next = new Set(selected.value);
    checked ? next.add(id) : next.delete(id);
    selected.value = next;
  }
  function togglePage(checked: boolean) { selected.value = new Set(checked ? items.value.map(item => item.id) : []); }
  watch(() => ({...filters, page: page.value, page_size: size.value}), (query, previous) => {
    selected.value = new Set();
    clearTimeout(timer);
    const changed = (Object.keys(filters) as (keyof TaskFilters)[]).filter(key => query[key] !== previous[key]);
    if (changed.length) {
      normalizedChange = {metadata: true, delay: changed.every(key => textFilters.has(key)) && query.page_size === previous.page_size ? 260 : 0};
      // 页码归一后由同一观察入口发起请求，保留文本防抖，避免第二个 page watcher 重复读取。
      if (page.value !== 1) { page.value = 1; return; }
    }
    const pending = normalizedChange || {metadata: false, delay: 0};
    normalizedChange = null;
    ++requestId;
    controller?.abort();
    queueRefresh({metadata: pending.metadata}, pending.delay);
  });
  const visibilityChanged = () => {
    clearTimeout(timer);
    if (document.hidden) { ++queuedRefresh; clearTimeout(debounce); controller?.abort(); ++requestId; loading.value = false; }
    else if (visible.value) queueRefresh();
  };
  document.addEventListener('visibilitychange', visibilityChanged);
  onScopeDispose(() => {
    ++requestId; ++queuedRefresh; controller?.abort(); clearTimeout(timer); clearTimeout(debounce);
    document.removeEventListener('visibilitychange', visibilityChanged);
  });
  return {filters, page, size, pages, total, items, facets, selected, loading, error, visible,
    refresh, setVisible, applyFilters, toggle, togglePage};
}
