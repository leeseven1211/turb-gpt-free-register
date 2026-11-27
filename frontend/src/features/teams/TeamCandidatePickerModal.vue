<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { TeamApiError, type TeamsApi } from '../../api/teams';
import { useNativeDialog } from '../../shared/useNativeDialog';
import type {
  TeamCandidateDTO,
  TeamCandidatesQuery,
  TeamDTO,
  TeamDecimalId,
} from './contracts';
import {
  teamReasonLabel,
} from './statusLabels';

const props = defineProps<{
  open: boolean;
  api: TeamsApi;
  team: TeamDTO | null;
  visible: boolean;
}>();

const emit = defineEmits<{
  close: [];
  confirmCandidates: [
    payload: { accountIds: string[]; expectedEmails: Record<string, string> },
  ];
  openAdvancedInAccounts: [team: { team_id: string; effective_name: string }];
  notify: [message: string];
}>();

const dialogRef = ref<HTMLDialogElement>();
useNativeDialog(dialogRef, () => props.open && props.visible, () => props.visible);

const searchQuery = ref('');
const scopeUnassignedOnly = ref(true);
const filterHasToken = ref(false);
const filterHasPassword = ref(false);
const filterTotpEnabled = ref(false);
const filterIncludeArchived = ref(false);

const page = ref(1);
const pageSize = 20;
const total = ref(0);
const loading = ref(false);
const loadError = ref('');
const items = ref<TeamCandidateDTO[]>([]);

const selectedIds = ref<TeamDecimalId[]>([]);
const expectedEmails = reactive<Record<string, string>>({});

const showPastePanel = ref(false);
const pasteText = ref('');
const resolving = ref(false);
const resolveError = ref('');
const resolveSummary = ref<{
  matchedSelectable: number;
  matchedIneligible: Array<{ email: string; account_id: string; reason: string }>;
  notFound: string[];
  ambiguous: Array<{ input: string; candidates: TeamCandidateDTO[] }>;
} | null>(null);

let loadController: AbortController | null = null;
let resolveController: AbortController | null = null;
let searchTimer: number | null = null;

const isActiveDialog = computed(() => props.open && props.visible);
const selectedSet = computed(() => new Set(selectedIds.value));
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));
const selectableOnPage = computed(() =>
  items.value.filter(row => !row.disabled),
);
const allPageSelectableChecked = computed(
  () =>
    selectableOnPage.value.length > 0 &&
    selectableOnPage.value.every(row => selectedSet.value.has(row.account.id)),
);

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

function abortRequests() {
  if (searchTimer !== null) {
    window.clearTimeout(searchTimer);
    searchTimer = null;
  }
  if (loadController) {
    loadController.abort();
    loadController = null;
  }
  if (resolveController) {
    resolveController.abort();
    resolveController = null;
  }
  loading.value = false;
  resolving.value = false;
}

function clearSelection() {
  selectedIds.value = [];
  for (const key of Object.keys(expectedEmails)) {
    delete expectedEmails[key];
  }
}

function resetState() {
  abortRequests();
  searchQuery.value = '';
  scopeUnassignedOnly.value = true;
  filterHasToken.value = false;
  filterHasPassword.value = false;
  filterTotpEnabled.value = false;
  filterIncludeArchived.value = false;
  page.value = 1;
  total.value = 0;
  items.value = [];
  loadError.value = '';
  clearSelection();
  showPastePanel.value = false;
  pasteText.value = '';
  resolveError.value = '';
  resolveSummary.value = null;
}

function buildCandidatesQuery(): TeamCandidatesQuery {
  return {
    page: page.value,
    page_size: pageSize,
    ...(searchQuery.value.trim() ? { q: searchQuery.value.trim() } : {}),
    scope: scopeUnassignedOnly.value ? 'unassigned' : 'all',
    archived: filterIncludeArchived.value ? 'all' : '0',
    ...(filterHasToken.value ? { has_access_token: 'true' } : {}),
    ...(filterHasPassword.value ? { has_password: 'true' } : {}),
    ...(filterTotpEnabled.value ? { totp_enabled: 'true' } : {}),
  };
}

async function fetchCandidates() {
  if (!isActiveDialog.value || !props.team) return;
  if (loadController) loadController.abort();
  const controller = new AbortController();
  loadController = controller;
  loading.value = true;
  loadError.value = '';

  try {
    const res = await props.api.listCandidates(
      props.team.id,
      buildCandidatesQuery(),
      controller.signal,
    );
    if (controller.signal.aborted || !isActiveDialog.value) return;
    items.value = res.items;
    total.value = res.total;
  } catch (err) {
    if (isAbortError(err) || controller.signal.aborted) return;
    loadError.value =
      err instanceof TeamApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : '加载候选账号失败';
  } finally {
    if (loadController === controller) {
      loadController = null;
      loading.value = false;
    }
  }
}

function triggerFilterReload() {
  page.value = 1;
  void fetchCandidates();
}

function scheduleSearch() {
  if (searchTimer !== null) window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    searchTimer = null;
    triggerFilterReload();
  }, 260);
}

function clearSearch() {
  searchQuery.value = '';
  triggerFilterReload();
}

function addSelection(accountId: TeamDecimalId, email: string | null) {
  if (!selectedSet.value.has(accountId)) {
    selectedIds.value = [...selectedIds.value, accountId];
  }
  if (email && !Object.hasOwn(expectedEmails, accountId)) {
    expectedEmails[accountId] = email;
  }
}

function removeSelection(accountId: TeamDecimalId) {
  if (selectedSet.value.has(accountId)) {
    selectedIds.value = selectedIds.value.filter(id => id !== accountId);
  }
  delete expectedEmails[accountId];
}

function toggleCandidate(accountId: TeamDecimalId, email: string | null, selectable: boolean) {
  if (!selectable) return;
  if (selectedSet.value.has(accountId)) {
    removeSelection(accountId);
  } else {
    addSelection(accountId, email);
  }
}

function toggleSelectAllPage() {
  if (allPageSelectableChecked.value) {
    const pageIdSet = new Set(selectableOnPage.value.map(r => r.account.id));
    selectedIds.value = selectedIds.value.filter(id => !pageIdSet.has(id));
    for (const id of pageIdSet) delete expectedEmails[id];
  } else {
    for (const row of selectableOnPage.value) {
      addSelection(row.account.id, row.account.email);
    }
  }
}

function rowReasonText(row: TeamCandidateDTO): string {
  if (row.category === 'another_team' && row.other_teams.length) {
    return `已归属「${row.other_teams.map(team => team.display_name || team.name || team.workspace_id).join('、')}」`;
  }
  return row.reason_code ? teamReasonLabel(row.reason_code) : badgeFor(row.category).label;
}

function badgeFor(state: TeamCandidateDTO['category']) {
  const badges = {
    new: { label: '可加入', tone: 'success' },
    resume_invite: { label: '可续邀请', tone: 'active' },
    already_member: { label: '已是成员', tone: 'neutral' },
    same_team_active: { label: '执行中可复用', tone: 'active' },
    another_team: { label: '已属其他Team', tone: 'warning' },
    missing_auth: { label: '缺认证材料', tone: 'danger' },
    unavailable: { label: '账号不可用', tone: 'danger' },
  };
  return badges[state] ?? { label: '状态待核对', tone: 'neutral' };
}

async function resolvePastedValues() {
  if (!props.team || resolving.value) return;
  const values = pasteText.value
    .split(/[\r\n,;，；\t ]+/)
    .map(item => item.trim())
    .filter(Boolean);
  if (!values.length) {
    resolveError.value = '请先粘贴邮箱地址或本地账号 ID';
    return;
  }

  if (resolveController) resolveController.abort();
  const controller = new AbortController();
  resolveController = controller;
  resolving.value = true;
  resolveError.value = '';

  try {
    const res = await props.api.resolveCandidates(
      props.team.id,
      values,
      controller.signal,
    );
    if (controller.signal.aborted || !isActiveDialog.value) return;

    let matchedSelectable = 0;
    const matchedIneligible: Array<{
      email: string;
      account_id: string;
      reason: string;
    }> = [];

    const notFound: string[] = [];
    const ambiguous: Array<{ input: string; candidates: TeamCandidateDTO[] }> = [];
    for (const item of res.items) {
      if (item.match_status === 'not_found') {
        notFound.push(item.input);
      } else if (item.match_status === 'ambiguous') {
        ambiguous.push({ input: item.input, candidates: item.candidates });
      } else {
        for (const row of item.candidates) {
          if (!row.disabled) {
            addSelection(row.account.id, row.account.email);
            matchedSelectable++;
          } else {
            matchedIneligible.push({ email: row.account.email || `#${row.account.id}`, account_id: row.account.id, reason: rowReasonText(row) });
          }
        }
      }
    }
    resolveSummary.value = { matchedSelectable, matchedIneligible, notFound, ambiguous };

    if (matchedSelectable > 0) {
      emit('notify', `已解析并勾选 ${matchedSelectable} 个可选账号`);
    }
  } catch (err) {
    if (isAbortError(err) || controller.signal.aborted) return;
    resolveError.value =
      err instanceof TeamApiError
        ? err.message
        : err instanceof Error
          ? err.message
          : '解析输入账号失败';
  } finally {
    if (resolveController === controller) {
      resolveController = null;
      resolving.value = false;
    }
  }
}

function goPage(nextPage: number) {
  if (nextPage < 1 || nextPage > totalPages.value || loading.value) return;
  page.value = nextPage;
  void fetchCandidates();
}

function openAdvancedAccounts() {
  if (!props.team) return;
  emit('openAdvancedInAccounts', {
    team_id: props.team.id,
    effective_name: props.team.display_name || props.team.name || props.team.workspace_id,
  });
}

function confirmNext() {
  if (!selectedIds.value.length) return;
  emit('confirmCandidates', {
    accountIds: [...selectedIds.value],
    expectedEmails: { ...expectedEmails },
  });
}

function requestClose() {
  abortRequests();
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
  () => [isActiveDialog.value, props.team?.id],
  ([active]) => {
    if (active) {
      resetState();
      void fetchCandidates();
    } else {
      abortRequests();
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  abortRequests();
});
</script>

<template>
  <dialog
    ref="dialogRef"
    class="tm-dialog tm-dialog--xl"
    aria-labelledby="teamCandidatePickerTitle"
    :aria-busy="loading || resolving"
    @cancel.prevent="requestClose"
    @click="onBackdropClick"
  >
    <div class="tm-dialog__head">
      <div>
        <p class="tm-dialog__kicker">CANDIDATE PICKER</p>
        <h3 id="teamCandidatePickerTitle" class="tm-dialog__title">
          选择待加入账号
        </h3>
        <p class="tm-dialog__desc">
          <template v-if="team">
            目标 Team：<strong>{{ team.display_name || team.name || team.workspace_id }}</strong>
            （<span class="tm-mono">{{ team.workspace_id }}</span>），默认聚焦未归属任何 Team 的账号。
          </template>
        </p>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <button
          type="button"
          class="tm-btn tm-btn--soft tm-btn--sm"
          :disabled="!team"
          @click="openAdvancedAccounts"
        >
          去账号页高级筛选选人 →
        </button>
        <button
          type="button"
          class="tm-dialog__close"
          aria-label="关闭候选选人器"
          @click="requestClose"
        >
          ×
        </button>
      </div>
    </div>

    <div class="tm-dialog__body">
      <!-- 搜索与快捷过滤胶囊 -->
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
        <div class="tm-search-box" style="flex: 1 1 260px; max-width: 340px;">
          <svg class="tm-search-box__icon" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
          <input
            v-model="searchQuery"
            type="search"
            placeholder="搜索候选账号邮箱或 #ID…"
            aria-label="搜索候选账号"
            @input="scheduleSearch"
            @keydown.enter.prevent="triggerFilterReload"
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

        <button
          type="button"
          class="tm-btn tm-btn--sm"
          @click="showPastePanel = !showPastePanel"
        >
          {{ showPastePanel ? '收起批量粘贴解析' : '批量粘贴邮箱或账号 ID' }}
        </button>
      </div>

      <div class="tm-filter-pills" role="group" aria-label="候选筛选条件">
        <button
          type="button"
          class="tm-pill-toggle"
          :class="{ 'is-active': scopeUnassignedOnly }"
          @click="
            scopeUnassignedOnly = !scopeUnassignedOnly;
            triggerFilterReload();
          "
        >
          仅未归属任何 Team
        </button>
        <button
          type="button"
          class="tm-pill-toggle"
          :class="{ 'is-active': filterHasToken }"
          @click="
            filterHasToken = !filterHasToken;
            triggerFilterReload();
          "
        >
          有 Token
        </button>
        <button
          type="button"
          class="tm-pill-toggle"
          :class="{ 'is-active': filterHasPassword }"
          @click="
            filterHasPassword = !filterHasPassword;
            triggerFilterReload();
          "
        >
          有密码
        </button>
        <button
          type="button"
          class="tm-pill-toggle"
          :class="{ 'is-active': filterTotpEnabled }"
          @click="
            filterTotpEnabled = !filterTotpEnabled;
            triggerFilterReload();
          "
        >
          已启用 2FA
        </button>
        <button
          type="button"
          class="tm-pill-toggle"
          :class="{ 'is-active': filterIncludeArchived }"
          @click="
            filterIncludeArchived = !filterIncludeArchived;
            triggerFilterReload();
          "
        >
          包含归档账号
        </button>
      </div>

      <!-- 批量粘贴邮箱或账号 ID 解析面板 -->
      <section
        v-if="showPastePanel"
        style="padding: 12px 14px; border: 1px solid var(--ui-color-border); border-radius: 9px; background: var(--ui-color-surface-subtle); display: grid; gap: 10px;"
      >
        <div class="tm-field">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span class="tm-field__label">粘贴多行或逗号分隔的邮箱 / 本地账号 ID</span>
            <span class="tm-field__hint">仅查询本地账号集合，不触发登录或远端请求</span>
          </div>
          <textarea
            v-model="pasteText"
            rows="3"
            placeholder="例如：&#10;user-a@example.com&#10;1024, 1025"
            :disabled="resolving"
          />
        </div>

        <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
          <span v-if="resolveError" style="color: var(--ui-color-danger, #b91c1c); font-size: 12px;">
            {{ resolveError }}
          </span>
          <span v-else class="tm-field__hint">系统将自动识别可选账号并勾选，列出未命中与同名冲突项</span>
          <button
            type="button"
            class="tm-btn tm-btn--soft tm-btn--sm"
            :disabled="resolving"
            @click="resolvePastedValues"
          >
            {{ resolving ? '解析中…' : '解析并勾选' }}
          </button>
        </div>

        <div
          v-if="resolveSummary"
          style="display: grid; gap: 8px; padding-top: 8px; border-top: 1px solid var(--ui-color-border); font-size: 12px;"
        >
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <span>
              自动勾选可选：<strong>{{ resolveSummary.matchedSelectable }}</strong> 个
            </span>
            <span v-if="resolveSummary.matchedIneligible.length">
              不可选跳过：<strong>{{ resolveSummary.matchedIneligible.length }}</strong> 个
            </span>
            <span v-if="resolveSummary.notFound.length">
              未找到：<strong>{{ resolveSummary.notFound.length }}</strong> 项
            </span>
            <span v-if="resolveSummary.ambiguous.length">
              同名冲突：<strong>{{ resolveSummary.ambiguous.length }}</strong> 项
            </span>
          </div>

          <div
            v-if="resolveSummary.matchedIneligible.length"
            style="display: grid; gap: 3px; color: var(--ui-color-text-secondary);"
          >
            <strong>不可选明细：</strong>
            <div
              v-for="skip in resolveSummary.matchedIneligible"
              :key="`skip:${skip.account_id}`"
            >
              {{ skip.email }} (#{{ skip.account_id }}) — {{ skip.reason }}
            </div>
          </div>

          <div v-if="resolveSummary.notFound.length" style="color: var(--ui-color-danger, #b91c1c);">
            未找到项：{{ resolveSummary.notFound.join('、') }}
          </div>

          <div v-if="resolveSummary.ambiguous.length" style="display: grid; gap: 6px;">
            <strong>同名/多匹配冲突（请手工核对具体 #account_id 后勾选）：</strong>
            <div
              v-for="amb in resolveSummary.ambiguous"
              :key="amb.input"
              style="padding: 8px 10px; border: 1px solid var(--ui-color-border); border-radius: 7px; background: var(--ui-color-surface); display: grid; gap: 5px;"
            >
              <div>输入项：<span class="tm-mono">{{ amb.input }}</span></div>
              <label
                v-for="cand in amb.candidates"
                :key="cand.account.id"
                style="display: flex; align-items: center; gap: 8px;"
              >
                <input
                  type="checkbox"
                  :checked="selectedSet.has(cand.account.id)"
                  :disabled="cand.disabled"
                  @change="toggleCandidate(cand.account.id, cand.account.email, !cand.disabled)"
                />
                <span>{{ cand.account.email }}</span>
                <span class="tm-mono">#{{ cand.account.id }}</span>
                <span v-if="cand.account.archived" class="tm-badge tm-badge--neutral">已归档</span>
                <span
                  class="tm-badge"
                  :class="`tm-badge--${badgeFor(cand.category).tone}`"
                >
                  {{ badgeFor(cand.category).label }}
                </span>
                <span
                  v-if="cand.disabled && cand.reason_code"
                  class="tm-field__hint"
                >
                  {{ rowReasonText(cand) }}
                </span>
              </label>
            </div>
          </div>
        </div>
      </section>

      <div v-if="loadError" class="tm-banner tm-banner--danger" role="alert">
        <div class="tm-banner__copy">{{ loadError }}</div>
        <button type="button" class="tm-btn tm-btn--sm" @click="fetchCandidates">重试</button>
      </div>

      <!-- 候选账号列表 -->
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; font-size: 12px;">
        <button
          type="button"
          class="tm-link-btn"
          :disabled="!selectableOnPage.length"
          @click="toggleSelectAllPage"
        >
          {{ allPageSelectableChecked ? '取消勾选本页可选' : `全选本页可选 (${selectableOnPage.length})` }}
        </button>
        <span class="tm-field__hint tm-tabular">
          共 {{ total }} 条候选 · 第 {{ page }} / {{ totalPages }} 页
        </span>
      </div>

      <div class="tm-candidate-list" :aria-busy="loading">
        <div
          v-if="loading && !items.length"
          style="padding: 24px; text-align: center; color: var(--ui-color-text-secondary);"
        >
          正在加载候选账号…
        </div>
        <div
          v-else-if="!items.length"
          style="padding: 24px; text-align: center; color: var(--ui-color-text-secondary);"
        >
          当前筛选条件下暂无候选账号，可放宽筛选或使用批量粘贴。
        </div>
        <label
          v-for="row in items"
          :key="row.account.id"
          class="tm-candidate-row"
          :class="{ 'is-disabled': row.disabled }"
        >
          <div class="tm-candidate-row__left" style="min-width: 0; flex: 1;">
            <input
              type="checkbox"
              :checked="selectedSet.has(row.account.id)"
              :disabled="row.disabled"
              @change="toggleCandidate(row.account.id, row.account.email, !row.disabled)"
            />
            <div class="tm-cell-stack" style="min-width: 0;">
              <div class="tm-cell-primary" style="flex-wrap: wrap;">
                <span>{{ row.account.email }}</span>
                <span class="tm-mono" style="color: var(--ui-color-text-muted);">#{{ row.account.id }}</span>
                <span v-if="row.account.archived" class="tm-badge tm-badge--neutral">已归档</span>
                <span v-if="row.has_access_token" class="tm-badge tm-badge--success">Token</span>
                <span v-if="row.has_password" class="tm-badge tm-badge--neutral">密码</span>
                <span v-if="row.totp_enabled" class="tm-badge tm-badge--neutral">2FA</span>
                <span v-if="row.email_status === 'invalid'" class="tm-badge tm-badge--danger">邮箱失效</span>
              </div>
              <div
                v-if="row.disabled || row.other_teams.length"
                class="tm-cell-sub"
              >
                {{ rowReasonText(row) }}
              </div>
            </div>
          </div>

          <div style="display: flex; align-items: center; gap: 6px; flex: none;">
            <span
              v-if="row.category === 'another_team' && row.other_teams.length"
              class="tm-badge tm-badge--warning"
            >
              {{ row.other_teams.map(team => team.display_name || team.name || team.workspace_id).join('、') }}
            </span>
            <span
              class="tm-badge"
              :class="`tm-badge--${badgeFor(row.category).tone}`"
            >
              {{ badgeFor(row.category).label }}
            </span>
          </div>
        </label>
      </div>

      <!-- 分页 -->
      <div
        v-if="totalPages > 1"
        style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;"
      >
        <button
          type="button"
          class="tm-btn tm-btn--sm"
          :disabled="page <= 1 || loading"
          @click="goPage(page - 1)"
        >
          上一页
        </button>
        <span class="tm-field__hint tm-tabular">{{ page }} / {{ totalPages }}</span>
        <button
          type="button"
          class="tm-btn tm-btn--sm"
          :disabled="page >= totalPages || loading"
          @click="goPage(page + 1)"
        >
          下一页
        </button>
      </div>
    </div>

    <div class="tm-dialog__foot">
      <div style="display: flex; align-items: center; gap: 10px;">
        <strong class="tm-tabular">已选 {{ selectedIds.length }} 个候选账号</strong>
        <button
          type="button"
          class="tm-link-btn"
          :disabled="!selectedIds.length"
          @click="clearSelection"
        >
          清空已选
        </button>
      </div>
      <div class="tm-dialog__foot-right">
        <button type="button" class="tm-btn" @click="requestClose">取消</button>
        <button
          type="button"
          class="tm-btn tm-btn--primary"
          :disabled="!selectedIds.length"
          @click="confirmNext"
        >
          下一步：本地预览与席位核对
        </button>
      </div>
    </div>
  </dialog>
</template>
