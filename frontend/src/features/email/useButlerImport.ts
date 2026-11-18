import {computed,reactive} from 'vue';
import {ApiError,isAbort} from '../../api/client';
import type {EmailApi} from '../../api/email';
import type {BatchResponse,ButlerBatch,ButlerFilters,ButlerPreview,ButlerRequest,EmailMountDependencies,EmailStorage} from './contracts';
import {message} from './presentation';
import {availabilityLabels,butlerErrors,providers,waitingLabels} from './butlerLabels';
export const BUTLER_IMPORT_STORAGE_KEY='turb.butler-import.v1';
const successful=(value?:string)=>['completed','succeeded','done'].includes(value||'');
const running=(value?:string)=>['pending','queued','running','processing'].includes(value||'');
const revision=(batch:ButlerBatch)=>JSON.stringify([batch.updated_at,batch.status,batch.imported,batch.pending,batch.submitting,batch.unknown,batch.failed,batch.error_code,batch.blocked_by]);
export function useButlerImport(api:EmailApi,deps:EmailMountDependencies,runtime:{storage:EmailStorage;uuid?:()=>string;now?:()=>number}){
 const state=reactive({open:false,filters:{provider:'icloud_hme',count:10} as ButlerFilters,providers:[...providers],preview:null as ButlerPreview|null,request:null as ButlerRequest|null,batch:null as ButlerBatch|null,busy:false,polling:false,previewing:false,error:'',storageError:false,resumePending:null as string|null});
 let active=false,disposed=false,previewVersion=0,pollVersion=0,previewController:AbortController|undefined,pollController:AbortController|undefined,optionsController:AbortController|undefined;
 let previewTimer:ReturnType<typeof setTimeout>|undefined,pollTimer:ReturnType<typeof setTimeout>|undefined,pollPromise:Promise<void>|null=null,refreshed=-1,lastRefresh=0,refreshPromise:Promise<void>|null=null;
 const now=runtime.now||Date.now,eligible=()=>active&&!document.hidden&&!disposed;
 try{
  const saved=JSON.parse(runtime.storage.getItem(BUTLER_IMPORT_STORAGE_KEY)||'null');
  if(saved&&typeof saved.request_id==='string'&&typeof saved.preview_token==='string'){
   state.request={request_id:saved.request_id,preview_token:saved.preview_token,filters:saved.filters};
   if(saved.filters&&typeof saved.filters.provider==='string'&&Number.isSafeInteger(saved.filters.count))state.filters={provider:saved.filters.provider,count:saved.filters.count};
   if(typeof saved.batch_id==='string'&&saved.batch_id){state.batch={batch_id:saved.batch_id,status:typeof saved.batch_status==='string'?saved.batch_status:'running'};if(saved.batch_status!=='cancelled'&&typeof saved.resume_revision==='string')state.resumePending=saved.resume_revision;}
  }
 }catch{state.storageError=true;state.error='无法读取浏览器中的导入记录；请先恢复浏览器存储后再导入。';}
 function persist(){if(!state.request)return;runtime.storage.setItem(BUTLER_IMPORT_STORAGE_KEY,JSON.stringify({...state.request,...(state.batch?{batch_id:state.batch.batch_id,batch_status:state.batch.status}:{}),...(state.resumePending?{resume_revision:state.resumePending}:{})}));}
 function invalidatePreview(){previewVersion++;previewController?.abort();optionsController?.abort();clearTimeout(previewTimer);state.preview=null;state.previewing=false;}
 function stopReads(){invalidatePreview();pollVersion++;pollController?.abort();pollController=undefined;pollPromise=null;state.polling=false;clearTimeout(pollTimer);}
 const isRunning=computed(()=>running(state.batch?.status));
 const canReset=computed(()=>state.batch?.status==='cancelled'||!!state.batch&&!state.batch.can_retry&&!Number(state.batch.unknown||state.batch.internal_unknown_count||0)&&['completed','succeeded','done','partial','partial_success','failed','rejected'].includes(state.batch.status));
 const canRetry=computed(()=>!!state.request&&!state.busy&&!state.polling&&state.batch?.status!=='cancelled'&&!isRunning.value&&!state.resumePending&&(!state.batch||state.batch.can_retry===true));
 const canCancel=computed(()=>!!state.batch&&state.batch.can_cancel!==false&&state.batch.status!=='cancelled'&&!successful(state.batch.status));
 const batchTitle=computed(()=>{
  if(state.resumePending)return'正在恢复原批次';
  const batch=state.batch;
  if(!batch)return state.busy?'正在提交导入':'导入请求响应缺失';
  const labels:Record<string,string>={pending:'等待导入',queued:'等待导入',running:'正在导入',processing:'正在导入',partial:batch.can_retry?'部分完成，可继续原批次':'本批次已结束（部分失败）',partial_success:batch.can_retry?'部分成功，可继续原批次':'本批次已结束（部分成功）',completed:'导入完成',succeeded:'导入完成',done:'导入完成',failed:'导入失败',rejected:'导入未开始',unknown:'导入失败',cancelled:'本批次已终止'};
  return labels[batch.status]||'状态记录缺失';
 });
 const batchDetails=computed(()=>{
  const batch=state.batch;if(!batch)return'可以关闭窗口，已保存原请求；重新打开后可恢复结果。';
  const lines=[batch.status==='cancelled'?'已停止后续导入。已导入邮箱、原租约和失败记录均保留；已发出的请求仍会保存结果。':isRunning.value||state.resumePending?'可以关闭窗口，导入会在后台继续；刷新页面也能恢复。':batch.can_retry?'可继续原批次处理剩余邮箱，已导入的邮箱会保留。':'已导入的邮箱已加入本地库存，可以关闭窗口或新建导入。'];
  for(const code of batch.blocked_by||[])lines.push(waitingLabels[code]||`等待准入（${code}）`);
  if(batch.error_code)lines.push(`${butlerErrors[batch.error_code]||'批次异常'}（${batch.error_code}）`);
  for(const [code,count]of Object.entries(batch.error_counts||{}))lines.push(`${butlerErrors[code]||'处理异常'}（${code}）：${count} 个`);
  if(batch.internal_unknown_count)lines.push(`原请求仍有 ${batch.internal_unknown_count} 个待核实回执，保留原批次恢复；内部状态：${batch.internal_status||'未记录'}。`);
  return lines.join('\n');
 });
 const availability=computed(()=>{
  const data=state.preview;if(!data)return'';
  const reasons=Object.entries(availabilityLabels).filter(([key])=>Number.isSafeInteger(data.availability_buckets?.[key])&&Number(data.availability_buckets?.[key])>0).map(([key,label])=>`${label} ${data.availability_buckets![key]} 个`);
  return`当前可用 ${Number(data.available||0)} 个 · 本次可导入 ${Number(data.selected||0)} 个。${reasons.length?`${Number.isSafeInteger(data.resource_total)?`当前查询范围 ${data.resource_total} 个`:'当前查询范围'}：${reasons.join(' · ')}。`:''}Butler“未租用”不等于可用于 OpenAI。查询不占用库存；确认后由 Butler 分配地址，导入时再核对本地占用。`;
 });
 function schedulePoll(){clearTimeout(pollTimer);if(eligible()&&state.batch&&state.batch.status!=='cancelled'&&(isRunning.value||state.resumePending))pollTimer=setTimeout(()=>void poll(),2000);}
 function refreshInventory(){
  const imported=Number(state.batch?.imported||0);
  if(!imported||imported===refreshed||refreshPromise||(isRunning.value&&refreshed>=0&&now()-lastRefresh<15000))return;
  refreshPromise=Promise.resolve().then(()=>deps.onInventoryChanged()).then(()=>{refreshed=imported;},cause=>{state.error=`邮箱已导入，但显示未完全刷新：${message(cause)}`;}).finally(()=>{refreshPromise=null;lastRefresh=now();if(!isRunning.value&&Number(state.batch?.imported||0)!==imported)refreshInventory();});
 }
 function accept(data:BatchResponse){
  if(!data.batch?.batch_id)throw new Error('服务端未返回导入批次');
  if(state.batch&&state.batch.batch_id!==data.batch.batch_id)throw new Error('服务端返回了不同批次，保留原批次恢复原请求');
  let cancelled=state.batch?.status==='cancelled';
  try{const saved=JSON.parse(runtime.storage.getItem(BUTLER_IMPORT_STORAGE_KEY)||'null');cancelled ||= saved?.batch_id===data.batch.batch_id&&saved.batch_status==='cancelled';}catch{/* keep in-memory receipt */}
  const batch=cancelled?{...data.batch,status:'cancelled',can_retry:false,can_cancel:false}:data.batch;
  if(state.resumePending&&(running(batch.status)||revision(batch)!==state.resumePending))state.resumePending=null;
  state.batch=batch;
  if(batch.status==='cancelled'){state.resumePending=null;pollVersion++;pollController?.abort();state.polling=false;clearTimeout(pollTimer);}
  try{persist();}catch{state.error='原请求已保存，批次编号暂未写入浏览器；重开后将恢复原请求。';}
  refreshInventory();
 }
 async function preview(){
  if(!eligible()||!state.open||state.request||state.busy)return;
  const filters={...state.filters};invalidatePreview();state.error='';
  if(!providers.some(row=>row.value===filters.provider)){state.error='请选择支持的邮箱来源';return;}
  if(!Number.isSafeInteger(filters.count)||filters.count<1){state.error='数量须为大于0的整数';return;}
  const ticket=previewVersion;previewController=new AbortController();state.previewing=true;
  try{const data=await api.butlerPreview(filters,previewController.signal);if(ticket!==previewVersion||!eligible()||!state.open||JSON.stringify(filters)!==JSON.stringify(state.filters))return;if(!data.preview_token)throw new Error('可用数量查询未返回有效结果，请刷新数量');state.preview={...data,filters};if(!data.selected)state.error='当前没有可用于 OpenAI 的邮箱，请在 Butler 按目标服务核对来源状态、历史占用和冷却限制后刷新数量。';}
  catch(cause){if(ticket===previewVersion&&!isAbort(cause))state.error=`查询可用数量失败：${message(cause)}`;}
  finally{if(ticket===previewVersion)state.previewing=false;}
 }
 function changeFilters(patch:Partial<ButlerFilters>){if(state.request)return;Object.assign(state.filters,patch);invalidatePreview();state.error='';if(eligible()&&state.open)previewTimer=setTimeout(()=>void preview(),400);}
 async function open(){
  state.open=true;
  if(state.storageError)return;
  if(state.batch){await poll();return;}
  if(state.request){state.error='上次导入未收到响应，请重试原请求恢复结果。';return;}
  if(!eligible())return;
  optionsController=new AbortController();const ticket=previewVersion;
  try{const data=await api.options(optionsController.signal);if(ticket!==previewVersion||!eligible()||!state.open)return;if(data.providers?.length)state.providers=data.providers;}
  catch(cause){if(ticket===previewVersion&&!isAbort(cause))state.error=`读取导入选项失败：${message(cause)}`;}
  if(ticket===previewVersion)await preview();
 }
 function close(){state.open=false;invalidatePreview();}
 async function retry(){
  if(state.busy||state.polling||!state.request||state.batch?.status==='cancelled'||(state.batch&&!state.batch.can_retry))return;
  const request={request_id:state.request.request_id,preview_token:state.request.preview_token},batch=state.batch;state.busy=true;state.error='';
  try{const data=await(batch?api.retryBatch(batch.batch_id,request):api.createBatch(request));if(batch)state.resumePending=revision(batch);accept(data);}
  catch(cause){
   if(!state.batch&&cause instanceof ApiError&&['import_preview_not_found','import_preview_expired','import_preview_empty','import_snapshot_conflict'].includes(cause.code)){
    try{runtime.storage.removeItem(BUTLER_IMPORT_STORAGE_KEY);state.request=null;invalidatePreview();state.error=`导入尚未开始：${message(cause)}。请重新预览。`;}catch{state.error='导入尚未开始，但原记录暂未清除；请恢复浏览器存储后重试原请求。';}
   }else state.error=`导入请求失败：${message(cause)}。请${state.batch?'继续原批次':'重试原请求'}恢复，已保留原编号。`;
  }finally{state.busy=false;schedulePoll();}
 }
 async function apply(){
  if(state.busy||state.request||!state.preview||state.preview.selected<1)return;
  if(JSON.stringify(state.filters)!==JSON.stringify(state.preview.filters)){invalidatePreview();state.error='筛选已变化，请刷新可用数量。';return;}
  try{if(state.storageError)throw new Error('storage');state.request={request_id:(runtime.uuid||(()=>crypto.randomUUID()))(),preview_token:state.preview.preview_token,filters:{...state.filters}};persist();}
  catch{state.request=null;state.error='无法保存导入请求，请启用浏览器本地存储后重试。';return;}
  await retry();
 }
 async function poll(){
  if(pollPromise)return pollPromise;
  if(!eligible()||!state.batch||state.busy)return;
  clearTimeout(pollTimer);const ticket=++pollVersion,id=state.batch.batch_id;pollController=new AbortController();state.polling=true;
  const task=(async()=>{try{const data=await api.batch(id,pollController!.signal);if(ticket!==pollVersion||!eligible()||state.batch?.batch_id!==id)return;state.error='';accept(data);}catch(cause){if(ticket===pollVersion&&!isAbort(cause))state.error=`暂时无法读取原批次：${message(cause)}。请重开此窗口恢复查看。`;}finally{if(ticket===pollVersion){state.polling=false;pollPromise=null;schedulePoll();}}})();
  pollPromise=task;await task;
 }
 async function cancel(){
  if(state.busy||!canCancel.value||!state.batch)return;const id=state.batch.batch_id;state.busy=true;state.error='';
  try{const data=await api.cancelBatch(id);accept(data);if(data.batch.status!=='cancelled'&&!successful(data.batch.status))throw new Error('服务端未返回终止回执');pollVersion++;pollController?.abort();pollPromise=null;state.polling=false;}
  catch(cause){state.error=`终止请求失败：${message(cause)}。已保留原批次，请重试终止或查看原批次状态。`;}
  finally{state.busy=false;schedulePoll();}
 }
 async function reset(){
  if(!canReset.value||state.busy||state.polling)return;
  try{runtime.storage.removeItem(BUTLER_IMPORT_STORAGE_KEY);}catch{state.error='无法清除上次导入记录，请恢复浏览器存储后重试。';return;}
  stopReads();state.request=null;state.batch=null;state.resumePending=null;state.error='';refreshed=-1;lastRefresh=0;await preview();
 }
 function storageChanged(event:StorageEvent){if(event.key!==BUTLER_IMPORT_STORAGE_KEY||!event.newValue||!state.batch)return;try{const saved=JSON.parse(event.newValue);if(saved.batch_id!==state.batch.batch_id||saved.batch_status!=='cancelled')return;pollVersion++;pollController?.abort();pollPromise=null;clearTimeout(pollTimer);state.polling=false;state.resumePending=null;state.batch={...state.batch,status:'cancelled',can_retry:false,can_cancel:false};}catch{/* invalid cross-tab data has no effect */}}
 window.addEventListener('storage',storageChanged);
 return{state,isRunning,canReset,canRetry,canCancel,batchTitle,batchDetails,availability,open,close,preview,changeFilters,apply,retry,poll,cancel,reset,
  setActive(value:boolean){if(disposed||value===active)return;active=value;if(!value)stopReads();else if(state.batch)void poll();else if(state.open&&!state.request)void open();},
  dispose(){disposed=true;stopReads();window.removeEventListener('storage',storageChanged);},
 };
}
