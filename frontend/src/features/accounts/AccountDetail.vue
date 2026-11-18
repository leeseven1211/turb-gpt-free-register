<script setup lang="ts">
import {computed, nextTick, onBeforeUnmount, onUnmounted, ref} from 'vue';
import type {AccountDetailReadApi} from '../../api/accountDetail';
import type {AccountViewRow} from './useAccounts';
import {useAccountDetail, type AccountDetailCallbacks, type AccountDetailPresentation, type PlanDetailsConsumer} from './useAccountDetail';

const props = defineProps<{api: AccountDetailReadApi; presentation: AccountDetailPresentation; callbacks: AccountDetailCallbacks}>();
const closeButton = ref<HTMLButtonElement>();
let unmounting = false;
let pendingFocus: HTMLElement | null = null;
function restorePendingFocus() {
  const trigger = pendingFocus;
  pendingFocus = null;
  if (trigger?.isConnected) trigger.focus({preventScroll: true});
}
const owner = useAccountDetail(props.api, {
  notify: message => props.callbacks.notify(message),
  opened(generation) {
    pendingFocus = null;
    void nextTick(() => {
      if (unmounting || owner.generation.value !== generation || !owner.isOpen.value) return;
      props.callbacks.syncModalScrollLock();
      closeButton.value?.focus({preventScroll: true});
    });
  },
  closed(restoreFocus, trigger, generation) {
    pendingFocus = restoreFocus ? trigger : null;
    void nextTick(() => {
      if (unmounting || owner.generation.value !== generation || owner.isOpen.value) return;
      props.callbacks.syncModalScrollLock();
      restorePendingFocus();
    });
  },
});
const {account, accountId, isOpen} = owner;
const title = computed(() => account.value ? account.value.email || `账号 #${account.value.id}` : '账号详情');
const subtitle = computed(() => account.value
  ? `账号 #${account.value.id} · ${props.presentation.sourceLabel(account.value.email_source) || '未知来源'}` : '');
const body = computed(() => account.value ? props.presentation.renderBody(account.value) : '');

function open(id: string, row: AccountViewRow, lease: PlanDetailsConsumer, trigger: HTMLElement | null) {
  const active = typeof document !== 'undefined' && document.activeElement instanceof HTMLElement ? document.activeElement : null;
  return owner.open(id, row, lease, trigger || active);
}
function close(restoreFocus = true) { owner.close(restoreFocus); }
onBeforeUnmount(() => { unmounting = true; owner.close(); });
onUnmounted(() => { props.callbacks.syncModalScrollLock(); restorePendingFocus(); });
defineExpose({open, close});
</script>
<template>
  <Teleport to="#accountDetailHost">
    <div id="accountDetailBackdrop" class="account-detail-backdrop" :class="{hidden: !isOpen}"
      :aria-hidden="!isOpen" @click.self="close()"></div>
    <aside id="accountDetailDrawer" class="account-detail-drawer" :class="{hidden: !isOpen}"
      :data-account-id="isOpen ? accountId : undefined" role="dialog" aria-modal="true" aria-labelledby="accountDetailTitle">
      <div class="account-detail-head">
        <div><div class="data-panel-kicker">ACCOUNT DETAIL</div><h2 id="accountDetailTitle">{{ title }}</h2><p id="accountDetailSubtitle">{{ subtitle }}</p></div>
        <button id="btnCloseAccountDetail" ref="closeButton" type="button" class="account-detail-close" aria-label="关闭账号详情" @click="close()">×</button>
      </div>
      <!-- The bridge supplies only the existing escaped, pure account presenter. -->
      <div id="accountDetailBody" class="account-detail-body" v-html="body"></div>
    </aside>
  </Teleport>
</template>
