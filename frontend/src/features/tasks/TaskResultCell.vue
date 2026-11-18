<script setup lang="ts">
import {computed} from 'vue';
import type {OperationTask} from '../../api/tasks';
import ListResult from '../../components/ListResult.vue';
import {shortErrorLabel} from '../../shared/errorLabels';
import {errorText, resultDetails} from './presentation';
import {taskResultSummary} from './resultSummary';

const props = defineProps<{task: OperationTask}>();
const summary = computed(() => taskResultSummary(props.task, shortErrorLabel(props.task.error_info)));
const details = computed(() => [...new Set([
  resultDetails(props.task),
  props.task.error_info?.display_code,
  props.task.error_info?.cause_display_code,
  props.task.error_info || props.task.error_message ? errorText(props.task.error_info, props.task.error_message) : '',
  props.task.error_message,
].filter((value): value is string => !!value))]);
</script>

<template>
  <ListResult v-bind="summary" :title="details.join('\n')">
    <template #details><p v-for="(paragraph, index) in details" :key="index">{{ paragraph }}</p></template>
  </ListResult>
</template>
