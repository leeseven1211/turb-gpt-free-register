<script setup lang="ts">
import {computed} from 'vue';
import type {ConfigActions} from './configActions';

const props = defineProps<{id: string; label: string; value: string; actions: ConfigActions}>();
const emit = defineEmits<{change: [value: string]}>();
const selected = computed(() => [...new Set(props.value.split(/[,，\s]+/).filter(Boolean))]);
const state = computed(() => props.actions.states.sub2apiGroups);
const options = computed(() => [
  ...props.actions.sub2apiGroups.value,
  ...selected.value
    .filter(value => !props.actions.sub2apiGroups.value.some(item => item.value === value))
    .map(value => ({value, label: `已配置分组（ID ${value}）`})),
]);
const status = computed(
  () =>
    `${
      state.value.error ||
      state.value.text ||
      (state.value.snapshot === null
        ? '可查询分组后勾选，也可直接填写 ID'
        : `已查询 ${props.actions.sub2apiGroups.value.length} 个分组`)
    }；${selected.value.length ? `当前选择分组 ID：${selected.value.join('、')}` : '当前选择全部分组'}。`,
);

function toggle(id: string, checked: boolean) {
  emit('change', (checked ? [...selected.value, id] : selected.value.filter(value => value !== id)).join(','));
}
</script>

<template>
  <div class="config-sub2api-groups-v2" data-sub2api-monitor-groups :aria-busy="state.loading">
    <div class="config-sub2api-input-row">
      <input
        :id="id"
        type="text"
        data-key="SUB2API_MONITOR_GROUP_IDS"
        :value="value"
        placeholder="例如：17,18；留空扫描全部"
        :aria-label="label"
        :aria-describedby="`${id}-groups-help ${id}-groups-status`"
        autocomplete="off"
        spellcheck="false"
        @input="emit('change', ($event.target as HTMLInputElement).value)"
      />
      <button
        type="button"
        class="btn"
        data-query-sub2api-groups
        :disabled="state.loading"
        @click="actions.querySub2ApiGroups()"
      >
        {{ state.loading ? '正在查询…' : '查询分组' }}
      </button>
    </div>
    <p :id="`${id}-groups-help`" class="config-setting-short-help-v2">
      使用已保存的 Sub2API 连接查询；可多选，不选时扫描全部分组，修改后点击保存生效。
    </p>
    <div
      class="config-multi-options-v2"
      data-sub2api-monitor-group-options
      role="group"
      aria-label="选择异常巡检分组"
    >
      <label
        v-for="option in options"
        :key="option.value"
        class="config-multi-option-v2"
        :class="{'is-selected': selected.includes(option.value)}"
      >
        <input
          type="checkbox"
          :data-sub2api-monitor-group-id="option.value"
          :checked="selected.includes(option.value)"
          @change="toggle(option.value, ($event.target as HTMLInputElement).checked)"
        />
        <span>{{ option.label }}</span>
      </label>
    </div>
    <p
      :id="`${id}-groups-status`"
      class="config-setting-short-help-v2 config-sub2api-status"
      data-sub2api-monitor-groups-status
      role="status"
      aria-live="polite"
    >
      {{ status }}
    </p>
  </div>
</template>
