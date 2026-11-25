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
const stepCols=computed(()=>{
  const n=steps.value.length;
  if(n<=1)return 1;
  if(n===2)return 2;
  if(n===3||n===6)return 3;
  if(n===4||n===7||n===8)return 4;
  return 5;
});
function stepDeps(step:Step){
  const parts:string[]=[];
  if(step.depends_on?.length){
    parts.push('前置：'+step.depends_on.map(id=>{
      const related=steps.value.find(s=>s.id===id||stepId(s)===id);
      return related?stepLabel(related):id;
    }).join('、'));
  }
  if(step.execution?.condition?.label)parts.push('条件：'+step.execution.condition.label);
  if(step.execution?.parallel_group)parts.push('并行：'+step.execution.parallel_group);
  return parts.join(' · ');
}
function stepDialogBackdrop(event:MouseEvent){
  const el=dialog.value;
  if(!el||event.target!==el)return;
  const box=el.getBoundingClientRect();
  if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)inspected.value=undefined;
}
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
  <ul v-if="steps.length" class="registration-steps" :class="`is-count-${steps.length===1?'1':steps.length===2?'2':'many'}`" :style="{'--reg-step-cols':stepCols}" aria-label="注册执行阶段，排列不代表固定顺序">
    <li v-for="step in steps" :key="stepId(step)" :class="[`is-${stepState(step)}`, {'is-inspected': selected === step}]">
      <button type="button" :title="tooltip(step)" :aria-pressed="inline ? selected === step : undefined" @click="activateStep(step)">
        <strong class="registration-step-title">
          <span v-if="stepState(step)==='success' || stepState(step)==='recovered'" class="registration-step-mark" aria-hidden="true">✓</span>
          <span v-else-if="['failed','request_unknown','manual_reconcile','password_confirmation_pending'].includes(stepState(step))" class="registration-step-mark" aria-hidden="true">!</span>
          <span v-else-if="['running','active','queued','waiting','awaiting_confirmation'].includes(stepState(step))" class="registration-step-dot is-pulse" aria-hidden="true"></span>
          <span v-else-if="['stopped','interrupted','debug_paused','attention_required','partial_success','unconfirmed','record_incomplete','deferred'].includes(stepState(step))" class="registration-step-dot is-warning" aria-hidden="true"></span>
          <span v-else class="registration-step-dot is-muted" aria-hidden="true"></span>
          <span class="registration-step-name">{{ stepLabel(step) }}</span>
        </strong>
        <span class="registration-step-meta">
          <small class="registration-step-state">{{ phaseState(step) }}</small>
          <small data-registration-step-duration>耗时 {{ duration(step) }}</small>
        </span>
        <small v-for="marker in phaseMarkers(step)" :key="marker" class="registration-step-marker">{{ marker }}</small>
        <small v-if="pauseSummary(step)" class="registration-step-pause">{{ pauseSummary(step) }}</small>
        <span v-if="stepDeps(step)" class="registration-step-dep">{{ stepDeps(step) }}</span>
      </button>
      <button v-if="!inline" type="button" :aria-label="`查看${stepLabel(step)}的关系与证据`" @click="inspected=step">详情</button>
    </li>
  </ul>
  <div v-if="selected" class="registration-stage-selected" :data-tone="stepState(selected)">
    <div class="registration-stage-selected-info" aria-live="polite">
      <div class="registration-stage-selected-head">
        <strong>{{ stepLabel(selected) }}</strong>
        <span class="registration-stage-selected-state"> · {{ phaseState(selected) }}</span>
      </div>
      <p v-if="selected.reason || selected.message">{{ selected.reason || selected.message }}</p>
      <p v-else-if="focusFailure && stepId(selected) === object(job.progress?.failure).step_id && object(job.progress?.failure).message">
        {{ object(job.progress?.failure).message }}
      </p>
    </div>
    <div class="registration-batch-actions registration-stage-selected-actions">
      <button type="button" class="registration-stage-btn-detail" :aria-label="`查看${stepLabel(selected)}的关系与证据`" @click="inspected=selected">阶段详情</button>
      <button type="button" class="registration-stage-btn-log" @click="emit('log',stepId(selected))">阶段日志</button>
    </div>
  </div>
  <p v-else-if="!steps.length" class="registration-step-note">暂无阶段记录，可查看任务日志。</p>
  <details v-if="steps.length" class="registration-relations-details">
    <summary>依赖与执行记录</summary>
    <div class="registration-relations-list">
      <div v-for="step in steps" :key="stepId(step)" class="registration-relations-item">
        <div class="registration-relations-head">
          <strong>{{stepLabel(step)}}</strong>
          <span class="registration-relations-state">{{ phaseState(step) }}</span>
        </div>
        <StepRelations :step="step" :siblings="steps"/>
      </div>
    </div>
  </details>
  <dialog ref="dialog" class="registration-dialog registration-step-dialog" aria-label="注册步骤关系与证据" @cancel.prevent="inspected=undefined" @close="inspected=undefined" @click="stepDialogBackdrop">
    <header>
      <div class="registration-dialog-title">
        <h3>{{inspected?stepLabel(inspected):'步骤详情'}}</h3>
        <span v-if="inspected" class="registration-dialog-pill" :data-tone="stepState(inspected)">{{ phaseState(inspected) }}</span>
      </div>
      <button type="button" class="ui-button registration-dialog-close" @click="inspected=undefined">关闭</button>
    </header>
    <div class="registration-dialog-body">
      <p v-if="inspected&&pauseSummary(inspected)" class="registration-dialog-pause">{{pauseSummary(inspected)}}</p>
      <StepEvidence v-if="inspected" :step="inspected" :siblings="steps"/>
    </div>
  </dialog>
 </div>
</template>
