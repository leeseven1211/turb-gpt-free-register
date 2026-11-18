<script setup lang="ts">
import type {useColumnWidths} from '../../shared/useColumnWidths';
defineProps<{index:number;columns:ReturnType<typeof useColumnWidths>;label:string}>();
</script>
<template><button class="em-resize" :aria-label="`调整${label}第 ${index+1} 列宽度`" @pointerdown="columns.resize(index,$event)" @keydown.left.prevent="columns.resizeWithKeyboard(index,-10)" @keydown.right.prevent="columns.resizeWithKeyboard(index,10)"/></template>
