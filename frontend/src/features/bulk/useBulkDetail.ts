import {computed, onScopeDispose, ref, shallowRef, watch} from 'vue';
import {bulkId, type BulkDetailDependencies, type BulkNavigation, type BulkPageData, type BulkRecord} from './contracts';
import type {AccountQuerySpec} from '../accounts/queryAdapter';
import {object, countsOf, operationKey, operationNames, targetId} from './bulkDetailPresentation';

export interface BulkConfirmation {
  title: string; description: string; label: string; count: number; scopeLabel: string;
  path: string; intentScope: string; body: BulkRecord; navigationKey: string; kind: 'retry'|'control';
}
const retryStates = ['failed', 'partial_success', 'not_executed', 'cancelled'];
export function useBulkDetail(getNavigation: () => BulkNavigation, deps: BulkDetailDependencies, initialVisible=getNavigation().view==='detail') {
  const navigation = ref({...getNavigation()});
  const visible = ref(initialVisible);
  const detail = shallowRef<BulkRecord|null>(null), targets = shallowRef<BulkPageData|null>(null), report = shallowRef<BulkRecord|null>(null);
  const rounds = shallowRef<BulkRecord[]>([]), roundsCursor = ref<string|null>(null);
  const selected = ref(new Set<string>()), previousCursors = ref<string[]>([]), pendingRound = ref<string|null>(null);
  const loading = ref(false), targetsLoading = ref(false), reportLoading = ref(false), roundsLoading = ref(false), writing = ref(false);
  const error = ref(''), targetError = ref(''), reportError = ref(''), actionError = ref('');
  const confirmation = shallowRef<BulkConfirmation|null>(null);
  let disposed = false, reportLoadedAt = 0, roundsStarted = false;
  let detailPending:Promise<void>|null=null,detailPendingKey='';
  const requests = new Map<string, {generation: number; controller: AbortController}>();
  const scopeKey = () => `${navigation.value.batch_id || ''}:${navigation.value.round_id || ''}`;
  const targetKey = () => `${scopeKey()}:${navigation.value.result_state || ''}`;
  const navigationKey = () => `${targetKey()}:${navigation.value.cursor || ''}`;
  function begin(kind: string) {const old=requests.get(kind); old?.controller.abort();const request={generation:(old?.generation||0)+1,controller:new AbortController()}; requests.set(kind,request);return request;}
  function valid(kind: string, request: ReturnType<typeof begin>) {return !disposed && requests.get(kind) === request && !request.controller.signal.aborted;}
  function abort(...kinds: string[]) {for(const kind of kinds) {requests.get(kind)?.controller.abort();requests.delete(kind);}if(kinds.includes('detail')){detailPending=null;detailPendingKey='';}}
  function params() {const p=new URLSearchParams({view:navigation.value.round_id?'round':'current'});if(navigation.value.round_id)p.set('round_id',bulkId(navigation.value.round_id));return p;}
  function path(suffix='') {return `/batches/${bulkId(navigation.value.batch_id)}${suffix}`;}
  function message(cause: unknown) {return cause instanceof Error?cause.message:String(cause);}
  function mergeRounds(items: unknown) {
    const merged=new Map(rounds.value.map(round=>[bulkId(round.id),round]));
    if(Array.isArray(items))for(const round of items) {const row=object(round);merged.set(bulkId(row.id),row);}
    rounds.value=[...merged.values()].sort((a,b)=>Number(b.round_no)-Number(a.round_no));
  }
  const counts=computed(()=>countsOf(detail.value?.summary || detail.value?.counts));
  const controlState=computed(()=>object(detail.value?.control));
  const ended=computed(()=>['ended','completed'].includes(String(controlState.value.state || detail.value?.control_state)));
  const paused=computed(()=>Boolean(controlState.value.paused || detail.value?.is_paused));
  const hasPrevious=computed(()=>previousCursors.value.length>0);
  const nextCursor=computed(()=>targets.value?.page?.has_more ? targets.value.page.next_cursor || null:null);
  const needsPolling=computed(()=>visible.value && navigation.value.view==='detail' && (!ended.value || Boolean(pendingRound.value) || Boolean(controlState.value.pending)));
  const hasReport=computed(()=>Object.hasOwn(operationNames,operationKey(detail.value)));
  function controlDisabled(action: string) {
    if(!detail.value || writing.value || confirmation.value || ended.value || controlState.value.pending)return true;
    if(action==='pause')return paused.value;
    if(action==='resume')return !paused.value;
    return object(detail.value.capabilities || object(detail.value.operation).capabilities)[action]===false;
  }
  async function loadTargets() {
    if(!visible.value || navigation.value.view!=='detail')return;
    const request=begin('targets');targetsLoading.value=true;targetError.value='';
    try {const p=params();p.set('page_size','50');if(navigation.value.cursor)p.set('cursor',navigation.value.cursor);if(navigation.value.result_state)p.set('state[]',navigation.value.result_state);
      const data=await deps.api.request<BulkPageData>(`${path('/targets')}?${p}`,{signal:request.controller.signal});
      if(valid('targets',request)){for(const row of data.items)targetId(row);targets.value=data;}
    }catch(cause){if(valid('targets',request))targetError.value=message(cause);}finally{if(valid('targets',request))targetsLoading.value=false;}
  }
  async function refreshReport(force=false) {
    if(!visible.value || navigation.value.view!=='detail' || !hasReport.value || reportLoading.value)return;
    const complete=ended.value || object(detail.value?.selected_round).state==='completed';
    const finalFresh=complete && report.value?.phase==='completed' && report.value.summary_revision===detail.value?.summary_revision;
    if(!force && ((complete && finalFresh)||(!complete && (report.value||reportError.value) && deps.now()-reportLoadedAt<10000)))return;
    const request=begin('report');reportLoading.value=true;reportLoadedAt=deps.now();
    try {const data=await deps.api.request<BulkRecord>(`${path('/report')}?${params()}`,{signal:request.controller.signal});if(valid('report',request)){report.value=data;reportError.value='';reportLoadedAt=deps.now();}}
    catch(cause){if(valid('report',request))reportError.value=message(cause);}finally{if(valid('report',request))reportLoading.value=false;}
  }
  function refresh(force=false):Promise<void> {
    if(disposed || !visible.value || navigation.value.view!=='detail' || !navigation.value.batch_id)return Promise.resolve();
    if(detailPending&&detailPendingKey===scopeKey())return detailPending;
    detailPendingKey=scopeKey();
    const pending=readDetail(force).finally(()=>{if(detailPending===pending){detailPending=null;detailPendingKey='';}});
    detailPending=pending;return pending;
  }
  async function readDetail(force=false) {
    if(disposed || !visible.value || navigation.value.view!=='detail' || !navigation.value.batch_id)return;
    const request=begin('detail');loading.value=true;error.value='';
    try {const data=await deps.api.request<BulkRecord>(`${path()}?${params()}`,{signal:request.controller.signal});if(!valid('detail',request))return;
      const previousRevision=detail.value?.summary_revision;detail.value=data;mergeRounds(data.rounds_head);if(data.selected_round)mergeRounds([data.selected_round]);
      if(!roundsStarted)roundsCursor.value=typeof data.rounds_next_cursor==='string'?data.rounds_next_cursor:null;
      if(pendingRound.value){const pending=rounds.value.find(round=>round.id===pendingRound.value);if(pending && pending.state!=='preparing'){pendingRound.value=null;deps.callbacks.notify(pending.completion_reason==='cancelled_before_freeze'?'重跑准备已取消，当前结果归属不变。':'重跑名单已固定，可以切换查看新轮次。');}}
      const work:Promise<void>[]=[refreshReport(force)];if(force || !targets.value || previousRevision!==data.summary_revision)work.push(loadTargets());await Promise.all(work);
    }catch(cause){if(valid('detail',request))error.value=message(cause);}finally{if(valid('detail',request))loading.value=false;}
  }
  async function moreRounds() {
    if(!visible.value || navigation.value.view!=='detail' || !roundsCursor.value||roundsLoading.value)return;const request=begin('rounds');roundsLoading.value=true;
    try {const p=new URLSearchParams({page_size:'20',cursor:roundsCursor.value});const data=await deps.api.request<BulkPageData>(`${path('/rounds')}?${p}`,{signal:request.controller.signal});
      if(valid('rounds',request)){mergeRounds(data.items);roundsCursor.value=data.page.has_more?data.page.next_cursor||null:null;roundsStarted=true;}
    }catch(cause){if(valid('rounds',request))actionError.value=message(cause);}finally{if(valid('rounds',request))roundsLoading.value=false;}
  }
  function change(extra: Partial<BulkNavigation>, keepHistory=false) {
    if(!keepHistory)previousCursors.value=[];
    navigation.value={...navigation.value,...extra};deps.callbacks.updateNavigation(extra);
  }
  async function next() {if(!nextCursor.value||targetsLoading.value)return;previousCursors.value.push(navigation.value.cursor||'');change({cursor:nextCursor.value},true);}
  async function previous() {if(!hasPrevious.value||targetsLoading.value)return;change({cursor:previousCursors.value.pop()||''},true);}
  async function first() {change({cursor:''});}
  async function setFilter(state: string) {change({result_state:state,cursor:''});}
  async function setRound(id: string) {change({round_id:id==='current'?'':bulkId(id),cursor:''});}
  function toggleTarget(id: string, checked: boolean) {const next=new Set(selected.value);checked?next.add(bulkId(id)):next.delete(id);selected.value=next;}
  function selectPage(checked: boolean) {for(const row of targets.value?.items||[])toggleTarget(targetId(row),checked);}
  function clearSelection() {selected.value=new Set();}
  function retryCount(choice: string) {return (choice==='unsuccessful'?retryStates:[choice]).reduce((total,state)=>total+(counts.value[state]||0),0);}
  function cancelConfirmation() {confirmation.value=null;}
  async function execute(intent: BulkConfirmation) {
    if(writing.value || disposed || !visible.value || navigation.value.view!=='detail' || intent.navigationKey!==navigationKey())return;
    writing.value=true;actionError.value='';confirmation.value=null;
    try {const result=await deps.intents.submit<BulkRecord>(intent.intentScope,intent.path,intent.body);
      deps.callbacks.notify(intent.kind==='retry'?'重跑已受理，正在按固定时点的结果准备新轮次。':'控制请求已受理，正在读取批次最新状态。');
      if(disposed || intent.navigationKey!==navigationKey())return;
      if(intent.kind==='retry'){pendingRound.value=bulkId(result.round_id||result.id);clearSelection();}
      await refresh(true);
    }catch(cause){if(!disposed && intent.navigationKey===navigationKey()){actionError.value=message(cause);const code=object(cause).code;if(['control_revision_conflict','control_revision_changed'].includes(String(code)))await refresh(true);}}
    finally{writing.value=false;}
  }
  async function confirm() {const intent=confirmation.value;if(intent)await execute(intent);}
  async function retry(checked=false, choice='failed') {
    if(!detail.value||writing.value||confirmation.value||!retryStates.includes(choice)&&choice!=='unsuccessful')return;
    const ids=[...selected.value],amount=checked?ids.length:retryCount(choice);if(!amount)return;
    const batch=bulkId(navigation.value.batch_id),round=navigation.value.round_id?bulkId(navigation.value.round_id):null;
    const intent:BulkConfirmation={title:'确认重跑',description:`将在当前批次下新建一轮，重跑 ${amount} 个账号；不会覆盖历史轮次。`,label:`重跑 ${amount} 个`,count:amount,scopeLabel:round?'当前轮':'当前结果',path:`/batches/${batch}/rounds`,intentScope:`retry:${batch}`,navigationKey:navigationKey(),kind:'retry',body:{source:{view:round?'round':'current',round_id:round,observed_summary_revision:detail.value.summary_revision,observed_target_count:amount},selection:checked?{kind:'targets',target_ids:ids}:{kind:'result_filter',states:choice==='unsuccessful'?[...retryStates]:[choice]},retry_mode:'automatic'}};
    if(amount>=10||choice==='unsuccessful')confirmation.value=intent;else await execute(intent);
  }
  async function control(action: string) {
    if(!['pause','resume','cancel_not_started','request_stop'].includes(action)||controlDisabled(action))return;
    const reversible=['pause','resume'].includes(action),stop=action==='request_stop',batch=bulkId(navigation.value.batch_id),round=navigation.value.round_id?bulkId(navigation.value.round_id):null;
    const amount=(stop?['running','waiting']:['pending_submit','waiting_account','queued','waiting']).reduce((total,key)=>total+(counts.value[key]||0),0);
    const intent:BulkConfirmation={title:stop?'停止正在执行':'取消排队账号',description:stop?'已开始执行的账号会收到协作停止请求，正在收尾的步骤会完成，不会立即强制中断。':'尚未开始的目标会取消；已开始账号链的必要步骤会继续收尾。',label:stop?'停止执行':'取消排队',count:amount,scopeLabel:!reversible&&round?'当前轮':'整个批次',path:`/batches/${batch}/control`,intentScope:`control:${batch}:${action}`,navigationKey:navigationKey(),kind:'control',body:{action,expected_control_revision:controlState.value.revision??detail.value?.control_revision,scope:!reversible&&round?{kind:'round',round_id:round}:{kind:'batch'}}};
    if(reversible)await execute(intent);else confirmation.value=intent;
  }
  function copyBatch(fixed: boolean) {if(!detail.value)return;const query=object(detail.value.selection_summary).query||detail.value.query_spec||object(detail.value.selection).query_spec;if(!fixed&&!query)return;deps.callbacks.copyBatch?.((query||{}) as AccountQuerySpec,fixed?{kind:'batch_targets',batch_id:bulkId(navigation.value.batch_id),selection:{kind:'all'}}:null,operationKey(detail.value));}
  function setVisible(value: boolean) {visible.value=value;if(!value){abort('detail','targets','report','rounds');loading.value=false;targetsLoading.value=false;reportLoading.value=false;roundsLoading.value=false;confirmation.value=null;}}
  watch(getNavigation, value=>{if(JSON.stringify(value)!==JSON.stringify(navigation.value)){previousCursors.value=[];navigation.value={...value};}}, {deep:true,flush:'sync'});
  watch(()=>navigation.value.view,value=>{if(value!=='detail')setVisible(false);},{flush:'sync'});
  watch(()=>[scopeKey(),targetKey(),navigation.value.cursor||''],(current,old)=>{
    confirmation.value=null;actionError.value='';
    if(!old||current[0]!==old[0]){abort('detail','targets','report','rounds');detail.value=null;targets.value=null;report.value=null;rounds.value=[];roundsCursor.value=null;roundsStarted=false;reportLoadedAt=0;reportError.value='';targetError.value='';loading.value=false;targetsLoading.value=false;reportLoading.value=false;roundsLoading.value=false;clearSelection();previousCursors.value=[];pendingRound.value=null;void refresh();}
    else {if(current[1]!==old[1]){clearSelection();previousCursors.value=[];}targets.value=null;void loadTargets();}
  },{immediate:true,flush:'sync'});
  onScopeDispose(()=>{disposed=true;abort('detail','targets','report','rounds');confirmation.value=null;});
  return {navigation,detail,targets,report,rounds,roundsCursor,selected,pendingRound,loading,targetsLoading,reportLoading,roundsLoading,writing,error,targetError,reportError,actionError,confirmation,counts,ended,paused,needsPolling,hasReport,hasPrevious,nextCursor,controlDisabled,refresh,loadTargets,refreshReport,moreRounds,next,previous,first,setFilter,setRound,toggleTarget,selectPage,clearSelection,retryCount,retry,control,confirm,cancelConfirmation,copyBatch,setVisible};
}
