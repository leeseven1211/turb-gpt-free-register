<script setup lang="ts">
import {computed,onBeforeUnmount,ref,shallowRef} from 'vue';
import type {RegistrationRetryEntry,RegistrationRetryReceipt} from './setupActions';
import type {AccountActionContext} from './useAccounts';

const props=defineProps<{notify?:(message:string)=>void}>();
type OpenTasks=(entries:readonly RegistrationRetryEntry[])=>void|Promise<void>;
interface ReceiptState {result:Partial<RegistrationRetryReceipt>;context:AccountActionContext|null;open:OpenTasks}
const state=shallowRef<ReceiptState|null>(null),revision=ref(0);
let disposed=false;
function copy<T>(value:T):T{
  if(Array.isArray(value))return Object.freeze(value.map(copy)) as T;
  if(value&&typeof value==='object')return Object.freeze(Object.fromEntries(Object.entries(value).map(([key,item])=>[key,copy(item)]))) as T;
  return value;
}
const started=computed(()=>Array.isArray(state.value?.result.started)?state.value.result.started:[]);
const reused=computed(()=>Array.isArray(state.value?.result.reused)?state.value.result.reused:[]);
const skipped=computed(()=>Array.isArray(state.value?.result.skipped)?state.value.result.skipped:[]);
const tasks=computed(()=>[...started.value,...reused.value]);
const summary=computed(()=>{
  const result=state.value?.result;
  return `注册重跑：已创建 ${Number(result?.started_count??started.value.length)} 个，进行中 ${Number(result?.reused_count??reused.value.length)} 个，跳过 ${Number(result?.skipped_count??skipped.value.length)} 个`;
});
const taskId=(entry:RegistrationRetryEntry)=>entry.task_id||entry.operation_task_id;
const targetId=(entry:RegistrationRetryEntry)=>taskId(entry)||entry.job_id;
function showResult(result:Partial<RegistrationRetryReceipt>,context:AccountActionContext|null,open:OpenTasks){
  if(disposed)return;
  state.value={result:copy(result),context:copy(context),open};++revision.value;
}
async function openTasks(items:readonly RegistrationRetryEntry[]=tasks.value){
  if(disposed||!state.value)return;
  const open=state.value.open;
  try{await open(copy(items));}
  catch(error){if(!disposed)props.notify?.('注册重跑请求已处理，打开任务失败: '+(error instanceof Error?error.message:'请求失败'));}
}
onBeforeUnmount(()=>{disposed=true;state.value=null;});
defineExpose({showResult,openTasks});
</script>

<template>
  <Teleport to="#accountRegistrationReceiptHost">
    <div id="accountRegistrationRetryResultV2" class="column-filter-summary account-search-summary" role="status" aria-live="polite" :hidden="!state">
      <span class="column-filter-summary-label">{{ state?summary:'' }}</span>
      <button v-if="tasks.length" type="button" class="jobs-tb-btn" data-registration-retry-tasks @click="openTasks()">打开任务中心</button>
      <details v-if="tasks.length||skipped.length" :key="revision">
        <summary>查看{{ skipped.length?'任务及跳过原因':'任务' }}</summary>
        <ul>
          <li v-for="(item,index) in tasks" :key="`task-${index}`">账号 #{{ item.account_id }} · {{ index<started.length?'已创建':'进行中' }} <button type="button" class="jobs-tb-btn" :data-registration-retry-result="index" :data-registration-retry-task-id="taskId(item)||undefined" :data-registration-retry-run-id="taskId(item)&&item.run_id?item.run_id:undefined" @click="openTasks([item])">查看任务{{ targetId(item)?` #${targetId(item)}`:'' }}</button></li>
          <li v-for="(item,index) in skipped" :key="`skipped-${index}`">账号 #{{ item.account_id }} · {{ item.reason||item.error||'当前不可重跑' }}</li>
        </ul>
      </details>
    </div>
  </Teleport>
</template>
