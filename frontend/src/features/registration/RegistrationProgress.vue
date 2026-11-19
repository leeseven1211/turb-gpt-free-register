<script setup lang="ts">
import {computed,ref} from 'vue';
import {useNativeDialog} from '../../shared/useNativeDialog';
import StepRelations from '../tasks/detail/StepRelations.vue';
import StepEvidence from '../tasks/detail/StepEvidence.vue';
import {phaseMarkers,phaseState,phaseSteps} from '../tasks/detail/flowPresentation';
import {formatDateTime,formatDuration} from '../tasks/presentation';
import {object,progressLabel,stepDuration,stepId,stepLabel,stepState,type Step} from '../tasks/detail/model';
const props=defineProps<{job:any;active:boolean;inline?:boolean;focusFailure?:boolean}>();
const emit=defineEmits<{log:[string]}>();
const steps=computed<Step[]>(()=>{
 const snapshot=[props.job?.progress,props.job?.progress_snapshot,props.job?.progress_v2].find(value=>Array.isArray(value?.main_steps));
 const list=snapshot?.main_steps||Object.entries(props.job?.progress_steps||{}).map(([id,value]:any)=>({id,...value}));
 return phaseSteps(list.map((step:any,index:number)=>({...step,id:String(step.id||step.step_id||step.key||`step-${index+1}`),label:step.label||step.name||step.id||step.step_id})));
});
const inspected=ref<Step>(),dialog=ref<HTMLDialogElement>();
const selectedId=ref<string>();
const selected=computed(()=>{
  if(!props.inline)return undefined;
  if(selectedId.value)return steps.value.find(step=>stepId(step)===selectedId.value);
  if(!props.focusFailure)return undefined;
  const recorded=String(object(props.job?.progress?.failure).step_id||'');
  return steps.value.find(step=>stepId(step)===recorded) || steps.value.find(step=>stepState(step)==='failed');
});
function activateStep(step:Step) {
  if(props.inline)selectedId.value=stepId(step);
  else emit('log',stepId(step));
}
useNativeDialog(dialog,()=>Boolean(inspected.value)&&props.active,()=>props.active);
const duration=(step:Step)=>formatDuration(stepDuration(step));
function pauseSummary(step:Step){const pause=object(step.debug_pause);return pause.state==='paused'?`调试暂停 · 等待结束调试${pause.paused_at?` · 暂停于 ${formatDateTime(pause.paused_at)}`:' · 暂停时间未记录'}${pause.hold_until?` · 保留至 ${formatDateTime(pause.hold_until)}`:''}`:'';}
function tooltip(step:Step){
 const attempts=step.attempts||[],children=step.children||[],stageLabel=(attempt:any)=>attempt.raw_stage_label||children.find(child=>child.id===attempt.raw_stage)?.label||attempt.raw_stage||'阶段';
 const observedStages=[...new Set(attempts.map(stageLabel))];
 return [`${stepLabel(step)} · ${phaseState(step)}`,pauseSummary(step),step.reason||step.message||'',`开始：${formatDateTime(step.started_at)}`,`结束：${formatDateTime(step.completed_at)}`,`耗时：${duration(step)}`,observedStages.length?`已记录阶段：${observedStages.join('、')}`:'',children.length?`子步骤（${children.length}）`:'',...children.map(child=>`${stepLabel(child)} · ${phaseState(child)} · ${duration(child)}${child.reason||child.message?`\n${child.reason||child.message}`:''}`),attempts.length?`阶段事件（${attempts.length} 条）`:'',...attempts.map((attempt:any,index:number)=>`${index+1}. ${stageLabel(attempt)} · ${progressLabel(attempt.display_status||attempt.state)}${attempt.created_at?` · ${formatDateTime(attempt.created_at)}`:attempt.event_time_known===false?' · 发生时间未记录':''}${attempt.message?`\n${attempt.message}`:''}`),props.inline?'点击步骤查看阶段摘要':'点击步骤查看对应日志'].filter(Boolean).join('\n');
}
</script>
<template>
 <div class="registration-progress">
  <div v-if="steps.length" class="registration-stage-heading">
    <h3 v-if="inline">执行阶段</h3>
    <p class="registration-step-note">按首次记录排列，不代表固定执行顺序</p>
  </div>
  <ul v-if="steps.length" class="registration-steps" aria-label="注册执行阶段，排列不代表固定顺序">
    <li v-for="step in steps" :key="stepId(step)" :class="[`is-${stepState(step)}`, {'is-inspected': selected === step}]">
      <button type="button" :title="tooltip(step)" :aria-pressed="inline ? selected === step : undefined" @click="activateStep(step)">
        <strong>
          <span v-if="stepState(step)==='success'" class="registration-step-mark" aria-hidden="true">✓</span>
          <span v-else-if="stepState(step)==='failed'" class="registration-step-mark" aria-hidden="true">!</span>
          {{ stepLabel(step) }}
        </strong>
        <small>{{ phaseState(step) }}</small>
        <small data-registration-step-duration>耗时 {{ duration(step) }}</small>
        <small v-for="marker in phaseMarkers(step)" :key="marker">{{ marker }}</small>
        <small v-if="pauseSummary(step)">{{ pauseSummary(step) }}</small>
      </button>
      <button v-if="!inline" type="button" :aria-label="`查看${stepLabel(step)}的关系与证据`" @click="inspected=step">详情</button>
    </li>
  </ul>
  <div v-if="selected" class="registration-stage-selected">
    <div aria-live="polite">
      <strong>{{ stepLabel(selected) }}</strong>
      <span> · {{ phaseState(selected) }}</span>
      <p v-if="selected.reason || selected.message">{{ selected.reason || selected.message }}</p>
      <p v-else-if="focusFailure && stepId(selected) === object(job.progress?.failure).step_id && object(job.progress?.failure).message">
        {{ object(job.progress?.failure).message }}
      </p>
    </div>
    <div class="registration-batch-actions">
      <button type="button" :aria-label="`查看${stepLabel(selected)}的关系与证据`" @click="inspected=selected">阶段详情</button>
      <button type="button" @click="emit('log',stepId(selected))">阶段日志</button>
    </div>
  </div>
  <p v-else-if="!steps.length" class="registration-step-note">暂无阶段记录，可查看任务日志。</p>
  <details v-if="steps.length"><summary>依赖与执行记录</summary><div v-for="step in steps" :key="stepId(step)"><strong>{{stepLabel(step)}}</strong><StepRelations :step="step" :siblings="steps"/></div></details>
  <dialog ref="dialog" class="registration-dialog" aria-label="注册步骤关系与证据" @cancel.prevent="inspected=undefined" @close="inspected=undefined"><header><h3>{{inspected?stepLabel(inspected):'步骤详情'}}</h3><button type="button" @click="inspected=undefined">关闭</button></header><p v-if="inspected&&pauseSummary(inspected)">{{pauseSummary(inspected)}}</p><StepEvidence v-if="inspected" :step="inspected" :siblings="steps"/></dialog>
 </div>
</template>
