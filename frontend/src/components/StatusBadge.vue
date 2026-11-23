<script setup lang="ts">
import {label, statusTone} from '../features/tasks/presentation';
import '../styles/list.css';
withDefaults(defineProps<{value?: string | null; group?: string}>(), {group: 'status'});
</script>
<template><span class="ui-badge tc-badge" :class="`ui-badge--${statusTone(value)}`">{{ label(group, value) }}</span></template>
