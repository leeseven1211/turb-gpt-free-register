<script setup lang="ts">
import ListCell from './ListCell.vue';
withDefaults(defineProps<{
  label: string;
  secondary?: string;
  title?: string;
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'active';
}>(), {tone: 'neutral'});
</script>

<template>
  <details v-if="$slots.details" class="list-result">
    <summary :title="title"><ListCell :text="label" :secondary="secondary" :title="title" :tone="tone"/></summary>
    <div class="list-result-details"><slot name="details"/></div>
  </details>
  <ListCell v-else :text="label" :secondary="secondary" :title="title" :tone="tone"/>
</template>

<style scoped>
.list-result {min-width:0;overflow-wrap:anywhere}
summary {display:flex;align-items:baseline;gap:5px;cursor:pointer;list-style:none}
summary::-webkit-details-marker {display:none}
summary::before {content:'▸';flex:none;color:var(--ui-color-text-secondary)}
.list-result[open]>summary::before {content:'▾'}
summary .list-cell {flex:1;min-width:0}
summary:focus-visible {outline:2px solid var(--ui-color-brand);outline-offset:3px}
.list-result-details {margin-top:8px;color:var(--ui-color-text-secondary);white-space:pre-wrap}
.list-result-details :deep(p+p) {margin-top:8px}
</style>
