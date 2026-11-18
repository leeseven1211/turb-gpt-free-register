<script setup lang="ts">
import {label, statusTone} from '../features/tasks/presentation';
withDefaults(defineProps<{value?: string | null; group?: string}>(), {group: 'status'});
</script>
<template><span class="tc-badge" :class="`tc-badge--${statusTone(value)}`">{{ label(group, value) }}</span></template>
