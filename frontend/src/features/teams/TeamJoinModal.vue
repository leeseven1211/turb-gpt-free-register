<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { TeamApiError, type TeamsApi } from '../../api/teams';
import { useNativeDialog } from '../../shared/useNativeDialog';
import { useTeamPolling } from './useTeamPolling';
import type {
  AccountsJoinRequestPayload,
  JoinPreviewResponse,
  JoinPreviewTargetPayload,
  JoinRequestDTO,
  JoinRequestItemDTO,
  JoinRequestItemsResponse,
  TeamDTO,
  TeamDecimalId,
} from './contracts';
import {
  formatNullableCount,
  teamCapacityBasisLabel,
  teamExecutionLabel,
  teamExecutionTone,
  teamReasonLabel,
  type BadgeTone,
} from './statusLabels';

const props = defineProps<{
  open: boolean;
  api: TeamsApi;
  initialTeam?: TeamDTO | null;
  target: AccountsJoinRequestPayload | null;
  visible: boolean;
  formatDateTime: (v: string | null | undefined) => string;
}>();

const emit = defineEmits<{
  close: [];
  submitted: [receipt: JoinRequestDTO, teamId: string];
  openTask: [taskId: string, runId?: string | null];
  openTeamDetail: [teamId: string];
  teamUpdated: [team: TeamDTO];
  notify: [message: string];
}>();

const dialogRef = ref<HTMLDialogElement>();
useNativeDialog(dialogRef, () => props.open && props.visible, () => props.visible);

const stage = ref<'preview' | 'receipt'>('preview');

const availableTeams = ref<TeamDTO[]>([]);
const teamsLoading = ref(false);
const teamsError = ref('');
const selectedTeamId = ref<string>('');
const selectedTeam = ref<TeamDTO | null>(null);

const preview = ref<JoinPreviewResponse | null>(null);
const previewLoading = ref(false);
const previewError = ref('');

const inlineLimitInput = ref('');
const savingLimit = ref(false);
const limitError = ref('');

const submitting = ref(false);
const submitError = ref('');
const submitNotice = ref('');

const receipt = ref<JoinRequestDTO | null>(null);
const receiptItems = ref<JoinRequestItemsResponse | null>(null);
const receiptLoading = ref(false);
const receiptError = ref('');

let teamController: AbortController | null = null;
let previewController: AbortController | null = null;
let receiptController: AbortController | null = null;
let limitController: AbortController | null = null;
let dialogEpoch = 0;

const isActiveDialog = computed(() => props.open && props.visible);
const needsTeamPicker = computed(() => !props.initialTeam);

const effectiveTeamId = computed(
  () => selectedTeam.value?.id || selectedTeamId.value || props.target?.targetTeamId || '',
);

const eligibleJoinCount = computed(() => preview.value?.counts.eligible_count ?? 0);

const canConfirmJoin = computed(() => {
  if (
    submitting.value ||
    savingLimit.value ||
    previewLoading.value ||
    !selectedTeam.value ||
    !preview.value
  ) {
    return false;
  }
  return preview.value.capacity.can_submit && eligibleJoinCount.value > 0;
});

const meterOccupiedPercent = computed(() => {
  const cap = preview.value?.capacity;
  if (!cap || cap.effective_limit === null || cap.effective_limit <= 0 || cap.occupied_count === null) {
    return 0;
  }
  return Math.min(100, Math.max(0, Math.round((cap.occupied_count / cap.effective_limit) * 100)));
});

const meterAddedPercent = computed(() => {
  const cap = preview.value?.capacity;
  if (!cap || cap.effective_limit === null || cap.effective_limit <= 0) return 0;
  const pct = Math.round(((cap.additional_required ?? 0) / cap.effective_limit) * 100);
  return Math.min(Math.max(0, 100 - meterOccupiedPercent.value), Math.max(0, pct));
});

const remainingAfterSubmit = computed(() => {
  const cap = preview.value?.capacity;
  if (!cap || cap.available_count === null || cap.additional_required === null) return null;
  return Math.max(0, cap.available_count - cap.additional_required);
});
const needsCapacityWait = computed(() => {
  const cap = preview.value?.capacity;
  const occupied = cap?.occupied_count;
  const limit = cap?.effective_limit;
  const additional = cap?.additional_required;
  return typeof occupied === 'number' && Number.isFinite(occupied) &&
    typeof limit === 'number' && Number.isFinite(limit) &&
    typeof additional === 'number' && Number.isFinite(additional) &&
    additional > 0 && occupied + additional > limit;
});
const meterToneClass = computed(() => {
  const cap = preview.value?.capacity;
  if (!cap) return '';
  if (cap.blocking_reason_code === 'team_limit_required' ||
      (cap.available_count !== null && cap.available_count <= 1)) return 'is-warn';
  return '';
});
const receiptPage = computed(() => receiptItems.value?.page ?? 1);
const receiptTotalPages = computed(() => Math.max(1, Math.ceil(
  (receiptItems.value?.total ?? receipt.value?.counts.unique_count ?? 0) /
  (receiptItems.value?.page_size ?? 20),
)));

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

function abortAll() {
  if (teamController) {
    teamController.abort();
    teamController = null;
    teamsLoading.value = false;
  }
  if (previewController) {
    previewController.abort();
    previewController = null;
    previewLoading.value = false;
  }
  if (receiptController) {
    receiptController.abort();
    receiptController = null;
    receiptLoading.value = false;
  }
  if (limitController) {
    limitController.abort();
    limitController = null;
    savingLimit.value = false;
  }
}

function resetState() {
  dialogEpoch++;
  abortAll();
  stage.value = 'preview';
  availableTeams.value = [];
  teamsLoading.value = false;
  teamsError.value = '';
  selectedTeamId.value = '';
  selectedTeam.value = null;
  preview.value = null;
  previewLoading.value = false;
  previewError.value = '';
  inlineLimitInput.value = '';
  savingLimit.value = false;
  limitError.value = '';
  submitting.value = false;
  submitError.value = '';
  submitNotice.value = '';
  receipt.value = null;
  receiptItems.value = null;
  receiptLoading.value = false;
  receiptError.value = '';
}

function buildTargetPayload(): JoinPreviewTargetPayload | null {
  if (!props.target) return null;
  if (props.target.mode === 'explicit') {
    const accountIds = [...(props.target.accountIds || [])];
    if (!accountIds.length) return null;
    const expected = props.target.expectedEmails;
    return {
      account_ids: accountIds,
      ...(expected && Object.keys(expected).length ? { expected_emails: expected } : {}),
    };
  }
  if (!props.target.selectionId || !props.target.selectionRevision) return null;
  return {
    selection_id: props.target.selectionId,
    selection_revision: props.target.selectionRevision,
  };
}

async function runPreview(teamId: TeamDecimalId) {
  const payload = buildTargetPayload();
  if (!isActiveDialog.value || !teamId || !payload) return;

  if (previewController) previewController.abort();
  const controller = new AbortController();
  previewController = controller;
  previewLoading.value = true;
  previewError.value = '';

  try {
    const res = await props.api.previewJoin(teamId, payload, controller.signal);
    if (controller.signal.aborted || !isActiveDialog.value) return;
    preview.value = res;
  } catch (err) {
    if (isAbortError(err) || controller.signal.aborted) return;
    preview.value = null;
    previewError.value =
      err instanceof TeamApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : '生成加入预览失败';
  } finally {
    if (previewController === controller) {
      previewController = null;
      previewLoading.value = false;
    }
  }
}

async function selectAndLoadTeam(teamId: TeamDecimalId) {
  if (!teamId) return;
  selectedTeamId.value = teamId;
  const fromList = availableTeams.value.find(t => t.id === teamId);
  if (fromList) {
    selectedTeam.value = fromList;
    await runPreview(teamId);
    return;
  }

  if (teamController) teamController.abort();
  const controller = new AbortController();
  teamController = controller;
  teamsLoading.value = true;
  teamsError.value = '';

  try {
    const detail = await props.api.detail(teamId, controller.signal);
    if (controller.signal.aborted || !isActiveDialog.value) return;
    selectedTeam.value = detail.team;
    await runPreview(detail.team.id);
  } catch (err) {
    if (isAbortError(err) || controller.signal.aborted) return;
    teamsError.value =
      err instanceof TeamApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : '获取目标 Team 信息失败';
  } finally {
    if (teamController === controller) {
      teamController = null;
      teamsLoading.value = false;
    }
  }
}

async function loadTeamOptions() {
  if (!isActiveDialog.value) return;
  if (teamController) teamController.abort();
  const controller = new AbortController();
  teamController = controller;
  teamsLoading.value = true;
  teamsError.value = '';

  try {
    const res = await props.api.list(
      { page: 1, page_size: 50, include_facets: '0' },
      controller.signal,
    );
    if (controller.signal.aborted || !isActiveDialog.value) return;
    availableTeams.value = res.items;
    if (res.items.length === 1) {
      selectedTeamId.value = res.items[0]!.id;
      selectedTeam.value = res.items[0]!;
      await runPreview(res.items[0]!.id);
    }
  } catch (err) {
    if (isAbortError(err) || controller.signal.aborted) return;
    teamsError.value =
      err instanceof TeamApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : '加载可选 Team 列表失败';
  } finally {
    if (teamController === controller) {
      teamController = null;
      teamsLoading.value = false;
    }
  }
}

async function initModal() {
  resetState();
  if (!isActiveDialog.value || !props.target) return;

  if (props.initialTeam) {
    selectedTeam.value = props.initialTeam;
    selectedTeamId.value = props.initialTeam.id;
    await runPreview(props.initialTeam.id);
    return;
  }

  if (props.target.targetTeamId) {
    await selectAndLoadTeam(props.target.targetTeamId);
    return;
  }

  await loadTeamOptions();
}

function onTeamDropdownChange(event: Event) {
  if (savingLimit.value || submitting.value) return;
  const nextId = (event.target as HTMLSelectElement).value;
  preview.value = null;
  previewError.value = '';
  submitError.value = '';
  submitNotice.value = '';
  if (!nextId) {
    selectedTeamId.value = '';
    selectedTeam.value = null;
    return;
  }
  void selectAndLoadTeam(nextId);
}

async function saveInlinePlannedLimit() {
  if (!isActiveDialog.value || !selectedTeam.value || savingLimit.value) return;
  limitError.value = '';
  const raw = inlineLimitInput.value.trim();
  if (!/^[1-9]\d*$/.test(raw)) {
    limitError.value = '请输入大于 0 的正整数作为本地计划人数上限';
    return;
  }
  const parsed = Number(raw);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    limitError.value = '本地计划人数上限数值超出有效范围';
    return;
  }

  const savedTeamId = selectedTeam.value.id;
  const savedRevision = selectedTeam.value.revision;
  const savedEpoch = dialogEpoch;
  const controller = new AbortController();
  limitController = controller;
  const isCurrentSave = () => !controller.signal.aborted && savedEpoch === dialogEpoch &&
    isActiveDialog.value && selectedTeam.value?.id === savedTeamId && selectedTeamId.value === savedTeamId;
  savingLimit.value = true;
  try {
    const res = await props.api.updateTeam(savedTeamId, {
      expected_revision: savedRevision,
      planned_member_limit: parsed,
    }, controller.signal);
    if (!isCurrentSave()) return;
    if (res.team.id !== savedTeamId) {
      throw new Error('保存响应的工作区与当前目标不一致，请刷新后重试');
    }
    selectedTeam.value = res.team;
    const idx = availableTeams.value.findIndex(t => t.id === res.team.id);
    if (idx >= 0) {
      availableTeams.value.splice(idx, 1, res.team);
    }
    emit('teamUpdated', res.team);
    emit('notify', '本地计划人数上限已更新，正在重新核算席位');
    await runPreview(savedTeamId);
  } catch (err) {
    if (isAbortError(err) || !isCurrentSave()) return;
    limitError.value =
      err instanceof TeamApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : '设置本地计划人数上限失败';
  } finally {
    if (limitController === controller) {
      limitController = null;
      savingLimit.value = false;
    }
  }
}

async function confirmJoin() {
  if (!canConfirmJoin.value || !selectedTeam.value || !preview.value) return;
  const payload = buildTargetPayload();
  if (!payload) return;
  const submittedTeamId = selectedTeam.value.id;
  const submittedEpoch = dialogEpoch;

  submitting.value = true;
  submitError.value = '';
  submitNotice.value = '';

  try {
    const res = await props.api.submitJoin(submittedTeamId, payload);
    emit('submitted', res, submittedTeamId);
    if (submittedEpoch !== dialogEpoch) return;
    receipt.value = res;
    stage.value = 'receipt';
    emit('notify', '批量加入请求已持久受理，逐项结果见回执');
    await loadReceiptPage(1);
  } catch (err) {
    if (submittedEpoch !== dialogEpoch) return;
    if (err instanceof TeamApiError) {
      if (
        err.status === 409 &&
        (err.code === 'team_revision_conflict' || err.code === 'revision_conflict')
      ) {
        submitNotice.value = '工作区状态已变更，已自动重新核算最新席位与名单，请二次确认后提交。';
        await selectAndLoadTeam(submittedTeamId);
        return;
      }
      if (err.status === 409 && err.code === 'team_limit_required') {
        submitNotice.value = '需要先配置本地计划人数上限，已重新加载席位核算。';
        await runPreview(submittedTeamId);
        return;
      }
      submitError.value = err.message || teamReasonLabel(err.code);
    } else {
      submitError.value = err instanceof Error ? err.message : '发起加入请求失败';
    }
  } finally {
    if (submittedEpoch === dialogEpoch) submitting.value = false;
  }
}

async function loadReceiptPage(nextPage: number) {
  if (!isActiveDialog.value || !receipt.value || receiptLoading.value) return;
  if (nextPage < 1 || (receiptItems.value && nextPage > receiptTotalPages.value)) return;
  const teamId = receipt.value.team_id;
  const requestId = receipt.value.id;
  if (receiptController) receiptController.abort();
  const controller = new AbortController();
  receiptController = controller;
  receiptLoading.value = true;
  receiptError.value = '';
  try {
    const res = await props.api.getJoinRequest(teamId, requestId,
      { page: nextPage, page_size: receiptItems.value?.page_size ?? 20 }, controller.signal);
    if (controller.signal.aborted || !isActiveDialog.value || receipt.value?.id !== requestId) return;
    receipt.value = res.request;
    receiptItems.value = res;
  } catch (err) {
    if (isAbortError(err) || controller.signal.aborted) return;
    receiptError.value = err instanceof Error ? err.message : '加载回执明细失败';
  } finally {
    if (receiptController === controller) {
      receiptController = null;
      receiptLoading.value = false;
    }
  }
}

useTeamPolling({
  visible: () => isActiveDialog.value && stage.value === 'receipt',
  shouldPoll: () => Boolean(receipt.value && ['preparing', 'queued', 'running', 'waiting'].includes(receipt.value.status)),
  onPoll: () => loadReceiptPage(receiptPage.value),
});

function receiptOutcomeBadge(status: JoinRequestItemDTO['acceptance_status']): { label: string; tone: BadgeTone } {
  if (status === 'pending') return { label: '待处理', tone: 'neutral' };
  if (status === 'accepted') return { label: '已受理', tone: 'success' };
  if (status === 'reused') return { label: '复用进行中', tone: 'active' };
  if (status === 'failed') return { label: '受理失败', tone: 'danger' };
  return { label: '已跳过', tone: 'warning' };
}

function receiptStatusLabel(status: JoinRequestDTO['status']): string {
  return status === 'preparing' ? '正在准备' : teamExecutionLabel(status);
}

function requestClose() {
  if (submitting.value || savingLimit.value) return;
  abortAll();
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

watch(
  () => [props.open, props.initialTeam?.id, props.target],
  () => {
    if (!props.open) {
      dialogEpoch++;
      abortAll();
      submitting.value = false;
      return;
    }
    resetState();
    if (props.visible) void initModal();
  },
  { immediate: true },
);

watch(() => props.visible, (visible) => {
  if (!visible) {
    abortAll();
    return;
  }
  if (!props.open) return;
  if (stage.value === 'receipt' && receipt.value) return;
  if (!selectedTeam.value) void initModal();
  else if (!preview.value) void runPreview(selectedTeam.value.id);
});

onBeforeUnmount(() => {
  dialogEpoch++;
  abortAll();
});
</script>

<template>
  <dialog
    ref="dialogRef"
    class="tm-dialog tm-dialog--lg"
    aria-labelledby="teamJoinDialogTitle"
    :aria-busy="submitting || savingLimit || previewLoading || receiptLoading"
    @cancel.prevent="requestClose"
    @click="onBackdropClick"
  >
    <div class="tm-dialog__head">
      <div>
        <p class="tm-dialog__kicker">
          {{ stage === 'receipt' ? 'JOIN REQUEST RECEIPT' : 'TEAM JOIN PREVIEW' }}
        </p>
        <h3 id="teamJoinDialogTitle" class="tm-dialog__title">
          {{ stage === 'receipt' ? '加入请求受理回执' : '加入 Team 预览与席位确认' }}
        </h3>
        <p class="tm-dialog__desc">
          <template v-if="selectedTeam">
            目标工作区：<strong>{{ selectedTeam.display_name || selectedTeam.name || selectedTeam.workspace_id }}</strong>
            （<span class="tm-mono">{{ selectedTeam.workspace_id }}</span>）
          </template>
          <template v-else>
            请选择目标 Team，系统将执行纯本地名单去重与席位容量核算。
          </template>
        </p>
      </div>
      <button
        type="button"
        class="tm-dialog__close"
        aria-label="关闭加入确认弹窗"
        :disabled="submitting || savingLimit"
        @click="requestClose"
      >
        ×
      </button>
    </div>

    <!-- 阶段 A：预览与席位确认 -->
    <div v-if="stage === 'preview'" class="tm-dialog__body">
      <!-- 未预选 Team 时提供选择器 -->
      <div v-if="needsTeamPicker" class="tm-field">
        <span class="tm-field__label">目标 Team 工作区</span>
        <select
          :value="selectedTeamId"
          :disabled="teamsLoading || submitting || savingLimit"
          aria-label="选择目标 Team"
          @change="onTeamDropdownChange"
        >
          <option value="">
            {{ teamsLoading ? '正在加载可用 Team…' : '请选择一个已绑定的 Team' }}
          </option>
          <option
            v-for="t in availableTeams"
            :key="t.id"
            :value="t.id"
          >
            {{ t.display_name || t.name || t.workspace_id }}（{{ t.workspace_id }} · 成员 {{ formatNullableCount(t.confirmed_member_count, '待同步') }}）
          </option>
        </select>
        <div v-if="teamsError" class="tm-banner tm-banner--danger" role="alert">
          <div class="tm-banner__copy">{{ teamsError }}</div>
          <button
            type="button"
            class="tm-btn tm-btn--sm"
            @click="target?.targetTeamId ? selectAndLoadTeam(target.targetTeamId) : loadTeamOptions()"
          >
            重试
          </button>
        </div>
      </div>

      <div v-if="previewLoading" class="tm-banner tm-banner--info" role="status">
        <div class="tm-banner__copy">正在执行本地名单分类与席位容量核算…</div>
      </div>

      <div v-if="previewError" class="tm-banner tm-banner--danger" role="alert">
        <div class="tm-banner__copy">{{ previewError }}</div>
        <button
          v-if="effectiveTeamId"
          type="button"
          class="tm-btn tm-btn--sm"
          @click="runPreview(effectiveTeamId)"
        >
          重新核算
        </button>
      </div>

      <template v-if="preview">
        <!-- 七类互斥统计，合格目标包含可复用执行。 -->
        <section class="tm-field">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap;">
            <span class="tm-field__label">
              本次选定名单拆解（去重共 {{ preview.counts.unique_count }} 个）
            </span>
            <span class="tm-field__hint">
              最近同步：{{ preview.team_last_synced_at ? formatDateTime(preview.team_last_synced_at) : '尚未同步' }}
            </span>
          </div>

          <div class="tm-preview-grid">
            <div class="tm-preview-stat is-highlight">
              <span>新加入目标</span>
              <strong>{{ preview.counts.new_count }}</strong>
            </div>
            <div class="tm-preview-stat">
              <span>已有邀请直接续接</span>
              <strong>{{ preview.counts.resume_invite_count }}</strong>
            </div>
            <div class="tm-preview-stat">
              <span>已是成员跳过</span>
              <strong>{{ preview.counts.already_member_count }}</strong>
            </div>
            <div class="tm-preview-stat">
              <span>同 Team 执行可复用</span>
              <strong>{{ preview.counts.same_team_active_count }}</strong>
            </div>
            <div class="tm-preview-stat">
              <span>已属其他Team跳过</span>
              <strong>{{ preview.counts.another_team_count }}</strong>
            </div>
            <div class="tm-preview-stat">
              <span>缺认证材料跳过</span>
              <strong>{{ preview.counts.missing_auth_count }}</strong>
            </div>
            <div class="tm-preview-stat">
              <span>账号不可用或身份变化</span>
              <strong>{{ preview.counts.unavailable_count }}</strong>
            </div>
          </div>
        </section>

        <!-- 席位与超限安全核对条 -->
        <section class="tm-seat-meter" :class="meterToneClass">
          <div class="tm-seat-meter__head">
            <span class="tm-seat-meter__title">
              席位与人数上限核对
            </span>
            <span class="tm-badge tm-badge--neutral">
              依据：{{ teamCapacityBasisLabel(preview.capacity.basis) }}
            </span>
          </div>

          <div class="tm-seat-meter__track" aria-hidden="true">
            <div
              class="tm-seat-meter__fill"
              :style="{ width: `${meterOccupiedPercent}%` }"
            />
            <div
              class="tm-seat-meter__fill--added"
              :style="{ width: `${meterAddedPercent}%` }"
            />
          </div>

          <div class="tm-seat-meter__foot" style="flex-wrap: wrap;">
            <span>
              已购席位：<strong>{{ formatNullableCount(preview.capacity.purchased_seats, '未返回', ' 席') }}</strong>
              · 本地计划上限：<strong>{{ preview.capacity.planned_member_limit !== null && preview.capacity.planned_member_limit !== undefined ? `${preview.capacity.planned_member_limit} 人` : '未设置' }}</strong>
            </span>
            <span>
              当前占用：<strong>{{ formatNullableCount(preview.capacity.occupied_count, '待同步', ' 席') }}</strong>
              · 本次新增占席：<strong>{{ formatNullableCount(preview.capacity.additional_required, '待同步', ' 席') }}</strong>
              · 提交后剩余：<strong>{{ formatNullableCount(remainingAfterSubmit, '待同步', ' 席') }}</strong>
            </span>
          </div>
        </section>

        <!-- 关键安全交互：未返回已购席位且未设本地上限时，内联补设 -->
        <div
          v-if="preview.capacity.blocking_reason_code === 'team_limit_required'"
          class="tm-banner tm-banner--warning"
          style="flex-direction: column; align-items: stretch;"
          role="alert"
        >
          <div class="tm-banner__copy">
            <strong>需先设置本地计划人数上限：</strong>
            <span>远端未返回已购席位，且当前未配置本地人数上限（含母号），无法直接发起拉人。</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <input
              v-model="inlineLimitInput"
              type="text"
              inputmode="numeric"
              placeholder="输入正整数人数上限（含母号）"
              aria-label="本地计划人数上限"
              style="flex: 1 1 200px; min-height: 32px; padding: 4px 10px; border: 1px solid var(--ui-color-border-strong); border-radius: 6px; background: var(--ui-color-surface);"
              :disabled="savingLimit"
            />
            <button
              type="button"
              class="tm-btn tm-btn--primary tm-btn--sm"
              :disabled="savingLimit"
              @click="saveInlinePlannedLimit"
            >
              {{ savingLimit ? '保存核算中…' : '设置本地计划人数上限并重新核算' }}
            </button>
          </div>
          <span v-if="limitError" style="color: var(--ui-color-danger, #b91c1c); font-size: 12px;">
            {{ limitError }}
          </span>
        </div>

        <div
          v-else-if="!preview.capacity.can_submit && preview.capacity.blocking_reason_code"
          class="tm-banner tm-banner--danger"
          role="alert"
        >
          <div class="tm-banner__copy">
            {{
              teamReasonLabel(preview.capacity.blocking_reason_code)
            }}
          </div>
        </div>

        <div v-if="needsCapacityWait" class="tm-banner tm-banner--warning" role="status">
          <div class="tm-banner__copy">
            请求受理后将等待可用席位，不会超额增购。
          </div>
        </div>

        <div v-if="preview.requires_sync" class="tm-banner tm-banner--info">
          <div class="tm-banner__copy">
            将在后台自动先执行一次工作区同步与席位预检，确认远端最新席位后再发出新邀请。
          </div>
        </div>

      </template>

      <div v-if="submitNotice" class="tm-banner tm-banner--warning" role="status">
        <div class="tm-banner__copy">{{ submitNotice }}</div>
      </div>

      <div v-if="submitError" class="tm-banner tm-banner--danger" role="alert">
        <div class="tm-banner__copy">{{ submitError }}</div>
      </div>
    </div>

    <!-- 阶段 B：加入请求回执视图 -->
    <div v-else-if="receipt" class="tm-dialog__body">
      <div class="tm-banner tm-banner--info" role="status">
        <div class="tm-banner__copy">
          加入请求（<span class="tm-mono">#{{ receipt.id }}</span>）：请求已持久受理，逐项结果见下方。实际入组结果请在邀请列表或任务中心追踪。
          <span class="tm-badge" :class="`tm-badge--${teamExecutionTone(receipt.status)}`">
            {{ receiptStatusLabel(receipt.status) }}
          </span>
        </div>
      </div>

      <div class="tm-preview-grid">
        <div class="tm-preview-stat">
          <span>待处理</span>
          <strong>{{ receipt.counts.pending_count }}</strong>
        </div>
        <div class="tm-preview-stat is-highlight">
          <span>已受理（含复用）</span>
          <strong>{{ receipt.counts.accepted_count }}</strong>
        </div>
        <div class="tm-preview-stat">
          <span>复用进行中</span>
          <strong>{{ receipt.counts.reused_count }}</strong>
        </div>
        <div class="tm-preview-stat">
          <span>跳过</span>
          <strong>{{ receipt.counts.skipped_count }}</strong>
        </div>
        <div class="tm-preview-stat">
          <span>受理失败</span>
          <strong>{{ receipt.counts.failed_count }}</strong>
        </div>
      </div>

      <button type="button" class="tm-btn tm-btn--sm" :disabled="receiptLoading" @click="loadReceiptPage(receiptPage)">
        {{ receiptLoading ? '正在刷新回执…' : '刷新回执' }}
      </button>
      <div v-if="receiptError" class="tm-banner tm-banner--danger" role="alert">
        <div class="tm-banner__copy">{{ receiptError }}</div>
      </div>

      <div class="tm-candidate-list" style="max-height: 280px;" :aria-busy="receiptLoading">
        <div
          v-if="!receiptItems?.items.length"
          style="padding: 18px; text-align: center; color: var(--ui-color-text-secondary);"
        >
          当前页暂无明细条目。
        </div>
        <div
          v-for="item in receiptItems?.items ?? []"
          :key="item.ordinal"
          class="tm-candidate-row"
        >
          <div class="tm-cell-stack" style="min-width: 0; flex: 1;">
            <div class="tm-cell-primary">
              <span>目标账号</span>
              <span class="tm-mono" style="color: var(--ui-color-text-muted);">{{ item.account_id ? `#${item.account_id}` : `目标 ${item.ordinal + 1}` }}</span>
            </div>
            <div class="tm-cell-sub">
              {{ item.message || (item.reason_code ? teamReasonLabel(item.reason_code) : '等待后台处理') }}
            </div>
          </div>

          <div style="display: flex; align-items: center; gap: 8px; flex: none;">
            <span
              class="tm-badge"
              :class="`tm-badge--${receiptOutcomeBadge(item.acceptance_status).tone}`"
            >
              {{ receiptOutcomeBadge(item.acceptance_status).label }}
            </span>
            <button
              v-if="item.task_id"
              type="button"
              class="tm-btn tm-btn--soft tm-btn--sm"
              @click="emit('openTask', item.task_id, item.run_id)"
            >
              查看任务
            </button>
          </div>
        </div>
      </div>

      <div
        v-if="receiptTotalPages > 1"
        style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;"
      >
        <button
          type="button"
          class="tm-btn tm-btn--sm"
          :disabled="receiptPage <= 1 || receiptLoading"
          @click="loadReceiptPage(receiptPage - 1)"
        >
          上一页
        </button>
        <span class="tm-field__hint tm-tabular">
          第 {{ receiptPage }} / {{ receiptTotalPages }} 页（共 {{ receiptItems?.total ?? receipt.counts.unique_count }} 条）
        </span>
        <button
          type="button"
          class="tm-btn tm-btn--sm"
          :disabled="receiptPage >= receiptTotalPages || receiptLoading"
          @click="loadReceiptPage(receiptPage + 1)"
        >
          下一页
        </button>
      </div>
    </div>

    <div class="tm-dialog__foot">
      <template v-if="stage === 'preview'">
        <span class="tm-field__hint">
          默认普通成员角色，自动接受指定工作区邀请并保留原个人空间
        </span>
        <div class="tm-dialog__foot-right">
          <button
            type="button"
            class="tm-btn"
            :disabled="submitting || savingLimit"
            @click="requestClose"
          >
            取消
          </button>
          <button
            type="button"
            class="tm-btn tm-btn--primary"
            :disabled="!canConfirmJoin"
            @click="confirmJoin"
          >
            {{ submitting ? '正在受理…' : '确认发起加入' }}
          </button>
        </div>
      </template>

      <template v-else>
        <span class="tm-field__hint">
          共请求 {{ receipt?.counts.requested_count ?? 0 }} 个目标账号
        </span>
        <div class="tm-dialog__foot-right">
          <button
            v-if="effectiveTeamId"
            type="button"
            class="tm-btn tm-btn--soft"
            @click="emit('openTeamDetail', effectiveTeamId)"
          >
            进入 Team 邀请列表追踪
          </button>
          <button
            type="button"
            class="tm-btn tm-btn--primary"
            @click="requestClose"
          >
            完成并关闭
          </button>
        </div>
      </template>
    </div>
  </dialog>
</template>
