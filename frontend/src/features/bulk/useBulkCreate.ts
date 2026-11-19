import {computed,onScopeDispose,ref} from 'vue';
import {BulkApiError} from '../../api/bulk';
import type {AccountQuerySpec} from '../accounts/queryAdapter';
import {accountFilters,filterChips,promotionOffers,selectedValues,type AccountFilterField,type AccountFilterKey} from '../accounts/filterDefinitions';
import type {BulkCatalog,BulkCreateDependencies,BulkDraft,BulkRecord} from './contracts';
import {bulkId} from './contracts';

interface Selection extends BulkRecord {id:string;state?:string;status?:string;target_count?:number;total_count?:number;selection_revision?:number;request_parameters?:BulkRecord;parameters?:BulkRecord;config_revision?:string;error_code?:string;error?:{message?:string};error_detail?:{message?:string}}
interface FacetOption {value:string;label?:string;count?:number}
type Facets=Record<string,FacetOption[]>;
const draftKey='turb_bulk_draft_v1',selectionKey='turb_bulk_selection_v1';
const clone=<T>(value:T):T=>JSON.parse(JSON.stringify(value));
const record=(value:unknown):BulkRecord=>value&&typeof value==='object'&&!Array.isArray(value)?value as BulkRecord:{};

/** Owns the create form. The containing page alone schedules selection polling. */
export function useBulkCreate(deps:BulkCreateDependencies) {
 const defaultDraft=():BulkDraft=>({name:'',operation_key:'plan_check',query:deps.adapter.normalize(),source:null,parameters:{},max_concurrency:3});
 const readSaved=(key:string):unknown=>{try{return JSON.parse(deps.storage.getItem(key)||'null');}catch{return null;}};
 const draft=ref<BulkDraft>(defaultDraft()),selection=ref<Selection|null>(null),catalog=ref<BulkCatalog|null>(null);
 const facets=ref<Facets>({}),matched=ref<number|null>(null),loading=ref(false),creating=ref(false),recovering=ref(false);
 const error=ref(''),errorField=ref(''),existingBatchId=ref(''),pendingRevision=ref(0);
 const facetCache=new Map<string,{facets:Facets;matched:number|null;at:number}>();
 const reads=new Set<AbortController>();
 let epoch=0,disposed=false,visible=true,initialized=false,initializePromise:Promise<void>|null=null;
 let refreshPromise:{epoch:number;promise:Promise<void>}|null=null,advancingEpoch:number|null=null;
 let pendingCreation:{epoch:number;paused:boolean}|null=null,facetTimer:ReturnType<typeof setTimeout>|undefined;
 const operations=computed(()=>catalog.value?.operations||[]);
 const operation=computed(()=>operations.value.find(item=>item.key===draft.value.operation_key));
 const configRevision=computed(()=>String(operation.value?.effective_settings?.config_revision??operation.value?.config_revision??catalog.value?.config_revision??''));
 const selectionState=computed(()=>selection.value?.state||selection.value?.status||'');
 const needsRefresh=computed(()=>selectionState.value==='preparing');
 const concurrencyMax=computed(()=>Number(catalog.value?.limits?.concurrency_max)||128);
 const pendingCount=computed(()=>{pendingRevision.value;try{return deps.intents.pending().length;}catch{return 1;}});
 const count=computed(()=>selectionState.value==='ready'?Number(selection.value?.target_count??selection.value?.total_count):draft.value.source?.kind==='ids'?(draft.value.source.ids as unknown[]).length:draft.value.source?null:matched.value);
 const scopeLabel=computed(()=>draft.value.source?.kind==='ids'?`已选 ${(draft.value.source.ids as unknown[]).length} 个账号`:draft.value.source?.kind==='batch_targets'?`批次 #${draft.value.source.batch_id} 的固定名单`:draft.value.query.filters.email?`邮箱含「${draft.value.query.filters.email}」`:'按当前筛选');
 const summary=computed(()=>creating.value?'正在固定账号范围…':selectionState.value==='ready'?'账号范围已固定':count.value===0?'没有匹配账号':'匹配账号数量');
 const hint=computed(()=>creating.value?'正在准备本批次，请稍候':selectionState.value==='ready'?'将使用这份固定名单创建批次':count.value===0?'请调整账号筛选条件':draft.value.source?.kind==='batch_targets'?'创建时沿用原批次固定名单':draft.value.source?.kind==='ids'?'将使用已选账号创建批次':matched.value==null?'正在统计，创建时会核对最终数量':`当前条件匹配 ${matched.value} 个账号，将全部执行`);
 const availabilityWarning=computed(()=>operation.value?.availability?.available===false?`当前设置不可用：${operation.value.availability.reason||record(operation.value.availability).reason_code||'请检查配置'}。请到配置页调整。`:'');

 function saveDraft(){try{deps.storage.setItem(draftKey,JSON.stringify(draft.value));}catch{/* Draft storage is best effort; intent storage remains mandatory. */}}
 function saveSelection(){try{if(selection.value)deps.storage.setItem(selectionKey,JSON.stringify(selection.value));else deps.storage.removeItem(selectionKey);}catch{/* The server selection remains recoverable through its request identity. */}}
 function hasOverrides(value:Selection|null){return[value?.request_parameters,value?.parameters].some(parameters=>Object.keys(parameters||{}).some(key=>key!=='timezone_offset_min'||draft.value.operation_key!=='plan_check'));}
 function normalizedDraft(raw:unknown):{draft:BulkDraft;limited:boolean}{
  const value=record(raw),query=deps.adapter.normalize(record(value.query));
  const source=value.source&&typeof value.source==='object'?clone(value.source as BulkRecord):null;
  const limited=!source&&Boolean(value.limit||query.limit);
  return{limited,draft:{...defaultDraft(),name:String(value.name||''),operation_key:String(value.operation_key||'plan_check'),
   query:deps.adapter.normalize({...query,limit:null}),source,parameters:{},max_concurrency:Number(value.max_concurrency??3)}};
 }
 function restoreDraft(raw:unknown,saved:unknown){const next=normalizedDraft(raw);draft.value=next.draft;const selected=record(saved);selection.value=typeof selected.id==='string'?clone(selected) as Selection:null;if(next.limited||hasOverrides(selection.value))selection.value=null;saveDraft();saveSelection();}
 restoreDraft(readSaved(draftKey),readSaved(selectionKey));
 function clearError(){error.value='';errorField.value='';existingBatchId.value='';}
 function report(value:unknown,prefix=''){
  const failure=value as Partial<BulkApiError>;error.value=prefix+(failure.message||String(value))+(failure.code?`（${failure.code}）`:'')+(failure.status===401?'，请重新登录后返回，草稿与请求身份已保留。':'');errorField.value=failure.field||'';
 }
 const aborted=(value:unknown)=>record(value).name==='AbortError';
 function setVisible(value:boolean){visible=value;if(!value){clearTimeout(facetTimer);reads.forEach(controller=>controller.abort());}}
 async function read<T>(path:string):Promise<T>{const controller=new AbortController();reads.add(controller);try{const result=await deps.api.request<T>(path,{signal:controller.signal});if(controller.signal.aborted)throw new DOMException('读取已取消','AbortError');return result;}finally{reads.delete(controller);}}
 async function loadCatalog(force=false){
  if(catalog.value&&!force)return;
  const result=await read<BulkCatalog>('/catalog');if(disposed)return;catalog.value=result;
  if(!operations.value.some(item=>item.key===draft.value.operation_key)){draft.value.operation_key=operations.value[0]?.key||'';selection.value=null;saveSelection();saveDraft();}
 }
 async function loadFacets(){
  if(!visible||disposed)return;
  const currentEpoch=epoch,signature=JSON.stringify(deps.adapter.normalize(draft.value.query));
  const cached=facetCache.get(signature);
  if(cached&&deps.now()-cached.at<30000){facets.value=cached.facets;matched.value=cached.matched;return;}
  matched.value=null;
  const data=await read<BulkRecord>(`/query-facets?query=${encodeURIComponent(signature)}`);
  const value=record(data.facets||data) as Facets,found=data.matched==null?null:Number(data.matched);
  facetCache.set(signature,{facets:value,matched:found,at:deps.now()});if(facetCache.size>10)facetCache.delete(facetCache.keys().next().value!);
  if(!disposed&&currentEpoch===epoch&&signature===JSON.stringify(deps.adapter.normalize(draft.value.query))){facets.value=value;matched.value=found;}
 }
 function scheduleFacets(){clearTimeout(facetTimer);if(!visible)return;const currentEpoch=epoch;facetTimer=setTimeout(()=>{void loadFacets().catch(failure=>{if(!aborted(failure)&&!disposed&&currentEpoch===epoch)report(failure,'筛选选项更新失败：');});},350);}
 function invalidate(){epoch++;pendingCreation=null;creating.value=false;selection.value=null;saveSelection();}
 function applySeed(value:BulkDraft){invalidate();clearTimeout(facetTimer);restoreDraft(clone(value),null);matched.value=null;clearError();if(initialized)scheduleFacets();}
 function setDraftField(key:'name'|'max_concurrency',value:string|number){if(creating.value)return;if(key==='name')draft.value.name=String(value);else draft.value.max_concurrency=Number(value);saveDraft();}
 function setOperation(key:string){if(creating.value||draft.value.operation_key===key)return;draft.value.operation_key=key;invalidate();clearError();saveDraft();}
 function updateQuery(query:AccountQuerySpec){if(creating.value)return;const next=deps.adapter.normalize({...query,limit:null});if(JSON.stringify(next)===JSON.stringify(draft.value.query))return;draft.value.query=next;matched.value=null;invalidate();clearError();saveDraft();scheduleFacets();}
 function setQueryField(field:AccountFilterField|'q'|'archived',value:string|readonly string[]){
  const query=clone(draft.value.query);if(['q','archived','date_from','date_to','plan'].includes(field))Object.assign(query,{[field]:value});else Object.assign(query.filters,{[field]:value});updateQuery(query);
 }
 function clearFilter(field:string){if(field==='date'){updateQuery({...draft.value.query,date_from:'',date_to:''});return;}setQueryField(field as AccountFilterField,field==='archived'?'0':['q','email','id'].includes(field)?'':[]);}
 function clearFilters(){if(creating.value)return;draft.value.source=null;draft.value.query=deps.adapter.normalize();matched.value=null;invalidate();clearError();saveDraft();scheduleFacets();}
 function facetLabel(group:string,value:string){return deps.callbacks.facetLabel?.(group,value)||value;}
 function filterOptions(key:AccountFilterKey):FacetOption[]{
  const fields=catalog.value?.query_schema?.fields,definition=Array.isArray(fields)?fields.map(record).find(field=>field.key===key):undefined;
  const configured=definition?.options??definition?.enum??definition?.values;
  const rows=facets.value[key]??(Array.isArray(configured)?configured:[]),found=new Map<string,FacetOption>();
  for(const entry of rows){const row=typeof entry==='object'&&entry?entry as FacetOption:{value:String(entry)};if(row.value)found.set(row.value,{...row,label:row.label||facetLabel(key==='token'?'account_token':key,row.value)});}
  if(key==='promotion')for(const value of promotionOffers)if(!found.has(value))found.set(value,{value,label:facetLabel(key,value)});
  for(const value of selectedValues(draft.value.query,key))if(!found.has(value))found.set(value,{value,label:facetLabel(key==='token'?'account_token':key,value)});
  return[...found.values()];
 }
 const chips=computed(()=>[...filterChips(draft.value.query,facetLabel),...(draft.value.query.q?[{key:'q',label:`搜索：${draft.value.query.q}`,removeLabel:'清除高级搜索',title:draft.value.query.q}]:[]),...(draft.value.query.archived!=='0'?[{key:'archived',label:draft.value.query.archived==='only'?'仅归档账号':'含归档账号',removeLabel:'清除归档筛选',title:''}]:[])]);
 function parameters():BulkRecord{const schema=operation.value?.parameter_schema;return schema?.timezone_offset_min||record(schema?.properties).timezone_offset_min?{timezone_offset_min:new Date().getTimezoneOffset()}:{};}
 async function pollSelection(){
  if(!selection.value||!visible||disposed)return;const id=bulkId(selection.value.id),currentEpoch=epoch;
  const result=await read<Selection>(`/selections/${encodeURIComponent(id)}?page_size=1`);
  if(disposed||currentEpoch!==epoch||selection.value?.id!==id)return;
  selection.value={...selection.value,...result};saveSelection();
 }
 async function initialize(){
  if(!visible||disposed)return;
  if(initializePromise)return initializePromise;if(initialized)return;
  loading.value=true;
  initializePromise=(async()=>{try{await loadCatalog();if(disposed||!visible)return;const currentEpoch=epoch;try{await loadFacets();}catch(failure){if(aborted(failure))return;if(currentEpoch===epoch)report(failure,'筛选选项读取失败：');}if(!disposed&&currentEpoch===epoch&&selection.value)await pollSelection();initialized=true;}catch(failure){if(!aborted(failure)&&!disposed)report(failure,'读取配置失败：');}finally{loading.value=false;initializePromise=null;}})();
  return initializePromise;
 }
 async function creationFailure(failure:unknown,currentEpoch:number){
  if(aborted(failure)||disposed||currentEpoch!==epoch)return;pendingCreation=null;creating.value=false;report(failure,'创建失败：');
  const detail=failure as BulkApiError;
  if(['config_revision_changed','selection_settings_mismatch'].includes(detail.code)){selection.value=null;saveSelection();try{await loadCatalog(true);}catch(reloadFailure){report(reloadFailure,'配置读取失败：');}if(!disposed&&currentEpoch===epoch)deps.callbacks.notify('配置已更新，请重新创建批次。');}
  else if(detail.code==='selection_consumed'&&detail.details?.existing_batch_id){existingBatchId.value=String(detail.details.existing_batch_id);deps.callbacks.notify(`该范围已用于批次 #${existingBatchId.value}`);}
  else if(detail.code==='selection_expired'){selection.value=null;saveSelection();}
 }
 async function advanceCreation(){
  const pending=pendingCreation;if(!pending||pending.epoch!==epoch||advancingEpoch===epoch||disposed||!visible)return;const currentEpoch=epoch;advancingEpoch=currentEpoch;
  try{
   if(selectionState.value==='preparing')return;
   const fixed=selection.value;
   if(!fixed||selectionState.value!=='ready')throw new BulkApiError(fixed?.error?.message||fixed?.error_detail?.message||'账号范围准备失败，请重试',0,fixed?.error_code||'selection_preparation_failed');
   if(Number(fixed.target_count??fixed.total_count)<=0)throw new BulkApiError('没有匹配账号，请调整筛选条件',0,'selection_empty');
   const op=operation.value;if(!op)throw new BulkApiError('没有可用的批量操作',0,'operation_unavailable');
   const body={name:draft.value.name,selection_id:bulkId(fixed.id),selection_revision:fixed.selection_revision,operation:{key:op.key,version:op.version||1},expected_config_revision:fixed.config_revision||configRevision.value,parameters:fixed.request_parameters||parameters(),execution:{max_concurrency:Number(draft.value.max_concurrency),start_paused:pending.paused}};
   const result=await deps.intents.submit('create','/batches',body);const batchId=bulkId(result.id||result.batch_id);
   if(disposed||currentEpoch!==epoch){deps.callbacks.notify(`原批次 #${batchId} 已创建${pending.paused?'并暂停':''}`);return;}
   selection.value=null;saveSelection();pendingCreation=null;creating.value=false;
   deps.callbacks.notify(!visible?`原批次 #${batchId} 已创建${pending.paused?'并暂停':''}`:pending.paused?'批次已创建并暂停，可在详情继续执行':'批次已受理，正在后台提交目标');if(visible)deps.callbacks.navigate('detail',{batch_id:batchId});
  }catch(failure){await creationFailure(failure,currentEpoch);}finally{pendingRevision.value++;if(advancingEpoch===currentEpoch)advancingEpoch=null;}
 }
 async function createBatch(paused=false){
  if(creating.value||recovering.value||disposed||!visible)return;clearError();
  const concurrency=Number(draft.value.max_concurrency);
  if(!Number.isInteger(concurrency)||concurrency<1||concurrency>concurrencyMax.value){report(new BulkApiError(`本批并发上限需为 1–${concurrencyMax.value} 的整数`,0,'invalid_concurrency',{},'max_concurrency'));return;}
  if(draft.value.name.length>120){report(new BulkApiError('批次名称最多 120 个字符',0,'invalid_name',{},'name'));return;}
  if(!operation.value){report(new BulkApiError('请先读取可用的批量操作',0,'operation_unavailable'));return;}
  if(hasOverrides(selection.value)){selection.value=null;saveSelection();}
  const currentEpoch=epoch;pendingCreation={epoch:currentEpoch,paused};creating.value=true;
  try{
   if(!['ready','preparing'].includes(selectionState.value)){
    const op=operation.value,body={operation:{key:op.key,version:op.version||1},source:clone(draft.value.source||{kind:'query',query:deps.adapter.normalize({...draft.value.query,limit:null})}),parameters:parameters(),expected_config_revision:configRevision.value};
    const result=await deps.intents.submit<Selection>('selection','/selections',body);
    if(disposed||currentEpoch!==epoch)return;selection.value={...result,request_parameters:body.parameters,config_revision:body.expected_config_revision};saveSelection();saveDraft();
   }
   if(selectionState.value==='preparing')await pollSelection();
   if(!disposed&&currentEpoch===epoch)await advanceCreation();
  }catch(failure){await creationFailure(failure,currentEpoch);}finally{pendingRevision.value++;}
 }
 async function refresh(force=false){
  if(disposed||!visible)return;if(refreshPromise?.epoch===epoch)return refreshPromise.promise;
  const currentEpoch=epoch,promise=(async()=>{const first=!initialized;if(first)await initialize();if(disposed||!visible||!initialized||currentEpoch!==epoch)return;try{if(force)await loadCatalog(true);if(!first){if(selection.value)await pollSelection();else await loadFacets();}if(currentEpoch===epoch)await advanceCreation();}catch(failure){if(!aborted(failure)&&currentEpoch===epoch){if(pendingCreation)await creationFailure(failure,currentEpoch);else report(failure,'读取账号范围失败：');}}})();
  refreshPromise={epoch:currentEpoch,promise};try{await promise;}finally{if(refreshPromise?.promise===promise)refreshPromise=null;}
 }
 function restoreSelectionRequest(body:BulkRecord,result:BulkRecord){
  const source=record(body.source),op=record(body.operation),query=deps.adapter.normalize(source.kind==='query'?record(source.query):{});
  const recovered={...defaultDraft(),operation_key:String(op.key||'plan_check'),query,source:source.kind==='query'?null:source};
  invalidate();restoreDraft(recovered,{...result,request_parameters:record(body.parameters),config_revision:body.expected_config_revision});
 }
 async function recover(){
  if(recovering.value||creating.value||disposed)return;recovering.value=true;clearError();const currentEpoch=epoch;
  try{
   const saved=deps.intents.pending()[0];if(!saved)return;const result=await deps.intents.recover(saved);
   if(disposed||currentEpoch!==epoch||!visible){deps.callbacks.notify(saved.path==='/batches'?`原批次 #${bulkId(result.id||result.batch_id)} 已创建`:'原请求回执已找回，当前草稿保留。');return;}
   if(saved.path==='/selections'){
    restoreSelectionRequest(saved.body,result);
    deps.callbacks.navigate('create');deps.callbacks.notify('已找回原账号范围，新批次使用配置页已保存的设置。');
   }else if(saved.path==='/batches'){selection.value=null;saveSelection();deps.callbacks.navigate('detail',{batch_id:bulkId(result.id||result.batch_id)});}
   else{const match=saved.path.match(/^\/batches\/(\d+)\//);if(match)deps.callbacks.navigate('detail',{batch_id:bulkId(match[1])});deps.callbacks.notify('原请求回执已找回。');}
  }catch(failure){report(failure,'找回请求失败：');}finally{recovering.value=false;pendingRevision.value++;}
 }
 onScopeDispose(()=>{disposed=true;epoch++;clearTimeout(facetTimer);reads.forEach(controller=>controller.abort());reads.clear();pendingCreation=null;});
 return{draft,selection,catalog,facets,matched,loading,creating,recovering,error,errorField,existingBatchId,operations,operation,configRevision,selectionState,needsRefresh,concurrencyMax,pendingCount,count,scopeLabel,summary,hint,availabilityWarning,chips,accountFilters,
  initialize,refresh,recover,restoreSelectionRequest,loadFacets,applySeed,setVisible,setDraftField,setOperation,setQueryField,clearFilter,clearFilters,filterOptions,createBatch,clearError};
}
