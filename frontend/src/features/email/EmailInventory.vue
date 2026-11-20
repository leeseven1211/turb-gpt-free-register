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
import EmailResizeGrip from './EmailResizeGrip.vue';
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
 <section class="em-list em-inventory" aria-label="邮箱池" :aria-busy="state.loading">
  <div class="em-toolbar"><div class="em-actions">
   <span>{{ state.selected.size?`已选 ${state.selected.size} 个邮箱`:'选择邮箱后批量操作' }}</span>
   <template v-if="state.selected.size"><button class="em-button" :disabled="state.busy" @click="owner.bulkStatus('available')">标记未使用</button><button class="em-button" :disabled="state.busy" @click="owner.bulkStatus('disabled')">停用选中</button><button class="em-button" :disabled="state.busy" @click="owner.bulkStatus('failed')">标失败</button><button class="em-button em-danger" :disabled="state.busy" @click="owner.bulkDelete()">删除选中</button></template>
   <button class="em-button" :disabled="state.busy||!state.items.length" @click="owner.copyPage()">复制当前页</button><button class="em-button em-primary" @click="emit('localImport')">导入邮箱</button><button class="em-button" data-butler-opener @click="emit('butlerImport')">{{ butlerLabel }}</button>
  </div>
  <ListFilterSummary :items="chips" @remove="removeFilter"/>
  <div class="em-actions em-inventory-utilities"><button class="em-button" @click="widths.resetColumns">恢复列宽</button><button class="em-button" :disabled="state.loading" @click="owner.refresh()">刷新</button></div></div>
  <div v-if="state.error" class="em-error" role="alert">{{ state.error }} <button class="em-button" @click="owner.refresh()">重试</button></div>
  <div v-if="state.summaryError" class="em-error" role="alert">{{ state.summaryError }} <button class="em-button" @click="owner.refreshDerivationSummary()">重试</button></div>
  <EmailReceipt :receipt="state.receipt"/>
  <div ref="tableViewport" class="em-table-wrap" role="region" tabindex="0" aria-label="邮箱列表，可滚动"><table class="em-table" :style="{width:`${widths.total.value}px`}">
   <colgroup><col v-for="(value,index) in widths.widths.value" :key="index" :style="{width:`${value}px`}"></colgroup>
   <thead><tr>
    <th><input type="checkbox" aria-label="全选当前页邮箱资源" :checked="!!state.items.length&&checked===state.items.length" :indeterminate="checked>0&&checked<state.items.length" :disabled="!state.items.length" @change="owner.togglePage(($event.target as HTMLInputElement).checked)"><EmailResizeGrip :index="0" :columns="widths" label="邮箱"/></th>
    <th><EmailColumnFilter label="邮箱" :value="state.filters.q" :active="active" @change="owner.updateFilters({q:$event})"/><EmailResizeGrip :index="1" :columns="widths" label="邮箱"/></th>
    <th><EmailColumnFilter label="类型" :value="state.filters.source" empty-value="all" :options="sources" :active="active" @change="owner.updateFilters({source:$event})"/><EmailResizeGrip :index="2" :columns="widths" label="邮箱"/></th>
    <th><EmailColumnFilter label="状态" :value="state.filters.status" :options="statuses" :active="active" @change="owner.updateFilters({status:$event})"/><EmailResizeGrip :index="3" :columns="widths" label="邮箱"/></th>
    <th>使用情况<EmailResizeGrip :index="4" :columns="widths" label="邮箱"/></th><th>凭证配置<EmailResizeGrip :index="5" :columns="widths" label="邮箱"/></th><th><EmailColumnFilter label="最近活动" type="date" :value="state.filters.used_date" :active="active" @change="owner.updateFilters({used_date:$event})"/><EmailResizeGrip :index="6" :columns="widths" label="邮箱"/></th><th>备注 / 原因<EmailResizeGrip :index="7" :columns="widths" label="邮箱"/></th><th>操作 <button class="em-text-button" @click="owner.resetFilters()">清筛</button><EmailResizeGrip :index="8" :columns="widths" label="邮箱"/></th>
   </tr></thead>
   <tbody><tr v-for="row in state.items" :key="keyOf(row)" :class="{'is-selected':state.selected.has(keyOf(row))}">
    <td><input type="checkbox" :aria-label="`选择邮箱 ${row.email}`" :checked="state.selected.has(keyOf(row))" @change="owner.toggle(row,($event.target as HTMLInputElement).checked)"></td>
    <td class="em-align-start"><button v-if="parent(row)" class="em-cell-button" :aria-label="`查看 ${row.email} 的历史子地址`" :title="[row.email,row.remote_label,`历史子地址 ${parent(row)?.child_count} 个`].filter(Boolean).join(' · ')" @click="emit('parent',row)"><ListCell :text="row.email" :secondary="`查看历史 · ${parent(row)?.child_count} 个`"/></button><ListCell v-else :text="row.email" :secondary="row.remote_label||undefined"/></td>
    <td><ListCell :text="sourceLabels[row.source]||row.source"/></td>
    <td><ListCell :text="statusLabels[row.status||'']||row.status||'状态记录缺失'"/></td>
    <td><ListCell :text="usageLabels[row.usage_state||row.status||'']||row.usage_state||row.status||'状态记录缺失'" :secondary="row.usage_state==='bound'&&row.registered_account_id?`账号 #${row.registered_account_id}`:undefined"/></td>
    <td><ListResult :label="credentials(row).text" :title="credentials(row).detail"><template #details>{{ credentials(row).detail }}</template></ListResult></td>
    <td><ListResult v-bind="{label:dateTimeLines(activity(row)).text,secondary:dateTimeLines(activity(row)).secondary}" :title="activityDetail(row)"><template #details>{{ activityDetail(row) }}</template></ListResult></td>
    <td class="em-align-start"><ListResult v-if="note(row)" data-email-note :label="reasonSummary(row)" :title="note(row)" :tone="row.service_sync_error?'danger':'neutral'"><template #details>{{ note(row) }}</template></ListResult><ListCell v-else text="—"/></td>
    <td><div class="em-row-actions"><button class="em-button" :disabled="state.busy" @click="owner.copyRow(row)">复制素材</button><button class="em-button em-danger" :disabled="state.busy" @click="owner.rowAction(row,'delete')">删除</button><details v-if="!['replaced','pending_sync'].includes(row.status||'')" class="em-more"><summary :aria-label="`更多操作 ${row.email}`">更多</summary><div><button v-for="(label,status) in {available:'恢复可用',disabled:'停用',failed:'标失败'}" v-show="status!==row.status" :key="status" class="em-button" :disabled="state.busy" @click="owner.rowAction(row,status)">{{ label }}</button></div></details></div></td>
   </tr><tr v-if="!state.items.length"><td colspan="9" class="em-empty" role="status">{{ state.loading?'正在加载邮箱资源…':state.error?'邮箱资源加载失败':'暂无邮箱资源，调整筛选条件或导入新的邮箱资源。' }}</td></tr></tbody>
  </table></div>
  <ListPagination compact :page="state.page" :size="state.size" :total="state.total" :busy="state.loading" :page-sizes="[10,20,30,50,100]" label="邮箱资源分页" @update:page="owner.setPage" @update:size="owner.setSize"/>
 </section>
</template>
