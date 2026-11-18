<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue';
import type {AccountsReadApi} from '../../api/accounts';
import type {AccountQueryAdapter} from './queryAdapter';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListPagination from '../../components/ListPagination.vue';
import AccountFilters from './AccountFilters.vue';
import AccountsTable from './AccountsTable.vue';
import {accountFilters,filterChips,type AccountFilterField} from './filterDefinitions';
import type {AccountPresentation,AccountsCallbacks} from './presentation';
import {useAccounts} from './useAccounts';
import './accounts.css';
const props=defineProps<{adapter:AccountQueryAdapter;api:AccountsReadApi;presentation:AccountPresentation;callbacks:AccountsCallbacks}>();
const list=useAccounts(props.adapter,props.api);
const {query,items,facets,searchTerms,total,page,size,pages,selected,loading,error,visible,invalidSearch,draftSearch,stale,pageSelected,pageIndeterminate}=list;
const table=ref<InstanceType<typeof AccountsTable>>(),search=ref<HTMLInputElement>();
const openFilter=ref<string|null>(null),documentVisible=ref(typeof document==='undefined'||!document.hidden),actionError=ref('');
// Portal menus recreate their buttons; keep pending actions with the list owner.
const pendingActions=new Set<string>();
const emailStatus=accountFilters.find(column=>column.key==='email_status')!;
const chips=computed(()=>[
  ...filterChips(query.value,props.presentation.facetLabel),
  ...searchTerms.value.map((term,index)=>({key:`search:${index}`,label:`${term.label}：${term.display_value}`,title:`高级搜索 · 同时满足：${term.label}：${term.display_value}`,removeLabel:`移除${term.label}：${term.display_value}`})),
]);
function changeFilter(key:AccountFilterField,value:string|readonly string[]){
  if(key==='plan')list.updateQuery({plan:[...(value as readonly string[])]});
  else if(key==='date_from'||key==='date_to')list.updateQuery({[key]:String(value)});
  else if(key==='id'||key==='email')list.updateFilters({[key]:String(value)},250);
  else list.updateFilters({[key]:[...(value as readonly string[])]});
}
function clearFilter(key:string){
  if(key.startsWith('search:')){const term=searchTerms.value[Number(key.slice(7))];if(term)list.removeSearchTerm({...term});search.value?.focus();return;}
  if(key==='date'){list.updateQuery({date_from:'',date_to:''});return;}
  const column=accountFilters.find(column=>column.key===key);
  if(column)changeFilter(column.key as AccountFilterField,column.kind==='text'?'':[]);
}
function report(cause:unknown){actionError.value=cause instanceof Error?cause.message:'账号操作暂不可用';props.callbacks.notify?.(actionError.value);}
async function invoke(action:string,id:string,trigger:HTMLElement|null){
  if(stale.value||!visible.value||!documentVisible.value)return;
  const pendingKey=JSON.stringify([id,action]);
  if(pendingActions.has(pendingKey))return;
  pendingActions.add(pendingKey);
  actionError.value='';
  try{
    const context=list.getActionContext({ids:[id],requireEmails:action.startsWith('account-email-invalid:')});
    await props.callbacks.invoke(action,context,trigger);
  }catch(cause){report(cause);}finally{pendingActions.delete(pendingKey);}
}
function detail(id:string,trigger:HTMLElement|null){
  if(stale.value||!visible.value||!documentVisible.value)return;
  actionError.value='';
  const row=list.getRowSnapshot(id);
  if(!row){report(new Error('账号详情暂不可用，请先刷新列表'));return;}
  let lease:ReturnType<typeof list.openPlanDetailsConsumer>|undefined;
  try{lease=list.openPlanDetailsConsumer(id);props.callbacks.openDetail(id,row,lease,trigger);}
  catch(cause){lease?.release();report(cause);}
}
function setVisible(value:boolean){if(!value){openFilter.value=null;props.callbacks.closeConsumers?.(false);}list.setVisible(value);}
function setArchived(value:boolean){openFilter.value=null;list.setArchived(value);}
function clearSearch(){list.clearSearch();search.value?.focus();}
function resetColumns(){table.value?.resetColumns();}
watch([list.selected,list.selectedEmails,total,page,size,query,loading,visible],()=>props.callbacks.onStateChange?.(Object.freeze({
  selectedIds:Object.freeze([...selected.value]),selectedEmails:Object.freeze({...list.selectedEmails.value}),
  total:total.value,page:page.value,size:size.value,archived:query.value.archived,loading:loading.value,visible:visible.value,
})),{immediate:true,flush:'post'});
const visibilityChanged=()=>{documentVisible.value=!document.hidden;if(document.hidden){openFilter.value=null;props.callbacks.closeConsumers?.();}};
if(typeof document!=='undefined')document.addEventListener('visibilitychange',visibilityChanged);
onBeforeUnmount(()=>{if(typeof document!=='undefined')document.removeEventListener('visibilitychange',visibilityChanged);props.callbacks.closeConsumers?.();});
defineExpose({refresh:list.refresh,pollStatuses:list.pollStatuses,setVisible,setArchived,openDetail:detail,setPage:list.setPage,setSize:list.setSize,
  closeMoreMenus:()=>table.value?.closeMenu(),
  updateQuery:list.updateQuery,updateFilters:list.updateFilters,resetFilters:list.resetFilters,resetColumns,
  getAccountSelectionSnapshot:list.getAccountSelectionSnapshot,getActionContext:list.getActionContext,getRowSnapshot:list.getRowSnapshot,
  openPlanDetailsConsumer:list.openPlanDetailsConsumer,removeAcknowledgedSelection:list.removeAcknowledgedSelection,clearSelection:list.clearSelection});
</script>
<template>
  <section v-show="visible" class="ac-root" aria-label="账号列表">
    <div class="ac-toolbar">
      <div class="ac-toolbar-main"><span id="accountsPageSummary" class="ac-count" role="status">{{ total.toLocaleString() }} 个账号 · 当前页 {{ items.length }} 条</span><ListFilterSummary :items="chips" @remove="clearFilter"/></div>
      <div class="ac-toolbar-utilities">
        <div class="ac-mobile-filters"><AccountFilters :query="query" :facets="facets" :label="presentation.facetLabel" :open="documentVisible&&openFilter==='all'" @update:open="openFilter=$event?'all':null" @change="changeFilter" @clear="clearFilter"/></div>
        <AccountFilters :column="emailStatus" :query="query" :facets="facets" :label="presentation.facetLabel" :open="documentVisible&&openFilter==='email_status'" @update:open="openFilter=$event?'email_status':null" @change="changeFilter" @clear="clearFilter"/>
        <form class="ac-search" role="search" @submit.prevent="list.submitSearch"><label for="accountAdvancedSearchV2">高级搜索</label><input id="accountAdvancedSearchV2" ref="search" type="search" :value="draftSearch" placeholder="空格或 / 组合，如：协议 jp" autocomplete="off" aria-describedby="accountAdvancedSearchHintV2 accountAdvancedSearchErrorV2" :aria-invalid="invalidSearch||undefined" @keydown.esc.prevent="clearSearch" @input="list.setSearchDraft(($event.target as HTMLInputElement).value)" @compositionstart="list.compositionStart" @compositionend="list.compositionEnd(($event.target as HTMLInputElement).value)"><button v-if="draftSearch" type="button" aria-label="清空高级搜索" title="清空高级搜索" @click="clearSearch">×</button></form>
        <span id="accountAdvancedSearchHintV2" class="ac-sr-only">空格或 / 表示同时满足；支持方式、地区、邮箱、姓名、来源、备注、ID。完整文字加双引号。</span>
        <button id="btnResetAccountFiltersV2" type="button" class="ac-link" title="清除全部列筛选" @click="list.resetFilters">清筛</button><button id="btnResetAccountsColumnsV2" type="button" class="ac-link" title="恢复账号列表默认列宽" @click="resetColumns">恢复列宽</button><button id="btnRefreshAccountsV2" type="button" class="ac-button" :disabled="loading" @click="list.refresh">{{ loading?'刷新中…':'刷新' }}</button>
      </div>
    </div>
    <p v-if="invalidSearch" id="accountAdvancedSearchErrorV2" class="ac-feedback" role="alert">{{ error }}</p>
    <div v-else-if="actionError||(error&&items.length)" class="ac-feedback" role="alert"><span>{{ actionError||error }}</span><button v-if="error" type="button" class="ac-link" @click="list.refresh">重试</button></div>
    <AccountsTable ref="table" :items="items" :selected="selected" :query="query" :facets="facets" :presentation="presentation" :loading="loading" :error="error" :invalid-search="invalidSearch" :stale="stale" :visible="visible&&documentVisible" :page-selected="pageSelected" :page-indeterminate="pageIndeterminate" :open-filter="openFilter" @update:open-filter="openFilter=$event" @filter="changeFilter" @clear-filter="clearFilter" @select="list.toggle" @select-page="list.togglePage" @action="invoke" @detail="detail" @retry="list.refresh" @rendered="callbacks.afterRender?.($event)"/>
    <ListPagination :page="page" :size="size" :pages="pages" :total="total" :busy="loading" :page-sizes="[10,20,30,50,100]" label="账号列表分页" @update:page="list.setPage" @update:size="list.setSize"/>
  </section>
</template>
