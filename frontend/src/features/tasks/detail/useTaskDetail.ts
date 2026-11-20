import { computed, onScopeDispose, ref, shallowRef } from 'vue';
import { tasksApi, type OperationTask, type TaskId } from '../../../api/tasks';
import {taskId as normalizeTaskId,optionalTaskId,sameTaskId} from '../../../api/taskIds';
import { isActive } from '../presentation';
import { mergeEvents, type DetailTab, type Progress, type TaskEvent, type TaskLog, type WindowMode } from './model';

type DetailApi = Pick<typeof tasksApi, 'detail' | 'progress' | 'events' | 'logs'>;
type ReadMode = 'tail' | 'start' | 'next' | 'incremental';
const message = (error: unknown): string => error instanceof Error ? error.message : '读取失败，请重试';

/** 每个详情实例拥有自己的请求代次、游标和轮询，不读取旧页面全局状态。 */
export function useTaskDetail(api: DetailApi = tasksApi, onTerminal: () => void = () => {}) {
  const opened = ref(false);
  const visible = ref(true);
  const taskId = ref<TaskId | null>(null);
  const runId = ref<TaskId | null>(null);
  const task = shallowRef<OperationTask | null>(null);
  const progress = shallowRef<Progress | null>(null);
  const events = shallowRef<TaskEvent[]>([]);
  const logs = shallowRef<TaskLog[]>([]);
  const tab = ref<DetailTab>('events');
  const stepFilter = ref<string | null>(null);
  const error = ref('');
  const progressError = ref('');
  const eventsError = ref('');
  const logsError = ref('');
  const loading = ref(false);
  const eventsLoading = ref(false);
  const logsLoading = ref(false);
  const eventCursor = ref<TaskId | null>(null);
  const logCursor = ref<number | null>(null);
  const eventsMode = ref<WindowMode>('tail');
  const logsMode = ref<WindowMode>('tail');
  const eventsEarlier = ref(false);
  const eventsMore = ref(false);
  const logsEarlier = ref(false);
  const logsMore = ref(false);
  const logsAvailable = ref(true);
  const runs = computed(() => task.value?.runs || []);
  const selectedRun = computed(() => runs.value.find(run => sameTaskId(run.id,runId.value)));
  let generation = 0;
  let eventRequest = 0;
  let logRequest = 0;
  let refreshRequest = 0;
  let pendingRefresh: Promise<void> | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let controller = new AbortController();
  let terminalNotified = false;

  function stopTimer() { if (timer !== undefined) clearTimeout(timer); timer = undefined; }
  function invalidate() {
    generation += 1;
    controller.abort();
    controller = new AbortController();
    pendingRefresh = null;
    loading.value = eventsLoading.value = logsLoading.value = false;
    stopTimer();
  }
  const current = (version: number) => version === generation && opened.value;
  const canRead = () => opened.value && visible.value && !!taskId.value;
  function schedule() {
    stopTimer();
    if (canRead() && (!task.value || isActive(task.value))) timer = setTimeout(() => void requestRefresh(true), 2000);
  }
  function clearRun() {
    eventRequest += 1;
    logRequest += 1;
    eventsLoading.value = logsLoading.value = false;
    progress.value = null;
    progressError.value = eventsError.value = logsError.value = '';
    events.value = [];
    logs.value = [];
    eventCursor.value = logCursor.value = null;
    eventsEarlier.value = eventsMore.value = logsEarlier.value = logsMore.value = false;
    eventsMode.value = logsMode.value = 'tail';
    logsAvailable.value = true;
  }

  async function loadEvents(mode: ReadMode = 'incremental') {
    if (!canRead() || !runId.value || !taskId.value) return;
    if (mode === 'incremental' && eventsLoading.value) return;
    if (mode === 'incremental' && eventsMode.value === 'start' && eventsMore.value) return;
    if (mode === 'next' && !eventsMore.value) return;
    const version = generation;
    const request = ++eventRequest;
    const first = mode === 'tail' || mode === 'start' || eventCursor.value === null;
    const query = { limit: 500, ...(mode === 'start' ? { after_id: 0 }
      : mode !== 'tail' && eventCursor.value !== null ? { after_id: eventCursor.value } : {}) };
    eventsLoading.value = true;
    try {
      const result = await api.events(taskId.value, runId.value, query, controller.signal);
      if (!current(version) || request !== eventRequest) return;
      events.value = first ? result.items : mergeEvents(events.value, result.items);
      eventCursor.value = result.next_after_id;
      if (mode === 'tail' || mode === 'start') eventsMode.value = mode;
      // 最近页的 has_more 指向更早历史，不能拿 forward cursor 继续翻它。
      if (first && eventsMode.value === 'tail') {
        eventsEarlier.value = result.has_more;
        eventsMore.value = false;
      } else {
        eventsMore.value = result.has_more;
        if (eventsMode.value === 'start') eventsEarlier.value = false;
      }
      eventsError.value = '';
    } catch (cause) { if (current(version) && request === eventRequest) eventsError.value = message(cause); }
    finally { if (current(version) && request === eventRequest) eventsLoading.value = false; }
  }

  async function loadLogs(mode: ReadMode = 'incremental') {
    if (!canRead() || !runId.value || !taskId.value) return;
    if (mode === 'incremental' && logsLoading.value) return;
    if (mode === 'incremental' && logsMode.value === 'start' && logsMore.value) return;
    if (mode === 'next' && !logsMore.value) return;
    const version = generation;
    const request = ++logRequest;
    const first = mode === 'tail' || mode === 'start' || logCursor.value === null;
    const query = { limit: 500, ...(mode === 'start' ? { cursor: 0 }
      : mode !== 'tail' && logCursor.value !== null ? { cursor: logCursor.value } : {}) };
    logsLoading.value = true;
    try {
      const result = await api.logs(taskId.value, runId.value, query, controller.signal);
      if (!current(version) || request !== logRequest) return;
      logs.value = first ? result.items : [...logs.value, ...result.items];
      logCursor.value = result.next_cursor;
      if (mode === 'tail' || mode === 'start') logsMode.value = mode;
      logsMore.value = result.has_more;
      // 文件尾读不返回起始字节，提供明确的从头入口而不猜是否还有早期行。
      logsEarlier.value = logsMode.value === 'tail' && result.available;
      logsAvailable.value = result.available;
      logsError.value = '';
    } catch (cause) { if (current(version) && request === logRequest) logsError.value = message(cause); }
    finally { if (current(version) && request === logRequest) logsLoading.value = false; }
  }

  async function refreshProgress(version: number) {
    if (!taskId.value || !runId.value) return;
    try {
      const result = await api.progress(taskId.value, runId.value, controller.signal);
      if (!current(version)) return;
      progress.value = result.progress;
      progressError.value = '';
    } catch (cause) { if (current(version)) progressError.value = message(cause); }
  }

  function refresh() { return requestRefresh(false); }
  function requestRefresh(automatic: boolean) {
    if (!canRead() || !taskId.value) return Promise.resolve();
    // 自动轮询保留界面状态；手动刷新可等待同一请求并显示加载反馈。
    if (!automatic) loading.value = true;
    if (pendingRefresh) return pendingRefresh;
    const version = generation;
    const request = ++refreshRequest;
    pendingRefresh = readDetail(version, request).finally(() => {
      if (current(version) && request === refreshRequest) { pendingRefresh = null; loading.value = false; schedule(); }
    });
    return pendingRefresh;
  }

  async function readDetail(version: number, request: number) {
    if (!taskId.value) return;
    stopTimer();
    try {
      const result = await api.detail(taskId.value, controller.signal);
      if (!current(version) || request !== refreshRequest) return;
      task.value = result.task;
      const available = result.task.runs || [];
      if (runId.value && !available.some(run => sameTaskId(run.id,runId.value))) {
        // 明确请求的历史 Run 不可用时不能代换成另一轮结果。
        clearRun();
        error.value = `所选运行 #${runId.value} 不存在或已不可用，请选择其他运行。`;
        return;
      }
      const desired = runId.value || result.task.last_run_id || available.at(-1)?.id || null;
      const next = available.some(run => sameTaskId(run.id,desired)) ? desired : available.at(-1)?.id || null;
      if (next !== runId.value) { clearRun(); runId.value = next; }
      error.value = '';
      if (runId.value) {
        await Promise.allSettled([refreshProgress(version), loadEvents(), ...(tab.value === 'logs' ? [loadLogs()] : [])]);
      }
      if (!current(version)) return;
      if (!isActive(result.task) && !terminalNotified) { terminalNotified = true; onTerminal(); }
    } catch (cause) { if (current(version)) error.value = message(cause); }
  }

  function open(id: TaskId, desiredRun?: TaskId | null, filter?: string | null) {
    invalidate();
    opened.value = true;
    taskId.value = normalizeTaskId(id);
    runId.value = optionalTaskId(desiredRun);
    task.value = null;
    error.value = '';
    tab.value = 'events';
    stepFilter.value = filter || null;
    terminalNotified = false;
    clearRun();
    return refresh();
  }
  function close() { opened.value = false; invalidate(); }
  function selectRun(id: TaskId) {
    id=normalizeTaskId(id);
    if (sameTaskId(id,runId.value)) return;
    invalidate();
    runId.value = id;
    stepFilter.value = null;
    clearRun();
    return refresh();
  }
  function selectTab(value: DetailTab) {
    tab.value = value;
    if (value === 'logs') return loadLogs();
  }
  function setVisible(value: boolean) {
    if (visible.value === value) return;
    visible.value = value;
    if (!value) invalidate();
    else if (opened.value) void refresh();
  }
  onScopeDispose(close);
  return { opened, taskId, runId, task, runs, selectedRun, progress, events, logs, tab, stepFilter,
    error, progressError, eventsError, logsError, loading, eventsLoading, logsLoading,
    eventsMode, logsMode, eventsEarlier, eventsMore, logsEarlier, logsMore, logsAvailable,
    open, close, selectRun, selectTab, setVisible, refresh, loadEvents, loadLogs };
}
