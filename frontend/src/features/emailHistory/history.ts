import {computed, onMounted, onScopeDispose, reactive, ref} from 'vue';
import {isAbort, request} from '../../api/client';

export interface ParentScope {source: string; id: string; email: string}
export interface HistoryRow {
  id: number | string; email: string; source: string; state?: string;
  parent_email?: string; parent_id?: number | string; created_at?: string;
  registered_account_id?: number | string; root_task_id?: number | string;
}
export const sources: Record<string, string> = {icloud_hide: 'iCloud 隐藏邮箱', outlook: 'Outlook'};
export const statuses: Record<string, string> = {
  available: '历史未领取', disabled: '已停用', reserved: '归属已保留',
  used: '已绑定账号', replaced: '换绑后地址', retired: '历史停用',
};
export const pageSizes = [10, 20, 30, 50, 100];
const defaultFilters = () => ({source: 'all', parent_id: '', q: '', parent_q: '', state: '', related_q: '', created_from: '', created_to: ''});
export type FilterKey = keyof ReturnType<typeof defaultFilters>;
export const filterLabels: Record<FilterKey, string> = {
  source: '来源', parent_id: '指定母邮箱', q: '子邮箱', parent_q: '母邮箱',
  state: '状态', related_q: '关联账号 / 任务', created_from: '开始日期', created_to: '结束日期',
};
export function ownership(row: HistoryRow) {
  const account = row.registered_account_id ? `账号 #${row.registered_account_id}` : '';
  const task = row.root_task_id ? `任务 #${row.root_task_id}` : '';
  return [account, task].filter(Boolean).join(' · ') || (['available', 'disabled'].includes(row.state || '') ? '尚未领取' : '历史归属');
}

export function useEmailHistory(clipboard: (value: string) => Promise<boolean>) {
  const state = reactive({
    filters: defaultFilters(), parentEmail: '', page: 1, size: 50, total: 0, items: [] as HistoryRow[],
    selected: new Map<string, string>(), loading: false, error: '', receipt: '',
  });
  const active = ref(false);
  let visible = false, generation = 0, lastSuccess = '';
  let controller: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  function query() {
    const params = new URLSearchParams({page: String(state.page), page_size: String(state.size)});
    for (const [key, value] of Object.entries(state.filters)) if (value.trim()) params.set(key, value.trim());
    return `/api/email-derivation/allocations?${params}`;
  }
  function cancel() {
    generation++;
    controller?.abort();
    controller = undefined;
    clearTimeout(timer);
    state.loading = false;
  }
  async function refresh() {
    cancel();
    if (!active.value) return;
    const ticket = generation;
    controller = new AbortController();
    const signal = controller.signal;
    state.loading = true;
    try {
      // 某页在读取时消失，只取一次修正页。两次响应都受同一轮取消约束。
      for (let attempt = 0; attempt < 2; attempt++) {
        const url = query();
        const result = await request<{items: HistoryRow[]; total: number}>(url, {method: 'GET', signal});
        if (ticket !== generation) return;
        if (!Array.isArray(result?.items) || !Number.isSafeInteger(result.total) || result.total < 0) throw new Error('历史列表响应格式不完整');
        const lastPage = Math.max(1, Math.ceil(result.total / state.size));
        if (state.page > lastPage) {
          state.page = lastPage;
          state.total = result.total;
          state.items = [];
          if (attempt) throw new Error('列表范围已变化，请重试');
          continue;
        }
        state.items = result.items;
        state.total = result.total;
        for (const row of result.items) if (state.selected.has(String(row.id))) state.selected.set(String(row.id), row.email);
        lastSuccess = url;
        state.error = '';
        return;
      }
    } catch (error) {
      if (ticket === generation && !isAbort(error)) state.error = `子邮箱历史加载失败：${error instanceof Error ? error.message : String(error)}`;
    } finally {
      if (ticket === generation) {state.loading = false; controller = undefined;}
    }
  }
  function schedule(delay = 0) {
    cancel();
    if (lastSuccess !== query()) {state.items = []; state.error = '';}
    if (!active.value) return;
    const ticket = generation;
    state.loading = true;
    const run = () => {if (ticket === generation) void refresh();};
    if (delay) timer = setTimeout(run, delay); else queueMicrotask(run);
  }
  function applyFilterChange(delay = 0) {
    state.page = 1;
    if (query() !== lastSuccess) state.total = 0;
    state.selected.clear(); state.receipt = '';
    schedule(delay);
  }
  function updateFilter(key: FilterKey, value: string) {
    if (state.filters[key] === value) return;
    if (key === 'source' || key === 'parent_id') {state.filters.parent_id = ''; state.parentEmail = '';}
    state.filters[key] = value;
    applyFilterChange(['q', 'parent_q', 'related_q'].includes(key) ? 250 : 0);
  }
  function setView(parent: ParentScope) {
    Object.assign(state.filters, defaultFilters(), {source: parent.source, parent_id: parent.id});
    state.parentEmail = parent.email;
    applyFilterChange();
  }
  function resetFilters() {
    Object.assign(state.filters, defaultFilters()); state.parentEmail = '';
    applyFilterChange();
  }
  function syncVisibility() {
    const next = visible && !document.hidden;
    if (active.value === next) return;
    active.value = next;
    if (next) return refresh();
    cancel();
  }
  function setVisible(value: boolean) {visible = value; return syncVisibility();}
  onMounted(() => document.addEventListener('visibilitychange', syncVisibility));
  onScopeDispose(() => {document.removeEventListener('visibilitychange', syncVisibility); active.value = false; cancel();});
  function setPage(page: number) {
    if (state.page === page) return;
    state.page = page; state.receipt = ''; schedule();
  }
  function setSize(size: number) {
    if (!pageSizes.includes(size) || size === state.size) return;
    state.size = size; state.page = 1; state.receipt = ''; schedule();
  }
  function toggle(row: HistoryRow, checked: boolean) {
    if (checked) state.selected.set(String(row.id), row.email);
    else state.selected.delete(String(row.id));
    state.receipt = '';
  }
  function togglePage(checked: boolean) {for (const row of state.items) toggle(row, checked);}
  async function copy() {
    const addresses = state.selected.size ? Array.from(state.selected.values()) : state.items.map(row => row.email);
    if (!addresses.length) return;
    const ticket = generation;
    let ok = false;
    try {ok = await clipboard(addresses.join('\n'));} catch { /* 菜单或浏览器可能拒绝剪贴板。 */ }
    if (ticket === generation) state.receipt = ok ? `已复制 ${addresses.length} 条历史子邮箱` : '复制失败，请重试';
  }
  const chips = computed(() => (Object.keys(filterLabels) as FilterKey[]).filter(key => state.filters[key] !== defaultFilters()[key]).map(key => {
    const raw = state.filters[key];
    const value = key === 'source' ? sources[raw] : key === 'state' ? statuses[raw] : key === 'parent_id' ? state.parentEmail || `#${raw}` : raw;
    return {key, label: `${filterLabels[key]}：${value || raw}`, removeLabel: `移除${filterLabels[key]}筛选`};
  }));
  function removeFilter(key: string) {
    if (Object.hasOwn(filterLabels, key)) updateFilter(key as FilterKey, defaultFilters()[key as FilterKey]);
  }
  return {state, active, chips, setView, setVisible, refresh, updateFilter, resetFilters, setPage, setSize, toggle, togglePage, copy, removeFilter};
}
