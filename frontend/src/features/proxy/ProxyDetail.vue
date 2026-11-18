<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import type { ProxyDetailSnapshot } from './contracts';
import { recordDetails, type FacetLabel } from './presentation';
const props = defineProps<{ snapshot: ProxyDetailSnapshot | null; facetLabel?: FacetLabel }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement>(),
  closeButton = ref<HTMLButtonElement>();
const fields = computed(() =>
  props.snapshot ? recordDetails(props.snapshot.view, props.snapshot.row, props.facetLabel) : [],
);
let savedOverflow: string | null = null,
  disposed = false;
function unlock() {
  if (savedOverflow !== null) {
    document.body.style.overflow = savedOverflow;
    savedOverflow = null;
  }
}
watch(
  () => props.snapshot,
  async (snapshot) => {
    await nextTick();
    if (disposed) return;
    if (snapshot) {
      if (!dialog.value?.open) {
        savedOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        dialog.value?.showModal();
        dialog.value?.scrollTo?.({ top: 0 });
        closeButton.value?.focus({ preventScroll: true });
      }
    } else {
      dialog.value?.close();
      unlock();
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  disposed = true;
  dialog.value?.close();
  unlock();
});
</script>
<template>
  <dialog
    ref="dialog"
    class="pt-detail-dialog"
    aria-labelledby="proxyTrafficDetailTitle"
    @cancel.prevent="emit('close')"
    @click.self="emit('close')"
    @close="snapshot && emit('close')"
  >
    <div class="pt-detail-head">
      <h3 id="proxyTrafficDetailTitle">
        {{ snapshot?.view === 'history' ? '线路历史详情' : '请求流量详情' }}
      </h3>
      <button
        ref="closeButton"
        type="button"
        class="pt-button"
        data-proxy-close-detail
        aria-label="关闭详情"
        @click="emit('close')"
      >
        关闭
      </button>
    </div>
    <dl class="pt-detail-fields">
      <div v-for="(field, index) in fields" :key="`${index}:${field.label}`">
        <dt>{{ field.label }}</dt>
        <dd>{{ field.value }}</dd>
      </div>
    </dl>
  </dialog>
</template>
