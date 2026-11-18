<script setup lang="ts">
import {computed} from 'vue';
import {count, duration, modeLabel, number, providerLabel, rate, type Metrics, type Statistics} from './statistics';
import DailyTrend from './DailyTrend.vue';

const props = defineProps<{data: Statistics}>();
const failures = computed(() => (props.data.failures ?? []).filter(item => count(item.count) > 0)
  .sort((a, b) => count(b.count) - count(a.count)));
const modeMetrics = [['extracted','出链'], ['paid','支付'], ['plus_confirmed','Plus'], ['failed','失败']] as const;
function share(row: Metrics) {
  const total = count(props.data.totals.total);
  return total > 0 ? Math.min(1, count(row.total) / total) : null;
}
</script>
<template>
  <div class="es-chart-grid">
    <DailyTrend :daily="data.daily"/>
    <section class="es-panel" aria-labelledby="extractStatsFailureTitle">
      <div class="es-panel-header"><h2 id="extractStatsFailureTitle">失败分类</h2><span>{{ number(data.totals.failed) }} 个失败任务</span></div>
      <ol v-if="failures.length" class="es-failures"><li v-for="item in failures" :key="item.code || item.label">
        <div class="es-failure-heading"><span>{{ item.label || item.code || '原因未记录' }}</span><strong>{{ number(item.count) }}</strong></div>
        <div class="es-failure-track" aria-hidden="true"><span :style="{width: `${count(item.count) / count(failures[0].count) * 100}%`}"></span></div>
        <code>{{ item.code || '未记录错误码' }}</code>
      </li></ol>
      <div v-else class="es-empty es-empty--compact"><span class="es-empty-success" aria-hidden="true">✓</span><strong>暂无失败记录</strong><p>所选范围没有失败任务。</p></div>
    </section>
  </div>
  <section class="es-panel es-platforms" aria-labelledby="extractStatsProvidersTitle">
    <div class="es-panel-header"><h2 id="extractStatsProvidersTitle">平台对比</h2><span>支付成功与 Plus 到账分别统计</span></div>
    <div v-if="data.providers?.length" class="es-table-scroll" tabindex="0" aria-label="平台统计，可左右滚动">
      <table class="es-provider-table"><caption class="es-sr-only">各提链平台的任务产出与转化</caption>
        <thead><tr><th scope="col">平台</th><th scope="col">任务数</th><th scope="col">已出链</th>
          <th scope="col" title="已出链 /（已出链 + 提链失败），未结束任务不进入分母">提链成功率</th><th scope="col">已支付</th>
          <th scope="col" title="已支付 /（已支付 + 支付失败），未结束任务不进入分母">支付成功率</th><th scope="col">Plus 已确认</th>
          <th scope="col">失败</th><th scope="col">处理中</th><th scope="col" title="最新成功运行的平均总耗时">平均耗时</th>
        </tr></thead>
        <tbody><tr v-for="row in data.providers" :key="row.provider_id">
          <th scope="row">{{ providerLabel(row.provider_id) }}</th><td>{{ number(row.total) }}</td><td class="es-number-extracted">{{ number(row.extracted) }}</td>
          <td :title="`已出链 ${number(row.extracted)}，提链失败 ${number(row.extraction_failed)}`">{{ rate(row.extraction_rate) }}</td>
          <td class="es-number-paid">{{ number(row.paid) }}</td><td :title="`已支付 ${number(row.paid)}，支付失败 ${number(row.payment_failed)}`">{{ rate(row.payment_rate) }}</td>
          <td>{{ number(row.plus_confirmed) }}</td><td>{{ number(row.failed) }}</td><td>{{ number(row.processing) }}</td><td class="es-nowrap">{{ duration(row.avg_seconds) }}</td>
        </tr></tbody>
      </table>
    </div>
    <div v-else class="es-empty es-empty--compact"><strong>暂无平台数据</strong><p>所选范围没有提链任务。</p></div>
  </section>
  <section class="es-panel es-mode-panel" aria-labelledby="extractStatsModesTitle">
    <div class="es-panel-header"><h2 id="extractStatsModesTitle">模式分布</h2><span>所选范围内的任务组成</span></div>
    <div v-if="data.modes?.length" class="es-modes"><article v-for="row in data.modes" :key="row.mode" class="es-mode">
      <div class="es-mode-heading"><h3>{{ modeLabel(row.mode) }}</h3><span>{{ rate(share(row)) }}</span></div>
      <strong class="es-mode-total">{{ number(row.total) }}<small> 个任务</small></strong>
      <div class="es-mode-track" aria-hidden="true"><span :style="{width: `${(share(row) ?? 0) * 100}%`}"></span></div>
      <dl><div v-for="[key, label] in modeMetrics" :key="key"><dt>{{ label }}</dt><dd>{{ number(row[key]) }}</dd></div></dl>
    </article></div>
    <div v-else class="es-empty es-empty--compact"><strong>暂无模式数据</strong></div>
  </section>
</template>
