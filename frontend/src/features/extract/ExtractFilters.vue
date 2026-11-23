<script setup lang="ts">
import {computed,ref} from 'vue';
import FilterPopover from '../../components/FilterPopover.vue';
import {modeLabel,statusOptions} from './presentation';
type ExtractFilterKey='query'|'provider'|'mode'|'status'|'batch';
const labels:Record<ExtractFilterKey,string>={query:'账号',provider:'平台',mode:'模式',status:'提链状态',batch:'批次'};
const props=defineProps<{column?:ExtractFilterKey;values:Record<ExtractFilterKey,string>;providers:{id:string;label?:string}[];batches:{batch_id:string|number;title?:string}[];counts?:Record<string,number>;batchBusy?:boolean;omitBatch?:boolean;open:boolean}>();
const emit=defineEmits<{'update:open':[boolean];change:[ExtractFilterKey,string]}>();
const selected=ref<ExtractFilterKey>('query'),current=computed(()=>props.column||selected.value),value=computed(()=>props.values[current.value]);
function change(value:string){emit('change',current.value,value);}
function setSelected(value:ExtractFilterKey){selected.value=value;}
const options=computed<{value:string;label:string;count?:number}[]>(()=>{
 if(current.value==='provider')return[{value:'',label:'全部平台'},...props.providers.map(provider=>({value:provider.id,label:provider.label||provider.id}))];
 if(current.value==='mode')return[{value:'',label:'全部模式'},...['extract_only','manual_payment','auto_payment'].map(mode=>({value:mode,label:modeLabel(mode)}))];
 if(current.value==='status')return statusOptions.filter(([key])=>{const count=props.counts?.[key||'all'];return count===undefined||count>0||key===value.value;}).map(([key,text])=>({value:key,label:text,count:props.counts?.[key||'all']}));
 if(current.value==='batch')return[{value:'',label:'全部任务'},...(value.value&&!props.batches.some(item=>String(item.batch_id)===value.value)?[{value:value.value,label:`批次 #${value.value}`}]:[]),...props.batches.map(batch=>({value:String(batch.batch_id),label:batch.title||`批次 #${batch.batch_id}`}))];
 return[];
});
</script>
<template>
 <FilterPopover :label="column?labels[column]:'提链任务'" :trigger-label="column?labels[column]:'筛选'" :active="column?Boolean(values[column]):Object.values(values).some(Boolean)" :summary="value" :open="open" @update:open="emit('update:open',$event)">
  <div class="extract-filter-fields">
   <div v-if="!column" class="extract-filter-field">筛选列<div class="list-filter-options" role="radiogroup" aria-label="选择提链任务筛选列"><label v-for="(label,key) in labels" v-show="key!=='batch'||!omitBatch" :key="key" class="list-filter-option"><input type="radio" :name="`extract-column-${label}`" :value="key" :checked="selected===key" @change="setSelected(key)"><span>{{ label }}</span></label></div></div>
   <div class="extract-filter-field">{{ labels[current] }}
    <input v-if="current==='query'" type="search" :value="value" aria-label="筛选账号值" placeholder="邮箱或任务号" @change="change(($event.target as HTMLInputElement).value)" @keydown.enter="emit('update:open',false)">
    <div v-else class="list-filter-options" role="radiogroup" :aria-label="`筛选${labels[current]}值`">
     <label v-for="option in options" :key="option.value" class="list-filter-option" :data-extract-option="option.value" :class="{'is-disabled':batchBusy&&current==='batch'}">
      <input type="radio" :name="`extract-${current}`" :value="option.value" :checked="value===option.value" :disabled="batchBusy&&current==='batch'" @change="change(option.value)">
      <span>{{ option.label }}</span><small v-if="option.count!==undefined">{{ option.count }}</small>
     </label>
    </div>
   </div>
   <slot v-if="current==='batch'"/>
   <div class="list-filter-actions"><button type="button" @click="change('')">清除此列</button><button type="button" class="list-filter-primary" @click="emit('update:open',false)">完成</button></div>
  </div>
 </FilterPopover>
</template>
<style scoped>
.extract-filter-fields,.extract-filter-field{display:flex;flex-direction:column;gap:8px}.extract-filter-fields{gap:12px}.extract-filter-field{font-weight:500}.list-filter-option.is-disabled{opacity:.55}
</style>
