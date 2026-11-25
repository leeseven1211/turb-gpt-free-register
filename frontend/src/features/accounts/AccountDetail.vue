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
<style>
#accountDetailDrawer .account-detail-head {
  padding: 16px 20px;
  border-bottom: 1px solid var(--ui-color-border, #e2e8f0);
  background: var(--ui-color-surface, #ffffff);
  gap: 12px;
}
#accountDetailDrawer .account-detail-head .data-panel-kicker {
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.06em;
  color: var(--ui-color-brand, #4f46e5);
  margin-bottom: 3px;
}
#accountDetailDrawer #accountDetailTitle {
  font-size: 17px;
  line-height: 1.35;
  margin: 0;
  word-break: break-all;
}
#accountDetailDrawer #accountDetailSubtitle {
  font-size: 12px;
  color: var(--ui-color-text-secondary, #64748b);
  margin: 3px 0 0;
}
#accountDetailDrawer .account-detail-close {
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
  border-radius: 8px;
  border: 1px solid var(--ui-color-border, #e2e8f0);
  background: var(--ui-color-surface, #ffffff);
  color: var(--ui-color-text-secondary, #475569);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color .15s ease, background-color .15s ease, color .15s ease;
}
#accountDetailDrawer .account-detail-close:hover {
  border-color: var(--ui-color-brand, #4f46e5);
  background: var(--ui-color-brand-soft, #eef2ff);
  color: var(--ui-color-brand, #4f46e5);
}
#accountDetailDrawer .account-detail-body {
  padding: 16px 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
#accountDetailDrawer .account-detail-section {
  padding: 14px 16px;
  border: 1px solid var(--ui-color-border, #e2e8f0);
  border-radius: 10px;
  background: var(--ui-color-surface-subtle, #f8fafc);
}
#accountDetailDrawer .account-detail-section-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--ui-color-text, #0f172a);
  margin-bottom: 6px;
}
#accountDetailDrawer .account-detail-section-copy {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--ui-color-text-secondary, #64748b);
}
#accountDetailDrawer .account-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
  gap: 8px;
}
#accountDetailDrawer .account-detail-state {
  padding: 9px 11px;
  border: 1px solid var(--ui-color-border, #e2e8f0);
  border-radius: 8px;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
#accountDetailDrawer .account-detail-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--ui-color-text-secondary, #64748b);
}
#accountDetailDrawer .account-detail-state-value {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--ui-color-text, #0f172a);
  min-width: 0;
  overflow-wrap: anywhere;
}
#accountDetailDrawer .account-detail-state > small {
  font-size: 11px;
  line-height: 1.45;
  color: var(--ui-color-text-secondary, #64748b);
  overflow-wrap: anywhere;
}
#accountDetailDrawer .account-detail-note {
  margin-top: 10px;
  padding: 9px 11px;
  border: 1px solid var(--ui-color-border, #e2e8f0);
  border-radius: 8px;
  background: #ffffff;
}
#accountDetailDrawer .account-detail-note > span {
  display: block;
  font-size: 11px;
  color: var(--ui-color-text-secondary, #64748b);
  margin-bottom: 4px;
}
#accountDetailDrawer .account-detail-note > p {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
