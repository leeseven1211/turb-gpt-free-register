<script setup lang="ts">
import {computed,ref,useId,watch} from 'vue';
import type {DailyPromotionOffer,DailyRegistrationRow,DailyRegistrationStatsState,DailyRegistrationSummary} from './contracts';
import type {AccountQuerySpec} from '../accounts/queryAdapter';

const props=defineProps<{
 state:DailyRegistrationStatsState;
 onBulkPlanCreate?:(value:{name:string;query:AccountQuerySpec})=>void;
}>();
type RangeMode='3'|'7'|'30'|'custom';
type DailyGroup=DailyRegistrationRow|DailyRegistrationSummary;
const mode=ref<RangeMode>('3');
const customFrom=ref('');
const customTo=ref('');
const selectedDate=ref('');
const detailId=`daily-registration-detail-${useId()}`;
const rows=computed(()=>Array.isArray(props.state.data?.rows)?props.state.data!.rows!:[]);
const dataRange=computed(()=>({
 from:props.state.data?.date_from||rows.value[0]?.date||'',
 to:props.state.data?.date_to||rows.value[rows.value.length-1]?.date||'',
}));
const rangeLabel=computed(()=>dataRange.value.from&&dataRange.value.to?`${dataRange.value.from} 至 ${dataRange.value.to}`:'日期范围待返回');
const cohortLabel=computed(()=>props.state.data?.cohort_basis_label||'按账号首次入库日期统计');
const updatedLabel=computed(()=>props.state.updatedAt
 ? `更新于 ${new Date(props.state.updatedAt).toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})}`
 : props.state.loading?'正在读取…':'尚未读取');
const errorLabel=computed(()=>props.state.error&&props.state.data&&props.state.scopeCurrent?`${props.state.error}，当前成功范围仍可使用。`:props.state.error);
const selectedRow=computed(()=>rows.value.find(row=>row.date===selectedDate.value));
const quantityRows=computed(()=>rows.value.map(row=>({row,total:knownNumber(row.accounts_total)})));
const axisStep=computed(()=>Math.max(1,Math.ceil(Math.max(0,...quantityRows.value.map(item=>item.total??0))/4)));
const axisMax=computed(()=>axisStep.value*4);
const axisTicks=computed(()=>[4,3,2,1,0].map(value=>value*axisStep.value));
const presenceKinds=[
 {key:'eligible',label:'有优惠',color:'#5b5ce2'},
 {key:'none',label:'无优惠',color:'#a2aabc'},
 {key:'unknown',label:'待确认',color:'#dbaf52'},
] as const;
const planOrder=['team','plus','go'];
function compareOffers(left:DailyPromotionOffer,right:DailyPromotionOffer):number{
 const rank=(plan:string)=>{const index=planOrder.indexOf(plan);return index<0?planOrder.length:index;};
 return rank(left.plan)-rank(right.plan)||left.label.localeCompare(right.label,'zh-CN')||left.key.localeCompare(right.key);
}
const offerSeries=computed(()=>{
 const offers=new Map<string,DailyPromotionOffer>();
 for(const row of rows.value)for(const offer of rowOffers(row)??[])if(!offers.has(offer.key))offers.set(offer.key,offer);
 return [...offers.values()].sort(compareOffers);
});
const anyOffersPending=computed(()=>rows.value.some(row=>rowOffers(row)===null));
const matrixStyle=computed(()=>({'--daily-date-count':rows.value.length,minWidth:`${180+rows.value.length*138}px`}));

function number(value:unknown):number{const parsed=Number(value);return Number.isFinite(parsed)?parsed:0;}
function knownNumber(value:unknown):number|null{
 if(value===null||value===undefined)return null;
 const parsed=Number(value);return Number.isFinite(parsed)?parsed:null;
}
function display(value:unknown):string{
 const parsed=knownNumber(value);return parsed===null?'—':new Intl.NumberFormat('zh-CN').format(parsed);
}
function share(row:DailyGroup,value:number):string{
 const total=knownNumber(row.accounts_total);
 if(!total||total<0||value<0)return '—';
 const percentage=value/total*100;
 if(percentage>0&&percentage<0.01)return '<0.01%';
 return `${new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2}).format(percentage)}%`;
}
function shareWidth(row:DailyGroup,value:number):number{
 const total=knownNumber(row.accounts_total);return total&&total>0?Math.max(0,Math.min(100,value/total*100)):0;
}
function presence(row:DailyGroup){
 const values=row.promotion_presence as DailyRegistrationRow['promotion_presence'];
 const total=knownNumber(row.accounts_total);
 if(!values||total===null||total<0)return null;
 const counts=presenceKinds.map(kind=>knownNumber(values[kind.key]));
 if(counts.some(value=>value===null||value<0)||counts.reduce<number>((sum,value)=>sum+(value??0),0)!==total)return null;
 return presenceKinds.map((kind,index)=>({...kind,count:counts[index]!}));
}
function rowOffers(row:DailyGroup):DailyPromotionOffer[]|null{
 if(!Array.isArray(row.offers))return null;
 return row.offers.map(offer=>({...offer,count:Math.max(0,number(offer.count)),stale_count:Math.max(0,number(offer.stale_count))})).sort(compareOffers);
}
function offerAt(row:DailyGroup,key:string):DailyPromotionOffer|null{
 const offers=rowOffers(row);if(offers===null)return null;
 return offers.find(offer=>offer.key===key)||{key,plan:'',label:'',count:0,stale_count:0};
}
function quantityLabel(row:DailyRegistrationRow):string{return `${row.date}，账号总数 ${display(row.accounts_total)}，点击选择日期`;}
function selectDate(date:string){selectedDate.value=date;}
function moveDate(event:KeyboardEvent,index:number){
 let next=index;
 if(event.key==='ArrowRight')next=Math.min(rows.value.length-1,index+1);
 else if(event.key==='ArrowLeft')next=Math.max(0,index-1);
 else if(event.key==='Home')next=0;
 else if(event.key==='End')next=rows.value.length-1;
 else return;
 event.preventDefault();const row=rows.value[next];if(!row)return;
 selectDate(row.date);
 const buttons=(event.currentTarget as HTMLElement).parentElement?.querySelectorAll<HTMLButtonElement>('[data-daily-bar]');
 buttons?.[next]?.focus({preventScroll:true});buttons?.[next]?.scrollIntoView?.({block:'nearest',inline:'nearest'});
}
function batchCount(row:DailyGroup):number|null{return knownNumber(row.unpromoted_count);}
function unpromotedDisplay(value:unknown):string{return knownNumber(value)===null?'待查':display(value);}
function canBatch(row:DailyGroup):boolean{return props.state.scopeCurrent&&batchCount(row)!==null&&batchCount(row)!>0&&!!row.query;}
function createBatch(row:DailyGroup,name:string){if(canBatch(row)&&row.query)props.onBulkPlanCreate?.({name,query:row.query as AccountQuerySpec});}
function dayFrom(value:string,offset:number):string{
 const date=new Date(`${value}T00:00:00Z`);date.setUTCDate(date.getUTCDate()+offset);return date.toISOString().slice(0,10);
}
function beijingToday():string{
 const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
 const values=Object.fromEntries(parts.filter(part=>part.type!=='literal').map(part=>[part.type,part.value]));return `${values.year}-${values.month}-${values.day}`;
}
function choosePreset(value:Exclude<RangeMode,'custom'>){mode.value=value;const end=beijingToday();void props.state.load(dayFrom(end,-(Number(value)-1)),end);}
function chooseCustom(){mode.value='custom';customFrom.value=props.state.displayedRange?.from||dataRange.value.from;customTo.value=props.state.displayedRange?.to||dataRange.value.to;}
function applyCustom(){if(mode.value==='custom'&&customFrom.value&&customTo.value&&customFrom.value<=customTo.value)void props.state.load(customFrom.value,customTo.value);}
watch(rows,value=>{if(!value.some(row=>row.date===selectedDate.value))selectedDate.value=value[0]?.date||'';},{immediate:true});
</script>

<template>
 <section class="daily-stats" aria-labelledby="daily-registration-title">
  <header class="daily-stats-head">
   <div><h2 id="daily-registration-title">每日账号注册与优惠</h2><p>北京时间 · {{cohortLabel}} · 包含归档账号</p></div>
   <div class="daily-stats-meta"><span data-daily-range>{{rangeLabel}}</span><span>{{updatedLabel}}</span></div>
  </header>
  <div class="daily-stats-controls" role="group" aria-label="统计日期范围">
   <button v-for="days in ['3','7','30'] as const" :key="days" type="button" :data-daily-range-3="days==='3'?'':undefined" :data-daily-range-7="days==='7'?'':undefined" :data-daily-range-30="days==='30'?'':undefined" :class="{active:mode===days}" :aria-pressed="mode===days" @click="choosePreset(days)">近 {{days}} 天</button>
   <button type="button" data-daily-range-custom :class="{active:mode==='custom'}" :aria-pressed="mode==='custom'" @click="chooseCustom">自定义</button>
   <template v-if="mode==='custom'"><label>开始日期<input v-model="customFrom" aria-label="开始日期" type="date" @change="applyCustom"></label><label>结束日期<input v-model="customTo" aria-label="结束日期" type="date" @change="applyCustom"></label></template>
  </div>
  <div v-if="state.error" class="daily-stats-error" data-daily-error role="alert"><span>{{errorLabel}}</span><button type="button" data-daily-retry :disabled="state.loading" @click="state.load()">重试</button></div>
  <div v-if="state.data&&!state.scopeCurrent" class="daily-stats-stale" data-daily-stale role="status">{{state.loading?'正在读取新日期范围，当前仍显示上一成功范围；完成前不能新建查套餐批量。':'新日期范围读取失败，当前仍显示上一成功范围；请重试后再新建查套餐批量。'}}</div>
  <div v-if="state.loading&&!state.data" class="daily-stats-loading" aria-live="polite">正在读取每日账号与优惠统计…</div>
  <template v-else-if="state.data">
   <template v-if="rows.length">
    <section class="daily-section" aria-labelledby="daily-total-title">
     <div class="daily-section-heading"><h3 id="daily-total-title">每日账号总数</h3><p>每个账号只归属首次入库的一天</p></div>
     <div class="daily-quantity-chart" role="group" aria-label="每日账号总数柱形图">
      <div class="daily-chart-axis" data-daily-axis><span>账号数</span><div aria-hidden="true"><span v-for="tick in axisTicks" :key="tick" data-daily-axis-tick>{{display(tick)}}</span></div></div>
      <div class="daily-chart-scroll">
       <div class="daily-quantity-plot" :style="{gridTemplateColumns:`repeat(${rows.length},minmax(76px,1fr))`,minWidth:`${rows.length*80}px`}">
        <div class="daily-chart-grid" aria-hidden="true"><i v-for="tick in axisTicks" :key="tick"></i></div>
        <button v-for="(item,index) in quantityRows" :key="item.row.date" type="button" class="daily-bar-column" :class="{selected:item.row.date===selectedDate}" :data-daily-bar="item.row.date" :aria-label="quantityLabel(item.row)" :aria-pressed="item.row.date===selectedDate" :aria-controls="detailId" :tabindex="item.row.date===selectedDate?0:-1" @click="selectDate(item.row.date)" @focus="selectDate(item.row.date)" @keydown="moveDate($event,index)">
         <strong data-daily-account-total>{{display(item.total)}}</strong><span class="daily-quantity-track" aria-hidden="true"><i data-daily-quantity :style="{height:`${(item.total??0)/axisMax*100}%`}"></i></span><span class="daily-date-label">{{item.row.date.slice(5)}}</span>
        </button>
       </div>
      </div>
     </div>
    </section>

    <section class="daily-section" aria-labelledby="daily-presence-title">
     <div class="daily-section-heading"><h3 id="daily-presence-title">每日有无优惠占比</h3><p>按账号去重；未查询或结果不完整的账号列为待确认</p></div>
     <div class="daily-presence-list">
      <article v-for="row in rows" :key="row.date" class="daily-presence-row" :data-daily-presence="row.date">
       <div class="daily-presence-date"><strong>{{row.date}}</strong><span>{{display(row.accounts_total)}} 个账号</span></div>
       <template v-if="presence(row)">
        <template v-if="row.accounts_total!>0">
         <div class="daily-presence-track" role="img" :aria-label="presence(row)!.map(item=>`${item.label} ${display(item.count)}个，${share(row,item.count)}`).join('，')"><i v-for="item in presence(row)!.filter(item=>item.count>0)" :key="item.key" :data-presence-segment="item.key" :style="{width:`${shareWidth(row,item.count)}%`,backgroundColor:item.color}"></i></div>
         <div class="daily-presence-values"><span v-for="item in presence(row)!" :key="item.key"><i :style="{backgroundColor:item.color}" aria-hidden="true"></i>{{item.label}} {{display(item.count)}} 个 · <strong>{{share(row,item.count)}}</strong></span></div>
        </template>
        <p v-else class="daily-data-pending">暂无账号 · 占比 —</p>
       </template>
       <p v-else class="daily-data-pending">有无优惠数据待查</p>
      </article>
     </div>
    </section>

    <section class="daily-section" aria-labelledby="daily-offers-title">
     <div class="daily-section-heading"><h3 id="daily-offers-title">每日优惠种类占比</h3><p>每项占比均以当天账号总数为分母；同一账号可有多种优惠，各项不相加</p></div>
     <div v-if="offerSeries.length" class="daily-offer-scroll" role="region" aria-label="各日期优惠种类账号数与占比" tabindex="0">
      <table class="daily-offer-table" :style="matrixStyle">
       <thead><tr><th scope="col">优惠种类</th><th v-for="row in rows" :key="row.date" scope="col">{{row.date}}<small>{{display(row.accounts_total)}} 个账号</small></th></tr></thead>
       <tbody><tr v-for="offer in offerSeries" :key="offer.key" :data-daily-offer-row="offer.key"><th scope="row">{{offer.label}}</th><td v-for="row in rows" :key="row.date" :data-daily-offer-cell="`${offer.key}:${row.date}`">
        <template v-if="offerAt(row,offer.key)"><div class="daily-offer-numbers"><strong>{{share(row,offerAt(row,offer.key)!.count)}}</strong><span>{{display(offerAt(row,offer.key)!.count)}} 个</span></div><div class="daily-offer-track" aria-hidden="true"><i data-daily-offer-fill :style="{width:`${shareWidth(row,offerAt(row,offer.key)!.count)}%`}"></i></div><small v-if="offerAt(row,offer.key)!.stale_count>0" class="daily-offer-stale">{{display(offerAt(row,offer.key)!.stale_count)}} 个待复查</small></template>
        <span v-else class="daily-data-pending">待查</span>
       </td></tr></tbody>
      </table>
     </div>
     <p v-else class="daily-data-pending">{{anyOffersPending?'优惠种类数据待查':'所选日期暂无已确认优惠记录。'}}</p>
     <p class="daily-snapshot-note">优惠采用最近查询结果，并非注册当日的历史优惠；历史优惠待复查后才计入已确认优惠。</p>
    </section>

    <div v-if="selectedRow" :id="detailId" class="daily-selected-action" aria-live="polite" aria-atomic="true" :data-daily-row="selectedRow.date">
     <div><strong>{{selectedRow.date}}</strong><span>Plus 无优惠账号查套餐 · 未归档 {{unpromotedDisplay(selectedRow.unpromoted_count)}} 个</span></div><button type="button" data-daily-bulk :disabled="!canBatch(selectedRow)" @click="createBatch(selectedRow,`${selectedRow.date} 无优惠账号查套餐`)">新建查套餐批量（{{unpromotedDisplay(selectedRow.unpromoted_count)}}）</button>
    </div>
   </template>
   <p v-else class="daily-stats-empty">所选日期暂无账号统计。</p>
   <div v-if="state.data.summary" class="daily-stats-summary"><div><strong>区间汇总</strong><span>账号总数 {{display(state.data.summary.accounts_total)}} · 包含归档账号</span></div><button type="button" data-daily-summary-bulk :disabled="!canBatch(state.data.summary)" @click="createBatch(state.data.summary,`${dataRange.from}..${dataRange.to} 无优惠账号查套餐`)">新建区间查套餐批量（{{unpromotedDisplay(state.data.summary.unpromoted_count)}}）</button></div>
  </template>
 </section>
</template>

<style scoped>
.daily-stats{--daily-purple:#5b5ce2;--daily-muted:#647086;--daily-plot-height:150px;--daily-header-height:28px;display:flex;flex-direction:column;gap:16px;min-width:0;padding:18px;border:1px solid #e6e9f0;border-radius:14px;background:#fff;box-shadow:0 1px 2px #10182808;color:#172033}
.daily-stats-head,.daily-stats-meta,.daily-stats-controls,.daily-section-heading,.daily-stats-error,.daily-selected-action,.daily-stats-summary{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;min-width:0}
.daily-stats-head h2{margin:0;font-size:17px;line-height:1.4;font-weight:700}.daily-stats-head p,.daily-section-heading p,.daily-snapshot-note{margin:4px 0 0;color:var(--daily-muted);font-size:12px;line-height:1.6}.daily-stats-meta{justify-content:flex-start;color:var(--daily-muted);font-size:11.5px;font-variant-numeric:tabular-nums}.daily-stats-controls{justify-content:flex-start;gap:7px}
.daily-stats-controls button,.daily-stats-controls input{min-height:34px;border:1px solid #dfe3eb;border-radius:7px;background:#fff;color:#475569;font:inherit;font-size:12px}.daily-stats-controls button{padding:0 11px;cursor:pointer}.daily-stats-controls button.active{border-color:var(--daily-purple);background:#eef0ff;color:#4f51be;font-weight:650}.daily-stats-controls label{display:flex;align-items:center;gap:6px;color:var(--daily-muted);font-size:12px}.daily-stats-controls input{padding:0 8px;max-width:100%;min-width:0}
.daily-stats button:focus-visible,.daily-stats input:focus-visible,.daily-offer-scroll:focus-visible{outline:2px solid var(--daily-purple);outline-offset:2px}.daily-stats-error{padding:9px 11px;border:1px solid #efc2c7;border-radius:8px;background:#fff7f8;color:#9f2f39;font-size:12px}.daily-stats-error button{min-height:30px;padding:0 10px;border:1px solid #b03a44;border-radius:6px;background:#fff;color:#9f2f39;font:inherit;cursor:pointer}.daily-stats-stale{padding:9px 11px;border:1px solid #f0cf9b;border-radius:8px;background:#fff9ed;color:#8a5a12;font-size:12px;line-height:1.5}.daily-stats-loading,.daily-stats-empty{padding:20px;color:var(--daily-muted);font-size:12px;text-align:center}
.daily-section{display:flex;flex-direction:column;gap:12px;min-width:0;padding-top:16px;border-top:1px solid #edf0f5}.daily-section-heading{align-items:baseline;justify-content:flex-start;gap:4px 16px}.daily-section-heading h3{margin:0;font-size:13px;line-height:1.5;font-weight:650}.daily-section-heading p{margin:0}.daily-data-pending{margin:0;color:var(--daily-muted);font-size:12px;line-height:1.6}
.daily-quantity-chart{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;min-width:0}.daily-chart-axis{display:grid;grid-template-rows:var(--daily-header-height) var(--daily-plot-height) 28px;min-width:30px;color:var(--daily-muted);font-size:11px;font-variant-numeric:tabular-nums}.daily-chart-axis>div{display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end}.daily-chart-axis>div span{line-height:1;transform:translateY(-50%)}.daily-chart-axis>div span:last-child{transform:translateY(50%)}.daily-chart-scroll,.daily-offer-scroll{min-width:0;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin;padding-bottom:3px}.daily-quantity-plot{position:relative;display:grid}.daily-chart-grid{position:absolute;inset:var(--daily-header-height) 0 28px;display:flex;flex-direction:column;justify-content:space-between;pointer-events:none}.daily-chart-grid i{height:0;border-top:1px dashed #edf0f5}.daily-chart-grid i:last-child{border-top:1px solid #dfe3eb}.daily-bar-column{position:relative;display:grid;grid-template-rows:var(--daily-header-height) var(--daily-plot-height) 28px;justify-items:center;min-width:0;padding:0 5px;border:0;border-radius:6px;background:transparent;color:var(--daily-muted);font:inherit;cursor:pointer}.daily-bar-column:hover{background:#f8f9fd}.daily-bar-column.selected{background:#f1f2ff}.daily-bar-column>strong{font-size:13px;font-weight:650;font-variant-numeric:tabular-nums}.daily-quantity-track{display:flex;align-items:flex-end;justify-content:center;width:100%;height:100%}.daily-quantity-track i{display:block;width:36px;max-width:65%;border-radius:4px 4px 0 0;background:var(--daily-purple)}.daily-date-label{align-self:center;font-size:11px;font-variant-numeric:tabular-nums}
.daily-presence-list{display:flex;flex-direction:column;gap:14px}.daily-presence-row{display:grid;grid-template-columns:120px minmax(0,1fr);gap:7px 16px;align-items:center;min-width:0}.daily-presence-date{grid-row:1/3;display:flex;flex-direction:column;gap:3px;font-size:12px;font-variant-numeric:tabular-nums}.daily-presence-date strong{font-weight:600}.daily-presence-date>span{color:var(--daily-muted)}.daily-presence-track{display:flex;height:17px;overflow:hidden;border-radius:4px;background:#f1f3f7;min-width:0}.daily-presence-track i{display:block;flex:none;height:100%}.daily-presence-values{display:flex;flex-wrap:wrap;gap:5px 18px;font-size:12px;line-height:1.5;color:#475569;font-variant-numeric:tabular-nums}.daily-presence-values>span{display:inline-flex;align-items:center;gap:4px}.daily-presence-values i{width:8px;height:8px;border-radius:2px;flex:none;margin-right:2px}.daily-presence-values strong{font-weight:600;color:#172033}
.daily-offer-table{width:100%;table-layout:fixed;border-collapse:collapse;text-align:left;font-size:12px;line-height:1.5}.daily-offer-table th,.daily-offer-table td{padding:10px 13px;border-bottom:1px solid #edf0f5;vertical-align:top}.daily-offer-table th:first-child{width:180px;padding-left:0;position:sticky;left:0;background:#fff;z-index:1}.daily-offer-table thead th{font-weight:600;color:#475569;padding-top:0}.daily-offer-table thead small{display:block;margin-top:2px;color:var(--daily-muted);font-weight:400}.daily-offer-table tbody th{font-weight:500;overflow-wrap:anywhere}.daily-offer-numbers{display:flex;align-items:baseline;justify-content:space-between;gap:6px;font-variant-numeric:tabular-nums}.daily-offer-numbers strong{font-size:13px;font-weight:600}.daily-offer-numbers span{color:var(--daily-muted);white-space:nowrap}.daily-offer-track{height:6px;margin-top:7px;border-radius:2px;background:#eef0f5;overflow:hidden}.daily-offer-track i{display:block;height:100%;background:var(--daily-purple);border-radius:2px}.daily-offer-stale{display:block;margin-top:5px;color:#8a5a12;font-size:11px}.daily-snapshot-note{margin:0;font-size:11.5px}
.daily-selected-action{padding:11px 12px;background:#f8f9fc;border-radius:8px}.daily-selected-action>div,.daily-stats-summary>div{display:flex;align-items:baseline;gap:7px 12px;flex-wrap:wrap;min-width:0}.daily-selected-action strong,.daily-stats-summary strong{font-size:12px;font-variant-numeric:tabular-nums}.daily-selected-action span,.daily-stats-summary span{font-size:12px;color:var(--daily-muted);line-height:1.6}.daily-selected-action button,.daily-stats-summary button{min-height:32px;padding:0 10px;border:1px solid var(--daily-purple);border-radius:6px;background:#fff;color:#4f51be;font:inherit;font-size:12px;font-weight:600;cursor:pointer}.daily-stats-summary{padding-top:12px;border-top:1px solid #edf0f5}.daily-stats button:disabled{border-color:#dfe3eb;background:#f5f6f8;color:#9aa3b2;cursor:not-allowed}
@media(max-width:620px){.daily-stats{padding:15px;gap:14px;--daily-plot-height:125px}.daily-stats-meta{width:100%;font-size:11px}.daily-section-heading{align-items:flex-start;flex-direction:column;gap:3px}.daily-presence-row{grid-template-columns:minmax(0,1fr);gap:6px}.daily-presence-date{grid-row:auto;flex-direction:row;justify-content:space-between}.daily-presence-values{gap:4px 12px}.daily-selected-action{align-items:stretch;flex-direction:column}.daily-selected-action button,.daily-stats-summary button{width:100%}.daily-stats-controls label{max-width:100%}.daily-offer-table th:first-child{width:140px}.daily-offer-table th,.daily-offer-table td{padding-left:10px;padding-right:10px}.daily-offer-table th:first-child{padding-left:0}.daily-section{padding-top:14px}}
@media(pointer:coarse){.daily-stats-controls button,.daily-stats-controls input,.daily-selected-action button,.daily-stats-summary button{min-height:44px}.daily-stats-controls input{font-size:16px}}
@media(prefers-reduced-motion:reduce){.daily-stats *{transition:none!important}}
</style>
