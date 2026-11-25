<script setup lang="ts">
const props = withDefaults(defineProps<{
  hasPrevious: boolean;
  nextCursor: string | null;
  itemCount: number;
  hasCursor?: boolean;
  busy?: boolean;
  label?: string;
}>(), {busy: false, hasCursor: false, label: '列表分页'});
const emit = defineEmits<{previous: []; next: []; first: []}>();
function previous() {if (!props.busy && props.hasPrevious) emit('previous');}
function next() {if (!props.busy && props.nextCursor) emit('next');}
function first() {if (!props.busy && props.hasCursor) emit('first');}
</script>
<template>
  <nav class="cursor-pagination" :aria-label="label" :aria-busy="busy">
    <div class="cursor-pagination__layout">
      <span class="cursor-pagination__count" aria-live="polite">本页 {{ itemCount }} 个</span>
      <div class="cursor-pagination__actions">
        <button v-if="hasCursor" type="button" class="cursor-pagination__first" data-cursor-first :disabled="busy" @click="first">返回首页</button>
        <button type="button" data-cursor-previous :disabled="busy || !hasPrevious" @click="previous">上一页</button>
        <button type="button" data-cursor-next :disabled="busy || !nextCursor" @click="next">下一页</button>
      </div>
    </div>
  </nav>
</template>
<style scoped>
.cursor-pagination {container:cursor-pagination / inline-size;min-width:0;padding:10px 16px;border-top:1px solid var(--ui-color-border);background:var(--ui-color-surface-subtle);color:var(--ui-color-text-secondary);font-size:12px;font-variant-numeric:tabular-nums}
.cursor-pagination__layout {display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:10px 16px;min-width:0}
.cursor-pagination__count {grid-column:3;grid-row:1;justify-self:end;min-width:0;max-width:100%;overflow-wrap:anywhere;text-align:right}
.cursor-pagination__actions {grid-column:2;grid-row:1;display:flex;align-items:center;justify-content:center;gap:6px;min-width:0;max-width:100%;flex-wrap:wrap}
.cursor-pagination button {display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;min-height:0;height:32px;margin:0;padding:0 12px;border:1px solid var(--ui-color-border-strong);border-radius:var(--ui-radius-sm, 6px);background:var(--ui-color-surface);color:var(--ui-color-text);font:inherit;line-height:1;cursor:pointer;white-space:nowrap;transition:border-color .15s ease,background .15s ease,color .15s ease}
.cursor-pagination button:hover:not(:disabled) {border-color:var(--ui-color-brand);color:var(--ui-color-brand);background:var(--ui-color-brand-soft)}
.cursor-pagination button:disabled {opacity:.45;cursor:not-allowed}
.cursor-pagination button:focus-visible {outline:2px solid var(--ui-color-brand);outline-offset:2px}
.cursor-pagination .cursor-pagination__first {border-color:transparent;background:transparent;color:var(--ui-color-text-secondary)}
.cursor-pagination .cursor-pagination__first:hover:not(:disabled) {border-color:transparent;background:var(--ui-color-brand-soft);color:var(--ui-color-brand)}
@container cursor-pagination (max-width:680px) {
  .cursor-pagination__layout {grid-template-columns:minmax(0,1fr)}
  .cursor-pagination__actions {grid-column:1}
  .cursor-pagination__count {grid-column:1;grid-row:2}
}
@media(max-width:680px) {.cursor-pagination {padding:10px 12px}.cursor-pagination button {min-height:36px;height:36px}}
</style>
