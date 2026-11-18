import {computed,onScopeDispose,ref,shallowRef} from 'vue';
import type {AccountActionContext} from './useAccounts';
export interface C2aReimportDependencies {
  request(path:string,options?:RequestInit):Promise<unknown>;
  notify(message:string):void;
  refreshAccounts(context:AccountActionContext):void|Promise<unknown>;
  selectionChanged?(context:AccountActionContext):void;
  trackAccepted(items:readonly Readonly<Record<string,unknown>>[],label:string,options:{navigate:false}):void|Promise<unknown>;
  openTasks(options:{filters:{type:'c2a_session_reimport'};taskId?:number;runId:number|null}):void|Promise<unknown>;
  beginBusy?(trigger:HTMLElement|null,label:string):(()=>void)|void;
}
export interface C2aReceiptEntry {item:Readonly<Record<string,unknown>>;state:'已入队'|'未入队'|'入队失败'}
function record(value:unknown):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('服务端响应格式无效');const result=value as Record<string,unknown>;if(result.ok===false)throw new Error(typeof result.error==='string'?result.error:'请求失败');return result;}
function freeze<T>(value:T):T{if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;}
function copy<T>(value:T):T{return freeze(JSON.parse(JSON.stringify(value)) as T);}
const message=(error:unknown)=>error&&typeof error==='object'&&'message' in error?String(error.message):'请求失败';
function entries(result:Record<string,unknown>):C2aReceiptEntry[]{return (['queued','skipped','failed'] as const).flatMap((field,index)=>(Array.isArray(result[field])?result[field] as unknown[]:[]).map(item=>({item:record(item),state:(['已入队','未入队','入队失败'] as const)[index]})));}
export function useC2aReimport(deps:C2aReimportDependencies,lifecycle:{closed?(trigger:HTMLElement|null,returnValue:string):void}={}){
  const isOpen=ref(false),submitting=ref(false),status=ref(''),accountIds=shallowRef<readonly number[]>([]),result=shallowRef<Readonly<Record<string,unknown>>|null>(null);
  let context:AccountActionContext|null=null,trigger:HTMLElement|null=null,disposed=false;
  const receiptEntries=computed(()=>result.value?entries(result.value):[]),taskEntries=computed(()=>receiptEntries.value.filter(entry=>Number(entry.item.task_id)>0));
  const summary=computed(()=>{const value=result.value;if(!value)return'';const queued=Number(value.queued_count??(Array.isArray(value.queued)?value.queued.length:0)),skipped=Number(value.skipped_count??(Array.isArray(value.skipped)?value.skipped.length:0)),failed=Number(value.failed_count??(Array.isArray(value.failed)?value.failed.length:0));return`C2A 重新导入：已入队 ${queued} 个，未入队 ${skipped+failed} 个`;});
  function open(supplied:AccountActionContext,button:HTMLElement|null=null){
    if(disposed)return false;
    if(isOpen.value){deps.notify('C2A 同步确认窗口不可用，请刷新页面后重试');return false;}
    const ids=supplied.accountIds.map(id=>{if(!/^[1-9]\d*$/.test(id)||!Number.isSafeInteger(Number(id)))throw new Error('账号 ID 无效');return Number(id);});
    if(!ids.length){deps.notify('请先选择账号');return false;}
    context=copy(supplied);accountIds.value=Object.freeze([...ids]);trigger=button;submitting.value=false;status.value='';isOpen.value=true;return true;
  }
  function close(returnValue='cancel',force=false){
    if(!isOpen.value||(submitting.value&&!force))return false;
    const button=trigger;isOpen.value=false;accountIds.value=[];context=null;trigger=null;
    lifecycle.closed?.(button,returnValue);return true;
  }
  async function followup(callback:()=>void|Promise<unknown>,prefix:string){try{await callback();}catch(error){deps.notify(prefix+message(error));}}
  function showResult(value:unknown){result.value=copy(record(value));}
  function openTasks(items:readonly Readonly<Record<string,unknown>>[]=taskEntries.value.map(entry=>entry.item)){
    const single=items.length===1?items[0]:null;
    return followup(()=>deps.openTasks({filters:{type:'c2a_session_reimport'},taskId:Number(single?.task_id)||undefined,runId:Number(single?.run_id)||null}),'C2A 请求已处理，打开任务失败: ');
  }
  async function submit(){
    if(disposed||!isOpen.value||!context||!accountIds.value.length||submitting.value)return;
    const ids=[...accountIds.value],captured=context,button=trigger;
    submitting.value=true;status.value='正在创建 C2A 同步任务…';
    const restore=deps.beginBusy?.(button,'提交导入…');let response:Record<string,unknown>;
    try{response=record(await deps.request('/api/accounts/c2a/sync-bulk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({account_ids:ids})}));}
    catch(error){deps.notify('重新导入 C2A 失败: '+message(error));if(!disposed)status.value=`提交失败：${message(error)}。请检查后再次提交。`;submitting.value=false;restore?.();deps.selectionChanged?.(captured);return;}
    try{
      if(!disposed)showResult(response);
      const skipped=Number(response.skipped_count||0)+Number(response.failed_count||0),queued=Array.isArray(response.queued)?response.queued:[];
      if(response.accepted){
        deps.notify(`C2A 重新导入已入队 ${response.queued_count||0} 个${skipped?`，未入队 ${skipped} 个（已显示具体原因）`:''}${queued.length?'，最终结果在任务回执中更新':''}`);
        const tasks=entries(response).filter(entry=>Number(entry.item.task_id)>0).map(entry=>entry.item);
        if(tasks.length)await followup(()=>deps.trackAccepted(tasks,'重新导入 C2A',{navigate:false}),'C2A 请求已处理，回执更新失败: ');
      }else{
        deps.notify(skipped?`C2A 已重新导入 ${response.updated_count||0} 个，跳过/失败 ${skipped} 个`:`C2A 已重新导入 ${response.updated_count||0} 个`);
        await followup(()=>deps.refreshAccounts(captured),'C2A 请求已处理，页面更新失败: ');
      }
    }catch(error){deps.notify('C2A 请求已处理，回执更新失败: '+message(error));}
    finally{submitting.value=false;try{restore?.();}finally{if(!disposed)close('submitted',true);}}
  }
  onScopeDispose(()=>{disposed=true;close('cancel',true);});
  return{isOpen,submitting,status,accountIds,result,receiptEntries,taskEntries,summary,open,close,submit,showResult,openTasks};
}
