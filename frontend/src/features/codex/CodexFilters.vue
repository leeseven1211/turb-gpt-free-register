<script setup lang="ts">
import {computed, ref, useId} from 'vue';
import type {CodexFacets, CodexFilters as FilterValues} from '../../api/codex';
import FilterPopover from '../../components/FilterPopover.vue';
import {clearFilter, codexColumns, facetLabel, filterChips, type CodexColumn} from './filterDefinitions';
const props = defineProps<{modelValue: FilterValues; facets: CodexFacets; open: boolean; column?: CodexColumn}>();
const emit = defineEmits<{'update:modelValue':[FilterValues];'update:open':[boolean]}>();
const chosen = ref('q'), radioName = useId();
const current = computed(() => props.column || codexColumns.find(column => column.key === chosen.value) || codexColumns[0]!);
const active = computed(() => props.column ? props.column.fields.some(field => !!props.modelValue[field]) : Object.values(props.modelValue).some(Boolean));
const summary = computed(() => filterChips(props.modelValue, props.facets).find(chip => chip.key === current.value.key)?.label || '');
const options = computed(() => {
  const field = current.value.fields[0]!;
  const values = (props.facets[current.value.key] || []).filter(item => current.value.key !== 'status' || item.value !== 'archived');
  const selected = props.modelValue[field];
  const result = values.map(item => ({...item, label: item.label || facetLabel(current.value.key, item.value)}));
  if (selected && !result.some(item => item.value === selected)) result.unshift({value:selected,label:facetLabel(current.value.key,selected),count:0});
  return result;
});
function change(field: keyof FilterValues, value: string) { emit('update:modelValue', {...props.modelValue, [field]: value}); }
function clear() { emit('update:modelValue', clearFilter(props.modelValue,current.value.key)); emit('update:open',false); }
function finishPointerChoice(event: MouseEvent, field: keyof FilterValues, value: string) {
  if (event.detail <= 0) return;
  // 关闭 Portal 会卸载 radio，原生 change 可能不再触发；先提交点击值。
  change(field, value);
  emit('update:open', false);
}
</script>
<template>
  <div :class="{'cx-all-filters': !column}">
    <FilterPopover :label="column?.label || '凭证'" :trigger-label="column ? undefined : '筛选'" :active="active" :summary="summary" :open="open" @update:open="emit('update:open',$event)">
      <div class="cx-filter-fields">
        <label v-if="!column" class="cx-filter-field">筛选列<select v-model="chosen" aria-label="选择筛选列"><option v-for="entry in codexColumns" :key="entry.key" :value="entry.key">{{ entry.label }}</option></select></label>
        <fieldset v-if="current.kind === 'enum'" class="list-filter-options">
          <legend class="cx-sr-only">{{ current.label }}</legend>
          <label class="list-filter-option"><input type="radio" :name="radioName" value="" :checked="!modelValue[current.fields[0]!]" @change="change(current.fields[0]!,'')" @click="finishPointerChoice($event,current.fields[0]!,'')"><span>全部</span></label>
          <label class="list-filter-option" v-for="option in options" :key="option.value"><input type="radio" :name="radioName" :value="option.value" :checked="modelValue[current.fields[0]!] === option.value" @change="change(current.fields[0]!,option.value)" @click="finishPointerChoice($event,current.fields[0]!,option.value)"><span>{{ option.label }}</span><small>{{ option.count }}</small></label>
        </fieldset>
        <template v-else>
          <label v-for="(field,index) in current.fields" :key="field" class="cx-filter-field">{{ current.kind === 'date-range' ? (index ? '截止日期' : '开始日期') : current.label }}
            <input :type="current.kind === 'text' ? 'text' : 'date'" :aria-label="current.kind === 'date-range' ? (index ? '截止日期' : '开始日期') : current.label" :value="modelValue[field]" :placeholder="current.placeholder" autocomplete="off" @input="change(field,($event.target as HTMLInputElement).value)" @keydown.enter.prevent="emit('update:open',false)">
          </label>
        </template>
        <div class="list-filter-actions"><button type="button" @click="clear">清除此列</button><button type="button" class="list-filter-primary" @click="emit('update:open',false)">完成</button></div>
      </div>
    </FilterPopover>
  </div>
</template>
