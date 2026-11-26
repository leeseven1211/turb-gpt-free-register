<script setup lang="ts">
import {computed,onBeforeUnmount,ref} from 'vue';
import type {CodexCallbacks,CodexRow} from '../../api/codex';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListPagination from '../../components/ListPagination.vue';
import CodexTable from './CodexTable.vue';
import CodexFilters from './CodexFilters.vue';
import {createCodexActions,type CodexAction} from './actions';
import {clearFilter,filterChips} from './filterDefinitions';
import {useCodexList} from './useCodexList';
import './codex.css';
const props=defineProps<{callbacks:CodexCallbacks}>();
const list=useCodexList();
const {items,facets,total,page,size,pages,archived,selected,loading,error,visible,filters}=list;
const actions=createCodexActions({selected,items,archived,refresh:list.refresh,callbacks:props.callbacks});
const {busy,error:actionError,uploadProgress}=actions;
const table=ref<InstanceType<typeof CodexTable>>();
const openFilter=ref<string|null>(null),documentVisible=ref(!document.hidden);
const chips=computed(()=>filterChips(filters,facets.value));
const bulkActions: {kind:CodexAction;id:string;label:string;title:string;danger?:boolean}[]=[
  {kind:'refreshToken',id:'btnCodexRefreshTokenBulkV2',label:'刷新 OAuth Token',title:'使用 refresh_token 刷新选中凭证，不需要邮箱验证码或短信'},
  {kind:'reauthorize',id:'btnCodexReauthorizeBulkV2',label:'重跑 Codex 授权',title:'重新执行 Codex OAuth 授权；按实际验证要求使用邮箱 OTP 和手机接码'},
  {kind:'downloadBulk',id:'btnCodexDownloadBulkV2',label:'下载凭证',title:'从数据库读取选中凭证，打包成一个 JSON 文件下载'},
  {kind:'downloadBulkCpa',id:'btnCodexDownloadBulkCpaV2',label:'从 CPA 下载',title:'从 CPA 下载真实 Codex JSON，打包为 ZIP'},
  {kind:'uploadSub2',id:'btnCodexUploadSub2V2',label:'上传 sub2api',title:'把选中的本地 Codex OAuth 凭证上传到 sub2api'},
  {kind:'archiveBulk',id:'btnCodexArchiveBulkV2',label:'归档选中',title:'归档或恢复选中的 Codex 凭证'},
  {kind:'deleteBulk',id:'btnCodexDeleteBulkV2',label:'删除选中',title:'删除数据库中选中的 Codex 凭证及导出状态',danger:true},
];
function setVisible(value:boolean){if(!value)openFilter.value=null;list.setVisible(value);}
function setArchived(value:boolean){openFilter.value=null;list.setArchived(value);}
async function refresh(){await list.refresh();}
function rowAction(action:CodexAction,row:CodexRow){void actions.run(action,[row.filename],row);}
function removeFilter(key:string){list.updateFilters(clearFilter(filters,key));}
const visibilityChanged=()=>{documentVisible.value=!document.hidden;if(document.hidden)openFilter.value=null;};
document.addEventListener('visibilitychange',visibilityChanged);
onBeforeUnmount(()=>document.removeEventListener('visibilitychange',visibilityChanged));
defineExpose({refresh,setVisible,setArchived});
</script>
<template>
  <section v-show="visible" class="cx-root" aria-label="Codex 授权">
    <div class="ui-list cx-workspace">
      <div id="codexToolbarV2" class="ui-list-toolbar cx-toolbar">
        <div class="ui-list-toolbar__main cx-toolbar-main"><span class="ui-list-count cx-count" role="status">{{ total.toLocaleString() }} 个凭证<span v-if="archived"> · 已归档</span></span><span v-if="selected.size" id="codexSelectedHintV2" class="cx-selected" role="status">已选 {{ selected.size }} 项</span><div v-if="selected.size" class="cx-bulk-actions" role="group" aria-label="选中凭证批量操作"><button v-for="entry in bulkActions" :id="entry.id" :key="entry.kind" type="button" class="ui-button" :class="{'ui-button--danger':entry.danger}" :title="entry.title" :disabled="busy" @click="actions.run(entry.kind)">{{ entry.kind==='archiveBulk' && archived?'恢复选中':entry.label }}</button></div><ListFilterSummary :items="chips" @remove="removeFilter"/></div>
        <div class="ui-list-toolbar__actions cx-toolbar-utilities"><CodexFilters :model-value="filters" :facets="facets" :open="documentVisible && openFilter === 'all'" @update:model-value="list.updateFilters" @update:open="openFilter=$event?'all':null"/><button v-if="chips.length" id="btnResetCodexFiltersV2" type="button" class="ui-link" @click="list.resetFilters">清除筛选</button><button v-if="uploadProgress" id="btnCodexUploadProgressV2" type="button" class="ui-button" @click="actions.showProgress">查看上传进度</button><button id="btnResetCodexColumnsV2" type="button" class="ui-link cx-reset-columns" title="恢复 Codex 列表默认列宽" @click="table?.resetColumns()">恢复列宽</button><button id="btnRefreshCodexV2" type="button" class="ui-button ui-refresh-button" :disabled="loading" @click="refresh">{{ loading?'刷新中…':'刷新' }}</button></div>
      </div>
      <div v-if="actionError || (error && items.length)" class="ui-list-feedback is-error cx-feedback" role="alert"><span>{{ actionError || error }}</span><button v-if="error" type="button" class="ui-link" @click="refresh">重试</button></div>
      <CodexTable ref="table" :items="items" :selected="selected" :filters="filters" :facets="facets" :loading="loading" :error="error" :busy="busy" :visible="visible && documentVisible" :open-filter="openFilter" @update:open-filter="openFilter=$event" @update:filters="list.updateFilters" @select="list.toggle" @select-page="list.togglePage" @action="rowAction" @retry="refresh"/>
      <ListPagination :page="page" :size="size" :pages="pages" :total="total" :busy="loading" :page-sizes="[10,20,30,50,100]" label="Codex 凭证分页" @update:page="list.setPage" @update:size="list.setSize"/>
    </div>
  </section>
</template>
