<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import FilterPopover from '../../components/FilterPopover.vue';
const props=defineProps<{label:string;value:string;active:boolean;type?:'text'|'date'|'range';endValue?:string;emptyValue?:string;options?:{value:string;label:string;count?:number}[]}>();
const emit=defineEmits<{change:[string];end:[string]}>();
const open=ref(false);
watch(()=>props.active,value=>{if(!value)open.value=false;});
const applied=computed(()=>props.value!==(props.emptyValue||'')||!!props.endValue);
const visibleOptions=computed(()=>(props.options||[]).filter(option=>option.count===undefined||option.count>0||option.value===props.value));
let composing=false;
function compositionEnd(event:CompositionEvent){composing=false;emit('change',(event.target as HTMLInputElement).value);}
function textInput(event:Event){if(!composing)emit('change',(event.target as HTMLInputElement).value);}
</script>
<template>
 <FilterPopover :label="label" :active="applied" :summary="[value,endValue].filter(Boolean).join(' 至 ')" :open="open" @update:open="open=$event">
  <div v-if="options" class="em-filter-field">{{ label }}
   <div class="list-filter-options" role="radiogroup" :aria-label="label">
    <label class="list-filter-option" :data-filter-value="emptyValue||''">
     <input type="radio" :name="`filter-${label}`" :value="emptyValue||''" :checked="!value||value===(emptyValue||'')" @change="emit('change',emptyValue||'')">
     <span>全部</span>
    </label>
    <label v-for="option in visibleOptions" :key="option.value" class="list-filter-option" :data-filter-value="option.value">
     <input type="radio" :name="`filter-${label}`" :value="option.value" :checked="value===option.value" @change="emit('change',option.value)">
     <span>{{ option.label }}</span>
     <small v-if="option.count!==undefined">{{ option.count }}</small>
    </label>
   </div>
  </div>
  <label v-else class="em-filter-field">{{ label }}
   <input :aria-label="label" :type="type==='date'||type==='range'?'date':'search'" :multiple="false" :value="value" @compositionstart="composing=true" @compositionend="compositionEnd" @input="textInput">
  </label>
  <label v-if="type==='range'" class="em-filter-field">结束日期<input type="date" :aria-label="`${label}结束`" :value="endValue" @input="emit('end',($event.target as HTMLInputElement).value)"></label>
  <div class="list-filter-actions"><button type="button" @click="emit('change',emptyValue||'');type==='range'&&emit('end','')">清除条件</button></div>
 </FilterPopover>
</template>
