<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { TeamApiError, type TeamsApi } from '../../api/teams';
import { useNativeDialog } from '../../shared/useNativeDialog';
import type { TeamDTO } from './contracts';
import { teamReasonLabel } from './statusLabels';

const props = defineProps<{
  open: boolean;
  api: TeamsApi;
  team: TeamDTO | null;
  visible: boolean;
}>();

const emit = defineEmits<{
  close: [];
  updated: [team: TeamDTO];
  conflict: [];
  notify: [message: string];
}>();

const dialogRef = ref<HTMLDialogElement>();
useNativeDialog(dialogRef, () => props.open && props.visible, () => props.visible);

const displayNameInput = ref('');
const plannedLimitInput = ref('');
const submitting = ref(false);
const errorMessage = ref('');
const hasConflict = ref(false);

const isActiveDialog = computed(() => props.open && props.visible);

const purchasedSeatsText = computed(() => {
  const seats = props.team?.purchased_seats;
  if (seats === null || seats === undefined || !Number.isFinite(seats)) {
    return '未返回';
  }
  return `已购 ${seats} 席`;
});

function syncFromTeam() {
  displayNameInput.value = props.team?.display_name ?? '';
  plannedLimitInput.value =
    props.team?.planned_member_limit !== null &&
    props.team?.planned_member_limit !== undefined
      ? String(props.team.planned_member_limit)
      : '';
  errorMessage.value = '';
  hasConflict.value = false;
}

watch(
  () => [isActiveDialog.value, props.team?.team_id, props.team?.revision],
  ([active]) => {
    if (active) {
      syncFromTeam();
    }
  },
  { immediate: true },
);

function parseLimit(): { ok: true; value: number | null } | { ok: false; message: string } {
  const raw = plannedLimitInput.value.trim();
  if (!raw) return { ok: true, value: null };
  if (!/^[1-9]\d*$/.test(raw)) {
    return {
      ok: false,
      message: '本地计划人数上限必须为正整数（不能为 0），或留空清除上限',
    };
  }
  const num = Number(raw);
  if (!Number.isSafeInteger(num) || num <= 0) {
    return { ok: false, message: '本地计划人数上限超出有效整数范围' };
  }
  return { ok: true, value: num };
}

async function submit() {
  if (!props.team || submitting.value) return;
  errorMessage.value = '';
  hasConflict.value = false;

  const trimmedName = displayNameInput.value.trim();
  if (trimmedName.length > 120) {
    errorMessage.value = '工作区别名不能超过 120 个字符';
    return;
  }

  const parsedLimit = parseLimit();
  if (!parsedLimit.ok) {
    errorMessage.value = parsedLimit.message;
    return;
  }

  submitting.value = true;
  try {
    const res = await props.api.updateTeam(props.team.team_id, {
      expected_revision: props.team.revision,
      display_name: trimmedName || null,
      planned_member_limit: parsedLimit.value,
    });
    emit('notify', '工作区设置已保存');
    emit('updated', res.team);
    emit('close');
  } catch (err) {
    if (err instanceof TeamApiError) {
      if (
        err.code === 'team_revision_conflict' ||
        err.code === 'revision_conflict' ||
        err.status === 409
      ) {
        hasConflict.value = true;
        errorMessage.value =
          '工作区状态已变更（版本冲突），请关闭后刷新最新信息再重新编辑';
        emit('conflict');
        return;
      }
      errorMessage.value = err.message || teamReasonLabel(err.code);
    } else {
      errorMessage.value = err instanceof Error ? err.message : '保存工作区设置失败';
    }
  } finally {
    submitting.value = false;
  }
}

function requestClose() {
  if (submitting.value) return;
  emit('close');
}

function onBackdropClick(event: MouseEvent) {
  const dialog = dialogRef.value;
  if (!dialog || event.target !== dialog) return;
  const rect = dialog.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) {
    requestClose();
    return;
  }
  if (
    event.clientX < rect.left ||
    event.clientX > rect.right ||
    event.clientY < rect.top ||
    event.clientY > rect.bottom
  ) {
    requestClose();
  }
}
</script>

<template>
  <dialog
    ref="dialogRef"
    class="tm-dialog"
    aria-labelledby="teamEditDialogTitle"
    :aria-busy="submitting"
    @cancel.prevent="requestClose"
    @click="onBackdropClick"
  >
    <div class="tm-dialog__head">
      <div>
        <p class="tm-dialog__kicker">TEAM SETTINGS</p>
        <h3 id="teamEditDialogTitle" class="tm-dialog__title">编辑工作区设置</h3>
        <p class="tm-dialog__desc">
          <template v-if="team">
            工作区：<strong class="tm-mono">{{ team.workspace_id }}</strong> · 远端名称「{{ team.workspace_name || '未返回' }}」
          </template>
        </p>
      </div>
      <button
        type="button"
        class="tm-dialog__close"
        aria-label="关闭编辑弹窗"
        :disabled="submitting"
        @click="requestClose"
      >
        ×
      </button>
    </div>

    <form class="tm-dialog__body" novalidate @submit.prevent="submit">
      <div class="tm-banner tm-banner--info">
        <div class="tm-banner__copy">
          <span>
            当前远端已购席位：<strong>{{ purchasedSeatsText }}</strong>
          </span>
          <span>·</span>
          <span>仅使用已购剩余席位，与已购席位共同取较小值。</span>
        </div>
      </div>

      <label class="tm-field">
        <span class="tm-field__label">工作区本地显示别名（display_name）</span>
        <input
          v-model="displayNameInput"
          type="text"
          maxlength="120"
          :placeholder="team?.workspace_name || '留空将恢复远端工作区名称'"
          :disabled="submitting"
        />
        <span class="tm-field__hint">
          留空将清除自定义别名，恢复展示远端工作区名称「{{ team?.workspace_name || '未返回' }}」。
        </span>
      </label>

      <label class="tm-field">
        <span class="tm-field__label">本地计划人数上限（planned_member_limit）</span>
        <input
          v-model="plannedLimitInput"
          type="text"
          inputmode="numeric"
          placeholder="输入正整数（含管理母号），或留空清除上限"
          :disabled="submitting"
        />
        <span class="tm-field__hint">
          仅接受正整数（含管理母号）或留空清除上限。下调上限不会移除现有成员或撤回邀请，仅拦截后续新增占位。
        </span>
      </label>

      <div
        v-if="team && (team.purchased_seats === null || team.purchased_seats === undefined)"
        class="tm-banner tm-banner--warning"
      >
        <div class="tm-banner__copy">
          当前远端未返回已购席位；若清除本地计划人数上限，后续批量加入新成员将被拦截，直到补充上限或同步出已购席位。
        </div>
      </div>

      <div v-if="errorMessage" class="tm-banner tm-banner--danger" role="alert">
        <div class="tm-banner__copy">{{ errorMessage }}</div>
      </div>

      <div class="tm-dialog__foot" style="margin: 4px -22px -18px;">
        <span class="tm-field__hint">
          <template v-if="team">当前修订版本 v{{ team.revision }}</template>
        </span>
        <div class="tm-dialog__foot-right">
          <button
            type="button"
            class="tm-btn"
            :disabled="submitting"
            @click="requestClose"
          >
            {{ hasConflict ? '关闭并刷新' : '取消' }}
          </button>
          <button
            type="submit"
            class="tm-btn tm-btn--primary"
            :disabled="submitting || !team"
          >
            {{ submitting ? '保存中…' : '保存修改' }}
          </button>
        </div>
      </div>
    </form>
  </dialog>
</template>
