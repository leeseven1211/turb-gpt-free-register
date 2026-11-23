<script setup lang="ts">
import '../styles/list.css';
// 列表工具栏：左侧计数与已应用条件，右侧本页操作。
defineProps<{filtered?: boolean}>();
</script>
<template>
  <div class="ui-list-toolbar" :class="{'is-filtered': filtered}">
    <div class="ui-list-toolbar__main"><slot/></div>
    <div v-if="$slots.actions" class="ui-list-toolbar__actions"><slot name="actions"/></div>
  </div>
</template>
