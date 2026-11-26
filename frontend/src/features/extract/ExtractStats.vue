<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted} from 'vue';
import type {ExtractDeps,ExtractMetrics} from './contracts';
import {createExtractStats} from './useExtractStats';
import {count,duration,modeLabel,number,providerLabel,rate,time} from './presentation';
const props=defineProps<{deps?:ExtractDeps}>(),stats=createExtractStats(props.deps||{}),{state}=stats;
const data=computed(()=>state.data),totals=computed(()=>data.value?.totals||{}),current=computed(()=>data.value?.current||{}),daily=computed(()=>data.value?.daily||[]),today=computed(()=>daily.value.at(-1)||{});
const providers=computed(()=>Object.entries(state.providers).filter(([id])=>id!=='lumen'));
const failures=computed(()=>(data.value?.failures||[])
 .filter(item=>count(item.count)>0)
 .sort((a,b)=>count(b.count)-count(a.count))
 .slice(0,5));
const failureMax=computed(()=>Math.max(1,...failures.value.map(item=>count(item.count))));
const series=[{key:'total',label:'任务总数',tone:'total'},{key:'extracted',label:'已出链',tone:'extracted'},{key:'paid',label:'已支付',tone:'paid'}] as const;
const hasTrend=computed(()=>daily.value.some(item=>count(item.total)>0));
const maximum=computed(()=>{const peak=Math.max(1,...daily.value.flatMap(item=>series.map(s=>count(item[s.key]))));return peak<=4?4:Math.ceil(peak/4)*4;});
const x=(index:number)=>48+(daily.value.length===1?406:index*812/Math.max(1,daily.value.length-1));
const y=(value:unknown)=>22+184*(1-count(value)/maximum.value);
const ticks=computed(()=>[...new Set([0,...daily.value.map((_,index)=>index).filter(index=>index%Math.max(1,Math.ceil(daily.value.length/7))===0),daily.value.length-1])].filter(index=>index>=0));
const path=(key:'total'|'extracted'|'paid')=>daily.value.map((item,index)=>`${index?'L':'M'}${x(index).toFixed(2)},${y(item[key]).toFixed(2)}`).join(' ');
const percent=(item:ExtractMetrics)=>count(totals.value.total)?Math.min(100,count(item.total)/count(totals.value.total)*100):0;
function setVisible(value:boolean){stats.setVisible(value);}
onMounted(()=>void stats.load());onBeforeUnmount(stats.destroy);defineExpose({load:stats.load,setVisible});
</script>
<template>
 <section class="extract-stats-page" :aria-busy="state.loading">
  <div class="es-controls">
   <div class="es-periods" role="group" aria-label="统计时间范围"><button v-for="days in [7,30,90]" :key="days" type="button" :data-extract-stats-days="days" :aria-pressed="state.days===days" @click="state.days=days;stats.load()">近 {{ days }} 天</button></div>
   <label>平台<select v-model="state.provider" data-extract-stats-provider @change="stats.load"><option value="">全部平台</option><option v-for="[id,label] in providers" :key="id" :value="id">{{ label }}</option></select></label>
   <button type="button" class="ui-refresh-button" data-extract-stats-refresh :disabled="state.loading" @click="stats.load">刷新</button>
   <span class="es-updated" role="status">{{ state.loading?'正在汇总提链任务…':data?.generated_at?`更新于 ${time(data.generated_at)}`:'' }}</span>
  </div>
  <div v-if="state.error" class="es-notice" role="alert"><span>{{ state.data?'刷新失败，以下保留上次统计。':'未取得所选范围的统计。' }}{{ state.error }}</span><button type="button" data-extract-stats-retry @click="stats.load">重试</button></div>
  <div v-if="!data&&state.loading" class="es-empty" role="status">正在汇总提链任务…</div>
  <template v-if="data">
   <section class="es-today" aria-label="今日与当前"><div class="es-panel-header"><h2>今日与当前</h2><span>今日任务按北京时间创建日归属</span></div><dl><div><dt>今日任务出链</dt><dd>{{ number(today.extracted) }}</dd></div><div><dt>今日任务 Plus</dt><dd>{{ number(today.plus_confirmed) }}</dd></div><div><dt>当前待支付<small>全部日期</small></dt><dd>{{ number(current.awaiting_payment) }}</dd></div></dl></section>
   <div class="es-scope"><span>{{ data.date_from||'—' }} — {{ data.date_to||'—' }}</span><span>按北京时间任务创建日归属</span></div>
   <div class="es-metrics"><article v-for="metric in [{key:'total',label:'任务总数',hint:'所选时间内创建的任务'},{key:'extracted',label:'已出链',hint:'已获得支付链接'},{key:'paid',label:'已支付',hint:'支付结果已确认'},{key:'plus_confirmed',label:'Plus 已确认',hint:'套餐到账已核验'}] as const" :key="metric.key" class="es-metric" :class="`es-metric--${metric.key}`"><span>{{ metric.label }}</span><strong>{{ number(totals[metric.key]) }}</strong><small>{{ metric.hint }}</small></article></div>
   <div class="es-summary-grid"><section class="es-panel"><div class="es-panel-header"><h2>转化与耗时</h2><span>未结束任务不进入成功率分母</span></div><dl class="es-conversion"><div><dt>提链成功率</dt><dd>{{ rate(totals.extraction_rate) }}</dd><span>已出链 /（已出链 + 提链失败）</span><small>出链 {{ number(totals.extracted) }} · 失败 {{ number(totals.extraction_failed) }}</small></div><div><dt>支付成功率</dt><dd>{{ rate(totals.payment_rate) }}</dd><span>已支付 /（已支付 + 支付失败）</span><small>支付 {{ number(totals.paid) }} · 失败 {{ number(totals.payment_failed) }}</small></div><div><dt>平均耗时</dt><dd>{{ duration(totals.avg_seconds) }}</dd><span>最新成功运行的总耗时</span></div></dl></section>
   <section class="es-panel"><div class="es-panel-header"><h2>区间任务状态</h2><span>所选范围的最新结果</span></div><dl class="es-state-grid"><div v-for="metric in [{key:'failed',label:'失败'},{key:'processing',label:'处理中'},{key:'awaiting_payment',label:'待支付'}] as const" :key="metric.key"><dt>{{ metric.label }}</dt><dd>{{ number(totals[metric.key]) }}</dd></div></dl><p class="es-current">{{ state.provider?'当前所选平台':'当前全部平台' }}，全部日期：处理中 {{ number(current.processing) }} · 待支付 {{ number(current.awaiting_payment) }}</p></section></div>
   <div class="es-chart-grid"><section class="es-panel es-trend"><div class="es-panel-header"><h2>每日趋势</h2><span>按北京时间任务创建日归属</span></div><template v-if="hasTrend"><div class="es-legend"><span v-for="s in series" :key="s.key" :class="`es-series--${s.tone}`">{{ s.label }}</span></div><svg viewBox="0 0 880 242" role="img" aria-label="每日提链任务、出链和支付趋势"><title>每日提链趋势，完整数据见下方表格</title><g v-for="i in [0,1,2,3,4]" :key="i"><line x1="48" x2="860" :y1="y(maximum*i/4)" :y2="y(maximum*i/4)" class="es-chart-gridline"/><text x="38" :y="y(maximum*i/4)+4" text-anchor="end" class="es-chart-label">{{ number(maximum*i/4) }}</text></g><text v-for="i in ticks" :key="i" :x="x(i)" y="232" text-anchor="middle" class="es-chart-label">{{ String(daily[i]?.date||'').slice(5) }}</text><path v-for="s in series" :key="s.key" :d="path(s.key)" class="es-chart-line" :class="`es-series--${s.tone}`"/></svg></template><div v-else class="es-empty"><strong>这个时间段还没有提链任务</strong><p>选择其他时间范围，或在提链工作台新建批次。</p></div><details v-if="daily.length" class="es-daily-data"><summary>查看每日明细数据</summary><div class="es-table-scroll"><table aria-label="每日趋势数据"><thead><tr><th>日期（北京时间）</th><th>任务总数</th><th>已出链</th><th>已支付</th><th>Plus 已确认</th></tr></thead><tbody><tr v-for="row in daily" :key="row.date"><th>{{ row.date }}</th><td>{{ number(row.total) }}</td><td>{{ number(row.extracted) }}</td><td>{{ number(row.paid) }}</td><td>{{ number(row.plus_confirmed) }}</td></tr></tbody></table></div></details></section>
   <section class="es-panel"><div class="es-panel-header"><h2>失败分类</h2><span>{{ number(totals.failed) }} 个失败任务</span></div><ol v-if="failures.length" class="es-failures"><li v-for="item in failures" :key="item.code||item.label"><div><span>{{ item.label||item.code||'原因未记录' }}</span><strong>{{ number(item.count) }}</strong></div><div class="es-failure-track" aria-hidden="true"><span :style="{width:`${count(item.count)/failureMax*100}%`}"></span></div><code>{{ item.code||'未记录错误码' }}</code></li></ol><div v-else class="es-empty"><strong>暂无失败记录</strong><p>所选范围没有失败任务。</p></div></section></div>
   <section class="es-panel"><div class="es-panel-header"><h2>平台对比</h2><span>支付成功与 Plus 到账分别统计</span></div><div v-if="data.providers?.length" class="es-table-scroll" tabindex="0" aria-label="平台统计，可左右滚动"><table class="es-provider-table"><thead><tr><th>平台</th><th>任务数</th><th>已出链</th><th title="已出链 /（已出链 + 提链失败）">提链成功率</th><th>已支付</th><th title="已支付 /（已支付 + 支付失败）">支付成功率</th><th>Plus 已确认</th><th>失败</th><th>处理中</th><th title="最新成功运行的平均总耗时">平均耗时</th></tr></thead><tbody><tr v-for="row in data.providers" :key="row.provider_id"><th>{{ providerLabel(row.provider_id) }}</th><td>{{ number(row.total) }}</td><td>{{ number(row.extracted) }}</td><td :title="`已出链 ${number(row.extracted)}，提链失败 ${number(row.extraction_failed)}`">{{ rate(row.extraction_rate) }}</td><td>{{ number(row.paid) }}</td><td :title="`已支付 ${number(row.paid)}，支付失败 ${number(row.payment_failed)}`">{{ rate(row.payment_rate) }}</td><td>{{ number(row.plus_confirmed) }}</td><td>{{ number(row.failed) }}</td><td>{{ number(row.processing) }}</td><td>{{ duration(row.avg_seconds) }}</td></tr></tbody></table></div><div v-else class="es-empty"><strong>暂无平台数据</strong><p>所选范围没有提链任务。</p></div></section>
   <section class="es-panel"><div class="es-panel-header"><h2>模式分布</h2><span>所选范围内的任务组成</span></div><div v-if="data.modes?.length" class="es-modes"><article v-for="row in data.modes" :key="row.mode" class="es-mode"><div><h3>{{ modeLabel(row.mode) }}</h3><span>{{ count(totals.total)?rate(percent(row)/100):'—' }}</span></div><strong>{{ number(row.total) }}<small> 个任务</small></strong><div class="es-mode-track" aria-hidden="true"><span :style="{width:`${percent(row)}%`}"></span></div><dl><div v-for="metric in [{key:'extracted',label:'出链'},{key:'paid',label:'支付'},{key:'plus_confirmed',label:'Plus'},{key:'failed',label:'失败'}] as const" :key="metric.key"><dt>{{ metric.label }}</dt><dd>{{ number(row[metric.key]) }}</dd></div></dl></article></div><div v-else class="es-empty">暂无模式数据</div></section>
  </template>
 </section>
</template>
<style scoped>
.extract-stats-page{display:flex;flex-direction:column;gap:16px;padding:18px 20px;color:var(--ui-color-text);min-width:0}
.es-controls,.es-periods,.es-scope,.es-panel-header{display:flex;align-items:center;gap:10px 12px}
.es-scope,.es-panel-header{justify-content:space-between}
.es-panel-header>span,.es-scope,.es-updated,small{color:var(--ui-color-text-secondary);font-size:12px}
.es-controls{flex-wrap:wrap;padding:10px 14px;border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-lg,12px);background:var(--ui-color-surface);box-shadow:var(--ui-shadow-sm)}
.es-periods{gap:4px;padding:3px;border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-md,8px);background:var(--ui-color-surface-subtle)}
.es-controls label{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--ui-color-text-secondary)}
.es-controls button,.es-notice button,.es-controls select{min-height:32px;height:32px;padding:0 12px;border:1px solid var(--ui-color-border-strong);border-radius:var(--ui-radius-sm,6px);background:var(--ui-color-surface);color:var(--ui-color-text);font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;transition:border-color .15s ease,background .15s ease,color .15s ease}
.es-periods button{min-height:28px;height:28px;border-color:transparent;background:transparent;color:var(--ui-color-text-secondary)}
.es-periods button:hover{color:var(--ui-color-text);background:var(--ui-color-surface)}
.es-controls button[aria-pressed=true]{border-color:transparent;color:var(--ui-color-brand);background:var(--ui-color-surface);box-shadow:0 1px 2px rgba(16,24,40,.06)}
.es-controls button:hover:not(:disabled):not([aria-pressed=true]){border-color:#b9bfce;background:var(--ui-color-surface-subtle)}
.es-updated{margin-left:auto;font-variant-numeric:tabular-nums}
.es-today,.es-panel,.es-metric{border:1px solid var(--ui-color-border);border-radius:var(--ui-radius-lg,12px);background:var(--ui-color-surface);padding:18px;min-width:0;box-shadow:var(--ui-shadow-sm)}
.es-today{background:linear-gradient(180deg,var(--ui-color-surface-subtle) 0%,var(--ui-color-surface) 100%)}
h2{font-size:15px;font-weight:700;margin:0}
.es-panel-header{align-items:baseline;flex-wrap:wrap;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid #f1f3f8}
.es-today dl,.es-state-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0}
.es-today dt{font-size:12.5px;color:var(--ui-color-text-secondary)}
.es-today small{margin-left:5px}
.es-today dd{font-size:24px;font-weight:720;margin:6px 0 0;font-variant-numeric:tabular-nums}
.es-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.es-metric{display:flex;flex-direction:column;gap:6px;border-top:3px solid var(--ui-color-border-strong)}
.es-metric--total{border-top-color:var(--ui-color-text-muted)}
.es-metric--extracted{border-top-color:var(--ui-color-brand)}
.es-metric--paid{border-top-color:var(--ui-color-success)}
.es-metric--plus_confirmed{border-top-color:#7c5cf0}
.es-metric>span{font-size:12.5px;color:var(--ui-color-text-secondary);font-weight:600}
.es-metric strong{font-size:30px;line-height:1.15;font-variant-numeric:tabular-nums}
.es-metric--extracted strong{color:var(--ui-color-brand)}
.es-metric--paid strong{color:var(--ui-color-success)}
.es-summary-grid,.es-chart-grid{display:grid;gap:16px;grid-template-columns:minmax(0,3fr) minmax(260px,2fr)}
.es-conversion{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:0}
.es-conversion>div{padding:12px 14px;border-radius:10px;background:var(--ui-color-surface-subtle);border:1px solid #eef1f6}
.es-conversion dd{font-size:22px;font-weight:700;margin:6px 0;font-variant-numeric:tabular-nums}
.es-conversion dt{font-size:12.5px;font-weight:600}
.es-conversion span,.es-conversion small{display:block;font-size:11px;color:var(--ui-color-text-secondary);line-height:1.65}
.es-state-grid{grid-template-columns:1fr 1fr;gap:12px}
.es-state-grid div{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border-radius:8px;background:var(--ui-color-surface-subtle);font-size:13px}
.es-state-grid dd{margin:0;font-weight:700;font-variant-numeric:tabular-nums}
.es-current{font-size:12px;color:var(--ui-color-text-secondary);margin:16px 0 0;line-height:1.7}
.es-trend svg{width:100%;height:auto;display:block}
.es-chart-line{fill:none;stroke-width:2.5;vector-effect:non-scaling-stroke}
.es-chart-gridline{stroke:var(--ui-color-border);stroke-dasharray:3 4}
.es-chart-label{font:11px sans-serif;fill:var(--ui-color-text-secondary)}
.es-series--total{stroke:var(--ui-color-brand);color:var(--ui-color-brand)}
.es-series--extracted{stroke:var(--ui-color-success);color:var(--ui-color-success)}
.es-series--paid{stroke:var(--ui-color-warning,#b37918);color:var(--ui-color-warning,#b37918)}
.es-legend{display:flex;gap:16px;font-size:12px;margin-bottom:10px}
.es-legend span::before{content:'●';margin-right:5px}
.es-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:140px;padding:16px;border:1px dashed var(--ui-color-border-strong);border-radius:10px;background:var(--ui-color-surface-subtle);gap:8px;text-align:center;color:var(--ui-color-text-secondary);font-size:13px}
.es-empty p{margin:0}
.es-table-scroll{overflow:auto;min-width:0}
.es-table-scroll table{width:100%;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums}
.es-table-scroll th,.es-table-scroll td{padding:11px 12px;text-align:right;border-bottom:1px solid var(--ui-color-border);white-space:nowrap}
.es-table-scroll th:first-child,.es-table-scroll td:first-child{text-align:left}
.es-table-scroll thead{color:var(--ui-color-text-secondary);background:var(--ui-color-surface-subtle)}
.es-daily-data{font-size:12px;margin-top:14px}
.es-daily-data summary{cursor:pointer;color:var(--ui-color-text-secondary);font-weight:600}
.es-failures{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:14px}
.es-failures li{padding:10px 12px;border-radius:8px;background:var(--ui-color-surface-subtle);border:1px solid #eef1f6}
.es-failures li>div:first-child{display:flex;justify-content:space-between;gap:8px;font-size:13px;overflow-wrap:anywhere}
.es-failures code{font-size:11px;color:var(--ui-color-text-secondary);overflow-wrap:anywhere}
.es-failure-track,.es-mode-track{height:5px;background:#e6eaf2;border-radius:3px;margin:8px 0;overflow:hidden}
.es-failure-track span,.es-mode-track span{display:block;height:100%;background:var(--ui-color-brand);border-radius:3px}
.es-modes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.es-mode{background:var(--ui-color-surface-subtle);border:1px solid var(--ui-color-border);border-radius:10px;padding:15px}
.es-mode>div:first-child{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.es-mode h3{font-size:13px;margin:0}
.es-mode>strong{display:block;margin:12px 0;font-size:24px;font-variant-numeric:tabular-nums}
.es-mode dl{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:12px 0 0;font-size:12px}
.es-mode dt{color:var(--ui-color-text-secondary)}
.es-mode dd{margin:6px 0 0;font-weight:650;font-variant-numeric:tabular-nums}
.es-notice{padding:12px 15px;border:1px solid var(--ui-color-danger-border);border-radius:var(--ui-radius-md);background:var(--ui-color-danger-soft);color:var(--ui-color-danger);display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:13px}
button:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid var(--ui-color-brand);outline-offset:3px}
@media(max-width:950px){.es-summary-grid,.es-chart-grid{grid-template-columns:1fr}.es-modes{grid-template-columns:1fr}.es-today dl{grid-template-columns:1fr 1fr}}
@media(max-width:600px){.extract-stats-page{padding:12px;gap:12px}.es-panel,.es-today,.es-metric{padding:14px}.es-metrics{grid-template-columns:1fr 1fr;gap:10px}.es-conversion{grid-template-columns:1fr;gap:12px}.es-today dd{font-size:20px}.es-updated{margin-left:0;width:100%}.es-periods{gap:4px}.es-controls button,.es-controls select{min-height:38px}.es-scope{align-items:flex-start;flex-direction:column;gap:5px}}
</style>
