<script setup lang="ts">
import '../styles/list.css';
// 列表的加载 / 错误 / 空状态行。文案由页面提供，组件只负责结构、语义角色与外观。
const props = withDefaults(defineProps<{
  colspan: number;
  loading?: boolean;
  error?: string | boolean;
  title?: string;
  text?: string;
  loadingTitle?: string;
  loadingText?: string;
  errorTitle?: string;
  retryLabel?: string;
}>(), {loading: false, error: '', title: '没有匹配的记录', text: '', loadingTitle: '正在加载…', loadingText: '', errorTitle: '加载失败', retryLabel: ''});
const emit = defineEmits<{retry: []}>();
const failed = () => !props.loading && !!props.error;
</script>
<template>
  <tr class="ui-table__state-row"><td :colspan="colspan">
    <div class="ui-table-state" :class="{'is-error': failed()}" :role="failed() ? 'alert' : 'status'">
      <span v-if="loading" class="ui-spinner" aria-hidden="true"></span>
      <strong>{{ loading ? loadingTitle : failed() ? errorTitle : title }}</strong>
      <p v-if="loading ? loadingText : failed() ? (typeof error === 'string' && error.trim()) : text">{{ loading ? loadingText : failed() ? error : text }}</p>
      <button v-if="failed() && retryLabel" type="button" class="ui-button" @click="emit('retry')">{{ retryLabel }}</button>
      <slot/>
    </div>
  </td></tr>
</template>
