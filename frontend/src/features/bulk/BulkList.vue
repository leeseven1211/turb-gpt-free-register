<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import CursorPagination from '../../components/CursorPagination.vue';
import FilterPopover from '../../components/FilterPopover.vue';
import TableState from '../../components/TableState.vue';
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
const stateTone = (state: string) => state === 'active' || state === 'settling' ? 'active' : ['paused', 'cancel_requested', 'stop_requested'].includes(state) ? 'warning' : 'neutral';
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
const resultSummary = computed(() => {
  const success = count(summary.value.success_targets);
  const partial = count(summary.value.partial_success_targets);
  let failed = count(summary.value.failed_targets);
  const oldFailed = count(summary.value.attention_targets);
  if (oldFailed !== null && failed !== null) failed += oldFailed;
  const total = success !== null && partial !== null && failed !== null ? success + partial + failed : null;
  return { success, partial, failed, total };
});
function percentage(value: number, total: number): string {
  return ((100 * value) / total).toFixed(1);
}
const kpis = computed(() => {
  const total = count(summary.value.total_batches);
  const paused = count(summary.value.paused_batches);
  const ended = count(summary.value.ended_batches);
  const result = resultSummary.value;
  return [
    { key: 'total_batches', label: '批次总数', value: total, unit: '批', tone: 'neutral', detail: chips.value.length ? '当前筛选' : '全部批次' },
    { key: 'active_batches', label: '执行中', value: count(summary.value.active_batches), unit: '批', tone: 'active', detail: paused === null ? '' : `已暂停 ${paused.toLocaleString('zh-CN')}` },
    { key: 'ended_batches', label: '已结束', value: ended, unit: '批', tone: 'neutral', detail: ended !== null && total ? `占 ${percentage(ended, total)}%` : '' },
    { key: 'success_targets', label: '成功账号', value: result.success, unit: '个', tone: 'success', detail: result.partial === null ? '' : `部分成功 ${result.partial.toLocaleString('zh-CN')}` },
    { key: 'failed_targets', label: '失败账号', value: result.failed, unit: '个', tone: 'warning', detail: result.failed !== null && result.total ? `占 ${percentage(result.failed, result.total)}%` : '' },
    { key: 'success_rate', label: '成功率', value: result.total && result.success !== null ? (100 * result.success) / result.total : null, unit: '%', tone: 'success', detail: '', available: result.total !== null },
  ].filter((item) => item.value !== null || item.available).map((item) => ({
    ...item,
    display: item.value === null ? '—' : item.key === 'success_rate' ? item.value.toFixed(1) : item.value.toLocaleString('zh-CN'),
  }));
});
const resultSegments = computed(() => {
  const { success, partial, failed, total } = resultSummary.value;
  if (!total) return [];
  return [
    { key: 'success', label: '成功', value: success! },
    { key: 'partial', label: '部分成功', value: partial! },
    { key: 'failed', label: '失败', value: failed! },
  ].map((item) => ({ ...item, width: `${(100 * item.value) / total}%` }));
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
  <section class="ui-list bl-root" aria-label="批次列表" :aria-busy="loading">
    <div
      v-if="kpis.length"
      class="bl-kpis"
      :style="{ '--bl-kpi-count': kpis.length }"
      aria-label="当前筛选范围的全部批次统计"
      title="统计覆盖当前筛选范围的全部批次；同一账号在不同批次分别计数，批次内取账号当前结果。"
    >
      <div
        v-for="kpi in kpis"
        :key="kpi.key"
        class="bl-kpi"
        :class="`is-${kpi.tone}`"
        :data-bulk-stat="kpi.key"
        :title="kpi.key === 'success_rate' ? '成功率 = 成功 ÷（成功 + 部分成功 + 失败），不含待执行、取消和未执行。' : undefined"
      >
        <span>{{ kpi.label }}</span
        ><div class="bl-kpi-value">
          <strong :title="kpi.display">{{ kpi.display }}<small v-if="kpi.value !== null">{{ kpi.unit }}</small></strong>
          <span v-if="kpi.detail" class="bl-kpi-detail" :title="kpi.detail">{{ kpi.detail }}</span>
        </div>
        <span
          v-if="kpi.key === 'success_rate' && resultSegments.length"
          class="bl-kpi-rail"
          role="img"
          :aria-label="resultSegments.map((item) => `${item.label} ${item.value}`).join('，')"
        ><i v-for="segment in resultSegments" :key="segment.key" :class="`is-${segment.key}`" :style="{ width: segment.width }" aria-hidden="true"></i></span>
      </div>
    </div>
      <div v-if="chips.length" class="ui-list-toolbar bl-toolbar">
        <div class="ui-list-toolbar__main bl-toolbar-main"><ListFilterSummary :items="chips" @remove="removeFilter" /></div>
        <div class="ui-list-toolbar__actions"><button type="button" class="ui-link" @click="list.resetFilters">清除筛选</button></div>
      </div>
    <div v-if="error" class="ui-list-feedback is-error bl-error" role="alert">
      <span>{{ error }}</span
      ><button type="button" class="ui-link" :disabled="loading" @click="list.refresh()">重试</button
      ><button
        v-if="stale && navigation.cursor"
        class="ui-link"
        type="button"
        :disabled="loading"
        @click="list.first"
      >
        返回首页</button
      ><button
        v-if="stale && hasPrevious"
        class="ui-link"
        type="button"
        :disabled="loading"
        @click="list.previous"
      >
        上一页
      </button>
    </div>
    <div ref="tableHost" class="ui-table-scroll bl-table-wrap" tabindex="0" role="region" aria-label="批次列表内容">
      <table class="ui-table ui-table--sticky-end bl-table">
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
                  <div class="list-filter-actions">
                    <button type="button" @click="removeFilter('q')">清除此列</button
                    ><button class="list-filter-primary" type="submit">查询</button>
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
                ><fieldset class="list-filter-options">
                  <legend class="ui-sr-only">操作类型</legend>
                  <label class="list-filter-option"
                    ><input
                      type="radio"
                      name="bulk-list-operation"
                      value=""
                      :checked="!navigation.operation"
                      @change="filter('operation', '')"
                    />全部操作</label
                  ><label class="list-filter-option" v-for="(label, key) in operations" :key="key"
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
                ><fieldset class="list-filter-options">
                  <legend class="ui-sr-only">运行状态</legend>
                  <label class="list-filter-option"
                    ><input
                      type="radio"
                      name="bulk-list-state"
                      value=""
                      :checked="!navigation.state"
                      @change="filter('state', '')"
                    />全部状态</label
                  ><label class="list-filter-option" v-for="(label, key) in states" :key="key"
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
                  ><div class="list-filter-actions"><button type="button" @click="removeFilter('date')">清除此列</button></div>
                </div></FilterPopover
              >
            </th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" :data-bulk-row="row.id">
            <td class="bl-col-name">
              <button
                type="button"
                class="ui-link bl-name"
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
              <span class="ui-badge bl-status" :class="`ui-badge--${stateTone(row.state)}`">{{ row.status }}</span>
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
                class="ui-link"
                data-bulk-report
                :disabled="stale"
                @click="report(row.id)"
              >
                查看报告
              </button>
            </td>
          </tr>
          <TableState v-if="!rows.length" :colspan="7" :loading="loading" :error="error ? ' ' : ''" loading-title="正在加载批次…" error-title="暂时无法读取批次" :title="chips.length ? '没有匹配的批次' : '还没有批次'" text="选择操作和账号范围，即可集中执行与追踪结果。"><button v-if="!loading && !error" type="button" class="ui-button ui-button--primary" data-bulk-create @click="deps.callbacks.navigate('create')">新建批次</button></TableState>
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
