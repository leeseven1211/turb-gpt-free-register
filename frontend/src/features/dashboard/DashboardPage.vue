<script setup lang="ts">
import {computed,onMounted,ref} from 'vue';
import {proxyLabel,useDashboard} from './useDashboard';
import type {DashboardDeps} from './contracts';

const props=defineProps<{api:any;deps:DashboardDeps}>();
const owner=useDashboard(props.api,props.deps);
const {data,extract,caps,loading,error,updatedAt}=owner;
const mounted=ref(false);
onMounted(()=>{mounted.value=true;});

const fmt=(value:any)=>new Intl.NumberFormat('zh-CN').format(Number(value||0));
const num=(value:any)=>Number(value||0);
const pct=(part:any,total:any)=>{const all=num(total);return all>0?Math.max(0,Math.min(100,Math.round(num(part)/all*100))):0;};
const planLabel=(plan:string)=>({free:'Free',free_trial_eligible:'Free · 试用资格',free_half_price_eligible:'Free · 半价资格',free_discount_eligible:'Free · 折扣资格',free_promo_unknown:'Free · 优惠待查',plus:'Plus',pro:'Pro',team:'Team',go:'Go',unknown:'未检测'} as Record<string,string>)[plan]||plan;

const accounts=computed<any>(()=>data.value?.accounts||{});
const email=computed<any>(()=>data.value?.email?.supply||{});
const emailSourcesAll=computed<any[]>(()=>{
 const sources=Array.isArray(email.value?.sources)?email.value.sources:Array.isArray(data.value?.email?.sources)?data.value.email.sources:[];
 return sources.filter((source:any)=>source?.kind==='local_pool');
});
const emailSources=computed<any[]>(()=>emailSourcesAll.value.filter((source:any)=>num(source.total)>0||num(source.available)>0));
const emailIdle=computed(()=>Math.max(0,emailSourcesAll.value.length-emailSources.value.length));
const emailAvailable=computed(()=>email.value?.status==='error'?'读取失败':num(email.value?.available));
const emailNumber=computed(()=>email.value?.status==='error'?'—':fmt(emailAvailable.value));
const emailTotal=computed(()=>num(email.value?.total));
const emailUsed=computed(()=>num(email.value?.used));
const emailBroken=computed(()=>num(email.value?.failed)+num(email.value?.disabled));
const emailTone=computed(()=>{
  if(email.value?.status==='error')return 'danger';
  if(emailTotal.value>0&&num(email.value?.available)===0)return 'warn';
  if(num(email.value?.available)>0)return 'ok';
  return 'idle';
});
const emailChip=computed(()=>email.value?.status==='error'?'读取失败':emailTotal.value===0?'未配置':num(email.value?.available)===0?'库存耗尽':'库存正常');

const codex=computed<any>(()=>data.value?.codex||{});
const codexTone=computed(()=>num(codex.value.pending)>0?'warn':num(codex.value.total)>0?'ok':'idle');

const plans=computed(()=>Object.entries(accounts.value?.plans||{}).map(([key,value])=>({key,label:planLabel(key),count:num(value)})).sort((a,b)=>b.count-a.count));
const planMax=computed(()=>Math.max(1,...plans.value.map(plan=>plan.count)));
const planTotal=computed(()=>plans.value.reduce((total,plan)=>total+plan.count,0));

const jobs=computed<any>(()=>data.value?.jobs||{});
const registrationDisabled=computed(()=>caps.value?.features?.register?.enabled===false);
const jobCounts=computed<any>(()=>({...jobs.value?.counts||{}}));
const todayCounts=computed<any>(()=>({...jobs.value?.today_counts||{}}));
const activeJobs=computed(()=>num(jobCounts.value.pending)+num(jobCounts.value.running)+num(jobCounts.value.stopping));
const todayTotal=computed(()=>num(todayCounts.value.success)+num(todayCounts.value.partial_success)+num(todayCounts.value.failed));
const cumulative=computed(()=>[
  {key:'success',label:'成功',value:num(jobCounts.value.success),color:'#1f9d75'},
  {key:'partial_success',label:'部分成功',value:num(jobCounts.value.partial_success),color:'#d99a2b'},
  {key:'failed',label:'失败',value:num(jobCounts.value.failed),color:'#d9534f'},
  {key:'cancelled',label:'停止/取消',value:num(jobCounts.value.stopped)+num(jobCounts.value.cancelled),color:'#98a2b3'},
].filter(item=>item.value>0));
const jobTone=computed(()=>activeJobs.value>0?'active':num(todayCounts.value.failed)>0?'warn':'idle');

const proxy=computed<any>(()=>data.value?.proxy||{});
const leases=computed<any[]>(()=>Array.isArray(proxy.value.leases)?proxy.value.leases.slice(0,3):[]);
const remainingLeases=computed(()=>Math.max(0,num(proxy.value.active_leases)-leases.value.length));
const registrationProxyDisabled=computed(()=>caps.value?.proxy?.registration?.enabled===false);
const proxyTone=computed(()=>num(proxy.value.active_leases)>0?'ok':'idle');

const extractData=computed<any>(()=>extract.value||{});
const extractTone=computed(()=>num(extractData.value.processing)>0?'active':'idle');
const extractEmpty=computed(()=>num(extractData.value.all)===0&&num(extractData.value.today_extracted)===0&&num(extractData.value.processing)===0&&num(extractData.value.awaiting_payment)===0);

const pulse=computed(()=>[
  {id:'email',label:'邮箱',value:emailNumber.value,badge:email.value?.status==='error'?'读取失败':num(email.value?.available)===0?'库存耗尽':`${emailNumber.value} 可用`,hint:num(email.value?.available)===0?'库存耗尽':`邮箱总量 ${fmt(emailTotal.value)}`,tone:emailTone.value,tab:'outlook'},
  {id:'accounts',label:'账号',value:fmt(accounts.value.active),badge:`${fmt(accounts.value.active)} 活跃`,hint:`归档 ${fmt(accounts.value.archived)}`,tone:'ok',tab:'accounts'},
  {id:'codex',label:'Codex',value:fmt(codex.value.total),badge:num(codex.value.pending)>0?`待导 ${fmt(codex.value.pending)}`:`${fmt(codex.value.total)} 凭证`,hint:`待导出 ${fmt(codex.value.pending)}`,tone:codexTone.value,tab:'codex'},
  {id:'plans',label:'套餐',value:fmt(plans.value.length),badge:`${fmt(plans.value.length)} 类`,hint:`${fmt(planTotal.value)} 个已归类`,tone:'ok',tab:'accounts'},
  {id:'extract',label:'提炼',value:fmt(extractData.value.today_extracted),badge:num(extractData.value.processing)>0?`进行 ${fmt(extractData.value.processing)}`:`今日 ${fmt(extractData.value.today_extracted)}`,hint:'今日已提炼',tone:extractTone.value,tab:'extract-workbench'},
  {id:'proxy',label:'代理',value:fmt(proxy.value.active_leases),badge:num(proxy.value.active_leases)>0?`${fmt(proxy.value.active_leases)} 出口`:proxyLabel(proxy.value.platform),hint:proxyLabel(proxy.value.platform),tone:proxyTone.value,tab:'proxy-traffic'},
  {id:'jobs',label:'任务',value:fmt(activeJobs.value),badge:activeJobs.value>0?`运行 ${fmt(activeJobs.value)}`:num(todayCounts.value.failed)>0?`异常 ${fmt(todayCounts.value.failed)}`:'空闲',hint:`累计 ${fmt(jobs.value.total)}`,tone:jobTone.value,tab:'tasks'},
]);

const alerts=computed(()=>{
  const list:Array<{tone:string;text:string;tab:string;label:string}>=[];
  if(email.value?.status==='error')list.push({tone:'danger',text:'邮箱池统计读取失败，暂时无法判断可用库存。',tab:'outlook',label:'检查邮箱池'});
  else if(emailTotal.value>0&&num(email.value?.available)===0)list.push({tone:'warning',text:`邮箱池已用完（已用 ${fmt(emailUsed.value)} / 邮箱总量 ${fmt(emailTotal.value)}），新的注册任务取不到邮箱。`,tab:'outlook',label:'添加邮箱库存'});
  return list.slice(0,2);
});

const updatedLabel=computed(()=>{
  if(!updatedAt.value)return loading.value?'正在读取…':'尚未读取';
  return `数据更新 ${new Date(updatedAt.value).toLocaleTimeString('zh-CN',{hour12:false})}`;
});
const go=(tab:string)=>props.deps.onNavigate?.(tab);

defineExpose({
  load:owner.load,
  setVisible:owner.setVisible,
  // 旧版入口保留为空操作，避免已缓存的页面脚本调用时报错。
  openCustomizer:()=>{},
  closeCustomizer:()=>{},
  resetLayout:()=>{},
});
</script>

<template>
 <div class="ov-page" :class="{'is-mounted':mounted}">
  <div class="ov-section-head">
   <div class="ov-section-title">
    <h2>服务脉搏</h2>
    <p>邮箱 · 账号 · Codex · 套餐 · 提炼 · 代理 · 任务</p>
   </div>
   <div class="ov-section-actions">
    <span class="ov-updated"><i aria-hidden="true"></i>{{updatedLabel}}</span>
    <button type="button" class="ov-refresh" :disabled="loading" @click="owner.load">
     <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 6.7"/><path d="M20 4v7h-7"/></svg>
     {{loading?'刷新中':'刷新'}}
    </button>
   </div>
  </div>

  <div v-if="error" class="ov-error" role="alert">
   <div><strong>总览加载失败</strong><span>{{error}}</span></div>
   <button type="button" @click="owner.load">重试</button>
  </div>

  <section v-if="alerts.length" class="ov-alerts" aria-label="需要关注">
   <article v-for="item in alerts" :key="item.text" class="ov-alert" :class="`is-${item.tone}`">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
    <p>{{item.text}}</p>
    <button type="button" @click="go(item.tab)">{{item.label}}</button>
   </article>
  </section>

  <section v-if="!data && loading" class="ov-skeleton" aria-label="正在读取总览">
   <div class="ov-skeleton-pulse"></div>
   <div class="ov-skeleton-grid"><i></i><i></i><i></i><i></i></div>
  </section>

  <template v-if="data">
   <nav class="ov-pulse" aria-label="服务脉搏">
    <button v-for="item in pulse" :key="item.id" type="button" class="ov-pulse-item" :class="[`is-${item.tone}`,{'is-zero':item.value==='0'}]" :title="`${item.label} · ${item.hint}`" @click="go(item.tab)">
     <span class="ov-pulse-top"><i aria-hidden="true"></i>{{item.label}}</span>
     <span class="ov-pulse-badge"><strong>{{item.badge}}</strong></span>
    </button>
   </nav>

   <div class="ov-grid">
    <article class="ov-card ov-card--email" data-overview-card="email" style="--accent:#1f9d75;--accent-soft:#e7f6f0">
     <header class="ov-card-head">
      <div class="ov-card-title">
       <span class="ov-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg></span>
       <div><h3>邮箱池</h3><p>本地库存与来源</p></div>
      </div>
      <button type="button" class="ov-link" data-overview-action="email" @click="go('outlook')">管理<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
     </header>
     <div class="ov-figure">
      <strong :class="{'is-danger':emailTone==='warn'}">{{emailNumber}}</strong><span>可用</span>
      <em v-if="emailTone!=='ok'" class="ov-chip" :class="`is-${emailTone}`">{{emailChip}}</em>
     </div>
     <div class="ov-mini-grid ov-mini-grid--3">
      <div><span>邮箱总量</span><strong>{{fmt(emailTotal)}}</strong></div>
      <div><span>已使用</span><strong>{{fmt(emailUsed)}}</strong></div>
      <div><span>停用 / 失败</span><strong>{{fmt(emailBroken)}}</strong></div>
     </div>
     <ul v-if="emailSources.length" class="ov-bars">
      <li v-for="source in emailSources" :key="source.source">
       <div class="ov-bar-label"><span>{{source.label}}</span><small>{{num(source.available)===0?'已用尽':`可用 ${fmt(source.available)}`}} / {{fmt(source.total)}}</small></div>
       <div class="ov-bar" :class="{'is-spent':num(source.available)===0&&num(source.total)>0}"><i :style="{width:pct(source.available,source.total)+'%'}"></i></div>
      </li>
     </ul>
     <p v-else class="ov-empty">还没有可统计的邮箱库存。</p>
     <p v-if="emailIdle" class="ov-foot">另有 {{emailIdle}} 个来源暂无库存 · 仅统计本地库存</p>
     <p v-else class="ov-foot">仅统计本地库存，用完后需手动导入</p>
    </article>

    <article class="ov-card ov-card--accounts" data-overview-card="accounts" style="--accent:#5b5ce2;--accent-soft:#eeeefe">
     <header class="ov-card-head">
      <div class="ov-card-title">
       <span class="ov-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/></svg></span>
       <div><h3>账号</h3><p>账号资产</p></div>
      </div>
      <button type="button" class="ov-link" data-overview-action="accounts" @click="go('accounts')">管理<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
     </header>
     <div class="ov-figure">
      <strong>{{fmt(accounts.active)}}</strong><span>活跃账号</span>
     </div>
     <div class="ov-split" aria-hidden="true"><i class="is-active" :style="{width:pct(accounts.active,accounts.total)+'%'}"></i><i class="is-idle" :style="{width:pct(accounts.archived,accounts.total)+'%'}"></i></div>
     <div class="ov-legend"><span><i style="background:#5b5ce2"></i>活跃 {{fmt(accounts.active)}}</span><span><i style="background:#d7dbe5"></i>归档 {{fmt(accounts.archived)}}</span></div>
     <div class="ov-mini-grid ov-mini-grid--2">
      <div><span>账号总数</span><strong>{{fmt(accounts.total)}}</strong></div>
      <div><span>Codex 就绪</span><strong>{{fmt(accounts.codex_ready)}}</strong></div>
     </div>
     <div class="ov-meter"><span>Codex 就绪率</span><div class="ov-bar"><i :style="{width:pct(accounts.codex_ready,accounts.active)+'%'}"></i></div><strong>{{pct(accounts.codex_ready,accounts.active)}}%</strong></div>
    </article>

    <article class="ov-card ov-card--codex" data-overview-card="codex" style="--accent:#377dff;--accent-soft:#e9f1ff">
     <header class="ov-card-head">
      <div class="ov-card-title">
       <span class="ov-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="11" width="18" height="10" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></span>
       <div><h3>Codex</h3><p>授权凭证</p></div>
      </div>
      <button type="button" class="ov-link" data-overview-action="codex" @click="go('codex')">查看<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
     </header>
     <div class="ov-figure">
      <strong>{{fmt(codex.total)}}</strong><span>已导出凭证</span>
      <em v-if="codexTone==='warn'" class="ov-chip is-warn">待导出</em>
     </div>
     <div class="ov-bar-label"><span>导出进度</span><small>{{fmt(codex.exported)}} / {{fmt(codex.total)}}</small></div>
     <div class="ov-bar ov-bar--thick"><i :style="{width:pct(codex.exported,codex.total)+'%'}"></i></div>
     <div class="ov-mini-grid ov-mini-grid--3">
      <div><span>已导出</span><strong>{{fmt(codex.exported)}}</strong></div>
      <div><span>待导出</span><strong>{{fmt(codex.pending)}}</strong></div>
      <div><span>账号就绪</span><strong>{{fmt(accounts.codex_ready)}}</strong></div>
     </div>
     <p class="ov-foot">账号 Codex 就绪 {{fmt(accounts.codex_ready)}} · 覆盖 {{pct(accounts.codex_ready,accounts.active)}}% 活跃账号</p>
    </article>

    <article class="ov-card ov-card--extract" data-overview-card="extract" style="--accent:#d97706;--accent-soft:#fdf3e3">
     <header class="ov-card-head">
      <div class="ov-card-title">
       <span class="ov-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z"/><path d="M19 15.5 20 18l2.5 1-2.5 1L19 22l-1-2-2.5-1 2.5-1 1-2.5Z"/></svg></span>
       <div><h3>提炼</h3><p>提链工作台</p></div>
      </div>
      <button type="button" class="ov-link" data-overview-action="extract" @click="go('extract-workbench')">工作台<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
     </header>
     <div class="ov-figure">
      <strong>{{fmt(extractData.today_extracted)}}</strong><span>今日已提炼</span>
      <em class="ov-chip" :class="`is-${extractTone}`">{{extractTone==='idle'?'空闲':'处理中'}}</em>
     </div>
     <div v-if="!extractEmpty" class="ov-mini-grid ov-mini-grid--3">
      <div><span>Plus 已确认</span><strong>{{fmt(extractData.today_plus_confirmed)}}</strong></div>
      <div><span>处理中</span><strong>{{fmt(extractData.processing)}}</strong></div>
      <div><span>待支付</span><strong>{{fmt(extractData.awaiting_payment)}}</strong></div>
     </div>
     <p v-if="extractEmpty" class="ov-empty">今日还没有提炼任务，进入工作台即可发起。</p>
     <p class="ov-foot">{{extractEmpty?'提链工作台空闲':`累计 ${fmt(extractData.all)} 个提炼任务`}}</p>
    </article>

    <article class="ov-card ov-card--plans" data-overview-card="plans" style="--accent:#8b5cf6;--accent-soft:#f3edff">
     <header class="ov-card-head">
      <div class="ov-card-title">
       <span class="ov-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 2 7l10 5 10-5-10-5Z"/><path d="m2 12 10 5 10-5"/><path d="m2 17 10 5 10-5"/></svg></span>
       <div><h3>套餐</h3><p>账号套餐分布</p></div>
      </div>
      <button type="button" class="ov-link" data-overview-action="plans" @click="go('accounts')">账号<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
     </header>
     <template v-if="plans.length">
      <div class="ov-figure ov-figure--small"><strong>{{fmt(plans.length)}}</strong><span>种套餐 · {{fmt(planTotal)}} 个账号</span></div>
      <ul class="ov-bars">
       <li v-for="plan in plans" :key="plan.key">
        <div class="ov-bar-label"><span>{{plan.label}}</span><small>{{fmt(plan.count)}} · {{pct(plan.count,planTotal)}}%</small></div>
        <div class="ov-bar"><i :style="{width:Math.max(4,Math.round(plan.count/planMax*100))+'%'}"></i></div>
       </li>
      </ul>
     </template>
     <p v-else class="ov-empty">还没有可用的套餐数据。</p>
    </article>

    <article class="ov-card ov-card--proxy" data-overview-card="proxy" style="--accent:#0e9aa7;--accent-soft:#e6f6f7">
     <header class="ov-card-head">
      <div class="ov-card-title">
       <span class="ov-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3Z"/></svg></span>
       <div><h3>代理</h3><p>网络出口</p></div>
      </div>
      <button type="button" class="ov-link" data-overview-action="proxy" @click="go('proxy-traffic')">查看<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
     </header>
     <div class="ov-figure">
      <strong>{{fmt(proxy.active_leases)}}</strong><span>活跃出口</span>
      <em class="ov-chip">{{proxyLabel(proxy.platform)}}</em>
     </div>
     <ul v-if="leases.length" class="ov-lease-list">
      <li v-for="(lease,index) in leases" :key="index"><i aria-hidden="true"></i><span>{{lease.endpoint||lease.exit_ip||'活跃出口'}}</span><small>{{lease.region||lease.provider||''}}</small></li>
     </ul>
     <p v-else class="ov-empty">{{registrationProxyDisabled?'注册代理未启用，当前没有活跃租约。':`当前没有活跃的代理租约，新任务会走 ${proxyLabel(proxy.platform)}。`}}</p>
     <p v-if="leases.length" class="ov-foot">{{registrationProxyDisabled?'注册代理未启用，已有租约仍保留':`代理平台 ${proxyLabel(proxy.platform)}`}}<template v-if="remainingLeases"> · 另有 {{remainingLeases}} 个活跃出口</template></p>
    </article>

    <article class="ov-card ov-card--jobs" data-overview-card="jobs" style="--accent:#475569;--accent-soft:#eef1f5">
     <header class="ov-card-head">
      <div class="ov-card-title">
       <span class="ov-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5h11"/><path d="M9 12h11"/><path d="M9 19h11"/><circle cx="4" cy="5" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="19" r="1"/></svg></span>
       <div><h3>任务</h3><p>注册流水线与队列</p></div>
      </div>
      <button type="button" class="ov-link" data-overview-action="jobs" @click="go('tasks')">任务中心<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
     </header>
     <div class="ov-task-columns">
      <section class="ov-task-block">
       <h4>当前队列</h4>
       <div class="ov-mini-grid ov-mini-grid--3">
        <div><span>运行中</span><strong>{{fmt(jobCounts.running)}}</strong></div>
        <div><span>待处理</span><strong>{{fmt(jobCounts.pending)}}</strong></div>
        <div><span>停止中</span><strong>{{fmt(jobCounts.stopping)}}</strong></div>
       </div>
      </section>
      <section class="ov-task-block">
       <h4>今日结果 <small>{{jobs.today}}</small></h4>
       <div class="ov-mini-grid ov-mini-grid--3">
        <div><span>成功</span><strong class="is-ok">{{fmt(todayCounts.success)}}</strong></div>
        <div><span>部分成功</span><strong class="is-warn">{{fmt(todayCounts.partial_success)}}</strong></div>
        <div><span>失败</span><strong class="is-danger">{{fmt(todayCounts.failed)}}</strong></div>
       </div>
      </section>
      <section class="ov-task-block ov-task-block--wide">
       <h4>累计结果 <small>{{fmt(jobs.total)}} 个任务</small></h4>
       <div v-if="cumulative.length" class="ov-stack" aria-hidden="true">
        <i v-for="item in cumulative" :key="item.key" :style="{width:(item.value/Math.max(1,jobs.total)*100)+'%',background:item.color}"></i>
       </div>
       <div v-else class="ov-stack ov-stack--empty" aria-hidden="true"></div>
       <div class="ov-stack-legend">
        <span v-for="item in cumulative" :key="item.key"><i :style="{background:item.color}"></i>{{item.label}} {{fmt(item.value)}}</span>
        <span v-if="!cumulative.length" class="ov-stack-empty-text">暂无累计结果</span>
       </div>
      </section>
     </div>
     <p v-if="registrationDisabled" class="ov-foot">注册功能未启用，历史任务仍可查看。</p>
    </article>
   </div>
  </template>
 </div>
</template>

<style scoped>
.ov-page{--ov-text:#172033;--ov-muted:#566175;--ov-line:#e6e9f0;--ov-soft:#f6f8fb;display:flex;flex-direction:column;gap:13px;min-width:0;font-family:var(--ui-font-sans,system-ui);color:var(--ov-text);opacity:0;transform:translateY(6px);transition:opacity .3s ease,transform .3s ease}
.ov-page.is-mounted{opacity:1;transform:none}
.ov-page *{box-sizing:border-box}
.ov-section-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;flex:none}
.ov-section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:10px 16px;flex-wrap:wrap;padding:2px 2px 0}
.ov-section-title{display:flex;align-items:baseline;gap:11px;flex-wrap:wrap;min-width:0}
.ov-section-head h2{margin:0;font-size:18px;line-height:1.3;letter-spacing:-.015em;font-weight:700}
.ov-section-head p{margin:0;color:#647086;font-size:12px;line-height:1.4}
.ov-updated{display:inline-flex;align-items:center;gap:7px;color:#647086;font-size:12px;font-variant-numeric:tabular-nums}
.ov-updated i{width:6px;height:6px;border-radius:50%;background:#1f9d75;box-shadow:0 0 0 4px rgba(31,157,117,.12)}
.ov-refresh{display:inline-flex;align-items:center;gap:7px;min-height:36px;padding:0 14px;border:1px solid var(--ov-line);border-radius:9px;background:#fff;color:#3d4659;font:inherit;font-size:12.5px;font-weight:650;cursor:pointer;box-shadow:0 1px 1px rgba(16,24,40,.03)}
.ov-refresh svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.ov-refresh:hover:not(:disabled){border-color:#c9cffa;color:#4f51be;background:#f7f7ff}
.ov-refresh:disabled{opacity:.6;cursor:default}
.ov-refresh:focus-visible,.ov-pulse-item:focus-visible,.ov-link:focus-visible,.ov-alert button:focus-visible,.ov-error button:focus-visible{outline:2px solid #5b5ce2;outline-offset:2px}

.ov-error{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 16px;border:1px solid #f3cdd1;border-radius:12px;background:#fff7f8;color:#a5323c;font-size:12.5px}
.ov-error div{display:flex;flex-direction:column;gap:2px;min-width:0}
.ov-error span{color:#8b4a52}
.ov-error button{min-height:32px;padding:0 12px;border:1px solid #eab6bc;border-radius:8px;background:#fff;color:#a5323c;font:inherit;font-size:12px;font-weight:650;cursor:pointer}

.ov-alerts{display:grid;gap:10px}
.ov-alert{display:flex;align-items:center;gap:11px;min-height:44px;padding:9px 12px;border:1px solid #efc07d;border-radius:11px;background:#fff8e9;color:#7a4a09;font-size:12.5px;line-height:1.5;box-shadow:inset 3px 0 #d9822b}
.ov-alert.is-danger{border-color:#eeb1b8;background:#fff6f7;color:#9f2f39;box-shadow:inset 3px 0 #d94a55}
.ov-alert svg{width:16px;height:16px;flex:none;fill:none;stroke:#c2710b;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.ov-alert p{flex:1;min-width:0;margin:0}
.ov-alert button{flex:none;min-height:32px;padding:0 12px;border:1px solid #b45309;border-radius:7px;background:#b45309;color:#fff;font:inherit;font-size:12px;font-weight:700;cursor:pointer}
.ov-alert button:hover{background:#96450a}
.ov-alert.is-danger button{border-color:#b03a44;background:#b03a44}
.ov-alert.is-danger button:hover{background:#97313a}
.ov-alert.is-danger svg{stroke:#b03a44}

.ov-skeleton{display:flex;flex-direction:column;gap:16px}
.ov-skeleton-pulse,.ov-skeleton-grid i{display:block;border-radius:14px;background:linear-gradient(90deg,#f1f4f9 25%,#e8ecf3 37%,#f1f4f9 63%);background-size:400% 100%;animation:ov-shimmer 1.4s ease infinite}
.ov-skeleton-pulse{height:42px;border-radius:999px}
.ov-skeleton-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.ov-skeleton-grid i{height:220px}

.ov-pulse{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px}
.ov-pulse-item{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:0;height:40px;padding:0 11px;border:1px solid var(--ov-line);border-radius:999px;background:#fff;color:inherit;font:inherit;text-align:left;cursor:pointer;box-shadow:0 1px 2px rgba(16,24,40,.03);transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease,background .16s ease}
.ov-pulse-item:hover{transform:translateY(-1px);border-color:#cfd5e3;background:#fbfcfe;box-shadow:0 4px 12px rgba(16,24,40,.06)}
.ov-pulse-item.is-ok:hover{border-color:#b8e3d4;background:#f8fdfb}
.ov-pulse-item.is-warn:hover{border-color:#f0cfa0;background:#fffcf6}
.ov-pulse-item.is-danger:hover{border-color:#f2bec3;background:#fff9fa}
.ov-pulse-item.is-active:hover{border-color:#c9cffa;background:#f9f9ff}
.ov-pulse-top{display:inline-flex;align-items:center;gap:6px;flex:none;color:#3d4659;font-size:12.5px;font-weight:650;white-space:nowrap}
.ov-pulse-top i{width:7px;height:7px;flex:none;border-radius:50%;background:#98a2b3;box-shadow:0 0 0 3px rgba(152,162,179,.14)}
.ov-pulse-item.is-ok .ov-pulse-top i{background:#1f9d75;box-shadow:0 0 0 3px rgba(31,157,117,.14)}
.ov-pulse-item.is-warn .ov-pulse-top i{background:#d9822b;box-shadow:0 0 0 3px rgba(217,130,43,.16);animation:ov-breathe 2.4s ease-in-out infinite}
.ov-pulse-item.is-danger .ov-pulse-top i{background:#d94a55;box-shadow:0 0 0 3px rgba(217,74,85,.18);animation:ov-breathe 1.8s ease-in-out infinite}
.ov-pulse-item.is-active .ov-pulse-top i{background:#5b5ce2;box-shadow:0 0 0 3px rgba(91,92,226,.18);animation:ov-breathe 2s ease-in-out infinite}
.ov-pulse-badge{display:inline-flex;align-items:center;min-width:0;height:22px;padding:0 8px;border-radius:999px;background:#f2f4f8;color:#566175;font-size:11.5px;line-height:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ov-pulse-badge strong{font-size:11.5px;font-weight:680;font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ov-pulse-item.is-ok .ov-pulse-badge{background:#eefaf5;color:#17805f}
.ov-pulse-item.is-warn .ov-pulse-badge{background:#fff6e5;color:#b46a12}
.ov-pulse-item.is-danger .ov-pulse-badge{background:#fff0f1;color:#c0392b}
.ov-pulse-item.is-active .ov-pulse-badge{background:#eef0ff;color:#4f51be}
.ov-pulse-item.is-zero:not(.is-warn):not(.is-danger) .ov-pulse-badge{background:#f4f6f9;color:#7d8596}
.ov-pulse-item.is-zero:not(.is-warn):not(.is-danger) .ov-pulse-badge strong{font-weight:600}

.ov-grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px;align-items:stretch}
.ov-card{position:relative;display:flex;flex-direction:column;gap:13px;min-width:0;padding:18px;border:1px solid var(--ov-line);border-radius:14px;background:#fff;box-shadow:0 1px 2px rgba(16,24,40,.03),0 6px 18px rgba(16,24,40,.035);overflow:hidden;transition:border-color .18s ease,box-shadow .18s ease}
.ov-card:hover{border-color:#d7dce7;box-shadow:0 2px 6px rgba(16,24,40,.04),0 10px 24px rgba(16,24,40,.055)}
.ov-card--email,.ov-card--accounts,.ov-card--codex,.ov-card--extract,.ov-card--plans,.ov-card--proxy{grid-column:span 4}
.ov-card--jobs{grid-column:span 12}
.ov-card-head{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:38px;padding-bottom:10px;border-bottom:1px solid #f1f3f8}
.ov-card-title{display:flex;align-items:center;gap:11px;min-width:0}
.ov-icon{display:grid;place-items:center;width:36px;height:36px;flex:none;border-radius:10px;background:var(--accent-soft);color:var(--accent)}
.ov-icon svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.ov-card-title h3{margin:0;font-size:15px;line-height:1.3;font-weight:700;letter-spacing:-.01em}
.ov-card-title p{margin:2px 0 0;color:#647086;font-size:12px;line-height:1.4}
.ov-link{display:inline-flex;align-items:center;gap:2px;flex:none;min-height:28px;padding:0 4px 0 9px;border:0;border-radius:7px;background:transparent;color:#768196;font:inherit;font-size:12px;font-weight:650;cursor:pointer;transition:background .15s ease,color .15s ease}
.ov-link svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.ov-link:hover{color:var(--accent);background:var(--accent-soft)}

.ov-figure{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap;min-width:0}
.ov-figure strong{font-size:34px;line-height:1;letter-spacing:-.035em;font-weight:730;font-variant-numeric:tabular-nums}
.ov-figure strong.is-danger{color:#c0392b}
.ov-figure>span{color:#667085;font-size:12.5px;font-weight:600}
.ov-figure--small strong{font-size:26px}
.ov-chip{display:inline-flex;align-items:center;min-height:23px;padding:1px 9px;border-radius:999px;background:#f1f3f8;color:#6b7488;font-size:11px;font-style:normal;font-weight:700;white-space:nowrap}
.ov-chip.is-ok{background:#e7f6f0;color:#17805f}
.ov-chip.is-warn{background:#fdf1de;color:#a9660f}
.ov-chip.is-danger{background:#fdeced;color:#b03a44}
.ov-chip.is-active{background:#eef0ff;color:#4f51be}
.ov-chip.is-idle{background:#f1f3f8;color:#6b7488}

.ov-mini-grid{display:grid;gap:12px;border-radius:10px;background:var(--ov-soft);padding:12px 14px}
.ov-mini-grid--2{grid-template-columns:repeat(2,minmax(0,1fr))}
.ov-mini-grid--3{grid-template-columns:repeat(3,minmax(0,1fr))}
.ov-mini-grid--4{grid-template-columns:repeat(4,minmax(0,1fr))}
.ov-mini-grid>div{display:flex;flex-direction:column;gap:3px;min-width:0}
.ov-mini-grid span{color:#647086;font-size:12px;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ov-mini-grid strong{font-size:15px;line-height:1.2;font-weight:700;font-variant-numeric:tabular-nums}
.ov-mini-grid strong.is-ok{color:#17805f}
.ov-mini-grid strong.is-warn{color:#b46a12}
.ov-mini-grid strong.is-danger{color:#c0392b}

.ov-bars{display:flex;flex-direction:column;gap:9px;margin:0;padding:0;list-style:none;min-width:0}
.ov-bars li{display:flex;flex-direction:column;gap:5px;min-width:0}
.ov-bar-label{display:flex;align-items:baseline;justify-content:space-between;gap:10px;min-width:0}
.ov-bar-label span{min-width:0;color:#3d4659;font-size:12.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ov-bar-label small{flex:none;color:#647086;font-size:11px;font-variant-numeric:tabular-nums}
.ov-bar{height:6px;border-radius:3px;background:#eef1f6;overflow:hidden}
.ov-bar i{display:block;height:100%;border-radius:3px;background:var(--accent);transition:width .4s cubic-bezier(.2,.75,.2,1)}
.ov-bar.is-spent i{width:100%!important;background:#dd9a3d;opacity:.8}
.ov-bar--thick{height:8px;border-radius:4px}

.ov-meter{display:flex;align-items:center;gap:9px;min-width:0;color:#7c86a2;font-size:11px}
.ov-meter>span{flex:none}
.ov-meter .ov-bar{flex:1;min-width:0}
.ov-meter>strong{flex:none;color:#3d4659;font-size:11.5px;font-weight:700;font-variant-numeric:tabular-nums}
.ov-split{display:flex;height:8px;border-radius:4px;background:#eef1f6;overflow:hidden}
.ov-split i{display:block;height:100%}
.ov-split .is-active{background:#5b5ce2}
.ov-split .is-idle{background:#d7dbe5}
.ov-legend{display:flex;gap:14px;flex-wrap:wrap;color:#647086;font-size:11px;margin-top:-6px}
.ov-legend span{display:inline-flex;align-items:center;gap:5px}
.ov-legend i{width:7px;height:7px;border-radius:2px}

.ov-lease-list{display:flex;flex-direction:column;gap:7px;margin:0;padding:0;list-style:none}
.ov-lease-list li{display:flex;align-items:center;gap:8px;min-height:26px;padding:5px 9px;border-radius:8px;background:var(--ov-soft);font-size:12px;color:#3d4659;min-width:0}
.ov-lease-list li i{width:6px;height:6px;flex:none;border-radius:50%;background:#0e9aa7}
.ov-lease-list li span{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}
.ov-lease-list li small{flex:none;color:#647086;font-size:11px}

.ov-empty{flex:1;display:flex;align-items:center;justify-content:center;min-height:76px;margin:0;padding:14px 16px;border:1px dashed #dde2ec;border-radius:10px;background:#fafbfd;color:#647086;font-size:12px;line-height:1.55;text-align:center}
.ov-foot{margin:auto 0 0;padding-top:4px;color:#6b778e;font-size:11.5px;line-height:1.5}
.ov-task-columns{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1.25fr);gap:14px;align-items:stretch}
.ov-task-block{display:flex;flex-direction:column;justify-content:space-between;gap:10px;min-width:0;padding:13px 15px;border:1px solid #eef1f6;border-radius:11px;background:#fafbfd}
.ov-task-block h4{margin:0;color:#566175;font-size:12px;font-weight:700;letter-spacing:.01em}
.ov-task-block h4 small{margin-left:6px;color:#7c86a2;font-size:11px;font-weight:600}
.ov-task-block .ov-mini-grid{background:transparent;padding:0}
.ov-stack{display:flex;height:10px;border-radius:5px;background:#eef1f6;overflow:hidden}
.ov-stack--empty{background:repeating-linear-gradient(-45deg,#eef1f6,#eef1f6 6px,#f6f8fb 6px,#f6f8fb 12px)}
.ov-stack i{display:block;height:100%}
.ov-stack i+i{box-shadow:inset 1px 0 rgba(255,255,255,.65)}
.ov-stack-legend{display:flex;flex-wrap:wrap;gap:6px 16px;color:#566175;font-size:11.5px}
.ov-stack-legend span{display:inline-flex;align-items:center;gap:6px;font-variant-numeric:tabular-nums}
.ov-stack-legend i{width:7px;height:7px;border-radius:2px}
.ov-stack-empty-text{color:#7c86a2}

@keyframes ov-shimmer{0%{background-position:100% 0}100%{background-position:0 0}}
@keyframes ov-breathe{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.72;transform:scale(.9)}}
@media (prefers-reduced-motion:reduce){.ov-page{opacity:1;transform:none;transition:none}.ov-pulse-item,.ov-card{transition:none}.ov-pulse-top i{animation:none!important}.ov-bar i{transition:none}.ov-skeleton-pulse,.ov-skeleton-grid i{animation:none}}
@media (max-width:1180px){
 .ov-pulse{display:flex;overflow-x:auto;scrollbar-width:none;gap:8px;padding-bottom:2px}
 .ov-pulse::-webkit-scrollbar{display:none}
 .ov-pulse-item{flex:0 0 auto;min-width:136px}
 .ov-card--email,.ov-card--accounts,.ov-card--codex,.ov-card--extract,.ov-card--plans,.ov-card--proxy{grid-column:span 6}
 .ov-task-columns{grid-template-columns:repeat(2,minmax(0,1fr))}
 .ov-task-block--wide{grid-column:1/-1}
}
@media (max-width:900px){
 .ov-grid{grid-template-columns:repeat(6,minmax(0,1fr))}
 .ov-card--jobs{grid-column:span 6}
}
@media (max-width:620px){
 .ov-grid{grid-template-columns:minmax(0,1fr)}
 .ov-card--email,.ov-card--accounts,.ov-card--codex,.ov-card--extract,.ov-card--plans,.ov-card--proxy,.ov-card--jobs{grid-column:1/-1}
 .ov-card{padding:16px}
 .ov-figure strong{font-size:30px}
 .ov-task-columns{grid-template-columns:minmax(0,1fr)}
 .ov-mini-grid--4{grid-template-columns:repeat(2,minmax(0,1fr))}
}
</style>
