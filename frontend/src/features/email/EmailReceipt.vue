<script setup lang="ts">
import ListResult from '../../components/ListResult.vue';
import type {Receipt} from './contracts';
defineProps<{receipt:Receipt|null}>();
</script>
<template><div v-if="receipt" class="em-receipt" role="status"><ListResult :label="receipt.label" :title="receipt.detail" :tone="receipt.tone"><template #details>{{ receipt.detail }}</template></ListResult></div></template>
