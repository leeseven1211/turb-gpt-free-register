<script setup lang="ts">
import {computed} from 'vue';
import type {ConfigActions, ConfigActionName} from './configActions';

const props = defineProps<{actions: ConfigActions; fieldKey: string}>();
const mapping: Record<string, {name: ConfigActionName; label: string; accessibleLabel: string; run: () => Promise<void>}> = {
  EXTRACT_LINK_HUANGUANG_CDK: {
    name: 'huanguangExtraction',
    label: '查询剩余次数',
    accessibleLabel: '查询幻光提链 CDK 剩余次数',
    run: () => props.actions.queryHuanguangQuota('extraction'),
  },
  EXTRACT_LINK_HUANGUANG_PAYMENT_CDK: {
    name: 'huanguangPayment',
    label: '查询剩余次数',
    accessibleLabel: '查询幻光支付扫码 CDK 剩余次数',
    run: () => props.actions.queryHuanguangQuota('payment'),
  },
  EXTRACT_LINK_HUANGUANG_XXSYUN_API_KEY: {
    name: 'huanguangXxsyun',
    label: '查询剩余次数',
    accessibleLabel: '查询幻光 XXSYUN API Key 剩余次数',
    run: () => props.actions.queryHuanguangXxsyun(),
  },
  EXTRACT_LINK_PAYMENT_XXSYUN_API_KEY: {
    name: 'xxsyunBalance',
    label: '查询积分',
    accessibleLabel: '查询独立支付 XXSYUN 积分',
    run: () => props.actions.queryXxsyunBalance(),
  },
};
const action = computed(() => mapping[props.fieldKey]);
const state = computed(() => (action.value ? props.actions.states[action.value.name] : null));
</script>

<template>
  <div v-if="action && state" class="config-field-actions" :aria-busy="state.loading || state.posting">
    <button
      type="button"
      class="btn"
      :aria-label="action.accessibleLabel"
      :disabled="state.loading || state.posting"
      :data-config-field-action="fieldKey"
      @click="action.run()"
    >
      {{ state.loading || state.posting ? '正在查询…' : action.label }}
    </button>
    <p
      v-if="state.error || state.text"
      class="config-setting-short-help-v2"
      :class="{'config-action-error': state.error}"
      role="status"
      aria-live="polite"
    >
      {{ state.error || state.text }}
    </p>
  </div>
</template>

<style scoped>
.config-field-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.config-field-actions p {
  margin: 0;
  padding: 3px 8px;
  border-radius: 6px;
  background: var(--config-subtle, #f8f9fc);
  border: 1px solid var(--config-border, #e5e8ef);
  font-size: 12px;
  line-height: 1.4;
  white-space: normal;
  overflow-wrap: anywhere;
}

.config-action-error {
  color: var(--config-danger, #b42318) !important;
  background: var(--config-danger-soft, #fef3f2) !important;
  border-color: var(--config-danger-border, #fecdca) !important;
}

button {
  min-height: 32px;
}
</style>
