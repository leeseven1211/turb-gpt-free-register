<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import ListCell from '../../components/ListCell.vue';
import ListResult from '../../components/ListResult.vue';
import { useColumnWidths } from '../../shared/useColumnWidths';
import { dateTimeLines, formatDateTime } from '../../shared/time';
import ProxyFilters from './ProxyFilters.vue';
import type { FilterKey } from './filterDefinitions';
import type { ProxyRecordView, ProxyRow, ProxySummary } from './contracts';
import {
  correlation,
  display,
  number,
  status,
  taskSummary,
  trafficBytes,
  type FacetLabel,
} from './presentation';
const props = defineProps<{
  view: ProxyRecordView;
  items: ProxyRow[];
  filters: { search: string; window: string; purpose: string };
  state: string;
  summary: ProxySummary | null;
  loading: boolean;
  error: string;
  visible: boolean;
  openFilter: string | null;
  scrollRevision: number;
  facetLabel?: FacetLabel;
}>();
const emit = defineEmits<{
  filter: [FilterKey, string];
  'update:openFilter': [string | null];
  detail: ['history' | 'traffic', ProxyRow, HTMLElement];
  retry: [];
}>();
const defaults = {
  current: [145, 144, 108, 156, 126, 220, 88, 188],
  history: [145, 144, 108, 156, 126, 220, 188, 92],
  traffic: [132, 92, 108, 170, 188, 220, 188, 92],
};
const storage = { current: 'proxyCurrent', history: 'proxyHistory', traffic: 'proxyTraffic' }[props.view];
const widths = useColumnWidths({
  defaults: defaults[props.view],
  storageKey: 'gpt_console_table_widths_' + storage,
  totalStorageKey: 'gpt_console_table_total_' + storage,
  min: 28,
  max: 2000,
});
const scroll = ref<HTMLElement>();
let appliedScrollRevision = props.scrollRevision;
watch(
  () => [props.items, props.scrollRevision] as const,
  async () => {
    if (props.scrollRevision === appliedScrollRevision) return;
    appliedScrollRevision = props.scrollRevision;
    await nextTick();
    if (scroll.value) scroll.value.scrollTop = 0;
  },
);
const headers = computed((): { label: string; filter?: FilterKey }[] =>
  props.view === 'traffic'
    ? [
        { label: '来源', filter: 'search' },
        { label: '方法' },
        { label: '采集状态', filter: 'state' },
        { label: '上传 / 下载 / 总计' },
        { label: '请求 / 失败 / 未完成 / 未知' },
        { label: '任务' },
        { label: '采集时间', filter: 'window' },
        { label: '详情' },
      ]
    : [
        { label: '租约', filter: 'search' },
        { label: '出口 IP' },
        { label: '状态', filter: 'state' },
        { label: '账号' },
        { label: '用途', filter: 'purpose' },
        { label: props.view === 'history' ? '任务 / 运行 / 注册 job' : '任务 / 运行' },
        ...(props.view === 'history'
          ? [{ label: '租约时间', filter: 'window' as const }, { label: '详情' }]
          : [{ label: '重试序号' }, { label: '时间', filter: 'window' as const }]),
      ],
);
const title = computed(() => ({ current: '当前租约', history: '线路历史', traffic: '请求流量' })[props.view]);
function leaseTime(row: ProxyRow) {
  const start = formatDateTime(row.acquired_at),
    end = row[props.view === 'history' ? 'released_at' : 'expires_at'];
  return {
    text: start,
    secondary: end ? `至 ${formatDateTime(end)}` : '进行中',
    title: `${start} · ${end ? formatDateTime(end) : '进行中'}`,
  };
}
function openDetail(row: ProxyRow, event: MouseEvent) {
  if (props.view !== 'current') emit('detail', props.view, row, event.currentTarget as HTMLElement);
}
defineExpose({ resetColumns: widths.resetColumns });
</script>
<template>
  <div
    ref="scroll"
    class="pt-table-scroll"
    tabindex="0"
    :aria-label="`${title}列表，可横向滚动`"
    :aria-busy="loading"
  >
    <table
      class="pt-table pt-records-table"
      :data-proxy-table="view"
      :style="{ '--pt-table-width': `${widths.total.value}px` }"
    >
      <caption class="pt-sr-only">
        {{
          title
        }}
      </caption>
      <colgroup>
        <col v-for="(width, index) in widths.widths.value" :key="index" :style="{ width: `${width}px` }" />
      </colgroup>
      <thead>
        <tr>
          <th v-for="(header, index) in headers" :key="header.label" scope="col">
            <ProxyFilters
              v-if="header.filter"
              :column="header.filter"
              :trigger-label="header.label"
              :view="view"
              :filters="filters"
              :state="state"
              :summary="summary"
              :open="visible && openFilter === `${view}:${header.filter}`"
              @change="(key, value) => emit('filter', key, value)"
              @update:open="emit('update:openFilter', $event ? `${view}:${header.filter}` : null)"
            /><span v-else>{{ header.label }}</span
            ><button
              v-if="index < headers.length - 1"
              type="button"
              class="pt-column-resize"
              :aria-label="`调整${header.label}列宽，方向键调整`"
              @pointerdown.prevent="widths.resize(index, $event)"
              @keydown.left.prevent="widths.resizeWithKeyboard(index, -10)"
              @keydown.right.prevent="widths.resizeWithKeyboard(index, 10)"
            ></button>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in items" :key="`${view}:${row.id ?? index}`">
          <template v-if="view === 'traffic'"
            ><td><ListCell :text="display(row.source)" /></td>
            <td><ListCell :text="display(row.method)" /></td>
            <td>
              <ListResult
                :label="trafficBytes(row).text === '未采集' ? '未采集' : '可观测'"
                :title="display(row.availability)"
                :tone="trafficBytes(row).text === '未采集' ? 'neutral' : 'success'"
              />
            </td>
            <td><ListCell v-bind="trafficBytes(row)" /></td>
            <td>
              <ListCell
                :text="
                  [row.request_count, row.failed_count, row.unfinished_count, row.unknown_count]
                    .map((value) => number(value) ?? '—')
                    .join(' / ')
                "
                title="请求 / 失败 / 未完成 / 未知"
              />
            </td>
            <td><ListCell v-bind="taskSummary(row, facetLabel)" /></td>
            <td>
              <ListCell v-bind="dateTimeLines(row.started_at)" :title="formatDateTime(row.started_at)" />
            </td>
            <td>
              <button
                v-if="row.id != null"
                type="button"
                class="pt-link"
                data-proxy-detail="traffic"
                aria-label="查看请求流量详情"
                @click="openDetail(row, $event)"
              >
                详情</button
              ><span v-else>—</span>
            </td></template
          >
          <template v-else
            ><td>
              <ListCell :text="display(row.lease_id, '未提供租约 ID')" :secondary="display(row.provider)" />
            </td>
            <td><ListCell :text="display(row.exit_ip)" /></td>
            <td>
              <ListResult
                :label="status(row.state).label"
                :title="status(row.state).title"
                :tone="status(row.state).tone"
              />
            </td>
            <td><ListCell :text="display(row.account_id)" /></td>
            <td><ListCell :text="display(row.purpose)" /></td>
            <td><ListCell :text="correlation(row, view === 'history')" /></td>
            <template v-if="view === 'current'"
              ><td><ListCell :text="display(row.route_attempt_no)" /></td>
              <td><ListCell v-bind="leaseTime(row)" /></td></template
            ><template v-else
              ><td><ListCell v-bind="leaseTime(row)" /></td>
              <td>
                <button
                  v-if="row.id != null"
                  type="button"
                  class="pt-link"
                  data-proxy-detail="history"
                  aria-label="查看线路历史详情"
                  @click="openDetail(row, $event)"
                >
                  详情</button
                ><span v-else>—</span>
              </td></template
            ></template
          >
        </tr>
        <tr v-if="!items.length">
          <td colspan="8">
            <div class="pt-empty" :role="error ? 'alert' : 'status'">
              <strong>{{
                loading ? `正在加载${title}` : error ? '代理与流量数据暂不可用' : `暂无${title}`
              }}</strong>
              <p>{{ error || (loading ? '正在同步代理与流量 API' : '当前没有可显示的持久化记录。') }}</p>
              <button v-if="error" type="button" class="pt-button" @click="emit('retry')">重新加载</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
