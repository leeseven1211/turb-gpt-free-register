<script setup lang="ts">
import {computed} from 'vue';
import type {AccountOperationReceiptsView} from './operationReceipts';

const props = defineProps<{receipts: AccountOperationReceiptsView}>();
const entries = computed(() => props.receipts.entries.value);
const formatTime = new Intl.DateTimeFormat('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'});
</script>

<template>
  <details v-if="entries.length" class="ac-operation-receipts" open>
    <summary>{{ entries.length }} 次提交需核对回执</summary>
    <ul class="ac-operation-receipt-list">
      <li v-for="entry in entries" :key="entry.key">
        <div class="ac-operation-receipt-row">
          <strong>{{ entry.label }} · {{ entry.count }} 个账号 · {{ formatTime.format(entry.submittedAt) }}</strong>
          <span role="status">{{ entry.message }}</span>
          <button class="ac-button" type="button" :disabled="entry.loading" @click="receipts.lookup(entry.key)">{{ entry.loading ? '查询中…' : '查询回执' }}</button>
          <button class="ac-link" type="button" @click="receipts.dismiss(entry.key)">移除此提示</button>
        </div>
        <div v-if="entry.items.length" class="ac-operation-receipt-row">
          <button v-for="item in entry.items" :key="`${item.task_id}:${item.run_id}`" class="ac-link" type="button" @click="receipts.open(item)">
            任务 #{{ item.task_id }}<template v-if="item.run_id"> · 执行 #{{ item.run_id }}</template>
          </button>
        </div>
      </li>
    </ul>
  </details>
</template>

<style scoped>
.ac-operation-receipts {
  flex: 0 0 auto;
  padding: 8px 12px;
  border-bottom: 1px solid var(--ui-color-border);
  background: var(--ui-color-surface-subtle, var(--ui-color-surface));
  color: var(--ui-color-text);
  font-size: 12px;
}
.ac-operation-receipts summary { width: fit-content; cursor: pointer; color: var(--ui-color-brand); }
.ac-operation-receipt-list {
  max-height: min(184px, 24dvh);
  overflow: auto;
  overscroll-behavior: contain;
  margin: 4px 0 0;
  padding: 0;
  list-style: none;
}
.ac-operation-receipt-list li { padding: 4px 0; }
.ac-operation-receipt-row { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; }
.ac-operation-receipt-row span { color: var(--ui-color-text-secondary); }
</style>
