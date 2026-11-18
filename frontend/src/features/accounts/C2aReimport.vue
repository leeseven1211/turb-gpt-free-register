<script setup lang="ts">
import {nextTick,onBeforeUnmount,ref} from 'vue';
import type {AccountActionContext} from './useAccounts';
import {useC2aReimport,type C2aReimportDependencies,type C2aReceiptEntry} from './useC2aReimport';
const props=defineProps<{deps:C2aReimportDependencies}>();
const dialog=ref<HTMLDialogElement>();
let disposed=false,handledCloseEvents=0,generation=0,focusFrame:number|undefined;
function restoreTrigger(trigger:HTMLElement|null,ticket:number){
  if(disposed||!trigger?.isConnected||typeof trigger.focus!=='function')return;
  trigger.focus({preventScroll:true});
  focusFrame=requestAnimationFrame(()=>{focusFrame=undefined;if(disposed||generation!==ticket||owner.isOpen.value)return;const more=trigger.closest<HTMLDetailsElement>('#accountsMoreActionsV2');const target=more?.open===false?more.querySelector<HTMLElement>('summary'):trigger;if(target?.isConnected)target.focus({preventScroll:true});});
}
const owner=useC2aReimport({...props.deps,beginBusy:(trigger,label)=>{
  if(props.deps.beginBusy)return props.deps.beginBusy(trigger,label);
  const button=trigger instanceof HTMLButtonElement?trigger:null,old=button?.textContent||'';
  if(button){button.disabled=true;button.textContent=label;}
  return()=>{if(button){button.textContent=old;button.disabled=false;}};
}},{closed:(trigger,returnValue)=>{
  if(dialog.value?.open){++handledCloseEvents;dialog.value.close(returnValue);}
  restoreTrigger(trigger,generation);
}});
const {isOpen,submitting,status,accountIds,result,receiptEntries,taskEntries,summary}=owner;
function open(context:AccountActionContext,trigger:HTMLElement|null=null){
  if(!dialog.value||typeof dialog.value.showModal!=='function'){props.deps.notify('C2A 同步确认窗口不可用，请刷新页面后重试');return false;}
  if(!owner.open(context,trigger))return false;
  ++generation;if(focusFrame!==undefined){cancelAnimationFrame(focusFrame);focusFrame=undefined;}
  void nextTick(()=>{if(!disposed&&isOpen.value&&!dialog.value?.open)dialog.value?.showModal();});return true;
}
function close(returnValue='cancel',options:{force?:boolean}={}){return owner.close(returnValue,options.force);}
function nativeClose(){if(handledCloseEvents){--handledCloseEvents;return;}if(dialog.value?.open)return;owner.close(dialog.value?.returnValue||'cancel',true);}
function cancel(event:Event){if(submitting.value)event.preventDefault();}
function subject(entry:C2aReceiptEntry,index:number){const id=Number(entry.item.id);return Number.isInteger(id)&&id>0?`账号 #${id}`:`提交项 #${Number(entry.item.input_index)||index+1}`;}
function details(entry:C2aReceiptEntry){return[entry.item.email,entry.item.error_code,entry.item.reason||entry.item.error].filter(Boolean).map(String).join(' · ');}
onBeforeUnmount(()=>{disposed=true;++generation;if(focusFrame!==undefined)cancelAnimationFrame(focusFrame);owner.close('cancel',true);});
defineExpose({open,close,submit:owner.submit,showResult:owner.showResult,openTasks:owner.openTasks,isSubmitting:submitting});
</script>
<template>
  <Teleport to="#accountC2aConfirmHost">
    <dialog ref="dialog" @close="nativeClose" @cancel="cancel" id="c2aReimportConfirmModal" aria-labelledby="c2aReimportConfirmTitle" aria-describedby="c2aReimportConfirmDescription">
      <div class="c2a-reimport-confirm-head">
        <div>
          <p class="c2a-reimport-confirm-kicker">本地 AT · 远端账号更新</p>
          <h3 id="c2aReimportConfirmTitle">批量同步到 C2A</h3>
          <p id="c2aReimportConfirmDescription">只把本地当前 AT 更新到同邮箱唯一匹配的既有 C2A 账号。</p>
        </div>
        <button type="button" class="c2a-reimport-confirm-close" id="btnCloseC2aReimportV2" :disabled="submitting" @click="close()" aria-label="关闭 C2A 同步确认窗口">×</button>
      </div>
      <div class="c2a-reimport-confirm-body">
        <p class="c2a-reimport-confirm-scope">将为 <strong id="c2aReimportConfirmCountV2">{{ accountIds.length }}</strong> 个已选账号创建同步任务。</p>
        <section class="c2a-reimport-confirm-note" aria-labelledby="c2aReimportConfirmScopeTitle">
          <h4 id="c2aReimportConfirmScopeTitle">更新范围</h4>
          <ul>
            <li>任务执行时读取本地保存的当前 AT；不会刷新本地 AT，也不会重新登录。</li>
            <li>只按完整邮箱唯一匹配既有 C2A 账号，并更新该账号的 AT；不会创建、删除、分组、代理、启用或更新 refresh_token。</li>
          </ul>
        </section>
        <section class="c2a-reimport-confirm-note" aria-labelledby="c2aReimportConfirmSafetyTitle">
          <h4 id="c2aReimportConfirmSafetyTitle">提交安全条件</h4>
          <p>任务写入前会确认 C2A 的“自动移除异常账号”和“自动移除限流账号”都已关闭；无法确认或任一开关开启时，不会发送更新。执行期间请保持两个开关关闭。</p>
        </section>
        <section class="c2a-reimport-confirm-note c2a-reimport-confirm-note--warning" aria-labelledby="c2aReimportConfirmSideEffectTitle">
          <h4 id="c2aReimportConfirmSideEffectTitle">C2A 端状态可能变化</h4>
          <p>当前 C2A 通用更新接口会按自身规则清除凭据错误。AT 更新确认后，异常账号可能恢复正常；最终以 C2A 状态和任务回执为准。</p>
        </section>
        <p class="c2a-reimport-confirm-status" id="c2aReimportConfirmStatusV2" role="status" aria-live="polite" aria-atomic="true" :hidden="!status">{{ status }}</p>
      </div>
      <div class="c2a-reimport-confirm-foot">
        <button type="button" class="jobs-tb-btn" id="btnCancelC2aReimportV2" :disabled="submitting" @click="close()">取消</button>
        <button type="button" class="jobs-tb-btn jobs-tb-btn--primary" id="btnConfirmC2aReimportV2" :disabled="submitting" @click="owner.submit">{{ submitting?'正在提交…':'提交并入队' }}</button>
      </div>
    </dialog>
  </Teleport>
  <Teleport to="#accountC2aReceiptHost">
    <div class="column-filter-summary account-search-summary" id="accountC2aReimportResultV2" role="status" aria-live="polite" :hidden="!result">
      <span class="column-filter-summary-label">{{ summary }}</span>
      <button v-if="taskEntries.length" type="button" class="jobs-tb-btn" data-c2a-reimport-tasks @click="owner.openTasks()">打开任务中心</button>
      <details v-if="receiptEntries.length" :key="summary" :open="receiptEntries.some(entry=>entry.state!=='已入队')"><summary>查看{{ receiptEntries.some(entry=>entry.state!=='已入队')?'任务与未入队原因':'任务' }}</summary><ul>
        <li v-for="(entry,index) in receiptEntries" :key="index">{{ subject(entry,index) }} · {{ entry.state }}{{ details(entry)?` · ${details(entry)}`:'' }}<button v-if="Number(entry.item.task_id)>0" type="button" class="jobs-tb-btn" :data-c2a-reimport-task="taskEntries.indexOf(entry)" @click="owner.openTasks([entry.item])">查看任务 #{{ Number(entry.item.task_id) }}</button></li>
      </ul></details>
    </div>
  </Teleport>
</template>
