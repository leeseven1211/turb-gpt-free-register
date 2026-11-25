<script setup lang="ts">
import {computed, ref, watch} from 'vue';

const props = withDefaults(defineProps<{
  page: number;
  size: number;
  total: number;
  pages?: number;
  busy?: boolean;
  compact?: boolean;
  label?: string;
  pageSizes?: number[];
}>(), {busy: false, label: '列表分页', pageSizes: () => [20, 50, 100]});
const emit = defineEmits<{'update:page': [number]; 'update:size': [number]}>();
const count = computed(() => Math.max(0, Math.floor(props.total) || 0));
const pageSize = computed(() => Math.max(1, Math.floor(props.size) || 1));
const pageCount = computed(() => Math.max(1, Math.floor(props.pages || Math.ceil(count.value / pageSize.value)) || 1));
const current = computed(() => Math.min(pageCount.value, Math.max(1, Math.floor(props.page) || 1)));
const rangeStart = computed(() => count.value ? Math.min(count.value, (current.value - 1) * pageSize.value + 1) : 0);
const rangeEnd = computed(() => Math.min(count.value, current.value * pageSize.value));
const sizes = computed(() => [...new Set([...props.pageSizes, pageSize.value])].filter(value => Number.isInteger(value) && value > 0).sort((a, b) => a - b));
const draft = ref(String(current.value));
const jumpError = ref(false);
watch([current, pageCount], () => { draft.value = String(current.value); jumpError.value = false; });

// 首尾始终可见，中间只保留当前页邻近项；大列表不生成全部页码。
const pageItems = computed(() => {
  const total = pageCount.value;
  if (total <= 7) return Array.from({length: total}, (_, index) => index + 1);
  if (current.value <= 4) return [1, 2, 3, 4, 5, 'after', total] as const;
  if (current.value >= total - 3) return [1, 'before', total - 4, total - 3, total - 2, total - 1, total] as const;
  return [1, 'before', current.value - 1, current.value, current.value + 1, 'after', total] as const;
});
function goTo(value: number) {
  if (props.busy || !count.value) return;
  const next = Math.min(pageCount.value, Math.max(1, value));
  draft.value = String(next);
  jumpError.value = false;
  if (next !== current.value) emit('update:page', next);
}
function jump() {
  if (props.busy || !count.value) return;
  const value = Number(draft.value.trim());
  if (!/^\d+$/.test(draft.value.trim()) || !Number.isSafeInteger(value)) { jumpError.value = true; return; }
  goTo(value);
}
function changeSize(event: Event) {
  if (props.busy) return;
  const next = Number((event.target as HTMLSelectElement).value);
  if (!sizes.value.includes(next) || next === pageSize.value) return;
  emit('update:page', 1);
  emit('update:size', next);
}
</script>
<template>
  <nav class="tc-pagination list-pagination" :class="{'list-pagination--compact': compact}" :aria-label="label" :aria-busy="busy">
    <div class="list-pagination__layout">
    <div class="list-pagination__controls">
      <div class="list-pagination__pages">
        <button type="button" class="list-pagination__button list-pagination__previous" :disabled="busy || !count || current <= 1" @click="goTo(current - 1)">上一页</button>
        <template v-for="item in pageItems" :key="item">
          <button v-if="typeof item === 'number'" type="button" class="list-pagination__button list-pagination__number" :class="{'is-current': item === current}" :aria-label="`第 ${item} 页`" :aria-current="item === current ? 'page' : undefined" :disabled="busy || !count || item === current" @click="goTo(item)">{{ item }}</button>
          <span v-else class="list-pagination__ellipsis" aria-hidden="true">…</span>
        </template>
        <span class="list-pagination__mobile-page" aria-live="polite">{{ current }} / {{ pageCount }}</span>
        <button type="button" class="list-pagination__button list-pagination__next" :disabled="busy || !count || current >= pageCount" @click="goTo(current + 1)">下一页</button>
      </div>
      <form class="list-pagination__jump" novalidate @submit.prevent="jump">
        <label>跳至 <input v-model="draft" aria-label="跳转页码" :aria-invalid="jumpError || undefined" :title="`输入 1 至 ${pageCount} 的整数页码`" type="text" inputmode="numeric" pattern="[0-9]*" autocomplete="off" :disabled="busy || !count || pageCount <= 1" @input="jumpError = false"> 页</label>
        <button class="list-pagination__button" type="submit" :disabled="busy || !count || pageCount <= 1">跳转</button>
      </form>
    </div>
    <div class="list-pagination__meta">
      <span class="list-pagination__range" aria-live="polite"><span v-if="count">{{ rangeStart.toLocaleString() }}–{{ rangeEnd.toLocaleString() }} / </span>共 {{ count.toLocaleString() }} 条</span>
      <label class="list-pagination__size">每页 <select aria-label="每页条数" :value="pageSize" :disabled="busy" @change="changeSize"><option v-for="value in sizes" :key="value" :value="value">{{ value }} 条</option></select></label>
    </div>
    <span v-if="jumpError" class="list-pagination__error" role="alert">请输入整数页码</span>
    </div>
  </nav>
</template>
<style scoped>
.list-pagination {container:list-pagination / inline-size;min-width:0;padding:10px 16px;flex:0 0 auto;border-top:1px solid var(--ui-color-border);background:var(--ui-color-surface-subtle);color:var(--ui-color-text-secondary);font-size:12px;font-variant-numeric:tabular-nums}
/* 等宽侧翼保持中间导航相对整个页尾居中，右侧统计不会改变中心位置。 */
.list-pagination__layout {display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:10px 16px;min-width:0}
.list-pagination__meta,.list-pagination__controls,.list-pagination__pages,.list-pagination__jump,.list-pagination__size {display:flex;align-items:center;gap:8px}
.list-pagination__meta {grid-column:3;justify-content:flex-end;gap:8px 14px;min-width:0;flex-wrap:wrap;text-align:right}
.list-pagination__range {max-width:100%;overflow-wrap:anywhere}
.list-pagination__controls {grid-column:2;justify-content:center;gap:10px 16px;min-width:0;flex-wrap:wrap}
.list-pagination__pages {gap:4px;max-width:100%;flex-wrap:wrap;justify-content:center}
.list-pagination__button {display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;min-width:32px;min-height:0;height:32px;margin:0;padding:0 10px;border:1px solid var(--ui-color-border-strong);border-radius:var(--ui-radius-sm, 6px);background:var(--ui-color-surface);color:var(--ui-color-text);font:inherit;line-height:1;white-space:nowrap;cursor:pointer;transition:border-color .15s ease,background .15s ease,color .15s ease,box-shadow .15s ease}
.list-pagination__button:hover:not(:disabled) {border-color:var(--ui-color-brand);color:var(--ui-color-brand);background:var(--ui-color-brand-soft)}
.list-pagination__button:disabled {cursor:not-allowed;opacity:.45}
.list-pagination__button.is-current {background:var(--ui-color-brand);border-color:var(--ui-color-brand);color:#fff;font-weight:600;opacity:1;cursor:default;box-shadow:0 1px 3px rgba(91,92,226,.25)}
.list-pagination__ellipsis {min-width:20px;text-align:center;color:var(--ui-color-text-muted)}
.list-pagination__jump {margin:0;gap:6px;flex:none}
.list-pagination__jump label,.list-pagination__size {display:flex;align-items:center;gap:6px;white-space:nowrap}
.list-pagination__jump input,.list-pagination__size select {box-sizing:border-box;min-height:0;height:32px;min-width:0;margin:0;padding:0 8px;border:1px solid var(--ui-color-border-strong);border-radius:var(--ui-radius-sm, 6px);background:var(--ui-color-surface);color:var(--ui-color-text);font:inherit;line-height:normal;transition:border-color .15s ease,box-shadow .15s ease}
.list-pagination__jump input {width:48px;text-align:center}
.list-pagination__size select {width:auto;min-width:74px;padding:0 10px}
.list-pagination :is(input,select):hover:not(:disabled) {border-color:#b9bfce}
.list-pagination input:disabled,.list-pagination select:disabled {opacity:.45;cursor:not-allowed}
.list-pagination input[aria-invalid=true] {border-color:var(--ui-color-danger)}
.list-pagination button:focus-visible,.list-pagination input:focus-visible,.list-pagination select:focus-visible {outline:2px solid var(--ui-color-brand);outline-offset:2px}
.list-pagination__mobile-page {display:none}
.list-pagination__error {grid-column:1/-1;text-align:center;color:var(--ui-color-danger)}
@media (min-width:681px) and (pointer:fine) {
  .list-pagination--compact {padding:8px 14px}
  .list-pagination--compact .list-pagination__layout {row-gap:6px}
  .list-pagination--compact :is(button,input,select) {box-sizing:border-box;height:30px;min-height:0;margin-block:0}
}
@container list-pagination (max-width:1120px) {
  .list-pagination__layout {grid-template-columns:minmax(0,1fr)}
  .list-pagination__controls,.list-pagination__meta {grid-column:1}
}
@container list-pagination (max-width:680px) {
  .list-pagination__layout {gap:8px}
  .list-pagination__controls {gap:8px 12px}
  .list-pagination__meta {gap:8px 12px}
  .list-pagination__pages {gap:6px}
  .list-pagination__number,.list-pagination__ellipsis {display:none}
  .list-pagination__mobile-page {display:block;min-width:36px;text-align:center;white-space:nowrap}
  .list-pagination__button {min-height:40px;height:40px;padding:0 10px}
  .list-pagination__jump label {gap:4px}
  .list-pagination__jump input {width:48px}
  .list-pagination__jump input,.list-pagination__size select {height:40px;min-height:40px;font-size:16px}
}
@media(max-width:680px) {
  .list-pagination {padding:10px 12px}
}
</style>
