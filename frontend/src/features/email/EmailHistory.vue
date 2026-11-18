<script setup lang="ts">
import {computed} from 'vue';
import ListCell from '../../components/ListCell.vue';
import ListPagination from '../../components/ListPagination.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import {dateTimeLines} from '../../shared/time';
import {useColumnWidths} from '../../shared/useColumnWidths';
import EmailColumnFilter from './EmailColumnFilter.vue';
import EmailReceipt from './EmailReceipt.vue';
import EmailResizeGrip from './EmailResizeGrip.vue';
import {historyLabels,ownership,sourceLabels} from './presentation';
import type {useEmailHistory} from './useEmailHistory';
const props=defineProps<{owner:ReturnType<typeof useEmailHistory>;active:boolean}>(),state=props.owner.state;
const widths=useColumnWidths({defaults:[40,248,224,112,120,172,140,88],storageKey:'gpt_console_table_widths_derivations',totalStorageKey:'gpt_console_table_total_derivations',min:28,max:20000});
const checked=computed(()=>state.items.filter(row=>state.selected.has(String(row.id))).length);
const sources=[{value:'icloud_hide',label:'iCloud 隐藏邮箱'},{value:'outlook',label:'Outlook'}];
const statuses=Object.entries(historyLabels).map(([value,label])=>({value,label}));
const chips=computed(()=>Object.entries(state.filters).filter(([key,value])=>value&&(key!=='source'||value!=='all')).map(([key,value])=>({key,label:`${({source:'来源',parent_id:'母邮箱',q:'子邮箱',parent_q:'母邮箱搜索',state:'状态',related_q:'关联账号/任务',created_from:'生成开始',created_to:'生成结束'} as Record<string,string>)[key]}：${key==='source'?sourceLabels[value]||value:key==='state'?historyLabels[value]||value:key==='parent_id'?state.parentEmail||`#${value}`:value}`,removeLabel:`移除${key}筛选`})));
function removeFilter(key:string){if(key==='parent_id')props.owner.clearParent();else props.owner.updateFilters({[key]:key==='source'?'all':''});}
</script>
<template>
 <section class="em-list" aria-label="历史子邮箱" :aria-busy="state.loading">
  <p class="em-help">子邮箱由你手动准备并导入本地库存；此处可查看、筛选和复制已有记录，Turb 不会自动生成。</p>
  <div class="em-toolbar"><div class="em-actions"><span>{{ state.selected.size?`已选 ${state.selected.size} 条历史记录`:'可筛选并复制历史子邮箱' }}</span><button class="em-button" :disabled="!state.items.length&&!state.selected.size" @click="owner.copy()">{{ state.selected.size?'复制选中':'复制当前页' }}</button></div><button class="em-button" @click="widths.resetColumns">恢复列宽</button></div>
  <div class="em-count-row" data-email-count-row><strong>{{ state.total }} 条历史记录</strong><span>当前页 {{ state.items.length }} 条</span><ListFilterSummary :items="chips" @remove="removeFilter"/></div>
  <div v-if="state.error" class="em-error" role="alert">{{ state.error }} <button class="em-button" @click="owner.refresh()">重试</button></div><EmailReceipt :receipt="state.receipt"/>
  <div class="em-table-wrap"><table class="em-table" :style="{width:`${widths.total.value}px`}"><colgroup><col v-for="(value,index) in widths.widths.value" :key="index" :style="{width:`${value}px`}"></colgroup><thead><tr>
   <th><input type="checkbox" aria-label="全选当前页子邮箱" :checked="!!state.items.length&&checked===state.items.length" :indeterminate="checked>0&&checked<state.items.length" :disabled="!state.items.length" @change="owner.togglePage(($event.target as HTMLInputElement).checked)"><EmailResizeGrip :index="0" :columns="widths" label="历史"/></th>
   <th><EmailColumnFilter label="子邮箱" :value="state.filters.q" :active="active" @change="owner.updateFilters({q:$event})"/><EmailResizeGrip :index="1" :columns="widths" label="历史"/></th>
   <th><EmailColumnFilter label="母邮箱" :value="state.filters.parent_q" :active="active" @change="owner.updateFilters({parent_q:$event})"/><EmailResizeGrip :index="2" :columns="widths" label="历史"/></th>
   <th><EmailColumnFilter label="来源" :value="state.filters.source" empty-value="all" :options="sources" :active="active" @change="owner.updateFilters({source:$event})"/><EmailResizeGrip :index="3" :columns="widths" label="历史"/></th>
   <th><EmailColumnFilter label="状态" :value="state.filters.state" :options="statuses" :active="active" @change="owner.updateFilters({state:$event})"/><EmailResizeGrip :index="4" :columns="widths" label="历史"/></th>
   <th><EmailColumnFilter label="关联账号 / 任务" :value="state.filters.related_q" :active="active" @change="owner.updateFilters({related_q:$event})"/><EmailResizeGrip :index="5" :columns="widths" label="历史"/></th>
   <th><EmailColumnFilter label="生成时间" type="range" :value="state.filters.created_from" :end-value="state.filters.created_to" :active="active" @change="owner.updateFilters({created_from:$event})" @end="owner.updateFilters({created_to:$event})"/><EmailResizeGrip :index="6" :columns="widths" label="历史"/></th>
   <th>操作 <button class="em-text-button" @click="owner.resetFilters()">清筛</button><EmailResizeGrip :index="7" :columns="widths" label="历史"/></th>
  </tr></thead>
  <tbody><tr v-for="row in state.items" :key="String(row.id)" :class="{'is-selected':state.selected.has(String(row.id))}">
   <td><input type="checkbox" :aria-label="`选择历史子邮箱 ${row.email}`" :checked="state.selected.has(String(row.id))" @change="owner.toggle(row,($event.target as HTMLInputElement).checked)"></td>
   <td class="em-align-start"><ListCell :text="row.email"/></td><td class="em-align-start"><ListCell :text="row.parent_email||'—'" :secondary="`母资源 #${row.parent_id||'—'}`"/></td>
   <td><ListCell :text="sourceLabels[row.source]||row.source"/></td><td><ListCell :text="historyLabels[row.state||'']||row.state||'状态记录缺失'"/></td><td><ListCell :text="ownership(row)"/></td><td><ListCell v-bind="dateTimeLines(row.created_at)"/></td><td><ListCell text="只读"/></td>
  </tr><tr v-if="!state.items.length"><td colspan="8" class="em-empty" role="status">{{ state.loading?'正在读取历史子邮箱…':state.error?'子邮箱历史加载失败':'当前筛选下没有历史子地址，请从 Email Butler 等来源手动准备邮箱，再导入本地库存。' }}</td></tr></tbody></table></div>
  <ListPagination :page="state.page" :size="state.size" :total="state.total" :busy="state.loading" :page-sizes="[20,50,100]" label="历史子邮箱分页" @update:page="owner.setPage" @update:size="owner.setSize"/>
 </section>
</template>
