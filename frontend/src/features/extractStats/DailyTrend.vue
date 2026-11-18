<script setup lang="ts">
import {computed} from 'vue';
import {count, number, type Daily} from './statistics';

const props = defineProps<{daily: Daily[]}>();
const series = [['total', '任务总数'], ['extracted', '已出链'], ['paid', '已支付']] as const;
const columns = [...series, ['plus_confirmed', 'Plus 已确认'], ['failed', '失败']] as const;
const hasTrend = computed(() => props.daily.some(row => count(row.total) > 0));
const maximum = computed(() => {
  const peak = Math.max(1, ...props.daily.flatMap(row => series.map(([key]) => count(row[key]))));
  return Math.ceil(peak / 4) * 4;
});
const ticks = computed(() => {
  const step = Math.max(1, Math.ceil(props.daily.length / 7));
  return props.daily.map((_, index) => index).filter(index => index % step === 0 || index === props.daily.length - 1);
});
function x(index: number) { return 48 + (props.daily.length === 1 ? 406 : index * 812 / (props.daily.length - 1)); }
function y(value: unknown) { return 22 + 184 * (1 - count(value) / maximum.value); }
function path(key: typeof series[number][0]) {
  return props.daily.map((row, index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)},${y(row[key]).toFixed(2)}`).join(' ');
}
</script>
<template>
  <section class="es-panel es-trend" aria-labelledby="extractStatsDailyTitle">
    <div class="es-panel-header"><h2 id="extractStatsDailyTitle">每日趋势</h2><span>按北京时间任务创建日归属</span></div>
    <div v-if="!hasTrend" class="es-empty"><strong>这个时间段还没有提链任务</strong><p>可选择其他时间范围。</p></div>
    <template v-else>
      <div class="es-chart-legend">
        <span v-for="[key, label] in series" :key="key"><i class="es-legend-dot" :class="`es-legend-dot--${key}`" aria-hidden="true"></i>{{ label }}</span>
      </div>
      <div class="es-chart-scroll">
        <svg class="es-chart" viewBox="0 0 880 242" role="img" aria-labelledby="extractStatsTrendTitle extractStatsTrendDescription">
          <title id="extractStatsTrendTitle">每日提链与支付趋势</title>
          <desc id="extractStatsTrendDescription">{{ daily.length }} 天的任务总数、已出链与已支付数量。完整数值以及 Plus 到账、失败数量可在下方每日明细中查看。</desc>
          <g v-for="i in [0, 1, 2, 3, 4]" :key="i">
            <line x1="48" x2="860" :y1="y(maximum * i / 4)" :y2="y(maximum * i / 4)" class="es-chart-gridline"/>
            <text x="38" :y="y(maximum * i / 4) + 4" text-anchor="end" class="es-chart-label">{{ number(maximum * i / 4) }}</text>
          </g>
          <text v-for="i in ticks" :key="i" :x="x(i)" y="232" text-anchor="middle" class="es-chart-label">{{ String(daily[i].date || '').slice(5) }}</text>
          <g v-for="[key,label] in series" :key="key">
            <path class="es-chart-line" :class="`es-chart-line--${key}`" :d="path(key)"/>
            <circle v-for="(row, i) in daily" :key="row.date" class="es-chart-point" :class="`es-chart-point--${key}`"
              :cx="x(i)" :cy="y(row[key])" :r="daily.length <= 31 ? 3 : 2">
              <title>{{ row.date }} {{ label }} {{ number(row[key]) }}</title>
            </circle>
          </g>
        </svg>
      </div>
      <details class="es-daily-details">
        <summary>查看每日明细</summary><div class="es-table-scroll"><table>
          <caption class="es-sr-only">每日任务统计，按北京时间任务创建日归属</caption>
          <thead><tr><th scope="col">日期</th><th v-for="[key,label] in columns" :key="key" scope="col">{{ label }}</th></tr></thead>
          <tbody><tr v-for="row in daily" :key="row.date"><th scope="row">{{ row.date }}</th><td v-for="[key] in columns" :key="key">{{ number(row[key]) }}</td></tr></tbody>
        </table></div>
      </details>
    </template>
  </section>
</template>
