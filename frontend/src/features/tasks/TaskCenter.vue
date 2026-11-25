<script setup lang="ts">
import {computed, nextTick, onBeforeUnmount, ref, watch} from 'vue';
import {tasksApi, type OperationTask, type TaskAction, type TaskFilters, type TaskId} from '../../api/tasks';
import {BulkMutationPendingError} from '../../api/bulkMutations';
import TaskDetail from './detail/TaskDetail.vue';
import TaskFiltersMenu from './TaskFilters.vue';
import {clearColumnFilter, filterColumns, filterSummary, isFilterActive} from './filterDefinitions';
import TaskTable from './TaskTable.vue';
import ListPagination from '../../components/ListPagination.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListToolbar from '../../components/ListToolbar.vue';
import {eligible, isActive, record} from './presentation';
import {useTaskList} from './useTaskList';
import '../../styles/task-center.css';

const emit = defineEmits<{batch: [string, string?]; changed: []}>();
const list = useTaskList();
const {filters, page, size, pages, total, items, facets, selected, loading, error, visible} = list;
const detail = ref<InstanceType<typeof TaskDetail> | null>(null);
const table = ref<InstanceType<typeof TaskTable> | null>(null);
const busy = ref(false), notice = ref(''), actionError = ref('');
const openFilter = ref<string | null>(null);
const targetInput = ref<HTMLInputElement | null>(null);
const targetDraft = ref(filters.target || '');
let targetTimer: ReturnType<typeof setTimeout> | undefined;
watch(() => filters.target, value => {
  clearTimeout(targetTimer);
  targetDraft.value = value || '';
});
onBeforeUnmount(() => clearTimeout(targetTimer));
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
function commitTarget(rawValue: string) {
  clearTimeout(targetTimer);
  const next = rawValue.trim();
  if (next === (filters.target || '')) return;
  updateFilters({...filters, target: next});
}
function onTargetInput(value: string) {
  targetDraft.value = value;
  clearTimeout(targetTimer);
  targetTimer = setTimeout(() => commitTarget(value), 250);
}
function clearTargetSearch() {
  clearTimeout(targetTimer);
  targetDraft.value = '';
  commitTarget('');
  targetInput.value?.focus();
}
function removeFilter(key: string) {
  const column = filterColumns.find(column => column.key === key);
  if (column) updateFilters(clearColumnFilter(column, filters));
}
function openDetail(taskId: TaskId, runId?: TaskId | null, stepId?: string | null) { detail.value?.open(taskId, runId, stepId); }
async function open(options: {filters?: Partial<TaskFilters>; taskId?: TaskId; runId?: TaskId | null; stepId?: string | null} = {}) {
  if (options.filters) list.applyFilters(options.filters);
  if (options.taskId) { await nextTick(); openDetail(options.taskId, options.runId, options.stepId); }
}
function setVisible(value: boolean) { if (!value) openFilter.value = null; list.setVisible(value); }
function closeDetail() { detail.value?.close(); }
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
    const ids = targets.map(task => task.id);
    const result = action === 'terminate'
      ? await tasksApi.bulk(action, ids, {onAccepted: receipt => {
        notice.value = `终止请求已受理，正在等待结果（命令 ${receipt.command_id}）`;
      }})
      : await tasksApi.bulk(action, ids);
    const accepted = Array.isArray(result.accepted) ? result.accepted : [];
    skipped.value = (result.skipped || []).map(item => ({id: item.task_id, message: item.error || item.message || '操作未接受'}));
    const acceptedCount = Number(result.accepted_count ?? accepted.length);
    if (action === 'cancel') {
      const cancelled = accepted.filter(item => item.state === 'cancelled').length;
      const cancelling = accepted.filter(item => item.state === 'cancelling').length;
      notice.value = `已取消 ${cancelled} 个，取消中 ${cancelling} 个${acceptedCount - cancelled - cancelling > 0 ? `，已受理 ${acceptedCount - cancelled - cancelling} 个` : ''}`;
    } else { notice.value = `已${labels[action]} ${acceptedCount} 个`; }
    const acceptedIds = new Set(accepted.map(item => String(item.task_id)));
    selected.value = new Set([...selected.value].filter(id => !acceptedIds.has(String(id))));
    if (skipped.value.length) notice.value += `，跳过 ${skipped.value.length} 个`;
    await refresh(); emit('changed');
  } catch (cause) { actionError.value = cause instanceof BulkMutationPendingError
    ? cause.message : `${labels[action]}失败：${cause instanceof Error ? cause.message : String(cause)}`; }
  finally { busy.value = false; }
}
defineExpose({open, refresh, closeDetail, setVisible});
</script>
<template>
  <section v-show="visible" class="tc-root" aria-label="统一任务中心">
    <div class="ui-list tc-workspace">
      <ListToolbar :filtered="activeFilters.length > 0">
        <span class="ui-list-count tc-count" role="status">{{ total.toLocaleString() }} 个任务</span>
        <div class="tc-target-search" role="search">
          <input ref="targetInput" type="search" :value="targetDraft" placeholder="搜索目标邮箱 / 账号..." aria-label="搜索任务目标" autocomplete="off" @input="onTargetInput(($event.target as HTMLInputElement).value)" @keydown.enter.prevent="commitTarget(targetDraft)" @keydown.esc.prevent="clearTargetSearch">
          <button v-if="targetDraft" type="button" class="tc-target-search__clear" aria-label="清空目标搜索" title="清空目标搜索" @click="clearTargetSearch">×</button>
        </div>
        <span v-if="selectedRows.length" class="tc-selection" role="status">已选 {{ selectedRows.length }} 项</span>
        <div v-if="selectedRows.length" class="tc-bulk-actions" role="group" aria-label="选中任务批量操作"><button v-for="kind in (['retry', 'cancel', 'terminate', 'delete'] as TaskAction[])" :key="kind" type="button" class="ui-button" :class="{'ui-button--danger': kind === 'delete' || kind === 'terminate'}" :disabled="busy || !counts[kind]" @click="bulk(kind)">{{ labels[kind] }}{{ counts[kind] ? `（${counts[kind]}）` : '' }}</button></div>
        <ListFilterSummary :items="filterChips" @remove="removeFilter"/>
        <template #actions>
          <TaskFiltersMenu :model-value="filters" :facets="facets" :open="openFilter === 'mobile'" @update:model-value="updateFilters" @update:open="openFilter = $event ? 'mobile' : null"/>
          <button v-if="activeFilters.length" type="button" class="ui-link" @click="list.applyFilters({})">清除全部筛选</button>
          <span class="tc-timezone" :title="timezone">时间按 {{ timezone }} 显示</span>
          <button type="button" class="ui-link" @click="table?.resetColumns()">恢复列宽</button>
          <button id="btnRefreshTasksV2" type="button" class="ui-button" :disabled="loading" @click="list.refresh()">{{ loading ? '刷新中…' : '刷新' }}</button>
        </template>
      </ListToolbar>
      <div v-if="notice || actionError || (error && items.length)" class="ui-list-feedback tc-feedback" :class="{'is-error': actionError || error}" :role="actionError || error ? 'alert' : 'status'">{{ actionError || error || notice }}<button v-if="error" type="button" class="ui-link" @click="list.refresh()">重试</button><details v-if="skipped.length"><summary>查看跳过原因</summary><ul><li v-for="item in skipped" :key="item.id">#{{ item.id }}：{{ item.message }}</li></ul></details></div>
      <TaskTable ref="table" :filters="filters" :facets="facets" v-model:open-filter="openFilter" @update:filters="updateFilters" :items="items" :selected="selected" :loading="loading" :error="error" :busy="busy" @select="list.toggle" @select-page="list.togglePage" @detail="openDetail" @action="action" @batch="(id, round) => emit('batch', id, round)" @retry="list.refresh()"/>
      <ListPagination v-model:page="page" v-model:size="size" :pages="pages" :total="total" :busy="loading"/>
    </div>
  </section>
  <TaskDetail ref="detail" @refresh="changed"/>
</template>
<style>
.tc-workspace .ui-list-toolbar {
  min-height: 48px;
  padding: 8px 14px;
  gap: 8px 12px;
}
.tc-workspace .ui-list-toolbar__main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 8px;
}
.tc-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--ui-color-text-secondary);
  white-space: nowrap;
}
.tc-selection {
  flex: none;
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  background: var(--ui-color-brand-soft, #eef2ff);
  color: var(--ui-color-brand, #4f46e5);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.tc-bulk-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  margin-left: 2px;
  padding-left: 10px;
  border-left: 1px solid var(--ui-color-border);
}
.tc-workspace .ui-list-toolbar :is(.ui-button, .ui-link, .tc-bulk-actions button) {
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  min-height: 32px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}
.tc-table td,
.tc-table .list-cell-primary,
.tc-table .list-cell-secondary,
.tc-table .tc-cell-line {
  overflow: hidden;
  text-overflow: ellipsis;
}
.tc-table thead th {
  position: sticky;
  top: 0;
  z-index: 6;
  background: #f8fafc;
}
.tc-table thead th:last-child {
  position: sticky;
  right: 0;
  z-index: 12;
  background: #f8fafc;
  border-left: 1px solid var(--ui-color-border);
  box-shadow: -6px 0 12px -6px rgba(15, 23, 42, .08);
  text-align: center;
}
.tc-table tbody td {
  background: #ffffff;
}
.tc-table tbody tr:hover td {
  background: #f8fafc;
}
.tc-table tbody tr.is-selected td {
  background: #eef2ff;
}
.tc-table tbody td:last-child {
  position: sticky;
  right: 0;
  z-index: 4;
  background: #ffffff;
  border-left: 1px solid var(--ui-color-border);
  box-shadow: -6px 0 12px -6px rgba(15, 23, 42, .08);
}
.tc-table tbody tr:hover td:last-child {
  background: #f8fafc;
}
.tc-table tbody tr.is-selected td:last-child {
  background: #eef2ff;
}
@media (max-width: 860px) {
  .tc-bulk-actions {
    flex-basis: 100%;
    margin-left: 0;
    padding-left: 0;
    border-left: 0;
  }
  .tc-table :is(th, td):last-child {
    position: static;
    border-left: 0;
    background: transparent;
    box-shadow: none;
  }
}
</style>
