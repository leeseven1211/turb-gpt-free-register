<script setup lang="ts">
withDefaults(defineProps<{
  items: {key: string; label: string; title?: string; removeLabel: string}[];
  label?: string;
}>(), {label: '已应用筛选'});
const emit = defineEmits<{remove: [key: string]}>();
</script>

<template>
  <div v-if="items.length" class="list-filter-summary" role="group" :aria-label="label">
    <button v-for="item in items" :key="item.key" type="button" class="list-filter-chip" :aria-label="item.removeLabel" :title="item.title || item.label" @click="emit('remove', item.key)">
      <span>{{ item.label }}</span><span aria-hidden="true">×</span>
    </button>
  </div>
</template>

<style scoped>
.list-filter-summary {display:flex;align-items:center;gap:6px;min-width:0;overflow-x:auto;scrollbar-width:thin;padding:3px;scroll-padding-inline:3px}
.list-filter-chip {display:inline-flex;align-items:center;gap:8px;flex:none;max-width:260px;min-height:28px;padding:3px 8px;border:1px solid var(--ui-color-border);border-radius:5px;background:var(--ui-color-brand-soft);color:var(--ui-color-brand);font:inherit;font-size:12px;cursor:pointer}
.list-filter-chip>span:first-child {overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.list-filter-chip>span:last-child {flex:none}
.list-filter-chip:focus-visible {outline:2px solid var(--ui-color-brand);outline-offset:1px}
@media(max-width:680px) {.list-filter-chip {min-height:36px;max-width:220px}}
</style>
