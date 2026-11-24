import {reactive} from 'vue';
import {createExtractApi} from '../../api/extract';
import {taskId} from '../../api/taskIds';
import {BulkMutationPendingError} from '../../api/bulkMutations';
import type {TaskId,ExtractApi,ExtractBatch,ExtractConfig,ExtractDeps,ExtractList,ExtractLoadOptions,ExtractQuery,ExtractReceipt,ExtractTask} from './contracts';
import {download,message,paymentUrl,selectedCsv} from './presentation';
const blankQuery=():ExtractQuery=>({page:1,size:20,provider:'',mode:'',status:'',query:'',batch:''});
const CACHE_MS=30000;
interface Inflight<T>{promise:Promise<T>;version:number}
export function createExtractWorkbench(input:ExtractDeps={}){
 const api=input.api||createExtractApi(input);
 const state=reactive({query:blankQuery(),items:[] as ExtractTask[],total:0,counts:{} as Record<string,number>,batches:[] as ExtractBatch[],batchTotal:0,batchPage:1,batchLoading:false,batchDetail:null as ExtractBatch|null,config:null as ExtractConfig|null,summary:null as Record<string,number>|null,loading:false,error:'',auxErrors:{config:'',summary:'',batches:'',detail:''},visible:input.visible!==false,selected:new Set<string>(),cancellingBatch:'',bulkBusy:false,receipt:null as ExtractReceipt|null});
 let dead=false,life=0,listVersion=0,auxVersion=0,detailVersion=0,configAt=0,batchesAt=0,batchesPage=0,failures=0;
 let timer:ReturnType<typeof setTimeout>|undefined,configRead:Inflight<ExtractConfig>|undefined,summaryRead:Inflight<Record<string,number>>|undefined;
 let listController:AbortController|undefined;
 const batchReads=new Map<number,Inflight<Awaited<ReturnType<ExtractApi['batches']>>>>(),detailReads=new Map<string,Inflight<{item:ExtractBatch}>>();
 const controllers=new Set<AbortController>();
 const active=()=>!dead&&state.visible&&!document.hidden;
 const valid=(epoch:number)=>epoch===life&&active();
 const notify=(text:string)=>input.notify?.(text);
 function controller(){const value=new AbortController();controllers.add(value);return value;}
 function clearTimer(){if(timer)clearTimeout(timer);timer=undefined;}
 function policy(){const p=state.config?.poll||{};const bounded=(v:unknown,fallback:number,max:number)=>Number.isFinite(Number(v))&&Number(v)>0?Math.min(max,Number(v))*1000:fallback;return{active:bounded(p.active_seconds,3000,60),idle:bounded(p.idle_seconds,15000,300),backoff:bounded(p.backoff_max_seconds,300000,1800)};}
 function schedule(retry=false){clearTimer();if(!active())return;const p=policy(),counts=state.counts,whole=state.batchDetail?.counts||{};const running=Number(counts.processing||whole.processing||0)>0;const waiting=Number(counts.awaiting_payment||whole.awaiting_payment||0)>0;const delay=retry?Math.min(p.backoff,p.idle*2**Math.min(10,Math.max(0,failures-1))):running?p.active:waiting?p.idle:0;if(delay)timer=setTimeout(()=>void load({quiet:true}),delay);}
 function readConfig(force:boolean,epoch:number){
  if(!force&&state.config&&Date.now()-configAt<CACHE_MS)return Promise.resolve(state.config);
  if(configRead)return configRead.promise;
  const version=++auxVersion,c=controller();
  const promise=api.config(c.signal).then(value=>{if(valid(epoch)&&configRead?.version===version){state.config=value;state.auxErrors.config='';configAt=Date.now();schedule(failures>0);}return value;}).catch(error=>{if(valid(epoch))state.auxErrors.config=message(error);throw error;}).finally(()=>{controllers.delete(c);if(configRead?.version===version)configRead=undefined;});
  configRead={version,promise};return promise;
 }
 function readSummary(epoch:number){if(summaryRead)return summaryRead.promise;const version=++auxVersion,c=controller();const promise=api.summary(c.signal).then(value=>{if(valid(epoch)){state.summary=value;state.auxErrors.summary='';}return value;}).catch(error=>{if(valid(epoch))state.auxErrors.summary=message(error);throw error;}).finally(()=>{controllers.delete(c);if(summaryRead?.version===version)summaryRead=undefined;});summaryRead={version,promise};return promise;}
 function readBatches(page:number,epoch:number){
  const pending=batchReads.get(page);
  if(pending)return pending.promise;
  const version=++auxVersion,c=controller();
  state.batchLoading=true;
  state.auxErrors.batches='';
  const current=()=>valid(epoch)&&page===state.batchPage&&batchReads.get(page)?.version===version;
  const promise=api.batches(page,c.signal).then(value=>{
   if(current()){
    state.batches=value.items;
    state.batchTotal=value.total;
    batchesPage=page;
    batchesAt=Date.now();
   }
   return value;
  }).catch(error=>{
   if(current())state.auxErrors.batches=message(error);
   throw error;
  }).finally(()=>{
   controllers.delete(c);
   if(current())state.batchLoading=false;
   if(batchReads.get(page)?.version===version)batchReads.delete(page);
  });
  batchReads.set(page,{version,promise});
  return promise;
 }
 async function loadBatchPage(page:number){
  if(!active()||state.batchLoading)return;
  const previous=state.batchPage,epoch=life;
  state.batchPage=page;
  try{
   await readBatches(page,epoch);
  }catch{
   // Keep the displayed options paired with their last successful page.
   if(valid(epoch)&&state.batchPage===page)state.batchPage=previous;
  }
 }
 function readDetail(id:string,epoch:number){const pending=detailReads.get(id);if(pending)return pending.promise;const version=++auxVersion,c=controller();const promise=api.batch(id,c.signal).finally(()=>{controllers.delete(c);if(detailReads.get(id)?.version===version)detailReads.delete(id);});detailReads.set(id,{version,promise});return promise;}
 async function auxiliaries(options:ExtractLoadOptions,epoch:number){
  void readConfig(!!options.force,epoch).catch(()=>{});void readSummary(epoch).catch(()=>{});
  const page=state.batchPage,id=state.query.batch,version=++detailVersion;
  const refresh=!!options.force||batchesPage!==page||Date.now()-batchesAt>=CACHE_MS;
  try{
   const rows=refresh?(await readBatches(page,epoch)).items:state.batches;
   if(!valid(epoch)||page!==state.batchPage||id!==state.query.batch||version!==detailVersion)return;
   if(!id){state.batchDetail=null;return;}
   const summary=!options.quiet||refresh?rows.find(row=>String(row.batch_id)===id):null;
   const value=summary|| (await readDetail(id,epoch)).item;
   if(valid(epoch)&&id===state.query.batch&&version===detailVersion){state.batchDetail=value;state.auxErrors.detail='';schedule(failures>0);}
  }catch(error){if(valid(epoch)&&id===state.query.batch&&page===state.batchPage)state.auxErrors.detail=message(error);}
 }
 async function load(options:ExtractLoadOptions={}){
  if(!active())return;clearTimer();const version=++listVersion,epoch=life,query={...state.query};listController?.abort();const c=controller();listController=c;state.loading=true;state.error='';
  void auxiliaries(options,epoch);
  try{const result:ExtractList=await api.tasks(query,c.signal);if(!valid(epoch)||version!==listVersion)return;state.items=result.items;state.total=result.total;state.counts=result.counts||{};state.query.page=result.page;for(const id of [...state.selected])if(!result.items.some(item=>String(item.task_id)===id))state.selected.delete(id);failures=0;input.onReady?.();schedule();}
  catch(error){if(valid(epoch)&&version===listVersion){state.error=message(error);failures++;schedule(true);}}
  finally{controllers.delete(c);if(valid(epoch)&&version===listVersion)state.loading=false;}
 }
 async function switchBatch(id:TaskId|''){Object.assign(state.query,blankQuery(),{batch:id?String(taskId(id)):''});state.batchDetail=null;state.selected.clear();detailVersion++;await load();}
 async function bulkAction(action:string){
  if(action==='clear'){state.selected.clear();return;}if(action==='export'){await exportRows(false);return;}if(state.bulkBusy)return;
  const rows=state.items.filter(item=>state.selected.has(String(item.task_id))),ids=rows.map(row=>row.task_id);if(!ids.length)return;
  state.bulkBusy=true;try{
   if(action==='links'){
    const candidates=rows.filter(row=>row.has_payment_entry||row.has_payment_link||row.has_qr);
    let skipped=rows.length-candidates.length;const lines:string[]=[];
    if(candidates.length){
     const result=await api.paymentEntries(candidates.map(row=>row.task_id));
     const entries=new Map(result.items.map(item=>[String(item.task_id),item]));
     for(const row of candidates){
      const item=entries.get(String(row.task_id)),entry=item?.status==='updated'?item.entry:undefined;
      const value=entry&&(paymentUrl(entry.payment_page_url)||paymentUrl(entry.payment_url)||entry.qr_data);
      if(value)lines.push(`${row.email||''}\t${value}`);else skipped++;
     }
    }
    if(lines.length){await (input.copyText?input.copyText(lines.join('\n')):navigator.clipboard.writeText(lines.join('\n')));notify(`已复制 ${lines.length} 条支付链接${skipped?`，跳过 ${skipped} 个`:''}`);}else notify('所选任务没有可复制的支付入口');return;
   }
   if(action!=='sync'&&action!=='sync_status')throw Error('不支持的批量操作');
   const result=await api.actionBulk(ids,'sync_status');state.receipt=result;
   let accepted=0,skipped=0,failed=0;
   for(const item of result.items){
    if(item.status==='updated'){accepted++;state.selected.delete(String(item.data?.task_id??item.key));}
    else if(item.status==='failed')failed++;else skipped++;
   }
   notify(`原单同步已入队：${accepted} 个${skipped?`，跳过 ${skipped} 个`:''}${failed?`，失败 ${failed} 个`:''}`);
   // 回执属于当前提交；后续列表读取失败不能把已确认的入队改成失败。
   await load({force:true});
  }catch(error){
   if(error instanceof BulkMutationPendingError){state.receipt={command_id:error.commandId,accepted:true};notify(error.message);}
   else state.error=message(error);
  }finally{state.bulkBusy=false;}
 }
 async function cancelBatch(options:{confirmed?:boolean}={}){
  const id=state.query.batch;if(!id||state.cancellingBatch)return;state.cancellingBatch=id;
  try{if(!options.confirmed&&!(await (input.confirm?input.confirm('确认取消当前整批尚未开始的排队任务？运行中与已完成任务保留，不受当前筛选和分页限制。'):window.confirm('确认取消当前整批尚未开始的排队任务？运行中与已完成任务保留。'))))return;
   const result=await api.cancel(id);if(result.ok===false)throw Error(result.error||'取消批次失败');state.receipt=result;notify(`批次 #${id}：已取消 ${result.cancelled||0} 个排队任务，跳过 ${result.skipped||0} 个${result.failed?`，失败 ${result.failed} 个，可再次处理剩余任务`:''}。`);await load({force:true});
  }catch(error){state.error=message(error);}finally{state.cancellingBatch='';}
 }
 async function exportRows(filtered=true){try{if(filtered){download(await api.export({...state.query}),'extract-workbench.csv');notify('已导出当前筛选结果（最多 5000 条）');return;}const rows=state.items.filter(item=>state.selected.has(String(item.task_id)));download(new Blob([selectedCsv(rows)],{type:'text/csv;charset=utf-8'}),'extract-workbench-selected.csv');}catch(error){state.error=message(error);}}
 function suspend(){life++;listVersion++;detailVersion++;clearTimer();controllers.forEach(c=>c.abort());controllers.clear();listController=undefined;configRead=undefined;summaryRead=undefined;batchReads.clear();detailReads.clear();state.batchPage=batchesPage||1;state.batchLoading=false;state.loading=false;}
 function setVisible(value:boolean){if(state.visible===value){if(value&&!state.loading)void load();return;}state.visible=value;if(value)void load();else suspend();}
 function onVisibility(){if(document.hidden)suspend();else if(state.visible)void load();}
 document.addEventListener('visibilitychange',onVisibility);
 function destroy(){dead=true;suspend();document.removeEventListener('visibilitychange',onVisibility);}
 return{state,load,loadBatchPage,setVisible,switchBatch,bulkAction,cancelBatch,exportRows,destroy};
}
