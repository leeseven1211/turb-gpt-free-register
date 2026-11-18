<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import CursorPagination from '../../components/CursorPagination.vue';
import FilterPopover from '../../components/FilterPopover.vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import type { BulkListDependencies, BulkNavigation, BulkRecord } from './contracts';
import { useBulkList, type BulkListFilter } from './useBulkList';

const props = defineProps<{ navigation: BulkNavigation; deps: BulkListDependencies }>();
const list = useBulkList(() => props.navigation, props.deps);
const { navigation, items, summary, nextCursor, loading, visible, error, hasPrevious, stale } = list;
const openFilter = ref<string | null>(null),
  draftSearch = ref(''),
  tableHost = ref<HTMLElement>();
const operations: Record<string, string> = {
  plan_check: '查询套餐',
  token_refresh: '刷新 AT',
  password_setup: '补密码',
  twofa_setup: '补 2FA',
  codex_retry: '补 Codex',
  account_completion: '组合补全',
};
const states: Record<string, string> = {
  active: '执行中',
  paused: '已暂停',
  cancel_requested: '取消中',
  stop_requested: '停止中',
  ended: '已结束',
};
const statusLabels: Record<string, string> = {
  ...states,
  settling: '汇总中',
  completed: '已完成',
  preparing: '准备中',
};
const terminal = ['success', 'partial_success', 'failed', 'not_executed', 'cancelled'];
const failedAliases = ['attention_required', 'request_unknown', 'manual_reconcile', 'unknown', 'unconfirmed'];
function object(value: unknown): BulkRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as BulkRecord) : {};
}
function count(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}
function text(value: unknown, fallback = '—'): string {
  return value == null || value === '' ? fallback : String(value);
}
const rows = computed(() =>
  items.value.map((item) => {
    const rawCounts = object(item.summary ?? item.counts),
      counts: Record<string, number> = {};
    for (const [key, value] of Object.entries(rawCounts))
      if (count(value) !== null) counts[key] = value as number;
    const total = count(item.target_count);
    const known = total === 0 || Object.keys(counts).length > 0;
    for (const alias of failedAliases) {
      if (alias in counts) {
        counts.failed = (counts.failed || 0) + counts[alias]!;
        delete counts[alias];
      }
    }
    const control = object(item.control),
      operation = object(item.operation);
    const paused = Boolean(control.paused ?? item.is_paused);
    const state = paused ? 'paused' : text(control.state ?? item.control_state ?? item.state, 'preparing');
    const key = text(operation.key ?? item.operation_key ?? item.action_key);
    const id = item.id;
    const done = known ? terminal.reduce((sum, value) => sum + (counts[value] || 0), 0) : null;
    const percent =
      total === null || done === null
        ? null
        : total === 0
          ? 0
          : Math.min(100, Math.round((100 * done) / total));
    return {
      id,
      name: text(item.name ?? item.title, `批次 #${id}`),
      operation: operations[key] || key,
      state,
      status: statusLabels[state] || state,
      counts,
      known,
      done,
      total,
      percent,
      createdAt: props.deps.callbacks.formatDateTime(item.created_at),
    };
  }),
);
const totalBatches = computed(() => count(summary.value.total_batches));
const countLabel = computed(() => {
  if (stale.value) return loading.value ? '正在读取批次数量…' : '批次数量未知';
  return totalBatches.value === null
    ? `本页 ${items.value.length} 个批次`
    : `${totalBatches.value.toLocaleString()} 个批次`;
});
const kpis = computed(() => {
  const values = [
    { key: 'active_batches', label: '执行中', value: count(summary.value.active_batches), unit: '批' },
    { key: 'ended_batches', label: '已结束', value: count(summary.value.ended_batches), unit: '批' },
    { key: 'failed_targets', label: '失败账号', value: count(summary.value.failed_targets), unit: '个' },
  ];
  const oldFailed = count(summary.value.attention_targets);
  if (oldFailed != null && values[2]!.value != null) values[2]!.value! += oldFailed;
  return values.filter((value) => value.value !== null);
});
const chips = computed(() => {
  const nav = navigation.value;
  const values = [
    ['q', nav.q ? `批次：${nav.q}` : ''],
    ['operation', nav.operation ? `操作：${operations[nav.operation] || nav.operation}` : ''],
    ['state', nav.state ? `状态：${states[nav.state] || nav.state}` : ''],
    [
      'date',
      nav.created_from || nav.created_to
        ? `创建日期：${nav.created_from || '不限'} 至 ${nav.created_to || '不限'}`
        : '',
    ],
  ];
  return values
    .filter(([, value]) => value)
    .map(([key, label]) => ({ key: key!, label: label!, removeLabel: `移除${label}` }));
});
watch(
  () => navigation.value.q,
  (value) => {
    draftSearch.value = value || '';
  },
  { immediate: true },
);
watch(
  () => props.navigation.view,
  () => {
    openFilter.value = null;
  },
);
function removeFilter(key: string) {
  if (key === 'date') void list.applyFilters({ created_from: '', created_to: '' });
  else void list.applyFilters({ [key as BulkListFilter]: '' });
}
function filter(key: BulkListFilter, value: string) {
  void list.applyFilters({ [key]: value });
}
function search() {
  void list.applyFilters({ q: draftSearch.value.trim() });
  openFilter.value = null;
}
function open(id: string, resultState?: string) {
  if (!visible.value || stale.value) return;
  props.deps.callbacks.navigate('detail', {
    batch_id: id,
    ...(resultState ? { result_state: resultState } : {}),
  });
}
function report(id: string) {
  if (visible.value && !stale.value) props.deps.callbacks.navigate('detail', { batch_id: id }, true);
}
function canRender() {
  const selection = window.getSelection();
  return stale.value || !(selection?.toString() && tableHost.value?.contains(selection.anchorNode));
}
async function refresh(poll = false) {
  if (canRender()) await list.refresh(poll, canRender);
}
function setVisible(value: boolean) {
  if (!value) openFilter.value = null;
  list.setVisible(value);
}
defineExpose({ refresh, setVisible });
</script>
<template>
  <section class="bl-root" aria-label="批次列表" :aria-busy="loading">
    <div v-if="kpis.length" class="bl-kpis">
      <div
        v-for="kpi in kpis"
        :key="kpi.key"
        class="bl-kpi"
        :class="{ 'is-warning': kpi.key === 'failed_targets' && !!kpi.value }"
      >
        <span>{{ kpi.label }}</span
        ><strong
          >{{ kpi.value }}<small>{{ kpi.unit }}</small></strong
        >
      </div>
    </div>
    <div class="bl-toolbar">
      <div class="bl-toolbar-main">
        <span class="bl-count" role="status">{{ countLabel }}</span
        ><ListFilterSummary :items="chips" @remove="removeFilter" />
      </div>
      <button v-if="chips.length" type="button" class="bl-link" @click="list.resetFilters">清除筛选</button>
    </div>
    <div v-if="error" class="bl-error" role="alert">
      <span>{{ error }}</span
      ><button type="button" class="bl-link" :disabled="loading" @click="list.refresh()">重试</button
      ><button
        v-if="stale && navigation.cursor"
        class="bl-link"
        type="button"
        :disabled="loading"
        @click="list.first"
      >
        返回首页</button
      ><button
        v-if="stale && hasPrevious"
        class="bl-link"
        type="button"
        :disabled="loading"
        @click="list.previous"
      >
        上一页
      </button>
    </div>
    <div ref="tableHost" class="bl-table-wrap" tabindex="0" role="region" aria-label="批次列表内容">
      <table class="bl-table">
        <thead>
          <tr>
            <th class="bl-col-name">
              <FilterPopover
                label="批次名称或编号"
                trigger-label="批次"
                :active="!!navigation.q"
                :summary="navigation.q"
                :open="openFilter === 'q'"
                @update:open="openFilter = $event ? 'q' : null"
                ><form class="bl-filter-fields" @submit.prevent="search">
                  <label
                    >名称或批次号<input
                      v-model="draftSearch"
                      type="search"
                      placeholder="搜索批次名称或编号"
                      autocomplete="off"
                  /></label>
                  <div class="bl-filter-actions">
                    <button type="button" @click="removeFilter('q')">清除此列</button
                    ><button type="submit">查询</button>
                  </div>
                </form></FilterPopover
              >
            </th>
            <th>
              <FilterPopover
                label="操作类型"
                :active="!!navigation.operation"
                :summary="operations[navigation.operation || ''] || navigation.operation"
                :open="openFilter === 'operation'"
                @update:open="openFilter = $event ? 'operation' : null"
                ><fieldset class="bl-filter-options">
                  <legend class="bl-sr-only">操作类型</legend>
                  <label
                    ><input
                      type="radio"
                      name="bulk-list-operation"
                      value=""
                      :checked="!navigation.operation"
                      @change="filter('operation', '')"
                    />全部操作</label
                  ><label v-for="(label, key) in operations" :key="key"
                    ><input
                      type="radio"
                      name="bulk-list-operation"
                      :value="key"
                      :checked="navigation.operation === key"
                      @change="filter('operation', key)"
                    />{{ label }}</label
                  >
                </fieldset></FilterPopover
              >
            </th>
            <th>
              <FilterPopover
                label="状态"
                :active="!!navigation.state"
                :summary="states[navigation.state || ''] || navigation.state"
                :open="openFilter === 'state'"
                @update:open="openFilter = $event ? 'state' : null"
                ><fieldset class="bl-filter-options">
                  <legend class="bl-sr-only">运行状态</legend>
                  <label
                    ><input
                      type="radio"
                      name="bulk-list-state"
                      value=""
                      :checked="!navigation.state"
                      @change="filter('state', '')"
                    />全部状态</label
                  ><label v-for="(label, key) in states" :key="key"
                    ><input
                      type="radio"
                      name="bulk-list-state"
                      :value="key"
                      :checked="navigation.state === key"
                      @change="filter('state', key)"
                    />{{ label }}</label
                  >
                </fieldset></FilterPopover
              >
            </th>
            <th>完成进度</th>
            <th>当前结果</th>
            <th>
              <FilterPopover
                label="创建时间"
                :active="!!(navigation.created_from || navigation.created_to)"
                :summary="`${navigation.created_from || '不限'} 至 ${navigation.created_to || '不限'}`"
                :open="openFilter === 'date'"
                @update:open="openFilter = $event ? 'date' : null"
                ><div class="bl-filter-fields">
                  <label
                    >开始日期<input
                      type="date"
                      :value="navigation.created_from"
                      @change="filter('created_from', ($event.target as HTMLInputElement).value)" /></label
                  ><label
                    >截止日期<input
                      type="date"
                      :value="navigation.created_to"
                      @change="filter('created_to', ($event.target as HTMLInputElement).value)" /></label
                  ><button type="button" @click="removeFilter('date')">清除此列</button>
                </div></FilterPopover
              >
            </th>
            <th><span class="bl-sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" :data-bulk-row="row.id">
            <td class="bl-col-name">
              <button
                type="button"
                class="bl-name"
                data-bulk-open
                :disabled="stale"
                :title="row.name"
                @click="open(row.id)"
              >
                {{ row.name }}</button
              ><span class="bl-secondary" :title="`批次 #${row.id}`">#{{ row.id }}</span>
            </td>
            <td>{{ row.operation }}</td>
            <td>
              <span class="bl-status" :class="`is-${row.state}`">{{ row.status }}</span>
            </td>
            <td data-bulk-progress>
              <template v-if="row.total !== null && row.done !== null"
                ><span class="bl-progress-copy"
                  >{{ row.done }} / {{ row.total }} <span>{{ row.percent }}%</span></span
                ><progress
                  :value="row.done"
                  :max="Math.max(1, row.total)"
                  :aria-label="`已结束 ${row.done} 个，共 ${row.total} 个`"
                ></progress></template
              ><span v-else class="bl-secondary">{{ row.total === null ? '名单准备中' : '结果待汇总' }}</span>
            </td>
            <td>
              <div class="bl-results">
                <button
                  type="button"
                  class="bl-result is-success"
                  data-bulk-result="success"
                  :disabled="stale || !row.counts.success"
                  @click="open(row.id, 'success')"
                >
                  成功 {{ row.known ? row.counts.success || 0 : '—' }}</button
                ><button
                  type="button"
                  class="bl-result is-failed"
                  data-bulk-result="failed"
                  :disabled="stale || !row.counts.failed"
                  @click="open(row.id, 'failed')"
                >
                  失败 {{ row.known ? row.counts.failed || 0 : '—' }}
                </button>
              </div>
            </td>
            <td class="bl-date">{{ row.createdAt }}</td>
            <td>
              <button
                type="button"
                class="bl-button"
                data-bulk-report
                :disabled="stale"
                @click="report(row.id)"
              >
                查看报告
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="7">
              <div class="bl-empty" role="status">
                <strong>{{
                  loading
                    ? '正在加载批次…'
                    : error
                      ? '暂时无法读取批次'
                      : chips.length
                        ? '没有匹配的批次'
                        : '还没有批次'
                }}</strong
                ><template v-if="!loading && !error"
                  ><p>选择操作和账号范围，即可集中执行与追踪结果。</p>
                  <button
                    type="button"
                    class="bl-button"
                    data-bulk-create
                    @click="deps.callbacks.navigate('create')"
                  >
                    新建批次
                  </button></template
                >
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <CursorPagination
      v-if="!stale"
      :has-previous="hasPrevious"
      :next-cursor="nextCursor"
      :item-count="items.length"
      :has-cursor="!!navigation.cursor"
      :busy="loading"
      label="批次分页"
      @previous="list.previous"
      @next="list.next"
      @first="list.first"
    />
  </section>
</template>
<style scoped src="./bulk-list.css"></style>
