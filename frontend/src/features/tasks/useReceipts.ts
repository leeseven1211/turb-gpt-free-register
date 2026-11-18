import {computed, onScopeDispose, ref} from 'vue';
import {tasksApi,type TaskId} from '../../api/tasks';
import {taskId,optionalTaskId,sameTaskId} from '../../api/taskIds';
import {isAbort} from '../../api/client';
import {record} from './presentation';

export interface AcceptedReference {accepted?: boolean; task_id?: TaskId; run_id?: TaskId | null; status?: string}
export interface Receipt {task_id: TaskId; run_id: TaskId | null; label: string; status: string; message: string}
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
    const results = await Promise.allSettled(selected.map(item => tasksApi.detail(item.task_id, controller!.signal)));
    if (id !== generation) return;
    results.forEach((result, index) => {
      const reference = selected[index]!;
      if (result.status === 'rejected') {
        if (!isAbort(result.reason)) error.value = '部分回执暂未读到，请稍后刷新。';
        return;
      }
      const task = result.value.task;
      const run = task.runs?.find(item => sameTaskId(item.id,reference.run_id));
      // 指定 Run 不能被最新 Run 的状态替换；旧回执缺失时保留原状态。
      if (reference.run_id && !run) { error.value = '部分执行记录暂未读到，请稍后刷新。'; return; }
      const source = run || task, summary = record(source.result_summary);
      reference.status = source.status || 'queued';
      reference.message = source.error_message || String(summary.message || (source.status === 'success' ? '已确认完成' : ''));
    });
    loading.value = false;
    controller = null;
    schedule();
  }
  function track(references: AcceptedReference[], title: string) {
    for (const item of references) {
      if (!item.accepted) continue;
      try {
        const task=taskId(item.task_id),run=optionalTaskId(item.run_id);
        if (items.value.some(existing => sameTaskId(existing.task_id,task) && (run===null?existing.run_id===null:sameTaskId(existing.run_id,run)))) continue;
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
