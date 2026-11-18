<script setup lang="ts">
import type {Facets, TaskFilters} from '../../api/tasks';
import FilterPopover from '../../components/FilterPopover.vue';
import TaskFilterFields from './TaskFilterFields.vue';
import {filterSummary, isFilterActive, type FilterColumn} from './filterDefinitions';

defineProps<{column: FilterColumn; modelValue: TaskFilters; facets: Facets; open: boolean}>();
const emit = defineEmits<{'update:modelValue': [TaskFilters]; 'update:open': [boolean]}>();
</script>

<template>
  <FilterPopover :label="column.label" :active="isFilterActive(column, modelValue)" :summary="filterSummary(column, modelValue, facets)"
    :open="open" @update:open="emit('update:open', $event)">
    <TaskFilterFields :column="column" :model-value="modelValue" :facets="facets"
      @update:model-value="emit('update:modelValue', $event)" @done="emit('update:open', false)" />
  </FilterPopover>
</template>
