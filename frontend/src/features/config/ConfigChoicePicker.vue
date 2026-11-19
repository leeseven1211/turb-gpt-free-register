<script setup lang="ts">
import {computed, ref} from 'vue';
import type {ConfigOption} from './contracts';
const props=withDefaults(defineProps<{label:string; values:string[]; options:ConfigOption[]; country?:boolean; emptyLabel?:string}>(),{emptyLabel:'未选择'});
const emit=defineEmits<{change:[values:string[]]}>();
const query=ref('');const root=ref<HTMLDetailsElement>();
const all=computed<ConfigOption[]>(()=>[...props.values.filter(value=>!props.options.some(item=>item.value===value)).map(value=>({value,label:`当前值（${value}）`})),...props.options]);
const filtered=computed(()=>all.value.filter(item=>`${item.value} ${item.label}`.toLowerCase().includes(query.value.trim().toLowerCase())));
const summary=computed(()=>props.values.map(value=>all.value.find(item=>item.value===value)?.label || value).join('、') || props.emptyLabel);
function toggle(value:string){emit('change',props.values.includes(value)?props.values.filter(item=>item!==value):[...props.values,value]);}
function keyboard(event:KeyboardEvent){
 if(event.key==='Escape'){if(root.value){root.value.open=false;root.value.querySelector('summary')?.focus();}return;}
 if(!['ArrowDown','ArrowUp','ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
 const buttons=Array.from(root.value?.querySelectorAll<HTMLButtonElement>('[data-choice]')||[]);const index=buttons.indexOf(event.target as HTMLButtonElement);if(index<0||!buttons.length)return;
 event.preventDefault();const target=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(['ArrowUp','ArrowLeft'].includes(event.key)?-1:1)+buttons.length)%buttons.length;buttons[target]?.focus();
}
</script>
<template>
 <details ref="root" class="config-vue-picker" @keydown="keyboard">
  <summary :aria-label="`${label}：${summary}`" :title="summary">{{ summary }}</summary>
  <div class="config-vue-picker-menu">
   <input v-model="query" type="search" :aria-label="`搜索${label}`" placeholder="搜索并选择">
   <div v-if="country" class="config-vue-chips" aria-label="已选国家，可点击移除">
    <button v-for="value in values" :key="value" type="button" :aria-label="`移除 ${value}`" @click="toggle(value)">{{ all.find(item=>item.value===value)?.label || value }} ×</button>
   </div>
   <div class="config-vue-picker-options" :aria-label="label" role="group">
    <button v-for="option in filtered" :key="option.value" type="button" data-choice :disabled="option.disabled" :aria-pressed="values.includes(option.value)" :title="option.reason" @click="toggle(option.value)"><span aria-hidden="true">{{ values.includes(option.value)?'✓':'○' }}</span> {{ option.label }}</button>
   </div>
   <p v-if="!filtered.length" role="status">未找到匹配选项</p>
  </div>
 </details>
</template>
