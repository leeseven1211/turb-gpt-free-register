<script setup lang="ts">
import {computed,nextTick,onBeforeUnmount,onMounted,ref,shallowRef,watch} from 'vue';
import BulkList from './BulkList.vue';
import BulkCreate from './BulkCreate.vue';
import BulkDetail from './BulkDetail.vue';
import {normalizeBulkNavigation} from './navigation';
import {bulkId,type BulkDraft,type BulkIntentClient,type BulkIntentRecord,type BulkNavigation,type BulkPageDependencies,type BulkRecord,type BulkSliceCallbacks} from './contracts';
import type {AccountQuerySpec} from '../accounts/queryAdapter';
const props=defineProps<{deps:BulkPageDependencies;initialNavigation?:BulkNavigation}>();
const navigation=shallowRef(normalizeBulkNavigation(props.initialNavigation));
const active=ref(false),hostVisible=ref(false),error=ref(''),notice=ref(''),recovering=ref(false),pendingRevision=ref(0);
const seed=shallowRef<BulkDraft|null>(null);
const list=ref<InstanceType<typeof BulkList>|null>(null),create=ref<InstanceType<typeof BulkCreate>|null>(null),detail=ref<InstanceType<typeof BulkDetail>|null>(null);
let disposed=false,navigationEpoch=0,visibilityEpoch=0,lastVisible=false,timer:ReturnType<typeof setTimeout>|undefined,refreshing:Promise<void>|null=null,refreshKey='',focusReport=false;
const visible=computed(()=>active.value&&hostVisible.value);
const callbacks:BulkSliceCallbacks={...props.deps.callbacks,navigate:(view,extra,focus)=>{void navigate(view,extra,focus);},updateNavigation:extra=>{void updateNavigation(extra);},
 notify:message=>{notice.value=message;pendingRevision.value++;props.deps.callbacks.notify(message);},
 copyBatch:(query,source,operationKey)=>{void openDraft(query,source,operationKey);}};
const intents:BulkIntentClient={
 pending:()=>props.deps.intents.pending(),
 submit:async<T=BulkRecord>(scope:string,path:string,body:BulkRecord)=>{try{return await props.deps.intents.submit<T>(scope,path,body);}finally{pendingRevision.value++;}},
 recover:async<T=BulkRecord>(record:BulkIntentRecord)=>{try{return await props.deps.intents.recover<T>(record);}finally{pendingRevision.value++;}},
};
const listDeps={api:props.deps.api,callbacks};
const createDeps={...props.deps,intents,callbacks};
const detailDeps={api:props.deps.api,intents,callbacks,now:props.deps.now};
const pending=computed(()=>{pendingRevision.value;try{return props.deps.intents.pending();}catch{return[];}});
const delay=computed(()=>!visible.value?0:navigation.value.view==='list'?7000:navigation.value.view==='create'?(create.value?.needsRefresh?2000:0):(detail.value?.needsRefresh?2000:0));
const title=computed(()=>navigation.value.view==='list'?'批量任务':navigation.value.view==='create'?'新建批次':`批次 #${navigation.value.batch_id}`);
function syncVisibility(){
 hostVisible.value=!document.hidden&&(props.deps.isVisible?.()??true);
 if(lastVisible!==visible.value){visibilityEpoch++;lastVisible=visible.value;}
 list.value?.setVisible(visible.value&&navigation.value.view==='list');
 create.value?.setVisible(visible.value&&navigation.value.view==='create');
 detail.value?.setVisible(visible.value&&navigation.value.view==='detail');
}
function schedule(){clearTimeout(timer);timer=undefined;if(disposed||!delay.value)return;timer=setTimeout(()=>{timer=undefined;syncVisibility();if(visible.value)void refresh(false);},delay.value);}
async function refresh(force=true):Promise<void>{
 await nextTick();if(disposed)return;syncVisibility();if(!visible.value)return;
 const key=JSON.stringify([navigation.value,visibilityEpoch]);if(refreshing&&refreshKey===key)return refreshing;
 const task=(async()=>{try{
  if(navigation.value.view==='list')await list.value?.refresh(!force);
  else if(navigation.value.view==='create')await create.value?.refresh(force);
  else{await detail.value?.refresh(force);if(focusReport){focusReport=false;await detail.value?.showReport();}}
 }finally{pendingRevision.value++;}})();
 refreshing=task;refreshKey=key;
 try{await task;}finally{if(refreshing===task){refreshing=null;refreshKey='';}schedule();}
}
async function activate(){active.value=true;await refresh(false);}
async function showReport(){
 await nextTick();
 if(visible.value&&navigation.value.view==='detail')await detail.value?.showReport();
}
function setVisible(value:boolean){active.value=value;syncVisibility();schedule();}
function navigationState():BulkNavigation{return{...navigation.value};}
function restoreNavigation(value:Partial<BulkNavigation>){navigationEpoch++;navigation.value=normalizeBulkNavigation(value);error.value='';notice.value='';focusReport=false;}
async function navigate(view:BulkNavigation['view'],extra:Partial<BulkNavigation>={},report=false){
 restoreNavigation({tab:'bulk',view,...extra});focusReport=report;active.value=true;
 props.deps.onNavigation(navigationState(),'push');await refresh(false);
}
async function updateNavigation(extra:Partial<BulkNavigation>){
 navigationEpoch++;
 navigation.value=normalizeBulkNavigation({...navigation.value,...extra});
 props.deps.onNavigation(navigationState(),Object.keys(extra).every(key=>key==='cursor')?'replace':'push');await nextTick();schedule();
}
async function openDraft(query:AccountQuerySpec,source:BulkRecord|null,operationKey='plan_check'){
 const frozen=JSON.parse(JSON.stringify({query,source})) as {query:AccountQuerySpec;source:BulkRecord|null};
 seed.value={name:'',operation_key:operationKey,query:props.deps.adapter.normalize({...frozen.query,limit:null}),source:frozen.source,parameters:{},max_concurrency:3};
 await navigate('create');
}
async function fromAccounts(selected=false,operationKey='plan_check',snapshot?:{ids:readonly (string|number)[];query:AccountQuerySpec}){
 if(!snapshot){callbacks.notify('账号范围未就绪，请返回账号页重试');return;}
 const ids=selected?snapshot.ids.map(value=>bulkId(typeof value==='number'&&Number.isSafeInteger(value)?String(value):value)):[];
 if(selected&&!ids.length){callbacks.notify('请先选择账号');return;}
 await openDraft(snapshot.query,selected?{kind:'ids',entity:'account',ids}:null,operationKey);
}
async function newBatch(){await openDraft(props.deps.adapter.normalize(),null);}
async function restoreSelectionRequest(body:BulkRecord,result:BulkRecord){await nextTick();create.value?.restoreSelectionRequest(body,result);}
async function recover(){
 if(recovering.value)return;recovering.value=true;error.value='';const ticket=navigationEpoch;
 try{const saved=props.deps.intents.pending()[0];if(!saved)return;const result=await props.deps.intents.recover(saved);
  if(disposed||ticket!==navigationEpoch||!visible.value){
   const id=result.id||result.batch_id||result.round_id;
   callbacks.notify(saved.path==='/batches'?`原批次 #${bulkId(id)} 已创建`:`原请求回执已找回${id?'，编号 #'+String(id):''}。`);return;
  }
  if(saved.path==='/selections'){seed.value=null;await restoreSelectionRequest(saved.body,result);await navigate('create');callbacks.notify('已找回原账号范围，新批次使用配置页已保存的设置。');}
  else if(saved.path==='/batches'){try{props.deps.storage.removeItem('turb_bulk_selection_v1');}catch{/* The accepted receipt is authoritative even when local cleanup is unavailable. */}await navigate('detail',{batch_id:bulkId(result.id||result.batch_id)});}
  else{const match=saved.path.match(/^\/batches\/([1-9]\d*)\//);if(match)await navigate('detail',{batch_id:match[1]});callbacks.notify('原请求回执已找回。');}
 }catch(cause){error.value=cause instanceof Error?cause.message:String(cause);}finally{recovering.value=false;pendingRevision.value++;}
}
function visibilityChanged(){const was=visible.value;syncVisibility();if(!was&&visible.value)void refresh(false);else schedule();}
watch(delay,schedule,{flush:'post'});
onMounted(()=>{syncVisibility();document.addEventListener('visibilitychange',visibilityChanged);});
onBeforeUnmount(()=>{disposed=true;clearTimeout(timer);document.removeEventListener('visibilitychange',visibilityChanged);});
defineExpose({activate,setVisible,refresh,showReport,navigationState,restoreNavigation,navigate,fromAccounts,recover,restoreSelectionRequest});
</script>
<template>
 <div class="bulk-page bulk-page-shell" data-bulk-vue :data-bulk-view="navigation.view">
  <header class="bulk-page-heading"><h2 data-bulk-title>{{title}}</h2><div class="bulk-actions"><button v-if="navigation.view!=='list'" type="button" class="jobs-tb-btn" @click="navigate('list')">批次列表</button><button type="button" class="jobs-tb-btn" data-bulk-action="refresh" @click="refresh(true)">刷新</button><button type="button" class="jobs-tb-btn jobs-tb-btn--primary" data-bulk-action="new" @click="newBatch">新建批次</button></div></header>
  <p v-if="error" class="bulk-error" data-bulk-error role="alert">{{error}}</p>
  <p v-if="notice" class="bulk-notice" data-bulk-notice role="status">{{notice}}</p>
  <div v-if="pending.length&&navigation.view!=='create'" class="bulk-notice bulk-global-recovery" data-bulk-recovery role="status"><span>有 {{pending.length}} 个请求未收到回执，草稿已保留。</span><button type="button" class="jobs-tb-btn" :disabled="recovering" @click="recover">{{recovering?'正在找回…':'找回原请求'}}</button></div>
  <div data-bulk-content>
   <BulkList v-show="navigation.view==='list'" ref="list" :navigation="navigation" :deps="listDeps"/>
   <BulkCreate v-show="navigation.view==='create'" ref="create" :navigation="navigation" :deps="createDeps" :seed="seed" :visible="visible&&navigation.view==='create'"/>
   <BulkDetail v-show="navigation.view==='detail'" ref="detail" :navigation="navigation" :deps="detailDeps" :visible="visible&&navigation.view==='detail'"/>
  </div>
 </div>
</template>
<style scoped>
.bulk-page-shell{min-width:0}.bulk-page-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.bulk-page-heading h2{font-size:19px;margin:0}.bulk-global-recovery{display:flex;align-items:center;gap:12px;flex-wrap:wrap}@media(max-width:680px){.bulk-page-heading{align-items:flex-start;flex-wrap:wrap}.bulk-page-heading .bulk-actions{flex-wrap:wrap}}
</style>
