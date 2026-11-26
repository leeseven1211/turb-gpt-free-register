<script setup lang="ts">
import {computed,ref,useId,watch} from 'vue';
import type {DailyRegistrationRow,DailyRegistrationStatsState,DailyRegistrationSummary} from './contracts';
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
const chartView=ref<'status'|'plans'>('status');
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

const planLabels:Record<string,string>={
 free:'Free',free_trial_eligible:'Free · 试用资格',free_half_price_eligible:'Free · 半价资格',
 free_discount_eligible:'Free · 折扣资格',free_promo_unknown:'Free · 优惠待查',
 plus:'Plus',pro:'Pro',team:'Team',go:'Go',unknown:'未检测',
};
const statusLabels:Record<string,string>={
 success:'成功',partial_success:'部分成功',failed:'失败',active:'进行中',cancelled:'取消',
 };
const extraStatusLabels:Record<string,string>={
 interrupted:'执行中断',unsupported:'不支持',deactivated:'已停用',
};
type ChartSegment={key:string;label:string;value:number;color:string};
const statusSeries=[
 {key:'success',label:'成功',keys:['success'],color:'#249b72'},
 {key:'partial_success',label:'部分成功',keys:['partial_success'],color:'#d39a27'},
 {key:'failed',label:'失败',keys:['failed'],color:'#df5a67'},
 {key:'active',label:'进行中',keys:['pending','queued','running','waiting','settling','stopping','cancelling'],color:'#4c86db'},
 {key:'cancelled',label:'取消',keys:['cancelled','stopped'],color:'#98a2b3'},
 {key:'interrupted',label:'执行中断',keys:['interrupted'],color:'#8b68c9'},
 {key:'unsupported',label:'不支持',keys:['unsupported'],color:'#b29bd7'},
 {key:'deactivated',label:'已停用',keys:['deactivated'],color:'#667085'},
];
const planColors:Record<string,string>={
 free:'#a5adbb',free_trial_eligible:'#4f9f88',free_half_price_eligible:'#6aab9b',
 free_discount_eligible:'#92bdb0',free_promo_unknown:'#baccc6',
 plus:'#6564d8',pro:'#4c86db',team:'#249b72',go:'#d39a27',unknown:'#d0d5df',
};
const planOrder=Object.keys(planLabels);
function comparePlanSeries(left:{key:string},right:{key:string}):number{
 const leftIndex=planOrder.indexOf(left.key);
 const rightIndex=planOrder.indexOf(right.key);
 return (leftIndex<0?planOrder.length:leftIndex)-(rightIndex<0?planOrder.length:rightIndex)||left.key.localeCompare(right.key);
}
const chartRows=computed(()=>rows.value.map(row=>{
 const unavailable=chartView.value==='status'?row.counts==null:row.plans==null;
 const total=chartView.value==='status'?knownNumber(row.total):knownNumber(row.accounts_total);
 let segments:ChartSegment[];
 if(unavailable){
  segments=[{key:'unavailable',label:chartView.value==='status'?'状态待查':'套餐待查',value:Math.max(0,total??0),color:'#b5bdcd'}];
 }else if(chartView.value==='status'){
  segments=statusSeries.map(series=>({...series,value:groupedCount(row,series.keys)??0}));
  const knownTotal=segments.reduce((sum,segment)=>sum+segment.value,0);
  if(total!==null&&total>knownTotal)segments.push({key:'other',label:'其他状态',value:total-knownTotal,color:'#b5bdcd'});
 }else{
  segments=(plans(row)??[]).map(plan=>({key:plan.key,label:plan.label,value:plan.count,color:planColors[plan.key]||'#8b8fa3'}))
   .sort(comparePlanSeries);
 }
 const visibleSegments=segments.filter(segment=>segment.value>0);
 return {row,total,unavailable,segments:visibleSegments,stackTotal:visibleSegments.reduce((sum,segment)=>sum+segment.value,0)};
}));
const axisStep=computed(()=>Math.max(1,Math.ceil(Math.max(0,...chartRows.value.map(item=>Math.max(item.total??0,item.stackTotal)))/4)));
const axisMax=computed(()=>axisStep.value*4);
const axisTicks=computed(()=>[4,3,2,1,0].map(value=>value*axisStep.value));
const chartLegend=computed(()=>{
 const series=new Map<string,ChartSegment>();
 for(const item of chartRows.value)for(const segment of item.segments)if(!series.has(segment.key))series.set(segment.key,segment);
 if(chartRows.value.some(item=>item.unavailable)&&!series.has('unavailable')){
  series.set('unavailable',{key:'unavailable',label:chartView.value==='status'?'状态待查':'套餐待查',value:0,color:'#b5bdcd'});
 }
 if(chartView.value==='status'){
  for(const item of statusSeries.slice(0,5))if(!series.has(item.key))series.set(item.key,{...item,value:0});
  return [...series.values()].sort((left,right)=>{
   const order=[...statusSeries.map(item=>item.key),'other','unavailable'];
   return order.indexOf(left.key)-order.indexOf(right.key);
  });
 }
 return [...series.values()].sort(comparePlanSeries);
});

function chartLabel(item:typeof chartRows.value[number]):string{
 const unit=chartView.value==='status'?'任务总数':'账号总数';
 const details=item.unavailable?[chartView.value==='status'?'状态待查':'套餐待查']:item.segments.map(segment=>`${segment.label} ${display(segment.value)}`);
 return `${item.row.date}，${unit} ${display(item.total)}${details.length?`，${details.join('，')}`:''}，点击查看当日详情`;
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
function count(row:DailyRegistrationRow|DailyRegistrationSummary,key:string):number|null{
 if(row.counts===null||row.counts===undefined)return null;
 return knownNumber((row.counts as Record<string,unknown>)[key])??0;
}
function countLabel(row:DailyRegistrationRow|DailyRegistrationSummary,key:string):string{
 const value=count(row,key);
 return `${statusLabels[key]||key} ${value===null?'—':number(value)}`;
}
function groupedCount(row:DailyRegistrationRow|DailyRegistrationSummary,keys:string[]):number|null{
 if(row.counts===null||row.counts===undefined)return null;
 return keys.reduce((total,key)=>total+(knownNumber((row.counts as Record<string,unknown>)[key])??0),0);
}
function groupedCountLabel(row:DailyRegistrationRow|DailyRegistrationSummary,label:string,keys:string[]):string{
 const value=groupedCount(row,keys);
 return `${label} ${value===null?'—':number(value)}`;
}
function extraStatuses(row:DailyRegistrationRow|DailyRegistrationSummary):Array<{key:string;label:string;value:number}>{
 if(row.counts===null||row.counts===undefined)return [];
 return Object.entries(extraStatusLabels)
  .map(([key,label])=>({key,label,value:knownNumber((row.counts as Record<string,unknown>)[key])??0}))
  .filter(item=>item.value>0);
}
function plans(row:DailyRegistrationRow|DailyRegistrationSummary):Array<{key:string;label:string;count:number}>|null{
 if(row.plans===null||row.plans===undefined)return null;
 return Object.entries(row.plans as Record<string,unknown>)
  .map(([key,value])=>({key,label:planLabels[key]||key,count:number(value)}))
  .sort((left,right)=>right.count-left.count);
}
function planTotal(row:DailyRegistrationRow|DailyRegistrationSummary):number|null{
 const values=plans(row);
 return values?.reduce((total,item)=>total+item.count,0)??null;
}
function planShare(row:DailyRegistrationRow|DailyRegistrationSummary,value:number):string{
 const total=planTotal(row);
 return total&&value>=0?`${Math.round(value/total*100)}%`:'—';
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
    <h2 id="daily-registration-title">每日注册统计</h2>
    <p>北京时间 · 按注册任务创建日期统计 · 套餐以最近成功查询为准 · 账号总数含归档账号</p>
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
  <div v-if="state.loading&&!state.data" class="daily-stats-loading" aria-live="polite">正在读取每日注册统计…</div>
  <template v-else-if="state.data">
   <div v-if="rows.length" class="daily-chart">
    <div class="daily-chart-heading">
     <div class="daily-chart-switch" role="group" aria-label="每日统计图表内容">
      <button type="button" data-daily-view="status" :aria-pressed="chartView==='status'" @click="chartView='status'">任务状态</button>
      <button type="button" data-daily-view="plans" :aria-pressed="chartView==='plans'" @click="chartView='plans'">套餐分布</button>
     </div>
     <p>点选日期查看详情 · 方向键切换日期</p>
    </div>
    <div class="daily-chart-legend" data-daily-legend aria-label="图例">
     <span v-for="item in chartLegend" :key="item.key"><i :class="{'is-unavailable':item.key==='unavailable'}" :style="{backgroundColor:item.color}" aria-hidden="true"></i>{{item.label}}</span>
     <span v-if="!chartLegend.length">{{chartView==='plans'?'暂无套餐账号':'暂无任务'}}</span>
    </div>
    <div class="daily-stats-chart" role="group" :aria-label="chartView==='status'?'每日注册任务状态堆叠柱状图':'每日注册账号套餐堆叠柱状图'">
     <div class="daily-chart-axis" data-daily-axis>
      <span class="daily-axis-unit">{{chartView==='status'?'任务数':'账号数'}}</span>
      <div class="daily-axis-ticks" aria-hidden="true"><span v-for="tick in axisTicks" :key="tick" data-daily-axis-tick>{{display(tick)}}</span></div>
     </div>
     <div class="daily-chart-scroll">
      <div class="daily-chart-plot" :style="{gridTemplateColumns:`repeat(${rows.length},minmax(44px,1fr))`,minWidth:`${rows.length*48}px`}">
       <div class="daily-chart-grid" aria-hidden="true"><i v-for="tick in axisTicks" :key="tick"></i></div>
       <button v-for="(item,index) in chartRows" :key="item.row.date" type="button" class="daily-bar-column" :class="{selected:item.row.date===selectedDate}"
        :data-daily-bar="item.row.date" :aria-label="chartLabel(item)" :title="chartLabel(item)" :aria-pressed="item.row.date===selectedDate" :aria-controls="detailId"
        :tabindex="item.row.date===selectedDate?0:-1" @click="selectDate(item.row.date)" @focus="selectDate(item.row.date)" @keydown="moveDate($event,index)">
        <span class="daily-bar-value" aria-hidden="true">{{display(item.total)}}</span>
        <span class="daily-bar-stack" aria-hidden="true">
         <span v-for="segment in item.segments" :key="segment.key" class="daily-bar-segment" :class="{'is-unavailable':segment.key==='unavailable'}"
          :data-daily-segment="segment.key" :style="{height:`${segment.value/axisMax*100}%`,backgroundColor:segment.color}"></span>
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
      <div><strong>{{row.date}}</strong><span>总数 {{display(row.total)}}</span></div>
      <button type="button" data-daily-bulk :disabled="!canBatch(row)" @click="createBatch(row,`${row.date} 无优惠账号查套餐`)">
       新建查套餐批量（{{unpromotedDisplay(row.unpromoted_count)}}）
      </button>
     </div>
     <div class="daily-row-metrics">
      <span>{{countLabel(row,'success')}}</span>
      <span>{{countLabel(row,'partial_success')}}</span>
      <span>{{countLabel(row,'failed')}}</span>
      <span>{{groupedCountLabel(row,'进行中',['pending','queued','running','waiting','settling','stopping','cancelling'])}}</span>
      <span>{{groupedCountLabel(row,'取消',['cancelled','stopped'])}}</span>
      <span v-for="item in extraStatuses(row)" :key="item.key">{{item.label}} {{item.value}}</span>
      <span>账号总数（含归档） {{display(row.accounts_total)}}</span>
      <span>未归档无优惠 {{unpromotedDisplay(row.unpromoted_count)}}</span>
     </div>
     <div class="daily-row-plans">
      <span class="daily-row-label">套餐分布</span>
      <template v-if="plans(row)">
       <span v-for="plan in plans(row)!" :key="plan.key" :title="`${plan.label} ${display(plan.count)}，占套餐账号 ${planShare(row,plan.count)}`">{{plan.label}} {{display(plan.count)}} · {{planShare(row,plan.count)}}</span>
       <span v-if="!plans(row)!.length">暂无账号</span>
      </template>
      <span v-else>套餐待查</span>
     </div>
    </article>
   </div>
   <p v-else class="daily-stats-empty">所选日期暂无任务。</p>

   <div v-if="state.data.summary" class="daily-stats-summary">
    <div>
     <strong>区间汇总</strong>
     <span>总数 {{display(state.data.summary.total)}} · 账号总数（含归档） {{display(state.data.summary.accounts_total)}} · 未归档无优惠 {{unpromotedDisplay(state.data.summary.unpromoted_count)}}</span>
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
.daily-stats-controls button:focus-visible,.daily-stats-controls input:focus-visible,.daily-stats-row button:focus-visible,.daily-stats-summary button:focus-visible,.daily-stats-error button:focus-visible,.daily-chart-switch button:focus-visible{outline:2px solid #5b5ce2;outline-offset:2px}
.daily-stats-error{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 11px;border:1px solid #efc2c7;border-radius:8px;background:#fff7f8;color:#9f2f39;font-size:12px}
.daily-stats-error button{min-height:30px;padding:0 10px;border:1px solid #b03a44;border-radius:6px;background:#fff;color:#9f2f39;font:inherit;font-size:11.5px;font-weight:650;cursor:pointer}
.daily-stats-error button:disabled{opacity:.5;cursor:default}
.daily-stats-stale{padding:9px 11px;border:1px solid #f0cf9b;border-radius:8px;background:#fff9ed;color:#8a5a12;font-size:12px;line-height:1.5}
.daily-stats-loading,.daily-stats-empty{padding:20px;border:1px dashed #dfe3eb;border-radius:9px;color:#647086;font-size:12px;text-align:center}
.daily-chart,.daily-selected-detail{min-width:0}
.daily-chart{--daily-plot-height:164px;display:flex;flex-direction:column;gap:11px}
.daily-chart-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.daily-chart-heading p{margin:0;color:#647086;font-size:11px;line-height:1.5}
.daily-chart-switch{display:inline-flex;gap:3px;padding:3px;border:1px solid #e6e9f0;border-radius:8px;background:#f6f7fa}
.daily-chart-switch button{min-height:31px;padding:0 13px;border:0;border-radius:5px;background:transparent;color:#647086;font:inherit;font-size:12px;cursor:pointer}
.daily-chart-switch button[aria-pressed=true]{background:#fff;color:#4f51be;font-weight:650;box-shadow:0 1px 3px rgba(16,24,40,.1)}
.daily-chart-legend{display:flex;flex-wrap:wrap;gap:6px 14px;color:#566175;font-size:11px;line-height:1.4}
.daily-chart-legend>span{display:inline-flex;align-items:center;gap:5px}
.daily-chart-legend i{display:inline-block;width:9px;height:9px;flex:none;border-radius:2px}
.daily-stats-chart{display:grid;grid-template-columns:auto minmax(0,1fr);gap:9px;min-width:0}
.daily-chart-axis{display:grid;grid-template-rows:22px var(--daily-plot-height) 28px;min-width:30px;color:#647086;font-size:10px;font-variant-numeric:tabular-nums}
.daily-axis-unit{align-self:start;font-size:10px;white-space:nowrap}
.daily-axis-ticks{display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end;position:relative}
.daily-axis-ticks span{line-height:1;transform:translateY(-50%)}
.daily-axis-ticks span:last-child{transform:translateY(50%)}
.daily-chart-scroll{min-width:0;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin;padding-bottom:3px}
.daily-chart-plot{position:relative;display:grid;gap:0}
.daily-chart-grid{position:absolute;inset:22px 0 28px;display:flex;flex-direction:column;justify-content:space-between;pointer-events:none}
.daily-chart-grid i{height:0;border-top:1px dashed #edf0f5}
.daily-chart-grid i:last-child{border-top:1px solid #dfe3eb}
.daily-bar-column{position:relative;display:grid;grid-template-rows:22px var(--daily-plot-height) 28px;justify-items:center;min-width:0;padding:0 3px;border:0;border-radius:6px;background:transparent;color:#647086;font:inherit;cursor:pointer;transition:background-color .12s ease}
.daily-bar-column:hover{background:#f6f7fb}
.daily-bar-column.selected{background:#eef0ff}
.daily-bar-column:focus-visible{outline:2px solid #5b5ce2;outline-offset:-2px}
.daily-bar-stack{display:flex;flex-direction:column-reverse;align-self:stretch;align-items:stretch;width:28px;max-width:80%}
.daily-bar-segment{display:block;width:100%;flex:none}
.daily-bar-segment:last-child{border-radius:4px 4px 0 0}
.is-unavailable{background-image:repeating-linear-gradient(135deg,transparent,transparent 3px,rgba(255,255,255,.65) 3px,rgba(255,255,255,.65) 5px)}
.daily-bar-column small{align-self:center;font-size:10px;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap}
.daily-bar-column.selected small{color:#4f51be;font-weight:700}
.daily-bar-value{align-self:start;max-width:100%;overflow:hidden;color:#566175;font-size:10px;line-height:1.4;font-variant-numeric:tabular-nums}
.daily-stats-row{display:flex;flex-direction:column;gap:9px;min-width:0;padding:12px;border:1px solid #edf0f5;border-radius:9px;background:#fafbfd}
.daily-row-heading{display:flex;align-items:center;justify-content:space-between;gap:8px}
.daily-row-heading>div{display:flex;align-items:baseline;gap:8px;min-width:0}
.daily-row-heading strong{font-size:13px;font-variant-numeric:tabular-nums}
.daily-row-heading span{color:#647086;font-size:11.5px}
.daily-row-heading button,.daily-stats-summary button{min-height:30px;padding:0 9px;border:1px solid #5b5ce2;border-radius:6px;background:#fff;color:#4f51be;font:inherit;font-size:11px;font-weight:650;cursor:pointer;white-space:nowrap}
.daily-row-heading button:disabled,.daily-stats-summary button:disabled{border-color:#dfe3eb;background:#f5f6f8;color:#9aa3b2;cursor:not-allowed}
.daily-row-metrics,.daily-row-plans{display:flex;flex-wrap:wrap;gap:5px 10px;color:#566175;font-size:11.5px;line-height:1.5}
.daily-row-metrics span,.daily-row-plans>span:not(.daily-row-label){font-variant-numeric:tabular-nums}
.daily-row-label{color:#647086;font-weight:650}
.daily-stats-summary{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding-top:12px;border-top:1px solid #edf0f5}
.daily-stats-summary>div{display:flex;flex-direction:column;gap:3px;min-width:0}
.daily-stats-summary strong{font-size:12.5px}
.daily-stats-summary span{color:#647086;font-size:11.5px;line-height:1.5}
@media(max-width:620px){
 .daily-stats{padding:15px}
 .daily-stats-meta{width:100%}
 .daily-chart{--daily-plot-height:140px}
 .daily-chart-heading p{width:100%;font-size:10.5px}
 .daily-chart-switch button{min-height:36px}
 .daily-stats-controls label{max-width:100%}
 .daily-stats-controls input{min-width:0;max-width:100%}
 .daily-row-heading{align-items:flex-start;flex-direction:column}
 .daily-row-heading button,.daily-stats-summary button{width:100%}
}
@media(prefers-reduced-motion:reduce){.daily-stats *{transition:none!important}}
</style>
