<script setup lang="ts">
import { computed } from 'vue';
import type { OperationRun } from '../../../api/tasks';
import { errorText, label } from '../presentation';
import { failureIsInferred, failureMessage, text, type Failure } from './model';

const props = defineProps<{ failure?: Failure | null; execution?: Pick<OperationRun, 'error_message' | 'error_info'> | null; status?: string | null }>();
const hasExecutionError = computed(() => !!(props.execution?.error_message || props.execution?.error_info));
const countryFailures = computed(() => (props.failure?.country_failures || []).filter(item => text(item.country).trim()));
const primaryFailure = computed(() => {
  const failure = props.failure;
  if (!failure) return '';
  return countryFailures.value.length && !failure.error_info?.auto_refresh_at_failed
    ? `${countryFailures.value.length} 个国家查询失败，展开查看具体原因` : failureMessage(failure);
});
const failureLocation = computed(() => {
  const failure = props.failure;
  if (!failure) return '';
  const stage = failure.error_info?.stage?.replace(/_result$/, '');
  return stage && !['unknown', 'complete', 'result', 'event', 'queued'].includes(stage) && stage !== failure.stage
    ? label('stage', stage) : [failure.label || failure.step_id || '阶段记录缺失', failure.stage].filter(Boolean).join(' · ');
});
const executionSummary = computed(() => hasExecutionError.value ? errorText(props.execution?.error_info, props.execution?.error_message) : '');
const sameFailure = computed(() => {
  if (!props.failure || !hasExecutionError.value) return false;
  // 同一原因可在执行结果保留原文、在步骤快照增加分类；只在已有内容确实对应时合并摘要。
  const normalize = (value: unknown) => text(value).replace(/\s+/g, ' ').trim();
  const failure = props.failure;
  const info = failure.error_info;
  const runInfo = props.execution?.error_info;
  const rawFailure = normalize(failure.message);
  const rawExecution = normalize(props.execution?.error_message);
  if (rawFailure && rawExecution && rawFailure !== rawExecution) return false;
  if (info?.cause_summary && runInfo?.cause_summary) return normalize(info.cause_summary) === normalize(runInfo.cause_summary);
  if (rawFailure && rawExecution) return rawFailure === rawExecution;
  const cause = normalize(info?.cause_summary || info?.summary || failure.message);
  return !!cause && cause === normalize(runInfo?.cause_summary || runInfo?.summary || props.execution?.error_message);
});
const evidence = computed(() => ({
  ...(props.failure ? { failure: props.failure } : {}),
  ...(hasExecutionError.value ? { execution: { error_message: props.execution?.error_message, error_info: props.execution?.error_info } } : {}),
}));
</script>

<template>
  <details v-if="failure || hasExecutionError" class="tc-progress-failure tc-task-failure">
    <summary>
      <strong v-if="failure">{{ failureIsInferred(failure) ? '历史失败位置' : '失败位置' }}：{{ failureLocation }}</strong>
      <strong v-else>执行失败</strong>
      <span>{{ primaryFailure || executionSummary }}</span>
      <span v-if="failure && hasExecutionError && !sameFailure" class="tc-failure-secondary">执行错误：{{ executionSummary }}</span>
      <small v-if="execution?.error_info?.display_code">{{ execution.error_info.display_code }}</small>
    </summary>
    <ul v-if="countryFailures.length"><li v-for="(country, index) in countryFailures" :key="index">{{ country.country }}：{{ country.summary || '诊断记录不完整' }}</li></ul>
    <p v-if="failure?.event_id">关联事件 {{ failure.event_id }}</p>
    <p v-if="failure?.reconcile_required || ['request_unknown', 'attention_required'].includes(text(status))">原请求证据已保留</p>
    <pre>{{ JSON.stringify(evidence, null, 2) }}</pre>
  </details>
</template>
