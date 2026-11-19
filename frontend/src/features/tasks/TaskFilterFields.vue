<script setup lang="ts">
import {computed, useId} from 'vue';
import type {Facets, TaskFilters} from '../../api/tasks';
import {clearColumnFilter, filterSummary, isFilterActive, type FilterColumn} from './filterDefinitions';
import {label, labels} from './presentation';

const props = defineProps<{column: FilterColumn; modelValue: TaskFilters; facets: Facets}>();
const emit = defineEmits<{'update:modelValue': [TaskFilters]; done: []}>();
const fieldId = useId();
const field = computed(() => props.column.fields[0]!);
const selected = computed(() => props.modelValue[field.value]);
const allLabels: Record<string, string> = {task_type: '全部类型', status: '全部状态', target_status: '全部目标状态', run_count: '全部次数', stage: '全部步骤'};
const statusOptionLabels: Record<string, string> = {stopping: '请求停止', cancelling: '请求取消'};
const options = computed(() => {
  const group = props.column.group || '';
  const source = props.facets[group] || [];
  const facets = new Map(source.map(item => [item.value, item]));
  const values = new Set([...Object.keys(labels[group] || {}), ...source.map(item => item.value), ...(selected.value ? [selected.value] : [])]);
  const visibleStatuses = ['queued', 'running', 'waiting', 'stopping', 'cancelling', 'settling', 'success', 'partial_success', 'failed', 'deactivated', 'unsupported', 'interrupted', 'stopped', 'cancelled'];
  return [...values].filter(value => !!value && (group !== 'status' || visibleStatuses.includes(value) || value === selected.value))
    .map(value => ({value, text: (group === 'status' && statusOptionLabels[value]) || facets.get(value)?.label || (value.includes(',')
      ? filterSummary(props.column, {...props.modelValue, [field.value]: value}, props.facets) : label(group, value)), count: facets.get(value)?.count}));
});

function update(key: keyof TaskFilters, value: string) {
  emit('update:modelValue', {...props.modelValue, [key]: value});
}
function choose(value: string, event: MouseEvent) {
  update(field.value, value);
  // 原生 radio 的方向键也会合成 click；只有指针选择直接收起。
  if (event.detail > 0) emit('done');
}
function clear() {
  emit('update:modelValue', clearColumnFilter(props.column, props.modelValue));
  emit('done');
}
</script>

<template>
  <form class="tc-filter-fields" @submit.prevent="emit('done')">
    <div v-if="column.kind === 'search'" class="tc-filter-field">
      <label :for="`${fieldId}-search`">{{ column.key === 'task_id' ? '任务 ID' : column.label }}</label>
      <input :id="`${fieldId}-search`" :value="selected" type="search" :inputmode="column.key === 'task_id' ? 'numeric' : undefined"
        :placeholder="column.placeholder" @input="update(field, ($event.target as HTMLInputElement).value)">
    </div>
    <div v-else-if="column.kind === 'select'" class="tc-filter-options" role="radiogroup" :aria-label="column.label">
      <label class="tc-filter-option" :class="{'is-selected': !selected}">
        <input type="radio" :name="fieldId" value="" :checked="!selected" @change="update(field, '')" @click="choose('', $event)">
        <span class="tc-filter-option-label">{{ allLabels[column.group || ''] || '全部' }}</span>
      </label>
      <label v-for="item in options" :key="item.value" class="tc-filter-option" :class="{'is-selected': selected === item.value}">
        <input type="radio" :name="fieldId" :value="item.value" :checked="selected === item.value" @change="update(field, item.value)" @click="choose(item.value, $event)">
        <span class="tc-filter-option-label">{{ item.text }}</span>
        <span v-if="item.count != null" class="tc-filter-option-count">{{ item.count }}</span>
      </label>
    </div>
    <div v-else class="tc-filter-date-range">
      <p class="tc-filter-hint">按创建日期筛选任务。</p>
      <div class="tc-filter-field">
        <label :for="`${fieldId}-from`">创建日期起</label>
        <input :id="`${fieldId}-from`" :value="modelValue.created_from" type="date" @input="update('created_from', ($event.target as HTMLInputElement).value)">
      </div>
      <div class="tc-filter-field">
        <label :for="`${fieldId}-to`">创建日期止</label>
        <input :id="`${fieldId}-to`" :value="modelValue.created_to" type="date" @input="update('created_to', ($event.target as HTMLInputElement).value)">
      </div>
    </div>
    <div class="tc-filter-footer">
      <button type="button" class="tc-link" :disabled="!isFilterActive(column, modelValue)" @click="clear">清除此列</button>
      <button type="submit" class="tc-button">完成</button>
    </div>
  </form>
</template>
