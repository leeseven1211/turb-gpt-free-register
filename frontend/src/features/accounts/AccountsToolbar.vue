<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,shallowRef} from 'vue';
import type {AccountActionContext} from './useAccounts';
import {ACCOUNT_TOOLBAR_BUTTONS,ACCOUNT_TOOLBAR_SECTIONS,type AccountToolbarButton,type AccountToolbarCapabilities,type AccountToolbarInvoke,type AccountToolbarState} from './accountToolbar';
import {useAccountQuickActions,type AccountQuickActionRuntime} from './useAccountQuickActions';
const props=defineProps<{
  state:AccountToolbarState;capabilities:AccountToolbarCapabilities;getContext:()=>AccountActionContext;
  invoke:AccountToolbarInvoke;runtime:AccountQuickActionRuntime;notify?:(message:string)=>void;
}>();
const toolbar=ref<HTMLElement>(),more=ref<HTMLDetailsElement>(),summary=ref<HTMLElement>();
const sections=ACCOUNT_TOOLBAR_SECTIONS.map(title=>({
  title,
  items:ACCOUNT_TOOLBAR_BUTTONS.filter(item=>item.section===title),
}));
const buttonsById=new Map(ACCOUNT_TOOLBAR_BUTTONS.map(item=>[item.id,item]));
const pending=shallowRef<ReadonlySet<string>>(new Set());
const usage=useAccountQuickActions(ACCOUNT_TOOLBAR_BUTTONS.map(item=>item.id),props.runtime,()=>{
  const root=toolbar.value,doc=root?.ownerDocument;
  return !!(more.value?.open||doc?.querySelector('dialog[open]')||root?.contains(doc?.activeElement??null));
});
const quickItems=computed(()=>usage.quickIds.value.map(id=>buttonsById.get(id)!));
const gate=(item:AccountToolbarButton)=>item.feature?props.capabilities[item.feature]:undefined;
const unavailable=(item:AccountToolbarButton)=>gate(item)?.enabled===false;
const disabled=(item:AccountToolbarButton)=>(item.selection&&props.state.selectedCount===0)||pending.value.has(item.action)||!!props.state.pending?.[item.action];
const label=(item:AccountToolbarButton)=>props.state.labels?.[item.action]||(item.id==='btnArchiveSelectedAccountsV2'&&props.state.archived?'恢复选中':item.label);
const baseTitle=(item:AccountToolbarButton)=>item.id==='btnArchiveSelectedAccountsV2'&&props.state.archived?'把选中的归档账号恢复到默认账号列表':item.title;
function buttonAttributes(item:AccountToolbarButton){
  const capability=gate(item);
  const unavailable=capability?.enabled===false;
  return {
    class:[item.className,{'feature-unavailable':unavailable}],
    disabled:disabled(item),
    title:unavailable?`不可用：${capability.reason||'缺少必要配置'}`:baseTitle(item),
    'data-feature':capability?item.feature:undefined,
    'data-feature-base-title':capability?baseTitle(item):undefined,
    'aria-disabled':capability?unavailable:undefined,
  };
}
function dismiss(event:KeyboardEvent){
  if(!more.value?.open)return;
  event.preventDefault();
  event.stopPropagation();
  more.value.open=false;
  summary.value?.focus({preventScroll:true});
}
function fitMenu(){
  const menu=more.value;
  const viewport=menu?.ownerDocument.defaultView;
  const anchor=toolbar.value?.closest('.ac-toolbar');
  if(!menu?.open||!viewport||!anchor)return;
  const bottom=anchor.getBoundingClientRect().bottom;
  menu.style.setProperty('--ac-batch-menu-height',`${Math.max(0,viewport.innerHeight-bottom-12)}px`);
}
function onToggle(){
  fitMenu();
  usage.schedule();
}
async function invoke(item:AccountToolbarButton,event:MouseEvent){
  const trigger=event.currentTarget as HTMLButtonElement;
  if(disabled(item)||unavailable(item)||trigger.disabled||trigger.getAttribute('aria-disabled')==='true')return;
  usage.record(item.id);pending.value=new Set([...pending.value,item.action]);
  try{await props.invoke(item.action,props.getContext(),trigger);}
  catch(error){props.notify?.(error instanceof Error?error.message:'账号操作失败，请稍后重试。');}
  finally{const next=new Set(pending.value);next.delete(item.action);pending.value=next;}
}
let documentOwner:Document|undefined;
onMounted(()=>{
  documentOwner=toolbar.value?.ownerDocument;
  const viewport=documentOwner?.defaultView;
  viewport?.addEventListener('resize',fitMenu);
  viewport?.addEventListener('scroll',fitMenu,{passive:true});
  documentOwner?.addEventListener('close',usage.schedule,true);
  usage.refresh();
});
onBeforeUnmount(()=>{
  const viewport=documentOwner?.defaultView;
  viewport?.removeEventListener('resize',fitMenu);
  viewport?.removeEventListener('scroll',fitMenu);
  documentOwner?.removeEventListener('close',usage.schedule,true);
});
defineExpose({refreshQuickActions:usage.refresh});
</script>
<template>
  <div class="accounts-command-deck" id="accountsCommandDeck">
    <div ref="toolbar" class="jobs-toolbar-v2 list-action-toolbar" id="accountsToolbarV2" :class="{'has-selection':state.selectedCount>0}" @focusout="usage.schedule">
      <span class="list-selection-hint" id="accountsSelectedHintV2">{{ state.selectedCount?`已选 ${state.selectedCount} 个账号`:'选择账号后批量操作' }}</span>

      <details ref="more" class="toolbar-overflow" id="accountsMoreActionsV2" @toggle="onToggle" @keydown.esc="dismiss">
        <summary ref="summary">批量操作</summary>
        <div class="toolbar-overflow-menu">
          <div v-for="section in sections" :key="section.title" class="toolbar-overflow-section toolbar-overflow-section--wide">
            <span class="toolbar-overflow-section-title">{{ section.title }}</span>
            <button v-for="item in section.items" :key="item.id" :id="item.id" type="button"
              v-bind="buttonAttributes(item)" @click="invoke(item,$event)">{{ label(item) }}</button>
          </div>
        </div>
      </details>
      <div class="acc-v2-btn-group account-quick-actions" id="accountsQuickActionsV2" role="group" aria-label="常用账号操作，按此浏览器使用次数排序" title="显示此浏览器使用次数最多的五项操作，批量操作一次算一次">
        <button v-for="item in quickItems" :key="item.id" :data-account-shortcut="item.id" type="button"
          v-bind="buttonAttributes(item)" @click="invoke(item,$event)">{{ label(item) }}</button>
      </div>
    </div>
  </div>
</template>
