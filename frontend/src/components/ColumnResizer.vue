<script setup lang="ts">
import '../styles/list.css';
// 表头列宽手柄：指针拖动或左右方向键，宽度计算交给 useColumnWidths。
defineProps<{label: string}>();
const emit = defineEmits<{start: [PointerEvent]; nudge: [number]}>();
</script>
<template>
  <button type="button" class="ui-table__resize" :aria-label="`调整${label}列宽，方向键调整`"
    @pointerdown.prevent="emit('start', $event)" @keydown.left.prevent="emit('nudge', -10)" @keydown.right.prevent="emit('nudge', 10)"></button>
</template>
