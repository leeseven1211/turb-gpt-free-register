<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { formatDateTime, formatDuration, label } from '../presentation';
import {taskId,optionalTaskId,type TaskId} from '../../../api/taskIds';
import type { OperationRun } from '../../../api/tasks';
import { object, progressLabel, records, stepDuration, stepId, stepLabel, stepState, text, type Progress, type Step } from './model';
import { phaseDependencyTags, phaseMarkers, phaseState, phaseSteps } from './flowPresentation';
import StepEvidence from './StepEvidence.vue';
import StepRelations from './StepRelations.vue';
import TaskFailure from './TaskFailure.vue';

const props = defineProps<{ progress: Progress | null; filter: string | null; active: boolean; context: string;
  taskType?: string | null;
  execution?: Pick<OperationRun, 'error_message' | 'error_info'> | null }>();
const emit = defineEmits<{ filter: [value: string | null]; child: [taskId: TaskId, runId: TaskId | null] }>();
const allSteps = computed(() => props.progress?.main_steps || []);
const steps = computed(() => phaseSteps(props.progress?.main_steps));
const stepCols = computed(() => {
  const count = steps.value.length;
  if (count <= 1) return 1;
  if (count === 2) return 2;
  if (count === 3) return 3;
  if (count === 4) return 4;
  if (count === 5) return 5;
  if (count === 6) return 3;
  if (count <= 8) return 4;
  return 5;
});
const inspectedId = ref<string | null>(null);
const inspected = computed(() => allSteps.value.find(step => stepId(step) === inspectedId.value));
const inspector = ref<HTMLDialogElement>();
let returnFocus: HTMLElement | null = null;
const children = computed(() => records(props.progress?.outcome?.child_tasks).flatMap(child=>{try{return [{...child,task_id:taskId(child.task_id),run_id:optionalTaskId(child.run_id),task_type:child.task_type,status:child.status}];}catch{return [];}}));
const currentText = computed(() => {
  const pause = object(props.progress?.debug_pause);
  if (pause.state === 'paused') return `调试暂停 · 等待结束调试${pause.paused_at ? ` · ${formatDateTime(text(pause.paused_at))}` : ''}`;
  const current = props.progress?.current;
  if (!current) return '执行阶段';
  const currentRecord = current as Record<string, unknown>;
  const currentName = text(currentRecord.label || currentRecord.step_id);
  const currentState = text(currentRecord.state).toLowerCase();
  if (currentState === 'success' || currentState === 'skipped') {
    const nextLabel = text(currentRecord.next_label);
    return nextLabel
      ? `当前：已完成${currentName} · 正在进入${nextLabel}`
      : `当前：已完成${currentName} · 正在进入下一阶段`;
  }
  const childLabel = text(currentRecord.child_label);
  return `当前：${currentName || '执行中'}${childLabel ? ` · ${childLabel}` : ''}`;
});
const sourceSubtitle = computed(() => {
  if (props.progress?.source === 'legacy_derived') return '历史记录还原';
  if (props.progress?.source === 'insufficient_evidence') return '无细分阶段记录';
  return '按实际执行顺序与依赖排列';
});
function phaseTitle(step: Step) { return [stepLabel(step), phaseState(step), ...phaseMarkers(step), step.reason || step.message, '点击筛选事件和日志'].filter(Boolean).join(' · '); }
function selected(step: Step) { return stepId(step) === props.filter || !!(props.filter && step.raw_stages?.includes(props.filter)); }
async function inspect(step: Step) {
  returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  inspectedId.value = stepId(step);
  await nextTick();
  if (!inspector.value?.open) inspector.value?.showModal();
}
function closeInspector() {
  inspector.value?.close();
  inspectedId.value = null;
  if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
  returnFocus = null;
}
function scrollInspector(event: WheelEvent) {
  const content = inspector.value?.querySelector<HTMLElement>('.tc-step-dialog-body');
  if (!content || event.ctrlKey || event.shiftKey || !event.deltaY || content.contains(event.target as Node)) return;
  if (content.scrollHeight <= content.clientHeight) return;
  event.preventDefault();
  content.scrollTop += event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? content.clientHeight : 1);
}
watch(() => [props.context, props.active], closeInspector);
onBeforeUnmount(() => inspector.value?.close());
</script>

<template>
  <section v-if="progress" class="tc-progress" aria-label="执行进度">
    <div class="tc-progress-heading"><strong>{{ currentText }}</strong><small>{{ sourceSubtitle }}</small></div>
    <ul v-if="steps.length" class="tc-progress-track" :data-step-count="steps.length" :style="{ '--tc-step-cols': String(stepCols) }" aria-label="执行阶段，排列不代表固定顺序">
      <li v-for="step in steps" :key="stepId(step)" :class="['tc-step', `tc-step--${stepState(step)}`, { 'tc-step--selected': selected(step) }]">
        <button type="button" class="tc-step-select" :aria-pressed="selected(step)" :title="phaseTitle(step)" @click="emit('filter', selected(step) ? null : stepId(step))">
          <span class="tc-step-dot" aria-hidden="true"></span><strong>{{ stepLabel(step) }}</strong>
          <span class="tc-step-meta">{{ phaseState(step) }}<small v-if="stepDuration(step) != null"> · {{ formatDuration(stepDuration(step)) }}</small><small v-for="marker in phaseMarkers(step)" :key="marker"> · {{ marker }}</small></span>
          <span v-if="phaseDependencyTags(step, allSteps).length" class="tc-step-deps"><em v-for="tag in phaseDependencyTags(step, allSteps)" :key="tag" class="tc-step-dep-chip">{{ tag }}</em></span>
        </button>
        <button type="button" class="tc-step-inspect" :aria-label="`查看${stepLabel(step)}的时间、阶段事件与子步骤`" title="查看阶段关系与证据" aria-haspopup="dialog" @click="inspect(step)"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><circle cx="8" cy="8" r="5.5" fill="none" stroke="currentColor"/><path d="M8 7v4M8 4.5v1" stroke="currentColor" stroke-width="1.5"/></svg></button>
      </li>
    </ul>
    <p v-else class="tc-detail-muted">此运行没有完整步骤快照，可继续查看事件、日志和诊断资源。</p>
    <details v-if="allSteps.length" class="tc-flow-relations">
      <summary><span class="tc-flow-relations__title">依赖与完整阶段记录</span><span class="tc-flow-relations__count">{{ allSteps.length }} 个阶段</span></summary>
      <div class="tc-flow-relations__panel">
        <p class="tc-flow-relations__hint">{{ progress.structure?.parallelism === 'explicit' ? '并行分组来自执行记录；依赖关系单独显示。' : '已记录的阶段按首次出现时间排列；未记录的并行关系不作推断。' }}</p>
        <div class="tc-flow-relations__grid">
          <div v-for="step in allSteps" :key="stepId(step)" class="tc-flow-relation">
            <div class="tc-flow-relation__head"><strong>{{ stepLabel(step) }}</strong><span class="tc-flow-relation__status">{{ phaseState(step) }}</span></div>
            <StepRelations :step="step" :siblings="allSteps"/>
          </div>
        </div>
      </div>
    </details>
    <TaskFailure :failure="progress.failure" :execution="execution" :status="progress.outcome.status" />
    <div v-if="children.length" class="tc-child-tasks"><strong>独立子任务</strong><button v-for="child in children" :key="child.task_id" type="button" @click="emit('child', child.task_id, child.run_id)">{{ label('task_type', text(child.task_type)) }} #{{ child.task_id }} · {{ progressLabel(child.status) }}</button></div>
    <dialog ref="inspector" class="tc-step-dialog" aria-labelledby="tc-step-title" @cancel.prevent="closeInspector" @close="inspectedId = null" @wheel.stop="scrollInspector" @click="event => { if (event.target === inspector) closeInspector(); }">
      <header><h3 id="tc-step-title">{{ inspected ? stepLabel(inspected) : '步骤详情' }}</h3><button type="button" autofocus @click="closeInspector">关闭</button></header>
      <div class="tc-step-dialog-body"><StepEvidence v-if="inspected" :step="inspected" :siblings="allSteps" /></div>
    </dialog>
  </section>
</template>
