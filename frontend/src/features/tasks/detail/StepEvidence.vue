<script setup lang="ts">
import { formatDateTime, formatDuration } from '../presentation';
import { object, progressLabel, stepDuration, stepLabel, stepState, text, type Step } from './model';
import {phaseState, phaseSteps} from './flowPresentation';
import StepRelations from './StepRelations.vue';
defineProps<{ step: Step; siblings?: Step[] }>();
</script>

<template>
  <section class="tc-step-evidence">
    <p v-if="step.reason || step.message" class="tc-step-evidence__summary">{{ step.reason || step.message }}</p>
    <dl class="tc-detail-facts">
      <div><dt>状态</dt><dd>{{ phaseState(step) }}</dd></div>
      <div><dt>开始</dt><dd>{{ formatDateTime(step.started_at) }}</dd></div>
      <div><dt>结束</dt><dd>{{ formatDateTime(step.completed_at) }}</dd></div>
      <div><dt>耗时</dt><dd>{{ formatDuration(stepDuration(step)) }}</dd></div>
      <div v-if="step.raw_stages?.length"><dt>原始阶段</dt><dd>{{ step.raw_stages.join('、') }}</dd></div>
    </dl>
    <StepRelations :step="step" :siblings="siblings"/>
    <details v-if="step.step_instances?.length" class="tc-technical"><summary>阶段实例（{{ step.step_instances.length }}）</summary><ol class="tc-attempt-list"><li v-for="(instance, index) in step.step_instances" :key="text(instance.step_instance_id) || index"><strong>记录 {{ index + 1 }} · {{ progressLabel(instance.state) }}</strong><p>{{ formatDateTime(instance.started_at) }} → {{ formatDateTime(instance.completed_at) }}</p><p v-if="instance.message">{{ instance.message }}</p></li></ol></details>
    <details v-if="step.attempts?.length" class="tc-technical">
      <summary>阶段事件（{{ step.attempts.length }}）</summary>
      <ol class="tc-attempt-list">
        <li v-for="(attempt, index) in step.attempts" :key="text(attempt.event_id) || index">
          <div class="tc-event-meta"><strong>记录 {{ index + 1 }} · {{ progressLabel(attempt.display_status || attempt.state) }}</strong><time>{{ !attempt.created_at && attempt.event_time_known === false ? '发生时间未记录' : formatDateTime(text(attempt.created_at)) }}</time></div>
          <p>{{ attempt.message || '无补充说明' }}</p>
          <small>{{ attempt.raw_stage_label || attempt.raw_stage }}<template v-if="attempt.event_id"> · 事件 {{ attempt.event_id }}</template></small>
          <details><summary>技术字段</summary><pre>{{ JSON.stringify(attempt, null, 2) }}</pre></details>
        </li>
      </ol>
    </details>
    <details v-if="phaseSteps(step.children).length" class="tc-technical">
      <summary>子步骤（{{ phaseSteps(step.children).length }}）</summary>
      <section v-for="child in phaseSteps(step.children)" :key="child.id" class="tc-child-step">
        <h4>{{ stepLabel(child) }} <span>{{ progressLabel(stepState(child)) }}</span></h4>
        <StepEvidence :step="child" :siblings="step.children"/>
      </section>
    </details>
    <details v-if="step.evidence && Object.keys(object(step.evidence)).length" class="tc-technical"><summary>步骤证据</summary><pre>{{ JSON.stringify(step.evidence, null, 2) }}</pre></details>
  </section>
</template>
