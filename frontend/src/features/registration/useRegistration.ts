import {computed,getCurrentInstance,onBeforeUnmount,reactive,ref} from 'vue';
import {isAbort} from '../../api/client';
import {taskId} from '../../api/taskIds';
import {createRegistrationApi,type RegistrationId,type RegistrationJob,type RegistrationSummary} from '../../api/registration';
import type {RegistrationAction,RegistrationDeps,RegistrationLoadOptions,RegistrationQuery,RegistrationState} from './contracts';

const queuedStatuses=['pending','queued','waiting'];
const runningStatuses=['running','stopping'];
const activeStatuses=[...queuedStatuses,...runningStatuses];
const terminalStatuses=['success','partial_success','failed','stopped','cancelled','interrupted','request_unknown','manual_reconcile','attention_required','password_confirmation_pending','unsupported','deactivated'];
const batchRetryStatuses=['failed','partial_success','interrupted','request_unknown','manual_reconcile','attention_required'];
const metadataCacheMs=10000;
type BatchAction = 'stopBatch' | 'cancelBatch' | 'retryBatch';
const emptyQuery=():RegistrationQuery=>({page:1,page_size:20,status:'',id:'',email:'',email_source:'',proxy:'',error:'',date_from:'',date_to:''});
const message=(error:unknown)=>error instanceof Error?error.message:'请求失败';
const batchString=(value:unknown)=>value==null?'':String(value).trim();
const jobSegment=(id:RegistrationId)=>encodeURIComponent(String(taskId(id)));
const emptyDetail=()=>({id:null as RegistrationId|null,job:null as any,log:'',debug:null as any,diagnostics:null as any,loading:false,error:'',comparison:null as any,compareError:'',comparing:false});

export function useRegistration(deps:RegistrationDeps){
  const api=deps.api||createRegistrationApi(),visible=ref(Boolean(deps.visible)),docVisible=ref(!document.hidden);
  let disposed=false;
  const active=computed(()=>visible.value&&docVisible.value&&!disposed);
  const state=reactive<RegistrationState&{
    query:RegistrationQuery;batchId:string;batchRefreshGeneration:number;statusCounts:Record<string,number>;facets:Record<string,any>;
    creating:boolean;pendingActions:Record<string,boolean>;lastCreate:any;lastAction:any;
    detail:ReturnType<typeof emptyDetail>;metaError:string;
  }>({jobs:[],total:0,batch:null,batches:[],meta:null,summary:null,view:deps.view||'launch',loading:false,error:'',receipt:null,
    query:emptyQuery(),batchId:'',batchRefreshGeneration:0,statusCounts:{},facets:{},creating:false,pendingActions:{},lastCreate:null,lastAction:null,detail:emptyDetail(),metaError:''});
  const creating=computed(()=>state.creating);
  const registrationUnavailable=computed(()=>{
    const feature=state.meta?.capabilities?.features?.register;
    if(state.metaError)return state.metaError;
    if(!state.meta)return state.metaError||'注册资格未确认，请刷新后重试';
    return feature?.enabled===true?'':String(feature?.reason||'注册资格未确认，请刷新后重试');
  });
  const notify=(text:string)=>deps.notify?.(text);
  let readVersion=0,refreshGeneration=0,summaryVersion=0,metaVersion=0,detailVersion=0;
  let loadedScopeSignature='';
  let jobsTimer:number|undefined,summaryTimer:number|undefined,detailTimer:number|undefined;
  let detailLoaded=false;
  let read:{version:number;signature:string;promise:Promise<void>;controller:AbortController}|undefined;
  let summaryRead:{version:number;promise:Promise<void>;controller:AbortController}|undefined;
  let metaRead:{version:number;promise:Promise<void>;controller:AbortController}|undefined;
  let detailController:AbortController|undefined,compareController:AbortController|undefined;
  let facetsSignature='',facetsAt=0,metaAt=0,metadataDirty=true;
  let createFlight:Promise<Record<string,any>>|undefined;
  const actionFlights=new Map<string,Promise<Record<string,any>>>();
  let actionHold=0;
  const detailActive=()=>!disposed&&docVisible.value&&state.detail.id!==null;
  const detailValid=(version:number,id:RegistrationId)=>detailActive()&&version===detailVersion&&String(state.detail.id)===String(id);

  function invalidateJobs(){
    readVersion++;read?.controller.abort();read=undefined;state.loading=false;
  }
  function invalidatePageReads(){
    invalidateJobs();summaryVersion++;summaryRead?.controller.abort();summaryRead=undefined;
    metaVersion++;metaRead?.controller.abort();metaRead=undefined;
  }
  function clearPageTimers(){window.clearInterval(jobsTimer);window.clearInterval(summaryTimer);jobsTimer=summaryTimer=undefined;}
  function shouldPollJobs(){
    if(!active.value)return false;
    if(actionHold>0)return false;
    if(state.view==='tasks')return true;
    const batch=state.batch;
    if(!batch||String(batch.batch_id)!==state.batchId||batch.projection_delayed)return true;
    return activeStatuses.some(status=>Number(batch.status_counts?.[status]||0)>0)
      ||batch.items.some(job=>activeStatuses.includes(String(job.status||'')));
  }
  function mergeQuery(options:RegistrationLoadOptions){
    for(const key of Object.keys(emptyQuery()) as (keyof RegistrationQuery)[]){
      const value=options[key];
      if(value===undefined)continue;
      if(key==='page'||key==='page_size'){
        const number=Number(value);
        if(Number.isSafeInteger(number)&&number>0)state.query[key]=key==='page_size'?Math.min(number,500):number;
      }else state.query[key]=String(value);
    }
    if(options.progress_batch_id!==undefined){
      const next=batchString(options.progress_batch_id);
      if(next!==state.batchId){state.batchId=next;state.batch=null;}
    }
  }
  function load(options:RegistrationLoadOptions={},background=false):Promise<void>{
    mergeQuery(options);
    if(!active.value||(options.automatic&&!shouldPollJobs()))return Promise.resolve();
    const signature=JSON.stringify({view:state.view,batchId:state.batchId,...state.query});
    if((options.automatic||options.coalesce)&&read?.signature===signature)return read.promise;
    read?.controller.abort();
    const version=++readVersion,controller=new AbortController(),requestView=state.view;
    if(!options.automatic)refreshGeneration++;
    const generation=refreshGeneration;
    const silentRefresh=Boolean((options.automatic||background)&&loadedScopeSignature===signature);
    state.loading=!silentRefresh;
    if(!options.automatic&&!background)state.error='';
    const valid=()=>active.value&&version===readVersion&&requestView===state.view;
    const promise=(async()=>{
      try{
        for(let correction=0;correction<2;correction++){
          const params:Record<string,string|number>={paged:1,...state.query,view:requestView==='tasks'?'table':'batch',
            progress_batch_id:state.batchId,refresh_generation:generation};
          // 轮询只要轻量列表；进度明细按需从 /api/jobs/<id>/progress 读取。
          if(requestView==='launch'||options.automatic)params.progress_detail=0;
          if(requestView==='tasks'&&options.automatic&&facetsSignature===signature&&Date.now()-facetsAt<30000)params.include_facets=0;
          const result=await api.jobs(params,controller.signal);
          if(!valid())return;
          if(Object.prototype.hasOwnProperty.call(result,'status_counts'))state.statusCounts=result.status_counts||{};
          if(requestView==='launch'){
            state.batches=result.progress_batches||[];
            const batch=result.progress_batch||null;
            if(!batch&&state.batchId){
              const fallback=batchString(state.batches[0]?.batch_id);
              if(fallback!==state.batchId){
                state.batchId=fallback;state.batch=null;
                if(fallback&&!correction)continue;
              }
            }
            if(!state.batchId&&batch?.batch_id)state.batchId=batchString(batch.batch_id);
            state.batch=batch;
            state.batchRefreshGeneration=generation;
          }else{
            state.total=Math.max(0,Number(result.total??result.items?.length??0)||0);
            if(Object.prototype.hasOwnProperty.call(result,'facets')){
              state.facets=result.facets||{};facetsSignature=signature;facetsAt=Date.now();
            }
            const pages=Math.max(1,Math.ceil(state.total/state.query.page_size));
            if(state.query.page>pages){
              state.query.page=pages;
              if(!correction)continue;
              throw new Error('列表范围已变化，请刷新后重试');
            }
            state.jobs=result.items||[];
          }
          state.error='';
          loadedScopeSignature=JSON.stringify({view:requestView,batchId:state.batchId,...state.query});
          return;
        }
      }catch(error){if(valid()&&!isAbort(error))state.error=message(error);}
      finally{if(version===readVersion){state.loading=false;read=undefined;}}
    })();
    read={version,signature,promise,controller};
    return promise;
  }
  function setBatch(id:string){return load({progress_batch_id:batchString(id)});}
  function readBatchProgress(id:RegistrationId,signal:AbortSignal){return api.progress(taskId(id),signal);}
  function updateQuery(patch:Partial<RegistrationQuery>){return load({...patch,page:patch.page??1});}
  function setPage(page:number){return load({page});}
  function setSize(size:number){return load({page:1,page_size:size});}

  function applySummary(value:RegistrationSummary){state.summary=value;}
  function renderEmailSupply(value:RegistrationSummary['email_supply']){state.summary={...(state.summary||{}),email_supply:value||{}};}
  function loadSummary():Promise<void>{
    if(!active.value)return Promise.resolve();
    summaryRead?.controller.abort();
    const version=++summaryVersion,controller=new AbortController();
    const promise=(async()=>{
      try{const result=await api.summary(controller.signal);if(version===summaryVersion&&active.value)applySummary(result);}
      catch(error){if(version===summaryVersion&&active.value&&!isAbort(error))renderEmailSupply({status:'error',reason:'本地库存读取失败，请稍后重试'});}
      finally{if(version===summaryVersion)summaryRead=undefined;}
    })();
    summaryRead={version,promise,controller};return promise;
  }
  function ensureMeta(force=false):Promise<void>{
    if(metaRead)return metaRead.promise;
    if(force)metadataDirty=true;
    if(!active.value)return Promise.resolve();
    if(!metadataDirty&&state.meta&&Date.now()-metaAt<metadataCacheMs)return Promise.resolve();
    const version=++metaVersion,controller=new AbortController();
    const promise=(async()=>{
      try{
        const value:any=await api.metadata(controller.signal);
        if(version!==metaVersion||!active.value)return;
        state.meta={...value,sources:Array.isArray(value.sources)?value.sources:[]};state.metaError='';metaAt=Date.now();metadataDirty=false;
      }catch(error){
        if(version===metaVersion&&active.value&&!isAbort(error)){
          const detail=message(error);
          state.metaError=/[\u3400-\u9fff]/.test(detail)?detail:`邮箱来源读取失败，请稍后重试${detail?`（${detail}）`:''}`;
        }
      }
      finally{if(version===metaVersion)metaRead=undefined;}
    })();
    metaRead={version,promise,controller};return promise;
  }
  function startPageReads(refreshMeta=false){
    clearPageTimers();
    if(!active.value)return;
    void ensureMeta(refreshMeta);void load({coalesce:true},true);void loadSummary();
    jobsTimer=window.setInterval(()=>{void load({automatic:true});},5000);
    summaryTimer=window.setInterval(()=>{if(!summaryRead)void loadSummary();void ensureMeta(true);},10000);
  }
  function setVisible(value:boolean){
    if(visible.value===value)return;
    visible.value=value;
    if(!value){clearPageTimers();invalidatePageReads();}
    else startPageReads(true);
  }
  function setView(value:'launch'|'tasks'){
    if(!['launch','tasks'].includes(value)||state.view===value)return;
    state.view=value;invalidateJobs();void load({coalesce:true});
  }

  function mutationReceipt(value:Record<string,any>,fallback='已受理'){
    const detail=value.message||value.warning||(value.started_count!=null?`已提交 ${value.started_count} 个失败任务`
      :value.deleted_count!=null?`已删除 ${value.deleted_count} 个任务`
      :value.cancelled!=null?`已取消 ${value.cancelled} 个排队任务`:fallback);
    const skipped=Array.isArray(value.skipped)?value.skipped.length:0;
    state.receipt={tone:value.warning?'warning':'success',message:String(detail)+(skipped?`，跳过 ${skipped} 个`:'')};
    notify(state.receipt.message);
  }
  function selectAcceptedBatch(receipt:Record<string,any>){
    const id=batchString(receipt.jobs?.[0]?.batch_id||receipt.job?.batch_id||receipt.batch_id);
    if(id){state.batchId=id;state.batch=null;}
  }
  function action(path:string,payload:unknown={}):Promise<Record<string,any>>{
    const key=JSON.stringify([path,payload]);
    const current=actionFlights.get(key);if(current)return current;
    state.pendingActions[key]=true;
    actionHold+=1;invalidatePageReads();
    const promise=(async()=>{
      try{
        const receipt=await api.action(path,payload);state.lastAction=receipt;selectAcceptedBatch(receipt);
        mutationReceipt(receipt);
        if(/\/delete(?:-bulk)?$/.test(path)&&state.detail.id!==null){
          const deleted=Array.isArray(receipt.deleted)?receipt.deleted:receipt.deleted===true?[path.split('/').at(-2)]:[];
          if(deleted.some((id:RegistrationId)=>String(id)===String(state.detail.id)))closeDetail();
        }
        void load();
        if(state.detail.id!==null)void refreshDetail();
        return receipt;
      }catch(error){state.receipt={tone:'danger',message:message(error)};notify(state.receipt.message);throw error;}
      finally{actionFlights.delete(key);delete state.pendingActions[key];}
    })();
    actionFlights.set(key,promise);return promise;
  }
  function create(payload:{count:number;workers:number;email_source:string;debug_enabled:boolean}):Promise<Record<string,any>>{
    if(createFlight)return createFlight;
    if(registrationUnavailable.value){
      const reason=registrationUnavailable.value;
      state.receipt={tone:'warning',message:reason};notify(reason);
      return Promise.reject(new Error(reason));
    }
    if(!Number.isSafeInteger(payload.count)||payload.count<1||!Number.isSafeInteger(payload.workers)||payload.workers<1){
      return Promise.reject(new Error('注册数量与并发线程数必须为有效的正整数'));
    }
    state.creating=true;
    createFlight=(async()=>{
      try{
        const receipt=await api.create({...payload});state.lastCreate=receipt;selectAcceptedBatch(receipt);
        mutationReceipt(receipt,`已提交 ${receipt.submitted||0} 个任务`);
        void load();return receipt;
      }catch(error){state.receipt={tone:'danger',message:message(error)};notify(state.receipt.message);throw error;}
      finally{state.creating=false;createFlight=undefined;}
    })();
    return createFlight;
  }
  function batchCandidates(kind:BatchAction) {
    const items=state.batch?.items||[];
    const statusOf=(row:RegistrationJob)=>String(row.display_status||row.status||'');
    if(kind==='stopBatch')return items.filter(row=>runningStatuses.includes(statusOf(row)));
    if(kind==='cancelBatch')return items.filter(row=>queuedStatuses.includes(statusOf(row)));
    return items.filter(row=>{
      const rawStatus=String(row.status||'');
      if(rawStatus==='cancelled'||rawStatus==='stopped')return false;
      return batchRetryStatuses.includes(statusOf(row))&&row.retryable;
    });
  }
  const batchActions=computed(()=>({
    stopBatch:Boolean(state.batchId)&&batchCandidates('stopBatch').length>0,
    cancelBatch:Boolean(state.batchId)&&batchCandidates('cancelBatch').length>0,
    retryBatch:batchCandidates('retryBatch').length>0,
  }));

  async function executeAction(kind:RegistrationAction,job?:RegistrationJob,selected:RegistrationId[]=[],debug=false){
    const candidates=kind==='stopBatch'||kind==='cancelBatch'||kind==='retryBatch'?batchCandidates(kind):[];
    const ids=kind==='retryBulk'||kind==='deleteBulk'?selected.map(id=>taskId(id)):candidates.map(row=>taskId(row.id));
    if(['stopBatch','cancelBatch','retryBatch','retryBulk','deleteBulk'].includes(kind)&&!ids.length){notify('当前没有可操作的任务');return null;}
    if(['stopBatch','cancelBatch'].includes(kind)&&!state.batchId)return null;
    if(kind==='retry'&&!job?.retryable){notify('该任务当前不可重试');return null;}
    if(['stop','delete','retry'].includes(kind)&&!job)throw new Error('任务不存在');
    const names:Record<RegistrationAction,string>={cancelAll:'取消所有排队任务',stopBatch:`停止当前批次的 ${ids.length} 个运行中任务`,
      cancelBatch:`取消当前批次的 ${ids.length} 个排队任务`,retryBatch:`重跑当前批次的 ${ids.length} 个失败任务`,
      stop:`停止任务 #${job?.id}`,delete:`删除任务 #${job?.id} 与对应日志`,retry:`${job?.retry_label||'重试'}任务 #${job?.id}`,
      deleteBulk:`删除选中的 ${ids.length} 个任务与对应日志`,retryBulk:`重试选中的 ${ids.length} 个任务`};
    const retryExplanation=kind==='retry'&&job?.retry_action==='codex'?'仅补跑 Codex 授权'
      :kind==='retry'&&job?.retry_action==='twofa'?'重新登录检查并补齐 Authenticator 2FA'
      :kind==='retry'&&job?.retry_action==='registration_resume'?'使用已保存账号密码继续邮箱验证'
      :'有原邮箱则复用，没有原邮箱则重新领取；已创建账号的任务按缺失步骤补跑，不能重试的由后端校验';
    const explain=kind==='retry'||kind==='retryBulk'||kind==='retryBatch'
      ?`\n${retryExplanation}。原任务记录和日志会保留。`
      :kind==='stop'||kind==='stopBatch'?'\n任务会在当前步骤检查点退出。'
      :kind==='cancelAll'||kind==='cancelBatch'?'\n运行中的任务不受影响。':'';
    const batch=encodeURIComponent(state.batchId);
    const jobId=job?jobSegment(job.id):'';
    if(!await (deps.confirm?deps.confirm(`确定${names[kind]}吗？${explain}`):window.confirm(`确定${names[kind]}吗？${explain}`)))return null;
    const routes:Record<RegistrationAction,[string,unknown]>={
      cancelAll:['/api/jobs/cancel-pending',{}],stopBatch:[`/api/jobs/batches/${batch}/stop`,{}],cancelBatch:[`/api/jobs/batches/${batch}/cancel`,{}],
      retryBatch:['/api/jobs/retry-bulk',{job_ids:ids,debug_enabled:debug}],stop:[`/api/jobs/${jobId}/stop`,{}],
      delete:[`/api/jobs/${jobId}/delete`,{}],retry:[`/api/jobs/${jobId}/retry`,{debug_enabled:debug}],
      deleteBulk:['/api/jobs/delete-bulk',{job_ids:ids}],retryBulk:['/api/jobs/retry-bulk',{job_ids:ids,debug_enabled:debug}]};
    return action(...routes[kind]);
  }

  function invalidateDetail(){
    detailVersion++;detailController?.abort();compareController?.abort();
    detailController=compareController=undefined;window.clearTimeout(detailTimer);detailTimer=undefined;
    state.detail.loading=false;state.detail.comparing=false;
  }
  async function refreshDetail(silent=detailLoaded,resetError=false){
    if(!detailActive())return;
    detailController?.abort();window.clearTimeout(detailTimer);
    const id=state.detail.id!,version=++detailVersion,controller=new AbortController();
    detailController=controller;
    if(!silent)state.detail.loading=true;
    if(resetError)state.detail.error='';
    const valid=()=>detailValid(version,id);
    try{
      const result=await api.log(id,controller.signal);if(!valid())return;
      state.detail.job=result.job||null;state.detail.log=String(result.log||'');
      const debug=await api.debug(id,controller.signal);if(!valid())return;
      state.detail.debug=debug?.enabled?debug:null;
      if(!debug?.enabled){const diagnostics=await api.diagnostics(id,controller.signal);if(!valid())return;state.detail.diagnostics=diagnostics;}
      else state.detail.diagnostics=null;
      detailLoaded=true;
      state.detail.error='';
    }catch(error){if(valid()&&!isAbort(error))state.detail.error=message(error);}
    finally{
      if(valid()){
        state.detail.loading=false;
        if(!terminalStatuses.includes(String(state.detail.job?.status||'')))detailTimer=window.setTimeout(()=>void refreshDetail(),2000);
      }
    }
  }
  function openLog(id:RegistrationId,stepId?:string|null){
    const exact=taskId(id),job=[...state.jobs,...(state.batch?.items||[])].find(row=>String(row.id)===String(exact));
    if(job?.operation_task_id&&deps.openTask){deps.openTask(job.operation_task_id,job.operation_run_id||null,stepId||null);return;}
    invalidateDetail();detailLoaded=false;state.detail={...emptyDetail(),id:exact};
    void refreshDetail(false,true);
  }
  function closeDetail(){invalidateDetail();detailLoaded=false;state.detail=emptyDetail();}
  async function compare(id:RegistrationId){
    const exact=taskId(id);
    if(!detailValid(detailVersion,exact))return null;
    compareController?.abort();const controller=new AbortController();compareController=controller;
    const valid=()=>detailActive()&&compareController===controller&&!controller.signal.aborted&&String(state.detail.id)===String(exact);
    state.detail.comparing=true;state.detail.compareError='';
    try{
      const value=await api.compare(exact,controller.signal);
      if(!valid())return null;
      state.detail.comparison=value;return value;
    }catch(error){
      if(valid()&&!isAbort(error)){state.detail.compareError=message(error);throw error;}
      return null;
    }finally{if(valid()){state.detail.comparing=false;compareController=undefined;}}
  }
  function visibilityChanged(){
    docVisible.value=!document.hidden;
    if(!docVisible.value){clearPageTimers();invalidatePageReads();invalidateDetail();}
    else{startPageReads(true);if(state.detail.id!==null)void refreshDetail();}
  }
  function dispose(){
    disposed=true;clearPageTimers();invalidatePageReads();invalidateDetail();
    document.removeEventListener('visibilitychange',visibilityChanged);
  }
  document.addEventListener('visibilitychange',visibilityChanged);
  if(getCurrentInstance())onBeforeUnmount(dispose);
  return {state,active,creating,registrationUnavailable,ensureMeta,load,loadSummary,renderEmailSupply,applySummary,setVisible,setView,
    setBatch,updateQuery,setPage,setSize,shouldPollJobs,create,action,executeAction,compare,openLog,refreshDetail,closeDetail,notify,
    terminalStatuses,activeStatuses,batchActions,readBatchProgress,dispose};
}
