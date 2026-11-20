<script setup lang="ts">
import {computed, nextTick, ref, watch} from 'vue';
import {tasksApi, type OperationTask, type TaskAction, type TaskFilters, type TaskId} from '../../api/tasks';
import TaskDetail from './detail/TaskDetail.vue';
import TaskFiltersMenu from './TaskFilters.vue';
import {clearColumnFilter, filterColumns, filterSummary, isFilterActive} from './filterDefinitions';
import TaskTable from './TaskTable.vue';
import ListPagination from '../../components/ListPagination.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import StatusBadge from '../../components/StatusBadge.vue';
import {eligible, isActive, record} from './presentation';
import {useTaskList} from './useTaskList';
import {useReceipts, type AcceptedReference} from './useReceipts';
import '../../styles/task-center.css';

const emit = defineEmits<{navigate: []; batch: [string, string?]; changed: []}>();
const list = useTaskList(), receipts = useReceipts();
const {filters, page, size, pages, total, items, facets, selected, loading, error, visible} = list;
const {items: receiptItems, pending: pendingReceipts, error: receiptError, loading: receiptsLoading} = receipts;
const detail = ref<InstanceType<typeof TaskDetail> | null>(null);
const table = ref<InstanceType<typeof TaskTable> | null>(null);
const busy = ref(false), notice = ref(''), actionError = ref('');
const openFilter = ref<string | null>(null);
watch(openFilter, key => {
  list.setFacetsVisible(key === 'mobile' || filterColumns.some(column => column.key === key && column.kind === 'select'));
});
const activeFilters = computed(() => filterColumns.filter(column => isFilterActive(column, filters)));
const filterChips = computed(() => activeFilters.value.map(column => ({key: column.key,
  label: `${column.label}：${filterSummary(column, filters, facets.value)}`,
  removeLabel: `清除${column.label}筛选`,
})));
const skipped = ref<{id: TaskId; message: string}[]>([]);
const selectedRows = computed(() => items.value.filter(task => selected.value.has(task.id)));
const counts = computed(() => Object.fromEntries((['retry', 'cancel', 'terminate', 'delete'] as TaskAction[])
  .map(action => [action, selectedRows.value.filter(task => eligible(task, action)).length])));
const labels: Record<TaskAction, string> = {retry: '重跑', cancel: '取消排队', terminate: '终止运行', delete: '删除'};
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
function updateFilters(value: TaskFilters) { Object.assign(filters, value); }
function removeFilter(key: string) {
  const column = filterColumns.find(column => column.key === key);
  if (column) updateFilters(clearColumnFilter(column, filters));
}
function openDetail(taskId: TaskId, runId?: TaskId | null, stepId?: string | null) { detail.value?.open(taskId, runId, stepId); }
async function open(options: {filters?: Partial<TaskFilters>; taskId?: TaskId; runId?: TaskId | null; stepId?: string | null} = {}) {
  if (options.filters) list.applyFilters(options.filters);
  if (options.taskId) { await nextTick(); openDetail(options.taskId, options.runId, options.stepId); }
}
function setVisible(value: boolean) { if (!value) openFilter.value = null; list.setVisible(value); receipts.setVisible(value); }
function closeDetail() { detail.value?.close(); }
function track(references: AcceptedReference[], title = '任务', options: {navigate?: boolean} = {}) {
  receipts.track(references, title);
  if (options.navigate !== false) emit('navigate');
}
async function refresh(options: {metadata?: boolean} = {}) {
  // 其他业务页只标记列表待刷新，返回任务中心时统一读取。
  if (visible.value) await list.refresh(options);
}
function changed() { void refresh(); emit('changed'); }
async function action(task: OperationTask, action: TaskAction) {
  if (busy.value) return;
  if (action === 'delete' && isActive(task)) return;
  if (action !== 'retry') {
    const text = action === 'delete' ? `确定删除任务 #${task.id}？\n\n任务会从任务中心隐藏，历史审计记录仍会保留。`
      : task.status === 'queued' ? `确定取消排队中的任务 #${task.id}？`
        : `确定终止任务 #${task.id}？\n\n任务会立即收口，已发出的远端请求证据会保留。`;
    if (!window.confirm(text)) return;
  }
  busy.value = true; actionError.value = ''; skipped.value = []; notice.value = '';
  try {
    const result = await tasksApi.action(task.id, action);
    const response = record(result.data || result);
    notice.value = action === 'retry' ? response.round_id || response.bulk_round_id ? '重跑已受理，已创建所属批次的新轮次' : '任务已重新入队'
      : action === 'delete' ? '任务已删除' : result.state === 'cancelled' ? '任务已取消' : '任务已终止，原请求证据已保留';
    selected.value.delete(task.id);
    await refresh();
    emit('changed');
  } catch (cause) { actionError.value = `${labels[action]}失败：${cause instanceof Error ? cause.message : String(cause)}`; }
  finally { busy.value = false; }
}
async function bulk(action: TaskAction) {
  if (busy.value) return;
  const targets = selectedRows.value.filter(task => eligible(task, action));
  if (!targets.length) return;
  const help = action === 'retry' ? '原任务记录和运行日志会保留，废号或无重跑来源的任务会跳过。'
    : action === 'cancel' ? '只取消尚未开始的排队任务。' : action === 'delete'
      ? '任务会从任务中心隐藏，历史审计记录仍会保留。' : '运行中的任务会立即收口，已发出的远端请求证据会保留。';
  if (!window.confirm(`确定${labels[action]}选中的 ${targets.length} 个任务吗？\n\n${help}`)) return;
  busy.value = true; actionError.value = ''; notice.value = ''; skipped.value = [];
  try {
    const result = await tasksApi.bulk(action, targets.map(task => task.id));
    const accepted = Array.isArray(result.accepted) ? result.accepted : [];
    skipped.value = (result.skipped || []).map(item => ({id: item.task_id, message: item.error || item.message || '操作未接受'}));
    const acceptedCount = Number(result.accepted_count ?? accepted.length);
    if (action === 'cancel') {
      const cancelled = accepted.filter(item => item.state === 'cancelled').length;
      const cancelling = accepted.filter(item => item.state === 'cancelling').length;
      notice.value = `已取消 ${cancelled} 个，取消中 ${cancelling} 个${acceptedCount - cancelled - cancelling > 0 ? `，已受理 ${acceptedCount - cancelled - cancelling} 个` : ''}`;
      const acceptedIds = new Set(accepted.map(item => String(item.task_id)));
      selected.value = new Set([...selected.value].filter(id => !acceptedIds.has(String(id))));
    } else { notice.value = `已${labels[action]} ${acceptedCount} 个`; selected.value = new Set(); }
    if (skipped.value.length) notice.value += `，跳过 ${skipped.value.length} 个`;
    await refresh(); emit('changed');
  } catch (cause) { actionError.value = `${labels[action]}失败：${cause instanceof Error ? cause.message : String(cause)}`; }
  finally { busy.value = false; }
}
defineExpose({open, refresh, track, closeDetail, setVisible});
</script>
<template>
  <section v-show="visible" class="tc-root" aria-label="统一任务中心">
    <section v-if="receiptItems.length" class="tc-receipts" aria-label="本次提交的任务回执">
      <div class="tc-receipts-header"><div><strong>本次提交</strong><span role="status">共 {{ receiptItems.length }} 项 · 等待/执行 {{ pendingReceipts.length }} · 成功 {{ receiptItems.filter(item => item.status === 'success').length }} · 失败或待处理 {{ receiptItems.length - pendingReceipts.length - receiptItems.filter(item => item.status === 'success').length }}</span></div><button type="button" class="tc-button" :disabled="receiptsLoading || !pendingReceipts.length" @click="receipts.refresh()">刷新回执</button></div>
      <p v-if="receiptError" class="tc-text-danger" role="alert">{{ receiptError }}</p>
      <details><summary>查看任务与最终结果</summary><ul class="tc-receipt-list"><li v-for="item in receiptItems" :key="`${item.task_id}:${item.run_id}`"><button type="button" class="tc-link" @click="openDetail(item.task_id, item.run_id)">{{ item.label }} #{{ item.task_id }}</button><StatusBadge :value="item.status"/><span>{{ item.message }}</span></li></ul></details>
    </section>
    <div class="tc-workspace">
      <div class="tc-toolbar" :class="{'tc-toolbar--filtered': activeFilters.length}">
        <div class="tc-toolbar-main">
          <div class="tc-selection" role="status">{{ selectedRows.length ? `已选 ${selectedRows.length} 项` : `${total.toLocaleString()} 个任务` }}</div>
          <ListFilterSummary :items="filterChips" @remove="removeFilter"/>
        </div>
        <div v-if="selectedRows.length" class="tc-bulk-actions"><button v-for="kind in (['retry', 'cancel', 'terminate', 'delete'] as TaskAction[])" :key="kind" type="button" class="tc-button" :class="{'tc-button-danger': kind === 'delete' || kind === 'terminate'}" :disabled="busy || !counts[kind]" @click="bulk(kind)">{{ labels[kind] }}{{ counts[kind] ? `（${counts[kind]}）` : '' }}</button></div>
        <div class="tc-toolbar-end"><TaskFiltersMenu :model-value="filters" :facets="facets" :open="openFilter === 'mobile'" @update:model-value="updateFilters" @update:open="openFilter = $event ? 'mobile' : null"/><button v-if="activeFilters.length" type="button" class="tc-link" @click="list.applyFilters({})">清除全部筛选</button><span class="tc-timezone" :title="timezone">时间按 {{ timezone }} 显示</span><button type="button" class="tc-link" @click="table?.resetColumns()">恢复列宽</button></div>
      </div>
      <div v-if="notice || actionError || (error && items.length)" class="tc-feedback" :class="{'tc-feedback-error': actionError || error}" :role="actionError || error ? 'alert' : 'status'">{{ actionError || error || notice }}<button v-if="error" type="button" class="tc-link" @click="list.refresh()">重试</button><details v-if="skipped.length"><summary>查看跳过原因</summary><ul><li v-for="item in skipped" :key="item.id">#{{ item.id }}：{{ item.message }}</li></ul></details></div>
      <TaskTable ref="table" :filters="filters" :facets="facets" v-model:open-filter="openFilter" @update:filters="updateFilters" :items="items" :selected="selected" :loading="loading" :error="error" :busy="busy" @select="list.toggle" @select-page="list.togglePage" @detail="openDetail" @action="action" @batch="(id, round) => emit('batch', id, round)" @retry="list.refresh()"/>
      <ListPagination v-model:page="page" v-model:size="size" :pages="pages" :total="total" :busy="loading"/>
    </div>
  </section>
  <TaskDetail ref="detail" @refresh="changed"/>
</template>
