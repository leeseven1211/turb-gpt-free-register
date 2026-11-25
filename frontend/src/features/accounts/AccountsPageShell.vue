<script setup lang="ts">
import {computed,onBeforeUnmount,ref,shallowRef} from 'vue';
import type {AccountsReadApi} from '../../api/accounts';
import type {AccountDetailReadApi} from '../../api/accountDetail';
import type {AccountQueryAdapter} from './queryAdapter';
import type {AccountPresentation,AccountsCallbacks,AccountsLegacyState} from './presentation';
import AccountsToolbar from './AccountsToolbar.vue';
import {ACCOUNT_TOOLBAR_BUTTONS,type AccountToolbarCapabilities} from './accountToolbar';
import type {AccountViewRow} from './useAccounts';
import type {AccountActionContext} from './useAccounts';
import type {AccountActionDispatcher} from './actions';
import AccountsList from './AccountsList.vue';
import AccountDetail from './AccountDetail.vue';
import Inspection from './Inspection.vue';
import EmailChange from './EmailChange.vue';
import C2aReimport from './C2aReimport.vue';
import RegistrationRetryReceipt from './RegistrationRetryReceipt.vue';
import AccountOperationReceipts from './AccountOperationReceipts.vue';
import type {RegistrationRetryEntry,RegistrationRetryReceipt as RegistrationReceipt} from './setupActions';
import type {C2aReimportDependencies} from './useC2aReimport';
import type {AccountEmailChangeDependencies} from './useAccountEmailChange';
import type {AccountInspectionDependencies,InspectionDialog} from './useAccountInspection';

const props=defineProps<{
  adapter:AccountQueryAdapter;api:AccountsReadApi;presentation:AccountPresentation;callbacks:AccountsCallbacks;
  detailApi:AccountDetailReadApi;
  detailPresentation:{renderBody(row:AccountViewRow):string;sourceLabel(value:unknown):string};
  syncModalScrollLock:()=>void;
  actions:AccountActionDispatcher;
  inspectionDependencies:AccountInspectionDependencies;
  emailChangeDependencies:AccountEmailChangeDependencies;
  c2aDependencies:C2aReimportDependencies;
  initialCapabilities:AccountToolbarCapabilities;
}>();
const list=ref<InstanceType<typeof AccountsList>>(),drawer=ref<InstanceType<typeof AccountDetail>>();
const inspection=ref<InstanceType<typeof Inspection>>();
const emailChange=ref<InstanceType<typeof EmailChange>>();
const c2a=ref<InstanceType<typeof C2aReimport>>();
const toolbar=ref<InstanceType<typeof AccountsToolbar>>();
const registrationReceipt=ref<InstanceType<typeof RegistrationRetryReceipt>>();
const toolbarSnapshot=shallowRef<AccountsLegacyState>(),capabilities=shallowRef(props.initialCapabilities),pendingVersion=ref(0);
const busyLabels=shallowRef<Readonly<Record<string,string>>>({});
function owner(){if(!list.value)throw new Error('账号列表正在加载，请稍后重试');return list.value;}
const toolbarState=computed(()=>{
  void pendingVersion.value;
  const context=list.value?.getActionContext();
  const pending=context?Object.fromEntries(ACCOUNT_TOOLBAR_BUTTONS.map(button=>[button.action,props.actions.isPending(button.action,context)])):{};
  pending.reimportSelectedC2a=c2a.value?.isSubmitting===true;
  return{selectedCount:toolbarSnapshot.value?.selectedIds.length||0,archived:toolbarSnapshot.value?.archived==='only',pending,labels:busyLabels.value};
});
async function invoke(action:string,context:AccountActionContext,trigger:HTMLElement|null=null){
  const promise=props.actions.isSupported(action)?props.actions.invoke(action,context,trigger):props.callbacks.invoke(action,context,trigger);
  ++pendingVersion.value;
  try{await promise;}finally{++pendingVersion.value;}
}
const callbacks:AccountsCallbacks={...props.callbacks,
  invoke,
  onStateChange:state=>{toolbarSnapshot.value=state;props.callbacks.onStateChange?.(state);},
  openDetail:(id,row,lease,trigger)=>{if(!drawer.value){lease.release();return;}drawer.value.open(id,row,lease,trigger);},
  closeConsumers:(restoreFocus=true)=>{drawer.value?.close(restoreFocus);props.callbacks.closeConsumers?.(restoreFocus);},
};
const detailCallbacks={notify:(message:string)=>props.callbacks.notify?.(message),syncModalScrollLock:()=>props.syncModalScrollLock()};
onBeforeUnmount(()=>props.actions.dispose());
defineExpose({
  setVisible:(value:boolean)=>{props.actions.setVisible(value);owner().setVisible(value);},setArchived:(value:boolean)=>owner().setArchived(value),
  refresh:()=>owner().refresh(),pollStatuses:()=>owner().pollStatuses(),
  getAccountSelectionSnapshot:(...args:Parameters<InstanceType<typeof AccountsList>['getAccountSelectionSnapshot']>)=>owner().getAccountSelectionSnapshot(...args),
  getActionContext:(...args:Parameters<InstanceType<typeof AccountsList>['getActionContext']>)=>owner().getActionContext(...args),
  getRowSnapshot:(id:string)=>owner().getRowSnapshot(id),openPlanDetailsConsumer:(id:string)=>owner().openPlanDetailsConsumer(id),
  removeAcknowledgedSelection:(ids:string[])=>owner().removeAcknowledgedSelection(ids),clearSelection:()=>owner().clearSelection(),
  setPage:(value:number)=>owner().setPage(value),setSize:(value:number)=>owner().setSize(value),
  updateQuery:(...args:Parameters<InstanceType<typeof AccountsList>['updateQuery']>)=>owner().updateQuery(...args),
  updateFilters:(...args:Parameters<InstanceType<typeof AccountsList>['updateFilters']>)=>owner().updateFilters(...args),
  resetFilters:()=>owner().resetFilters(),resetColumns:()=>owner().resetColumns(),
  openDetail:(id:string,trigger:HTMLElement|null=null)=>owner().openDetail(id,trigger),
  closeDetail:(restoreFocus=true)=>drawer.value?.close(restoreFocus),
  isActionSupported:(action:string)=>props.actions.isSupported(action),
  isActionPending:(action:string)=>props.actions.isPending(action,owner().getActionContext()),
  invokeAction:invoke,
  syncToolbarPending:()=>{++pendingVersion.value;},
  setToolbarBusyLabel:(action:string,label?:string)=>{const next={...busyLabels.value};if(label)next[action]=label;else delete next[action];busyLabels.value=next;},
  closeMoreMenus:()=>owner().closeMoreMenus(),
  setCapabilities:(value:AccountToolbarCapabilities)=>{capabilities.value=value;},
  refreshQuickActions:()=>toolbar.value?.refreshQuickActions(),
  showRegistrationResult:(result:Partial<RegistrationReceipt>,context:AccountActionContext|null,open:(items:readonly RegistrationRetryEntry[])=>void|Promise<void>)=>registrationReceipt.value?.showResult(result,context,open),
  openInspectionStart:(context:AccountActionContext,trigger:HTMLElement|null=null)=>inspection.value?.openStart(context,trigger),
  openInspectionHistory:(trigger:HTMLElement|null=null)=>inspection.value?.openHistory(trigger),
  openInspectionFailures:(id:number,trigger:HTMLElement|null=null)=>inspection.value?.openFailures(id,trigger),
  closeInspection:(kind?:InspectionDialog)=>inspection.value?.close(kind),
  refreshInspectionHistory:()=>inspection.value?.refreshHistory(),
  refreshInspectionFailures:()=>inspection.value?.refreshFailures(),
  changeInspectionPage:(delta:number)=>inspection.value?.changeHistoryPage(delta),
  changeInspectionFailuresPage:(delta:number)=>inspection.value?.changeFailuresPage(delta),
  stopInspection:(id:number)=>inspection.value?.stop(id),
  openEmailChange:(id:string,context:AccountActionContext,trigger:HTMLElement|null=null)=>emailChange.value?.openSingle(id,context,trigger),
  openBulkEmailChange:(context:AccountActionContext,trigger:HTMLElement|null=null)=>emailChange.value?.openBulk(context,trigger),
  closeEmailChange:(options:{restoreFocus?:boolean}={})=>emailChange.value?.close(options),
  openC2a:(context:AccountActionContext,trigger:HTMLElement|null=null)=>c2a.value?.open(context,trigger),
  closeC2a:(returnValue='cancel',options:{force?:boolean}={})=>c2a.value?.close(returnValue,options),
  submitC2a:()=>c2a.value?.submit(),showC2aResult:(result:unknown)=>c2a.value?.showResult(result),
  openC2aTasks:(items:readonly Readonly<Record<string,unknown>>[])=>c2a.value?.openTasks(items),
});
</script>
<template>
  <AccountsList ref="list" :adapter="adapter" :api="api" :presentation="presentation" :callbacks="callbacks">
    <template #actions>
      <AccountsToolbar ref="toolbar" :state="toolbarState" :capabilities="capabilities" :get-context="()=>owner().getActionContext()" :invoke="invoke" :notify="callbacks.notify"/>
    </template>
    <template #feedback>
      <AccountOperationReceipts v-if="actions.receipts" :receipts="actions.receipts"/>
    </template>
  </AccountsList>
  <AccountDetail ref="drawer" :api="detailApi" :presentation="detailPresentation" :callbacks="detailCallbacks"/>
  <Inspection ref="inspection" :deps="inspectionDependencies"/>
  <EmailChange ref="emailChange" :deps="emailChangeDependencies"/>
  <C2aReimport ref="c2a" :deps="c2aDependencies"/>
  <RegistrationRetryReceipt ref="registrationReceipt" :notify="callbacks.notify"/>
</template>
