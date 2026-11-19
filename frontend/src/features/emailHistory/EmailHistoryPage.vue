<script setup lang="ts">
import {computed, ref, watch} from 'vue';
import FilterPopover from '../../components/FilterPopover.vue';
import ListCell from '../../components/ListCell.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListPagination from '../../components/ListPagination.vue';
import {dateTimeLines} from '../../shared/time';
import {useColumnWidths} from '../../shared/useColumnWidths';
import {filterLabels, ownership, pageSizes, sources, statuses, useEmailHistory, type FilterKey} from './history';

const props = defineProps<{clipboard: (value: string) => Promise<boolean>}>();
const {state, active, chips, setView, setVisible, refresh, updateFilter, resetFilters, removeFilter, setPage, setSize, toggle, togglePage, copy} = useEmailHistory(props.clipboard);
defineExpose({setView, setVisible, refresh});
const {widths, total, resize, resizeWithKeyboard, resetColumns} = useColumnWidths({
  defaults: [40, 248, 224, 112, 120, 172, 140, 88], storageKey: 'gpt_console_table_widths_derivations',
  totalStorageKey: 'gpt_console_table_total_derivations', min: 28, max: 20000,
});
type Column = {key: string; label: string; filter?: FilterKey; options?: Record<string, string>};
const columns: Column[] = [
  {key: 'check', label: '选择'}, {key: 'child', label: '子邮箱', filter: 'q'}, {key: 'parent', label: '母邮箱', filter: 'parent_q'},
  {key: 'source', label: '来源', filter: 'source', options: sources}, {key: 'state', label: '状态', filter: 'state', options: statuses},
  {key: 'related', label: '关联账号 / 任务', filter: 'related_q'}, {key: 'date', label: '生成时间', filter: 'created_from'}, {key: 'actions', label: '操作'},
];
const checked = computed(() => state.items.filter(row => state.selected.has(String(row.id))).length);
const open = ref('');
watch(active, value => {if (!value) open.value = '';});
function changeOpen(key: string, value: boolean) {
  if (value) open.value = key;
  else if (open.value === key) open.value = '';
}
function textInput(key: FilterKey, event: Event) {
  if (!(event as InputEvent).isComposing) updateFilter(key, (event.target as HTMLInputElement).value);
}
function clearColumn(key: FilterKey) {
  updateFilter(key, key === 'source' ? 'all' : '');
  if (key === 'created_from') updateFilter('created_to', '');
}
</script>

<template>
  <div class="eh-page" :aria-busy="state.loading">
    <p class="eh-note">子邮箱由你手动准备并导入本地库存；此处可查看、筛选和复制已有记录，Turb 不会自动生成。</p>
    <div class="eh-toolbar">
      <span>{{ state.selected.size ? `已选 ${state.selected.size} 条历史记录` : '可筛选并复制历史子邮箱' }}</span>
      <button type="button" class="eh-button" data-history-copy :disabled="!state.items.length && !state.selected.size" @click="copy">{{ state.selected.size ? '复制选中' : '复制当前页' }}</button>
      <button type="button" class="eh-button eh-reset-widths" @click="resetColumns">恢复列宽</button>
    </div>
    <div class="eh-count-row" data-email-count-row>
      <strong>{{ state.total }} 条历史记录</strong>
      <span>当前页 {{ state.items.length }} 条</span>
      <ListFilterSummary class="eh-summary" :items="chips" @remove="removeFilter"/>
    </div>
    <p v-if="state.error" class="eh-error" role="alert">{{ state.error }} <button type="button" class="eh-button" @click="refresh">重试</button></p>
    <p v-if="state.receipt" class="eh-note" role="status">{{ state.receipt }}</p>
    <div class="eh-scroll">
      <table class="eh-table" aria-label="历史子邮箱" :style="{width: `${total}px`}">
        <colgroup><col v-for="(value,index) in widths" :key="index" :style="{width:`${value}px`}"></colgroup>
        <thead><tr>
          <th v-for="(column,index) in columns" :key="column.key" scope="col">
            <input v-if="column.key === 'check'" type="checkbox" aria-label="全选当前页子邮箱" :checked="!!state.items.length && checked === state.items.length" :indeterminate="checked > 0 && checked < state.items.length" :disabled="!state.items.length" @change="togglePage(($event.target as HTMLInputElement).checked)">
            <FilterPopover v-else-if="column.filter" :label="column.label" :open="open === column.key" :active="chips.some(chip => chip.key === column.filter || (column.key === 'date' && chip.key === 'created_to'))" :summary="column.key === 'date' ? [state.filters.created_from,state.filters.created_to].filter(Boolean).join(' 至 ') : column.options?.[state.filters[column.filter]] || state.filters[column.filter]" @update:open="changeOpen(column.key, $event)">
              <label v-if="column.options" class="eh-field">{{ column.label }}
                <select :aria-label="column.label" :value="state.filters[column.filter]" @change="updateFilter(column.filter, ($event.target as HTMLSelectElement).value)">
                  <option :value="column.filter === 'source' ? 'all' : ''">全部</option>
                  <option v-for="(label,key) in column.options" :key="key" :value="key">{{ label }}</option>
                </select>
              </label>
              <template v-else-if="column.key === 'date'">
                <label v-for="key in (['created_from','created_to'] as const)" :key="key" class="eh-field">{{ filterLabels[key] }}
                  <input type="date" :aria-label="filterLabels[key]" :value="state.filters[key]" @input="textInput(key, $event)">
                </label>
              </template>
              <label v-else class="eh-field">{{ column.label }}
                <input type="search" :aria-label="column.label" :value="state.filters[column.filter]" @input="textInput(column.filter, $event)" @compositionend="updateFilter(column.filter, ($event.target as HTMLInputElement).value)">
              </label>
              <div class="list-filter-actions"><button type="button" @click="clearColumn(column.filter)">清除条件</button></div>
            </FilterPopover>
            <template v-else>操作 <button type="button" class="eh-clear" @click="resetFilters">清筛</button></template>
            <button type="button" class="eh-grip" :aria-label="`调整${column.label}列宽`" @pointerdown.prevent="resize(index,$event)" @keydown.left.prevent="resizeWithKeyboard(index,-10)" @keydown.right.prevent="resizeWithKeyboard(index,10)"/>
          </th>
        </tr></thead>
        <tbody>
          <tr v-for="row in state.items" :key="row.id" :class="{'eh-selected': state.selected.has(String(row.id))}">
            <td><input type="checkbox" :aria-label="`选择 ${row.email}`" :checked="state.selected.has(String(row.id))" @change="toggle(row,($event.target as HTMLInputElement).checked)"></td>
            <td><ListCell :text="row.email"/></td><td><ListCell :text="row.parent_email || '—'" :secondary="`母资源 #${row.parent_id || '—'}`"/></td>
            <td><ListCell :text="sources[row.source] || row.source"/></td>
            <td><ListCell :text="statuses[row.state || ''] || row.state || '状态记录缺失'" :tone="row.state === 'disabled' ? 'danger' : row.state === 'available' ? 'success' : 'neutral'"/></td>
            <td><ListCell :text="ownership(row)"/></td><td><ListCell v-bind="dateTimeLines(row.created_at)"/></td><td><ListCell text="只读"/></td>
          </tr>
          <tr v-if="!state.items.length"><td colspan="8" class="eh-empty" role="status">
            {{ state.loading ? '正在读取历史子邮箱…' : state.error ? '子邮箱历史加载失败' : '当前筛选下没有历史子地址，请从 Email Butler 等来源手动准备邮箱，再导入本地库存。' }}
          </td></tr>
        </tbody>
      </table>
    </div>
    <ListPagination :page="state.page" :size="state.size" :total="state.total" :busy="state.loading" :page-sizes="pageSizes" label="历史子邮箱分页" @update:page="setPage" @update:size="setSize"/>
  </div>
</template>

<style scoped>
.eh-page {min-width:0;color:var(--ui-color-text);font-size:13px}
.eh-note,.eh-error {padding:8px 16px;margin:0;line-height:1.6;color:var(--ui-color-text-secondary)}
.eh-error {color:var(--ui-color-danger)}
.eh-toolbar {display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:8px 16px;background:var(--ui-color-surface-subtle)}
.eh-count-row {display:flex;align-items:center;gap:12px;min-width:0;padding:6px 16px;color:var(--ui-color-text-secondary)}
.eh-count-row>strong,.eh-count-row>span {flex:none;white-space:nowrap}
.eh-summary {flex:0 1 auto;min-width:0}
.eh-reset-widths {margin-inline-start:auto}
.eh-button,.eh-clear {background:var(--ui-color-surface);color:var(--ui-color-text);border:1px solid var(--ui-color-border-strong);border-radius:5px;font:inherit;cursor:pointer;min-height:32px;padding:4px 8px}
.eh-clear {border:none;color:var(--ui-color-brand);background:transparent;padding:0}
.eh-button:disabled {opacity:.5;cursor:default}
.eh-field {display:grid;gap:4px;margin-bottom:10px}
.eh-field input,.eh-field select {width:100%;min-height:36px;padding:5px 8px;border:1px solid var(--ui-color-border-strong);border-radius:5px;background:var(--ui-color-surface);color:var(--ui-color-text)}
.eh-scroll {max-width:100%;overflow:auto}
.eh-table {table-layout:fixed;border-collapse:collapse;font-size:12px;min-width:100%}
.eh-table th,.eh-table td {position:relative;text-align:left;vertical-align:middle;padding:8px;border-block-end:1px solid var(--ui-color-border)}
.eh-table th {background:var(--ui-color-surface-subtle);color:var(--ui-color-text-secondary)}
.eh-table th:first-child,.eh-table td:first-child {text-align:center}
.eh-table input[type=checkbox] {width:16px;height:16px;min-height:0;margin:0;vertical-align:middle;accent-color:var(--ui-color-brand)}
.eh-table .eh-empty {text-align:start;padding:14px 16px}
.eh-selected {background:var(--ui-color-brand-soft)}
.eh-grip {position:absolute;inset-block:0;right:0;width:8px;padding:0;border:0;background:transparent;cursor:col-resize;touch-action:none}
.eh-grip:hover,.eh-grip:focus-visible {border-right:2px solid var(--ui-color-brand)}
@media(max-width:680px) {.eh-button,.eh-clear,.eh-table :deep(.tc-column-filter-trigger) {min-height:40px}.eh-field input,.eh-field select {font-size:16px}}
</style>
