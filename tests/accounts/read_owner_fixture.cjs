// Legacy regression cases use the production Vue read owner and list component.
const {vueHarness: vue} = require('./actions_fixture.cjs');
const {effectScope} = require('../../frontend/node_modules/vue');
const {DOMWrapper,flushPromises} = require('../../frontend/node_modules/@vue/test-utils');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const sandbox = {window: {}, URLSearchParams};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../webui/static/js/shared/account-query.js'), 'utf8'), sandbox);
const adapter = vue.load('src/features/accounts/queryAdapter.ts').createAccountQueryAdapter(sandbox.window.AccountQuery);
const {useAccounts} = vue.load('src/features/accounts/useAccounts.ts');
const {ApiError} = vue.load('src/api/client.ts');
const plain = value => JSON.parse(JSON.stringify(value));
const row = (id = 1, values = {}) => ({id,email:`account-${id}@example.test`,has_access_token:false,has_account_password:false,totp_enabled:false,email_invalid:false,...values});
const list = (items = [row()], values = {}) => ({ok:true,compact:true,items,total:items.length,page:1,page_size:10,offset:0,limit:10,revision:'full',facets:{},search_terms:[],...values});
const statusRow = (id = 1, values = {}) => ({id,plan_details_revision:'v1',plan_summary:{promotions:[],countries:[]},...values});
const status = (items = [statusRow()], values = {}) => ({ok:true,items,total:items.length,page:1,page_size:10,offset:0,limit:10,revision:'status',status_fields:[],queue:{workers:1,registration_workers:1,queue_limit:100,min_interval:0,jitter:0},...values});
function deferred(){let resolve,reject;const promise=new Promise((done,fail)=>{resolve=done;reject=fail;});return{promise,resolve,reject};}
const presentation = {cell:(_key,value)=>`<span>${value.email||value.id}</span>`,menu:()=>'',emailInvalidBadge:()=>'',registrationDriverLabel:value=>value||'未记录',facetLabel:(_group,value)=>value, mobileSummary:()=>'',rowTone:()=> 'ok'};
function createReadFixture(t, {mounted = false, handlers = {}, render = presentation} = {}) {
  Object.defineProperty(vue.document,'hidden',{configurable:true,value:false});
  const requests = [], statusRequests = [], detailsRequests = [];
  const behavior = {list: async () => list(), statuses: async () => status(), planDetails: async () => ({ok:true,item:{}}), ...handlers};
  const api = {
    list(spec,page,size,signal){const call={spec:plain(spec),page,size,signal};requests.push(call);return behavior.list(call);},
    statuses(spec,page,size,signal){const call={spec:plain(spec),page,size,signal};statusRequests.push(call);return behavior.statuses(call);},
    planDetails(id,signal){const call={id,signal};detailsRequests.push(call);return behavior.planDetails(call);},
  };
  const calls=[],callbacks={invoke:(...args)=>calls.push(args),openDetail(){}};
  let scope,owner,wrapper;const prior = new Map();
  if(mounted){
    vue.cleanup();
    for(const name of ['Document','ShadowRoot','HTMLButtonElement','HTMLInputElement']){prior.set(name,Object.getOwnPropertyDescriptor(globalThis,name));Object.defineProperty(globalThis,name,{configurable:true,writable:true,value:vue.document.defaultView[name]});}
    wrapper=vue.mount(vue.load('src/features/accounts/AccountsList.vue').default,{props:{adapter,api,presentation:render,callbacks}});owner=wrapper.vm;
  }else{scope=effectScope();owner=scope.run(()=>useAccounts(adapter,api));}
  t.after(()=>{scope?.stop();if(wrapper){vue.cleanup();for(const [name,descriptor] of prior){if(descriptor)Object.defineProperty(globalThis,name,descriptor);else delete globalThis[name];}}});
  owner.setVisible(true);
  return{owner,wrapper,body:new DOMWrapper(vue.document.body),requests,statusRequests,detailsRequests,behavior,api,adapter,plain,calls,ready:flushPromises(),settle:flushPromises,
    params(call=requests.at(-1)){return adapter.toLegacy(call.spec,{paged:'1',page:call.page,page_size:call.size});}};
}
module.exports={createReadFixture,adapter,vue,row,list,status,statusRow,deferred,plain,ApiError,presentation};
