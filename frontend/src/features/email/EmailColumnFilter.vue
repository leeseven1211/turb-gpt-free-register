<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import FilterPopover from '../../components/FilterPopover.vue';
const props=defineProps<{label:string;value:string;active:boolean;type?:'text'|'date'|'range';endValue?:string;emptyValue?:string;options?:{value:string;label:string;count?:number}[]}>();
const emit=defineEmits<{change:[string];end:[string]}>();
const open=ref(false);
watch(()=>props.active,value=>{if(!value)open.value=false;});
const applied=computed(()=>props.value!==(props.emptyValue||'')||!!props.endValue);
let composing=false;
function compositionEnd(event:CompositionEvent){composing=false;emit('change',(event.target as HTMLInputElement).value);}
function textInput(event:Event){if(!composing)emit('change',(event.target as HTMLInputElement).value);}
</script>
<template>
 <FilterPopover :label="label" :active="applied" :summary="[value,endValue].filter(Boolean).join(' 至 ')" :open="open" @update:open="open=$event">
  <label class="em-filter-field">{{ label }}
   <select v-if="options" :aria-label="label" :value="value" @change="emit('change',($event.target as HTMLSelectElement).value)">
    <option :value="emptyValue||''">全部</option><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}{{ option.count===undefined?'':` (${option.count})` }}</option>
   </select>
   <input v-else :aria-label="label" :type="type==='date'||type==='range'?'date':'search'" :multiple="false" :value="value" @compositionstart="composing=true" @compositionend="compositionEnd" @input="textInput">
  </label>
  <label v-if="type==='range'" class="em-filter-field">结束日期<input type="date" :aria-label="`${label}结束`" :value="endValue" @input="emit('end',($event.target as HTMLInputElement).value)"></label>
  <button type="button" class="em-button" @click="emit('change',emptyValue||'');type==='range'&&emit('end','')">清除条件</button>
 </FilterPopover>
</template>
