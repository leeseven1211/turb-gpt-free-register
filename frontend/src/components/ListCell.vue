<script setup lang="ts">
withDefaults(defineProps<{
  text: string;
  secondary?: string;
  title?: string;
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'active';
}>(), {tone: 'neutral'});
</script>

<template>
  <div class="list-cell" :class="`list-cell--${tone}`" :title="title ?? [text, secondary].filter(Boolean).join(' · ')">
    <div class="list-cell-primary" :class="{'list-cell-single': !!secondary}"><slot>{{ text }}</slot></div>
    <div v-if="secondary" class="list-cell-secondary">{{ secondary }}</div>
  </div>
</template>

<style scoped>
.list-cell {min-width:0;max-width:100%;line-height:18px;color:var(--ui-color-text)}
.list-cell-primary {display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;overflow-wrap:anywhere;max-height:36px}
.list-cell-single,.list-cell-secondary {display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-height:18px}
.list-cell-secondary {margin-top:4px;color:var(--ui-color-text-secondary)}
.list-cell--danger .list-cell-primary {color:var(--ui-color-danger)}
.list-cell--success .list-cell-primary {color:var(--ui-color-success)}
.list-cell--warning .list-cell-primary {color:var(--ui-color-warning,var(--ui-color-text))}
.list-cell--active .list-cell-primary {color:var(--ui-color-brand)}
.list-cell :deep(button) {font:inherit;max-width:100%;width:100%;min-height:0;padding:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
