<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import type { TeamsApi } from '../../api/teams';
import ColumnResizer from '../../components/ColumnResizer.vue';
import FilterPopover from '../../components/FilterPopover.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListPagination from '../../components/ListPagination.vue';
import ListToolbar from '../../components/ListToolbar.vue';
import TableState from '../../components/TableState.vue';
import { useColumnWidths } from '../../shared/useColumnWidths';
import type {
  TeamDecimalId,
  TeamFacets,
  TeamMemberDTO,
  TeamMembersQuery,
  TeamsHostCallbacks,
} from './contracts';
import {
  teamMembershipLabel,
  teamMembershipTone,
  teamRoleLabel,
  teamRoleTone,
  type BadgeTone,
} from './statusLabels';

const props = defineProps<{
  api: TeamsApi;
  teamId: TeamDecimalId;
  visible: boolean;
  callbacks: TeamsHostCallbacks;
}>();

const ROLE_OPTIONS = [
  { value: 'owner', label: '所有者' },
  { value: 'admin', label: '管理员' },
  { value: 'member', label: '成员' },
  { value: 'unknown', label: '待核验' },
] as const;

const MEMBERSHIP_STATE_OPTIONS = [
  { value: 'joined', label: '已加入' },
  { value: 'left', label: '已退出' },
  { value: 'unconfirmed', label: '待确认' },
] as const;

const LINKED_OPTIONS = [
  { value: 'all', label: '全部成员' },
  { value: 'linked', label: '已关联本地账号' },
  { value: 'unlinked', label: '未关联本地账号' },
] as const;

const query = reactive<{
  page: number;
  page_size: number;
  q: string;
  role: string;
  membership_state: string;
  linked: 'all' | 'linked' | 'unlinked';
}>({
  page: 1,
  page_size: 20,
  q: '',
  role: '',
  membership_state: 'joined',
  linked: 'all',
});

const searchDraft = ref('');
const openFilter = ref<string | null>(null);
const loading = ref(false);
const error = ref('');
const items = ref<TeamMemberDTO[]>([]);
const total = ref(0);
const facets = ref<TeamFacets>({});

const { widths, total: tableWidth, resize, resizeWithKeyboard } = useColumnWidths({
  defaults: [210, 140, 88, 96, 156, 126, 194],
  storageKey: 'turb_team_members_column_widths_v2',
  min: 80,
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

const activeFilterChips = computed(() => {
  const chips: Array<{ key: string; label: string; removeLabel: string }> = [];
  if (query.q) {
    chips.push({ key: 'q', label: `关键词：${query.q}`, removeLabel: '清除关键词筛选' });
  }
  if (query.linked !== 'all') {
    const label = LINKED_OPTIONS.find(o => o.value === query.linked)?.label ?? query.linked;
    chips.push({ key: 'linked', label: `本地账号：${label}`, removeLabel: '清除本地账号筛选' });
  }
  if (query.role) {
    chips.push({ key: 'role', label: `角色：${teamRoleLabel(query.role)}`, removeLabel: '清除角色筛选' });
  }
  if (query.membership_state !== 'joined') {
    const label = MEMBERSHIP_STATE_OPTIONS.find(o => o.value === query.membership_state)?.label ?? teamMembershipLabel(query.membership_state);
    chips.push({ key: 'membership_state', label: `成员状态：${label}`, removeLabel: '恢复默认仅查看已加入' });
  }
  return chips;
});

const isFiltered = computed(() => activeFilterChips.value.length > 0);

function removeFilter(key: string): void {
  if (key === 'q') {
    clearTimeout(searchTimer);
    searchDraft.value = '';
    query.q = '';
  } else if (key === 'linked') {
    query.linked = 'all';
  } else if (key === 'role') {
    query.role = '';
  } else if (key === 'membership_state') {
    query.membership_state = 'joined';
  }
  query.page = 1;
  void fetchMembers();
}

function clearAllFilters(): void {
  clearTimeout(searchTimer);
  searchDraft.value = '';
  query.q = '';
  query.role = '';
  query.membership_state = 'joined';
  query.linked = 'all';
  query.page = 1;
  void fetchMembers();
}

function applyLinked(value: 'all' | 'linked' | 'unlinked'): void {
  query.linked = value;
  query.page = 1;
  openFilter.value = null;
  void fetchMembers();
}

function applyRole(value: string): void {
  query.role = value;
  query.page = 1;
  openFilter.value = null;
  void fetchMembers();
}

function applyMembershipState(value: string): void {
  query.membership_state = value;
  query.page = 1;
  openFilter.value = null;
  void fetchMembers();
}

function clearSearch(): void {
  clearTimeout(searchTimer);
  searchDraft.value = '';
  if (query.q !== '') {
    query.q = '';
    query.page = 1;
    void fetchMembers();
  }
}

function handlePageChange(nextPage: number): void {
  query.page = nextPage;
  void fetchMembers();
}

function handleSizeChange(nextSize: number): void {
  query.page_size = nextSize;
  query.page = 1;
  void fetchMembers();
}

async function fetchMembers(options: { silent?: boolean; includeFacets?: 0 | 1 } = {}): Promise<void> {
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

  const requestQuery: TeamMembersQuery = {
    page: query.page,
    page_size: query.page_size,
    include_facets: String(options.includeFacets ?? 1) as '0' | '1',
    ...(query.q ? { q: query.q } : {}),
    ...(query.role ? { role: query.role as NonNullable<TeamMembersQuery['role']> } : {}),
    membership_state: (query.membership_state || 'joined') as NonNullable<TeamMembersQuery['membership_state']>,
    linked: query.linked,
  };

  try {
    const res = await props.api.listMembers(props.teamId, requestQuery, controller.signal);
    if (seq !== requestSeq) return;
    items.value = res.items;
    total.value = res.total;
    if (res.facets && Object.keys(res.facets).length > 0) {
      facets.value = res.facets;
    }
  } catch (err) {
    if (controller.signal.aborted || seq !== requestSeq) return;
    const message = err instanceof Error ? err.message : '加载工作区成员失败';
    if (!options.silent) {
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

watch(searchDraft, value => {
  clearTimeout(searchTimer);
  const trimmed = value.trim();
  if (trimmed === query.q) return;
  searchTimer = setTimeout(() => {
    query.q = trimmed;
    query.page = 1;
    void fetchMembers();
  }, 250);
});

watch(
  () => props.teamId,
  () => {
    query.page = 1;
    items.value = [];
    total.value = 0;
    facets.value = {};
    void fetchMembers();
  },
  { immediate: true },
);

watch(() => props.visible, active => {
  if (active) {
    void fetchMembers();
  } else {
    activeController?.abort();
    activeController = null;
    requestSeq += 1;
    loading.value = false;
  }
});

onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  activeController?.abort();
});

defineExpose({
  refresh: () => fetchMembers(),
});
</script>

<template>
  <section class="ui-list" aria-label="工作区成员列表">
    <ListToolbar :filtered="isFiltered">
      <span class="ui-list-count">共 {{ total.toLocaleString() }} 名成员</span>

      <div class="tm-search-box">
        <svg class="tm-search-box__icon" viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="7" cy="7" r="4.5" />
          <path d="m10.5 10.5 3 3" />
        </svg>
        <input
          v-model="searchDraft"
          type="search"
          aria-label="搜索工作区成员"
          placeholder="搜索邮箱 / 显示名 / 本地 ID"
          @keydown.enter.prevent="query.q = searchDraft.trim(); query.page = 1; void fetchMembers()"
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
          class="tm-btn ui-refresh-button"
          :disabled="loading"
          @click="void fetchMembers()"
        >
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </template>
    </ListToolbar>

    <div class="ui-table-wrap ui-table-scroll" tabindex="0" aria-label="成员表格，可横向滚动" :aria-busy="loading">
      <table class="ui-table ui-table--sticky-end ui-table--cards" :style="{ '--ui-table-width': `${tableWidth}px` }">
        <caption class="ui-sr-only">工作区已同步成员列表</caption>
        <colgroup>
          <col v-for="(width, idx) in widths" :key="idx" :style="{ width: `${width}px` }" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">
              成员
              <ColumnResizer label="成员" @start="resize(0, $event)" @nudge="resizeWithKeyboard(0, $event)" />
            </th>
            <th scope="col">
              <FilterPopover
                label="本地账号"
                :active="query.linked !== 'all'"
                :summary="LINKED_OPTIONS.find(o => o.value === query.linked)?.label"
                :open="visible && openFilter === 'linked'"
                @update:open="openFilter = $event ? 'linked' : null"
              >
                <fieldset class="list-filter-options">
                  <legend class="ui-sr-only">本地账号关联筛选</legend>
                  <label v-for="opt in LINKED_OPTIONS" :key="opt.value" class="list-filter-option">
                    <input
                      type="radio"
                      name="member-linked"
                      :value="opt.value"
                      :checked="query.linked === opt.value"
                      @change="applyLinked(opt.value)"
                    />
                    <span>{{ opt.label }}</span>
                    <small v-if="facetCount('linked', opt.value) !== null">{{ facetCount('linked', opt.value) }}</small>
                  </label>
                </fieldset>
                <div class="list-filter-actions">
                  <button type="button" @click="applyLinked('all')">重置</button>
                  <button type="button" class="list-filter-primary" @click="openFilter = null">完成</button>
                </div>
              </FilterPopover>
              <ColumnResizer label="本地账号" @start="resize(1, $event)" @nudge="resizeWithKeyboard(1, $event)" />
            </th>
            <th scope="col">
              <FilterPopover
                label="角色"
                :active="Boolean(query.role)"
                :summary="query.role ? teamRoleLabel(query.role) : ''"
                :open="visible && openFilter === 'role'"
                @update:open="openFilter = $event ? 'role' : null"
              >
                <fieldset class="list-filter-options">
                  <legend class="ui-sr-only">成员角色筛选</legend>
                  <label class="list-filter-option">
                    <input type="radio" name="member-role" value="" :checked="!query.role" @change="applyRole('')" />
                    <span>全部角色</span>
                  </label>
                  <label v-for="opt in ROLE_OPTIONS" :key="opt.value" class="list-filter-option">
                    <input
                      type="radio"
                      name="member-role"
                      :value="opt.value"
                      :checked="query.role === opt.value"
                      @change="applyRole(opt.value)"
                    />
                    <span>{{ opt.label }}</span>
                    <small v-if="facetCount('role', opt.value) !== null">{{ facetCount('role', opt.value) }}</small>
                  </label>
                </fieldset>
                <div class="list-filter-actions">
                  <button type="button" @click="applyRole('')">清除</button>
                  <button type="button" class="list-filter-primary" @click="openFilter = null">完成</button>
                </div>
              </FilterPopover>
              <ColumnResizer label="角色" @start="resize(2, $event)" @nudge="resizeWithKeyboard(2, $event)" />
            </th>
            <th scope="col">
              <FilterPopover
                label="成员状态"
                :active="query.membership_state !== 'joined'"
                :summary="MEMBERSHIP_STATE_OPTIONS.find(o => o.value === query.membership_state)?.label"
                :open="visible && openFilter === 'membership_state'"
                @update:open="openFilter = $event ? 'membership_state' : null"
              >
                <fieldset class="list-filter-options">
                  <legend class="ui-sr-only">成员状态筛选</legend>
                  <label v-for="opt in MEMBERSHIP_STATE_OPTIONS" :key="opt.value" class="list-filter-option">
                    <input
                      type="radio"
                      name="member-state"
                      :value="opt.value"
                      :checked="query.membership_state === opt.value"
                      @change="applyMembershipState(opt.value)"
                    />
                    <span>{{ opt.label }}</span>
                    <small v-if="facetCount('membership_state', opt.value) !== null">{{ facetCount('membership_state', opt.value) }}</small>
                  </label>
                </fieldset>
                <div class="list-filter-actions">
                  <button type="button" @click="applyMembershipState('joined')">恢复已加入</button>
                  <button type="button" class="list-filter-primary" @click="openFilter = null">完成</button>
                </div>
              </FilterPopover>
              <ColumnResizer label="成员状态" @start="resize(3, $event)" @nudge="resizeWithKeyboard(3, $event)" />
            </th>
            <th scope="col">
              加入时间
              <ColumnResizer label="加入时间" @start="resize(4, $event)" @nudge="resizeWithKeyboard(4, $event)" />
            </th>
            <th scope="col">
              最近任务
              <ColumnResizer label="最近任务" @start="resize(5, $event)" @nudge="resizeWithKeyboard(5, $event)" />
            </th>
            <th scope="col">操作</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="member in items" :key="member.id">
            <td data-label="成员">
              <div class="tm-cell-stack">
                <div class="tm-cell-primary">
                  <span :title="member.email || undefined">{{ member.email || '未返回' }}</span>
                </div>
                <div class="tm-cell-sub">
                  {{ (member.remote_user_id ? `远端 ID：${member.remote_user_id}` : '—') }}
                </div>
              </div>
            </td>

            <td data-label="本地账号">
              <div v-if="member.account" class="tm-cell-stack">
                <div class="tm-cell-primary">
                  <button
                    type="button"
                    class="tm-link-btn tm-tabular"
                    @click="callbacks.openAccountDetail(member.account.id)"
                  >
                    #{{ member.account.id }}
                  </button>
                  <span v-if="member.account.archived" class="tm-badge tm-badge--neutral">已归档</span>
                </div>
                <div v-if="member.account.email && member.account.email !== member.email" class="tm-cell-sub">
                  {{ member.account.email }}
                </div>
              </div>
              <span v-else class="tm-badge tm-badge--neutral">外部成员</span>
            </td>

            <td data-label="角色">
              <span class="tm-badge" :class="badgeClass(teamRoleTone(member.role))">
                {{ teamRoleLabel(member.role) }}
              </span>
            </td>

            <td data-label="成员状态">
              <div class="tm-cell-stack">
                <div class="tm-cell-primary">
                  <span class="tm-badge" :class="badgeClass(teamMembershipTone(member.membership_state))">
                    {{ teamMembershipLabel(member.membership_state) }}
                  </span>
                </div>
                <div class="tm-cell-sub">
                  {{ member.last_verified_at ? `核验 ${callbacks.formatDateTime(member.last_verified_at)}` : '待核验' }}
                </div>
              </div>
            </td>

            <td data-label="加入时间">
              <span class="ui-time">
                {{ member.joined_at ? callbacks.formatDateTime(member.joined_at) : '未返回' }}
              </span>
            </td>

            <td data-label="最近任务">
              <button
                v-if="member.latest_task?.task_id"
                type="button"
                class="tm-link-btn tm-tabular"
                @click="callbacks.openTask(member.latest_task!.task_id!, member.latest_task?.run_id)"
              >
                任务 #{{ member.latest_task?.task_id }}
              </button>
              <span v-else class="tm-cell-sub">—</span>
            </td>

            <td data-label="操作">
              <div class="tm-row-actions">
                <button
                  v-if="member.account"
                  type="button"
                  class="tm-btn tm-btn--sm"
                  @click="callbacks.openAccountDetail(member.account.id)"
                >
                  查看本地账号
                </button>
                <button
                  v-if="member.latest_task?.task_id"
                  type="button"
                  class="tm-btn tm-btn--sm"
                  @click="callbacks.openTask(member.latest_task!.task_id!, member.latest_task?.run_id)"
                >
                  查看任务
                </button>
                <span v-if="!member.account && !member.latest_task?.task_id" class="tm-cell-sub">—</span>
              </div>
            </td>
          </tr>

          <TableState
            v-if="!items.length"
            :colspan="7"
            :loading="loading"
            :error="error"
            loading-title="正在加载工作区成员"
            loading-text="读取已同步的工作区成员与本地账号关联关系"
            error-title="加载工作区成员失败"
            :title="isFiltered ? '没有匹配的成员记录' : '暂无已同步成员'"
            :text="isFiltered ? '可调整搜索词或筛选条件后重新查询。' : '点击上方「同步」从工作区拉取最新成员名单。'"
            retry-label="重试"
            @retry="void fetchMembers()"
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
      label="成员列表分页"
      @update:page="handlePageChange"
      @update:size="handleSizeChange"
    />
  </section>
</template>
