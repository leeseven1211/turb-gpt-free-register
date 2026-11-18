<script setup lang="ts">
import {computed} from 'vue';
import {number, rate, duration, type Statistics, type Metrics} from './statistics';

const props = defineProps<{data: Statistics; filtered: boolean}>();
const totals = computed(() => props.data.totals);
const current = computed<Metrics>(() => props.data.current ?? {});
const today = computed<Metrics>(() => props.data.daily.at(-1) ?? {});
const metrics = [
  ['total', '任务总数', '所选时间内创建的任务', ''], ['extracted', '已出链', '已获得支付链接', 'brand'],
  ['paid', '已支付', '支付结果已确认', 'green'], ['plus_confirmed', 'Plus 已确认', '套餐到账已核验', 'blue'],
] as const;
const states = [
  ['failed', '失败', 'red'], ['processing', '处理中', 'brand'], ['awaiting_payment', '待支付', 'amber'], ['needs_review', '待核对', 'amber'],
] as const;
</script>
<template>
  <section class="es-today" aria-labelledby="extractStatsTodayTitle">
    <div class="es-today-heading"><h2 id="extractStatsTodayTitle">今日与当前</h2><span>今日任务按北京时间创建日归属</span></div>
    <dl>
      <div><dt>今日任务出链</dt><dd>{{ number(today.extracted) }}</dd></div>
      <div><dt>今日任务 Plus</dt><dd>{{ number(today.plus_confirmed) }}</dd></div>
      <div><dt>当前待支付<small>全部日期</small></dt><dd>{{ number(current.awaiting_payment) }}</dd></div>
      <div><dt>当前待核对<small>全部日期</small></dt><dd>{{ number(current.needs_review) }}</dd></div>
    </dl>
  </section>
  <div class="es-scope"><span>{{ data.date_from || '—' }} — {{ data.date_to || '—' }}</span><span>按任务创建日统计 · 同一任务仅计一次</span></div>
  <div class="es-metrics">
    <article v-for="[key, label, hint, tone] in metrics" :key="key" class="es-metric" :class="tone && `es-metric--${tone}`">
      <span class="es-metric-label">{{ label }}</span><strong>{{ number(totals[key]) }}</strong><span class="es-metric-hint">{{ hint }}</span>
    </article>
  </div>
  <div class="es-summary-grid">
    <section class="es-panel es-conversion" aria-labelledby="extractStatsConversionTitle">
      <div class="es-panel-header"><h2 id="extractStatsConversionTitle">转化与耗时</h2><span>未结束任务不进入成功率分母</span></div>
      <dl>
        <div><dt>提链成功率</dt><dd>{{ rate(totals.extraction_rate) }}</dd><span>已出链 /（已出链 + 提链失败）</span><small>出链 {{ number(totals.extracted) }} · 失败 {{ number(totals.extraction_failed) }}</small></div>
        <div><dt>支付成功率</dt><dd>{{ rate(totals.payment_rate) }}</dd><span>已支付 /（已支付 + 支付失败）</span><small>支付 {{ number(totals.paid) }} · 失败 {{ number(totals.payment_failed) }}</small></div>
        <div><dt>平均耗时</dt><dd class="es-duration">{{ duration(totals.avg_seconds) }}</dd><span>最新成功运行的总耗时</span></div>
      </dl>
    </section>
    <section class="es-panel es-task-states" aria-labelledby="extractStatsStatesTitle">
      <div class="es-panel-header"><h2 id="extractStatsStatesTitle">区间任务状态</h2><span>所选范围的最新结果</span></div>
      <dl><div v-for="[key, label, tone] in states" :key="key"><dt><i class="es-state-dot" :class="`es-state-dot--${tone}`" aria-hidden="true"></i>{{ label }}</dt><dd>{{ number(totals[key]) }}</dd></div></dl>
      <p class="es-current">{{ filtered ? '当前所选平台' : '当前全部平台' }}，全部日期：处理中 {{ number(current.processing) }} · 待支付 {{ number(current.awaiting_payment) }} · 待核对 {{ number(current.needs_review) }}</p>
    </section>
  </div>
</template>
