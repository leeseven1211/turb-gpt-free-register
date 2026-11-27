<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import type { TeamsApi } from '../../api/teams';
import TeamInvitationsTab from './TeamInvitationsTab.vue';
import TeamMembersTab from './TeamMembersTab.vue';
import type {
  TeamDTO,
  TeamDecimalId,
  TeamDetailResponse,
  TeamsHostCallbacks,
} from './contracts';
import {
  teamDisplayName,
  teamEffectiveLimit,
  formatNullableCount,
  formatSeatLimitDisplay,
  isTeamActivelyRunning,
  teamReasonLabel,
  teamRoleLabel,
  teamRoleTone,
  teamSyncLabel,
  teamSyncTone,
  workspaceAvatarHue,
  workspaceInitials,
  type BadgeTone,
} from './statusLabels';
import { useTeamPolling } from './useTeamPolling';

const props = defineProps<{
  api: TeamsApi;
  teamId: TeamDecimalId;
  section: 'members' | 'invitations';
  visible: boolean;
  callbacks: TeamsHostCallbacks;
  joinRequestId?: string;
}>();

const emit = defineEmits<{
  back: [];
  'update:section': [section: 'members' | 'invitations'];
  'open-edit': [team: TeamDTO];
  'open-change-manager': [team: TeamDTO];
  'open-join': [team: TeamDTO];
  'team-loaded': [team: TeamDTO];
  'clear-join-request': [];
}>();

const detail = shallowRef<TeamDetailResponse | null>(null);
const loading = ref(false);
const error = ref('');
const syncing = ref(false);
const reverifying = ref(false);
const rootRef = ref<HTMLElement | null>(null);
const membersTabRef = ref<InstanceType<typeof TeamMembersTab> | null>(null);
const invitationsTabRef = ref<InstanceType<typeof TeamInvitationsTab> | null>(null);

let activeController: AbortController | null = null;
let requestSeq = 0;

const team = computed(() => detail.value?.team ?? null);
const actions = computed(() => detail.value?.actions ?? null);
const permissionVerifiedAt = computed(() => detail.value?.permission_verified_at ?? null);

function badgeClass(tone: BadgeTone): string {
  return `tm-badge--${tone}`;
}

const showPermissionBanner = computed(() => {
  if (!team.value || !actions.value) return false;
  const code = actions.value.join.reason_code;
  return code === 'team_permission_denied' || code === 'team_auth_required';
});

const permissionBannerMessage = computed(() => {
  if (actions.value?.join.reason_code) return teamReasonLabel(actions.value.join.reason_code);
  return '当前管理母号缺少管理权限或登录态已失效，暂不可执行邀请操作。';
});

const joinButtonDisabled = computed(() => {
  const joinAction = actions.value?.join;
  if (!joinAction) return true;
  if (joinAction.enabled) return false;
  return joinAction.reason_code !== 'team_limit_required';
});

const joinButtonTitle = computed(() => {
  const joinAction = actions.value?.join;
  if (!joinAction) return '正在读取工作区操作状态';
  if (joinAction.enabled) return '从现有账号选择成员并自动邀请入组';
  if (joinAction.reason_code === 'team_limit_required') {
    return '当前未返回已购席位，点击可先配置本地上限或选人并设置上限';
  }
  return teamReasonLabel(joinAction.reason_code);
});

const syncDisabled = computed(() => {
  if (syncing.value || !team.value) return true;
  if (team.value.last_sync_status === 'queued' || team.value.last_sync_status === 'running') return true;
  return actions.value ? !actions.value.sync.enabled : false;
});

const seatDisplay = computed(() => (team.value ? formatSeatLimitDisplay(team.value) : null));
function closeMenus(): void {
  const root = rootRef.value;
  if (!root) return;
  root.querySelectorAll<HTMLDetailsElement>('details.tm-inline-menu[open]').forEach(el => {
    el.open = false;
  });
}

function handleDocumentClick(event: MouseEvent): void {
  const target = event.target instanceof Element ? event.target : null;
  if (!target?.closest('details.tm-inline-menu')) {
    closeMenus();
  }
}

async function fetchDetail(options: { silent?: boolean } = {}): Promise<void> {
  if (!props.visible) return;
  if (!props.teamId) return;
  activeController?.abort();
  const controller = new AbortController();
  activeController = controller;
  const seq = ++requestSeq;

  if (!options.silent) {
    loading.value = true;
  }
  error.value = '';

  try {
    const res = await props.api.detail(props.teamId, controller.signal);
    if (seq !== requestSeq) return;
    detail.value = res;
    emit('team-loaded', res.team);
  } catch (err) {
    if (controller.signal.aborted || seq !== requestSeq) return;
    const message = err instanceof Error ? err.message : '加载工作区详情失败';
    if (!options.silent || !detail.value) {
      error.value = message;
    }
  } finally {
    if (activeController === controller) {
      activeController = null;
    }
    if (seq === requestSeq) {
      loading.value = false;
    }
  }
}

async function handleSync(): Promise<void> {
  if (!team.value || syncDisabled.value) return;
  syncing.value = true;
  try {
    const res = await props.api.syncTeam(team.value.id);
    props.callbacks.notify(res.reused ? '当前已有进行中的同步任务，正在追踪进度' : '已启动工作区同步任务');
    await fetchDetail({ silent: true });
  } catch (err) {
    props.callbacks.notify(err instanceof Error ? err.message : '同步任务提交失败');
  } finally {
    syncing.value = false;
  }
}

async function handleReverify(): Promise<void> {
  if (!team.value || reverifying.value) return;
  closeMenus();
  reverifying.value = true;
  try {
    const res = await props.api.reverifyTeam(team.value.id);
    props.callbacks.notify('已提交管理权限重新核验任务');
    if (res.task_id) {
      await fetchDetail({ silent: true });
    }
  } catch (err) {
    props.callbacks.notify(err instanceof Error ? err.message : '重新核验权限提交失败');
  } finally {
    reverifying.value = false;
  }
}

function handleOpenTasks(): void {
  if (!team.value) return;
  closeMenus();
  props.callbacks.openTasksForTeam(team.value.id, teamDisplayName(team.value));
}

function handleOpenEdit(): void {
  if (!team.value) return;
  closeMenus();
  emit('open-edit', team.value);
}

function handleOpenChangeManager(): void {
  if (!team.value) return;
  closeMenus();
  emit('open-change-manager', team.value);
}

function refreshAll(): void {
  void fetchDetail({ silent: false });
  if (props.section === 'members') {
    membersTabRef.value?.refresh();
  } else {
    invitationsTabRef.value?.refresh();
  }
}

useTeamPolling({
  visible: () => props.visible,
  shouldPoll: () => isTeamActivelyRunning(team.value),
  onPoll: async () => {
    await fetchDetail({ silent: true });
    if (props.section === 'members') {
      await membersTabRef.value?.refresh();
    }
  },
  intervalMs: 3000,
});

watch(
  () => props.teamId,
  () => {
    detail.value = null;
    error.value = '';
    void fetchDetail();
  },
  { immediate: true },
);

onMounted(() => {
  document.addEventListener('click', handleDocumentClick);
});

watch(() => props.visible, active => {
  if (active) {
    void fetchDetail();
  } else {
    activeController?.abort();
    activeController = null;
    requestSeq += 1;
    loading.value = false;
  }
});

onBeforeUnmount(() => {
  activeController?.abort();
  document.removeEventListener('click', handleDocumentClick);
});

defineExpose({
  refresh: (options?: { silent?: boolean }) => fetchDetail(options),
  refreshAll,
  updateTeamSnapshot: (nextTeam: TeamDTO) => {
    if (detail.value && detail.value.team.id === nextTeam.id) {
      detail.value = { ...detail.value, team: nextTeam };
    }
    void fetchDetail({ silent: true });
  },
});
</script>

<template>
  <div ref="rootRef" class="tm-root">
    <!-- 顶部返回条 -->
    <nav class="tm-detail-nav" aria-label="Team 详情导航">
      <button type="button" class="tm-back-btn" @click="emit('back')">
        ← 返回工作区列表
      </button>
      <button
        type="button"
        class="tm-btn tm-btn--ghost tm-btn--sm"
        :disabled="loading"
        @click="refreshAll"
      >
        {{ loading ? '刷新中…' : '刷新详情' }}
      </button>
    </nav>

    <!-- 加载失败整页兜底 -->
    <div v-if="error && !team" class="tm-banner tm-banner--danger" role="alert">
      <div class="tm-banner__copy">
        <strong>加载工作区详情失败：</strong>
        <span>{{ error }}</span>
      </div>
      <div class="tm-row-actions">
        <button type="button" class="tm-btn tm-btn--sm" @click="void fetchDetail()">重试</button>
      </div>
    </div>

    <!-- 同步失败但保留上次成功快照横幅 -->
    <div v-if="team && team.last_sync_status === 'failed'" class="tm-banner tm-banner--warning" role="alert">
      <div class="tm-banner__copy">
        <strong>最近一次同步失败：</strong>
        <span>
          同步详情请查看相关任务。
          以下展示上次成功同步快照（{{ team.last_synced_at ? callbacks.formatDateTime(team.last_synced_at) : '暂无成功快照' }}）。
        </span>
      </div>
      <div class="tm-row-actions">
        <button
          type="button"
          class="tm-btn tm-btn--sm"
          :disabled="syncDisabled"
          @click="void handleSync()"
        >
          立即重新同步
        </button>

      </div>
    </div>

    <!-- 权限或登录态失效横幅 -->
    <div v-if="team && showPermissionBanner" class="tm-banner tm-banner--danger" role="alert">
      <div class="tm-banner__copy">
        <strong>管理权限异常：</strong>
        <span>{{ permissionBannerMessage }}</span>
      </div>
      <div class="tm-row-actions">
        <button
          type="button"
          class="tm-btn tm-btn--sm"
          :disabled="reverifying || (actions ? !actions.reverify.enabled : false)"
          @click="void handleReverify()"
        >
          {{ reverifying ? '核验提交中…' : '重新核验权限' }}
        </button>
        <button
          type="button"
          class="tm-btn tm-btn--sm tm-btn--danger"
          @click="handleOpenChangeManager"
        >
          更换管理母号
        </button>
      </div>
    </div>

    <!-- 头部工作区卡片 -->
    <section v-if="team" class="tm-hero-card" aria-label="工作区详情摘要">
      <div class="tm-hero-top">
        <div class="tm-hero-title-group">
          <div
            class="tm-workspace-avatar tm-workspace-avatar--lg"
            :style="{ '--tm-hue': String(workspaceAvatarHue(team.workspace_id)) }"
            aria-hidden="true"
          >
            {{ workspaceInitials(teamDisplayName(team)) }}
          </div>

          <div class="tm-hero-heading">
            <div class="tm-hero-name-row">
              <h2>{{ teamDisplayName(team) }}</h2>

              <span
                v-if="team.display_name && team.name && team.display_name !== team.name"
                class="tm-cell-sub"
              >
                原名：{{ team.name }}
              </span>
              <button
                type="button"
                class="tm-btn tm-btn--ghost tm-btn--sm"
                title="编辑工作区备注别名与本地人数上限"
                @click="handleOpenEdit"
              >
                编辑别名与上限
              </button>
            </div>

            <div class="tm-hero-meta-row">
              <span class="tm-mono">{{ team.workspace_id }}</span>
              <span>·</span>
              <span>
                管理母号：
                <button
                  v-if="team.manager_account.id"
                  type="button"
                  class="tm-link-btn"
                  @click="callbacks.openAccountDetail(team.manager_account.id)"
                >
                  {{ team.manager_account.email || `#${team.manager_account.id}` }}
                </button>
                <span v-else>{{ team.manager_account.email || '—' }}</span>
              </span>
              <span class="tm-badge" :class="badgeClass(teamRoleTone(team.role))">
                {{ teamRoleLabel(team.role) }}
              </span>
              <span v-if="team.manager_account.archived" class="tm-badge tm-badge--neutral">已归档</span>
              <span>·</span>
              <span>
                权限核验：{{ permissionVerifiedAt ? callbacks.formatDateTime(permissionVerifiedAt) : '待核验' }}
              </span>
            </div>
          </div>
        </div>

        <div class="tm-hero-actions">
          <button
            type="button"
            class="tm-btn tm-btn--primary"
            :disabled="joinButtonDisabled"
            :title="joinButtonTitle"
            @click="emit('open-join', team)"
          >
            加入账号
          </button>
          <button
            type="button"
            class="tm-btn"
            :disabled="syncDisabled"
            title="同步工作区成员、邀请与席位"
            @click="void handleSync()"
          >
            {{ syncing || team.last_sync_status === 'queued' || team.last_sync_status === 'running' ? '同步中…' : '同步' }}
          </button>
          <details class="tm-inline-menu">
            <summary aria-label="工作区更多操作">···</summary>
            <div class="tm-inline-menu__panel">
              <button type="button" @click="handleOpenTasks">查看相关任务</button>
              <button type="button" @click="handleOpenEdit">设置别名与人数上限</button>
              <button type="button" @click="handleOpenChangeManager">更换管理母号</button>
              <button
                type="button"
                :disabled="reverifying || (actions ? !actions.reverify.enabled : false)"
                @click="void handleReverify()"
              >
                {{ reverifying ? '权限核验提交中…' : '重新核验权限' }}
              </button>
            </div>
          </details>
        </div>
      </div>

      <!-- 下半部分：4 个独立非相加指标砖块 + 右侧席位容量安全条 -->
      <div class="tm-facts-grid">
        <div class="tm-fact-tile">
          <div class="tm-fact-tile__label">
            <span>已确认成员</span>
          </div>
          <div class="tm-fact-tile__value" :class="{ 'is-null': team.confirmed_member_count === null }">
            {{ formatNullableCount(team.confirmed_member_count, '待同步') }}
          </div>
          <div class="tm-fact-tile__sub">远端已确认（含母号）</div>
        </div>

        <div class="tm-fact-tile">
          <div class="tm-fact-tile__label">
            <span>待接受邀请</span>
          </div>
          <div class="tm-fact-tile__value" :class="{ 'is-null': team.pending_invite_count === null }">
            {{ formatNullableCount(team.pending_invite_count, '待同步') }}
          </div>
          <div class="tm-fact-tile__sub">远端有效待接受</div>
        </div>

        <div class="tm-fact-tile">
          <div class="tm-fact-tile__label">
            <span>本系统处理中</span>
          </div>
          <div class="tm-fact-tile__value">
            {{ formatNullableCount(team.processing_count, '—') }}
          </div>
          <div class="tm-fact-tile__sub">独立计数，勿直接相加</div>
        </div>

        <div class="tm-fact-tile">
          <div class="tm-fact-tile__label">
            <span>同步状态</span>
          </div>
          <div class="tm-fact-tile__value">
            <span class="tm-badge" :class="badgeClass(teamSyncTone(team.last_sync_status))">
              <span
                v-if="team.last_sync_status === 'queued' || team.last_sync_status === 'running'"
                class="tm-badge__dot"
              ></span>
              {{ teamSyncLabel(team.last_sync_status) }}
            </span>
          </div>
          <div class="tm-fact-tile__sub">
            {{ team.last_synced_at ? callbacks.formatDateTime(team.last_synced_at) : '待同步' }}
          </div>
        </div>

        <div class="tm-seat-meter">
          <div class="tm-seat-meter__head">
            <span class="tm-seat-meter__title">席位与本地上限</span>
            <span v-if="seatDisplay" class="tm-badge" :class="badgeClass(seatDisplay.tone)">
              加入前核算容量
            </span>
          </div>

          <div class="tm-seat-meter__foot">
            <span>
              已占待预检 /
              有效上限 {{ formatNullableCount(teamEffectiveLimit(team), '未设置') }}
            </span>
            <span>
              可用余量待预检
            </span>
          </div>
          <div class="tm-seat-meter__foot">
            <span>已购 {{ formatNullableCount(team.purchased_seats, '未返回', ' 席') }}</span>
            <span>本地上限 {{ formatNullableCount(team.planned_member_limit, '未设置', ' 人') }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 加载占位 -->
    <section v-else-if="loading" class="tm-hero-card" aria-busy="true">
      <div class="ui-table-state" style="min-height: 120px;">
        <span class="ui-spinner" aria-hidden="true"></span>
        <strong>正在加载工作区详情…</strong>
      </div>
    </section>

    <!-- 分段页签栏 -->
    <div class="tm-tabs-bar" role="tablist" aria-label="工作区详情页签">
      <div class="tm-tabs">
        <button
          type="button"
          role="tab"
          class="tm-tab-btn"
          :class="{ 'is-active': section === 'members' }"
          :aria-selected="section === 'members'"
          @click="emit('update:section', 'members')"
        >
          <span>成员</span>
          <span class="tm-tab-count">
            {{ team ? formatNullableCount(team.confirmed_member_count, '待同步') : '—' }}
          </span>
        </button>

        <button
          type="button"
          role="tab"
          class="tm-tab-btn"
          :class="{ 'is-active': section === 'invitations' }"
          :aria-selected="section === 'invitations'"
          @click="emit('update:section', 'invitations')"
        >
          <span>邀请</span>
          <span class="tm-tab-count">
            <template v-if="team">
              {{
                (team.processing_count ?? 0) > 0
                  ? `${formatNullableCount(team.pending_invite_count, '待同步')} · 处理中 ${team.processing_count}`
                  : formatNullableCount(team.pending_invite_count, '待同步')
              }}
            </template>
            <template v-else>—</template>
          </span>
        </button>
      </div>
    </div>

    <!-- 页签内容 -->
    <TeamMembersTab
      v-if="section === 'members'"
      ref="membersTabRef"
      :api="api"
      :team-id="teamId"
      :visible="visible && section === 'members'"
      :callbacks="callbacks"
    />

    <TeamInvitationsTab
      v-else
      ref="invitationsTabRef"
      :api="api"
      :team-id="teamId"
      :visible="visible && section === 'invitations'"
      :callbacks="callbacks"
      :join-request-id="joinRequestId"
      @refresh-team="void fetchDetail({ silent: true })"
      @clear-join-request="emit('clear-join-request')"
    />
  </div>
</template>
