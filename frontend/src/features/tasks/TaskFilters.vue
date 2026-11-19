<script setup lang="ts">
import {computed, ref} from 'vue';
import type {Facets, TaskFilters} from '../../api/tasks';
import FilterPopover from '../../components/FilterPopover.vue';
import TaskFilterFields from './TaskFilterFields.vue';
import {filterColumns, isFilterActive} from './filterDefinitions';
const props = defineProps<{modelValue: TaskFilters; facets: Facets; open: boolean}>();
const emit = defineEmits<{'update:modelValue': [TaskFilters]; 'update:open': [boolean]}>();
const selected = ref(filterColumns[0]!.key);
const column = computed(() => filterColumns.find(item => item.key === selected.value)!);
const activeCount = computed(() => filterColumns.filter(item => isFilterActive(item, props.modelValue)).length);
</script>
<template>
  <div class="tc-mobile-filters">
    <FilterPopover label="任务条件" :trigger-label="activeCount ? `筛选（${activeCount}）` : '筛选'" :active="activeCount > 0" :open="open" @update:open="emit('update:open', $event)">
      <label class="tc-filter-column-picker">筛选列<select v-model="selected"><option v-for="item in filterColumns" :key="item.key" :value="item.key">{{ item.label }}{{ isFilterActive(item, modelValue) ? ' · 已筛选' : '' }}</option></select></label>
      <TaskFilterFields :key="selected" :column="column" :model-value="modelValue" :facets="facets" @update:model-value="emit('update:modelValue', $event)" @done="emit('update:open', false)"/>
    </FilterPopover>
  </div>
</template>
