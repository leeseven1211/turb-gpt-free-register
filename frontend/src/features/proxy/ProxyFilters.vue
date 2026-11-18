<script setup lang="ts">
import { computed, ref } from 'vue';
import FilterPopover from '../../components/FilterPopover.vue';
import type { ProxyRecordView, ProxySummary } from './contracts';
import { filterLabels, options, type FilterKey } from './filterDefinitions';
const props = defineProps<{
  column?: FilterKey;
  triggerLabel?: string;
  view: ProxyRecordView;
  filters: { search: string; window: string; purpose: string };
  state: string;
  summary: ProxySummary | null;
  open: boolean;
}>();
const emit = defineEmits<{ 'update:open': [boolean]; change: [FilterKey, string] }>();
const selected = ref<FilterKey>('search');
const fields = computed(
  () => ['search', 'state', ...(props.view === 'traffic' ? [] : ['purpose']), 'window'] as FilterKey[],
);
const current = computed(
    () => props.column ?? (fields.value.includes(selected.value) ? selected.value : 'search'),
  ),
  value = computed(() => (current.value === 'state' ? props.state : props.filters[current.value]));
const active = computed(() =>
  props.column
    ? value.value !== (current.value === 'search' ? '' : 'all')
    : fields.value.some(
        (key) => (key === 'state' ? props.state : props.filters[key]) !== (key === 'search' ? '' : 'all'),
      ),
);
function change(value: string) {
  emit('change', current.value, value);
  if (current.value !== 'search') emit('update:open', false);
}
</script>
<template>
  <FilterPopover
    :label="column ? filterLabels[column] : '代理记录'"
    :trigger-label="triggerLabel || (column ? filterLabels[column] : '筛选')"
    :active="active"
    :summary="value"
    :open="open"
    @update:open="emit('update:open', $event)"
  >
    <div class="pt-filter-fields">
      <label v-if="!column" class="pt-filter-field"
        >筛选列<select v-model="selected" aria-label="选择代理记录筛选列">
          <option v-for="key in fields" :key="key" :value="key">{{ filterLabels[key] }}</option>
        </select></label
      >
      <label v-if="current === 'search'" class="pt-filter-field"
        >搜索<input
          :value="value"
          type="search"
          :placeholder="view === 'traffic' ? '来源、方法或关联 ID' : '账号、任务、租约或 IP'"
          aria-label="搜索代理记录"
          autocomplete="off"
          @input="change(($event.target as HTMLInputElement).value)"
          @keydown.enter.prevent="emit('update:open', false)"
      /></label>
      <div v-else class="pt-filter-options" role="group" :aria-label="filterLabels[current]">
        <button
          v-for="item in options(current, view, summary, value)"
          :key="item.value"
          type="button"
          :data-proxy-filter-option="item.value"
          :aria-pressed="item.value === value"
          @click="change(item.value)"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="pt-filter-actions">
        <button type="button" class="pt-link" @click="change(current === 'search' ? '' : 'all')">
          清除此列</button
        ><button type="button" class="pt-button" @click="emit('update:open', false)">完成</button>
      </div>
    </div>
  </FilterPopover>
</template>
