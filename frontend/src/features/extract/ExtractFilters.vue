<script setup lang="ts">
import {computed,ref} from 'vue';
import FilterPopover from '../../components/FilterPopover.vue';
import {modeLabel,statusOptions} from './presentation';
type ExtractFilterKey='query'|'provider'|'mode'|'status'|'batch';
const labels:Record<ExtractFilterKey,string>={query:'账号',provider:'平台',mode:'模式',status:'提链状态',batch:'批次'};
const props=defineProps<{column?:ExtractFilterKey;values:Record<ExtractFilterKey,string>;providers:{id:string;label?:string}[];batches:{batch_id:string|number;title?:string}[];counts?:Record<string,number>;open:boolean}>();
const emit=defineEmits<{'update:open':[boolean];change:[ExtractFilterKey,string]}>();
const selected=ref<ExtractFilterKey>('query'),current=computed(()=>props.column||selected.value),value=computed(()=>props.values[current.value]);
function change(value:string){emit('change',current.value,value);}
</script>
<template>
 <FilterPopover :label="column?labels[column]:'提链任务'" :trigger-label="column?labels[column]:'筛选'" :active="column?Boolean(values[column]):Object.values(values).some(Boolean)" :summary="value" :open="open" @update:open="emit('update:open',$event)">
  <div class="extract-filter-fields">
   <label v-if="!column">筛选列<select v-model="selected" aria-label="选择提链任务筛选列"><option v-for="(label,key) in labels" :key="key" :value="key">{{label}}</option></select></label>
   <label>{{labels[current]}}
    <input v-if="current==='query'" type="search" :value="value" aria-label="筛选账号值" placeholder="邮箱或任务号" @change="change(($event.target as HTMLInputElement).value)" @keydown.enter="emit('update:open',false)">
    <select v-else-if="current==='provider'" :value="value" aria-label="筛选平台值" @change="change(($event.target as HTMLSelectElement).value)"><option value="">全部平台</option><option v-for="provider in providers" :key="provider.id" :value="provider.id">{{provider.label||provider.id}}</option></select>
    <select v-else-if="current==='mode'" :value="value" aria-label="筛选模式值" @change="change(($event.target as HTMLSelectElement).value)"><option value="">全部模式</option><option v-for="mode in ['extract_only','manual_payment','auto_payment']" :key="mode" :value="mode">{{modeLabel(mode)}}</option></select>
    <select v-else-if="current==='status'" :value="value" aria-label="筛选提链状态值" @change="change(($event.target as HTMLSelectElement).value)"><option v-for="option in statusOptions" :key="option[0]" :value="option[0]">{{option[1]}}{{counts&&counts[option[0]||'all']!==undefined?` (${counts[option[0]||'all']})`:''}}</option></select>
    <select v-else :value="value" aria-label="筛选批次值" @change="change(($event.target as HTMLSelectElement).value)"><option value="">全部任务</option><option v-if="value&&!batches.some(item=>String(item.batch_id)===value)" :value="value">批次 #{{value}}</option><option v-for="batch in batches" :key="String(batch.batch_id)" :value="String(batch.batch_id)">{{batch.title||`批次 #${batch.batch_id}`}}</option></select>
   </label>
   <slot v-if="current==='batch'"/>
   <div class="extract-filter-actions"><button type="button" @click="change('')">清除此列</button><button type="button" @click="emit('update:open',false)">完成</button></div>
  </div>
 </FilterPopover>
</template>
<style scoped>
.extract-filter-fields,.extract-filter-fields label{display:flex;flex-direction:column;gap:8px}.extract-filter-fields{gap:12px}.extract-filter-fields :is(input,select){width:100%;min-height:36px;min-width:0;border:1px solid var(--ui-color-border-strong);border-radius:5px;padding:5px 8px;background:var(--ui-color-surface);color:inherit}.extract-filter-actions{display:flex;justify-content:space-between;gap:8px}.extract-filter-actions button{min-height:34px;padding:4px 8px}
</style>
