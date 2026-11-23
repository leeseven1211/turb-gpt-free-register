<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import ListCell from '../../components/ListCell.vue';
import ListPagination from '../../components/ListPagination.vue';
import TableState from '../../components/TableState.vue';
import ListResult from '../../components/ListResult.vue';
import { formatDateTime } from '../../shared/time';
import type { ProxyPoolSnapshot } from './contracts';
import { display, errorPresentation, number, object, status } from './presentation';
const props = defineProps<{ pool: ProxyPoolSnapshot | null; loading: boolean }>();
const counts = computed(() => props.pool?.counts ?? {}),
  countries = computed(() => props.pool?.country_pools ?? []);
const inventory = computed(() => props.pool?.items ?? []);
const page = ref(1);
const pageSize = ref(20);
const tableScroll = ref<HTMLElement | null>(null);
const lastPage = computed(() => Math.max(1, Math.ceil(inventory.value.length / pageSize.value)));
const pageStart = computed(() => (page.value - 1) * pageSize.value);
const visibleInventory = computed(() =>
  inventory.value.slice(pageStart.value, pageStart.value + pageSize.value),
);
watch(lastPage, (last) => {
  if (page.value > last) page.value = last;
});
watch([page, pageSize], () => {
  if (tableScroll.value) tableScroll.value.scrollTop = 0;
});
const capacity = computed(
  () =>
    `${['fetching', 'checking', 'ready', 'leased', 'shared', 'rotation_wait'].reduce((sum, key) => sum + (number(counts.value[key]) ?? 0), 0)} / ${props.pool?.policy.max_size || '—'}`,
);
const summaries = [
  ['poolReady', 'ready', '可领取'],
  ['poolFetching', 'fetching', '补货中'],
  ['poolChecking', 'checking', '复检中'],
  ['poolLeased', 'leased', '独占使用'],
  ['poolShared', 'shared', '共享使用'],
];
const countryCounts = [
  ['ready', '可领取'],
  ['fetching', '补货中'],
  ['checking', '复检中'],
  ['leased', '独占使用'],
  ['shared', '共享使用'],
  ['rotation_wait', '等待轮换'],
  ['quarantine', '故障隔离'],
];
const count = (value: unknown) => number(value) ?? '—';
</script>
<template>
  <div class="pt-workspace" data-proxy-module-panel="pool">
    <div class="pt-summary" aria-label="代理池库存摘要">
      <div>
        <span>代理池容量</span><strong data-proxy-summary="poolCapacity">{{ pool ? capacity : '—' }}</strong>
      </div>
      <div v-for="[key, state, label] in summaries" :key="key">
        <span>{{ label }}</span
        ><strong :data-proxy-summary="key">{{ pool ? counts[state!] || 0 : '—' }}</strong>
      </div>
    </div>
    <section class="ui-list pt-panel" aria-label="独立代理池库存">
      <header class="ui-list-toolbar pt-pool-header">
        <h3>代理池库存</h3>
        <span v-if="pool" role="status"
          >快照包含最近 {{ inventory.length }} 条库存 · 最小可用 {{ pool.policy.min_ready || 0 }} ·
          本进程等待 {{ pool.waiting_local || 0 }} / 维护线程 {{ pool.workers_local || 0
          }}<template v-if="countries.length"> · 分国家 {{ countries.length }} 组</template
          ><template v-if="pool.capacity_warning"> · {{ pool.capacity_warning }}</template></span
        ><span v-else role="status">{{ loading ? '正在加载代理池库存' : '代理池快照暂不可用' }}</span>
      </header>
      <div v-if="countries.length" class="pt-country-summary" aria-label="分国家代理池统计">
        <strong>分国家库存</strong>
        <div class="pt-country-cards">
          <div
            v-for="(country, index) in countries"
            :key="String(country.provider) + ':' + String(country.region) + ':' + index"
            class="pt-country-card"
          >
            <ListCell
              :text="display(country.region || country.country, '未标注')"
              :secondary="display(country.provider, '未标注')"
            />
            <p>
              {{
                countryCounts
                  .map(([key, label]) => `${label} ${count(object(country.counts)[key!])}`)
                  .join(' · ')
              }}
            </p>
            <small>等待 {{ count(country.waiting_local) }} · 目标 {{ count(country.target_ready) }}</small
            ><ListResult
              v-if="country.last_supply_error"
              :label="errorPresentation(country.last_supply_error).label"
              :title="errorPresentation(country.last_supply_error).evidence"
              tone="warning"
              ><template #details>{{
                errorPresentation(country.last_supply_error).evidence
              }}</template></ListResult
            ><small v-if="country.last_supply_error && Number(country.retry_after_seconds)"
              >{{ country.retry_after_seconds }} 秒后补货</small
            >
          </div>
        </div>
      </div>
        <div ref="tableScroll" class="ui-table-scroll pt-table-scroll" tabindex="0" aria-label="代理池库存，可横向滚动">
          <table class="ui-table pt-table pt-pool-table" data-proxy-table="pool">
          <thead>
            <tr>
              <th
                v-for="label in [
                  '资源',
                  '状态',
                  '来源 / 国家',
                  '脱敏端点',
                  '脱敏出口',
                  '校验 / 到期',
                  '最近错误',
                ]"
                :key="label"
                scope="col"
              >
                {{ label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in visibleInventory" :key="String(row.resource_id || pageStart + index)">
              <td><ListCell :text="display(row.resource_id)" /></td>
              <td>
                <ListResult
                  :label="status(row.state).label"
                  :title="status(row.state).title"
                  :tone="status(row.state).tone"
                />
              </td>
              <td><ListCell :text="display(row.provider)" :secondary="display(row.region)" /></td>
              <td><ListCell :text="display(row.endpoint)" /></td>
              <td><ListCell :text="display(row.exit_ip)" /></td>
              <td>
                <ListCell
                  :text="`校验 ${formatDateTime(row.checked_at)}`"
                  :secondary="`到期 ${formatDateTime(row.expires_at)}`"
                />
              </td>
              <td>
                <ListResult
                  :label="errorPresentation(row.last_error_code).label"
                  :title="errorPresentation(row.last_error_code).evidence"
                  :tone="row.last_error_code ? 'warning' : 'neutral'"
                  ><template v-if="row.last_error_code" #details>{{
                    errorPresentation(row.last_error_code).evidence
                  }}</template></ListResult
                >
              </td>
            </tr>
              <TableState v-if="!inventory.length" :colspan="7" :loading="loading && !pool" loading-title="正在加载代理池库存" :title="pool ? '暂无脱敏库存' : '暂时没有代理池快照'" :text="pool ? '等待后台补货或复检' : '代理池服务或旧版本接口暂未返回脱敏库存'"/>
          </tbody>
        </table>
      </div>
        <ListPagination
          v-if="pool"
          v-model:page="page"
          v-model:size="pageSize"
          :total="inventory.length"
          class="pt-pool-pagination"
          label="代理池库存分页"
        />
    </section>
  </div>
</template>
<style scoped>
.pt-pool-pagination {
  border-bottom: 1px solid var(--ui-color-border);
}
</style>
