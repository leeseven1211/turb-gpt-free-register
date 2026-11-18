<script setup lang="ts">
import {onBeforeUnmount,onMounted,ref,shallowRef} from 'vue';
import type {AccountActionContext} from './useAccounts';
import {ACCOUNT_TOOLBAR_BUTTONS,ACCOUNT_TOOLBAR_SECTIONS,type AccountToolbarButton,type AccountToolbarCapabilities,type AccountToolbarInvoke,type AccountToolbarState} from './accountToolbar';
import {useAccountQuickActions,type AccountQuickActionRuntime} from './useAccountQuickActions';
const props=defineProps<{
  state:AccountToolbarState;capabilities:AccountToolbarCapabilities;getContext:()=>AccountActionContext;
  invoke:AccountToolbarInvoke;runtime:AccountQuickActionRuntime;notify?:(message:string)=>void;
}>();
const toolbar=ref<HTMLElement>(),more=ref<HTMLDetailsElement>(),ready=ref(false);
const homeSlots=new Map<string,HTMLElement>(),quickSlots=new Map<number,HTMLElement>();
const pending=shallowRef<ReadonlySet<string>>(new Set());
const usage=useAccountQuickActions(ACCOUNT_TOOLBAR_BUTTONS.map(item=>item.id),props.runtime,()=>{
  const root=toolbar.value,doc=root?.ownerDocument;
  return !!(more.value?.open||doc?.querySelector('dialog[open]')||root?.contains(doc?.activeElement??null));
});
function slot(map:Map<string,HTMLElement>|Map<number,HTMLElement>,key:string|number,node:unknown){
  const slots=map as Map<string|number,HTMLElement>;
  if(node&&typeof node==='object'&&'nodeType' in node)slots.set(key,node as HTMLElement);else slots.delete(key);
}
function target(item:AccountToolbarButton):HTMLElement{
  const position=usage.quickIds.value.indexOf(item.id);
  return (position>=0?quickSlots.get(position):homeSlots.get(item.id))!;
}
const gate=(item:AccountToolbarButton)=>item.feature?props.capabilities[item.feature]:undefined;
const unavailable=(item:AccountToolbarButton)=>gate(item)?.enabled===false;
const disabled=(item:AccountToolbarButton)=>(item.selection&&props.state.selectedCount===0)||pending.value.has(item.action)||!!props.state.pending?.[item.action];
const label=(item:AccountToolbarButton)=>props.state.labels?.[item.action]||(item.id==='btnArchiveSelectedAccountsV2'&&props.state.archived?'恢复选中':item.label);
const baseTitle=(item:AccountToolbarButton)=>item.id==='btnArchiveSelectedAccountsV2'&&props.state.archived?'把选中的归档账号恢复到默认账号列表':item.title;
const title=(item:AccountToolbarButton)=>unavailable(item)?`不可用：${gate(item)?.reason||'缺少必要配置'}`:baseTitle(item);
async function invoke(item:AccountToolbarButton,event:MouseEvent){
  const trigger=event.currentTarget as HTMLButtonElement;
  if(disabled(item)||unavailable(item)||trigger.disabled||trigger.getAttribute('aria-disabled')==='true')return;
  usage.record(item.id);pending.value=new Set([...pending.value,item.action]);
  try{await props.invoke(item.action,props.getContext(),trigger);}
  catch(error){props.notify?.(error instanceof Error?error.message:'账号操作失败，请稍后重试。');}
  finally{const next=new Set(pending.value);next.delete(item.action);pending.value=next;}
}
let documentOwner:Document|undefined;
onMounted(()=>{documentOwner=toolbar.value?.ownerDocument;documentOwner?.addEventListener('close',usage.schedule,true);ready.value=true;usage.refresh();});
onBeforeUnmount(()=>documentOwner?.removeEventListener('close',usage.schedule,true));
defineExpose({refreshQuickActions:usage.refresh});
</script>
<template>
  <div class="accounts-command-deck" id="accountsCommandDeck">
    <div ref="toolbar" class="jobs-toolbar-v2 list-action-toolbar" id="accountsToolbarV2" :class="{'has-selection':state.selectedCount>0}" @focusout="usage.schedule">
      <span class="list-selection-hint" id="accountsSelectedHintV2">{{ state.selectedCount?`已选 ${state.selectedCount} 个账号`:'选择账号后批量操作' }}</span>
      <div class="acc-v2-btn-group account-quick-actions" id="accountsQuickActionsV2" role="group" aria-label="常用账号操作，按此浏览器使用次数排序" title="显示此浏览器使用次数最多的五项操作，批量操作一次算一次">
        <span v-for="position in 5" :key="position" :ref="node=>slot(quickSlots,position-1,node)" class="account-action-slot"></span>
      </div>
      <details ref="more" class="toolbar-overflow" id="accountsMoreActionsV2" @toggle="usage.schedule">
        <summary>更多操作</summary>
        <div class="toolbar-overflow-menu">
          <div v-for="section in ACCOUNT_TOOLBAR_SECTIONS" :key="section" class="toolbar-overflow-section toolbar-overflow-section--wide">
            <span class="toolbar-overflow-section-title">{{ section }}</span>
            <span v-for="item in ACCOUNT_TOOLBAR_BUTTONS.filter(item=>item.section===section)" :key="item.id" :ref="node=>slot(homeSlots,item.id,node)" class="account-action-slot"></span>
          </div>
        </div>
      </details>
    </div>
    <template v-if="ready">
      <Teleport v-for="item in ACCOUNT_TOOLBAR_BUTTONS" :key="item.id" :to="target(item)">
        <button type="button" :id="item.id" :class="[item.className,{'feature-unavailable':unavailable(item)}]" :disabled="disabled(item)" :title="title(item)"
          :data-feature="gate(item)?item.feature:undefined" :data-feature-base-title="gate(item)?baseTitle(item):undefined" :aria-disabled="gate(item)?unavailable(item):undefined" @click="invoke(item,$event)">{{ label(item) }}</button>
      </Teleport>
    </template>
  </div>
</template>
<style scoped>
.account-action-slot{display:contents}
</style>
