<script setup lang="ts">
import {computed,ref,type DeepReadonly} from 'vue';
import type {AccountFacets} from '../../api/accounts';
import type {AccountQuerySpec} from './queryAdapter';
import FilterPopover from '../../components/FilterPopover.vue';
import {accountFilters,columnActive,facetOptions,filterChips,selectedValues,textValue,type AccountColumn,type AccountFacetLabel,type AccountFilterField} from './filterDefinitions';
const props=defineProps<{query:DeepReadonly<AccountQuerySpec>;facets:DeepReadonly<AccountFacets>;label:AccountFacetLabel;open:boolean;column?:AccountColumn}>();
const emit=defineEmits<{'update:open':[boolean];change:[AccountFilterField,string|readonly string[]];clear:[string]}>();
const chosen=ref('id');
const current=computed(()=>props.column||accountFilters.find(column=>column.key===chosen.value)||accountFilters[0]!);
const active=computed(()=>props.column?columnActive(props.query,props.column):accountFilters.some(column=>columnActive(props.query,column)));
const summary=computed(()=>filterChips(props.query,props.label).find(chip=>chip.key===current.value.key)?.label||'');
const options=computed(()=>facetOptions(props.query,props.facets,current.value,props.label));
const selected=computed(()=>selectedValues(props.query,current.value.key));
const fields=computed(():AccountFilterField[]=>current.value.kind==='date-range'?['date_from','date_to']:[current.value.key as AccountFilterField]);
function toggle(value:string,checked:boolean){const next=new Set(selected.value);if(checked)next.add(value);else next.delete(value);emit('change',current.value.key as AccountFilterField,[...next]);}
function clear(){emit('clear',current.value.key);emit('update:open',false);}
</script>
<template>
  <FilterPopover :label="column?.label||'账号'" :trigger-label="column?undefined:'筛选'" :active="active" :summary="summary" :open="open" @update:open="emit('update:open',$event)">
    <div class="ac-filter-fields">
      <label v-if="!column" class="ac-filter-field">筛选列<select v-model="chosen" aria-label="选择账号筛选列"><option v-for="entry in accountFilters" :key="entry.key" :value="entry.key">{{ entry.label }}</option></select></label>
      <fieldset v-if="current.kind==='enum'" class="list-filter-options">
        <legend class="ac-sr-only">{{ current.label }}，可多选</legend>
        <label class="list-filter-option"><input type="checkbox" :checked="!selected.length" @change="emit('change',current.key as AccountFilterField,[])"><span>全部</span></label>
        <label class="list-filter-option" v-for="option in options" :key="option.value"><input type="checkbox" :value="option.value" :checked="selected.includes(option.value)" @change="toggle(option.value,($event.target as HTMLInputElement).checked)"><span>{{ option.label }}</span><small>{{ option.count }}</small></label>
      </fieldset>
      <template v-else><label v-for="(field,index) in fields" :key="field" class="ac-filter-field">{{ current.kind==='date-range'?(index?'截止日期':'开始日期'):current.label }}<input :type="current.kind==='date-range'?'date':'text'" :inputmode="current.key==='id'?'numeric':undefined" :value="textValue(query,field)" :placeholder="current.placeholder" autocomplete="off" @input="emit('change',field,($event.target as HTMLInputElement).value)" @keydown.enter.prevent="emit('update:open',false)"></label></template>
      <div class="list-filter-actions"><button type="button" @click="clear">清除此列</button><button type="button" class="list-filter-primary" @click="emit('update:open',false)">完成</button></div>
    </div>
  </FilterPopover>
</template>
