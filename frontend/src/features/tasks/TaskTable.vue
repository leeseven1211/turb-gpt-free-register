<script setup lang="ts">
import {computed} from 'vue';
import {useColumnWidths} from '../../shared/useColumnWidths';
import {emptyFilters, type Facets, type OperationTask, type TaskAction, type TaskFilters, type TaskId} from '../../api/tasks';
import TaskColumnFilter from './TaskColumnFilter.vue';
import {filterColumns} from './filterDefinitions';
import ListCell from '../../components/ListCell.vue';
import TaskResultCell from './TaskResultCell.vue';
import {canRetry, canStop, failureStageText, formatDateTime, formatDuration, isActive, label, record} from './presentation';
import {taskListStatus} from './statusDisplay';
const props = withDefaults(defineProps<{items: OperationTask[]; selected: Set<TaskId>; loading: boolean; error: string; busy: boolean; filters?: TaskFilters; facets?: Facets; openFilter?: string | null}>(), {filters: emptyFilters, facets: () => ({}), openFilter: null});
const emit = defineEmits<{select: [TaskId, boolean]; selectPage: [boolean]; detail: [TaskId]; action: [OperationTask, TaskAction]; batch: [string, string?]; retry: []; 'update:filters': [TaskFilters]; 'update:openFilter': [string | null]}>();
const allChecked = computed(() => props.items.length > 0 && props.items.every(item => props.selected.has(item.id)));
const partial = computed(() => !allChecked.value && props.items.some(item => props.selected.has(item.id)));
const rows = computed(() => props.items.map(task => ({task, ...taskListStatus(task)})));
const columns = ['选择', 'ID', '类型', '目标', '执行状态', '目标状态', '批次 / 触发', '运行次数', '当前步骤', '创建 / 完成', '结果 / 错误', '操作'];
const defaults = [40, 72, 118, 198, 108, 112, 145, 88, 128, 168, 170, 145];
const {widths, resize, resizeWithKeyboard, resetColumns} = useColumnWidths({defaults,
  storageKey: 'turb_task_center_columns', min: 65, max: 800, savedMin: 40});

function stepText(task: OperationTask) { return failureStageText(task) || task.current_stage_label || label('stage', task.current_stage); }
function stepTitle(task: OperationTask) { return [task.current_stage_label || label('stage', task.current_stage), failureStageText(task), formatDuration(task.duration_ms)].filter(Boolean).join(' · '); }
function batchId(task: OperationTask) { return String(task.bulk_batch_id || record(task.bulk_context).batch_id || ''); }
function batchRound(task: OperationTask) { return String(task.bulk_round_id || record(task.bulk_context).round_id || ''); }
defineExpose({resetColumns});
</script>
<template>
  <div class="tc-table-scroll" tabindex="0" aria-label="任务列表，可横向滚动" :aria-busy="loading">
    <table class="tc-table" :style="{'--tc-table-width': `${widths.reduce((sum, n) => sum + n, 0)}px`}">
      <caption class="tc-sr-only">任务中心列表，选择任务可批量操作</caption>
      <colgroup><col v-for="(width, index) in widths" :key="index" :style="{width: `${width}px`}"></colgroup>
      <thead><tr><th v-for="(name, index) in columns" :key="name" scope="col">
        <input v-if="index === 0" type="checkbox" aria-label="全选当前页任务" :checked="allChecked" :indeterminate="partial" :disabled="!items.length" @change="emit('selectPage', ($event.target as HTMLInputElement).checked)">
        <template v-else>
          <TaskColumnFilter v-if="filterColumns[index - 1]" :column="filterColumns[index - 1]!" :model-value="filters" :facets="facets" :open="openFilter === filterColumns[index - 1]!.key" @update:model-value="emit('update:filters', $event)" @update:open="emit('update:openFilter', $event ? filterColumns[index - 1]!.key : null)"/>
          <template v-else>{{ name }}</template>
          <button v-if="index < columns.length - 1" type="button" class="tc-column-resize" :aria-label="`调整${name}列宽，方向键调整`" @pointerdown.prevent="resize(index, $event)" @keydown.left.prevent="resizeWithKeyboard(index, -10)" @keydown.right.prevent="resizeWithKeyboard(index, 10)"></button>
        </template>
      </th></tr></thead>
      <tbody><tr v-for="{task, execution, target} in rows" :key="task.id" :class="{'tc-row-selected': selected.has(task.id)}">
        <td data-label="选择"><input type="checkbox" :checked="selected.has(task.id)" :aria-label="`选择任务 #${task.id}`" @change="emit('select', task.id, ($event.target as HTMLInputElement).checked)"></td>
        <td data-label="ID"><button type="button" class="tc-link tc-task-id" @click="emit('detail', task.id)">#{{ task.id }}</button></td>
        <td data-label="类型"><ListCell :text="label('task_type', task.task_type)"/></td>
        <td data-label="目标"><ListCell :text="task.account_id ? `账号 #${task.account_id}` : task.attempt_id ? `注册尝试 #${task.attempt_id}` : '—'" :secondary="task.email_snapshot || task.email || '—'"><strong>{{ task.account_id ? `账号 #${task.account_id}` : task.attempt_id ? `注册尝试 #${task.attempt_id}` : '—' }}</strong></ListCell></td>
        <td data-label="执行状态"><span class="tc-badge" :class="`tc-badge--${execution.tone}`" :title="execution.title">{{ execution.label }}</span><span v-if="execution.secondary" class="tc-subline tc-cell-line" :title="execution.secondary">{{ execution.secondary }}</span></td>
        <td data-label="目标状态"><span v-if="target" class="tc-badge" :class="`tc-badge--${target.tone}`" :title="target.title">{{ target.label }}</span><span v-else class="tc-cell-line" aria-label="无额外目标状态">—</span></td>
        <td data-label="批次 / 触发"><ListCell :text="task.batch_title || task.batch_uuid || (batchId(task) ? '查看批次' : '单任务')" :secondary="label('trigger', task.trigger)"><button v-if="batchId(task)" type="button" class="tc-link" @click="emit('batch', batchId(task), batchRound(task))">{{ task.batch_title || task.batch_uuid || '查看批次' }}</button><template v-else>{{ task.batch_title || task.batch_uuid || '单任务' }}</template></ListCell></td>
        <td data-label="运行次数"><ListCell :text="`${task.run_count || 0} 次`" :secondary="`最近 #${task.last_run_no || '—'}`"/></td>
        <td data-label="当前步骤"><ListCell :text="stepText(task)" :secondary="formatDuration(task.duration_ms)" :title="stepTitle(task)" :tone="failureStageText(task) ? 'danger' : 'neutral'"/></td>
        <td data-label="创建 / 完成" class="tc-time"><ListCell :text="formatDateTime(task.created_at)" :secondary="formatDateTime(task.completed_at)"/></td>
        <td data-label="结果 / 错误"><TaskResultCell :task="task"/></td>
        <td data-label="操作"><div class="tc-row-actions"><button type="button" class="tc-link" @click="emit('detail', task.id)">详情</button><button v-if="canRetry(task)" type="button" class="tc-link" :disabled="busy" @click="emit('action', task, 'retry')">重跑</button><button v-if="canStop(task)" type="button" class="tc-link tc-text-danger" :disabled="busy" @click="emit('action', task, 'terminate')">{{ task.status === 'queued' ? '取消' : '终止' }}</button><button v-if="!isActive(task)" type="button" class="tc-link tc-text-danger" :disabled="busy" @click="emit('action', task, 'delete')">删除</button></div></td>
      </tr>
      <tr v-if="!items.length" class="tc-empty-row"><td :colspan="columns.length"><div class="tc-empty" :role="error ? 'alert' : 'status'"><span v-if="loading" class="tc-spinner" aria-hidden="true"></span><strong>{{ loading ? '正在加载任务记录' : error ? '任务列表加载失败' : '没有匹配的任务' }}</strong><p>{{ error || (loading ? '正在同步任务状态' : '可调整筛选条件，或清除全部筛选。') }}</p><button v-if="error" type="button" class="tc-button" @click="emit('retry')">重新加载</button></div></td></tr>
      </tbody>
    </table>
  </div>
</template>
