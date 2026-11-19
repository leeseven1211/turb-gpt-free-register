// Run the actual Vue owner/components and request clients with an in-memory HTTP boundary.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {createVueHarness}=require('../frontend_vue_loader.cjs');
const harness=createVueHarness();
const {effectScope,ref,watch}=require('../../frontend/node_modules/vue');
const {flushPromises,DOMWrapper}=require('../../frontend/node_modules/@vue/test-utils');
for(const name of ['Document','ShadowRoot','HTMLButtonElement','HTMLInputElement','HTMLSelectElement','NodeFilter','XMLSerializer']){
 Object.defineProperty(globalThis,name,{configurable:true,writable:true,value:harness.document.defaultView[name]});
}
const queryContext={window:{},URLSearchParams};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../webui/static/js/shared/account-query.js'),'utf8'),queryContext);
const AccountQuery=queryContext.window.AccountQuery;
const adapter=harness.load('src/features/accounts/queryAdapter.ts').createAccountQueryAdapter(AccountQuery);
const {createBulkApi,BulkApiError}=harness.load('src/api/bulk.ts');
const {createBulkIntent}=harness.load('src/features/bulk/useBulkIntent.ts');
const {useBulkCreate}=harness.load('src/features/bulk/useBulkCreate.ts');
const {useBulkDetail}=harness.load('src/features/bulk/useBulkDetail.ts');
const {normalizeBulkNavigation}=harness.load('src/features/bulk/navigation.ts');
const presentation=harness.load('src/features/bulk/bulkDetailPresentation.ts');
const plain=value=>JSON.parse(JSON.stringify(value));
function deferred(){let resolve,reject;const promise=new Promise((done,fail)=>{resolve=done;reject=fail;});return{promise,resolve,reject};}
function storage(saved={}){
 const values=new Map(Object.entries(saved).map(([key,value])=>[key,JSON.stringify(value)]));
 return{getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key),key:index=>[...values.keys()][index]??null,get length(){return values.size;}};
}
function catalog(){return{operations:[{key:'plan_check',version:1,label:'查套餐',effective_settings:{config_revision:'fixture-v1'},parameter_schema:{timezone_offset_min:{type:'integer'}}},{key:'token_refresh',version:1,label:'刷新 AT'}],query_schema:{fields:[]},limits:{concurrency_max:128}};}
const facetLabel=(_group,value)=>({none:'无优惠',free_trial:'免费试用',other_promo:'其他优惠',expired:'已过期',has:'有 Token',outlook:'Outlook',icloud_hide:'iCloud Hide'}[value]||value);
function dependencies(saved={},overrides={}){
 const store=storage(saved),calls=[],navigations=[],notices=[],updates=[];
 const handlers={
  read:async route=>route==='/catalog'?catalog():route.startsWith('/query-facets')?{facets:{source:[{value:'outlook'}]},matched:500}:{id:'9007199254740993',state:'ready',target_count:5,selection_revision:2},
  post:async route=>route==='/selections'?{id:'9007199254740993',state:'preparing'}:{id:'9007199254740997'},
  ...overrides,
 };
 const api=createBulkApi(async(url,options={})=>{
  const route=url.replace(/^\/api\/bulk/,''),body=options.body?JSON.parse(options.body):undefined;
  calls.push({url,path:route,options,body,method:options.method||'GET'});
  try{const data=await(body?handlers.post(route,body,options):handlers.read(route,options));return{ok:true,status:200,json:async()=>({ok:true,data})};}
  catch(error){if(error instanceof BulkApiError&&error.status)return{ok:false,status:error.status,json:async()=>({ok:false,error:{code:error.code,message:error.message,details:error.details,field:error.field}})};throw error;}
 });
 let key=0,time=100000;
 const callbacks={navigate:(view,extra)=>navigations.push({view,...extra}),notify:value=>notices.push(value),updateNavigation:extra=>updates.push(extra),formatDateTime:String,facetLabel,openTask(){}};
 const deps={adapter,api,intents:createBulkIntent(api,store,()=>`fixture-key-${++key}`),storage:store,callbacks,now:()=>time};
 return{deps,store,calls,handlers,navigations,notices,updates,setTime:value=>{time=value;},writes:()=>calls.filter(call=>call.method==='POST')};
}
function createFixture(t,{saved={},handlers={},mounted=false,seed=null}={}){
 const h=dependencies(saved,handlers);let scope;
 if(mounted)h.wrapper=harness.mount(harness.load('src/features/bulk/BulkCreate.vue').default,{props:{navigation:{tab:'bulk',view:'create'},deps:h.deps,seed}});
 else{scope=effectScope();h.owner=scope.run(()=>useBulkCreate(h.deps));}
 t.after(()=>{scope?.stop();h.wrapper?.unmount();});
 h.draft=extra=>({name:'本批测试',operation_key:'plan_check',query:adapter.normalize({filters:{promotion:['none']}}),source:null,parameters:{},max_concurrency:3,...extra});
 h.initialize=async()=>{if(h.owner)await h.owner.initialize();else await flushPromises();};
 h.refresh=async()=>{await(h.owner?h.owner.refresh():h.wrapper.vm.refresh());await flushPromises();};
 return h;
}
async function detailFixture(t,{navigation={},detail={},targets=[],handlers={},mounted=false}={}){
 const nav=ref({tab:'bulk',view:'detail',batch_id:'71',...navigation});
 const data={operation:{key:'plan_check'},target_count:5,summary_revision:1,control:{state:'active',revision:7},summary:{queued:3},rounds_head:[],...detail};
 const h=dependencies({},{
  read:async route=>route.includes('/targets?')?{items:targets,page:{has_more:false,page_size:50}}:route.includes('/report?')?{operation_key:'plan_check',phase:'running',view:{kind:'current'}}:plain(data),
  ...handlers,
 });
 h.deps.callbacks.updateNavigation=extra=>{h.updates.push(extra);nav.value={...nav.value,...extra};};
 let scope;
 if(mounted){h.wrapper=harness.mount(harness.load('src/features/bulk/BulkDetail.vue').default,{props:{navigation:nav.value,deps:h.deps}});scope=effectScope();scope.run(()=>watch(nav,value=>{void h.wrapper.setProps({navigation:value});},{flush:'sync'}));}
 else{scope=effectScope();h.owner=scope.run(()=>useBulkDetail(()=>nav.value,h.deps));}
 t.after(()=>{scope?.stop();h.wrapper?.unmount();});await flushPromises();
 return{...h,navigation:nav,data};
}
module.exports={harness,AccountQuery,adapter,createBulkApi,BulkApiError,createBulkIntent,normalizeBulkNavigation,presentation,plain,deferred,storage,catalog,dependencies,createFixture,detailFixture,flushPromises,DOMWrapper,effectScope,ref,watch};
