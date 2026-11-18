import {computed,onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue';
import type {DashboardApi} from '../../api/dashboard';
import type {DashboardDeps,DashboardPreferences,DashboardRegion} from './contracts';

export const OVERVIEW_PREFERENCE_KEY='gpt_console_overview_preferences_v1';
export const REGIONS:DashboardRegion[]=['metrics','panels'];
const esc=(value:any)=>String(value??'');
const num=(value:any)=>Number(value||0);
function sourceValue(source:any,key:string){const value=source?.[key];return Number.isInteger(value)&&value>=0?String(value):source?.status==='error'?'读取失败':'未知';}
function supplyHint(supply:any){const updated=supply?.statistics_updated_at;const freshness=updated?`；统计于 ${new Date(updated).toLocaleTimeString()} 更新`:'';return `仅统计本地库存；用完后请手动导入邮箱。邮箱由 Email Butler 等邮箱服务准备${supply?.reason?`；${supply.reason}`:''}${freshness}`;}
function supplyAvailable(supply:any){if(supply?.status==='error')return '读取失败';if(Number.isInteger(supply?.available)&&supply.available>=0)return supply.available;return Array.isArray(supply?.sources)?supply.sources.reduce((total:number,source:any)=>total+num(source?.available),0):0;}
function capability(caps:any,...path:string[]){let value=caps;for(const key of path){if(!value||typeof value!=='object')return null;value=value[key];}return typeof value?.enabled==='boolean'?value.enabled:null;}
function emailSources(data:any,caps:any){const local=data?.email?.supply?.sources;if(Array.isArray(local))return local.filter((source:any)=>source?.kind==='local_pool');const sources=Array.isArray(data?.email?.sources)?data.email.sources:[];return sources.filter((source:any)=>source?.enabled===true&&(capability(caps,'email_sources',source.source)??true));}
function localPools(data:any,caps:any){return emailSources(data,caps).filter((source:any)=>source?.kind==='local_pool');}
function proxyAvailable(data:any,caps:any){const platform=String(data?.proxy?.platform||'none').trim().toLowerCase();if(!platform||platform==='none'||platform==='direct')return false;return capability(caps,'proxy','registration')??true;}
function jobsAvailable(data:any,caps:any){const counts=data?.jobs?.counts||{};const active=num(counts.running)+num(counts.pending)+num(counts.stopping);if(num(data?.jobs?.total)<=0&&active<=0)return false;return capability(caps,'features','register')??true;}
export function proxyLabel(platform:any){const value=String(platform||'').trim();return ({'1024proxy':'1024Proxy','711proxy':'711Proxy',manual:'手动代理池', '1024':'1024Proxy',pool:'静态代理池',none:'直连',direct:'直连'} as Record<string,string>)[value.toLowerCase()]||value||'未配置';}
export function normalizePreferences(raw:any,available:Record<DashboardRegion,string[]>):DashboardPreferences{
 const source=raw&&typeof raw==='object'?raw:{};const known=new Set<string>(REGIONS.flatMap(region=>available[region]||[]));const hidden=Array.isArray(source.hidden)?Array.from(new Set<string>((source.hidden as unknown[]).filter((id):id is string=>typeof id==='string'&&known.has(id)))):[];
 const order={} as Record<DashboardRegion,string[]>;for(const region of REGIONS){const ids=available[region]||[],saved=Array.isArray(source.order?.[region])?(source.order[region] as unknown[]).filter((id):id is string=>typeof id==='string'):[];order[region]=Array.from(new Set<string>([...saved.filter(id=>ids.includes(id)),...ids.filter(id=>!saved.includes(id))]));}
 const sizes:Record<string,string>={},heights:Record<string,number>={};for(const id of known){sizes[id]=['normal','wide','full'].includes(source.sizes?.[id])?source.sizes[id]:'normal';const height=Number(source.heights?.[id]);if(Number.isFinite(height)&&height>=100&&height<=800)heights[id]=Math.round(height);}
 return {order,hidden,sizes,heights};
}
function readPreferences(available:Record<DashboardRegion,string[]>){try{return normalizePreferences(JSON.parse(localStorage.getItem(OVERVIEW_PREFERENCE_KEY)||'{}'),available);}catch{return normalizePreferences({},available);}}
function savePreferences(prefs:DashboardPreferences){try{localStorage.setItem(OVERVIEW_PREFERENCE_KEY,JSON.stringify(prefs));}catch{}}

export const CARD_DEFS=[
 {id:'metric-accounts',region:'metrics' as const,label:'有效账号',available:(d:any)=>num(d?.accounts?.total)>0},
 {id:'metric-email',region:'metrics' as const,label:'本地可用邮箱',available:(d:any,c:any)=>emailSources(d,c).length>0},
 {id:'metric-jobs',region:'metrics' as const,label:'运行任务',available:(d:any,c:any)=>jobsAvailable(d,c)},
 {id:'metric-codex',region:'metrics' as const,label:'Codex 凭证',available:(d:any)=>num(d?.codex?.total)>0},
 {id:'metric-proxy',region:'metrics' as const,label:'活跃出口',available:(d:any,c:any)=>proxyAvailable(d,c)},
 {id:'panel-email',region:'panels' as const,label:'邮箱资源 · 本地库存',available:(d:any,c:any)=>emailSources(d,c).length>0},
 {id:'panel-proxy',region:'panels' as const,label:'网络出口 · 代理与网络',available:(d:any,c:any)=>proxyAvailable(d,c)},
 {id:'panel-jobs',region:'panels' as const,label:'注册流水线 · 今日任务结果',available:(d:any,c:any)=>jobsAvailable(d,c)},
 {id:'panel-accounts',region:'panels' as const,label:'账号资产 · 套餐分布',available:(d:any)=>Object.keys(d?.accounts?.plans||{}).length>0},
 {id:'panel-task-queue',region:'panels' as const,label:'注册流水线 · 当前任务队列',available:(d:any,c:any)=>jobsAvailable(d,c)&&['pending','running','stopping'].some(key=>num(d?.jobs?.counts?.[key])>0)},
 {id:'panel-job-history',region:'panels' as const,label:'注册流水线 · 累计任务结果',available:(d:any,c:any)=>jobsAvailable(d,c)&&['success','partial_success','failed','stopped','cancelled'].some(key=>num(d?.jobs?.counts?.[key])>0)},
 {id:'panel-email-health',region:'panels' as const,label:'邮箱资源 · 邮箱池状态',available:(d:any,c:any)=>localPools(d,c).some((s:any)=>num(s.total)>0)},
 {id:'panel-codex-progress',region:'panels' as const,label:'Codex 授权 · 凭证处理进度',available:(d:any)=>num(d?.codex?.total)>0},
] as const;
function availableIds(data:any,caps:any){return Object.fromEntries(REGIONS.map(region=>[region,CARD_DEFS.filter(card=>card.region===region&&card.available(data,caps)).map(card=>card.id)])) as Record<DashboardRegion,string[]>;}
function density(height:number|undefined){return !height?'normal':height<220?'minimal':height<300?'compact':'normal';}
function more(count:number,unit:string){return count>0?`另有 ${count} ${unit}`:'';}
function cardPayload(id:string,data:any,caps:any,prefs:DashboardPreferences){
 const accounts=data?.accounts||{},email=data?.email||{},jobs=data?.jobs||{},proxy=data?.proxy||{},codex=data?.codex||{};
 if(id==='metric-accounts')return {value:num(accounts.active),hint:`归档 ${num(accounts.archived)}`,color:'#5b5ce2'};
 if(id==='metric-email')return {value:supplyAvailable(email.supply),hint:supplyHint(email.supply),color:'#2dbb8a'};
 if(id==='metric-jobs'){const c=jobs.counts||{};return {value:num(c.running)+num(c.pending)+num(c.stopping),hint:`累计任务 ${num(jobs.total)}`,color:'#e6a23c'};}
 if(id==='metric-codex')return {value:num(codex.total),hint:`待导出 ${num(codex.pending)}`,color:'#377dff'};
 if(id==='metric-proxy')return {value:num(proxy.active_leases),hint:`代理平台 ${proxyLabel(proxy.platform)}`,color:'#a855f7'};
 if(id==='panel-email'){const sources=emailSources(data,caps);return {kind:'email',action:['outlook','管理邮箱'],sources};}
 if(id==='panel-proxy'){const leases=(proxy.leases||[]).slice(0,3),total=Math.max(num(proxy.active_leases),(proxy.leases||[]).length);return {kind:'proxy',action:['config','配置'],platform:proxyLabel(proxy.platform),active:num(proxy.active_leases),leases,more:more(total-1,'个出口')};}
 if(id==='panel-jobs'){const c=jobs.today_counts||{};return {kind:'today',action:['register','查看全部'],today:jobs.today||'今天',rows:[['success','成功',num(c.success)],['partial_success','部分成功',num(c.partial_success)],['failed','失败',num(c.failed)]]};}
 if(id==='panel-accounts'){const plans=Object.entries(accounts.plans||{}).sort((a:any,b:any)=>num(b[1])-num(a[1]));return {kind:'plans',action:['accounts','管理账号'],plans};}
 if(id==='panel-task-queue'){const c=jobs.counts||{};return {kind:'queue',action:['register','查看任务'],rows:[['待处理',num(c.pending)],['运行中',num(c.running)],['停止中',num(c.stopping)]]};}
 if(id==='panel-job-history'){const c=jobs.counts||{};return {kind:'history',action:['register','查看任务'],rows:[['成功',num(c.success)],['失败',num(c.failed)],['部分成功',num(c.partial_success)],['已停止或取消',num(c.stopped)+num(c.cancelled)]]};}
 if(id==='panel-email-health'){const pools=localPools(data,caps),count=(key:string)=>pools.reduce((t:any,s:any)=>t+num(s[key]),0);return {kind:'health',action:['outlook','查看邮箱'],rows:[['可用邮箱',count('available')],['已用邮箱',count('used')],['失败邮箱',count('failed')],['停用邮箱',count('disabled')]]};}
 return {kind:'codex',action:['codex','查看凭证'],rows:[['已导出',num(codex.exported)],['待导出',num(codex.pending)],['账号 Codex 就绪',num(accounts.codex_ready)]]};
}
export function useDashboard(api:DashboardApi,deps:DashboardDeps={}){
 const data=ref<any>(null),caps=ref<any>({}),loading=ref(false),error=ref(''),visible=ref(Boolean(deps.visible)),customizerOpen=ref(false),epoch=ref(0);let timer:number|undefined,controller:AbortController|undefined,inflight:Promise<void>|undefined,disposed=false;
 const prefs=reactive<DashboardPreferences>({order:{metrics:[],panels:[]},hidden:[],sizes:{},heights:{}});
 function syncPrefs(){if(!data.value)return;const normalized=readPreferences(availableIds(data.value,caps.value));prefs.order=normalized.order;prefs.hidden=normalized.hidden;prefs.sizes=normalized.sizes;prefs.heights=normalized.heights;}
 const ids=computed(()=>data.value?availableIds(data.value,caps.value):{metrics:[],panels:[]});
 const cards=computed(()=>REGIONS.flatMap(region=>(prefs.order[region]||[]).filter(id=>!prefs.hidden.includes(id)).map(id=>CARD_DEFS.find(card=>card.id===id)).filter(card=>card&&card.available(data.value,caps.value)).map(card=>({card:card!,payload:cardPayload(card!.id,data.value,caps.value,prefs),size:prefs.sizes[card!.id]||'normal',height:prefs.heights[card!.id],density:density(prefs.heights[card!.id])}))));
 function persist(){savePreferences(normalizePreferences(prefs,ids.value));}
 function mutate(mutator:(p:DashboardPreferences)=>void){mutator(prefs);const normalized=normalizePreferences(prefs,ids.value);prefs.order=normalized.order;prefs.hidden=normalized.hidden;prefs.sizes=normalized.sizes;prefs.heights=normalized.heights;persist();}
 function move(region:DashboardRegion,id:string,direction:'up'|'down'){mutate(p=>{const a=p.order[region]||[],i=a.indexOf(id),j=direction==='up'?i-1:i+1;if(i<0||j<0||j>=a.length)return;[a[i],a[j]]=[a[j],a[i]];});}
 function toggle(id:string,value:boolean){mutate(p=>{p.hidden=p.hidden.filter(item=>item!==id);if(!value)p.hidden.push(id);});}
 function reorder(region:DashboardRegion,source:string,target:string,after=false){if(!ids.value[region].includes(source)||!ids.value[region].includes(target))return;mutate(p=>{const a=p.order[region]||[],from=a.indexOf(source);if(from<0||source===target)return;a.splice(from,1);const to=a.indexOf(target);a.splice(to+(after?1:0),0,source);});}
 function resize(id:string,key:'width'|'height',delta:number){mutate(p=>{if(key==='width'){const options=['normal','wide','full'],i=Math.max(0,Math.min(2,options.indexOf(p.sizes[id]||'normal')+delta));p.sizes[id]=options[i];}else p.heights[id]=Math.max(160,Math.min(800,(p.heights[id]||220)+delta));});}
 function reset(){try{localStorage.removeItem(OVERVIEW_PREFERENCE_KEY);}catch{};if(data.value)syncPrefs();deps.notify?.('已恢复默认布局');}
 function load():Promise<void>{
  if(disposed||!visible.value||document.hidden)return Promise.resolve();if(inflight)return inflight;
  const current=++epoch.value;controller?.abort();controller=new AbortController();loading.value=true;error.value='';
  const pending=(async()=>{try{const [result,capabilityResult]=await Promise.all([api.dashboard(controller!.signal),api.capabilities(controller!.signal).catch(()=>null)]);if(current!==epoch.value||!visible.value||document.hidden)return;data.value=result;if(capabilityResult!==null){caps.value=capabilityResult||{};deps.onCapabilities?.(caps.value);}syncPrefs();deps.onReady?.();}catch(e:any){if(current===epoch.value&&!String(e?.name||'').includes('Abort')){error.value=e?.message||'总览加载失败';deps.notify?.(`总览加载失败：${error.value}`);}}finally{if(current===epoch.value){loading.value=false;inflight=undefined;}}})();
  inflight=pending;return pending;
 }
 function schedule(){if(timer)window.clearInterval(timer);timer=window.setInterval(()=>void load(),15000);}
 function setVisible(value:boolean){if(disposed||visible.value===Boolean(value))return;visible.value=Boolean(value);epoch.value++;controller?.abort();inflight=undefined;if(visible.value){schedule();void load();}else{if(timer)window.clearInterval(timer);timer=undefined;loading.value=false;customizerOpen.value=false;}}
 function setCustomizer(value:boolean){customizerOpen.value=value;}
 const onVisibility=()=>{if(!document.hidden&&visible.value)void load();else{epoch.value++;controller?.abort();inflight=undefined;loading.value=false;customizerOpen.value=false;}};
 onMounted(()=>{document.addEventListener('visibilitychange',onVisibility);if(visible.value){schedule();void load();}});
 onBeforeUnmount(()=>{disposed=true;visible.value=false;epoch.value++;inflight=undefined;loading.value=false;customizerOpen.value=false;document.removeEventListener('visibilitychange',onVisibility);controller?.abort();if(timer)window.clearInterval(timer);timer=undefined;});
 watch(()=>deps.visible,value=>setVisible(Boolean(value)));
 return {data,caps,loading,error,visible,customizerOpen,cards,ids,prefs,mutate,load,setVisible,openCustomizer:()=>setCustomizer(true),closeCustomizer:()=>setCustomizer(false),resetLayout:reset,toggle,move,reorder,resize,cardPayload};
}
