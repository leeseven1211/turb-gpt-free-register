<script setup lang="ts">
import StatsBreakdown from './StatsBreakdown.vue';
import StatsSummary from './StatsSummary.vue';
import {ranges, type StatsDependencies} from './statistics';
import {useExtractStats} from './useExtractStats';

const props = defineProps<{deps?: StatsDependencies}>();
const {days, provider, providers, data, busy, error, status, load, setDays, setVisible} = useExtractStats(props.deps ?? {});
defineExpose({load, setVisible});
</script>
<template>
  <section class="extract-stats-page" :aria-busy="busy" aria-labelledby="extractStatsTitle">
    <header class="es-page-header">
      <div><h1 id="extractStatsTitle">提链统计</h1><p>查看任务产出、支付转化与失败原因</p></div>
      <span class="es-timezone">北京时间 · 每个任务的最新结果</span>
    </header>
    <div class="es-toolbar" role="group" aria-label="筛选提链统计">
      <div class="es-periods" role="group" aria-label="统计时间范围">
        <button v-for="range in ranges" :key="range" type="button" :data-extract-stats-days="range" :aria-pressed="range === days" @click="setDays(range)">近 {{ range }} 天</button>
      </div>
      <label class="es-provider-label">平台<select v-model="provider" data-extract-stats-provider aria-label="按提链平台筛选" @change="load()">
        <option value="">全部平台</option><option v-for="[id, label] in providers" :key="id" :value="id">{{ label }}</option>
      </select></label>
      <button type="button" class="es-refresh" data-extract-stats-refresh :disabled="busy" :aria-busy="busy" @click="load()">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5M6.1 7a7 7 0 0 1 11.5-1L20 9M4 15l2.4 3A7 7 0 0 0 18 17"/></svg><span>刷新</span>
      </button>
      <span class="es-load-status" data-extract-stats-status role="status" aria-live="polite">{{ status }}</span>
    </div>
    <div v-if="error" class="es-notice" data-extract-stats-notice role="alert">
      <span>{{ data ? '刷新失败，以下保留上次统计。' : '统计暂时无法加载。' }}{{ error }}</span><button type="button" data-extract-stats-retry @click="load()">重试</button>
    </div>
    <div data-extract-stats-content>
      <template v-if="data"><StatsSummary :data="data" :filtered="Boolean(provider)"/><StatsBreakdown :data="data"/></template>
      <div v-else-if="busy" class="es-loading" role="status"><span class="es-loading-dot" aria-hidden="true"></span>正在汇总提链任务…</div>
      <div v-else-if="error" class="es-loading es-loading--failed">未取得所选范围的统计，请重试。</div>
    </div>
  </section>
</template>
