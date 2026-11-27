<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import type { TeamsApi } from '../../api/teams';
import ColumnResizer from '../../components/ColumnResizer.vue';
import FilterPopover from '../../components/FilterPopover.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListPagination from '../../components/ListPagination.vue';
import ListResult from '../../components/ListResult.vue';
import ListToolbar from '../../components/ListToolbar.vue';
import TableState from '../../components/TableState.vue';
import { useColumnWidths } from '../../shared/useColumnWidths';
import type {
  TeamDecimalId,
  TeamFacets,
  TeamInvitationDTO,
  TeamInvitationsQuery,
  TeamsHostCallbacks,
} from './contracts';
import {
  formatInvitationBusinessFacts,
  formatInvitationExecutionFacts,
  formatInvitationResultSummary,
  teamExecutionLabel,
  teamInvitationStateLabel,
  teamJoinStageLabel,
  teamMembershipLabel,
  type BadgeTone,
} from './statusLabels';
import { useTeamPolling } from './useTeamPolling';

const props = defineProps<{
  api: TeamsApi;
  teamId: TeamDecimalId;
  visible: boolean;
  callbacks: TeamsHostCallbacks;
  joinRequestId?: string;
}>();

const emit = defineEmits<{
  'refresh-team': [];
  'clear-join-request': [];
}>();

const INVITATION_STATE_OPTIONS = [
  { value: 'not_sent', label: '未发邀请' },
  { value: 'pending', label: '待接受邀请' },
  { value: 'accepted', label: '邀请已接受' },
  { value: 'revoked', label: '邀请已撤回' },
  { value: 'expired', label: '邀请已过期' },
  { value: 'unknown', label: '邀请状态未知' },
] as const;

const MEMBERSHIP_STATE_OPTIONS = [
  { value: 'joined', label: '已加入' },
  { value: 'not_joined', label: '未入组' },
  { value: 'removed', label: '已移除' },
  { value: 'left', label: '已退出' },
  { value: 'unknown', label: '待核实' },
] as const;

const EXECUTION_STATUS_OPTIONS = [
  { value: 'idle', label: '未执行' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '执行中' },
  { value: 'waiting_user', label: '等待人工处理' },
  { value: 'succeeded', label: '已完成' },
  { value: 'failed', label: '执行失败' },
  { value: 'cancelled', label: '已取消' },
] as const;

const STAGE_OPTIONS = [
  { value: 'precheck_capacity', label: '预检席位与容量' },
  { value: 'send_invite', label: '母号发送邀请' },
  { value: 'await_invite_mail', label: '等待接收邀请邮件' },
  { value: 'open_invite_link', label: '解析并打开邀请链接' },
  { value: 'authenticate_target', label: '认证目标账号' },
  { value: 'accept_workspace_join', label: '确认加入工作区' },
  { value: 'verify_membership', label: '回查工作区成员状态' },
] as const;

const query = reactive<{
  page: number;
  page_size: number;
  q: string;
  invitation_state: string;
  membership_state: string;
  execution_status: string;
  stage: string;
  join_request_id: string;
}>({
  page: 1,
  page_size: 20,
  q: '',
  invitation_state: '',
  membership_state: '',
  execution_status: '',
  stage: '',
  join_request_id: props.joinRequestId || '',
});

const searchDraft = ref('');
const openFilter = ref<string | null>(null);
const loading = ref(false);
const bulkBusy = ref(false);
const error = ref('');
const items = ref<TeamInvitationDTO[]>([]);
const total = ref(0);
const facets = ref<TeamFacets>({});
const selectedIds = ref<Set<TeamDecimalId>>(new Set());
const actingIds = ref<Set<TeamDecimalId>>(new Set());

// 严格 6 列：目标账号 | 业务事实 | 执行与阶段 | 结果摘要 | 时间 | 操作
const { widths, total: tableWidth, resize, resizeWithKeyboard } = useColumnWidths({
  defaults: [215, 132, 154, 178, 152, 198],
  storageKey: 'turb_team_invitations_column_widths_v2',
  min: 90,
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

function missingAuthMaterials(row: TeamInvitationDTO): boolean {
  if (row.error?.reason_code === 'team_target_auth_missing') return true;
  const acc = row.target_account;
  return Boolean(acc.account_id) && !acc.has_access_token && !acc.has_account_password;
}

const pageSelected = computed(() => items.value.length > 0 && items.value.every(row => selectedIds.value.has(row.invitation_id)));
const pageIndeterminate = computed(() => !pageSelected.value && items.value.some(row => selectedIds.value.has(row.invitation_id)));

function toggleSelectAllPage(checked: boolean): void {
  const next = new Set(selectedIds.value);
  for (const row of items.value) {
    if (checked) next.add(row.invitation_id);
    else next.delete(row.invitation_id);
  }
  selectedIds.value = next;
}

function toggleSelectRow(invitationId: TeamDecimalId, checked: boolean): void {
  const next = new Set(selectedIds.value);
  if (checked) next.add(invitationId);
  else next.delete(invitationId);
  selectedIds.value = next;
}

function clearSelection(): void {
  selectedIds.value = new Set();
}

const activeFilterChips = computed(() => {
  const chips: Array<{ key: string; label: string; removeLabel: string }> = [];
  if (query.join_request_id) {
    chips.push({
      key: 'join_request_id',
      label: `入组批次：#${query.join_request_id}`,
      removeLabel: '清除批次过滤',
    });
  }
  if (query.q) {
    chips.push({ key: 'q', label: `关键词：${query.q}`, removeLabel: '清除关键词筛选' });
  }
  if (query.invitation_state) {
    chips.push({
      key: 'invitation_state',
      label: `邀请状态：${teamInvitationStateLabel(query.invitation_state)}`,
      removeLabel: '清除邀请状态筛选',
    });
  }
  if (query.membership_state) {
    chips.push({
      key: 'membership_state',
      label: `成员状态：${teamMembershipLabel(query.membership_state)}`,
      removeLabel: '清除成员状态筛选',
    });
  }
  if (query.execution_status) {
    chips.push({
      key: 'execution_status',
      label: `执行状态：${teamExecutionLabel(query.execution_status)}`,
      removeLabel: '清除执行状态筛选',
    });
  }
  if (query.stage) {
    chips.push({
      key: 'stage',
      label: `阶段：${teamJoinStageLabel(query.stage)}`,
      removeLabel: '清除阶段筛选',
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
  } else if (key === 'join_request_id') {
    query.join_request_id = '';
    emit('clear-join-request');
  } else if (key === 'invitation_state') {
    query.invitation_state = '';
  } else if (key === 'membership_state') {
    query.membership_state = '';
  } else if (key === 'execution_status') {
    query.execution_status = '';
  } else if (key === 'stage') {
    query.stage = '';
  }
  query.page = 1;
  void fetchInvitations();
}

function clearAllFilters(): void {
  clearTimeout(searchTimer);
  searchDraft.value = '';
  query.q = '';
  query.invitation_state = '';
  query.membership_state = '';
  query.execution_status = '';
  query.stage = '';
  if (query.join_request_id) {
    query.join_request_id = '';
    emit('clear-join-request');
  }
  query.page = 1;
  void fetchInvitations();
}

function clearSearch(): void {
  clearTimeout(searchTimer);
  searchDraft.value = '';
  if (query.q !== '') {
    query.q = '';
    query.page = 1;
    void fetchInvitations();
  }
}

function applyBusinessFilter(field: 'invitation_state' | 'membership_state', value: string): void {
  query[field] = value;
  query.page = 1;
  void fetchInvitations();
}

function applyExecutionFilter(field: 'execution_status' | 'stage', value: string): void {
  query[field] = value;
  query.page = 1;
  void fetchInvitations();
}

function handlePageChange(nextPage: number): void {
  query.page = nextPage;
  void fetchInvitations();
}

function handleSizeChange(nextSize: number): void {
  query.page_size = nextSize;
  query.page = 1;
  void fetchInvitations();
}

async function fetchInvitations(options: { silent?: boolean; includeFacets?: 0 | 1 } = {}): Promise<void> {
  if (!props.teamId) return;
  activeController?.abort();
  const controller = new AbortController();
  activeController = controller;
  const seq = ++requestSeq;

  if (!options.silent) {
    loading.value = true;
  }
  error.value = '';

  const requestQuery: TeamInvitationsQuery = {
    page: query.page,
    page_size: query.page_size,
    include_facets: options.includeFacets ?? 1,
    ...(query.q ? { q: query.q } : {}),
    ...(query.invitation_state ? { invitation_state: query.invitation_state } : {}),
    ...(query.membership_state ? { membership_state: query.membership_state } : {}),
    ...(query.execution_status ? { execution_status: query.execution_status } : {}),
    ...(query.stage ? { stage: query.stage } : {}),
    ...(query.join_request_id ? { join_request_id: query.join_request_id } : {}),
  };

  try {
    const res = await props.api.listInvitations(props.teamId, requestQuery, controller.signal);
    if (seq !== requestSeq) return;
    items.value = res.items;
    total.value = res.total;
    if (res.facets && Object.keys(res.facets).length > 0) {
      facets.value = res.facets;
    }
  } catch (err) {
    if (controller.signal.aborted || seq !== requestSeq) return;
    const message = err instanceof Error ? err.message : '加载邀请与入组记录失败';
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

async function handleContinueRow(row: TeamInvitationDTO): Promise<void> {
  const next = new Set(actingIds.value);
  next.add(row.invitation_id);
  actingIds.value = next;
  try {
    const res = await props.api.continueInvitation(props.teamId, row.invitation_id);
    props.callbacks.notify(
      res.outcome === 'reused_active'
        ? `已复用当前进行中的入组执行（${row.email}）`
        : `已受理继续加入（${row.email}）`,
    );
    await fetchInvitations({ silent: true, includeFacets: 0 });
    emit('refresh-team');
  } catch (err) {
    props.callbacks.notify(err instanceof Error ? err.message : '继续加入提交失败');
  } finally {
    const cleaned = new Set(actingIds.value);
    cleaned.delete(row.invitation_id);
    actingIds.value = cleaned;
  }
}

async function handleRetryRow(row: TeamInvitationDTO): Promise<void> {
  const next = new Set(actingIds.value);
  next.add(row.invitation_id);
  actingIds.value = next;
  try {
    const res = await props.api.retryInvitation(props.teamId, row.invitation_id);
    props.callbacks.notify(
      res.outcome === 'reused_active'
        ? `已复用当前活跃执行（${row.email}）`
        : `已创建重跑任务（${row.email}）`,
    );
    await fetchInvitations({ silent: true, includeFacets: 0 });
    emit('refresh-team');
  } catch (err) {
    props.callbacks.notify(err instanceof Error ? err.message : '重跑提交失败');
  } finally {
    const cleaned = new Set(actingIds.value);
    cleaned.delete(row.invitation_id);
    actingIds.value = cleaned;
  }
}

async function handleBulkContinue(): Promise<void> {
  const ids = [...selectedIds.value];
  if (!ids.length || bulkBusy.value) return;
  bulkBusy.value = true;
  try {
    const res = await props.api.continueInvitationsBulk(props.teamId, ids);
    props.callbacks.notify(
      `批量继续加入已受理：新增排队 ${res.queued_count}，复用 ${res.reused_active_count}，跳过 ${res.skipped_count}`,
    );
    clearSelection();
    await fetchInvitations({ silent: true, includeFacets: 0 });
    emit('refresh-team');
  } catch (err) {
    props.callbacks.notify(err instanceof Error ? err.message : '批量继续加入失败');
  } finally {
    bulkBusy.value = false;
  }
}

async function handleBulkRetry(): Promise<void> {
  const ids = [...selectedIds.value];
  if (!ids.length || bulkBusy.value) return;
  bulkBusy.value = true;
  try {
    const res = await props.api.retryInvitationsBulk(props.teamId, ids);
    props.callbacks.notify(
      `批量重跑已受理：新增排队 ${res.queued_count}，复用 ${res.reused_active_count}，跳过 ${res.skipped_count}`,
    );
    clearSelection();
    await fetchInvitations({ silent: true, includeFacets: 0 });
    emit('refresh-team');
  } catch (err) {
    props.callbacks.notify(err instanceof Error ? err.message : '批量重跑失败');
  } finally {
    bulkBusy.value = false;
  }
}

useTeamPolling({
  visible: () => props.visible,
  shouldPoll: () => items.value.some(row => row.execution_status === 'queued' || row.execution_status === 'running'),
  onPoll: async () => {
    await fetchInvitations({ silent: true, includeFacets: 0 });
    emit('refresh-team');
  },
  intervalMs: 3000,
});

watch(searchDraft, value => {
  clearTimeout(searchTimer);
  const trimmed = value.trim();
  if (trimmed === query.q) return;
  searchTimer = setTimeout(() => {
    query.q = trimmed;
    query.page = 1;
    void fetchInvitations();
  }, 250);
});

watch(
  () => props.joinRequestId,
  nextId => {
    const normalized = nextId || '';
    if (normalized === query.join_request_id) return;
    query.join_request_id = normalized;
    query.page = 1;
    void fetchInvitations();
  },
);

watch(
  () => props.teamId,
  () => {
    query.page = 1;
    clearSelection();
    items.value = [];
    total.value = 0;
    facets.value = {};
    void fetchInvitations();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  activeController?.abort();
});

defineExpose({
  refresh: () => fetchInvitations(),
});
</script>

<template>
  <section class="ui-list" aria-label="邀请与入组记录">
    <ListToolbar :filtered="isFiltered">
      <span class="ui-list-count">
        共 {{ total.toLocaleString() }} 条邀请记录
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
          aria-label="搜索邀请记录"
          placeholder="搜索邮箱 / 本地账号 ID"
          @keydown.enter.prevent="query.q = searchDraft.trim(); query.page = 1; void fetchInvitations()"
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
          class="tm-btn tm-btn--soft"
          :disabled="!selectedIds.size || bulkBusy"
          @click="void handleBulkContinue()"
        >
          {{ bulkBusy ? '处理中…' : '批量继续加入' }}
        </button>
        <button
          type="button"
          class="tm-btn"
          :disabled="!selectedIds.size || bulkBusy"
          @click="void handleBulkRetry()"
        >
          批量重跑
        </button>
        <button
          type="button"
          class="tm-btn ui-refresh-button"
          :disabled="loading"
          @click="void fetchInvitations()"
        >
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </ListToolbar>

    <div v-if="selectedIds.size" class="ui-list-bulkbar">
      <span class="ui-list-bulkbar__count">已跨页选中 {{ selectedIds.size }} 条邀请记录</span>
      <button type="button" class="tm-btn tm-btn--ghost tm-btn--sm" @click="clearSelection">
        清空选择
      </button>
    </div>

    <div class="ui-table-wrap ui-table-scroll" tabindex="0" aria-label="邀请与入组表格，可横向滚动" :aria-busy="loading">
      <table class="ui-table ui-table--sticky-end ui-table--cards" :style="{ '--ui-table-width': `${tableWidth}px` }">
        <caption class="ui-sr-only">工作区邀请记录与自动入组状态（严格六列）</caption>
        <colgroup>
          <col v-for="(width, idx) in widths" :key="idx" :style="{ width: `${width}px` }" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">
              <span style="display: inline-flex; align-items: center; gap: 10px;">
                <input
                  type="checkbox"
                  aria-label="全选当前页邀请记录"
                  :checked="pageSelected"
                  :indeterminate="pageIndeterminate"
                  :disabled="!items.length"
                  @change="toggleSelectAllPage(($event.target as HTMLInputElement).checked)"
                />
                <span>目标账号</span>
              </span>
              <ColumnResizer label="目标账号" @start="resize(0, $event)" @nudge="resizeWithKeyboard(0, $event)" />
            </th>

            <th scope="col">
              <FilterPopover
                label="业务事实"
                :active="Boolean(query.invitation_state || query.membership_state)"
                :summary="[
                  query.invitation_state ? teamInvitationStateLabel(query.invitation_state) : '',
                  query.membership_state ? teamMembershipLabel(query.membership_state) : '',
                ].filter(Boolean).join(' · ')"
                :open="visible && openFilter === 'business'"
                @update:open="openFilter = $event ? 'business' : null"
              >
                <div style="display: grid; gap: 10px;">
                  <label class="tm-field">
                    <span class="tm-field__label">邀请状态</span>
                    <select
                      :value="query.invitation_state"
                      aria-label="筛选邀请状态"
                      @change="applyBusinessFilter('invitation_state', ($event.target as HTMLSelectElement).value)"
                    >
                      <option value="">全部邀请状态</option>
                      <option v-for="opt in INVITATION_STATE_OPTIONS" :key="opt.value" :value="opt.value">
                        {{ opt.label }}{{ facetCount('invitation_state', opt.value) !== null ? ` (${facetCount('invitation_state', opt.value)})` : '' }}
                      </option>
                    </select>
                  </label>

                  <label class="tm-field">
                    <span class="tm-field__label">成员状态</span>
                    <select
                      :value="query.membership_state"
                      aria-label="筛选成员状态"
                      @change="applyBusinessFilter('membership_state', ($event.target as HTMLSelectElement).value)"
                    >
                      <option value="">全部成员状态</option>
                      <option v-for="opt in MEMBERSHIP_STATE_OPTIONS" :key="opt.value" :value="opt.value">
                        {{ opt.label }}{{ facetCount('membership_state', opt.value) !== null ? ` (${facetCount('membership_state', opt.value)})` : '' }}
                      </option>
                    </select>
                  </label>

                  <div class="list-filter-actions">
                    <button
                      type="button"
                      @click="query.invitation_state = ''; query.membership_state = ''; query.page = 1; openFilter = null; void fetchInvitations()"
                    >
                      清除
                    </button>
                    <button type="button" class="list-filter-primary" @click="openFilter = null">完成</button>
                  </div>
                </div>
              </FilterPopover>
              <ColumnResizer label="业务事实" @start="resize(1, $event)" @nudge="resizeWithKeyboard(1, $event)" />
            </th>

            <th scope="col">
              <FilterPopover
                label="执行与阶段"
                :active="Boolean(query.execution_status || query.stage)"
                :summary="[
                  query.execution_status ? teamExecutionLabel(query.execution_status) : '',
                  query.stage ? teamJoinStageLabel(query.stage) : '',
                ].filter(Boolean).join(' · ')"
                :open="visible && openFilter === 'execution'"
                @update:open="openFilter = $event ? 'execution' : null"
              >
                <div style="display: grid; gap: 10px;">
                  <label class="tm-field">
                    <span class="tm-field__label">执行状态</span>
                    <select
                      :value="query.execution_status"
                      aria-label="筛选执行状态"
                      @change="applyExecutionFilter('execution_status', ($event.target as HTMLSelectElement).value)"
                    >
                      <option value="">全部执行状态</option>
                      <option v-for="opt in EXECUTION_STATUS_OPTIONS" :key="opt.value" :value="opt.value">
                        {{ opt.label }}{{ facetCount('execution_status', opt.value) !== null ? ` (${facetCount('execution_status', opt.value)})` : '' }}
                      </option>
                    </select>
                  </label>

                  <label class="tm-field">
                    <span class="tm-field__label">当前阶段</span>
                    <select
                      :value="query.stage"
                      aria-label="筛选当前阶段"
                      @change="applyExecutionFilter('stage', ($event.target as HTMLSelectElement).value)"
                    >
                      <option value="">全部阶段</option>
                      <option v-for="opt in STAGE_OPTIONS" :key="opt.value" :value="opt.value">
                        {{ opt.label }}{{ facetCount('stage', opt.value) !== null ? ` (${facetCount('stage', opt.value)})` : '' }}
                      </option>
                    </select>
                  </label>

                  <div class="list-filter-actions">
                    <button
                      type="button"
                      @click="query.execution_status = ''; query.stage = ''; query.page = 1; openFilter = null; void fetchInvitations()"
                    >
                      清除
                    </button>
                    <button type="button" class="list-filter-primary" @click="openFilter = null">完成</button>
                  </div>
                </div>
              </FilterPopover>
              <ColumnResizer label="执行与阶段" @start="resize(2, $event)" @nudge="resizeWithKeyboard(2, $event)" />
            </th>

            <th scope="col">
              结果摘要
              <ColumnResizer label="结果摘要" @start="resize(3, $event)" @nudge="resizeWithKeyboard(3, $event)" />
            </th>

            <th scope="col">
              时间
              <ColumnResizer label="时间" @start="resize(4, $event)" @nudge="resizeWithKeyboard(4, $event)" />
            </th>

            <th scope="col">操作</th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="row in items"
            :key="row.invitation_id"
            :class="{ 'is-selected': selectedIds.has(row.invitation_id) }"
          >
            <!-- 第 1 列：目标账号 -->
            <td data-label="目标账号">
              <div style="display: flex; align-items: flex-start; gap: 10px; min-width: 0;">
                <input
                  type="checkbox"
                  style="margin-top: 3px;"
                  :aria-label="`选择邀请记录 ${row.email}`"
                  :checked="selectedIds.has(row.invitation_id)"
                  @change="toggleSelectRow(row.invitation_id, ($event.target as HTMLInputElement).checked)"
                />
                <div class="tm-cell-stack">
                  <div class="tm-cell-primary">
                    <span :title="row.email">{{ row.email || row.target_account.email || '未返回' }}</span>
                  </div>
                  <div class="tm-cell-sub" style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                    <button
                      v-if="row.target_account.account_id"
                      type="button"
                      class="tm-link-btn tm-tabular"
                      @click="callbacks.openAccountDetail(row.target_account.account_id)"
                    >
                      #{{ row.target_account.account_id }}
                    </button>
                    <span v-else class="tm-badge tm-badge--neutral">未入库</span>
                    <span v-if="row.target_account.archived" class="tm-badge tm-badge--neutral">已归档</span>
                    <span v-if="missingAuthMaterials(row)" class="tm-badge tm-badge--warning">缺认证材料</span>
                    <span v-if="row.target_account.email_invalid" class="tm-badge tm-badge--danger">邮箱失效</span>
                  </div>
                </div>
              </div>
            </td>

            <!-- 第 2 列：业务事实 -->
            <td data-label="业务事实">
              <div class="tm-cell-stack">
                <div class="tm-cell-primary">
                  <span class="tm-badge" :class="badgeClass(formatInvitationBusinessFacts(row).tone)">
                    {{ formatInvitationBusinessFacts(row).primary }}
                  </span>
                </div>
                <div class="tm-cell-sub">
                  {{ formatInvitationBusinessFacts(row).secondary }}
                </div>
              </div>
            </td>

            <!-- 第 3 列：执行与阶段 -->
            <td data-label="执行与阶段">
              <div class="tm-cell-stack">
                <div class="tm-cell-primary">
                  <span class="tm-badge" :class="badgeClass(formatInvitationExecutionFacts(row).tone)">
                    <span
                      v-if="row.execution_status === 'queued' || row.execution_status === 'running'"
                      class="tm-badge__dot"
                    ></span>
                    {{ formatInvitationExecutionFacts(row).primary }}
                  </span>
                </div>
                <div class="tm-cell-sub" :title="formatInvitationExecutionFacts(row).secondary">
                  {{ formatInvitationExecutionFacts(row).secondary }}
                </div>
              </div>
            </td>

            <!-- 第 4 列：结果摘要 -->
            <td data-label="结果摘要">
              <ListResult
                :label="formatInvitationResultSummary(row).label"
                :secondary="formatInvitationResultSummary(row).secondary"
                :tone="formatInvitationResultSummary(row).tone"
                :title="formatInvitationResultSummary(row).detail || formatInvitationResultSummary(row).label"
              >
                <template v-if="formatInvitationResultSummary(row).detail" #details>
                  <p v-if="row.error?.reason_code">
                    原因码：<span class="tm-mono">{{ row.error.reason_code }}</span>
                  </p>
                  <p>{{ formatInvitationResultSummary(row).detail }}</p>
                </template>
              </ListResult>
            </td>

            <!-- 第 5 列：时间 -->
            <td data-label="时间">
              <div class="tm-cell-stack">
                <div class="tm-cell-sub">
                  邀请于：{{ row.invited_at ? callbacks.formatDateTime(row.invited_at) : '—' }}
                </div>
                <div class="tm-cell-sub">
                  {{ row.accepted_at ? `接受于：${callbacks.formatDateTime(row.accepted_at)}` : `更新于：${callbacks.formatDateTime(row.updated_at)}` }}
                </div>
              </div>
            </td>

            <!-- 第 6 列：操作 -->
            <td data-label="操作">
              <div class="tm-row-actions">
                <button
                  v-if="row.actions.can_continue"
                  type="button"
                  class="tm-btn tm-btn--sm tm-btn--soft"
                  :disabled="actingIds.has(row.invitation_id)"
                  @click="void handleContinueRow(row)"
                >
                  继续加入
                </button>
                <button
                  v-if="row.actions.can_retry"
                  type="button"
                  class="tm-btn tm-btn--sm"
                  :disabled="actingIds.has(row.invitation_id)"
                  @click="void handleRetryRow(row)"
                >
                  重跑
                </button>
                <button
                  v-if="row.actions.can_open_task && row.latest_task_id"
                  type="button"
                  class="tm-btn tm-btn--sm tm-btn--ghost"
                  @click="callbacks.openTask(row.latest_task_id, row.latest_run_id)"
                >
                  查看任务
                </button>
                <span
                  v-if="!row.actions.can_continue && !row.actions.can_retry && !(row.actions.can_open_task && row.latest_task_id)"
                  class="tm-cell-sub"
                >
                  —
                </span>
              </div>
            </td>
          </tr>

          <TableState
            v-if="!items.length"
            :colspan="6"
            :loading="loading"
            :error="error"
            loading-title="正在加载邀请与入组记录"
            loading-text="同步当前工作区的远端邀请与自动加入进度"
            error-title="加载邀请记录失败"
            :title="isFiltered ? '没有匹配的邀请记录' : '暂无邀请与入组记录'"
            :text="isFiltered ? '可调整搜索或筛选条件后重试。' : '点击上方「加入账号」批量发起邀请，或等待工作区同步返回远端待接受邀请。'"
            retry-label="重试"
            @retry="void fetchInvitations()"
          >
            <button v-if="!loading && !error && isFiltered" type="button" class="tm-btn tm-btn--sm" @click="clearAllFilters">
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
      label="邀请记录分页"
      @update:page="handlePageChange"
      @update:size="handleSizeChange"
    />
  </section>
</template>
