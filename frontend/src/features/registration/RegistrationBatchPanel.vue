<script setup lang="ts">
import {computed, onBeforeUnmount, ref, watch} from 'vue';
import {isAbort} from '../../api/client';
import type {JobProgressResponse, RegistrationBatch, RegistrationId, RegistrationJob} from '../../api/registration';
import {shortErrorLabel} from '../../shared/errorLabels';
import {dateTimeLines} from '../../shared/time';
import {formatDateTime, formatDuration} from '../tasks/presentation';
import {object, records, text} from '../tasks/detail/model';
import RegistrationProgress from './RegistrationProgress.vue';

type Filter = 'all' | 'success' | 'failed' | 'active' | 'other';
type BatchAction = 'stopBatch' | 'cancelBatch' | 'retryBatch';
const props = defineProps<{
  batch: RegistrationBatch | null;
  batches: RegistrationBatch[];
  batchId: string;
  refreshGeneration: number;
  active: boolean;
  loading: boolean;
  error: string;
  actions: Record<BatchAction, boolean>;
  mutating: boolean;
  statusLabel: (value: unknown) => string;
  sourceLabel: (value: unknown) => string;
  driverLabel: (value: unknown) => string;
  readProgress: (id: RegistrationId, signal: AbortSignal) => Promise<JobProgressResponse>;
}>();
const emit = defineEmits<{
  select: [string];
  refresh: [];
  batchAction: [BatchAction];
  retry: [RegistrationJob];
  log: [RegistrationId, string?];
}>();

const filters: {key: Filter; label: string}[] = [
  {key:'all', label:'全部'}, {key:'success', label:'成功'}, {key:'failed', label:'失败'},
  {key:'active', label:'运行 / 排队'}, {key:'other', label:'其他'},
];
const filter = ref<Filter>('all');
const expandedId = ref<string | null>(null);
const focusFailure = ref(false);
const rows = computed(() => props.batch?.items || []);
const batchOptions = computed(() => {
  if (props.batch && !props.batches.some(batch => String(batch.batch_id) === String(props.batch?.batch_id))) {
    return [props.batch, ...props.batches];
  }
  return props.batches;
});
const status = (job: RegistrationJob) => job.status || job.display_status || '';
function category(job: RegistrationJob): Exclude<Filter, 'all'> {
  const value = status(job);
  if (value === 'success' || value === 'failed') return value;
  return ['running', 'pending', 'stopping'].includes(value) ? 'active' : 'other';
}

// A selected batch carries the current attempts of all slots. Derive the
// counts and actions from those rows so the filter always matches the number.
const counts = computed(() => {
  const result = {all:rows.value.length, success:0, failed:0, active:0, other:0};
  for (const row of rows.value) result[category(row)]++;
  return result;
});
const displayedFilters = computed(() => filters.filter(item => item.key !== 'other' || counts.value.other || filter.value === 'other'));
const displayedRows = computed(() => filter.value === 'all' ? rows.value : rows.value.filter(row => category(row) === filter.value));
const expandedJob = computed(() => displayedRows.value.find(job => String(job.id) === expandedId.value));
const progressJob = ref<RegistrationJob>();
const progressError = ref('');
let progressRequest: AbortController | undefined;
const batchStatus = computed(() => {
  const value = counts.value;
  if (!value.all) return {label:'暂无任务', tone:'other'};
  if (value.active) {
    return {label: rows.value.some(row => status(row) !== 'pending' && category(row) === 'active') ? '运行中' : '排队中', tone:'active'};
  }
  if (value.failed) return {label:value.failed === value.all ? '失败' : '部分失败', tone:'failed'};
  if (value.success === value.all) return {label:'已完成', tone:'success'};
  return {label:'已结束', tone:'other'};
});
const duration = (start: unknown, end: unknown, currentTime?: number) => {
  const endTime = end ? Date.parse(text(end)) : currentTime ?? NaN;
  const elapsed = endTime - Date.parse(text(start));
  return Number.isFinite(elapsed) && elapsed >= 0 ? formatDuration(elapsed) : '';
};
const batchDuration = computed(() => duration(props.batch?.started_at, props.batch?.completed_at));
const formatCount = (value: number) => value.toLocaleString('zh-CN');
const failure = (job: RegistrationJob) => object(object(job.progress).failure);

const rowSummaries = computed(() => {
  // 批次轮询返回新摘要时刷新运行中的耗时。
  const now = Date.now();
  return displayedRows.value.map(job => {
    const tone = category(job);
    const running = tone === 'active' && status(job) !== 'pending';
    return {
      job, tone, result: rowResult(job, tone),
      identity: [
        `#${job.id}`,
        job.email_source && props.sourceLabel(job.email_source),
        job.registration_driver && props.driverLabel(job.registration_driver),
        typeof job.retry_count === 'number' && `人工重试 ${job.retry_count} 次`,
      ].filter(Boolean).join(' · '),
      elapsed: duration(job.started_at, job.completed_at, running ? now : undefined),
      started: rowTime(job.started_at),
      completed: rowTime(job.completed_at),
    };
  });
});
function rowTime(value?: string | null) {
  if (!value || !Number.isFinite(Date.parse(value))) return null;
  const {text: date, secondary: time} = dateTimeLines(value);
  return {label: time ? `${date.slice(5)} ${time}` : date, full: time ? `${date} ${time}` : date};
}
function rowResult(job: RegistrationJob, tone: Exclude<Filter, 'all'>) {
  if (tone === 'failed' || status(job) === 'partial_success') {
    const short = job.error_info ? shortErrorLabel(object(job.error_info)) : '';
    const stage = text(failure(job).label);
    if (short && short !== '执行异常') return short;
    if (stage && Array.from(stage).length <= 10) return stage;
    return short || '执行异常';
  }
  if (tone === 'active') return text(object(object(job.progress).current).label);
  return '';
}
function rowStatus(job: RegistrationJob) {
  if (job.debug_state === 'paused') return '调试暂停';
  return props.statusLabel(job.display_status || status(job));
}
function optionLabel(batch: RegistrationBatch) {
  const counts = batch.status_counts || {};
  const running = Number(counts.running || 0) + Number(counts.stopping || 0);
  const pending = Number(counts.pending || 0);
  const date = batch.created_at ? formatDateTime(batch.created_at).replace(/:\d{2}$/, '') : String(batch.batch_id);
  const state = running || pending ? `运行 ${running} / 等待 ${pending}` : `成功 ${counts.success || 0} / 失败 ${counts.failed || 0}`;
  return `${date} · ${state}`;
}
function setFilter(value: Filter) {
  filter.value = value;
  expandedId.value = null;
  focusFailure.value = false;
  if (value === 'failed' && displayedRows.value.length === 1) {
    expandedId.value = String(displayedRows.value[0]!.id);
    focusFailure.value = true;
  }
}
function toggleDetails(job: RegistrationJob) {
  const id = String(job.id);
  expandedId.value = expandedId.value === id ? null : id;
  focusFailure.value = expandedId.value !== null && category(job) === 'failed';
}

function resetProgress() {
  progressRequest?.abort();
  progressRequest = undefined;
  progressJob.value = undefined;
  progressError.value = '';
}
const runId = (job?: RegistrationJob) => String(job?.operation_run_id ?? '');
async function loadProgress(job: RegistrationJob) {
  if (progressRequest || !props.active) return;
  const controller = new AbortController();
  progressRequest = controller;
  progressError.value = '';
  try {
    const result = await props.readProgress(job.id, controller.signal);
    if (controller.signal.aborted) return;
    if (!result.ok || !result.job || String(result.job.id) !== String(job.id)
      || !Array.isArray(object(result.job.progress).main_steps)) {
      throw new Error('阶段详情读取失败，请重试');
    }
    if (runId(job) && runId(job) !== runId(result.job)) {
      throw new Error('当前执行已更新，请刷新批次后重试');
    }
    progressJob.value = result.job;
  } catch (error) {
    if (!controller.signal.aborted && !isAbort(error)) {
      progressError.value = error instanceof Error ? error.message : '阶段详情读取失败，请重试';
    }
  } finally {
    if (progressRequest === controller) progressRequest = undefined;
  }
}

watch(() => props.batchId, () => setFilter('all'));
watch([() => props.active, () => props.batchId, expandedJob, () => props.refreshGeneration],
  ([active, batchId, job, generation], [, previousBatch, previousJob, previousGeneration]) => {
    if (!active || !job) {
      resetProgress();
      if (active && props.batch && expandedId.value !== null) {
        expandedId.value = null;
        focusFailure.value = false;
      }
      return;
    }
    const changed = batchId !== previousBatch || String(job.id) !== String(previousJob?.id)
      || runId(job) !== runId(previousJob) || status(job) !== (previousJob && status(previousJob));
    const refreshed = generation !== previousGeneration;
    if (changed || refreshed) resetProgress();
    if (changed || refreshed || (!progressJob.value && !progressError.value) || category(job) === 'active') {
      void loadProgress(job);
    }
  },
);
onBeforeUnmount(resetProgress);
</script>

<template>
  <section class="registration-batch" aria-labelledby="registration-batch-title" :aria-busy="loading">
    <header class="registration-batch-header">
      <div>
        <div class="registration-batch-title">
          <h2 id="registration-batch-title">任务批次进度</h2>
          <span v-if="batch" class="registration-state" :data-tone="batchStatus.tone">{{ batchStatus.label }}</span>
          <span v-if="batch?.projection_delayed" class="registration-hint">进度同步中</span>
        </div>
        <p v-if="batch" class="registration-hint registration-batch-meta">
          <span>{{ formatCount(batch.total ?? counts.all) }} 个任务</span>
          <span v-if="batch.workers">并发 {{ batch.workers }}</span>
          <span v-if="batchDuration">批次耗时 {{ batchDuration }}</span>
        </p>
      </div>
      <div v-if="batchOptions.length" class="registration-batch-actions">
        <select :value="batchId" aria-label="选择任务批次" @change="emit('select', ($event.target as HTMLSelectElement).value)">
          <option v-for="option in batchOptions" :key="String(option.batch_id)" :value="String(option.batch_id)">{{ optionLabel(option) }}</option>
        </select>
        <button v-if="actions.stopBatch" type="button" :disabled="mutating" @click="emit('batchAction','stopBatch')">停止运行</button>
        <button v-if="actions.cancelBatch" type="button" :disabled="mutating" @click="emit('batchAction','cancelBatch')">取消排队</button>
        <button v-if="actions.retryBatch" type="button" :disabled="mutating" @click="emit('batchAction','retryBatch')">重跑失败</button>
      </div>
    </header>

    <div v-if="error" class="registration-batch-notice" role="alert">{{ error }} <button type="button" @click="emit('refresh')">刷新批次</button></div>
    <p v-else-if="!batch || !rows.length" class="registration-batch-notice">{{ loading ? '正在读取任务批次…' : '暂无注册任务批次' }}</p>
    <template v-if="batch && counts.all">
      <div class="registration-batch-meter" aria-hidden="true">
        <span v-for="item in displayedFilters.slice(1)" :key="item.key" :data-tone="item.key" :style="{flexGrow:counts[item.key]}"></span>
      </div>
      <div class="registration-batch-filters" role="group" aria-label="按批次任务状态筛选">
        <button v-for="item in displayedFilters" :key="item.key" type="button" :data-batch-filter="item.key" :aria-pressed="filter === item.key" @click="setFilter(item.key)">
          <span v-if="item.key !== 'all'" class="registration-status-dot" :data-tone="item.key" aria-hidden="true"></span>{{ item.label }} {{ formatCount(counts[item.key]) }}
        </button>
      </div>

      <article v-for="{job, tone, result, identity, elapsed, started, completed} in rowSummaries" :key="String(job.id)" class="registration-batch-card" :data-tone="tone">
        <div class="registration-batch-row">
          <div class="registration-batch-identity">
            <strong>{{ job.email || (job.status === 'pending' ? '等待执行…' : '准备邮箱中…') }}</strong>
            <small>{{ identity }}</small>
          </div>
          <div class="registration-batch-result">
            <span class="registration-state" :data-tone="tone">{{ rowStatus(job) }}</span>
            <small v-if="result">{{ result }}</small>
          </div>
          <div v-if="elapsed || started || completed" class="registration-batch-timing">
            <strong v-if="elapsed">运行耗时 {{ elapsed }}</strong>
            <div class="registration-batch-dates">
              <small v-if="started">开始 <time :datetime="job.started_at || undefined" :title="started.full">{{ started.label }}</time></small>
              <small v-if="completed">结束 <time :datetime="job.completed_at || undefined" :title="completed.full">{{ completed.label }}</time></small>
            </div>
          </div>
          <div class="registration-batch-actions registration-batch-row-actions">
            <button type="button" :aria-label="`查看阶段 · ${job.email || `任务 #${job.id}`}`"
              :aria-expanded="expandedId === String(job.id)" :aria-controls="`registration-stages-${job.id}`" @click="toggleDetails(job)">阶段</button>
            <button type="button" :aria-label="`查看日志 · ${job.email || `任务 #${job.id}`}`" @click="emit('log',job.id)">日志</button>
            <button v-if="job.retryable" type="button" :disabled="mutating" @click="emit('retry',job)">{{ job.retry_label || '重试' }}</button>
          </div>
        </div>
        <div :id="`registration-stages-${job.id}`" class="registration-batch-evidence" :hidden="expandedId !== String(job.id)"
          :data-progress-state="expandedId === String(job.id) ? (progressError ? 'error' : progressJob ? 'ready' : 'loading') : undefined">
          <template v-if="expandedId === String(job.id)">
            <p v-if="progressError" class="registration-step-note" role="alert">
              {{ progressError }} <button type="button" @click="loadProgress(job)">重试读取</button>
            </p>
            <p v-else-if="!progressJob" class="registration-step-note" role="status">正在读取阶段详情…</p>
            <template v-if="progressJob">
              <RegistrationProgress :job="progressJob" :active="active" inline :focus-failure="focusFailure" @log="emit('log',job.id,$event)"/>
              <details v-if="progressJob.error_message">
                <summary>原始错误摘要</summary>
                <p>{{ progressJob.error_message }}</p>
              </details>
              <details v-if="records(progressJob.attempts).length || records(progressJob.route_attempts).length">
                <summary>尝试与线路记录</summary>
                <p v-for="attempt in records(progressJob.attempts)" :key="text(attempt.id || attempt.attempt_id)">
                  {{ statusLabel(attempt.status) }} · {{ attempt.error_message || '已记录' }}
                </p>
                <p v-for="route in records(progressJob.route_attempts)" :key="text(route.route_attempt_no)">
                  线路尝试 {{ route.route_attempt_no || 1 }} · {{ route.retry_reason || statusLabel(route.status) }}
                </p>
              </details>
            </template>
          </template>
        </div>
      </article>
      <p v-if="!displayedRows.length" class="registration-batch-notice">没有符合条件的任务</p>
      <p class="registration-batch-footer registration-hint" aria-live="polite">显示 {{ formatCount(displayedRows.length) }} 条任务</p>
    </template>
  </section>
</template>
