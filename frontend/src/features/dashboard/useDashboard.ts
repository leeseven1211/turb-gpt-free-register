import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue';
import type {DashboardApi} from '../../api/dashboard';
import type {DashboardDeps} from './contracts';

export const DASHBOARD_POLL_MS = 20000;

const num=(value:any)=>Number(value||0);

function normalizeExtract(payload:any){
  if(!payload||typeof payload!=='object'||payload.ok!==true)return null;
  return {
    today_extracted:num(payload.today_extracted),
    today_plus_confirmed:num(payload.today_plus_confirmed),
    awaiting_payment:num(payload.awaiting_payment),
    processing:num(payload.processing),
    all:num(payload.all),
    providers:Array.isArray(payload.providers)?payload.providers.filter((item:any)=>item&&typeof item==='object'):[],
  };
}

export function proxyLabel(platform:any){
  const value=String(platform||'').trim();
  return ({'1024proxy':'1024Proxy','711proxy':'711Proxy',manual:'手动代理池','1024':'1024Proxy',pool:'静态代理池',none:'直连',direct:'直连'} as Record<string,string>)[value.toLowerCase()]||value||'未配置';
}

export function useDashboard(api:DashboardApi,deps:DashboardDeps={}){
  const data=ref<any>(null);
  const extract=ref<any>(null);
  const caps=ref<any>({});
  const daily=ref<any>(null);
  const dailyLoading=ref(false);
  const dailyError=ref('');
  const dailyUpdatedAt=ref<string|null>(null);
  const dailyRequestedRange=ref<{from?:string;to?:string}|null>(null);
  const dailyDisplayedRange=ref<{from?:string;to?:string}|null>(null);
  const loading=ref(false);
  const error=ref('');
  const updatedAt=ref<number|null>(null);
  const visible=ref(Boolean(deps.visible));
  const loaded=ref(false);
  let timer:number|undefined,controller:AbortController|undefined,dailyController:AbortController|undefined,inflight:Promise<void>|undefined,dailyInflight:Promise<void>|undefined,dailyInflightKey='',disposed=false,epoch=0,dailyEpoch=0;
  let dailyQuery:{from?:string;to?:string}={};

  function loadDaily(dateFrom?:string,dateTo?:string):Promise<void>{
    if(disposed||!visible.value||document.hidden||!api.registrationDaily)return Promise.resolve();
    const hasExplicitRange=dateFrom!==undefined||dateTo!==undefined;
    const from=hasExplicitRange?(dateFrom||undefined):dailyQuery.from;
    const to=hasExplicitRange?(dateTo||undefined):dailyQuery.to;
    const key=JSON.stringify([from||'',to||'']);
    if(dailyInflight&&dailyInflightKey===key)return dailyInflight;
    dailyQuery={from,to};
    if(hasExplicitRange)dailyRequestedRange.value={from,to};
    const current=++dailyEpoch;
    dailyController?.abort();
    dailyController=new AbortController();
    dailyLoading.value=true;
    dailyError.value='';
    const signal=dailyController.signal;
    const pending=(async()=>{
      try{
        const result=await api.registrationDaily?.(from,to,signal);
        if(current!==dailyEpoch||!visible.value||document.hidden)return;
        if(!result||result.ok===false)throw new Error(result?.message||'每日注册统计读取失败');
        daily.value=result;
        dailyDisplayedRange.value={
          from:typeof result.date_from==='string'?result.date_from:from,
          to:typeof result.date_to==='string'?result.date_to:to,
        };
        dailyUpdatedAt.value=typeof result.updated_at==='string'?result.updated_at:new Date().toISOString();
      }catch(cause:any){
        if(current===dailyEpoch&&!String(cause?.name||'').includes('Abort')){
          dailyError.value=cause?.message||'每日注册统计读取失败';
        }
      }finally{
        if(current===dailyEpoch){dailyLoading.value=false;dailyInflight=undefined;}
      }
    })();
    dailyInflight=pending;
    dailyInflightKey=key;
    return pending;
  }

  function setVisible(value:boolean){
    if(disposed||visible.value===Boolean(value))return;
    visible.value=Boolean(value);epoch++;dailyEpoch++;controller?.abort();dailyController?.abort();inflight=undefined;dailyInflight=undefined;
    if(visible.value){schedule();void load(true);}
    else{if(timer)window.clearInterval(timer);timer=undefined;loading.value=false;dailyLoading.value=false;dailyInflightKey='';}
  }

  function schedule(){
    if(timer)window.clearInterval(timer);
    timer=window.setInterval(()=>void load(true),DASHBOARD_POLL_MS);
  }

  function load(silent=false):Promise<void>{
    if(disposed||!visible.value||document.hidden)return Promise.resolve();
    const quiet=silent&&loaded.value;
    if(inflight){
      if(!quiet)loading.value=true;
      return inflight;
    }
    void loadDaily(dailyQuery.from,dailyQuery.to);
    const current=++epoch;controller?.abort();controller=new AbortController();if(!quiet)loading.value=true;if(!silent)error.value='';
    const signal=controller.signal;
    const pending=(async()=>{
      try{
        const [dashResult,capabilityResult,extractResult]=await Promise.allSettled([
          api.dashboard(signal),
          api.capabilities(signal),
          api.extractSummary?api.extractSummary(signal):Promise.resolve(null),
        ]);
        if(current!==epoch||!visible.value||document.hidden)return;
        if(dashResult.status==='rejected')throw dashResult.reason;
        data.value=dashResult.value;
        extract.value=extractResult.status==='fulfilled'?normalizeExtract(extractResult.value):null;
        if(capabilityResult.status==='fulfilled'&&capabilityResult.value!=null){
          caps.value=capabilityResult.value||{};
          deps.onCapabilities?.(caps.value);
        }
        loaded.value=true;
        error.value='';
        updatedAt.value=Date.now();
        deps.onReady?.();
      }catch(e:any){
        if(current===epoch&&!String(e?.name||'').includes('Abort')){
          error.value=e?.message||'总览加载失败';
          deps.notify?.(`总览加载失败：${error.value}`);
        }
      }finally{
        if(current===epoch){loading.value=false;inflight=undefined;}
      }
    })();
    inflight=pending;return pending;
  }

  const onVisibility=()=>{
    if(!document.hidden&&visible.value)void load(true);
    else{epoch++;dailyEpoch++;controller?.abort();dailyController?.abort();inflight=undefined;dailyInflight=undefined;dailyInflightKey='';loading.value=false;dailyLoading.value=false;}
  };

  onMounted(()=>{
    document.addEventListener('visibilitychange',onVisibility);
    if(visible.value){schedule();void load();}
  });
  onBeforeUnmount(()=>{
    disposed=true;visible.value=false;epoch++;dailyEpoch++;inflight=undefined;dailyInflight=undefined;dailyInflightKey='';loading.value=false;dailyLoading.value=false;
    document.removeEventListener('visibilitychange',onVisibility);
    controller?.abort();
    dailyController?.abort();
    if(timer)window.clearInterval(timer);
    timer=undefined;
  });
  watch(()=>deps.visible,value=>setVisible(Boolean(value)));

  const hasData=computed(()=>Boolean(data.value));
  const dailyScopeCurrent=computed(()=>{
    if(!daily.value||!dailyRequestedRange.value)return true;
    return dailyRequestedRange.value.from===dailyDisplayedRange.value?.from
      &&dailyRequestedRange.value.to===dailyDisplayedRange.value?.to;
  });
  return {data,extract,caps,daily,dailyLoading,dailyError,dailyUpdatedAt,dailyRequestedRange,dailyDisplayedRange,dailyScopeCurrent,loading,error,updatedAt,visible,hasData,load,loadDaily,setVisible};
}
