<script setup lang="ts">
import { computed, ref } from 'vue';
import ListFilterSummary from '../../components/ListFilterSummary.vue';
import ListPagination from '../../components/ListPagination.vue';
import ProxyPool from './ProxyPool.vue';
import ProxyRecordsTable from './ProxyRecordsTable.vue';
import ProxyFilters from './ProxyFilters.vue';
import ProxyDetail from './ProxyDetail.vue';
import { useProxyTraffic } from './useProxyTraffic';
import { chips, type FilterKey } from './filterDefinitions';
import { bytes } from './presentation';
import type { ProxyRecordView, ProxyTrafficDeps } from './contracts';
import './proxy.css';
const props = defineProps<{ deps: ProxyTrafficDeps }>();
const owner = useProxyTraffic(props.deps);
const { view, recordView, filters, pages, summary, pool, detail, loading, error, active, openFilter } = owner;
const tables = ref<Partial<Record<ProxyRecordView, InstanceType<typeof ProxyRecordsTable>>>>({});
const views: ProxyRecordView[] = ['current', 'history', 'traffic'];
const labels = { current: '当前租约', history: '线路历史', traffic: '请求流量' };
const applied = computed(() =>
  chips(filters, {
    current: pages.current.state,
    history: pages.history.state,
    traffic: pages.traffic.state,
  }),
);
const current = computed(() => pages[recordView.value]);
function change(name: ProxyRecordView, key: FilterKey, value: string) {
  if (key === 'state') owner.setState(name, value);
  else owner.updateFilters({ [key]: value });
}
function resetColumns() {
  tables.value[recordView.value]?.resetColumns();
  props.deps.notify?.('已恢复默认列宽');
}
function keyboard(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const index = views.indexOf(recordView.value),
    next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? views.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + views.length) % views.length;
  owner.setRecordView(views[next]!);
  (event.currentTarget as HTMLElement)
    .querySelector<HTMLButtonElement>(`[data-proxy-view="${views[next]}"]`)
    ?.focus({ preventScroll: true });
}
defineExpose({
  load: owner.load,
  setVisible: owner.setVisible,
  setView: owner.setView,
  closeDetail: owner.closeDetail,
});
</script>
<template>
  <div class="pt-root" data-proxy-vue>
    <ProxyPool v-show="view === 'pool'" :pool="pool" :loading="loading" />
    <div v-show="view === 'records'" class="pt-workspace" data-proxy-module-panel="records">
      <div class="pt-summary" aria-label="租约与流量摘要">
        <div>
          <span>累计可观测流量</span
          ><strong data-proxy-summary="totalBytes">{{ summary ? bytes(summary.total_bytes) : '—' }}</strong>
        </div>
        <div>
          <span>今日可观测流量</span
          ><strong data-proxy-summary="todayBytes">{{ summary ? bytes(summary.today_bytes) : '—' }}</strong>
        </div>
        <div>
          <span>今日请求记录</span
          ><strong data-proxy-summary="todayRequestCount">{{
            summary ? (summary.today_request_count ?? summary.today_browser_count ?? '—') : '—'
          }}</strong>
        </div>
        <div>
          <span>今日新建线路</span
          ><strong data-proxy-summary="todayRouteCount">{{ summary?.today_route_count ?? '—' }}</strong>
        </div>
      </div>
      <div class="ui-list pt-records-sheet">
      <div class="ui-list-toolbar pt-toolbar">
        <div class="pt-view-tabs" role="tablist" aria-label="代理与流量视图" @keydown="keyboard">
          <button
            v-for="name in views"
            :key="name"
            type="button"
            role="tab"
            :data-proxy-view="name"
            :aria-selected="recordView === name"
            :aria-controls="`proxy-panel-${name}`"
            :tabindex="recordView === name ? 0 : -1"
            :class="{ 'is-active': recordView === name }"
            @click="owner.setRecordView(name)"
          >
            {{ labels[name] }} <span>{{ error ? '—' : pages[name].total }}</span>
          </button>
        </div>
        <div class="ui-list-toolbar__main pt-toolbar-main">
          <span class="ui-list-count pt-count" role="status">{{
            error ? '数据暂不可用' : `${current.total.toLocaleString()} 条记录`
          }}</span
          ><ListFilterSummary :items="applied" @remove="owner.removeFilter" />
        </div>
        <div class="ui-list-toolbar__actions pt-toolbar-actions">
          <span class="pt-mobile-filter">
            <ProxyFilters
              :view="recordView"
              :filters="filters"
              :state="current.state"
              :summary="summary"
              :open="active && openFilter === 'all'"
              @change="(key, value) => change(recordView, key, value)"
              @update:open="openFilter = $event ? 'all' : null"
            />
          </span>
          <button v-if="applied.length" type="button" class="ui-link" @click="owner.resetFilters">清筛</button>
          <button type="button" class="ui-link" aria-label="恢复当前列表列宽" @click="resetColumns">恢复列宽</button>
          <button type="button" class="ui-button pt-refresh-btn ui-refresh-button" :disabled="loading" @click="owner.load()">{{ loading ? '刷新中…' : '刷新' }}</button>
        </div>
      </div>
      <section
        v-for="name in views"
        v-show="recordView === name"
        :id="`proxy-panel-${name}`"
        :key="name"
        role="tabpanel"
        :aria-label="labels[name]"
        :aria-hidden="recordView !== name"
        :data-proxy-panel="name"
        class="pt-panel"
      >
        <ProxyRecordsTable
          :ref="
            (value) => {
              if (value) tables[name] = value as InstanceType<typeof ProxyRecordsTable>;
            }
          "
          :view="name"
          :items="pages[name].items"
          :filters="filters"
          :state="pages[name].state"
          :summary="summary"
          :loading="loading"
          :error="error"
          :visible="active && view === 'records' && recordView === name"
          :open-filter="openFilter"
          :scroll-revision="owner.scrollRevision[name]"
          :facet-label="deps.facetLabel"
          @filter="(key, value) => change(name, key, value)"
          @update:open-filter="openFilter = $event"
          @detail="owner.openDetail"
          @retry="owner.load()"
        /><ListPagination
          :page="pages[name].page"
          :size="pages[name].size"
          :total="pages[name].total"
          :busy="loading"
          :page-sizes="[20, 50, 100]"
          :label="`${labels[name]}分页`"
          @update:page="owner.setPage(name, $event)"
          @update:size="owner.setSize(name, $event)"
        />
      </section>
      </div>
    </div>
    <ProxyDetail :snapshot="detail" :facet-label="deps.facetLabel" @close="owner.closeDetail()" />
  </div>
</template>
