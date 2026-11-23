<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import ListCell from '../../components/ListCell.vue';
import ListResult from '../../components/ListResult.vue';
import ListPagination from '../../components/ListPagination.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import {dateTimeLines,formatDateTime} from '../../shared/time';
import {useColumnWidths} from '../../shared/useColumnWidths';
import EmailColumnFilter from './EmailColumnFilter.vue';
import EmailReceipt from './EmailReceipt.vue';
import ColumnResizer from '../../components/ColumnResizer.vue';
import TableState from '../../components/TableState.vue';
import ListToolbar from '../../components/ListToolbar.vue';
import {credentials,keyOf,reasonSummary,sourceLabels,statusLabels,usageLabels} from './presentation';
import type {useEmailInventory} from './useEmailInventory';
import type {EmailRow} from './contracts';
const props=defineProps<{owner:ReturnType<typeof useEmailInventory>;active:boolean;butlerLabel:string}>();
const emit=defineEmits<{localImport:[];butlerImport:[];parent:[EmailRow]}>();
const state=props.owner.state;
const tableViewport=ref<HTMLElement>();
let resetScrollOnNextResult=false;
watch([()=>state.page,()=>state.size,()=>Object.values(state.filters)],()=>{
  resetScrollOnNextResult=true;
});
watch(()=>state.items,()=>{
  if(!resetScrollOnNextResult||!tableViewport.value)return;
  tableViewport.value.scrollTop=0;
  resetScrollOnNextResult=false;
},{flush:'post'});
const widths=useColumnWidths({defaults:[40,228,112,104,120,160,140,164,228],storageKey:'gpt_console_table_widths_outlook',totalStorageKey:'gpt_console_table_total_outlook',min:28,max:20000});
const checked=computed(()=>state.items.filter(row=>state.selected.has(keyOf(row))).length);
const chips=computed(()=>Object.entries(state.filters).filter(([key,value])=>value&&(key!=='source'||value!=='all')).map(([key,value])=>({key,label:`${({q:'邮箱',source:'类型',status:'状态',used_date:'最近使用日期'} as Record<string,string>)[key]}：${key==='source'?sourceLabels[value]||value:key==='status'?statusLabels[value]||value:value}`,removeLabel:`移除${key}筛选`})));
const sources=computed(()=>Object.entries(sourceLabels).filter(([key])=>key!=='all').map(([value,label])=>({value,label,count:state.facets.source?.find(row=>row.value===value)?.count})));
const statuses=computed(()=>[...new Set([...Object.keys(statusLabels),...(state.facets.status||[]).map(row=>row.value),state.filters.status])].filter(Boolean).map(value=>({value,label:statusLabels[value]||value,count:state.facets.status?.find(row=>row.value===value)?.count})));
const parent=(row:EmailRow)=>state.parents.find(item=>item.source===row.source&&String(item.parent_id)===String(row.id)&&Number(item.child_count)>0);
const note=(row:EmailRow)=>row.service_sync_error||row.note||row.disabled_reason||'';
function removeFilter(key:string){props.owner.updateFilters({[key]:key==='source'?'all':''});}
function activity(row:EmailRow){return row.last_activity_at||row.used_at||row.updated_at||row.created_at;}
function activityDetail(row:EmailRow){return`${row.used_at?'最近使用':row.last_activity_at?'最近更新':'导入时间'}：${formatDateTime(activity(row))}${row.synced_at?`\n同步：${formatDateTime(row.synced_at)}`:''}`;}
</script>
<template>
 <section class="ui-list em-list em-inventory" aria-label="邮箱池" :aria-busy="state.loading">
  <ListToolbar class="em-toolbar" :filtered="chips.length>0">
   <span v-if="state.selected.size" class="ui-list-count">已选 {{ state.selected.size }} 个邮箱</span>
   <div v-if="state.selected.size" class="em-bulk-actions" role="group" aria-label="选中邮箱批量操作"><button class="ui-button" :disabled="state.busy" @click="owner.bulkStatus('available')">标记未使用</button><button class="ui-button" :disabled="state.busy" @click="owner.bulkStatus('disabled')">停用选中</button><button class="ui-button" :disabled="state.busy" @click="owner.bulkStatus('failed')">标失败</button><button class="ui-button ui-button--danger" :disabled="state.busy" @click="owner.bulkDelete()">删除选中</button></div>
   <ListFilterSummary :items="chips" @remove="removeFilter"/>
   <template #actions>
    <button v-if="chips.length" class="ui-link" @click="owner.resetFilters()">清筛</button>
    <button class="ui-button" :disabled="state.busy||!state.items.length" @click="owner.copyPage()">复制当前页</button>
    <button class="ui-button" data-butler-opener @click="emit('butlerImport')">{{ butlerLabel }}</button>
    <button class="ui-button ui-button--primary" @click="emit('localImport')">导入邮箱</button>
    <button class="ui-link" @click="widths.resetColumns">恢复列宽</button>
    <button class="ui-button" :disabled="state.loading" @click="owner.refresh()">刷新</button>
   </template>
  </ListToolbar>
  <div v-if="state.error" class="ui-list-feedback is-error" role="alert">{{ state.error }} <button class="ui-link" @click="owner.refresh()">重试</button></div>
  <div v-if="state.summaryError" class="ui-list-feedback is-error" role="alert">{{ state.summaryError }} <button class="ui-link" @click="owner.refreshDerivationSummary()">重试</button></div>
  <EmailReceipt :receipt="state.receipt"/>
  <div ref="tableViewport" class="ui-table-scroll em-table-wrap" role="region" tabindex="0" aria-label="邮箱列表，可滚动"><table class="ui-table ui-table--sticky-end em-table" :style="{'--ui-table-width':`${widths.total.value}px`}">
   <colgroup><col v-for="(value,index) in widths.widths.value" :key="index" :style="{width:`${value}px`}"></colgroup>
   <thead><tr>
    <th class="ui-col-check"><input type="checkbox" aria-label="全选当前页邮箱资源" :checked="!!state.items.length&&checked===state.items.length" :indeterminate="checked>0&&checked<state.items.length" :disabled="!state.items.length" @change="owner.togglePage(($event.target as HTMLInputElement).checked)"><ColumnResizer label="选择" @start="widths.resize(0,$event)" @nudge="widths.resizeWithKeyboard(0,$event)"/></th>
    <th><EmailColumnFilter label="邮箱" :value="state.filters.q" :active="active" @change="owner.updateFilters({q:$event})"/><ColumnResizer label="邮箱" @start="widths.resize(1,$event)" @nudge="widths.resizeWithKeyboard(1,$event)"/></th>
    <th><EmailColumnFilter label="类型" :value="state.filters.source" empty-value="all" :options="sources" :active="active" @change="owner.updateFilters({source:$event})"/><ColumnResizer label="类型" @start="widths.resize(2,$event)" @nudge="widths.resizeWithKeyboard(2,$event)"/></th>
    <th><EmailColumnFilter label="状态" :value="state.filters.status" :options="statuses" :active="active" @change="owner.updateFilters({status:$event})"/><ColumnResizer label="状态" @start="widths.resize(3,$event)" @nudge="widths.resizeWithKeyboard(3,$event)"/></th>
    <th>使用情况<ColumnResizer label="使用情况" @start="widths.resize(4,$event)" @nudge="widths.resizeWithKeyboard(4,$event)"/></th><th>凭证配置<ColumnResizer label="凭证配置" @start="widths.resize(5,$event)" @nudge="widths.resizeWithKeyboard(5,$event)"/></th><th><EmailColumnFilter label="最近活动" type="date" :value="state.filters.used_date" :active="active" @change="owner.updateFilters({used_date:$event})"/><ColumnResizer label="最近活动" @start="widths.resize(6,$event)" @nudge="widths.resizeWithKeyboard(6,$event)"/></th><th>备注 / 原因<ColumnResizer label="备注 / 原因" @start="widths.resize(7,$event)" @nudge="widths.resizeWithKeyboard(7,$event)"/></th><th>操作<ColumnResizer label="操作" @start="widths.resize(8,$event)" @nudge="widths.resizeWithKeyboard(8,$event)"/></th>
   </tr></thead>
   <tbody><tr v-for="row in state.items" :key="keyOf(row)" :class="{'is-selected':state.selected.has(keyOf(row))}">
    <td class="ui-col-check"><input type="checkbox" :aria-label="`选择邮箱 ${row.email}`" :checked="state.selected.has(keyOf(row))" @change="owner.toggle(row,($event.target as HTMLInputElement).checked)"></td>
    <td><button v-if="parent(row)" class="em-cell-button" :aria-label="`查看 ${row.email} 的历史子地址`" :title="[row.email,row.remote_label,`历史子地址 ${parent(row)?.child_count} 个`].filter(Boolean).join(' · ')" @click="emit('parent',row)"><ListCell :text="row.email" :secondary="`查看历史 · ${parent(row)?.child_count} 个`"/></button><ListCell v-else :text="row.email" :secondary="row.remote_label||undefined"/></td>
    <td><ListCell :text="sourceLabels[row.source]||row.source"/></td>
    <td><ListCell :text="statusLabels[row.status||'']||row.status||'状态记录缺失'"/></td>
    <td><ListCell :text="usageLabels[row.usage_state||row.status||'']||row.usage_state||row.status||'状态记录缺失'" :secondary="row.usage_state==='bound'&&row.registered_account_id?`账号 #${row.registered_account_id}`:undefined"/></td>
    <td><ListResult :label="credentials(row).text" :title="credentials(row).detail"><template #details>{{ credentials(row).detail }}</template></ListResult></td>
    <td><ListResult v-bind="{label:dateTimeLines(activity(row)).text,secondary:dateTimeLines(activity(row)).secondary}" :title="activityDetail(row)"><template #details>{{ activityDetail(row) }}</template></ListResult></td>
    <td><ListResult v-if="note(row)" data-email-note :label="reasonSummary(row)" :title="note(row)" :tone="row.service_sync_error?'danger':'neutral'"><template #details>{{ note(row) }}</template></ListResult><ListCell v-else text="—"/></td>
    <td><div class="ui-row-actions em-row-actions"><button class="ui-link" :disabled="state.busy" @click="owner.copyRow(row)">复制素材</button><button class="ui-link ui-link--danger" :disabled="state.busy" @click="owner.rowAction(row,'delete')">删除</button><details v-if="!['replaced','pending_sync'].includes(row.status||'')" class="em-more"><summary :aria-label="`更多操作 ${row.email}`">更多</summary><div><button v-for="(label,status) in {available:'恢复可用',disabled:'停用',failed:'标失败'}" v-show="status!==row.status" :key="status" class="ui-link" :disabled="state.busy" @click="owner.rowAction(row,status)">{{ label }}</button></div></details></div></td>
   </tr><TableState v-if="!state.items.length" :colspan="9" :loading="state.loading" :error="state.error?' ':''" loading-title="正在加载邮箱资源…" error-title="邮箱资源加载失败" title="暂无邮箱资源" text="调整筛选条件或导入新的邮箱资源。"/></tbody>
  </table></div>
  <ListPagination compact :page="state.page" :size="state.size" :total="state.total" :busy="state.loading" :page-sizes="[10,20,30,50,100]" label="邮箱资源分页" @update:page="owner.setPage" @update:size="owner.setSize"/>
 </section>
</template>
