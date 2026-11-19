<script setup lang="ts">
import {computed,ref} from 'vue';
import FilterPopover from '../../components/FilterPopover.vue';
type RegistrationFilterKey='id'|'email'|'email_source'|'status'|'proxy'|'error'|'date_from'|'date_to';
const labels:Record<RegistrationFilterKey,string>={id:'ID',email:'邮箱',email_source:'邮箱来源',status:'状态',proxy:'代理',error:'错误',date_from:'开始日期',date_to:'截止日期'};
const props=defineProps<{column?:RegistrationFilterKey;values:Record<RegistrationFilterKey,string>;sources:{value:string;label?:string}[];open:boolean}>();
const emit=defineEmits<{'update:open':[boolean];change:[RegistrationFilterKey,string]}>();
const selected=ref<RegistrationFilterKey>('email'),current=computed(()=>props.column||selected.value),value=computed(()=>props.values[current.value]);
const statusOptions=computed(()=>[...new Set(['pending','running','stopping','success','partial_success','failed','stopped','cancelled','interrupted','request_unknown','attention_required',...(props.values.status?[props.values.status]:[])])]);
const statusLabel=(key:string)=>({pending:'排队中',running:'运行中',stopping:'停止中',success:'成功',partial_success:'部分成功',failed:'失败',stopped:'已停止',cancelled:'已取消',interrupted:'执行中断',request_unknown:'待核对',attention_required:'待核对'} as Record<string,string>)[key]||key;
function change(value:string){emit('change',current.value,value);}
</script>
<template>
 <FilterPopover :label="column?labels[column]:'注册任务'" :trigger-label="column?labels[column]:'筛选'" :active="column?Boolean(values[column]):Object.values(values).some(Boolean)" :summary="value" :open="open" @update:open="emit('update:open',$event)">
  <div class="registration-filter-fields">
   <label v-if="!column">筛选列<select v-model="selected" aria-label="选择注册任务筛选列"><option v-for="(label,key) in labels" :key="key" :value="key">{{label}}</option></select></label>
   <label>{{labels[current]}}
    <select v-if="current==='email_source'" :value="value" :aria-label="`筛选${labels[current]}值`" @change="change(($event.target as HTMLSelectElement).value)"><option value="">全部邮箱来源</option><option v-for="source in sources" :key="source.value" :value="source.value">{{source.label||source.value}}</option></select>
    <select v-else-if="current==='status'" :value="value" aria-label="筛选状态值" @change="change(($event.target as HTMLSelectElement).value)"><option value="">全部状态</option><option v-for="status in statusOptions" :key="status" :value="status">{{statusLabel(status)}}</option></select>
    <input v-else :type="current.startsWith('date_')?'date':'search'" :value="value" :aria-label="`筛选${labels[current]}值`" @change="change(($event.target as HTMLInputElement).value)" @keydown.enter="emit('update:open',false)">
   </label>
   <div class="registration-filter-actions"><button type="button" @click="change('')">清除此列</button><button type="button" @click="emit('update:open',false)">完成</button></div>
  </div>
 </FilterPopover>
</template>
<style scoped>
.registration-filter-fields,.registration-filter-fields label{display:flex;flex-direction:column;gap:8px}.registration-filter-fields{gap:12px}.registration-filter-fields :is(input,select){width:100%;min-height:36px;min-width:0;border:1px solid var(--ui-color-border-strong);border-radius:5px;padding:5px 8px;background:var(--ui-color-surface);color:inherit}.registration-filter-actions{display:flex;justify-content:space-between;gap:8px}.registration-filter-actions button{min-height:34px;padding:4px 8px}
</style>
