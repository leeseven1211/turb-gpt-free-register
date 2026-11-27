<script setup lang="ts">
import { nextTick, ref, shallowRef } from 'vue';
import type { TeamsApi } from '../../api/teams';
import TeamBindModal from './TeamBindModal.vue';
import TeamCandidatePickerModal from './TeamCandidatePickerModal.vue';
import TeamDetailView from './TeamDetailView.vue';
import TeamEditModal from './TeamEditModal.vue';
import TeamJoinModal from './TeamJoinModal.vue';
import TeamsListView from './TeamsListView.vue';
import {
  teamDecimalId,
  type AccountsJoinRequestPayload,
  type JoinRequestDTO,
  type TeamDTO,
  type TeamDecimalId,
  type TeamsHostCallbacks,
  type TeamsNavigationState,
} from './contracts';
import './teams.css';

const props = withDefaults(
  defineProps<{
    api: TeamsApi;
    callbacks: TeamsHostCallbacks;
    initialNavigation?: Partial<TeamsNavigationState>;
    initialVisible?: boolean;
  }>(),
  {
    initialVisible: true,
  },
);

function normalizeState(next?: Partial<TeamsNavigationState>): TeamsNavigationState {
  if (next?.view === 'detail' && next.team_id) {
    return {
      tab: 'teams',
      view: 'detail',
      team_id: teamDecimalId(next.team_id, 'Team ID'),
      section: next.section === 'invitations' ? 'invitations' : 'members',
    };
  }
  return {
    tab: 'teams',
    view: 'list',
  };
}

const initialState = normalizeState(props.initialNavigation);

const visible = ref(props.initialVisible);
const view = ref<'list' | 'detail'>(initialState.view);
const activeTeamId = ref<TeamDecimalId | null>(initialState.team_id ?? null);
const activeSection = ref<'members' | 'invitations'>(initialState.section ?? 'members');
const joinRequestFilterId = ref('');
const savedScrollY = ref(0);
const activeDetailTeam = shallowRef<TeamDTO | null>(null);

const listRef = ref<InstanceType<typeof TeamsListView> | null>(null);
const detailRef = ref<InstanceType<typeof TeamDetailView> | null>(null);

// 4 个并发弹窗状态
const bindModalOpen = ref(false);
const bindModalMode = ref<'bind' | 'change_manager'>('bind');
const bindTargetTeam = shallowRef<TeamDTO | null>(null);

const editModalOpen = ref(false);
const editingTeam = shallowRef<TeamDTO | null>(null);

const candidateModalOpen = ref(false);
const candidateTeam = shallowRef<TeamDTO | null>(null);

const joinModalOpen = ref(false);
const joinInitialTeam = shallowRef<TeamDTO | null>(null);
const joinTarget = shallowRef<AccountsJoinRequestPayload | null>(null);

function navigationState(): TeamsNavigationState {
  if (view.value === 'detail' && activeTeamId.value) {
    return {
      tab: 'teams',
      view: 'detail',
      team_id: activeTeamId.value,
      section: activeSection.value,
    };
  }
  return {
    tab: 'teams',
    view: 'list',
  };
}

function navigate(
  next: Partial<TeamsNavigationState>,
  mode: 'push' | 'replace' = 'push',
  options: { emit?: boolean } = {},
): void {
  const normalized = normalizeState(next);
  const wasList = view.value === 'list';

  if (normalized.view === 'detail' && normalized.team_id) {
    if (wasList && typeof window !== 'undefined') {
      savedScrollY.value = window.scrollY || 0;
    }
    view.value = 'detail';
    activeTeamId.value = normalized.team_id;
    activeSection.value = normalized.section ?? 'members';
    if (typeof window !== 'undefined' && wasList) {
      void nextTick(() => window.scrollTo({ top: 0 }));
    }
  } else {
    view.value = 'list';
    activeTeamId.value = null;
    activeSection.value = 'members';
    joinRequestFilterId.value = '';
    activeDetailTeam.value = null;
    void nextTick(() => {
      if (typeof window !== 'undefined') {
        window.scrollTo({ top: savedScrollY.value });
      }
      void listRef.value?.refresh({ silent: true });
    });
  }

  if (options.emit !== false) {
    props.callbacks.onNavigation(navigationState(), mode);
  }
}

function handleOpenDetail(teamId: TeamDecimalId, section: 'members' | 'invitations' = 'members'): void {
  joinRequestFilterId.value = '';
  navigate({ view: 'detail', team_id: teamId, section }, 'push');
}

function handleBackToList(): void {
  navigate({ view: 'list' }, 'push');
}

function handleUpdateSection(section: 'members' | 'invitations'): void {
  if (activeSection.value === section) return;
  activeSection.value = section;
  props.callbacks.onNavigation(navigationState(), 'replace');
}

function openBindModal(): void {
  bindModalMode.value = 'bind';
  bindTargetTeam.value = null;
  bindModalOpen.value = true;
}

function handleOpenChangeManager(team: TeamDTO): void {
  bindModalMode.value = 'change_manager';
  bindTargetTeam.value = team;
  bindModalOpen.value = true;
}

function handleOpenEdit(team: TeamDTO): void {
  editingTeam.value = team;
  editModalOpen.value = true;
}

function handleOpenJoinFromTeam(team: TeamDTO): void {
  candidateTeam.value = team;
  candidateModalOpen.value = true;
}

function openJoinFromAccounts(payload: AccountsJoinRequestPayload): void {
  joinInitialTeam.value =
    payload.targetTeamId && activeDetailTeam.value?.team_id === payload.targetTeamId
      ? activeDetailTeam.value
      : null;
  joinTarget.value = payload;
  joinModalOpen.value = true;
}

function handleConfirmCandidates(payload: {
  accountIds: TeamDecimalId[];
  expectedEmails: Record<string, string>;
}): void {
  const target = candidateTeam.value;
  candidateModalOpen.value = false;
  if (!target) return;
  joinInitialTeam.value = target;
  joinTarget.value = {
    mode: 'explicit',
    accountIds: payload.accountIds,
    expectedEmails: payload.expectedEmails,
    targetTeamId: target.team_id,
  };
  joinModalOpen.value = true;
}

function handleTeamBound(team: TeamDTO): void {
  bindModalOpen.value = false;
  void listRef.value?.refresh({ silent: true });
  navigate({ view: 'detail', team_id: team.team_id, section: 'members' }, 'push');
}

function handleManagerUpdated(team: TeamDTO): void {
  bindModalOpen.value = false;
  handleTeamUpdated(team);
}

function handleOpenExistingTeam(teamId: TeamDecimalId): void {
  bindModalOpen.value = false;
  navigate({ view: 'detail', team_id: teamId, section: 'members' }, 'push');
}

function handleTeamUpdated(team: TeamDTO): void {
  editModalOpen.value = false;
  if (editingTeam.value?.team_id === team.team_id) {
    editingTeam.value = team;
  }
  if (activeDetailTeam.value?.team_id === team.team_id) {
    activeDetailTeam.value = team;
  }
  if (joinInitialTeam.value?.team_id === team.team_id) {
    joinInitialTeam.value = team;
  }
  if (candidateTeam.value?.team_id === team.team_id) {
    candidateTeam.value = team;
  }
  if (view.value === 'detail' && activeTeamId.value === team.team_id) {
    detailRef.value?.updateTeamSnapshot(team);
  }
  void listRef.value?.refresh({ silent: true });
}

function handleEditConflict(): void {
  if (view.value === 'detail' && activeTeamId.value) {
    void detailRef.value?.refresh({ silent: true });
  }
  void listRef.value?.refresh({ silent: true });
}

function handleJoinSubmitted(_receipt: JoinRequestDTO, teamId: TeamDecimalId): void {
  if (view.value === 'detail' && activeTeamId.value === teamId) {
    detailRef.value?.refreshAll();
  }
  void listRef.value?.refresh({ silent: true });
}

function closeDialogs(): void {
  bindModalOpen.value = false;
  editModalOpen.value = false;
  candidateModalOpen.value = false;
  joinModalOpen.value = false;
}

function setVisible(nextVisible: boolean): void {
  visible.value = nextVisible;
}

async function refresh(): Promise<void> {
  if (view.value === 'detail' && activeTeamId.value) {
    detailRef.value?.refreshAll();
    return;
  }
  await listRef.value?.refresh();
}

defineExpose({
  setVisible,
  navigate,
  navigationState,
  openJoinFromAccounts,
  openBindModal,
  closeDialogs,
  refresh,
});
</script>

<template>
  <div class="tm-page-shell">
    <TeamsListView
      v-show="view === 'list'"
      ref="listRef"
      :api="api"
      :visible="visible && view === 'list'"
      :callbacks="callbacks"
      @open-detail="handleOpenDetail"
      @open-bind="openBindModal"
      @open-edit="handleOpenEdit"
      @open-change-manager="handleOpenChangeManager"
      @open-join="handleOpenJoinFromTeam"
    />

    <TeamDetailView
      v-if="view === 'detail' && activeTeamId"
      ref="detailRef"
      :api="api"
      :team-id="activeTeamId"
      :section="activeSection"
      :visible="visible && view === 'detail'"
      :callbacks="callbacks"
      :join-request-id="joinRequestFilterId"
      @back="handleBackToList"
      @update:section="handleUpdateSection"
      @open-edit="handleOpenEdit"
      @open-change-manager="handleOpenChangeManager"
      @open-join="handleOpenJoinFromTeam"
      @team-loaded="activeDetailTeam = $event"
      @clear-join-request="joinRequestFilterId = ''"
    />

    <TeamBindModal
      :open="bindModalOpen"
      :api="api"
      :mode="bindModalMode"
      :team="bindTargetTeam"
      :visible="visible"
      @close="bindModalOpen = false"
      @bound="handleTeamBound"
      @manager-updated="handleManagerUpdated"
      @open-existing-team="handleOpenExistingTeam"
      @notify="callbacks.notify"
    />

    <TeamEditModal
      :open="editModalOpen"
      :api="api"
      :team="editingTeam"
      :visible="visible"
      @close="editModalOpen = false"
      @updated="handleTeamUpdated"
      @conflict="handleEditConflict"
      @notify="callbacks.notify"
    />

    <TeamCandidatePickerModal
      :open="candidateModalOpen"
      :api="api"
      :team="candidateTeam"
      :visible="visible"
      @close="candidateModalOpen = false"
      @confirm-candidates="handleConfirmCandidates"
      @open-advanced-in-accounts="(team) => { candidateModalOpen = false; callbacks.openAccountsCandidateMode(team); }"
      @notify="callbacks.notify"
    />

    <TeamJoinModal
      :open="joinModalOpen"
      :api="api"
      :initial-team="joinInitialTeam"
      :target="joinTarget"
      :visible="visible"
      :format-date-time="callbacks.formatDateTime"
      @close="joinModalOpen = false"
      @submitted="handleJoinSubmitted"
      @open-task="(taskId, runId) => callbacks.openTask(taskId, runId)"
      @open-team-detail="(teamId) => { joinModalOpen = false; navigate({ view: 'detail', team_id: teamId, section: 'invitations' }, 'push'); }"
      @team-updated="handleTeamUpdated"
      @notify="callbacks.notify"
    />
  </div>
</template>
