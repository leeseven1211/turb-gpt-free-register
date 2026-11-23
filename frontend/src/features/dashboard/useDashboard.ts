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
    needs_review:num(payload.needs_review),
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
  const loading=ref(false);
  const error=ref('');
  const updatedAt=ref<number|null>(null);
  const visible=ref(Boolean(deps.visible));
  let timer:number|undefined,controller:AbortController|undefined,inflight:Promise<void>|undefined,disposed=false,epoch=0;

  function setVisible(value:boolean){
    if(disposed||visible.value===Boolean(value))return;
    visible.value=Boolean(value);epoch++;controller?.abort();inflight=undefined;
    if(visible.value){schedule();void load();}
    else{if(timer)window.clearInterval(timer);timer=undefined;loading.value=false;}
  }

  function schedule(){
    if(timer)window.clearInterval(timer);
    timer=window.setInterval(()=>void load(),DASHBOARD_POLL_MS);
  }

  function load():Promise<void>{
    if(disposed||!visible.value||document.hidden)return Promise.resolve();
    if(inflight)return inflight;
    const current=++epoch;controller?.abort();controller=new AbortController();loading.value=true;error.value='';
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
    if(!document.hidden&&visible.value)void load();
    else{epoch++;controller?.abort();inflight=undefined;loading.value=false;}
  };

  onMounted(()=>{
    document.addEventListener('visibilitychange',onVisibility);
    if(visible.value){schedule();void load();}
  });
  onBeforeUnmount(()=>{
    disposed=true;visible.value=false;epoch++;inflight=undefined;loading.value=false;
    document.removeEventListener('visibilitychange',onVisibility);
    controller?.abort();
    if(timer)window.clearInterval(timer);
    timer=undefined;
  });
  watch(()=>deps.visible,value=>setVisible(Boolean(value)));

  const hasData=computed(()=>Boolean(data.value));
  return {data,extract,caps,loading,error,updatedAt,visible,hasData,load,setVisible};
}
