<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { admissionText, formatDateTime, formatDuration, label, statusTone } from '../presentation';
import { artifactUrl, eventState, matchesStep, meaningfulDetail, object, orderedEvents, progressLabel, stepId, stepLabel, strings, text, type DetailTab, type TaskEvent } from './model';
import {sameTaskId,type TaskId} from '../../../api/taskIds';
import { useTaskDetail } from './useTaskDetail';
import TaskProgress from './TaskProgress.vue';
import TaskFailure from './TaskFailure.vue';
import './detail.css';

const emit = defineEmits<{ close: []; refresh: [] }>();
const detail = useTaskDetail(undefined, () => emit('refresh'));
const { opened, taskId, runId, task, runs, selectedRun, progress, events, logs, tab, stepFilter, error,
  progressError, eventsError, logsError, loading, eventsLoading, logsLoading, eventsMode, logsMode,
  eventsEarlier, eventsMore, logsEarlier, logsMore, logsAvailable } = detail;
const dialog = ref<HTMLDialogElement>();
const scroller = ref<HTMLElement>();
const newItems = ref(0);
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
const tabs: { id: DetailTab; label: string }[] = [{ id: 'events', label: '事件时间线' }, { id: 'logs', label: '运行日志' }, { id: 'artifacts', label: '诊断资源' }];
const steps = computed(() => progress.value?.main_steps || []);
const selectedStep = computed(() => steps.value.find(step => stepId(step) === stepFilter.value || !!(stepFilter.value && step.raw_stages?.includes(stepFilter.value))));
const filteredEvents = computed(() => orderedEvents(events.value.filter(event => matchesStep(event, stepFilter.value, steps.value))));
const filteredLogs = computed(() => logs.value.filter(item => matchesStep(item, stepFilter.value, steps.value, true)));
// 模板更新（读取状态、页签、滚动提示）不重复格式化整页事件和技术证据。
const eventRows = computed(() => filteredEvents.value.map(event => {
  const state = eventState(event);
  const fields = meaningfulDetail(event.detail);
  return { event, state, timestamp: formatDateTime(event.created_at),
    stageLabel: event.stage_label || label('stage', event.stage), association: eventAssociation(event),
    stateLabel: state ? progressLabel(state) : '记录', detailJson: fields ? JSON.stringify(fields, null, 2) : null };
}));
const logRows = computed(() => filteredLogs.value.map(item => {
  const fields = meaningfulDetail(item.fields);
  return { item, timestamp: item.ts ? formatDateTime(item.ts) : '时间缺失',
    detailJson: fields ? JSON.stringify(fields, null, 2) : null };
}));
const runSummary = computed(() => runId.value ? selectedRun.value : task.value);
const target = computed(() => task.value?.email_snapshot || task.value?.email || (task.value?.account_id ? `账号 #${task.value.account_id}` : task.value?.target_id || '执行记录与诊断'));
const resources = computed(() => (task.value?.resources || []).filter(item => !runId.value || sameTaskId(item.run_id,runId.value)));
const debug = computed(() => selectedRun.value?.debug_artifacts);
const pause = computed(() => object(selectedRun.value?.debug_pause || progress.value?.debug_pause));
let returnFocus: HTMLElement | null = null;
let changingWindow = false;

function eventAssociation(event: TaskEvent): string {
  const detailFields = object(event.detail);
  const mainStep = text(event.main_step_id || detailFields.main_step_id);
  const rawStage = text(event.raw_stage || detailFields.raw_stage || event.stage);
  let associated = steps.value.filter(step => mainStep ? stepId(step) === mainStep : step.raw_stages?.includes(rawStage));
  if (associated.length !== 1) {
    const eid = text(event.event_id || event.id);
    if (eid) {
      const byEventId = steps.value.filter(step => strings(step.event_ids).includes(eid));
      if (byEventId.length === 1) associated = byEventId;
    }
  }
  if (associated.length !== 1 && (rawStage === 'nested_live_check'
      || ((rawStage === 'remote_request' || rawStage === 'reconcile') && text(detailFields.action) === 'token_refresh'))) {
    const fallback = steps.value.find(step => stepId(step) === 'refresh_token')
      || steps.value.find(step => stepId(step) === 'access_token')
      || steps.value.find(step => stepId(step) === 'authenticate');
    if (fallback) return stepLabel(fallback);
  }
  if (associated.length !== 1 && (rawStage === 'queued' || text(event.event_type).startsWith('run.'))) {
    return '运行状态';
  }
  return associated.length === 1 ? stepLabel(associated[0]!) : '未关联步骤';
}
function finishClose() {
  if (!opened.value) return;
  detail.close();
  if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
  returnFocus = null;
  emit('close');
}
function close() { dialog.value?.close(); finishClose(); }
async function open(id: TaskId, desiredRun?: TaskId | null, filter?: string | null) {
  if (!opened.value) returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  newItems.value = 0;
  detail.setVisible(!document.hidden);
  const pending = detail.open(id, desiredRun, filter);
  await nextTick();
  if (!dialog.value?.open && opened.value) dialog.value?.showModal();
  return pending;
}
function setVisible(value: boolean) { detail.setVisible(value); }
function visibilityChanged() { setVisible(!document.hidden); }
function selectRun(event: Event) {
  newItems.value = 0;
  void detail.selectRun((event.target as HTMLSelectElement).value);
}
async function selectTab(value: DetailTab) {
  newItems.value = 0;
  await detail.selectTab(value);
  await nextTick();
  if (scroller.value) scroller.value.scrollTop = 0;
}
function tabKeys(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const index = tabs.findIndex(item => item.id === tab.value);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
    : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
  event.preventDefault();
  void selectTab(tabs[next]!.id);
  (event.currentTarget as HTMLElement).querySelector<HTMLButtonElement>(`[data-detail-tab="${tabs[next]!.id}"]`)?.focus();
}
async function loadWindow(mode: 'tail' | 'start' | 'next') {
  changingWindow = true;
  if (tab.value === 'events') await detail.loadEvents(mode);
  else await detail.loadLogs(mode);
  await nextTick();
  if (scroller.value && mode !== 'next') scroller.value.scrollTop = mode === 'tail' ? scroller.value.scrollHeight : 0;
  newItems.value = 0;
  changingWindow = false;
}
function scrollLatest() { if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight; newItems.value = 0; }
function scrollFromHeader(event: WheelEvent) {
  const panel = scroller.value;
  // 矮屏允许整个详情滚动，标题区滚轮交给外层，保证底部控件可达。
  if (dialog.value && dialog.value.scrollHeight > dialog.value.clientHeight + 1) return;
  if (event.defaultPrevented || (event.target instanceof Element && event.target.closest('.tc-step-dialog'))) return;
  if (!panel || event.ctrlKey || event.shiftKey || panel.contains(event.target as Node) || !event.deltaY) return;
  if (panel.scrollHeight <= panel.clientHeight) return;
  event.preventDefault();
  panel.scrollTop += event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? panel.clientHeight : 1);
}
watch([events, logs], async ([nextEvents, nextLogs], [oldEvents, oldLogs]) => {
  if (changingWindow) return;
  const panel = scroller.value;
  const atEnd = !panel || panel.scrollTop + panel.clientHeight >= panel.scrollHeight - 40;
  const added = tab.value === 'events' ? nextEvents.length - oldEvents.length : tab.value === 'logs' ? nextLogs.length - oldLogs.length : 0;
  if (added <= 0) return;
  await nextTick();
  if (atEnd) scrollLatest();
  else newItems.value += added;
});
watch(stepFilter, () => { newItems.value = 0; if (scroller.value) scroller.value.scrollTop = 0; });
onMounted(() => { visibilityChanged(); document.addEventListener('visibilitychange', visibilityChanged); });
onBeforeUnmount(() => { document.removeEventListener('visibilitychange', visibilityChanged); dialog.value?.close(); });
defineExpose({ open, close, setVisible });
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="tc-detail-dialog" aria-labelledby="tc-detail-title" @cancel.prevent="close" @close="finishClose" @wheel="scrollFromHeader">
      <header class="tc-detail-header">
        <h2 id="tc-detail-title">任务 #{{ taskId }} <span v-if="task">{{ label('task_type', task.task_type) }}</span></h2>
        <span class="tc-detail-target" :title="String(target)" tabindex="0">{{ target }}</span>
        <div v-if="runSummary" class="tc-detail-status" :class="`tc-detail-status--${statusTone(runSummary.status)}`"><strong>{{ label('status', runSummary.status) }}</strong><span>耗时 {{ formatDuration(runSummary.duration_ms) }}</span></div>
        <label v-if="task" class="tc-detail-run"><span>运行</span><select :value="runId || ''" aria-label="选择执行实例" :disabled="runs.length < 2 && (!runId || !!selectedRun)" @change="selectRun"><option v-if="runId && !selectedRun" :value="runId" disabled>运行 #{{ runId }} 不可用</option><option v-else-if="!runs.length" value="">暂无运行</option><option v-for="run in runs" :key="run.id" :value="run.id">第 {{ run.run_no || '—' }} 次 · {{ label('status', run.status) }}</option></select></label>
        <div class="tc-detail-header-actions"><button type="button" :disabled="loading" @click="detail.refresh">{{ loading ? '刷新中…' : '刷新' }}</button><button type="button" autofocus aria-label="关闭任务详情" @click="close">关闭</button></div>
      </header>
      <div v-if="error" class="tc-detail-error" role="alert">读取任务失败：{{ error }}<span v-if="task">。保留上次已读取的记录。</span><button type="button" :disabled="loading" @click="detail.refresh">重试</button></div>
      <div v-if="loading && !task" class="tc-detail-empty" role="status">正在读取任务详情…</div>
      <template v-if="task">
        <p v-if="runSummary?.status === 'queued'" class="tc-detail-notice">{{ admissionText(runSummary) }}</p>
        <p v-if="pause.state === 'paused'" class="tc-detail-notice">调试暂停，等待结束调试。<template v-if="pause.hold_until">保留至 {{ formatDateTime(pause.hold_until) }}。</template></p>
        <TaskFailure v-if="!progress" :execution="runSummary" :status="runSummary?.status" />
        <TaskProgress :progress="progress" :task-type="task?.task_type" :execution="runSummary" :filter="stepFilter" :active="opened" :context="`${taskId}:${runId}`" @filter="value => stepFilter = value" @child="open" />
        <p v-if="progressError" class="tc-detail-error" role="status">进度读取失败：{{ progressError }}<template v-if="progress">；保留上次快照</template></p>
        <div class="tc-detail-view-toolbar">
          <div class="tc-detail-tabs" role="tablist" aria-label="任务详情视图" @keydown="tabKeys"><button v-for="item in tabs" :id="`tc-detail-tab-${item.id}`" :key="item.id" type="button" role="tab" :data-detail-tab="item.id" :aria-selected="tab === item.id" :aria-controls="`tc-detail-panel-${item.id}`" :tabindex="tab === item.id ? 0 : -1" @click="selectTab(item.id)">{{ item.label }}</button></div>
          <div class="tc-detail-filter" :class="{ 'is-active': !!stepFilter }"><span>当前查看：<strong>{{ selectedStep ? stepLabel(selectedStep) : stepFilter || '全流程' }}</strong></span><button v-if="stepFilter" type="button" @click="stepFilter = null">清除步骤筛选</button></div>
          <div v-if="tab !== 'artifacts'" class="tc-detail-read-toolbar"><button type="button" :aria-pressed="(tab === 'events' ? eventsMode : logsMode) === 'start'" :disabled="eventsLoading || logsLoading || !runId" @click="loadWindow('start')">从头加载</button><button type="button" :aria-pressed="(tab === 'events' ? eventsMode : logsMode) === 'tail'" :disabled="eventsLoading || logsLoading || !runId" @click="loadWindow('tail')">最近记录</button></div>
        </div>
        <div ref="scroller" class="tc-detail-content">
          <section v-show="tab === 'events'" id="tc-detail-panel-events" role="tabpanel" aria-labelledby="tc-detail-tab-events" tabindex="0">
            <p v-if="eventsError" class="tc-detail-error" role="alert">事件读取失败：{{ eventsError }}<button type="button" :disabled="eventsLoading" @click="detail.loadEvents()">重试</button></p>
            <p v-if="eventsEarlier" class="tc-detail-notice">当前展示最近记录；更早历史可通过“从头加载”读取。</p>
            <div v-if="!filteredEvents.length" class="tc-detail-empty" role="status">{{ eventsLoading ? '正在读取事件…' : stepFilter ? '当前步骤暂无关联事件' : '此运行暂无事件' }}</div>
            <article v-for="row in eventRows" :key="row.event.id" :class="['tc-event', { 'tc-event--error': row.state === 'failed', 'tc-event--success': row.state === 'success' || row.state === 'recovered', 'tc-event--running': row.state === 'running', 'tc-event--warning': ['stopped', 'interrupted', 'debug_paused', 'attention_required', 'queued'].includes(row.state) }]">
              <div class="tc-event-meta"><time>{{ row.timestamp }}</time><span class="tc-event-level" :data-level="(row.event.level || 'INFO').toUpperCase()">{{ row.event.level || 'INFO' }}</span><strong class="tc-event-stage">{{ row.stageLabel }}</strong><span v-if="row.association" class="tc-event-step">{{ row.association }}</span><span class="tc-event-state" :data-state="row.state || 'info'">{{ row.stateLabel }}</span><small class="tc-event-id">事件 {{ row.event.event_id || row.event.id }}</small></div>
              <p>{{ row.event.message || '—' }}</p><details v-if="row.detailJson" class="tc-technical"><summary>技术详情</summary><pre>{{ row.detailJson }}</pre></details>
            </article>
            <button v-if="eventsMore" class="tc-load-more" type="button" :disabled="eventsLoading" @click="loadWindow('next')">{{ eventsLoading ? '正在读取…' : '继续加载后续事件' }}</button>
          </section>
          <section v-show="tab === 'logs'" id="tc-detail-panel-logs" role="tabpanel" aria-labelledby="tc-detail-tab-logs" tabindex="0">
            <p v-if="logsError" class="tc-detail-error" role="alert">日志读取失败：{{ logsError }}<button type="button" :disabled="logsLoading" @click="detail.loadLogs()">重试</button></p>
            <p v-if="logsEarlier" class="tc-detail-notice">正在查看文件尾部；“从头加载”将按顺序分页读取。</p>
            <div v-if="!filteredLogs.length" class="tc-detail-empty" role="status">{{ logsLoading ? '正在读取运行日志…' : !logsAvailable ? '当前 Run 暂无技术日志，历史任务可能只有事件时间线' : stepFilter ? '当前步骤暂无关联运行日志' : '此运行暂无日志' }}</div>
            <article v-for="(row, index) in logRows" :key="`${row.item.event_uuid || row.item.event_id || ''}:${row.item.ts}:${index}`" class="tc-log-line" :data-level="(row.item.level || 'INFO').toUpperCase()">
              <div class="tc-event-meta"><time>{{ row.timestamp }}</time><strong class="tc-log-level" :data-level="(row.item.level || 'INFO').toUpperCase()">{{ row.item.level || 'INFO' }}</strong><span class="tc-log-stage">{{ row.item.stage_label || row.item.stage || '未关联步骤' }}</span></div><p>{{ row.item.message }}</p><details v-if="row.detailJson" class="tc-technical"><summary>技术详情</summary><pre>{{ row.detailJson }}</pre></details>
            </article>
            <button v-if="logsMore" class="tc-load-more" type="button" :disabled="logsLoading" @click="loadWindow('next')">{{ logsLoading ? '正在读取…' : '继续加载后续日志' }}</button>
          </section>
          <section v-show="tab === 'artifacts'" id="tc-detail-panel-artifacts" role="tabpanel" aria-labelledby="tc-detail-tab-artifacts" tabindex="0">
            <article v-if="debug?.available" class="tc-artifact"><h3>Roxy 刷新调试</h3><p>{{ debug.state === 'recording' ? '正在抓包' : '诊断已保存' }} · 请求 {{ object(debug.summary).request_count || 0 }} 条</p><p v-if="selectedRun?.result_summary?.debug_browser_kept === true">失败窗口已保留，可在 Roxy 中查看。</p><div class="tc-artifact-links"><a v-if="artifactUrl(debug.har_url)" :href="artifactUrl(debug.har_url)!" download>下载 HAR</a><a v-if="artifactUrl(debug.page_state_url)" :href="artifactUrl(debug.page_state_url)!" download>下载页面现场</a><a v-if="artifactUrl(debug.screenshot_url)" :href="artifactUrl(debug.screenshot_url)!" target="_blank" rel="noopener">查看失败截图</a></div></article>
            <article v-for="(resource, index) in resources" :key="text(resource.id) || index" class="tc-artifact"><h3>{{ resource.resource_type || '运行资源' }}</h3><p>{{ resource.provider || resource.state || '—' }}</p><small>{{ formatDateTime(resource.acquired_at || resource.created_at) }}</small></article>
            <div v-if="!debug?.available && !resources.length" class="tc-detail-empty">当前 Run 没有诊断资源或产物</div>
            <details v-if="runSummary?.result_summary" class="tc-technical"><summary>执行结果字段</summary><pre>{{ JSON.stringify(runSummary.result_summary, null, 2) }}</pre></details>
          </section>
        </div>
        <footer class="tc-detail-footer"><small>时间按浏览器时区显示 · {{ timezone }}</small><button v-if="newItems && tab !== 'artifacts'" type="button" @click="scrollLatest">有 {{ newItems }} 条新记录，回到底部</button><small v-else-if="loading || eventsLoading || logsLoading" role="status">正在同步记录…</small></footer>
      </template>
    </dialog>
  </Teleport>
</template>
