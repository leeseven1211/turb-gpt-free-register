import {computed,onScopeDispose,ref,shallowRef,watch} from 'vue';
import type {AccountActionContext} from './useAccounts';

export interface AccountInspectionDependencies {
  request(path:string,options?:RequestInit):Promise<unknown>;
  notify(message:string):void;
  operationWorkers():number;
  randomUUID():string;
  refreshAccounts():void|Promise<unknown>;
  refreshSummary():void|Promise<unknown>;
  openTask(taskId:number):void|Promise<unknown>;
  formatDateTime(value:unknown):string;
  fallbackFocus?():HTMLElement|null;
}
export type InspectionDialog='start'|'history'|'failures';
export type InspectionRow=Readonly<Record<string,unknown>>;
export const inspectionScopeLabel=(scope:string)=>scope==='only'?'已归档账号':scope==='all'?'全部账号':'未归档账号';
export const inspectionStatusLabel=(status:unknown)=>({running:'进行中',completed:'已完成',interrupted:'已中断'}[String(status)]||String(status??''));
export const inspectionFailureLabel=(status:unknown)=>({deactivated_skipped:'已废跳过',rejected:'未能入队',failed:'查活失败',error:'执行异常',attention_required:'执行失败',interrupted:'执行中断'}[String(status)]||String(status??''));
const message=(error:unknown)=>error&&typeof error==='object'&&'message' in error?String(error.message):String(error);
function payload(value:unknown):Record<string,unknown>{return value&&typeof value==='object'?value as Record<string,unknown>:{};}
function snapshots(value:unknown):readonly InspectionRow[]{return Object.freeze((Array.isArray(value)?value:[]).map(row=>Object.freeze({...payload(row)})));}

/** Owns only inspection UI requests; closing a view never cancels accepted remote work. */
export function useAccountInspection(deps:AccountInspectionDependencies){
  const startOpen=ref(false),historyOpen=ref(false),failuresOpen=ref(false);
  const archived=ref('0'),workers=ref<number|string>(3),starting=ref(false),startError=ref('');
  const historyPage=ref(1),failurePage=ref(1),failureId=ref<number|null>(null);
  const historyRows=shallowRef<readonly InspectionRow[]>([]),failureRows=shallowRef<readonly InspectionRow[]>([]);
  const historyTotal=ref(0),failureTotal=ref(0),historyReady=ref(false),failureReady=ref(false),failureError=ref('');
  const historyLoading=ref(false),failureLoading=ref(false),active=ref(false);
  let requestKey:string|null=null,historyVersion=0,failureVersion=0,disposed=false;
  let historyController:AbortController|undefined,failureController:AbortController|undefined;
  let timer:ReturnType<typeof setInterval>|undefined;
  const documentVisible=()=>typeof document==='undefined'||!document.hidden;
  const historyLabel=computed(()=>historyReady.value?`共 ${historyTotal.value} 条 · 第 ${historyPage.value} 页`:'');
  const failureLabel=computed(()=>failureReady.value?`共 ${failureTotal.value} 条 · 第 ${failurePage.value} 页`:'');
  async function request(path:string,options:RequestInit={},controller=new AbortController()){
    const timeout=setTimeout(()=>controller.abort(),30000);
    try{return payload(await deps.request(path,{...options,signal:controller.signal}));}
    finally{clearTimeout(timeout);}
  }
  function refreshAccountViews(){
    for(const refresh of [deps.refreshAccounts,deps.refreshSummary]){
      try{void Promise.resolve(refresh()).catch(()=>{});}catch{/* Accepted inspection state is not a retryable start failure. */}
    }
  }
  function openStart(context:AccountActionContext){if(disposed)return;archived.value=context.archived;workers.value=Math.min(16,deps.operationWorkers());startError.value='';startOpen.value=true;}
  async function submit(){
    const count=Number(workers.value);
    if(disposed||starting.value||!Number.isInteger(count)||count<1||count>16)return;
    starting.value=true;
    try{
      requestKey ||= deps.randomUUID();
      const result=await request('/api/accounts/inspections',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workers:count,archived:archived.value,idempotency_key:requestKey})});
      requestKey=null;active.value=true;
      if(disposed)return;
      startOpen.value=false;
      deps.notify(result.created?'巡检已加入统一任务队列':'已有本次巡检记录，已打开历史');
      openHistory();
    }catch(error){if(!disposed)startError.value=`巡检启动请求失败：${message(error)}。可查看巡检历史，或使用当前提交再次确认。`;}
    finally{starting.value=false;}
  }
  function openHistory(){if(disposed)return;historyPage.value=1;++historyVersion;historyOpen.value=true;void refreshHistory();}
  function changeHistoryPage(delta:number){if(historyLoading.value)return;historyPage.value=Math.max(1,historyPage.value+delta);++historyVersion;void refreshHistory();}
  async function refreshHistory(){
    if(disposed||historyLoading.value||!historyOpen.value||!documentVisible())return;
    historyLoading.value=true;
    const page=historyPage.value,version=historyVersion,controller=new AbortController();historyController=controller;
    try{
      const result=await request(`/api/accounts/inspections?page=${page}`,{},controller);
      if(disposed||controller.signal.aborted||!historyOpen.value||page!==historyPage.value||version!==historyVersion)return;
      const wasActive=active.value;active.value=!!result.active;
      if(wasActive&&!active.value)refreshAccountViews();
      historyRows.value=snapshots(result.items);historyTotal.value=Number(result.total);historyReady.value=true;
    }catch(error){if(!disposed&&historyOpen.value&&documentVisible()&&version===historyVersion)deps.notify(`读取巡检历史失败：${message(error)}`);}
    finally{
      historyLoading.value=false;if(historyController===controller)historyController=undefined;
      if(version!==historyVersion&&!disposed&&historyOpen.value&&documentVisible())void refreshHistory();
    }
  }
  function openFailures(id:number){
    if(disposed)return;
    failureId.value=Number(id);failurePage.value=1;++failureVersion;failureReady.value=false;failureError.value='';failureRows.value=[];failuresOpen.value=true;void refreshFailures();
  }
  function changeFailuresPage(delta:number){if(failureLoading.value)return;failurePage.value=Math.max(1,failurePage.value+delta);++failureVersion;void refreshFailures();}
  async function refreshFailures(){
    if(disposed||failureLoading.value||!failureId.value||!failuresOpen.value||!documentVisible())return;
    failureLoading.value=true;
    const id=failureId.value,page=failurePage.value,version=failureVersion,controller=new AbortController();failureController=controller;
    try{
      const result=await request(`/api/accounts/inspections/${id}/failures?page=${page}`,{},controller);
      if(disposed||controller.signal.aborted||!failuresOpen.value||id!==failureId.value||page!==failurePage.value||version!==failureVersion)return;
      failureRows.value=snapshots(result.items);failureTotal.value=Number(result.total);failureReady.value=true;failureError.value='';
    }catch(error){if(!disposed&&failuresOpen.value&&documentVisible()&&version===failureVersion)failureError.value=`读取失败：${message(error)}，可点击刷新重试。`;}
    finally{
      failureLoading.value=false;if(failureController===controller)failureController=undefined;
      if(version!==failureVersion&&!disposed&&failuresOpen.value&&documentVisible())void refreshFailures();
    }
  }
  async function stop(id:number){
    if(disposed)return;
    try{await request(`/api/accounts/inspections/${Number(id)}/cancel`,{method:'POST'});if(disposed)return;deps.notify('已请求停止，将在安全检查点结束');void refreshHistory();}
    catch(error){if(!disposed)deps.notify(`停止巡检失败：${message(error)}`);}
  }
  function close(kind?:InspectionDialog){
    if(!kind||kind==='start')startOpen.value=false;
    if(!kind||kind==='history'){historyOpen.value=false;++historyVersion;historyController?.abort();}
    if(!kind||kind==='failures'){failuresOpen.value=false;++failureVersion;failureController?.abort();}
  }
  function syncTimer(){
    if(timer!==undefined){clearInterval(timer);timer=undefined;}
    if(disposed||!documentVisible()||(!historyOpen.value&&!failuresOpen.value))return;
    timer=setInterval(()=>{if(historyOpen.value)void refreshHistory();if(failuresOpen.value)void refreshFailures();},5000);
  }
  function visibilityChanged(){
    if(!documentVisible()){++historyVersion;++failureVersion;historyController?.abort();failureController?.abort();}
    syncTimer();
  }
  watch([historyOpen,failuresOpen],syncTimer,{flush:'sync'});
  if(typeof document!=='undefined')document.addEventListener('visibilitychange',visibilityChanged);
  onScopeDispose(()=>{disposed=true;close();syncTimer();if(typeof document!=='undefined')document.removeEventListener('visibilitychange',visibilityChanged);});
  return{startOpen,historyOpen,failuresOpen,archived,workers,starting,startError,historyPage,failurePage,failureId,historyRows,failureRows,historyTotal,failureTotal,historyReady,failureReady,failureError,historyLoading,failureLoading,historyLabel,failureLabel,
    openStart,submit,openHistory,openFailures,close,changeHistoryPage,changeFailuresPage,refreshHistory,refreshFailures,stop};
}
