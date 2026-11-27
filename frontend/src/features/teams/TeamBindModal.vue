<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { TeamApiError, type TeamsApi } from '../../api/teams';
import { useNativeDialog } from '../../shared/useNativeDialog';
import {
  optionalTeamDecimalId,
  parseTeamJson,
  teamDecimalId,
  type AccountTeamMembershipBadge,
  type BindingProbeDTO,
  type BindingProbeWorkspaceDTO,
  type TeamDTO,
  type TeamDecimalId,
} from './contracts';
import {
  TEAM_PROBE_STAGE_STEPS,
  formatNullableCount,
  teamReasonLabel,
  teamRoleLabel,
  teamRoleTone,
} from './statusLabels';

interface LocalAccountOption {
  id: TeamDecimalId;
  email: string;
  archived: boolean;
  account_status: string;
  team_memberships: AccountTeamMembershipBadge[];
}

const props = defineProps<{
  open: boolean;
  api: TeamsApi;
  mode: 'bind' | 'change_manager';
  team?: TeamDTO | null;
  visible: boolean;
}>();

const emit = defineEmits<{
  close: [];
  bound: [team: TeamDTO];
  managerUpdated: [team: TeamDTO];
  openExistingTeam: [teamId: string];
  notify: [message: string];
}>();

const dialogRef = ref<HTMLDialogElement>();
useNativeDialog(dialogRef, () => props.open && props.visible, () => props.visible);

const searchQuery = ref('');
const accountsLoading = ref(false);
const accountsError = ref('');
const accounts = ref<LocalAccountOption[]>([]);
const selectedAccountId = ref<TeamDecimalId | null>(null);

const probe = ref<BindingProbeDTO | null>(null);
const probeLoading = ref(false);
const probeError = ref('');
const selectedWorkspaceId = ref<string>('');
const nowMs = ref(Date.now());

const displayNameInput = ref('');
const plannedLimitInput = ref('');
const formError = ref('');
const submitting = ref(false);
const conflictExistingTeamId = ref<TeamDecimalId | null>(null);
const forceProbeExpired = ref(false);

let searchController: AbortController | null = null;
let probeController: AbortController | null = null;
let pollTimer: number | null = null;
let expiryTimer: number | null = null;
let searchDebounceTimer: number | null = null;

const isActiveDialog = computed(() => props.open && props.visible);
const isChangeManager = computed(() => props.mode === 'change_manager');

const selectedAccount = computed(
  () => accounts.value.find(acc => acc.id === selectedAccountId.value) ?? null,
);

const isProbeRunning = computed(
  () =>
    probeLoading.value ||
    probe.value?.status === 'queued' ||
    probe.value?.status === 'running',
);

const isProbeExpired = computed(() => {
  if (forceProbeExpired.value) return true;
  if (!probe.value) return false;
  if (probe.value.status === 'expired') return true;
  if (!probe.value.expires_at) return false;
  const expiresMs = Date.parse(probe.value.expires_at);
  return Number.isFinite(expiresMs) && expiresMs <= nowMs.value;
});

const selectedWorkspace = computed(
  () =>
    probe.value?.workspaces.find(ws => ws.workspace_id === selectedWorkspaceId.value) ??
    null,
);

const probeStageIndex = computed(() => {
  const current = probe.value;
  if (!current) return -1;
  if (current.status === 'success' || current.stage === 'completed') {
    return TEAM_PROBE_STAGE_STEPS.length;
  }
  const idx = TEAM_PROBE_STAGE_STEPS.findIndex(step => step.key === current.stage);
  if (idx >= 0) return idx;
  return current.status === 'queued' ? 0 : 1;
});

const canSubmit = computed(() => {
  if (submitting.value || isProbeRunning.value || isProbeExpired.value) return false;
  if (!probe.value || probe.value.status !== 'success') return false;
  const ws = selectedWorkspace.value;
  if (!ws || !ws.selectable) return false;
  if (isChangeManager.value && !props.team) return false;
  return true;
});

function clearTimers() {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
  if (expiryTimer !== null) {
    window.clearInterval(expiryTimer);
    expiryTimer = null;
  }
  if (searchDebounceTimer !== null) {
    window.clearTimeout(searchDebounceTimer);
    searchDebounceTimer = null;
  }
}

function abortProbePolling() {
  if (pollTimer !== null) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
  if (probeController) {
    probeController.abort();
    probeController = null;
  }
  probeLoading.value = false;
}

function abortSearch() {
  if (searchDebounceTimer !== null) {
    window.clearTimeout(searchDebounceTimer);
    searchDebounceTimer = null;
  }
  if (searchController) {
    searchController.abort();
    searchController = null;
  }
}

function resetState() {
  abortSearch();
  abortProbePolling();
  clearTimers();
  searchQuery.value = '';
  accountsError.value = '';
  accounts.value = [];
  selectedAccountId.value = null;
  probe.value = null;
  probeError.value = '';
  selectedWorkspaceId.value = '';
  displayNameInput.value = '';
  plannedLimitInput.value = '';
  formError.value = '';
  conflictExistingTeamId.value = null;
  forceProbeExpired.value = false;
  nowMs.value = Date.now();
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

function normalizeMembershipList(raw: unknown): AccountTeamMembershipBadge[] {
  if (!Array.isArray(raw)) return [];
  const result: AccountTeamMembershipBadge[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const rec = item as Record<string, unknown>;
    const teamId = optionalTeamDecimalId(rec.team_id);
    if (!teamId) continue;
    const rawState = String(rec.membership_state || 'joined');
    const membershipState: AccountTeamMembershipBadge['membership_state'] =
      rawState === 'invited' || rawState === 'joining' ? rawState : 'joined';
    result.push({
      team_id: teamId,
      workspace_id: String(rec.workspace_id || ''),
      workspace_name: String(rec.workspace_name || rec.name || ''),
      display_name: rec.display_name ? String(rec.display_name) : null,
      role: (String(rec.role || 'unknown') as AccountTeamMembershipBadge['role']),
      membership_state: membershipState,
    });
  }
  return result;
}

async function fetchAccounts() {
  if (!isActiveDialog.value) return;
  abortSearch();
  const controller = new AbortController();
  searchController = controller;
  accountsLoading.value = true;
  accountsError.value = '';

  try {
    const params = new URLSearchParams({
      paged: '1',
      page: '1',
      page_size: '20',
      include_facets: '0',
      archived: 'all',
    });
    const q = searchQuery.value.trim();
    if (q) params.set('q', q);

    const response = await fetch(`/api/accounts?${params.toString()}`, {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });

    if (
      response.status === 401 ||
      (response.redirected &&
        new URL(response.url, window.location.origin).pathname === '/login')
    ) {
      const next = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      window.location.assign(`/login?next=${encodeURIComponent(next)}`);
      return;
    }

    const rawText = await response.text();
    const parsed = rawText ? (parseTeamJson(rawText) as Record<string, unknown>) : null;
    if (!response.ok || !parsed || parsed.ok === false || !Array.isArray(parsed.items)) {
      const errMsg =
        (parsed && typeof parsed.error === 'string' && parsed.error) ||
        (parsed && typeof parsed.message === 'string' && parsed.message) ||
        `加载本地账号失败（HTTP ${response.status}）`;
      throw new Error(errMsg);
    }

    const mapped: LocalAccountOption[] = [];
    for (const rawItem of parsed.items) {
      if (!rawItem || typeof rawItem !== 'object') continue;
      const item = rawItem as Record<string, unknown>;
      const id = optionalTeamDecimalId(item.id);
      if (!id) continue;
      mapped.push({
        id,
        email: String(item.email || `账号 #${id}`),
        archived: Boolean(item.archived),
        account_status: String(item.account_status || '未知状态'),
        team_memberships: normalizeMembershipList(item.team_memberships),
      });
    }
    accounts.value = mapped;

    if (!selectedAccountId.value && mapped.length === 1 && !isCurrentManager(mapped[0]!)) {
      selectedAccountId.value = mapped[0]!.id;
    }
  } catch (err) {
    if (isAbortError(err)) return;
    accountsError.value = err instanceof Error ? err.message : '加载账号列表失败';
  } finally {
    if (searchController === controller) {
      searchController = null;
      accountsLoading.value = false;
    }
  }
}

function scheduleSearch() {
  if (searchDebounceTimer !== null) {
    window.clearTimeout(searchDebounceTimer);
  }
  searchDebounceTimer = window.setTimeout(() => {
    searchDebounceTimer = null;
    void fetchAccounts();
  }, 260);
}

function clearSearch() {
  searchQuery.value = '';
  void fetchAccounts();
}

function isCurrentManager(acc: LocalAccountOption): boolean {
  return (
    isChangeManager.value &&
    Boolean(props.team?.manager_account.account_id) &&
    props.team?.manager_account.account_id === acc.id
  );
}

function selectAccount(accountId: TeamDecimalId) {
  if (isProbeRunning.value || submitting.value) return;
  selectedAccountId.value = accountId;
  formError.value = '';
  conflictExistingTeamId.value = null;
}

function applySuggestedWorkspace(probeData: BindingProbeDTO) {
  const workspaces = probeData.workspaces || [];
  if (
    probeData.suggested_workspace_id &&
    workspaces.some(
      ws => ws.workspace_id === probeData.suggested_workspace_id && ws.selectable,
    )
  ) {
    selectedWorkspaceId.value = probeData.suggested_workspace_id;
    return;
  }
  if (isChangeManager.value && props.team?.workspace_id) {
    const target = workspaces.find(
      ws => ws.workspace_id === props.team?.workspace_id && ws.selectable,
    );
    if (target) {
      selectedWorkspaceId.value = target.workspace_id;
      return;
    }
  }
  const selectableList = workspaces.filter(ws => ws.selectable);
  selectedWorkspaceId.value =
    selectableList.length === 1 ? selectableList[0]!.workspace_id : '';
}

function ensureExpiryTimer() {
  if (expiryTimer !== null) return;
  expiryTimer = window.setInterval(() => {
    nowMs.value = Date.now();
  }, 5000);
}

async function pollProbeOnce(probeId: TeamDecimalId, controller: AbortController) {
  if (!isActiveDialog.value || controller.signal.aborted) return;
  try {
    const nextProbe = await props.api.getBindingProbe(probeId, controller.signal);
    if (controller.signal.aborted || !isActiveDialog.value) return;
    probe.value = nextProbe;
    nowMs.value = Date.now();

    if (nextProbe.status === 'queued' || nextProbe.status === 'running') {
      pollTimer = window.setTimeout(() => {
        pollTimer = null;
        void pollProbeOnce(probeId, controller);
      }, 1500);
      return;
    }

    probeLoading.value = false;
    if (nextProbe.status === 'success') {
      applySuggestedWorkspace(nextProbe);
      ensureExpiryTimer();
    } else if (nextProbe.status === 'expired') {
      forceProbeExpired.value = true;
    } else if (nextProbe.status === 'failed') {
      probeError.value =
        nextProbe.error?.summary ||
        teamReasonLabel(nextProbe.error?.reason_code, nextProbe.error) ||
        '工作区核验失败';
    }
  } catch (err) {
    if (isAbortError(err) || controller.signal.aborted) return;
    probeLoading.value = false;
    probeError.value =
      err instanceof TeamApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : '轮询探测状态失败';
  }
}

async function startProbe(accountIdOverride?: TeamDecimalId) {
  const targetId = accountIdOverride ?? selectedAccountId.value;
  if (!targetId || submitting.value) return;

  selectedAccountId.value = targetId;
  abortProbePolling();
  const controller = new AbortController();
  probeController = controller;

  probeLoading.value = true;
  probeError.value = '';
  formError.value = '';
  conflictExistingTeamId.value = null;
  forceProbeExpired.value = false;
  selectedWorkspaceId.value = '';
  probe.value = null;

  try {
    const created = await props.api.createBindingProbe(
      {
        manager_account_id: teamDecimalId(targetId, '管理母号 ID'),
        target_workspace_id: isChangeManager.value
          ? props.team?.workspace_id ?? null
          : null,
      },
      controller.signal,
    );
    if (controller.signal.aborted || !isActiveDialog.value) return;

    const selectedAcc = accounts.value.find(item => item.id === targetId);
    probe.value = {
      probe_id: created.probe_id,
      probe_revision: '1',
      manager_account_id: targetId,
      manager_email: selectedAcc?.email ?? '',
      target_workspace_id: isChangeManager.value
        ? props.team?.workspace_id ?? null
        : null,
      status: created.status,
      stage: 'queued',
      task_id: created.task_id,
      run_id: created.run_id,
      expires_at: null,
      suggested_workspace_id: null,
      workspaces: [],
      error: null,
    };

    await pollProbeOnce(created.probe_id, controller);
  } catch (err) {
    if (isAbortError(err) || controller.signal.aborted) return;
    probeLoading.value = false;
    probeError.value =
      err instanceof TeamApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : '发起绑定探测失败';
  }
}

function selectWorkspace(ws: BindingProbeWorkspaceDTO) {
  if (!ws.selectable || submitting.value || isProbeExpired.value) return;
  selectedWorkspaceId.value = ws.workspace_id;
  formError.value = '';
  conflictExistingTeamId.value = null;
}

function formatWorkspaceSeats(seats: number | null | undefined): string {
  if (seats === null || seats === undefined || !Number.isFinite(seats)) {
    return '未返回席位';
  }
  return `已购 ${seats} 席`;
}

function workspaceDisabledReason(ws: BindingProbeWorkspaceDTO): string {
  if (ws.disabled_reason) return ws.disabled_reason;
  if (ws.disabled_reason_code) return teamReasonLabel(ws.disabled_reason_code);
  if (!ws.is_team_workspace) return '个人空间不可绑定';
  if (!ws.can_manage) return '母号无管理权限';
  if (ws.already_bound_team_id) return '该工作区已绑定';
  return '当前工作区不可选';
}

function stepClass(index: number): Record<string, boolean> {
  const currentIdx = probeStageIndex.value;
  if (probe.value?.status === 'success') {
    return { 'is-done': true };
  }
  if (index < currentIdx) {
    return { 'is-done': true };
  }
  if (index === currentIdx && isProbeRunning.value) {
    return { 'is-current': true };
  }
  return {};
}

function parsePlannedLimit(): { ok: true; value: number | null } | { ok: false; message: string } {
  const raw = plannedLimitInput.value.trim();
  if (!raw) return { ok: true, value: null };
  if (!/^[1-9]\d*$/.test(raw)) {
    return { ok: false, message: '本地计划人数上限必须为大于 0 的整数，或留空不设上限' };
  }
  const num = Number(raw);
  if (!Number.isSafeInteger(num) || num <= 0) {
    return { ok: false, message: '本地计划人数上限数值超出有效范围' };
  }
  return { ok: true, value: num };
}

async function submit() {
  if (!canSubmit.value || !probe.value || !selectedWorkspace.value) return;
  formError.value = '';
  conflictExistingTeamId.value = null;

  if (!isChangeManager.value) {
    const trimmedName = displayNameInput.value.trim();
    if (trimmedName.length > 120) {
      formError.value = '本地显示别名不能超过 120 个字符';
      return;
    }
    const parsedLimit = parsePlannedLimit();
    if (!parsedLimit.ok) {
      formError.value = parsedLimit.message;
      return;
    }

    submitting.value = true;
    try {
      const res = await props.api.createTeam({
        manager_account_id: probe.value.manager_account_id,
        workspace_id: selectedWorkspace.value.workspace_id,
        probe_id: probe.value.probe_id,
        probe_revision: probe.value.probe_revision,
        display_name: trimmedName || null,
        planned_member_limit: parsedLimit.value,
      });
      emit('notify', '工作区绑定成功，正在后台同步成员快照');
      emit('bound', res.team);
      emit('close');
    } catch (err) {
      if (err instanceof TeamApiError) {
        if (err.code === 'team_probe_expired' || err.code === 'probe_expired') {
          forceProbeExpired.value = true;
          formError.value = '核验结果已过期，请重新探测后再提交';
          return;
        }
        if (err.code === 'team_already_bound') {
          const existingId = optionalTeamDecimalId(err.details.existing_team_id);
          conflictExistingTeamId.value = existingId;
          formError.value = err.message || '该工作区已在本地绑定，可直接打开已有 Team';
          return;
        }
        formError.value = err.message || teamReasonLabel(err.code);
      } else {
        formError.value = err instanceof Error ? err.message : '绑定工作区失败';
      }
    } finally {
      submitting.value = false;
    }
    return;
  }

  if (!props.team) return;
  submitting.value = true;
  try {
    const res = await props.api.updateTeam(props.team.team_id, {
      expected_revision: props.team.revision,
      manager_account_id: probe.value.manager_account_id,
      probe_id: probe.value.probe_id,
      probe_revision: probe.value.probe_revision,
    });
    emit('notify', '管理母号已更换');
    emit('managerUpdated', res.team);
    emit('close');
  } catch (err) {
    if (err instanceof TeamApiError) {
      if (err.code === 'team_probe_expired' || err.code === 'probe_expired') {
        forceProbeExpired.value = true;
        formError.value = '核验结果已过期，请重新探测后再提交';
        return;
      }
      formError.value = err.message || teamReasonLabel(err.code);
    } else {
      formError.value = err instanceof Error ? err.message : '更换管理母号失败';
    }
  } finally {
    submitting.value = false;
  }
}

function requestClose() {
  if (submitting.value) return;
  abortSearch();
  abortProbePolling();
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
  isActiveDialog,
  active => {
    if (active) {
      resetState();
      void fetchAccounts();
    } else {
      abortSearch();
      abortProbePolling();
      clearTimers();
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  abortSearch();
  abortProbePolling();
  clearTimers();
});
</script>

<template>
  <dialog
    ref="dialogRef"
    class="tm-dialog tm-dialog--lg"
    aria-labelledby="teamBindDialogTitle"
    :aria-busy="submitting || isProbeRunning"
    @cancel.prevent="requestClose"
    @click="onBackdropClick"
  >
    <div class="tm-dialog__head">
      <div>
        <p class="tm-dialog__kicker">
          {{ isChangeManager ? 'TEAM MANAGER HANDOVER' : 'TEAM WORKSPACE BINDING' }}
        </p>
        <h3 id="teamBindDialogTitle" class="tm-dialog__title">
          {{ isChangeManager ? '更换管理母号' : '绑定已有 Team 工作区' }}
        </h3>
        <p class="tm-dialog__desc">
          <template v-if="isChangeManager && team">
            目标工作区：<strong>{{ team.effective_name }}</strong>
            （<span class="tm-mono">{{ team.workspace_id }}</span>），仅切换执行管理的本地母号，不转移远端所有权。
          </template>
          <template v-else>
            选择具备工作区管理权限的本地账号作为母号，通过后台探测核验工作区后建立本地关联。
          </template>
        </p>
      </div>
      <button
        type="button"
        class="tm-dialog__close"
        aria-label="关闭弹窗"
        :disabled="submitting"
        @click="requestClose"
      >
        ×
      </button>
    </div>

    <div class="tm-dialog__body">
      <!-- 第 1 步：选择管理母号 -->
      <section class="tm-field">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
          <span class="tm-field__label">1. 选择管理母号（包含已归档账号）</span>
          <div class="tm-search-box" style="flex: 1 1 260px; max-width: 340px;">
            <svg class="tm-search-box__icon" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            <input
              v-model="searchQuery"
              type="search"
              placeholder="搜索账号邮箱或 #ID…"
              aria-label="搜索管理母号"
              :disabled="submitting"
              @input="scheduleSearch"
              @keydown.enter.prevent="fetchAccounts"
            />
            <button
              v-if="searchQuery"
              type="button"
              class="tm-search-box__clear"
              aria-label="清空搜索"
              @click="clearSearch"
            >
              ×
            </button>
          </div>
        </div>

        <div v-if="accountsError" class="tm-banner tm-banner--danger" role="alert">
          <div class="tm-banner__copy">{{ accountsError }}</div>
          <button type="button" class="tm-btn tm-btn--sm" @click="fetchAccounts">重试</button>
        </div>

        <div class="tm-candidate-list" style="max-height: 210px;" :aria-busy="accountsLoading">
          <div
            v-if="accountsLoading && !accounts.length"
            style="padding: 18px; text-align: center; color: var(--ui-color-text-secondary);"
          >
            正在搜索本地账号…
          </div>
          <div
            v-else-if="!accounts.length"
            style="padding: 18px; text-align: center; color: var(--ui-color-text-secondary);"
          >
            未找到匹配的本地账号，请调整搜索关键字。
          </div>
          <div
            v-for="acc in accounts"
            :key="acc.id"
            class="tm-candidate-row"
            :class="{ 'is-selected': selectedAccountId === acc.id }"
            style="cursor: pointer;"
            @click="selectAccount(acc.id)"
          >
            <div class="tm-candidate-row__left" style="min-width: 0; flex: 1;">
              <input
                type="radio"
                name="tm_bind_manager_account"
                :checked="selectedAccountId === acc.id"
                :aria-label="`选择母号 ${acc.email}`"
                @change="selectAccount(acc.id)"
              />
              <div class="tm-cell-stack" style="min-width: 0;">
                <div class="tm-cell-primary">
                  <span>{{ acc.email }}</span>
                  <span class="tm-mono" style="color: var(--ui-color-text-muted);">#{{ acc.id }}</span>
                  <span v-if="acc.archived" class="tm-badge tm-badge--neutral">已归档</span>
                  <span class="tm-badge tm-badge--neutral">{{ acc.account_status }}</span>
                  <span v-if="isCurrentManager(acc)" class="tm-badge tm-badge--active">当前母号</span>
                </div>
                <div
                  v-if="acc.team_memberships.length"
                  class="tm-cell-sub"
                  style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;"
                >
                  <span>已关联 Team：</span>
                  <span
                    v-for="m in acc.team_memberships"
                    :key="`${m.team_id}:${m.workspace_id}`"
                    class="acc-team-pill"
                  >
                    {{ m.display_name || m.workspace_name || `Team #${m.team_id}` }} · {{ teamRoleLabel(m.role) }}
                  </span>
                </div>
              </div>
            </div>
            <button
              type="button"
              class="tm-btn tm-btn--soft tm-btn--sm"
              :disabled="isProbeRunning || submitting"
              @click.stop="startProbe(acc.id)"
            >
              {{
                isProbeRunning && selectedAccountId === acc.id
                  ? '探测中…'
                  : '探测并核验工作区'
              }}
            </button>
          </div>
        </div>

        <div
          v-if="selectedAccount"
          style="display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-top: 2px;"
        >
          <span class="tm-field__hint">
            已选账号：<strong>{{ selectedAccount.email }}</strong>（#{{ selectedAccount.id }}）
          </span>
          <button
            type="button"
            class="tm-btn tm-btn--primary tm-btn--sm"
            :disabled="isProbeRunning || submitting"
            @click="startProbe()"
          >
            {{ isProbeRunning ? '正在探测工作区…' : '探测并核验工作区' }}
          </button>
        </div>
      </section>

      <!-- 第 2 步：绑定探测实时进度条 -->
      <section v-if="probe || probeLoading || probeError" class="tm-field">
        <span class="tm-field__label">2. 工作区核验进度</span>
        <div class="tm-probe-stepper" role="status" aria-live="polite">
          <div
            v-for="(step, index) in TEAM_PROBE_STAGE_STEPS"
            :key="step.key"
            class="tm-probe-step"
            :class="stepClass(index)"
          >
            <span class="tm-probe-step__dot">
              {{ stepClass(index)['is-done'] ? '✓' : index + 1 }}
            </span>
            <span>{{ step.label }}</span>
          </div>
        </div>

        <div v-if="probeError" class="tm-banner tm-banner--danger" role="alert">
          <div class="tm-banner__copy">
            <span>{{ probeError }}</span>
            <span v-if="probe?.error?.detail" class="tm-cell-sub">{{ probe.error.detail }}</span>
          </div>
          <button
            type="button"
            class="tm-btn tm-btn--sm"
            :disabled="!selectedAccountId || isProbeRunning || submitting"
            @click="startProbe()"
          >
            重新探测
          </button>
        </div>
      </section>

      <!-- 过期提示 -->
      <div
        v-if="probe && probe.status === 'success' && isProbeExpired"
        class="tm-banner tm-banner--warning"
        role="alert"
      >
        <div class="tm-banner__copy">
          <span>核验结果已过期，请重新探测后继续确认绑定。</span>
        </div>
        <button
          type="button"
          class="tm-btn tm-btn--sm"
          :disabled="!selectedAccountId || isProbeRunning || submitting"
          @click="startProbe()"
        >
          重新探测
        </button>
      </div>

      <!-- 第 3 步：单选工作区列表 -->
      <section v-if="probe && probe.status === 'success'" class="tm-field">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
          <span class="tm-field__label">3. 选择目标工作区（单选确认）</span>
          <span class="tm-field__hint">
            核验账号：{{ probe.manager_email || `#${probe.manager_account_id}` }}
          </span>
        </div>

        <div
          v-if="!probe.workspaces.length"
          class="tm-banner tm-banner--warning"
        >
          <div class="tm-banner__copy">未在该账号下发现任何工作区。</div>
        </div>

        <div v-else class="tm-workspace-list">
          <div
            v-for="ws in probe.workspaces"
            :key="ws.workspace_id"
            class="tm-workspace-option"
            :class="{
              'is-selected': selectedWorkspaceId === ws.workspace_id,
              'is-disabled': !ws.selectable || isProbeExpired,
            }"
            role="radio"
            :aria-checked="selectedWorkspaceId === ws.workspace_id"
            :aria-disabled="!ws.selectable || isProbeExpired"
            @click="selectWorkspace(ws)"
          >
            <div style="display: flex; align-items: flex-start; gap: 10px; min-width: 0; flex: 1;">
              <input
                type="radio"
                name="tm_probe_workspace"
                :checked="selectedWorkspaceId === ws.workspace_id"
                :disabled="!ws.selectable || isProbeExpired || submitting"
                style="margin-top: 3px;"
                @change="selectWorkspace(ws)"
              />
              <div class="tm-cell-stack" style="min-width: 0; flex: 1;">
                <div class="tm-cell-primary" style="flex-wrap: wrap;">
                  <span>{{ ws.workspace_name || ws.workspace_id }}</span>
                  <span class="tm-mono" style="color: var(--ui-color-text-muted);">{{ ws.workspace_id }}</span>
                  <span class="tm-plan-tag">{{ ws.plan_type || 'unknown' }}</span>
                  <span class="tm-badge" :class="`tm-badge--${teamRoleTone(ws.role)}`">
                    {{ teamRoleLabel(ws.role) }}
                  </span>
                  <span
                    class="tm-badge"
                    :class="ws.can_manage ? 'tm-badge--success' : 'tm-badge--danger'"
                  >
                    {{ ws.can_manage ? '可管理' : '无管理权限' }}
                  </span>
                </div>
                <div class="tm-cell-sub" style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                  <span>{{ formatWorkspaceSeats(ws.purchased_seats) }}</span>
                  <span>成员：{{ formatNullableCount(ws.confirmed_member_count, '待同步', ' 人') }}</span>
                  <span>待接受：{{ formatNullableCount(ws.pending_invite_count, '待同步', ' 份') }}</span>
                </div>
                <div v-if="!ws.selectable" class="tm-cell-sub is-danger">
                  不可选原因：{{ workspaceDisabledReason(ws) }}
                </div>
              </div>
            </div>

            <div v-if="ws.already_bound_team_id" style="flex: none;">
              <button
                type="button"
                class="tm-btn tm-btn--soft tm-btn--sm"
                @click.stop="emit('openExistingTeam', ws.already_bound_team_id!)"
              >
                打开已绑定工作区
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 第 4 步：仅绑定模式填写别名与人数上限 -->
      <section
        v-if="!isChangeManager && probe && probe.status === 'success' && selectedWorkspace"
        class="tm-field"
      >
        <span class="tm-field__label">4. 本地显示与席位上限设置（可选）</span>

        <div
          v-if="selectedWorkspace.purchased_seats === null"
          class="tm-banner tm-banner--warning"
        >
          <div class="tm-banner__copy">
            远端未返回已购席位数（未返回），强烈建议现在设置「本地计划人数上限」（含管理母号），否则后续拉人前必须先补设。
          </div>
        </div>

        <div class="tm-form-grid">
          <label class="tm-field">
            <span class="tm-field__label">本地显示别名（display_name）</span>
            <input
              v-model="displayNameInput"
              type="text"
              maxlength="120"
              :placeholder="selectedWorkspace.workspace_name || '留空则使用远端工作区名称'"
              :disabled="submitting"
            />
            <span class="tm-field__hint">留空将展示远端工作区名称，最多 120 字符。</span>
          </label>

          <label class="tm-field">
            <span class="tm-field__label">本地计划人数上限（planned_member_limit）</span>
            <input
              v-model="plannedLimitInput"
              type="text"
              inputmode="numeric"
              placeholder="正整数（含母号），留空不设上限"
              :disabled="submitting"
            />
            <span class="tm-field__hint">
              默认策略仅使用已购剩余席位；同时设置时取两者较小值。
            </span>
          </label>
        </div>
      </section>

      <!-- 提交错误与重复绑定提示 -->
      <div v-if="formError" class="tm-banner tm-banner--danger" role="alert">
        <div class="tm-banner__copy">{{ formError }}</div>
        <button
          v-if="conflictExistingTeamId"
          type="button"
          class="tm-btn tm-btn--soft tm-btn--sm"
          @click="emit('openExistingTeam', conflictExistingTeamId!)"
        >
          打开已绑定 Team
        </button>
      </div>
    </div>

    <div class="tm-dialog__foot">
      <span class="tm-field__hint">
        <template v-if="isChangeManager">
          仅更新本地执行管理身份，不自动退出或修改原有成员事实
        </template>
        <template v-else>
          确认绑定后将立即入队后台首次成员与邀请同步任务
        </template>
      </span>
      <div class="tm-dialog__foot-right">
        <button
          type="button"
          class="tm-btn"
          :disabled="submitting"
          @click="requestClose"
        >
          取消
        </button>
        <button
          type="button"
          class="tm-btn tm-btn--primary"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{
            submitting
              ? '提交中…'
              : isChangeManager
                ? '确认更换母号'
                : '确认绑定工作区'
          }}
        </button>
      </div>
    </div>
  </dialog>
</template>
