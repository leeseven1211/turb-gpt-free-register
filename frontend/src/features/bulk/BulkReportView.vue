<script setup lang="ts">
import {computed} from 'vue';
import BulkReport from './BulkReport.vue';
import {operationNames} from './bulkReportPresentation';
import type {BulkReportState} from './mountBulkReport';

const props = defineProps<BulkReportState>();
const supported = computed(() => Object.hasOwn(operationNames, props.operationKey));
const title = computed(() => `${operationNames[props.operationKey]}报告`);
</script>

<template>
  <template v-if="supported">
    <BulkReport
      v-if="report && report.operation_key === operationKey"
      :report="report"
      :format-date-time="formatDateTime"
    />
    <section v-else class="bulk-plan-report bulk-report-placeholder" :aria-label="title">
      <h3>{{ title }}</h3>
      <p v-if="!error" role="status">正在汇总本次执行结果…</p>
    </section>
    <div v-if="error" class="bulk-report-load-error">
      <p class="bulk-error" role="alert">{{ error }}</p>
      <button
        type="button"
        class="jobs-tb-btn"
        data-bulk-action="report-refresh"
        @click.stop="onRetry()"
      >
        重新读取报告
      </button>
    </div>
  </template>
</template>
