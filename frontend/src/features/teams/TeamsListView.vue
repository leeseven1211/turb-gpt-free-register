<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import type { TeamsApi } from '../../api/teams';
import ColumnResizer from '../../components/ColumnResizer.vue';
import FilterPopover from '../../components/FilterPopover.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListPagination from '../../components/ListPagination.vue';
import ListToolbar from '../../components/ListToolbar.vue';
import TableState from '../../components/TableState.vue';
import { useColumnWidths } from '../../shared/useColumnWidths';
import type {
  TeamDTO,
  TeamDecimalId,
  TeamFacets,
  TeamListQuery,
  TeamListSummary,
  TeamsHostCallbacks,
} from './contracts';
import {
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
  visible: boolean;
  callbacks: TeamsHostCallbacks;
}>();

const emit = defineEmits<{
  'open-detail': [teamId: TeamDecimalId, section?: 'members' | 'invitations'];
  'open-bind': [];
  'open-edit': [team: TeamDTO];
  'open-change-manager': [team: TeamDTO];
  'open-join': [team: TeamDTO];
}>();

const ROLE_OPTIONS = [
  { value: 'owner', label: '所有者' },
  { value: 'admin', label: '管理员' },
  { value: 'member', label: '成员' },
  { value: 'unknown', label: '待核验' },
] as const;

const SYNC_STATUS_OPTIONS = [
  { value: 'never', label: '未同步' },
  { value: 'queued', label: '排队同步' },
  { value: 'running', label: '同步中' },
  { value: 'success', label: '已同步' },
  { value: 'failed', label: '同步失败' },
] as const;

const query = reactive<{
  page: number;
  page_size: number;
  q: string;
  role: string;
  last_sync_status: string;
}>({
  page: 1,
  page_size: 20,
  q: '',
  role: '',
  last_sync_status: '',
});

const searchDraft = ref('');
const openFilter = ref<string | null>(null);
const loading = ref(false);
const bulkSyncing = ref(false);
const error = ref('');
const items = ref<TeamDTO[]>([]);
const total = ref(0);
const facets = ref<TeamFacets>({});
const summary = ref<TeamListSummary | null>(null);
const selectedIds = ref<Set<TeamDecimalId>>(new Set());
const syncingIds = ref<Set<TeamDecimalId>>(new Set());
const listRootRef = ref<HTMLElement | null>(null);

const { widths, total: tableWidth, resize, resizeWithKeyboard } = useColumnWidths({
  defaults: [36, 194, 174, 72, 72, 62, 144, 152, 200],
  storageKey: 'turb_teams_list_column_widths_v2',
  min: 36,
  max: 640,
});

let searchTimer: ReturnType<typeof setTimeout> | undefined;
let activeController: AbortController | null = null;
let requestSeq = 0;

function badgeClass(tone: BadgeTone): string {
  return `tm-badge--${tone}`;
}

function facetCount(field: string, value: string): number | null {
  const list = facets.value[field];
  if (!list) return null;
  const hit = list.find(item => item.value === value);
  return hit ? hit.count : null;
}

const pageSelected = computed(() => items.value.length > 0 && items.value.every(row => selectedIds.value.has(row.team_id)));
const pageIndeterminate = computed(() => !pageSelected.value && items.value.some(row => selectedIds.value.has(row.team_id)));

function toggleSelectAllPage(checked: boolean): void {
  const next = new Set(selectedIds.value);
  for (const row of items.value) {
    if (checked) next.add(row.team_id);
    else next.delete(row.team_id);
  }
  selectedIds.value = next;
}

function toggleSelectRow(teamId: TeamDecimalId, checked: boolean): void {
  const next = new Set(selectedIds.value);
  if (checked) next.add(teamId);
  else next.delete(teamId);
  selectedIds.value = next;
}

function clearSelection(): void {
  selectedIds.value = new Set();
}

const activeFilterChips = computed(() => {
  const chips: Array<{ key: string; label: string; removeLabel: string }> = [];
  if (query.q) {
    chips.push({ key: 'q', label: `关键词：${query.q}`, removeLabel: '清除关键词筛选' });
  }
  if (query.role) {
    chips.push({ key: 'role', label: `母号角色：${teamRoleLabel(query.role)}`, removeLabel: '清除母号角色筛选' });
  }
  if (query.last_sync_status) {
    chips.push({
      key: 'last_sync_status',
      label: `同步状态：${teamSyncLabel(query.last_sync_status)}`,
      removeLabel: '清除同步状态筛选',
    });
  }
  return chips;
});

const isFiltered = computed(() => activeFilterChips.value.length > 0);

function removeFilter(key: string): void {
  if (key === 'q') {
    clearTimeout(searchTimer);
    searchDraft.value = '';
    query.q = '';
  } else if (key === 'role') {
    query.role = '';
  } else if (key === 'last_sync_status') {
    query.last_sync_status = '';
  }
  query.page = 1;
  void fetchList();
}

function clearAllFilters(): void {
  clearTimeout(searchTimer);
  searchDraft.value = '';
  query.q = '';
  query.role = '';
  query.last_sync_status = '';
  query.page = 1;
  void fetchList();
}

function clearSearch(): void {
  clearTimeout(searchTimer);
  searchDraft.value = '';
  if (query.q !== '') {
    query.q = '';
    query.page = 1;
    void fetchList();
  }
}

function applyRoleFilter(value: string): void {
  query.role = value;
  query.page = 1;
  openFilter.value = null;
  void fetchList();
}

function applySyncStatusFilter(value: string): void {
  query.last_sync_status = value;
  query.page = 1;
  openFilter.value = null;
  void fetchList();
}

function handlePageChange(nextPage: number): void {
  query.page = nextPage;
  void fetchList();
}

function handleSizeChange(nextSize: number): void {
  query.page_size = nextSize;
  query.page = 1;
  void fetchList();
}

function closeInlineMenus(except?: Element | null): void {
  const root = listRootRef.value;
  if (!root) return;
  root.querySelectorAll<HTMLDetailsElement>('details.tm-inline-menu[open]').forEach(el => {
    if (!except || el !== except) {
      el.open = false;
    }
  });
}

function handleMenuToggle(event: Event): void {
  const details = event.currentTarget as HTMLDetailsElement | null;
  if (details?.open) {
    closeInlineMenus(details);
  }
}

function handleDocumentClick(event: MouseEvent): void {
  const target = event.target instanceof Element ? event.target : null;
  const activeMenu = target?.closest('details.tm-inline-menu') ?? null;
  closeInlineMenus(activeMenu);
}

async function fetchList(options: { silent?: boolean; includeFacets?: 0 | 1 } = {}): Promise<void> {
  activeController?.abort();
  const controller = new AbortController();
  activeController = controller;
  const seq = ++requestSeq;

  if (!options.silent) {
    loading.value = true;
  }
  error.value = '';

  const requestQuery: TeamListQuery = {
    page: query.page,
    page_size: query.page_size,
    include_facets: options.includeFacets ?? 1,
    ...(query.q ? { q: query.q } : {}),
    ...(query.role ? { role: query.role } : {}),
    ...(query.last_sync_status ? { last_sync_status: query.last_sync_status } : {}),
  };

  try {
    const res = await props.api.list(requestQuery, controller.signal);
    if (seq !== requestSeq) return;
    items.value = res.items;
    total.value = res.total;
    summary.value = res.summary;
    if (res.facets && Object.keys(res.facets).length > 0) {
      facets.value = res.facets;
    }
  } catch (err) {
    if (controller.signal.aborted || seq !== requestSeq) return;
    const message = err instanceof Error ? err.message : '加载 Team 工作区列表失败';
    if (!options.silent) {
      error.value = message;
    }
  } finally {
    if (activeController === controller) {
      activeController = null;
    }
    if (seq === requestSeq && !options.silent) {
      loading.value = false;
    }
  }
}

async function handleSyncOne(team: TeamDTO): Promise<void> {
  if (syncingIds.value.has(team.team_id)) return;
  const next = new Set(syncingIds.value);
  next.add(team.team_id);
  syncingIds.value = next;
  try {
    const res = await props.api.syncTeam(team.team_id);
    props.callbacks.notify(
      res.reused
        ? `工作区「${team.effective_name}」已有进行中的同步任务`
        : `已启动工作区「${team.effective_name}」同步`,
    );
    await fetchList({ silent: true, includeFacets: 0 });
  } catch (err) {
    props.callbacks.notify(err instanceof Error ? err.message : '同步工作区提交失败');
  } finally {
    const cleaned = new Set(syncingIds.value);
    cleaned.delete(team.team_id);
    syncingIds.value = cleaned;
  }
}

async function handleBulkSync(): Promise<void> {
  const ids = [...selectedIds.value];
  if (!ids.length || bulkSyncing.value) return;
  bulkSyncing.value = true;
  try {
    const res = await props.api.syncTeamsBulk(ids);
    props.callbacks.notify(
      `批量同步已受理：排队 ${res.queued_count}，复用 ${res.reused_count}，跳过 ${res.skipped_count}`,
    );
    clearSelection();
    await fetchList({ silent: true, includeFacets: 0 });
  } catch (err) {
    props.callbacks.notify(err instanceof Error ? err.message : '批量同步提交失败');
  } finally {
    bulkSyncing.value = false;
  }
}

function handleOpenTasksFromMenu(event: MouseEvent, team: TeamDTO): void {
  const details = (event.currentTarget as HTMLElement | null)?.closest('details');
  if (details) details.open = false;
  props.callbacks.openTasksForTeam(team.team_id, team.effective_name);
}

function handleEditFromMenu(event: MouseEvent, team: TeamDTO): void {
  const details = (event.currentTarget as HTMLElement | null)?.closest('details');
  if (details) details.open = false;
  emit('open-edit', team);
}

function handleChangeManagerFromMenu(event: MouseEvent, team: TeamDTO): void {
  const details = (event.currentTarget as HTMLElement | null)?.closest('details');
  if (details) details.open = false;
  emit('open-change-manager', team);
}

useTeamPolling({
  visible: () => props.visible,
  shouldPoll: () => items.value.some(isTeamActivelyRunning),
  onPoll: () => fetchList({ silent: true, includeFacets: 0 }),
  intervalMs: 3000,
});

watch(searchDraft, value => {
  clearTimeout(searchTimer);
  const trimmed = value.trim();
  if (trimmed === query.q) return;
  searchTimer = setTimeout(() => {
    query.q = trimmed;
    query.page = 1;
    void fetchList();
  }, 250);
});

onMounted(() => {
  document.addEventListener('click', handleDocumentClick);
  void fetchList();
});

onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  activeController?.abort();
  document.removeEventListener('click', handleDocumentClick);
});

defineExpose({
  refresh: (options?: { silent?: boolean }) => fetchList({ silent: options?.silent, includeFacets: options?.silent ? 0 : 1 }),
});
</script>

<template>
  <div ref="listRootRef" class="tm-root">
    <!-- 顶部三张紧凑概览卡 -->
    <section class="tm-summary-strip" aria-label="Team 工作区概览">
      <article class="tm-summary-card">
        <div class="tm-summary-card__meta">
          <span class="tm-summary-card__label">已绑定工作区</span>
          <span class="tm-summary-card__hint">当前已纳管的工作区总数</span>
        </div>
        <strong class="tm-summary-card__value">
          {{ summary ? summary.total_teams.toLocaleString() : '—' }}
        </strong>
      </article>

      <article class="tm-summary-card" :class="{ 'is-active': (summary?.syncing_teams ?? 0) > 0 }">
        <div class="tm-summary-card__meta">
          <span class="tm-summary-card__label">正在同步 / 处理中</span>
          <span class="tm-summary-card__hint">包含同步及入组排队执行</span>
        </div>
        <strong class="tm-summary-card__value">
          {{ summary ? summary.syncing_teams.toLocaleString() : '—' }}
        </strong>
      </article>

      <article class="tm-summary-card" :class="{ 'is-warn': (summary?.attention_teams ?? 0) > 0 }">
        <div class="tm-summary-card__meta">
          <span class="tm-summary-card__label">需关注工作区</span>
          <span class="tm-summary-card__hint">同步异常、权限受限或待设上限</span>
        </div>
        <strong class="tm-summary-card__value">
          {{ summary ? summary.attention_teams.toLocaleString() : '—' }}
        </strong>
      </article>
    </section>

    <!-- 主列表面板 -->
    <section class="ui-list" aria-label="Team 工作区列表">
      <ListToolbar :filtered="isFiltered">
        <span class="ui-list-count">
          共 {{ total.toLocaleString() }} 个工作区
          <small v-if="selectedIds.size">已选 {{ selectedIds.size }} 项</small>
        </span>

        <div class="tm-search-box">
          <svg class="tm-search-box__icon" viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="7" cy="7" r="4.5" />
            <path d="m10.5 10.5 3 3" />
          </svg>
          <input
            v-model="searchDraft"
            type="search"
            aria-label="搜索工作区"
            placeholder="搜索名称 / workspace_id / 母号邮箱"
            @keydown.enter.prevent="query.q = searchDraft.trim(); query.page = 1; void fetchList()"
          />
          <button
            v-if="searchDraft"
            type="button"
            class="tm-search-box__clear"
            aria-label="清空搜索"
            @click="clearSearch"
          >
            ×
          </button>
        </div>

        <ListFilterSummary :items="activeFilterChips" @remove="removeFilter" />

        <template #actions>
          <button
            type="button"
            class="tm-btn"
            :disabled="!selectedIds.size || bulkSyncing"
            @click="void handleBulkSync()"
          >
            {{ bulkSyncing ? '同步提交中…' : '同步选中' }}
          </button>
          <button
            type="button"
            class="tm-btn ui-refresh-button"
            :disabled="loading"
            @click="void fetchList()"
          >
            {{ loading ? '刷新中…' : '刷新' }}
          </button>
          <button
            type="button"
            class="tm-btn tm-btn--primary"
            @click="emit('open-bind')"
          >
            绑定已有 Team
          </button>
        </template>
      </ListToolbar>

      <div v-if="selectedIds.size" class="ui-list-bulkbar">
        <span class="ui-list-bulkbar__count">已跨页选中 {{ selectedIds.size }} 个工作区</span>
        <button type="button" class="tm-btn tm-btn--ghost tm-btn--sm" @click="clearSelection">
          清空选择
        </button>
      </div>

      <div class="ui-table-wrap ui-table-scroll" tabindex="0" aria-label="Team 工作区表格，可横向滚动" :aria-busy="loading">
        <table class="ui-table ui-table--sticky-end ui-table--cards" :style="{ '--ui-table-width': `${tableWidth}px` }">
          <caption class="ui-sr-only">已绑定的 ChatGPT Team 工作区列表</caption>
          <colgroup>
            <col v-for="(width, idx) in widths" :key="idx" :style="{ width: `${width}px` }" />
          </colgroup>
          <thead>
            <tr>
              <th scope="col" class="ui-col-check">
                <input
                  type="checkbox"
                  aria-label="全选当前页工作区"
                  :checked="pageSelected"
                  :indeterminate="pageIndeterminate"
                  :disabled="!items.length"
                  @change="toggleSelectAllPage(($event.target as HTMLInputElement).checked)"
                />
              </th>

              <th scope="col">
                工作区
                <ColumnResizer label="工作区" @start="resize(1, $event)" @nudge="resizeWithKeyboard(1, $event)" />
              </th>

              <th scope="col">
                <FilterPopover
                  label="管理母号"
                  :active="Boolean(query.role)"
                  :summary="query.role ? teamRoleLabel(query.role) : ''"
                  :open="visible && openFilter === 'role'"
                  @update:open="openFilter = $event ? 'role' : null"
                >
                  <fieldset class="list-filter-options">
                    <legend class="ui-sr-only">按母号角色筛选</legend>
                    <label class="list-filter-option">
                      <input type="radio" name="team-role" value="" :checked="!query.role" @change="applyRoleFilter('')" />
                      <span>全部角色</span>
                    </label>
                    <label v-for="opt in ROLE_OPTIONS" :key="opt.value" class="list-filter-option">
                      <input
                        type="radio"
                        name="team-role"
                        :value="opt.value"
                        :checked="query.role === opt.value"
                        @change="applyRoleFilter(opt.value)"
                      />
                      <span>{{ opt.label }}</span>
                      <small v-if="facetCount('role', opt.value) !== null">{{ facetCount('role', opt.value) }}</small>
                    </label>
                  </fieldset>
                  <div class="list-filter-actions">
                    <button type="button" @click="applyRoleFilter('')">清除</button>
                    <button type="button" class="list-filter-primary" @click="openFilter = null">完成</button>
                  </div>
                </FilterPopover>
                <ColumnResizer label="管理母号" @start="resize(2, $event)" @nudge="resizeWithKeyboard(2, $event)" />
              </th>

              <th scope="col" title="远端已确认加入的成员数">
                已确认
                <ColumnResizer label="已确认成员" @start="resize(3, $event)" @nudge="resizeWithKeyboard(3, $event)" />
              </th>

              <th scope="col" title="远端待接受的邀请数">
                待接受
                <ColumnResizer label="待接受邀请" @start="resize(4, $event)" @nudge="resizeWithKeyboard(4, $event)" />
              </th>

              <th scope="col">
                处理中
                <ColumnResizer label="处理中" @start="resize(5, $event)" @nudge="resizeWithKeyboard(5, $event)" />
              </th>

              <th scope="col">
                席位 / 上限
                <ColumnResizer label="席位 / 上限" @start="resize(6, $event)" @nudge="resizeWithKeyboard(6, $event)" />
              </th>

              <th scope="col">
                <FilterPopover
                  label="最近同步"
                  :active="Boolean(query.last_sync_status)"
                  :summary="query.last_sync_status ? teamSyncLabel(query.last_sync_status) : ''"
                  :open="visible && openFilter === 'last_sync_status'"
                  @update:open="openFilter = $event ? 'last_sync_status' : null"
                >
                  <fieldset class="list-filter-options">
                    <legend class="ui-sr-only">按同步状态筛选</legend>
                    <label class="list-filter-option">
                      <input
                        type="radio"
                        name="team-sync"
                        value=""
                        :checked="!query.last_sync_status"
                        @change="applySyncStatusFilter('')"
                      />
                      <span>全部同步状态</span>
                    </label>
                    <label v-for="opt in SYNC_STATUS_OPTIONS" :key="opt.value" class="list-filter-option">
                      <input
                        type="radio"
                        name="team-sync"
                        :value="opt.value"
                        :checked="query.last_sync_status === opt.value"
                        @change="applySyncStatusFilter(opt.value)"
                      />
                      <span>{{ opt.label }}</span>
                      <small v-if="facetCount('last_sync_status', opt.value) !== null">
                        {{ facetCount('last_sync_status', opt.value) }}
                      </small>
                    </label>
                  </fieldset>
                  <div class="list-filter-actions">
                    <button type="button" @click="applySyncStatusFilter('')">清除</button>
                    <button type="button" class="list-filter-primary" @click="openFilter = null">完成</button>
                  </div>
                </FilterPopover>
                <ColumnResizer label="最近同步" @start="resize(7, $event)" @nudge="resizeWithKeyboard(7, $event)" />
              </th>

              <th scope="col">操作</th>
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="team in items"
              :key="team.team_id"
              :class="{ 'is-selected': selectedIds.has(team.team_id) }"
            >
              <td class="ui-col-check">
                <input
                  type="checkbox"
                  :aria-label="`选择工作区 ${team.effective_name}`"
                  :checked="selectedIds.has(team.team_id)"
                  @change="toggleSelectRow(team.team_id, ($event.target as HTMLInputElement).checked)"
                />
              </td>

              <td data-label="工作区">
                <div class="tm-workspace-identity">
                  <div
                    class="tm-workspace-avatar"
                    :style="{ '--tm-hue': String(workspaceAvatarHue(team.workspace_id)) }"
                    aria-hidden="true"
                  >
                    {{ workspaceInitials(team.effective_name) }}
                  </div>
                  <div class="tm-workspace-copy">
                    <div class="tm-workspace-title-row">
                      <button
                        type="button"
                        class="tm-workspace-name-btn"
                        :title="team.effective_name"
                        @click="emit('open-detail', team.team_id, 'members')"
                      >
                        {{ team.effective_name }}
                      </button>
                      <span v-if="team.plan_type" class="tm-plan-tag">{{ team.plan_type }}</span>
                    </div>
                    <div class="tm-workspace-sub">
                      <span class="tm-mono" :title="team.workspace_id">{{ team.workspace_id }}</span>
                    </div>
                  </div>
                </div>
              </td>

              <td data-label="管理母号">
                <div class="tm-cell-stack">
                  <div class="tm-cell-primary">
                    <button
                      v-if="team.manager_account.account_id"
                      type="button"
                      class="tm-link-btn"
                      :title="team.manager_account.email"
                      @click="callbacks.openAccountDetail(team.manager_account.account_id)"
                    >
                      {{ team.manager_account.email || `#${team.manager_account.account_id}` }}
                    </button>
                    <span v-else>{{ team.manager_account.email || '—' }}</span>
                  </div>
                  <div class="tm-cell-sub" style="display: flex; align-items: center; gap: 5px; flex-wrap: wrap;">
                    <span class="tm-badge" :class="badgeClass(teamRoleTone(team.manager_role))">
                      {{ teamRoleLabel(team.manager_role) }}
                    </span>
                    <span v-if="team.manager_account.archived" class="tm-badge tm-badge--neutral">已归档</span>
                    <span v-if="team.can_manage === false" class="tm-badge tm-badge--danger">无管理权限</span>
                  </div>
                </div>
              </td>

              <td data-label="已确认成员">
                <div class="tm-metric-cell">
                  <span class="tm-metric-val" :class="{ 'is-null': team.confirmed_member_count === null }">
                    {{ formatNullableCount(team.confirmed_member_count, '待同步') }}
                  </span>
                </div>
              </td>

              <td data-label="待接受邀请">
                <div class="tm-metric-cell">
                  <span class="tm-metric-val" :class="{ 'is-null': team.pending_invite_count === null }">
                    {{ formatNullableCount(team.pending_invite_count, '待同步') }}
                  </span>
                </div>
              </td>

              <td data-label="处理中">
                <div class="tm-metric-cell">
                  <span class="tm-metric-val" :class="{ 'is-processing': team.processing_count > 0 }">
                    {{ formatNullableCount(team.processing_count, '—') }}
                  </span>
                </div>
              </td>

              <td data-label="席位 / 上限">
                <div class="tm-cell-stack">
                  <div class="tm-cell-primary">
                    <span>{{ formatSeatLimitDisplay(team).primary }}</span>
                  </div>
                  <div class="tm-cell-sub">
                    <span class="tm-badge" :class="badgeClass(formatSeatLimitDisplay(team).tone)">
                      {{ formatSeatLimitDisplay(team).secondary }}
                    </span>
                  </div>
                </div>
              </td>

              <td data-label="最近同步">
                <div class="tm-cell-stack">
                  <div class="tm-cell-primary">
                    <span class="tm-badge" :class="badgeClass(teamSyncTone(team.last_sync_status))">
                      <span
                        v-if="team.last_sync_status === 'queued' || team.last_sync_status === 'running'"
                        class="tm-badge__dot"
                      ></span>
                      {{ teamSyncLabel(team.last_sync_status) }}
                    </span>
                  </div>
                  <div
                    v-if="team.last_sync_status === 'failed'"
                    class="tm-cell-sub is-danger"
                    :title="team.last_sync_error?.summary || ''"
                  >
                    {{ teamReasonLabel(team.last_sync_error?.reason_code, team.last_sync_error) }}
                  </div>
                  <div v-else class="tm-cell-sub tm-tabular">
                    {{ team.last_synced_at ? callbacks.formatDateTime(team.last_synced_at) : '待同步' }}
                  </div>
                </div>
              </td>

              <td data-label="操作">
                <div class="tm-row-actions">
                  <button
                    type="button"
                    class="tm-btn tm-btn--sm"
                    @click="emit('open-detail', team.team_id, 'members')"
                  >
                    查看
                  </button>
                  <button
                    type="button"
                    class="tm-btn tm-btn--sm tm-btn--soft"
                    :disabled="team.can_manage === false"
                    :title="team.can_manage === false ? '当前母号无管理权限，请先核验或更换母号' : '选择账号批量邀请并自动加入'"
                    @click="emit('open-join', team)"
                  >
                    拉人
                  </button>
                  <button
                    type="button"
                    class="tm-btn tm-btn--sm"
                    :disabled="syncingIds.has(team.team_id) || team.last_sync_status === 'queued' || team.last_sync_status === 'running'"
                    @click="void handleSyncOne(team)"
                  >
                    {{ syncingIds.has(team.team_id) ? '同步中' : '同步' }}
                  </button>
                  <details class="tm-inline-menu" @toggle="handleMenuToggle">
                    <summary aria-label="更多操作">···</summary>
                    <div class="tm-inline-menu__panel">
                      <button type="button" @click="handleOpenTasksFromMenu($event, team)">
                        查看相关任务
                      </button>
                      <button type="button" @click="handleEditFromMenu($event, team)">
                        设置别名与上限
                      </button>
                      <button type="button" @click="handleChangeManagerFromMenu($event, team)">
                        更换管理母号
                      </button>
                    </div>
                  </details>
                </div>
              </td>
            </tr>

            <TableState
              v-if="!items.length"
              :colspan="9"
              :loading="loading"
              :error="error"
              loading-title="正在加载 Team 工作区"
              loading-text="获取已绑定的工作区、成员快照与同步状态"
              error-title="加载工作区列表失败"
              :title="isFiltered ? '没有匹配的工作区' : '还没有绑定的 Team 工作区'"
              :text="isFiltered ? '可调整搜索关键词或清除筛选条件后再试。' : '选择一个已有 ChatGPT Team 管理权的主账号完成探测与绑定，即可统一管理成员、席位并自动批量拉人。'"
              retry-label="重试"
              @retry="void fetchList()"
            >
              <button
                v-if="!loading && !error && !isFiltered"
                type="button"
                class="tm-btn tm-btn--primary"
                @click="emit('open-bind')"
              >
                绑定已有 Team
              </button>
              <button
                v-else-if="!loading && !error && isFiltered"
                type="button"
                class="tm-btn tm-btn--sm"
                @click="clearAllFilters"
              >
                清除筛选条件
              </button>
            </TableState>
          </tbody>
        </table>
      </div>

      <ListPagination
        :page="query.page"
        :size="query.page_size"
        :total="total"
        :busy="loading"
        label="Team 工作区列表分页"
        @update:page="handlePageChange"
        @update:size="handleSizeChange"
      />
    </section>
  </div>
</template>
