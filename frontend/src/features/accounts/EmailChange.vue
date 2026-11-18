<script setup lang="ts">
import {computed, nextTick, onBeforeUnmount, onUnmounted, ref} from 'vue';
import type {AccountActionContext} from './useAccounts';
import {useAccountEmailChange, type AccountEmailChangeDependencies} from './useAccountEmailChange';
const props = defineProps<{deps: AccountEmailChangeDependencies}>();
const modal = ref<HTMLElement>(), select = ref<HTMLSelectElement>(), closeButton = ref<HTMLButtonElement>();
let unmounting = false, pendingFocus: HTMLElement | null = null;
function restoreFocus() {
  const trigger = pendingFocus; pendingFocus = null;
  if (trigger?.isConnected) trigger.focus({preventScroll: true});
}
const owner = useAccountEmailChange(props.deps, {
  opened(generation) {
    pendingFocus = null;
    void nextTick(() => {
      if (unmounting || owner.generation.value !== generation || !owner.isOpen.value) return;
      select.value?.setCustomValidity(''); props.deps.syncModalScrollLock(); closeButton.value?.focus({preventScroll: true});
    });
  },
  sourcesReady(generation) {
    void nextTick(() => {
      if (unmounting || owner.generation.value !== generation || !owner.isOpen.value) return;
      select.value?.focus({preventScroll: true});
    });
  },
  closed(restore, trigger, generation) {
    pendingFocus = restore ? trigger : null;
    void nextTick(() => {
      if (unmounting || owner.generation.value !== generation || owner.isOpen.value) return;
      props.deps.syncModalScrollLock(); restoreFocus();
    });
  },
});
const {isOpen, account, accountIds, mode, sources, source, sourceStatus, sourceDisabled, error, submitting} = owner;
const title = computed(() => isOpen.value && mode.value === 'bulk' ? '批量换绑邮箱' : '换绑邮箱');
const label = computed(() => !isOpen.value ? '' : mode.value === 'bulk'
  ? `已选 ${accountIds.value.length} 个账号 · 将按账号分别领取新邮箱`
  : `账号 #${account.value?.id} · 当前邮箱 ${account.value?.email || '-'}`);
const placeholder = computed(() => sourceStatus.value === 'loading' ? '正在读取邮箱来源…'
  : sourceStatus.value === 'failed' ? '邮箱来源读取失败' : sourceStatus.value === 'ready' ? '请选择邮箱来源' : '打开弹窗后读取可用来源');
function activeTrigger(trigger: HTMLElement | null) {
  return trigger || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
}
function openSingle(id: string | number, context: AccountActionContext, trigger: HTMLElement | null = null) {
  return owner.openSingle(id, context, activeTrigger(trigger));
}
function openBulk(context: AccountActionContext, trigger: HTMLElement | null = null) {
  return owner.openBulk(context, activeTrigger(trigger));
}
function close(options: {restoreFocus?: boolean} = {}) {owner.close(options);}
async function submit() {
  select.value?.setCustomValidity('');
  if (!select.value?.checkValidity() || !source.value || sourceDisabled.value) {
    select.value?.setCustomValidity('请选择新邮箱来源'); owner.error.value = '请选择新邮箱来源';
    select.value?.reportValidity(); select.value?.focus(); return;
  }
  await owner.submit();
}
function keydown(event: KeyboardEvent) {
  if (!isOpen.value) return;
  if (event.key === 'Escape') {event.preventDefault(); close(); return;}
  if (event.key !== 'Tab') return;
  const controls = Array.from(modal.value?.querySelectorAll<HTMLElement>('button, select, [href], [tabindex]:not([tabindex="-1"])') || [])
    .filter(item => !('disabled' in item && item.disabled) && !item.hidden);
  const first = controls[0], last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last?.focus();}
  else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
}
document.addEventListener('keydown', keydown);
onBeforeUnmount(() => {unmounting = true; document.removeEventListener('keydown', keydown); owner.close();});
onUnmounted(() => {props.deps.syncModalScrollLock(); restoreFocus();});
defineExpose({openSingle, openBulk, close});
</script>
<template>
  <Teleport to="#accountEmailChangeHost">
    <div ref="modal" id="emailChangeModal" class="email-change-modal" :class="{hidden: !isOpen}" role="dialog" aria-modal="true"
      :aria-hidden="!isOpen" aria-labelledby="emailChangeTitle" aria-describedby="emailChangeNote"
      :data-account-id="isOpen && mode==='single' ? String(account?.id) : ''" :data-account-ids="isOpen && mode==='bulk' ? JSON.stringify(accountIds.map(Number)) : ''" @click.self="close()">
      <div class="email-change-dialog" role="document">
        <div class="email-change-head">
          <div><div class="data-panel-kicker">PROTOCOL OPERATION</div><h2 id="emailChangeTitle">{{ title }}</h2><p id="emailChangeAccountLabel">{{ label }}</p></div>
          <button ref="closeButton" id="btnCloseEmailChange" type="button" class="account-detail-close" aria-label="关闭换绑邮箱" @click="close()">×</button>
        </div>
        <form id="emailChangeForm" class="email-change-form" novalidate @submit.prevent="submit">
          <label class="email-change-field" for="emailChangeSource">
            <span>新邮箱来源</span>
            <select ref="select" id="emailChangeSource" v-model="source" name="email_source" required :disabled="sourceDisabled" aria-describedby="emailChangeSourceHelp emailChangeSourceError">
              <option value="">{{ placeholder }}</option>
              <option v-for="(item,index) in sources" :key="`${item.value}:${index}`" :value="item.value" :disabled="!item.enabled" :title="item.reason" :data-reason="item.reason">{{ item.label }}{{ item.enabled ? '' : '（不可用）' }}</option>
            </select>
            <small id="emailChangeSourceHelp">系统会从所选邮箱池自动领取新地址，并读取新邮箱验证码。</small>
            <small id="emailChangeSourceError" class="email-change-error" role="alert" :hidden="!error">{{ error }}</small>
          </label>
          <div id="emailChangeNote" class="email-change-note">换绑、Recent Login 和验证码校验全部走协议任务，不会启动浏览器。成功写回后会自动创建一次协议查活任务刷新 AT。</div>
          <div class="email-change-foot">
            <button id="btnCancelEmailChange" type="button" class="jobs-tb-btn" @click="close()">取消</button>
            <button id="btnSubmitEmailChange" type="submit" class="jobs-tb-btn jobs-tb-btn--primary" :disabled="submitting">{{ submitting ? '提交中…' : '开始换绑' }}</button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>
