<script setup lang="ts">
import {computed,ref,useId,watch} from 'vue';
import type {DailyPromotionOffer,DailyRegistrationRow,DailyRegistrationStatsState,DailyRegistrationSummary} from './contracts';
import type {AccountQuerySpec} from '../accounts/queryAdapter';

const props=defineProps<{
 state:DailyRegistrationStatsState;
 onBulkPlanCreate?:(value:{name:string;query:AccountQuerySpec})=>void;
}>();

type RangeMode='7'|'30'|'custom';
const mode=ref<RangeMode>('7');
const customFrom=ref('');
const customTo=ref('');
const customReady=ref(false);
const selectedDate=ref('');
const detailId=`daily-registration-detail-${useId()}`;

const rows=computed(()=>Array.isArray(props.state.data?.rows)?props.state.data!.rows!:[]);
const dataRange=computed(()=>({
 from:props.state.data?.date_from||rows.value[0]?.date||'',
 to:props.state.data?.date_to||rows.value[rows.value.length-1]?.date||'',
}));
const rangeLabel=computed(()=>dataRange.value.from&&dataRange.value.to
 ? `${dataRange.value.from} 至 ${dataRange.value.to}`
 : '日期范围待返回');
const updatedLabel=computed(()=>props.state.updatedAt
 ? `更新于 ${new Date(props.state.updatedAt).toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})}`
 : props.state.loading?'正在读取…':'尚未读取');
const errorLabel=computed(()=>props.state.error&&props.state.data&&props.state.scopeCurrent
 ? `${props.state.error}，当前成功范围仍可使用。`
 : props.state.error);
const selectedRow=computed(()=>rows.value.find(row=>row.date===selectedDate.value));

const planLabels:Record<string,string>={team:'Team',plus:'Plus',go:'Go'};
const planOrder=['team','plus','go'];
type ChartSegment=DailyPromotionOffer&{color:string};
function compareOffers(left:DailyPromotionOffer,right:DailyPromotionOffer):number{
 const rank=(plan:string)=>{const index=planOrder.indexOf(plan);return index<0?planOrder.length:index;};
 return rank(left.plan)-rank(right.plan)||left.label.localeCompare(right.label,'zh-CN')||left.key.localeCompare(right.key);
}
function offerColor(offer:DailyPromotionOffer):string{
 let hash=0;
 for(const character of offer.key)hash=(hash*31+character.charCodeAt(0))>>>0;
 const hue=({team:156,plus:250,go:35} as Record<string,number>)[offer.plan]??210;
 return `hsl(${hue+hash%25-12} ${52+(hash>>>5)%20}% ${39+(hash>>>10)%18}%)`;
}
function rowOffers(row:DailyRegistrationRow|DailyRegistrationSummary):DailyPromotionOffer[]|null{
 if(!Array.isArray(row.offers))return null;
 return row.offers.map((offer:DailyPromotionOffer)=>({...offer,count:Math.max(0,number(offer.count)),stale_count:Math.max(0,number(offer.stale_count))})).sort(compareOffers);
}
function offerGroups(row:DailyRegistrationRow|DailyRegistrationSummary){
 const groups=new Map<string,DailyPromotionOffer[]>();
 for(const offer of rowOffers(row)??[])groups.set(offer.plan,[...(groups.get(offer.plan)??[]),offer]);
 return [...groups].map(([plan,offers])=>({plan,label:planLabels[plan]||plan,offers}));
}
const chartRows=computed(()=>rows.value.map(row=>{
 const offers=rowOffers(row);
 const segments:ChartSegment[]=(offers??[]).filter(offer=>offer.count>0).map(offer=>({...offer,color:offerColor(offer)}));
 return {row,unavailable:offers===null,segments,total:offers===null?null:segments.reduce((sum,segment)=>sum+segment.count,0)};
}));
const axisStep=computed(()=>Math.max(1,Math.ceil(Math.max(0,...chartRows.value.map(item=>item.total??0))/4)));
const axisMax=computed(()=>axisStep.value*4);
const axisTicks=computed(()=>[4,3,2,1,0].map(value=>value*axisStep.value));
const chartLegend=computed(()=>{
 const series=new Map<string,ChartSegment>();
 for(const item of chartRows.value)for(const segment of item.segments)if(!series.has(segment.key))series.set(segment.key,segment);
 return [...series.values()].sort(compareOffers);
});
const hasUnavailableOffers=computed(()=>chartRows.value.some(item=>item.unavailable));

function chartLabel(item:typeof chartRows.value[number]):string{
 const details=item.unavailable?'优惠数据待查':item.segments.map(segment=>offerDetail(item.row,segment)).join('，');
 return `${item.row.date}，优惠覆盖数 ${display(item.total)}，账号总数 ${display(item.row.accounts_total)}，有优惠账号 ${display(item.row.promoted_accounts_total)}${details?`，${details}`:''}，点击查看当日详情`;
}
function selectDate(date:string){
 selectedDate.value=date;
}
function moveDate(event:KeyboardEvent,index:number){
 let next=index;
 if(event.key==='ArrowRight')next=Math.min(rows.value.length-1,index+1);
 else if(event.key==='ArrowLeft')next=Math.max(0,index-1);
 else if(event.key==='Home')next=0;
 else if(event.key==='End')next=rows.value.length-1;
 else return;
 event.preventDefault();
 const row=rows.value[next];
 if(!row)return;
 selectDate(row.date);
 const buttons=(event.currentTarget as HTMLElement).parentElement?.querySelectorAll<HTMLButtonElement>('[data-daily-bar]');
 buttons?.[next]?.focus({preventScroll:true});
 buttons?.[next]?.scrollIntoView?.({block:'nearest',inline:'nearest'});
}

function number(value:unknown):number{
 const parsed=Number(value);
 return Number.isFinite(parsed)?parsed:0;
}
function knownNumber(value:unknown):number|null{
 if(value===null||value===undefined)return null;
 const parsed=Number(value);
 return Number.isFinite(parsed)?parsed:null;
}
function offerShare(row:DailyRegistrationRow|DailyRegistrationSummary,value:number):string{
 const total=knownNumber(row.accounts_total);
 return total&&value>=0?`${Math.round(value/total*100)}%`:'—';
}
function offerDetail(row:DailyRegistrationRow|DailyRegistrationSummary,offer:DailyPromotionOffer):string{
 return `${offer.label} ${display(offer.count)}个账号 · ${offerShare(row,offer.count)}（占当日账号）`;
}
function display(value:unknown):string{
 const parsed=knownNumber(value);
 return parsed===null?'—':new Intl.NumberFormat('zh-CN').format(parsed);
}
function unpromotedDisplay(value:unknown):string{
 const parsed=knownNumber(value);
 return parsed===null?'待查':new Intl.NumberFormat('zh-CN').format(parsed);
}
function batchCount(row:DailyRegistrationRow|DailyRegistrationSummary):number|null{
 return knownNumber(row.unpromoted_count);
}
function canBatch(row:DailyRegistrationRow|DailyRegistrationSummary):boolean{
 return props.state.scopeCurrent&&batchCount(row)!==null&&batchCount(row)!>0&&!!row.query;
}
function createBatch(row:DailyRegistrationRow|DailyRegistrationSummary,name:string){
 if(!canBatch(row)||!row.query)return;
 props.onBulkPlanCreate?.({name,query:row.query as AccountQuerySpec});
}

function dayFrom(value:string,offset:number):string{
 const date=new Date(`${value}T00:00:00Z`);
 date.setUTCDate(date.getUTCDate()+offset);
 return date.toISOString().slice(0,10);
}
function beijingToday():string{
 const parts=new Intl.DateTimeFormat('en-US',{
  timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',
 }).formatToParts(new Date());
 const values=Object.fromEntries(parts.filter(part=>part.type!=='literal').map(part=>[part.type,part.value]));
 return `${values.year}-${values.month}-${values.day}`;
}
function presetRange(days:number):[string,string]{
 const end=beijingToday();
 return [dayFrom(end,-(days-1)),end];
}
function choosePreset(value:Exclude<RangeMode,'custom'>){
 mode.value=value;
 const [from,to]=presetRange(Number(value));
 void props.state.load(from,to);
}
function chooseCustom(){
 mode.value='custom';
 customFrom.value=props.state.displayedRange?.from||dataRange.value.from;
 customTo.value=props.state.displayedRange?.to||dataRange.value.to;
}
function applyCustom(){
 if(mode.value!=='custom'||!customFrom.value||!customTo.value||customFrom.value>customTo.value)return;
 void props.state.load(customFrom.value,customTo.value);
}

watch(rows,value=>{
 if(!value.some(row=>row.date===selectedDate.value))selectedDate.value=value[0]?.date||'';
},{immediate:true});
watch(()=>[props.state.data?.date_from,props.state.data?.date_to] as const,([from,to])=>{
 if(!customReady.value&&(from||to)){
  customFrom.value=from||'';
  customTo.value=to||'';
  customReady.value=true;
 }
},{immediate:true});
</script>

<template>
 <section class="daily-stats" aria-labelledby="daily-registration-title">
  <header class="daily-stats-head">
   <div>
    <h2 id="daily-registration-title">每日账号套餐优惠</h2>
    <p>北京时间 · 按注册任务创建日期关联账号 · 优惠以最近成功查询为准，并非注册当日历史 · 含归档账号</p>
   </div>
   <div class="daily-stats-meta">
    <span data-daily-range>{{rangeLabel}}</span>
    <span>{{updatedLabel}}</span>
   </div>
  </header>

  <div class="daily-stats-controls" role="group" aria-label="统计日期范围">
   <button type="button" data-daily-range-7 :class="{active:mode==='7'}" @click="choosePreset('7')">近 7 天</button>
   <button type="button" data-daily-range-30 :class="{active:mode==='30'}" @click="choosePreset('30')">近 30 天</button>
  <button type="button" :class="{active:mode==='custom'}" @click="chooseCustom">自定义</button>
   <template v-if="mode==='custom'">
    <label>开始日期<input v-model="customFrom" type="date" @change="applyCustom"></label>
    <label>结束日期<input v-model="customTo" type="date" @change="applyCustom"></label>
   </template>
  </div>

  <div v-if="state.error" class="daily-stats-error" data-daily-error role="alert">
   <span>{{errorLabel}}</span>
   <button type="button" data-daily-retry :disabled="state.loading" @click="state.load()">重试</button>
  </div>
  <div v-if="state.data&&!state.scopeCurrent" class="daily-stats-stale" data-daily-stale role="status">
   {{state.loading?'正在读取新日期范围，当前仍显示上一成功范围；完成前不能新建查套餐批量。':'新日期范围读取失败，当前仍显示上一成功范围；请重试后再新建查套餐批量。'}}
  </div>
  <div v-if="state.loading&&!state.data" class="daily-stats-loading" aria-live="polite">正在读取每日套餐优惠…</div>
  <template v-else-if="state.data">
   <div v-if="rows.length" class="daily-chart">
    <div class="daily-chart-heading">
     <strong>每日套餐优惠分布</strong>
     <p>点选日期查看详情 · 方向键切换日期</p>
    </div>
    <p class="daily-chart-note">同一账号有多项优惠时分别计数；每项按账号去重。占比 = 优惠账号数 ÷ 当日账号总数，多项占比合计可超过100%。</p>
    <div class="daily-chart-legend" data-daily-legend aria-label="套餐优惠图例">
     <span v-for="item in chartLegend" :key="item.key"><i :style="{backgroundColor:item.color}" aria-hidden="true"></i>{{item.label}}</span>
     <span v-if="hasUnavailableOffers">优惠数据待查</span>
     <span v-else-if="!chartLegend.length">暂无可用优惠记录</span>
    </div>
    <div class="daily-stats-chart" role="group" aria-label="每日账号套餐优惠覆盖堆叠柱状图">
     <div class="daily-chart-axis" data-daily-axis>
      <span class="daily-axis-unit">优惠覆盖数</span>
      <div class="daily-axis-ticks" aria-hidden="true"><span v-for="tick in axisTicks" :key="tick" data-daily-axis-tick>{{display(tick)}}</span></div>
     </div>
     <div class="daily-chart-scroll">
      <div class="daily-chart-plot" :style="{gridTemplateColumns:`repeat(${rows.length},minmax(64px,1fr))`,minWidth:`${rows.length*68}px`}">
       <div class="daily-chart-grid" aria-hidden="true"><i v-for="tick in axisTicks" :key="tick"></i></div>
       <button v-for="(item,index) in chartRows" :key="item.row.date" type="button" class="daily-bar-column" :class="{selected:item.row.date===selectedDate}"
        :data-daily-bar="item.row.date" :aria-label="chartLabel(item)" :title="chartLabel(item)" :aria-pressed="item.row.date===selectedDate" :aria-controls="detailId"
        :tabindex="item.row.date===selectedDate?0:-1" @click="selectDate(item.row.date)" @focus="selectDate(item.row.date)" @keydown="moveDate($event,index)">
        <span class="daily-bar-value" aria-hidden="true">
         <span data-daily-account-total>账号 {{display(item.row.accounts_total)}}</span>
         <span data-daily-coverage-total>覆盖 {{item.unavailable?'待查':display(item.total)}}</span>
        </span>
        <span class="daily-bar-stack" aria-hidden="true">
         <span v-for="segment in item.segments" :key="segment.key" class="daily-bar-segment"
          :data-daily-segment="segment.key" :title="offerDetail(item.row,segment)" :style="{height:`${segment.count/axisMax*100}%`,backgroundColor:segment.color}"></span>
        </span>
        <small aria-hidden="true">{{item.row.date.slice(5)}}</small>
       </button>
      </div>
     </div>
    </div>
   </div>

   <div v-if="selectedRow" :id="detailId" class="daily-selected-detail" aria-live="polite" aria-atomic="true">
    <article v-for="row in [selectedRow]" :key="row.date" class="daily-stats-row" :data-daily-row="row.date">
     <div class="daily-row-heading">
      <div><strong>{{row.date}}</strong><span>注册任务总数 {{display(row.total)}}</span></div>
      <button type="button" data-daily-bulk :disabled="!canBatch(row)" @click="createBatch(row,`${row.date} 无优惠账号查套餐`)">
       新建查套餐批量（{{unpromotedDisplay(row.unpromoted_count)}}）
      </button>
     </div>
     <div class="daily-row-metrics">
      <span>账号总数（含归档） {{display(row.accounts_total)}}</span>
      <span>有优惠账号 {{display(row.promoted_accounts_total)}}</span>
      <span>未归档 Plus 无优惠 {{unpromotedDisplay(row.unpromoted_count)}}</span>
     </div>
     <div class="daily-row-offers">
      <template v-if="rowOffers(row)">
       <div v-for="group in offerGroups(row)" :key="group.plan" class="daily-offer-group" :data-daily-offer-group="group.plan">
        <strong>{{group.label}}</strong>
        <div class="daily-offer-items">
         <div v-for="offer in group.offers" :key="offer.key" class="daily-offer-item" :data-daily-offer="offer.key">
          <span class="daily-offer-name"><i :style="{backgroundColor:offerColor(offer)}" aria-hidden="true"></i>{{offer.label}}</span>
          <span class="daily-offer-count">{{display(offer.count)}} 个账号 · {{offerShare(row,offer.count)}}</span>
          <span v-if="offer.stale_count>0" class="daily-offer-stale">{{display(offer.stale_count)}} 个待复查</span>
         </div>
        </div>
       </div>
       <span v-if="!rowOffers(row)!.length" class="daily-offers-empty">暂无可用优惠记录（含无优惠或未查询账号）。</span>
      </template>
      <span v-else class="daily-offers-empty">优惠数据待查</span>
     </div>
    </article>
   </div>
   <p v-else class="daily-stats-empty">所选日期暂无统计。</p>

   <div v-if="state.data.summary" class="daily-stats-summary">
    <div>
     <strong>区间汇总</strong>
     <span>注册任务总数 {{display(state.data.summary.total)}} · 账号总数（含归档，区间去重） {{display(state.data.summary.accounts_total)}} · 有优惠账号 {{display(state.data.summary.promoted_accounts_total)}} · 未归档 Plus 无优惠 {{unpromotedDisplay(state.data.summary.unpromoted_count)}}</span>
    </div>
    <button type="button" data-daily-summary-bulk :disabled="!canBatch(state.data.summary)" @click="createBatch(state.data.summary,`${dataRange.from}..${dataRange.to} 无优惠账号查套餐`)">
     新建区间查套餐批量（{{unpromotedDisplay(state.data.summary.unpromoted_count)}}）
    </button>
   </div>
  </template>
 </section>
</template>

<style scoped>
.daily-stats{display:flex;flex-direction:column;gap:14px;min-width:0;padding:18px;border:1px solid #e6e9f0;border-radius:14px;background:#fff;box-shadow:0 1px 2px rgba(16,24,40,.03),0 6px 18px rgba(16,24,40,.035);color:#172033}
.daily-stats-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;flex-wrap:wrap}
.daily-stats-head h2{margin:0;font-size:17px;line-height:1.3;font-weight:700}
.daily-stats-head p{margin:4px 0 0;color:#647086;font-size:12px;line-height:1.5}
.daily-stats-meta{display:flex;gap:12px;flex-wrap:wrap;color:#647086;font-size:11.5px;font-variant-numeric:tabular-nums}
.daily-stats-controls{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.daily-stats-controls>button,.daily-stats-controls input{min-height:34px;border:1px solid #dfe3eb;border-radius:7px;background:#fff;color:#475569;font:inherit;font-size:12px}
.daily-stats-controls>button{padding:0 11px;cursor:pointer}
.daily-stats-controls>button.active{border-color:#5b5ce2;background:#eef0ff;color:#4f51be;font-weight:650}
.daily-stats-controls label{display:flex;align-items:center;gap:6px;color:#647086;font-size:11.5px}
.daily-stats-controls input{padding:0 8px}
.daily-stats-controls button:focus-visible,.daily-stats-controls input:focus-visible,.daily-stats-row button:focus-visible,.daily-stats-summary button:focus-visible,.daily-stats-error button:focus-visible{outline:2px solid #5b5ce2;outline-offset:2px}
.daily-stats-error{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 11px;border:1px solid #efc2c7;border-radius:8px;background:#fff7f8;color:#9f2f39;font-size:12px}
.daily-stats-error button{min-height:30px;padding:0 10px;border:1px solid #b03a44;border-radius:6px;background:#fff;color:#9f2f39;font:inherit;font-size:11.5px;font-weight:650;cursor:pointer}
.daily-stats-error button:disabled{opacity:.5;cursor:default}
.daily-stats-stale{padding:9px 11px;border:1px solid #f0cf9b;border-radius:8px;background:#fff9ed;color:#8a5a12;font-size:12px;line-height:1.5}
.daily-stats-loading,.daily-stats-empty{padding:20px;border:1px dashed #dfe3eb;border-radius:9px;color:#647086;font-size:12px;text-align:center}
.daily-chart,.daily-selected-detail{min-width:0}
.daily-chart{--daily-header-height:38px;--daily-plot-height:164px;display:flex;flex-direction:column;gap:11px}
.daily-chart-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.daily-chart-heading p{margin:0;color:#647086;font-size:11px;line-height:1.5}
.daily-chart-heading>strong{font-size:12px;font-weight:650}
.daily-chart-note{margin:-4px 0 0;color:#647086;font-size:11px;line-height:1.5}
.daily-chart-legend{display:flex;flex-wrap:wrap;gap:6px 14px;color:#566175;font-size:11px;line-height:1.4}
.daily-chart-legend>span{display:inline-flex;align-items:center;gap:5px}
.daily-chart-legend i{display:inline-block;width:9px;height:9px;flex:none;border-radius:2px}
.daily-stats-chart{display:grid;grid-template-columns:auto minmax(0,1fr);gap:9px;min-width:0}
.daily-chart-axis{display:grid;grid-template-rows:var(--daily-header-height) var(--daily-plot-height) 28px;min-width:30px;color:#647086;font-size:10px;font-variant-numeric:tabular-nums}
.daily-axis-unit{align-self:start;font-size:10px;white-space:nowrap}
.daily-axis-ticks{display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end;position:relative}
.daily-axis-ticks span{line-height:1;transform:translateY(-50%)}
.daily-axis-ticks span:last-child{transform:translateY(50%)}
.daily-chart-scroll{min-width:0;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin;padding-bottom:3px}
.daily-chart-plot{position:relative;display:grid;gap:0}
.daily-chart-grid{position:absolute;inset:var(--daily-header-height) 0 28px;display:flex;flex-direction:column;justify-content:space-between;pointer-events:none}
.daily-chart-grid i{height:0;border-top:1px dashed #edf0f5}
.daily-chart-grid i:last-child{border-top:1px solid #dfe3eb}
.daily-bar-column{position:relative;display:grid;grid-template-rows:var(--daily-header-height) var(--daily-plot-height) 28px;justify-items:center;min-width:0;padding:0 3px;border:0;border-radius:6px;background:transparent;color:#647086;font:inherit;cursor:pointer;transition:background-color .12s ease}
.daily-bar-column:hover{background:#f6f7fb}
.daily-bar-column.selected{background:#eef0ff}
.daily-bar-column:focus-visible{outline:2px solid #5b5ce2;outline-offset:-2px}
.daily-bar-stack{display:flex;flex-direction:column-reverse;align-self:stretch;align-items:stretch;width:28px;max-width:80%}
.daily-bar-segment{display:block;width:100%;flex:none}
.daily-bar-segment:last-child{border-radius:4px 4px 0 0}
.daily-bar-column small{align-self:center;font-size:10px;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap}
.daily-bar-column.selected small{color:#4f51be;font-weight:700}
.daily-bar-value{align-self:start;display:flex;flex-direction:column;gap:2px;max-width:100%;white-space:nowrap;color:#566175;font-size:10px;line-height:1.4;font-variant-numeric:tabular-nums}
.daily-stats-row{display:flex;flex-direction:column;gap:9px;min-width:0;padding:12px;border:1px solid #edf0f5;border-radius:9px;background:#fafbfd}
.daily-row-heading{display:flex;align-items:center;justify-content:space-between;gap:8px}
.daily-row-heading>div{display:flex;align-items:baseline;gap:8px;min-width:0}
.daily-row-heading strong{font-size:13px;font-variant-numeric:tabular-nums}
.daily-row-heading span{color:#647086;font-size:11.5px}
.daily-row-heading button,.daily-stats-summary button{min-height:30px;padding:0 9px;border:1px solid #5b5ce2;border-radius:6px;background:#fff;color:#4f51be;font:inherit;font-size:11px;font-weight:650;cursor:pointer;white-space:nowrap}
.daily-row-heading button:disabled,.daily-stats-summary button:disabled{border-color:#dfe3eb;background:#f5f6f8;color:#9aa3b2;cursor:not-allowed}
.daily-row-metrics{display:flex;flex-wrap:wrap;gap:5px 14px;color:#566175;font-size:11.5px;line-height:1.5;font-variant-numeric:tabular-nums}
.daily-row-offers{display:flex;flex-direction:column;gap:10px;padding-top:3px}
.daily-offer-group{display:grid;grid-template-columns:42px minmax(0,1fr);gap:9px;align-items:baseline}
.daily-offer-group>strong{color:#475569;font-size:11.5px;font-weight:650}
.daily-offer-items{display:flex;flex-direction:column;gap:6px;min-width:0}
.daily-offer-item{display:flex;align-items:baseline;gap:5px 12px;flex-wrap:wrap;color:#566175;font-size:11.5px;line-height:1.5}
.daily-offer-name{display:inline-flex;align-items:center;gap:6px;min-width:0;overflow-wrap:anywhere}
.daily-offer-name i{display:inline-block;width:9px;height:9px;flex:none;border-radius:2px}
.daily-offer-count{font-variant-numeric:tabular-nums;white-space:nowrap}
.daily-offer-stale{color:#8a5a12;font-size:11px;white-space:nowrap}
.daily-offers-empty{color:#647086;font-size:11.5px;line-height:1.5}
.daily-stats-summary{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding-top:12px;border-top:1px solid #edf0f5}
.daily-stats-summary>div{display:flex;flex-direction:column;gap:3px;min-width:0}
.daily-stats-summary strong{font-size:12.5px}
.daily-stats-summary span{color:#647086;font-size:11.5px;line-height:1.5}
@media(max-width:620px){
 .daily-stats{padding:15px}
 .daily-stats-meta{width:100%}
 .daily-chart{--daily-plot-height:140px}
 .daily-chart-heading p{width:100%;font-size:10.5px}
 .daily-stats-controls label{max-width:100%}
 .daily-stats-controls input{min-width:0;max-width:100%}
 .daily-row-heading{align-items:flex-start;flex-direction:column}
 .daily-row-heading button,.daily-stats-summary button{width:100%}
}
@media(prefers-reduced-motion:reduce){.daily-stats *{transition:none!important}}
</style>
