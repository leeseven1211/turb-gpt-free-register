import {computed, onScopeDispose, ref} from 'vue';
import {tasksApi, type OperationReceiptReference, type TaskId} from '../../api/tasks';
import {taskId, optionalTaskId} from '../../api/taskIds';
import {isAbort} from '../../api/client';

export interface AcceptedReference {accepted?: boolean; task_id?: TaskId; run_id?: TaskId | null; status?: string}
export interface Receipt extends OperationReceiptReference {label: string; status: string; message: string}
const receiptKey = ({task_id, run_id}: OperationReceiptReference) => `${task_id}:${run_id ?? ''}`;
export function useReceipts() {
  const items = ref<Receipt[]>([]), visible = ref(false), loading = ref(false), error = ref('');
  const terminal = new Set(['success', 'partial_success', 'failed', 'cancelled', 'stopped', 'interrupted', 'attention_required', 'deactivated', 'unsupported', 'request_unknown', 'manual_reconcile']);
  const pending = computed(() => items.value.filter(item => !terminal.has(item.status)));
  let timer: ReturnType<typeof setTimeout> | undefined, cursor = 0, generation = 0;
  let controller: AbortController | null = null;
  const schedule = () => {
    clearTimeout(timer);
    if (visible.value && !document.hidden && pending.value.length) timer = setTimeout(() => void refresh(), 2000);
  };
  async function refresh() {
    if (loading.value || !visible.value || document.hidden || !pending.value.length) return;
    const start = cursor % pending.value.length;
    const selected = [...pending.value.slice(start), ...pending.value.slice(0, start)].slice(0, 20);
    cursor = start + selected.length;
    const id = ++generation;
    controller = new AbortController();
    loading.value = true;
    error.value = '';
    try {
      const result = await tasksApi.receipts(selected, controller.signal);
      if (id !== generation) return;
      const byKey = new Map(result.items.map(item => [receiptKey(item), item]));
      for (const reference of selected) {
        const item = byKey.get(receiptKey(reference));
        if (!item) {
          error.value = reference.run_id === null
            ? '部分回执暂未读到，请稍后刷新。' : '部分执行记录暂未读到，请稍后刷新。';
          continue;
        }
        reference.status = item.status || 'queued';
        reference.message = item.message || (item.status === 'success' ? '已确认完成' : '');
      }
    } catch (cause) {
      if (id === generation && !isAbort(cause)) error.value = '回执暂未读到，请稍后刷新。';
    } finally {
      if (id === generation) {
        loading.value = false;
        controller = null;
        schedule();
      }
    }
  }
  function track(references: AcceptedReference[], title: string) {
    for (const item of references) {
      if (!item.accepted) continue;
      try {
        const task=taskId(item.task_id),run=optionalTaskId(item.run_id);
        const key = receiptKey({task_id: task, run_id: run});
        if (items.value.some(existing => receiptKey(existing) === key)) continue;
        items.value.push({task_id: task, run_id: run, label: title, status: item.status || 'queued', message: ''});
      } catch { error.value='任务回执标识无效，无法读取原任务。'; }
    }
    void refresh();
  }
  function setVisible(value: boolean) {
    visible.value = value;
    clearTimeout(timer);
    if (value && !document.hidden) void refresh();
    else { ++generation; controller?.abort(); loading.value = false; }
  }
  const onVisibility = () => setVisible(visible.value);
  document.addEventListener('visibilitychange', onVisibility);
  onScopeDispose(() => { ++generation; controller?.abort(); clearTimeout(timer); document.removeEventListener('visibilitychange', onVisibility); });
  return {items, pending, error, loading, track, refresh, setVisible};
}
